# Informe de estado · Unidad III · Actividad 2

Dashboard administrativo e idempotencia de transacciones

**Proyecto:** Sistema General de Ingresos  
**Directorio auditado:** `/home/avenkal/Descargas/Tecnologico_De_Software/Cuatri-4/Back/U3/unidad3_actividad1_equipo`  
**Especificación:** `/home/avenkal/Descargas/unidad3_actividad_2(1).pdf`  
**Fecha de auditoría:** 18 de noviembre de 2026  

Este informe describe el estado real del código, las pruebas ejecutadas y lo que falta para cerrar la entrega. No inventa capturas, resultados ni funcionalidades.

---

## 1. Resumen general

La Actividad 2 se implementó sobre el proyecto de la Actividad 1. El backend GraphQL ya disponía de la mayoría de mutaciones administrativas; se agregó idempotencia persistente a `createTransaction`, la consulta `me`, el rol en `companyUsers`, el usuario administrador de demostración y el dashboard administrativo en el mismo cliente HTML/JS.

En el entorno de desarrollo de esta auditoría:

- Las pruebas unitarias y un smoke test GraphQL se ejecutaron con éxito.
- Docker/MySQL no estuvo disponible, por lo que la persistencia se verificó con SQLite mediante la misma capa ORM.
- Existen **tres commits locales** en un clon del repositorio `Tareas_backend`, **sin push** a GitHub.
- El directorio de trabajo principal **no es un repositorio Git**; el historial vive en `_tareas_backend/`.

---

## 2. Estado actual del proyecto

| Componente | Estado |
| --- | --- |
| Backend / idempotencia | Implementado y verificado en pruebas automatizadas |
| Backend / operaciones administrativas | Implementado y verificado |
| Frontend / dashboard financiero | Conservado |
| Frontend / dashboard administrativo | Implementado en código; UI no capturada en evidencias visuales |
| Documentación README | Actualizada en esta auditoría |
| Evidencias GraphQL JSON | Disponibles |
| Evidencias visuales (capturas) | Pendientes |
| MySQL vía Docker Compose | No verificado en este entorno |
| Push a GitHub | No realizado |

---

## 3. Estructura de directorios

```text
unidad3_actividad1_equipo/
├── README.md
├── INFORME_ESTADO_ACTIVIDAD2.md          # este informe
├── REPORTE_TECNICO_U3_ACTIVIDAD2.md
├── dashboard/                            # cliente único (financiero + admin)
├── ingresos/                             # API FastAPI + GraphQL + tests
├── documentacion/
├── evidencias/
│   └── actividad2/
├── verificacion/
└── _tareas_backend/                      # clon Git de Tareas_backend (no entregar como dependencia)
    └── U3_Actividad2/                    # copia versionada con 3 commits locales
```

---

## 4. Archivos nuevos

| Archivo | Propósito |
| --- | --- |
| `ingresos/tests/test_idempotency.py` | Pruebas de idempotencia |
| `ingresos/tests/test_admin_operations.py` | Pruebas de operaciones administrativas |
| `REPORTE_TECNICO_U3_ACTIVIDAD2.md` | Reporte técnico previo de implementación |
| `INFORME_ESTADO_ACTIVIDAD2.md` | Este informe de auditoría |
| `evidencias/actividad2/pruebas_funcionales.json` | Resultado del smoke test GraphQL |
| `evidencias/actividad2/idempotencia_graphiql_ejemplo.md` | Notas de evidencia de idempotencia |
| `evidencias/actividad2/INSTRUCCIONES_CAPTURAS.md` | Guía para capturas manuales |
| `evidencias/actividad2/unittest_resumen.txt` | Resumen de unittest |
| Modelo `IdempotencyKey` en `financial_models.py` | Tabla `idempotency_keys` |

---

## 5. Archivos modificados

