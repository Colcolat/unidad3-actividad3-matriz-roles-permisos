"""Genera configuración local sin contraseñas compartidas en el repositorio."""
import secrets
from pathlib import Path

target = Path(__file__).resolve().parent / '.env'
if target.exists():
    print('La configuración ya existe; no se modificó.')
else:
    db_password = secrets.token_hex(16)
    values = {
        'MYSQL_PORT': '3313',
        'MYSQL_PASSWORD': db_password,
        'MYSQL_ROOT_PASSWORD': secrets.token_hex(24),
        'DATABASE_URL': f'mysql+pymysql://ingresos:{db_password}@127.0.0.1:3313/ingresos_u3',
        'JWT_SECRET': secrets.token_hex(32),
        'DEMO_PASSWORD': secrets.token_urlsafe(18),
    }
    with target.open('x') as stream:
        stream.write('\n'.join(f'{k}={v}' for k, v in values.items()) + '\n')
    target.chmod(0o600)
    print('Se creó ingresos/.env con valores exclusivos de esta instalación.')
