"""Conjunto de laboratorio reproducible; no contiene registros de una empresa real."""
import os
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from app.database import Base, SessionLocal, engine
from app.models import Company, CompanyUser, User
from app.financial_models import Account, AccountConcept, Concept, Transaction
from app.rbac import seed_rbac, assign_role_internal
from app.rbac_models import RoleModel
from app.security import hash_password


def seed_demo(db, password):
    if db.scalar(select(Company.id).limit(1)) is not None:
        raise RuntimeError('La base ya tiene empresas. No se modificaron sus datos; usa una base vacía para la demo.')
    seed_rbac(db)
    company = Company(name='Empresa de demostración')
    empty = Company(name='Empresa sin cuentas (prueba)')
    db.add_all([company, empty])
    db.flush()
    blocked = RoleModel(code='SIN_LECTURA_DEMO', name='Sin lectura (prueba)', is_active=True)
    db.add(blocked)
    db.flush()
    reader = db.scalar(select(RoleModel).where(RoleModel.code == 'CONSULTA'))
    admin_role = db.scalar(select(RoleModel).where(RoleModel.code == 'ADMINISTRADOR'))
    members = {}
    for email, name, target, role, is_admin in [
        ('admin@dashboard.example.com', 'Administrador de demostración', company, admin_role, True),
        ('consulta@dashboard.example.com', 'Consulta de demostración', company, reader, False),
        ('sinpermiso@dashboard.example.com', 'Usuario sin permiso de lectura', company, blocked, False),
        ('vacia@dashboard.example.com', 'Consulta de empresa vacía', empty, reader, False),
    ]:
        user = User(name=name, email=email, password_hash=hash_password(password))
        db.add(user)
        db.flush()
        member = CompanyUser(company_id=target.id, user_id=user.id, is_admin=is_admin)
        db.add(member)
        db.flush()
        assign_role_internal(db, member, role)
        members[email] = member
    income = Concept(company_id=company.id, concept_type='INCOME', name='Ingreso de laboratorio')
    expense = Concept(company_id=company.id, concept_type='EXPENSE', name='Egreso de laboratorio')
    db.add_all([income, expense])
    db.flush()
    captured_by = members['admin@dashboard.example.com'].user_id
    for name, kind, opening, incoming, outgoing in [
        ('Banco', 'DEBIT', '500.00', '2000.00', '1700.00'),
        ('Caja', 'CASH', '300.00', '500.00', '1000.00'),
        ('Ahorro', 'SAVINGS', '200.00', '1000.00', '200.00'),
    ]:
        account = Account(company_id=company.id, account_type=kind, name=name)
        db.add(account)
        db.flush()
        for concept in (income, expense):
            db.add(AccountConcept(account_id=account.id, concept_id=concept.id))
        for moment, amount, concept, label in [
            ('2026-10-25T12:00:00', opening, income, 'Saldo previo al período'),
            ('2026-10-26T00:00:00', incoming, income, 'Ingreso del período'),
            ('2026-10-30T23:59:59', outgoing, expense, 'Egreso del período'),
        ]:
            db.add(Transaction(account_id=account.id, concept_id=concept.id,
                transaction_type=concept.concept_type, amount=Decimal(amount),
                transaction_date=datetime.fromisoformat(moment), captured_by=captured_by,
                short_description=label))
    db.commit()
    return {email: (m.id, m.company_id) for email, m in members.items()}


if __name__ == '__main__':
    password = os.environ.get('DEMO_PASSWORD')
    if not password:
        raise SystemExit('Falta DEMO_PASSWORD: ejecuta python configurar.py.')
    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        seed_demo(session, password)
    print('Demo registrada: 2 empresas, 4 usuarios, 3 cuentas y 9 movimientos. Contraseña en .env local.')