| Archivo | Cambio principal |
| --- | --- |
| `ingresos/app/financial_models.py` | Tabla `idempotency_keys` |
| `ingresos/app/schema.py` | Idempotencia, `me`, rol en `companyUsers`, alias de tipos de cuenta |
| `ingresos/app/demo.py` | Usuario `admin@...`, tipos `DEBIT`/`SAVINGS` |
| `ingresos/tests/test_access_by_role.py` | Inclusión de `idempotencyKey` |
| `dashboard/index.html` | Navegación y pantallas administrativas |
| `dashboard/app.js` | Lógica de administración y permisos |
| `dashboard/styles.css` | Estilos del panel administrativo |
| `dashboard/README.md` | Descripción del cliente unificado |
| `documentacion/consultas.graphql` | Ejemplos de administración e idempotencia |
| `README.md` | Documentación de Actividad 2 (actualizado en esta auditoría) |
| `repositorio.txt` | Apunta a `Aven-Kal97/Tareas_backend` |
| `.gitignore` | Inclusión de `_tareas_backend/` |

**Secreto local (no versionar):** existe `ingresos/.env` en el disco. Debe permanecer fuera de Git.

---

## 6. Implementación del backend

### 6.1 Idempotencia de `createTransaction`

- Campo obligatorio `idempotencyKey` (UUID) en `CreateTransactionInput`.
- Hash SHA-256 del cuerpo relevante (`accountId`, `conceptId`, tipo, monto, fechas y descripciones).
- Tabla `idempotency_keys` con UNIQUE `(company_id, operation, idempotency_key)`.
- Movimiento y llave se confirman en el mismo `commit`.
- Ante `IntegrityError` (concurrencia), se hace `rollback` y se recupera el movimiento existente o se reporta conflicto de hash.
- Se conservan las validaciones RBAC (`transactions.write`) y de negocio previas.

### 6.2 Operaciones administrativas

Ya existían y se reutilizaron:

- `companyUsers`, `createCompanyUser`, `deactivateCompanyUser`
- `accounts`, `createAccount`
- `concepts`, `createConcept`
- `accountConcepts`, `assignConceptToAccount`, `removeConceptFromAccount`

Se completaron:

- Campo `role` en la respuesta de membresías.
- Consulta `me` con `companyId`, empresa, rol y lista de permisos.
- Seed de demostración con administrador principal.

### 6.3 Cambios en MySQL

Diseño orientado a MySQL 8 vía Docker Compose (`ingresos/docker-compose.yml`, base `ingresos_u3`). La tabla `idempotency_keys` se crea con `Base.metadata.create_all` al arrancar la API.

**Limitación de verificación:** en esta máquina no se pudo levantar el daemon de Docker; la lógica se verificó con SQLite.

---

## 7. Implementación del frontend

Una sola aplicación (`dashboard/`), con menú:

- Dashboard financiero (Actividad 1)
- Dashboard administrativo
  - Usuarios
  - Cuentas
  - Conceptos

Características observadas en el código:

- Carga de `me` tras el login para permisos.
- Contadores, búsqueda y filtros en usuarios.
- Traducción de tipos de cuenta y enmascarado de referencia.
- Pantalla dividida de conceptos y asignación por cuenta.
- Ocultación de botones de escritura sin permiso.
- Refresco de datos tras mutaciones exitosas.
- Cierre de sesión y retorno al login ante sesión inválida.

No se verificaron capturas visuales del navegador en las evidencias de Actividad 2.

---

## 8. Cambios en MySQL

| Elemento | Detalle |
| --- | --- |
| Tabla nueva | `idempotency_keys` |
| Campos | id, company_id, operation, idempotency_key, request_hash, resource_id, created_at |
| Restricción | UNIQUE empresa + operación + llave |
| Datos previos | No se diseñó un borrado destructivo; el seed de demo solo corre sobre base vacía |

---

## 9. Seguridad y autorización

- JWT Bearer con membresía y empresa.
- Matriz RBAC en `ingresos/app/rbac.py`.
- El backend deniega operaciones sin permiso (`FORBIDDEN`).
- El frontend oculta botones, pero no sustituye la autorización del servidor.
- Las contraseñas no se listan en consultas ni tablas.
- `sessionStorage` guarda el token; se elimina al cerrar sesión.

