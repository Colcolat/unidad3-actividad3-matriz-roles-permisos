"""Prueba MySQL + HTTP + navegador; crea evidencias sin guardar credenciales ni tokens."""
import csv
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ingresos'))
from dotenv import load_dotenv
load_dotenv(ROOT / 'ingresos/.env')
import httpx
from sqlalchemy import create_engine, text
from playwright.sync_api import sync_playwright, expect

URL = os.getenv('DEMO_URL', 'http://127.0.0.1:8013')
OUT = ROOT / 'evidencias'
OUT.mkdir(exist_ok=True)
password = os.environ['DEMO_PASSWORD']
checks = []
def checked(label):
    checks.append(label)
    print('OK:', label)

fields = '''companyId companyName currency fromDate toDate openingBalance totalIncome totalExpense
profit closingBalance isInRed accountsInRed transactionCount accounts { accountId accountName isActive
openingBalance totalIncome totalExpense profit closingBalance isInRed transactionCount }'''
query = 'query($from: Date!, $to: Date!) { generalBalance(fromDate: $from, toDate: $to) { ' + fields + ' } }'
variables = {'from': '2026-10-26', 'to': '2026-10-30'}
client = httpx.Client(base_url=URL, timeout=20)
assert client.get('/dashboard/').status_code == 200
assert client.get('/graphql').status_code == 200
checked('API, dashboard y GraphiQL disponibles en el mismo origen')
login = client.post('/graphql', json={'query': 'mutation($input: LoginInput!) { login(input: $input) { token tokenType } }', 'variables': {'input': {'email': 'consulta@dashboard.example.com', 'password': password}}}).json()
assert not login.get('errors'), login.get('errors')
token = login['data']['login']['token']
checked('Login real con usuario registrado en MySQL')
response = client.post('/graphql', headers={'Authorization': f'Bearer {token}'}, json={'query': query, 'variables': variables}).json()
assert not response.get('errors'), response.get('errors')
balance = response['data']['generalBalance']
expected = dict(zip(['openingBalance','totalIncome','totalExpense','profit','closingBalance'], ['1000.00','3500.00','2900.00','600.00','1600.00']))
for k,v in expected.items(): assert balance[k] == v, (k,balance[k])
assert not balance['isInRed'] and balance['accountsInRed'] == 1
assert balance['accounts'][1]['accountName'] == 'Caja' and balance['accounts'][1]['closingBalance'] == '-200.00'
(OUT / 'balance_mysql.json').write_text(json.dumps(response, ensure_ascii=False, indent=2)+'\n')
checked('GraphQL coincide con los cinco importes de referencia y una cuenta en rojo')
engine = create_engine(os.environ['DATABASE_URL'])
with engine.connect() as connection:
    version = connection.execute(text('SELECT VERSION()')).scalar()
    rows = connection.execute(text('''SELECT a.name AS cuenta, t.transaction_date AS fecha,
    t.transaction_type AS tipo, t.amount AS importe FROM transactions t
    JOIN accounts a ON a.id=t.account_id WHERE a.company_id=:company AND t.is_active=1
    ORDER BY t.transaction_date,a.id'''), {'company': int(balance['companyId'])}).mappings().all()
    totals = connection.execute(text('''SELECT
    SUM(CASE WHEN t.transaction_date < '2026-10-26' THEN CASE WHEN t.transaction_type='INCOME' THEN t.amount ELSE -t.amount END ELSE 0 END) AS inicial,
    SUM(CASE WHEN t.transaction_date >= '2026-10-26' AND t.transaction_date < '2026-10-31' AND t.transaction_type='INCOME' THEN t.amount ELSE 0 END) AS ingresos,
    SUM(CASE WHEN t.transaction_date >= '2026-10-26' AND t.transaction_date < '2026-10-31' AND t.transaction_type='EXPENSE' THEN t.amount ELSE 0 END) AS egresos
    FROM transactions t JOIN accounts a ON a.id=t.account_id WHERE a.company_id=:company AND t.is_active=1'''), {'company': int(balance['companyId'])}).one()
assert tuple(f'{v:.2f}' for v in totals) == ('1000.00', '3500.00', '2900.00')
with (OUT / 'movimientos_mysql.csv').open('w', newline='') as stream:
    writer = csv.DictWriter(stream, fieldnames=['cuenta','fecha','tipo','importe'], lineterminator='\n')
    writer.writeheader(); writer.writerows(rows)
checked(f'Consulta SQL independiente en MySQL {version} confirma saldos y movimientos')
for candidate in [None, 'token-invalido-de-prueba']:
    r = client.post('/graphql', headers={'Authorization': f'Bearer {candidate}'} if candidate else {}, json={'query':query, 'variables':variables}).json()
    assert r['errors'][0]['extensions']['code'] == 'UNAUTHENTICATED' and r['data'] is None
checked('HTTP rechaza ausencia de token y token inválido sin devolver balances')
r = client.post('/graphql', headers={'Authorization': f'Bearer {token}'}, json={'query':query, 'variables':{'from':'2026-10-31','to':'2026-10-26'}}).json()
assert r['errors'][0]['extensions']['code'] == 'BAD_USER_INPUT'
checked('HTTP rechaza fechas invertidas')

