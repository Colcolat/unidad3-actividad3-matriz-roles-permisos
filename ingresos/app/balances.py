"""Balances de lectura: importes exactos y contexto de empresa validado por el API."""
from datetime import date, datetime, time, timedelta
from decimal import Decimal

import strawberry
from graphql import GraphQLError
from sqlalchemy import and_, case, func, select

from app.financial_models import Account, Transaction
from app.models import Company
from app.rbac import exigir_permiso


@strawberry.type
class AccountBalance:
    account_id: strawberry.ID
    account_name: str
    is_active: bool
    opening_balance: str
    total_income: str
    total_expense: str
    profit: str
    closing_balance: str
    is_in_red: bool
    transaction_count: int


@strawberry.type
class GeneralBalance:
    company_id: strawberry.ID
    company_name: str
    currency: str
    from_date: date
    to_date: date
    opening_balance: str
    total_income: str
    total_expense: str
    profit: str
    closing_balance: str
    is_in_red: bool
    accounts_in_red: int
    transaction_count: int
    accounts: list[AccountBalance]


def balance_for_company(db, actor: int, from_date: date, to_date: date,
                        account_id: int | None = None) -> GeneralBalance:
    member = exigir_permiso(db, actor, 'accounts.read')
    exigir_permiso(db, actor, 'transactions.read', member.company_id)
    if from_date > to_date:
        raise GraphQLError('La fecha inicial no puede ser posterior a la fecha final.',
                           extensions={'code': 'BAD_USER_INPUT'})
    if to_date == date.max:
        raise GraphQLError('La fecha final debe ser anterior al 31/12/9999.',
                           extensions={'code': 'BAD_USER_INPUT'})
    start = datetime.combine(from_date, time.min)
    end = datetime.combine(to_date + timedelta(days=1), time.min)
    period = and_(Transaction.transaction_date >= start, Transaction.transaction_date < end)
    signed = case((Transaction.transaction_type == 'INCOME', Transaction.amount),
                  else_=-Transaction.amount)
    # Una agregación para todas las cuentas; no se descargan movimientos al cliente.
    totals = select(
        Transaction.account_id.label('account_id'),
        func.sum(case((Transaction.transaction_date < start, signed), else_=0)).label('opening'),
        func.sum(case((and_(period, Transaction.transaction_type == 'INCOME'), Transaction.amount), else_=0)).label('income'),
        func.sum(case((and_(period, Transaction.transaction_type == 'EXPENSE'), Transaction.amount), else_=0)).label('expense'),
        func.sum(case((period, 1), else_=0)).label('count'),
    ).join(Account, Account.id == Transaction.account_id).where(
        Account.company_id == member.company_id,
        Transaction.is_active.is_(True), Transaction.transaction_date < end,
    ).group_by(Transaction.account_id).subquery()
    stmt = select(Account, totals.c.opening, totals.c.income, totals.c.expense, totals.c.count).outerjoin(
        totals, totals.c.account_id == Account.id
    ).where(Account.company_id == member.company_id).order_by(Account.id)
    if account_id is not None:
        stmt = stmt.where(Account.id == account_id)
    rows = db.execute(stmt).all()
    if account_id is not None and not rows:
        raise GraphQLError('La cuenta no existe en tu empresa.', extensions={'code': 'NOT_FOUND'})
    opening_total = income_total = expense_total = Decimal('0.00')
    accounts = []
    for account, opening, income, expense, count in rows:
        opening, income, expense = (Decimal(v or 0) for v in (opening, income, expense))
        profit = income - expense
        closing = opening + profit
        accounts.append(AccountBalance(
            account_id=strawberry.ID(str(account.id)), account_name=account.name,
            is_active=account.is_active, opening_balance=f'{opening:.2f}',
            total_income=f'{income:.2f}', total_expense=f'{expense:.2f}',
            profit=f'{profit:.2f}', closing_balance=f'{closing:.2f}',
            is_in_red=closing < 0, transaction_count=int(count or 0),
        ))
        opening_total += opening
        income_total += income
        expense_total += expense
    profit = income_total - expense_total
    closing = opening_total + profit
    return GeneralBalance(
        company_id=strawberry.ID(str(member.company_id)),
        company_name=db.get(Company, member.company_id).name, currency='MXN',
        from_date=from_date, to_date=to_date, opening_balance=f'{opening_total:.2f}',
        total_income=f'{income_total:.2f}', total_expense=f'{expense_total:.2f}',
        profit=f'{profit:.2f}', closing_balance=f'{closing:.2f}', is_in_red=closing < 0,
        accounts_in_red=sum(a.is_in_red for a in accounts),
        transaction_count=sum(a.transaction_count for a in accounts), accounts=accounts,
    )