Rol de escritura de demostración: `admin@dashboard.example.com` (`ADMINISTRADOR`).  
Rol de solo lectura: `consulta@dashboard.example.com` (`CONSULTA`).

---

## 10. Pruebas ejecutadas y resultados verificables

### 10.1 Unitarias

Comando:

```bash
cd ingresos
python -m unittest discover -s tests
```

Resultado re-verificado en la auditoría: **Ran 28 tests · OK (skipped=1)**.

Incluyen `test_idempotency` (primera ejecución, reintento, conflicto de hash, llave nueva, concurrencia, persistencia de sesión, rollback) y `test_admin_operations`.

### 10.2 Smoke GraphQL

Archivo: `evidencias/actividad2/pruebas_funcionales.json`

Resultados observados:

- Login administrador correcto.
- Alta de usuario, error de correo duplicado y baja lógica (`isActive: false`).
- Alta de cuenta y concepto; asignación; error de duplicado; remoción con concepto aún activo.
- Usuario `CONSULTA` sin `accounts.write`.
- Idempotencia: mismo `id` en reintento; error con datos distintos; nuevo `id` con otra llave.

### 10.3 No verificadas aquí

- Docker Compose + MySQL 8.
- Capturas de GraphiQL y del dashboard en navegador.
- Comprobación SQL directa sobre MySQL tras reiniciar la API.

---

## 11. Funcionalidades terminadas

- Idempotencia de `createTransaction` en código y pruebas automatizadas.
- Operaciones GraphQL administrativas con rol y `me`.
- Dashboard administrativo integrado al cliente existente.
- Conservación del dashboard financiero, login y cierre de sesión.
- RBAC de lectura/escritura en backend y UI.
- Documentación de consultas, README e informe.

---

## 12. Funcionalidades pendientes

1. Obtener capturas reales de Usuarios, Cuentas, Conceptos, error de duplicado y vista de solo lectura.
2. Levantar MySQL con Docker y repetir la demostración de idempotencia + altas sobre MySQL.
3. Publicar en GitHub (`git push`) cuando el equipo lo decida.
4. Opcional: boceto si el diseño final difiere de las figuras del PDF.

---

## 13. Errores conocidos

| Problema | Impacto | Mitigación |
| --- | --- | --- |
| Docker no disponible en el entorno de auditoría | No se verificó MySQL real | Usar `docker compose up` en Arch con Docker activo |
| Workspace principal sin `.git` | Los commits están en `_tareas_backend` | Trabajar/publicar desde ese clon o inicializar Git conscientemente |
| Existe `ingresos/.env` local | Riesgo si se agrega por error | Mantenerlo en `.gitignore` |
| Tipos legacy `BANK` en datos antiguos | Podían romper `accounts` GraphQL | Alias `BANK → DEBIT` y seed actualizado a `DEBIT`/`SAVINGS` |
| `test_e07_mysql` se omite sin MySQL | Cobertura MySQL incompleta aquí | Ejecutar con contenedor activo |

---

## 14. Requisitos del PDF cumplidos y no cumplidos