with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True)
    context = browser.new_context(viewport={'width':1440,'height':1000}, device_scale_factor=1, locale='es-MX')
    page = context.new_page()
    errors = []
    requests = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('request', lambda r: requests.append(r.url) if r.url.endswith('/graphql') else None)
    page.goto(URL + '/dashboard/', wait_until='networkidle')
    page.screenshot(path=str(OUT / '01_login.png'), full_page=True)
    def login_as(email):
        page.locator('#email').fill(email)
        page.locator('#password').fill(password)
        page.locator('#login-button').click()
        expect(page.locator('#dashboard-view')).to_be_visible()
    login_as('consulta@dashboard.example.com')
    page.locator('#demo-period').click()
    expect(page.locator('#closingBalance')).to_have_text('$1,600.00')
    expect(page.locator('#openingBalance')).to_have_text('$1,000.00')
    expect(page.locator('#totalIncome')).to_have_text('$3,500.00')
    expect(page.locator('#totalExpense')).to_have_text('$2,900.00')
    expect(page.locator('#profit')).to_have_text('$600.00')
    expect(page.locator('#general-risk')).to_have_text('General en rojo: No')
    expect(page.locator('#accounts-risk')).to_have_text('Cuentas en rojo: 1')
    expect(page.locator('#account-rows tr')).to_have_count(3)
    page.screenshot(path=str(OUT / '02_dashboard.png'), full_page=True)
    page.locator('.accounts-panel').screenshot(path=str(OUT / '03_detalle_cuentas.png'))
    checked('Navegador: login, indicadores y tabla coinciden con la respuesta real')
    page.set_viewport_size({'width':390,'height':844})
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Desbordamiento móvil'
    expect(page.locator('#closingBalance')).to_have_text('$1,600.00')
    page.screenshot(path=str(OUT / '08_movil.png'), full_page=True)
    page.set_viewport_size({'width':1440,'height':1000})
    checked('Diseño móvil de 390 px sin desbordamiento de la página')
    page.locator('#to-date').fill('2026-10-26')
    page.locator('#to-date').dispatch_event('change')
    expect(page.locator('#closingBalance')).to_have_text('$4,500.00')
    expect(page.locator('#applied-period')).to_have_text('26/10/2026 al 26/10/2026')
    page.screenshot(path=str(OUT / '04_cambio_fechas.png'), full_page=True)
    checked('Cambio de fechas actualiza importes y etiqueta del mismo período')
    before = len(requests)
    page.locator('#from-date').fill('2026-10-31')
    page.locator('#from-date').dispatch_event('change')
    expect(page.locator('#status')).to_contain_text('Revisa las fechas')
    expect(page.locator('#results')).to_be_hidden()
    assert len(requests) == before
    page.screenshot(path=str(OUT / '05_fechas_invalidas.png'), full_page=True)
    checked('Fechas invertidas: mensaje claro, sin petición al API ni importes anteriores')
    page.locator('#logout').click()
    expect(page.locator('#login-view')).to_be_visible()
    assert page.evaluate("sessionStorage.getItem('sgi-session')") is None
    checked('Cerrar sesión elimina el token del almacenamiento del cliente')
    login_as('sinpermiso@dashboard.example.com')
    expect(page.locator('#status')).to_contain_text('Acceso denegado')
    expect(page.locator('#results')).to_be_hidden()
    page.screenshot(path=str(OUT / '06_sin_permiso.png'), full_page=True)
    checked('Usuario sin permiso ve acceso denegado y ningún total inventado')
    page.locator('#logout').click()
    login_as('vacia@dashboard.example.com')
    expect(page.locator('#empty-accounts')).to_be_visible()
    expect(page.locator('#table-wrapper')).to_be_hidden()
    page.screenshot(path=str(OUT / '09_sin_cuentas.png'), full_page=True)
    checked('Empresa sin cuentas: estado vacío real y aislamiento entre empresas')
    page.locator('#logout').click()
    login_as('consulta@dashboard.example.com')
    page.locator('#from-date').fill('2026-11-01')
    page.locator('#to-date').fill('2026-11-10')
    page.locator('#to-date').dispatch_event('change')
    expect(page.locator('#no-movements')).to_be_visible()
    expect(page.locator('#openingBalance')).to_have_text('$1,600.00')
    expect(page.locator('#profit')).to_have_text('$0.00')
    page.screenshot(path=str(OUT / '10_sin_movimientos.png'), full_page=True)
    checked('Período sin movimientos conserva el saldo anterior')
    page.locator('#logout').click()
    page.evaluate("sessionStorage.setItem('sgi-session', JSON.stringify({token:'token-invalido-de-prueba'}))")
    page.reload()
    expect(page.locator('#login-view')).to_be_visible()
    expect(page.locator('#login-message')).to_contain_text('sesión venció o no es válida')
    expect(page.locator('#dashboard-view')).to_be_hidden()
    assert page.evaluate("sessionStorage.getItem('sgi-session')") is None
    page.screenshot(path=str(OUT / '07_token_invalido.png'), full_page=True)
    checked('Token inválido: regreso al login, mensaje visible y token eliminado')
    assert not errors, errors
    checked('Sin errores de JavaScript durante el recorrido')
    browser.close()
client.close()
engine.dispose()
(OUT / 'verificacion_integracion.json').write_text(json.dumps({'mysql_version':version,'checks_passed':len(checks),'checks':checks}, ensure_ascii=False, indent=2)+'\n')
print(f'{len(checks)} comprobaciones de integración correctas.')
