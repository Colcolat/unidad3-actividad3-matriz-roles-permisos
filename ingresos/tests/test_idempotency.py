import os
import secrets
import tempfile
import threading
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.demo import seed_demo
from app.financial_models import Account, Concept, IdempotencyKey, Transaction
from app.models import CompanyUser
from app.rbac import assign_role_internal
from app.rbac_models import RoleModel
from app.schema import schema
import app.schema as schema_module
from app.security import create_access_token


MUTATION = """
mutation($input: CreateTransactionInput!) {
  createTransaction(input: $input) {
    id
    accountId
    conceptId
    transactionType
    amount
  }
}
"""


class IdempotencyTest(unittest.TestCase):
    def setUp(self):
        self.secret = secrets.token_hex(32)
        self.env = patch.dict(os.environ, {"JWT_SECRET": self.secret})
        self.env.start()
        self.temp = tempfile.TemporaryDirectory()
        self.engine = create_engine(
            f"sqlite:///{Path(self.temp.name) / 'idempotency.sqlite'}",
            connect_args={"check_same_thread": False},
        )

        @event.listens_for(self.engine, "connect")
        def _fk(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        self.session_patch = patch.object(schema_module, "SessionLocal", self.sessions)
        self.session_patch.start()
        with self.sessions() as db:
            members = seed_demo(db, secrets.token_urlsafe(12))
            role = db.scalar(select(RoleModel).where(RoleModel.code == "CAPTURISTA"))
            membership = db.get(CompanyUser, members["consulta@dashboard.example.com"][0])
            assign_role_internal(db, membership, role)
            db.commit()
            accounts = db.scalars(select(Account)).all()
            concepts = {item.concept_type: item for item in db.scalars(select(Concept)).all()}
            self.account_id = str(accounts[0].id)
            self.income_id = str(concepts["INCOME"].id)
            self.expense_id = str(concepts["EXPENSE"].id)
            self.company_id = members["consulta@dashboard.example.com"][1]
        self.token = create_access_token(*members["consulta@dashboard.example.com"])

    def tearDown(self):
        self.session_patch.stop()
        self.engine.dispose()
        self.temp.cleanup()
        self.env.stop()

    def execute(self, variables):
        return schema.execute_sync(
            MUTATION,
            variable_values=variables,
            context_value={
                "request": SimpleNamespace(headers={"authorization": f"Bearer {self.token}"})
            },
        )

    def base_input(self, **overrides):
        payload = {
            "accountId": self.account_id,
            "conceptId": self.expense_id,
            "transactionType": "EXPENSE",
            "amount": "100.00",
            "idempotencyKey": str(uuid.uuid4()),
            "shortDescription": "Prueba de idempotencia",
        }
        payload.update(overrides)
        return payload

    def test_first_execution_creates_transaction_and_key(self):
        key = str(uuid.uuid4())
        result = self.execute({"input": self.base_input(idempotencyKey=key)})
        self.assertIsNone(result.errors, result.errors)
        created_id = result.data["createTransaction"]["id"]
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Transaction)), 10)
            recorded = db.scalar(
                select(IdempotencyKey).where(IdempotencyKey.idempotency_key == key)
            )
            self.assertIsNotNone(recorded)
            self.assertEqual(str(recorded.resource_id), created_id)
            self.assertEqual(recorded.company_id, self.company_id)
            self.assertEqual(recorded.operation, "createTransaction")

    def test_retry_same_key_same_payload_returns_same_id(self):
        key = str(uuid.uuid4())
        payload = self.base_input(idempotencyKey=key)
        first = self.execute({"input": payload})
        second = self.execute({"input": payload})
        self.assertIsNone(first.errors, first.errors)
        self.assertIsNone(second.errors, second.errors)
        self.assertEqual(
            first.data["createTransaction"]["id"],
            second.data["createTransaction"]["id"],
        )
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Transaction)), 10)
            self.assertEqual(
                db.scalar(select(func.count()).select_from(IdempotencyKey)),
                1,
            )

    def test_same_key_different_payload_is_rejected(self):
        key = str(uuid.uuid4())
        first = self.execute({"input": self.base_input(idempotencyKey=key, amount="100.00")})
        self.assertIsNone(first.errors, first.errors)
        second = self.execute({"input": self.base_input(idempotencyKey=key, amount="200.00")})
        self.assertIsNotNone(second.errors)
        self.assertIn("otros datos", second.errors[0].message)
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Transaction)), 10)

    def test_different_key_creates_another_transaction(self):
        first = self.execute({"input": self.base_input(amount="100.00")})
        second = self.execute({"input": self.base_input(amount="100.00")})
        self.assertIsNone(first.errors, first.errors)
        self.assertIsNone(second.errors, second.errors)
        self.assertNotEqual(
            first.data["createTransaction"]["id"],
            second.data["createTransaction"]["id"],
        )
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Transaction)), 11)

    def test_concurrent_same_key_creates_one_transaction(self):
        key = str(uuid.uuid4())
        payload = self.base_input(idempotencyKey=key)
        barrier = threading.Barrier(8)
        results = []

        def worker():
            barrier.wait()
            results.append(self.execute({"input": payload}))

        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda _: worker(), range(8)))

        successes = [item for item in results if item.errors is None]
        self.assertEqual(len(successes), 8)
        ids = {item.data["createTransaction"]["id"] for item in successes}
        self.assertEqual(len(ids), 1)
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Transaction)), 10)
            self.assertEqual(db.scalar(select(func.count()).select_from(IdempotencyKey)), 1)

    def test_persistence_across_new_session(self):
        key = str(uuid.uuid4())
        payload = self.base_input(idempotencyKey=key)
        first = self.execute({"input": payload})
        self.assertIsNone(first.errors, first.errors)
        self.session_patch.stop()
        self.session_patch = patch.object(schema_module, "SessionLocal", self.sessions)
        self.session_patch.start()
        second = self.execute({"input": payload})
        self.assertIsNone(second.errors, second.errors)
        self.assertEqual(
            first.data["createTransaction"]["id"],
            second.data["createTransaction"]["id"],
        )

    def test_rollback_when_validation_fails_does_not_store_key(self):
        key = str(uuid.uuid4())
        result = self.execute(
            {
                "input": self.base_input(
                    idempotencyKey=key,
                    amount="0",
                )
            }
        )
        self.assertIsNotNone(result.errors)
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Transaction)), 9)
            self.assertIsNone(
                db.scalar(select(IdempotencyKey).where(IdempotencyKey.idempotency_key == key))
            )


if __name__ == "__main__":
    unittest.main()