| Requisito | Estado | Archivo relacionado | Evidencia o explicación |
| --- | --- | --- | --- |
| Idempotencia en `createTransaction` con `idempotencyKey` | COMPLETADO | `ingresos/app/schema.py` | Pruebas unitarias + `pruebas_funcionales.json` (mismo id en reintento) |
| Llave UUID generada por el cliente | COMPLETADO | `dashboard` no captura movimientos; se demuestra en GraphiQL/tests | El PDF indica demostrar la mutación existente, no capturar movimientos en el admin |
| Persistencia de la llave en BD (no solo memoria) | COMPLETADO | `ingresos/app/financial_models.py` | Modelo `IdempotencyKey`; verificado vía ORM/SQLite |
| Tabla con empresa, operación, llave, hash e id de movimiento | COMPLETADO | `idempotency_keys` | Campos y UNIQUE presentes en el modelo |
| Mismo commit para movimiento y llave | COMPLETADO | `schema.py` (`create_transaction`) | Un solo `commit` tras `flush` de ambos |
| Reintento misma llave → mismo movimiento | COMPLETADO | `tests/test_idempotency.py` | Verificado |
| Misma llave, datos distintos → error | COMPLETADO | `tests/test_idempotency.py` | Mensaje de conflicto verificado |
| Llave distinta → nuevo movimiento | COMPLETADO | `tests/test_idempotency.py` | Verificado |
| Concurrencia segura (no SELECT-INSERT ingenuo) | COMPLETADO | `schema.py` + test concurrente | Manejo de `IntegrityError` + UNIQUE |
| Persistencia tras reiniciar API | NO VERIFICADO | — | Se simuló nueva sesión ORM; no se reinició API contra MySQL |
| Rollback si falla la transacción | COMPLETADO | `test_idempotency` (monto inválido) | No queda llave ni movimiento extra |
| Captura GraphiQL de dos envíos con mismo id | PENDIENTE | `evidencias/actividad2/` | Hay JSON/notas; faltan capturas de pantalla |
| Una sola aplicación con menú financiero/administrativo | COMPLETADO | `dashboard/index.html`, `app.js` | Código presente; HTTP `/dashboard/` respondió 200 en smoke previo |
| Módulo Usuarios (conteos, tabla, búsqueda, alta, desactivar) | COMPLETADO | `dashboard/*`, `schema.py` | Código + pruebas GraphQL de alta/baja/duplicado |
| Mostrar inconsistencia si hay >1 administrador | COMPLETADO | `dashboard/app.js` | Se muestra nota cuando `admins > 1` |
| No pedir `isAdmin` en alta ordinaria | COMPLETADO | Formulario usuarios | Solo nombre, correo y contraseña |
| Módulo Cuentas (tabla, filtros, alta, etiquetas ES) | COMPLETADO | `dashboard/*` | Implementado en cliente |
| Módulo Conceptos (catálogo + asignación por cuenta) | COMPLETADO | `dashboard/*` | Implementado; duplicado y remoción verificados por API |
| Baja lógica (no borrar filas) | COMPLETADO | Mutaciones existentes | `isActive=false` verificado en usuario y relación cuenta-concepto |
| RBAC backend + ocultar botones sin write | COMPLETADO | `rbac.py`, `app.js` | Denegación API verificada; ocultación en código |
| JWT y cierre de sesión | COMPLETADO | `security.py`, `app.js` | Flujo heredado de Actividad 1, conservado |
| Contraseña no visible en tablas/consultas | COMPLETADO | Esquema GraphQL / UI | No se expone password en tipos de respuesta |
| Operaciones sobre empresa de la sesión | COMPLETADO | Resolvers | Usan actor/token; aislamiento verificado en tests |
| README con acceso a administración y rol de prueba | COMPLETADO | `README.md` | Actualizado en esta auditoría |
| Capturas de tres pantallas + error duplicado + solo lectura | PENDIENTE | `evidencias/actividad2/INSTRUCCIONES_CAPTURAS.md` | Instrucciones sí; capturas no |
| Verificación en MySQL de no duplicar movimiento | NO VERIFICADO | Docker/MySQL | Verificado en SQLite/ORM, no en MySQL real |
| Boceto si cambió respecto a figuras del PDF | PENDIENTE | `documentacion/` | No se generó boceto nuevo de Actividad 2 |

---

## 15. Instrucciones para ejecutar el sistema desde Arch Linux

```bash
cd /home/avenkal/Descargas/Tecnologico_De_Software/Cuatri-4/Back/U3/unidad3_actividad1_equipo
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r ingresos/requirements.txt
cd ingresos
python configurar.py
# Asegurar que el servicio Docker esté activo en el sistema
docker compose up -d --wait
python -m app.demo   # solo base vacía
python -m uvicorn app.main:app --host 127.0.0.1 --port 8013
```

