import os
import secrets
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.demo import seed_demo
from app.financial_models import Account, AccountConcept, Concept
from app.models import CompanyUser
from app.schema import schema
import app.schema as schema_module
from app.security import create_access_token


class AdminOperationsTest(unittest.TestCase):
    def setUp(self):
        self.secret = secrets.token_hex(32)
        self.env = patch.dict(os.environ, {"JWT_SECRET": self.secret})
        self.env.start()
        self.temp = tempfile.TemporaryDirectory()
        self.engine = create_engine(f"sqlite:///{Path(self.temp.name) / 'admin.sqlite'}")
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine, autoflush=False)
        self.session_patch = patch.object(schema_module, "SessionLocal", self.sessions)
        self.session_patch.start()
        with self.sessions() as db:
            self.members = seed_demo(db, "secreto-pruebas-admin")
        self.tokens = {
            key.split("@")[0]: create_access_token(*ids)
            for key, ids in self.members.items()
        }
        self.company_id = str(self.members["admin@dashboard.example.com"][1])

    def tearDown(self):
        self.session_patch.stop()
        self.engine.dispose()
        self.temp.cleanup()
        self.env.stop()

    def execute(self, query, token="admin", variables=None):
        headers = {"authorization": f"Bearer {self.tokens[token]}"} if token else {}
        return schema.execute_sync(
            query,
            variable_values=variables,
            context_value={"request": SimpleNamespace(headers=headers)},
        )

    def test_me_and_company_users_include_role(self):
        me = self.execute("query { me { companyId companyName isAdmin role { code name } permissions } }")
        self.assertIsNone(me.errors, me.errors)
        self.assertEqual(me.data["me"]["role"]["code"], "ADMINISTRADOR")
        self.assertIn("company.users.write", me.data["me"]["permissions"])
        users = self.execute(
            "query { companyUsers { id isAdmin isActive user { name email } role { code name } } }"
        )
        self.assertIsNone(users.errors, users.errors)
        self.assertGreaterEqual(len(users.data["companyUsers"]), 3)
        admin_rows = [row for row in users.data["companyUsers"] if row["isAdmin"]]
        self.assertEqual(len(admin_rows), 1)
        self.assertEqual(admin_rows[0]["role"]["code"], "ADMINISTRADOR")

    def test_create_user_duplicate_and_deactivate(self):
        created = self.execute(
            '''mutation($input: CreateCompanyUserInput!) {
              createCompanyUser(input: $input) { id isActive isAdmin user { email } role { code } }
            }''',
            variables={
                "input": {
                    "companyId": self.company_id,
                    "name": "Usuario nuevo",
                    "email": "nuevo@dashboard.example.com",
                    "password": "secreto123",
                }
            },
        )
        self.assertIsNone(created.errors, created.errors)
        self.assertFalse(created.data["createCompanyUser"]["isAdmin"])
        self.assertEqual(created.data["createCompanyUser"]["role"]["code"], "CONSULTA")
        member_id = created.data["createCompanyUser"]["id"]

        duplicate = self.execute(
            '''mutation($input: CreateCompanyUserInput!) {
              createCompanyUser(input: $input) { id }
            }''',
            variables={
                "input": {
                    "companyId": self.company_id,
                    "name": "Duplicado",
                    "email": "nuevo@dashboard.example.com",
                    "password": "secreto123",
                }
            },
        )
        self.assertIsNotNone(duplicate.errors)
        self.assertIn("correo", duplicate.errors[0].message.lower())

        deactivated = self.execute(
            f'mutation {{ deactivateCompanyUser(id: "{member_id}") {{ id isActive }} }}'
        )
        self.assertIsNone(deactivated.errors, deactivated.errors)
        self.assertFalse(deactivated.data["deactivateCompanyUser"]["isActive"])
        with self.sessions() as db:
            row = db.get(CompanyUser, int(member_id))
            self.assertIsNotNone(row)
            self.assertFalse(row.is_active)

    def test_second_admin_is_rejected(self):
        result = self.execute(
            '''mutation($input: CreateCompanyAdminInput!) {
              createCompanyAdmin(input: $input) { id }
            }''',
            variables={
                "input": {
                    "companyId": self.company_id,
                    "name": "Otro admin",
                    "email": "otro-admin@dashboard.example.com",
                    "password": "secreto123",
                }
            },
        )
        self.assertIsNotNone(result.errors)
        self.assertIn("administrador principal", result.errors[0].message.lower())

    def test_accounts_and_concepts_flow(self):
        account = self.execute(
            '''mutation($input: CreateAccountInput!) {
              createAccount(input: $input) { id name accountType bankName isActive }
            }''',
            variables={
                "input": {
                    "companyId": self.company_id,
                    "accountType": "WALLET",
                    "name": "Monedero demo",
                    "bankName": None,
                    "clabe": None,
                    "shortDescription": "Cuenta de prueba admin",
                }
            },
        )
        self.assertIsNone(account.errors, account.errors)
        account_id = account.data["createAccount"]["id"]

        concept = self.execute(
            '''mutation($input: CreateConceptInput!) {
              createConcept(input: $input) { id name conceptType isActive }
            }''',
            variables={
                "input": {
                    "companyId": self.company_id,
                    "conceptType": "EXPENSE",
                    "name": "Renta oficina",
                    "shortDescription": "Egreso de prueba",
                }
            },
        )
        self.assertIsNone(concept.errors, concept.errors)
        concept_id = concept.data["createConcept"]["id"]

        assigned = self.execute(
            '''mutation($input: AssignConceptToAccountInput!) {
              assignConceptToAccount(input: $input) { id isActive concept { id } }
            }''',
            variables={"input": {"accountId": account_id, "conceptId": concept_id}},
        )
        self.assertIsNone(assigned.errors, assigned.errors)

        duplicate = self.execute(
            '''mutation($input: AssignConceptToAccountInput!) {
              assignConceptToAccount(input: $input) { id }
            }''',
            variables={"input": {"accountId": account_id, "conceptId": concept_id}},
        )
        self.assertIsNotNone(duplicate.errors)
        self.assertIn("ya está asignado", duplicate.errors[0].message.lower())

        removed = self.execute(
            f'mutation {{ removeConceptFromAccount(accountId: "{account_id}", conceptId: "{concept_id}") }}'
        )
        self.assertIsNone(removed.errors, removed.errors)
        self.assertTrue(removed.data["removeConceptFromAccount"])

        with self.sessions() as db:
            concept_row = db.get(Concept, int(concept_id))
            self.assertTrue(concept_row.is_active)
            relation = db.scalar(
                select(AccountConcept).where(
                    AccountConcept.account_id == int(account_id),
                    AccountConcept.concept_id == int(concept_id),
                )
            )
            self.assertFalse(relation.is_active)

    def test_read_only_user_cannot_write(self):
        denied_users = self.execute(
            '''mutation($input: CreateCompanyUserInput!) {
              createCompanyUser(input: $input) { id }
            }''',
            token="consulta",
            variables={
                "input": {
                    "companyId": self.company_id,
                    "name": "No permitido",
                    "email": "nopermitido@dashboard.example.com",
                    "password": "secreto123",
                }
            },
        )
        self.assertIsNotNone(denied_users.errors)
        self.assertIn("company.users.write", denied_users.errors[0].message)

        denied_account = self.execute(
            '''mutation($input: CreateAccountInput!) {
              createAccount(input: $input) { id }
            }''',
            token="consulta",
            variables={
                "input": {
                    "companyId": self.company_id,
                    "accountType": "CASH",
                    "name": "Caja no permitida",
                }
            },
        )
        self.assertIsNotNone(denied_account.errors)
        self.assertIn("accounts.write", denied_account.errors[0].message)

    def test_company_isolation(self):
        empty = self.execute("query { companyUsers { id user { email } } }", token="vacia")
        self.assertIsNone(empty.errors, empty.errors)
        emails = {row["user"]["email"] for row in empty.data["companyUsers"]}
        self.assertEqual(emails, {"vacia@dashboard.example.com"})
        accounts = self.execute("query { accounts { id } }", token="vacia")
        self.assertIsNone(accounts.errors, accounts.errors)
        self.assertEqual(accounts.data["accounts"], [])


if __name__ == "__main__":
    unittest.main()
