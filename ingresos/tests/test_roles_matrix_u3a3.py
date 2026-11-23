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
from app import models, financial_models, rbac_models  # noqa: F401
from app.models import Company, CompanyUser, User
from app.financial_models import Account, AccountConcept, Concept
from app.rbac import PERMISSION_MATRIX, assign_role_internal, seed_rbac
from app.rbac_models import CompanyUserRoleModel, PermissionModel, RoleModel, RolePermissionModel
from app.schema import schema
from app.security import create_access_token
import app.schema as schema_module


class RolesMatrixActivity3Test(unittest.TestCase):
    def setUp(self):
        self.secret_patch = patch.dict(os.environ, {"JWT_SECRET": secrets.token_hex(32)})
        self.secret_patch.start()
        self.temporary = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary.name) / "u3a3.sqlite"
        self.engine = create_engine(f"sqlite:///{self.database_path}")
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine, autoflush=False)
        with self.session_factory() as db:
            company = Company(name="Empresa Demo")
            db.add(company)
            db.flush()
            seed_rbac(db)
            roles = {r.code: r for r in db.scalars(select(RoleModel)).all()}
            self.roles = {code: str(r.id) for code, r in roles.items()}
            self.permissions = {p.code: str(p.id) for p in db.scalars(select(PermissionModel)).all()}
            self.company_id = str(company.id)

            self.members = {}
            self.tokens = {}
            for key, name, email, role_code, is_admin in [
                ("admin", "Ana López", "ana@demo.mx", "ADMINISTRADOR", True),
                ("contador", "Luis Herrera", "luis@demo.mx", "CONTADOR", False),
                ("capturista1", "María Ruiz", "maria@demo.mx", "CAPTURISTA", False),
                ("capturista2", "José Paz", "jose@demo.mx", "CAPTURISTA", False),
                ("consulta", "Pedro León", "pedro@demo.mx", "CONSULTA", False),
            ]:
                user = User(name=name, email=email, password_hash="hash-demo")
                db.add(user)
                db.flush()
                member = CompanyUser(company_id=company.id, user_id=user.id, is_admin=is_admin)
                db.add(member)
                db.flush()
                assign_role_internal(db, member, roles[role_code])
                self.members[key] = str(member.id)
                self.tokens[key] = create_access_token(member.id, company.id)

            account = Account(company_id=company.id, account_type="CASH", name="Caja Principal")
            concept = Concept(company_id=company.id, concept_type="INCOME", name="Venta")
            db.add_all([account, concept])
            db.flush()
            db.add(AccountConcept(account_id=account.id, concept_id=concept.id))
            db.commit()
            self.account_id = str(account.id)
            self.concept_id = str(concept.id)

        self.original_sessions = schema_module.SessionLocal
        schema_module.SessionLocal = self.session_factory

    def tearDown(self):
        self.secret_patch.stop()
        schema_module.SessionLocal = self.original_sessions
        self.engine.dispose()
        self.temporary.cleanup()

    def execute(self, query, actor_key=None, variables=None):
        headers = {}
        if actor_key is not None:
            headers["authorization"] = f"Bearer {self.tokens[actor_key]}"
        return schema.execute_sync(
            query,
            variable_values=variables or {},
            context_value={"request": SimpleNamespace(headers=headers)},
        )

    def test_matrix_queries_require_token_and_roles_read(self):
        q = """query Matriz($roleId: ID!) {
          roles(activeOnly: true) { id code name }
          permissions(activeOnly: true) { id code name }
          rolePermissions(roleId: $roleId) { isActive permission { id code } }
        }"""
        variables = {"roleId": self.roles["CAPTURISTA"]}

        # Sin token: rechazado
        unauth = self.execute(q, None, variables)
        self.assertIsNotNone(unauth.errors)

        # Capturista y Consulta: rechazados por falta de roles.read
        for actor in ("capturista1", "consulta"):
            denied = self.execute(q, actor, variables)
            self.assertIsNotNone(denied.errors)
            self.assertIn("roles.read", str(denied.errors[0]))

        # Admin y Contador: permitidos y coinciden con sección 2.2
        for actor in ("admin", "contador"):
            ok = self.execute(q, actor, variables)
            self.assertIsNone(ok.errors)
            codes = sorted(rp["permission"]["code"] for rp in ok.data["rolePermissions"] if rp["isActive"])
            self.assertEqual(codes, sorted(PERMISSION_MATRIX["CAPTURISTA"]))

    def test_column_change_affects_all_capturistas_and_is_idempotent(self):
        create_account = """mutation($input: CreateAccountInput!) {
          createAccount(input: $input) { id name }
        }"""
        # Antes del cambio, ninguno de los capturistas puede crear cuenta
        for cap in ("capturista1", "capturista2"):
            res = self.execute(create_account, cap, {
                "input": {"companyId": self.company_id, "accountType": "CASH", "name": f"Nueva {cap}"}
            })
            self.assertIsNotNone(res.errors)

        # Vista previa y guardado de Capturista sumando accounts.write
        desired_codes = ["accounts.read", "accounts.write", "concepts.read", "transactions.read", "transactions.write"]
        desired_ids = [self.permissions[c] for c in desired_codes]

        preview = self.execute(
            """query($input: SetRolePermissionsInput!) {
              previewRolePermissions(input: $input) {
                toActivate { code } toDeactivate { code } unchanged { code } finalCount
              }
            }""",
            "admin",
            {"input": {"roleId": self.roles["CAPTURISTA"], "permissionIds": desired_ids}},
        )
        self.assertIsNone(preview.errors)
        self.assertEqual(preview.data["previewRolePermissions"]["toActivate"], [{"code": "accounts.write"}])
        self.assertEqual(preview.data["previewRolePermissions"]["toDeactivate"], [])
        self.assertEqual(len(preview.data["previewRolePermissions"]["unchanged"]), 4)
        self.assertEqual(preview.data["previewRolePermissions"]["finalCount"], 5)

        save_mut = """mutation($input: SetRolePermissionsInput!) {
          setRolePermissions(input: $input) {
            activated { code } deactivated { code } finalCount changed
          }
        }"""
        first = self.execute(save_mut, "admin", {"input": {"roleId": self.roles["CAPTURISTA"], "permissionIds": desired_ids}})
        self.assertIsNone(first.errors)
        self.assertTrue(first.data["setRolePermissions"]["changed"])
        self.assertEqual(first.data["setRolePermissions"]["finalCount"], 5)

        # Segundo guardado de la misma columna: changed=False sin duplicar filas
        second = self.execute(save_mut, "admin", {"input": {"roleId": self.roles["CAPTURISTA"], "permissionIds": desired_ids}})
        self.assertIsNone(second.errors)
        self.assertFalse(second.data["setRolePermissions"]["changed"])
        self.assertEqual(second.data["setRolePermissions"]["finalCount"], 5)

        # Ambos capturistas ahora pueden crear cuenta con el mismo token
        for cap in ("capturista1", "capturista2"):
            res = self.execute(create_account, cap, {
                "input": {"companyId": self.company_id, "accountType": "CASH", "name": f"Nueva {cap}"}
            })
            self.assertIsNone(res.errors)

    def test_contador_cannot_save_matrix_or_assign_role_and_admin_column_protected(self):
        save_mut = """mutation($input: SetRolePermissionsInput!) {
          setRolePermissions(input: $input) { changed }
        }"""
        denied = self.execute(
            save_mut,
            "contador",
            {"input": {"roleId": self.roles["CAPTURISTA"], "permissionIds": [self.permissions["accounts.read"]]}},
        )
        self.assertIsNotNone(denied.errors)
        self.assertIn("roles.write", str(denied.errors[0]))

        admin_blocked = self.execute(
            save_mut,
            "admin",
            {"input": {"roleId": self.roles["ADMINISTRADOR"], "permissionIds": [self.permissions["accounts.read"]]}},
        )
        self.assertIsNotNone(admin_blocked.errors)

    def test_assign_role_changes_user_without_touching_matrix_or_is_admin(self):
        assign_mut = """mutation($input: AssignRoleInput!) {
          assignRole(input: $input) { isActive role { code name } }
        }"""
        # Pedro (Consulta) pasa a Capturista
        res = self.execute(
            assign_mut,
            "admin",
            {"input": {"companyUserId": self.members["consulta"], "roleId": self.roles["CAPTURISTA"]}},
        )
        self.assertIsNone(res.errors)
        self.assertEqual(res.data["assignRole"]["role"]["code"], "CAPTURISTA")

        with self.session_factory() as db:
            member = db.get(CompanyUser, int(self.members["consulta"]))
            self.assertFalse(member.is_admin)
            active_roles = db.scalars(select(CompanyUserRoleModel).where(
                CompanyUserRoleModel.company_user_id == member.id,
                CompanyUserRoleModel.is_active.is_(True),
            )).all()
            self.assertEqual(len(active_roles), 1)
            consulta_perms = sorted(db.scalars(
                select(PermissionModel.code).join(RolePermissionModel).where(
                    RolePermissionModel.role_id == int(self.roles["CONSULTA"]),
                    RolePermissionModel.is_active.is_(True),
                )
            ).all())
            self.assertEqual(consulta_perms, sorted(PERMISSION_MATRIX["CONSULTA"]))

        # Con el mismo token ya puede registrar movimiento
        tx_res = self.execute(
            """mutation($input: CreateTransactionInput!) {
              createTransaction(input: $input) { id }
            }""",
            "consulta",
            {
                "input": {
                    "accountId": self.account_id,
                    "conceptId": self.concept_id,
                    "transactionType": "INCOME",
                    "amount": "150.00",
                    "transactionDate": "2026-10-28T10:00:00",
                    "shortDescription": "Prueba cambio de puesto",
                    "idempotencyKey": "11111111-1111-4111-8111-111111111111",
                }
            },
        )
        self.assertIsNone(tx_res.errors)


if __name__ == "__main__":
    unittest.main()