Abrir:

- http://127.0.0.1:8013/dashboard/
- http://127.0.0.1:8013/graphql

---

## 16. Comandos para verificar el funcionamiento

```bash
# Pruebas automatizadas
source .venv/bin/activate
cd ingresos
python -m unittest discover -s tests -v

# Salud del API
curl http://127.0.0.1:8013/health

# Contraseña demo local
python -c "from dotenv import dotenv_values; print(dotenv_values('.env')['DEMO_PASSWORD'])"
```

En GraphiQL: login con `admin@dashboard.example.com`, enviar dos veces `createTransaction` con la misma `idempotencyKey` y confirmar el mismo `id`.

En el dashboard: entrar a administración, crear usuario, forzar correo duplicado, desactivar, crear cuenta/concepto, asignar dos veces y quitar.

Con MySQL:

```bash
docker compose exec mysql mysql -uingresos -p"$MYSQL_PASSWORD" ingresos_u3 \
  -e "SELECT id, company_id, operation, idempotency_key, resource_id FROM idempotency_keys;"
```

---

## 17. Cambios realizados al README original

En esta auditoría se **actualizó el `README.md` existente** (no se creó otro con nombre distinto). Cambios principales:

1. Título alineado a «Sistema General de Ingresos – Unidad III, Actividad 2».
2. Se **conservaron exactamente** los cinco nombres y matrículas del equipo.
3. Se reorganizó en las secciones pedidas (objetivos, arquitectura, idempotencia, admin, seguridad, pruebas, estado).
4. Se mantuvo la continuidad con el dashboard financiero de la Actividad 1.
5. Se documentaron versiones reales de dependencias.
6. Se distinguieron funciones verificadas y pendientes, sin inventar capturas MySQL.

No se agregaron coautores ni menciones a asistentes de IA.

---

## 18. Recomendaciones antes de la entrega

1. **No duplicar commits.** En `_tareas_backend` ya existen los tres commits solicitados; falta el `git push` manual.
2. Si trabajas desde el workspace sin Git, copia solo los archivos finales a `U3_Actividad2` del clon y publica esos commits, o sincroniza el README/informe nuevos con un commit adicional de documentación si lo consideras necesario.
3. Arranca Docker, carga la demo y genera las capturas pendientes.
4. Confirma que `ingresos/.env` no entra al commit (`git status` / `.gitignore`).
5. Verifica con el usuario `consulta@...` que no aparecen botones de alta.
6. Repite la mutación idempotente en GraphiQL y guarda la captura.

---

## 19. Conclusiones

El desarrollo de la Actividad 2 está **funcionalmente avanzado y mayormente completo en código**: idempotencia, backend administrativo, dashboard integrado y pruebas automatizadas verificables. Los huecos reales para una entrega al 100 % según el PDF son operativos y de evidencia: **MySQL con Docker, capturas visuales y publicación en GitHub**.

El equipo puede completar esos pasos desde Arch Linux con la terminal de IntelliJ IDEA, sin rehacer la implementación.

---

## Anexo A · Estado de Git (solo lectura)

### Workspace `unidad3_actividad1_equipo`

- **No es un repositorio Git** (`fatal: not a git repository`).

### Clon `_tareas_backend`

```text
Rama: main
Remoto: https://github.com/Aven-Kal97/Tareas_backend.git
Estado: ahead of origin/main by 3 commits
Working tree: clean
```

Commits locales ya creados:

| Hash corto | Mensaje |
| --- | --- |
| `f8a03d6` | feat: add idempotency support for transactions |
| `61a4f92` | feat: extend GraphQL administrative operations |
| `2673fa7` | feat: integrate administrative dashboard and documentation |

