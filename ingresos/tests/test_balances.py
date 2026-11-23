import logging
import os
import secrets
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import jwt
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.demo import seed_demo
from app.financial_models import Account, Transaction
from app.models import CompanyUser
from app.rbac_models import PermissionModel, RolePermissionModel, RoleModel
from app.schema import schema
from app.security import create_access_token
import app.schema as schema_module

FIELDS = '''companyId currency fromDate toDate openingBalance totalIncome totalExpense profit
closingBalance isInRed accountsInRed transactionCount accounts { accountId accountName isActive
openingBalance totalIncome totalExpense profit closingBalance isInRed transactionCount }'''
QUERY = 'query($from: Date!, $to: Date!) { generalBalance(fromDate: $from, toDate: $to) { ' + FIELDS + ' } }'


class BalanceTest(unittest.TestCase):
    def setUp(self):
        self.secret = secrets.token_hex(32)
        self.env = patch.dict(os.environ, {'JWT_SECRET': self.secret})
        self.env.start()
        self.temp = tempfile.TemporaryDirectory()
        self.engine = create_engine(f'sqlite:///{Path(self.temp.name) / "balance.sqlite"}')
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine, autoflush=False)
        self.session_patch = patch.object(schema_module, 'SessionLocal', self.sessions)
        self.session_patch.start()
        with self.sessions() as db:
            members = seed_demo(db, secrets.token_urlsafe(12))
        self.tokens = {email.split('@')[0]: create_access_token(*ids) for email, ids in members.items()}
        self.member, self.company = members['consulta@dashboard.example.com']

    def tearDown(self):
        self.session_patch.stop()
        self.engine.dispose()
        self.temp.cleanup()
        self.env.stop()

    def execute(self, query=QUERY, token='consulta', start='2026-10-26', end='2026-10-30'):
        token = self.tokens.get(token, token)
        headers = {'authorization': f'Bearer {token}'} if token else {}
        return schema.execute_sync(query, variable_values={'from': start, 'to': end},
                                   context_value={'request': SimpleNamespace(headers=headers)})

    def data(self, **kwargs):
        result = self.execute(**kwargs)
        self.assertIsNone(result.errors)
        return result.data['generalBalance']

    def test_reference_totals_and_individual_account_match(self):
        value = self.data()
        self.assertEqual([value[k] for k in ('openingBalance','totalIncome','totalExpense','profit','closingBalance')],
                         ['1000.00','3500.00','2900.00','600.00','1600.00'])
        self.assertFalse(value['isInRed'])
        self.assertEqual(value['accountsInRed'], 1)
        self.assertEqual(value['transactionCount'], 6)
        for item in value['accounts']:
            result = self.execute('query($from: Date!, $to: Date!) { accountBalance(accountId: "' + item['accountId'] + '", fromDate: $from, toDate: $to) { closingBalance } }')
            self.assertIsNone(result.errors)
            self.assertEqual(result.data['accountBalance']['closingBalance'], item['closingBalance'])
        self.assertEqual(value['accounts'][1]['closingBalance'], '-200.00')

    def test_inclusive_days_and_negative_profit_without_negative_general(self):
        first = self.data(end='2026-10-26')
        self.assertEqual(first['closingBalance'], '4500.00')
        self.assertEqual(first['totalExpense'], '0.00')
        last = self.data(start='2026-10-30')
        self.assertEqual(last['openingBalance'], '4500.00')
        self.assertEqual(last['profit'], '-2900.00')
        self.assertEqual(last['closingBalance'], '1600.00')
        self.assertFalse(last['isInRed'])
        before = self.data(start='2026-10-01', end='2026-10-24')
        self.assertEqual(before['closingBalance'], '0.00')

    def test_empty_period_keeps_opening_and_empty_company_has_no_accounts(self):
        value = self.data(start='2026-11-01', end='2026-11-10')
        self.assertEqual(value['openingBalance'], '1600.00')
        self.assertEqual(value['transactionCount'], 0)
        empty = self.data(token='vacia')
        self.assertEqual(empty['accounts'], [])
        self.assertEqual(empty['closingBalance'], '0.00')
        self.assertNotEqual(empty['companyId'], str(self.company))

    def test_invalid_periods_are_rejected(self):
        for start, end in [('2026-10-31','2026-10-26'), ('2026-02-30','2026-03-01'), ('9999-12-31','9999-12-31')]:
            self.assertTrue(self.execute(start=start, end=end).errors)

    def test_both_permissions_required_and_denied_data_not_zero(self):
        denied = self.execute(token='sinpermiso')
        self.assertTrue(denied.errors)
        self.assertIsNone(denied.data)
        self.assertEqual(denied.errors[0].extensions['code'], 'FORBIDDEN')
        with self.sessions() as db:
            role = db.scalar(select(RoleModel).where(RoleModel.code == 'CONSULTA'))
            permission = db.scalar(select(PermissionModel).where(PermissionModel.code == 'transactions.read'))
            relation = db.scalar(select(RolePermissionModel).where(RolePermissionModel.role_id == role.id, RolePermissionModel.permission_id == permission.id))
            relation.is_active = False
            db.commit()
        self.assertTrue(self.execute().errors)

    def test_authentication_and_active_membership_required(self):
        expired = jwt.encode({'companyUserId': self.member, 'companyId': self.company,
                              'exp': datetime.now(timezone.utc) - timedelta(minutes=1)}, self.secret, algorithm='HS256')
        forged = jwt.encode({'companyUserId': self.member, 'companyId': self.company,
                             'exp': datetime.now(timezone.utc) + timedelta(minutes=1)}, secrets.token_hex(32), algorithm='HS256')
        for token in [None, 'invalid', expired, forged]:
            result = self.execute(token=token)
            self.assertIsNone(result.data)
            self.assertEqual(result.errors[0].extensions['code'], 'UNAUTHENTICATED')
        with self.sessions() as db:
            db.get(CompanyUser, self.member).user.is_active = False
            db.commit()
        self.assertEqual(self.execute().errors[0].extensions['code'], 'UNAUTHENTICATED')

    def test_foreign_accounts_and_client_identity_arguments_are_rejected(self):
        account = self.data()['accounts'][0]['accountId']
        result = self.execute('query($from: Date!, $to: Date!) { accountBalance(accountId: "' + account + '", fromDate: $from, toDate: $to) { closingBalance } }', token='vacia')
        self.assertEqual(result.errors[0].extensions['code'], 'NOT_FOUND')
        self.assertTrue(self.execute(QUERY.replace('fromDate: $from', 'companyId: "1", fromDate: $from')).errors)
        self.assertTrue(self.execute(QUERY.replace('fromDate: $from', 'actorCompanyUserId: "1", fromDate: $from')).errors)

    def test_inactive_account_history_kept_and_cancelled_transaction_ignored(self):
        with self.sessions() as db:
            db.scalar(select(Account).where(Account.name == 'Caja')).is_active = False
            cancelled = db.scalar(select(Transaction).where(Transaction.transaction_type == 'EXPENSE'))
            cancelled.is_active = False
            db.commit()
        value = self.data()
        self.assertEqual(value['totalExpense'], '1200.00')
        self.assertFalse(value['accounts'][1]['isActive'])
        self.assertEqual(value['accounts'][1]['closingBalance'], '-200.00')

    def test_decimal_cents_and_queries_do_not_write(self):
        with self.sessions() as db:
            tx = db.scalar(select(Transaction).where(Transaction.transaction_type == 'INCOME', Transaction.transaction_date >= datetime(2026,10,26)))
            tx.amount = Decimal('0.10')
            db.commit()
        with self.engine.connect() as connection:
            before = connection.exec_driver_sql('SELECT COUNT(*) FROM transactions').scalar()
        value = self.data()
        self.assertEqual(value['totalIncome'], '1500.10')
        self.assertEqual(value['closingBalance'], '-399.90')
        self.assertTrue(value['isInRed'])
        with self.engine.connect() as connection:
            after = connection.exec_driver_sql('SELECT COUNT(*) FROM transactions').scalar()
        self.assertEqual(before, after)


if __name__ == '__main__':
    unittest.main()