**Importante:** no conviene volver a crear esos tres commits sobre el mismo clon. Si se actualiza el README/informe después de `2673fa7`, el equipo puede añadir un commit documental adicional o enmendar solo si cumple sus propias reglas de flujo.

### Secretos detectados

- `ingresos/.env` presente en disco → **no incluir** en commits.

---

## Anexo B · Cómo organizar los tres commits (manual)

### Caso recomendado: los commits ya existen

Solo publica:

```bash
cd /home/avenkal/Descargas/Tecnologico_De_Software/Cuatri-4/Back/U3/unidad3_actividad1_equipo/_tareas_backend
git log --oneline origin/main..HEAD
git status
# Revisar que no haya .env
git push -u origin HEAD
```

Si deseas incorporar el `README.md` y `INFORME_ESTADO_ACTIVIDAD2.md` actualizados en esta auditoría:

```bash
cd /home/avenkal/Descargas/Tecnologico_De_Software/Cuatri-4/Back/U3/unidad3_actividad1_equipo
cp README.md INFORME_ESTADO_ACTIVIDAD2.md _tareas_backend/U3_Actividad2/
cd _tareas_backend
git status
git add U3_Actividad2/README.md U3_Actividad2/INFORME_ESTADO_ACTIVIDAD2.md
git commit -m "$(cat <<'EOF'
docs: update Activity 2 README and status report

EOF
)"
git push
```

### Caso alternativo: rehacer tres commits desde cero

Solo aplica si partes de un árbol **sin** esos commits. Distribución sugerida:

**Commit 1 — idempotencia**

```bash
git add \
  U3_Actividad2/ingresos/app/financial_models.py \
  U3_Actividad2/ingresos/app/schema.py \
  U3_Actividad2/ingresos/app/demo.py \
  U3_Actividad2/ingresos/tests/test_idempotency.py \
  U3_Actividad2/ingresos/tests/test_access_by_role.py
# más el resto del proyecto base si es el primer commit del directorio
git commit -m "$(cat <<'EOF'
feat: add idempotency support for transactions

EOF
)"
```

**Commit 2 — backend administrativo**

```bash
git add \
  U3_Actividad2/ingresos/app/schema.py \
  U3_Actividad2/ingresos/app/demo.py \
  U3_Actividad2/ingresos/tests/test_admin_operations.py \
  U3_Actividad2/documentacion/consultas.graphql
git commit -m "$(cat <<'EOF'
feat: extend GraphQL administrative operations

EOF
)"
```

**Commit 3 — dashboard y documentación**

```bash
git add \
  U3_Actividad2/dashboard/ \
  U3_Actividad2/README.md \
  U3_Actividad2/INFORME_ESTADO_ACTIVIDAD2.md \
  U3_Actividad2/REPORTE_TECNICO_U3_ACTIVIDAD2.md \
  U3_Actividad2/evidencias/actividad2/ \
  U3_Actividad2/repositorio.txt
git commit -m "$(cat <<'EOF'
feat: integrate administrative dashboard and documentation

EOF
)"
git push -u origin HEAD
```

### Si un archivo mezcla etapas (`schema.py`, `demo.py`)

Cuando el historial no esté separado:

```bash
git add -p U3_Actividad2/ingresos/app/schema.py
```

Revisa cada hunk: incluye en el commit 1 solo idempotencia; deja para el commit 2 `me`, rol en `companyUsers` y cambios administrativos. En la práctica actual del clon, esa separación **ya quedó hecha** entre `f8a03d6` y `61a4f92`; no es necesario repetir `git add -p` salvo que reconstruyas el historial.

---

## Anexo C · Integrantes (sin alteración)

| Nombre | Matrícula |
| --- | --- |
| Angel Abraham Lugo Saenz | SW2409052 |
| Juan Jose Zapata Buenfil | SW2509044 |
| Josue Enmanuel Poot Mateo | SW2509033 |
| Sergio Origion Huerta Martinez | SW2509012 |
| Diego Ramirez Magaña | SW2509051 |

Docente: Gimer Amilcar Cervera Evia.
