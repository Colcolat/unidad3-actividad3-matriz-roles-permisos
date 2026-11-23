# Reporte técnico · Unidad III · Actividad 2

Dashboard administrativo e idempotencia de movimientos

## 1. Introducción

Este reporte documenta la implementación de la Actividad 2 del Parcial III sobre el Sistema General de Ingresos. El trabajo se construyó a partir de la Actividad 1 (dashboard financiero), sin sustituir ese flujo y sin alterar las entregas de las unidades I y II.

## 2. Objetivos

1. Hacer idempotente la mutación `createTransaction` con persistencia en base de datos.
2. Completar o verificar las operaciones GraphQL necesarias para administrar usuarios, cuentas y conceptos.
3. Integrar un dashboard administrativo en la misma aplicación del dashboard financiero.
4. Conservar autenticación JWT y control de acceso por permisos RBAC.
5. Documentar pruebas reales y el procedimiento de ejecución.

## 3. Arquitectura utilizada

- Backend: FastAPI + Strawberry GraphQL + SQLAlchemy.
- Persistencia objetivo: MySQL 8 (Docker Compose). En el entorno de automatización de esta entrega, Docker no estuvo disponible; las pruebas automatizadas y la verificación funcional se ejecutaron con SQLite usando la misma capa ORM.
- Frontend: HTML, CSS y JavaScript sin framework, servido por FastAPI en `/dashboard/`.
- Autenticación: JWT Bearer con membresía y empresa en el token.
- Autorización: roles `ADMINISTRADOR`, `CONTADOR`, `CAPTURISTA` y `CONSULTA` con permisos granulares.

## 4. Análisis del proyecto inicial

El proyecto base ya incluía:

- Modelos de empresa, usuarios, membresías, cuentas, conceptos, relaciones cuenta-concepto y movimientos.
- Consultas de balance (`generalBalance`, `accountBalance`).
- Mutaciones administrativas básicas (`createCompanyUser`, `createAccount`, `createConcept`, `assignConceptToAccount`, `removeConceptFromAccount`, `deactivateCompanyUser`).
- Dashboard financiero de solo lectura.

Faltaban:

- Idempotencia persistente en `createTransaction`.
- Exposición del rol en `companyUsers`.
- Consulta de sesión (`me`) con permisos efectivos para el frontend.
- Navegación y pantallas administrativas.
- Usuario administrador de demostración con permisos de escritura.

## 5. Implementación de idempotencia

Se agregó el campo obligatorio `idempotencyKey` (UUID) a `CreateTransactionInput`.

Flujo:

1. Se valida la llave y se calcula un hash SHA-256 del contenido relevante de la petición.
2. Si la llave ya existe para la empresa y la operación `createTransaction`, se compara el hash.
3. Hash igual: se devuelve el movimiento original.
4. Hash distinto: se responde error claro de reutilización con otros datos.
5. Si la llave es nueva, el movimiento y el registro de idempotencia se confirman en la misma transacción.
6. Ante conflicto de unicidad por concurrencia, se hace rollback y se recupera el movimiento ganador.

## 6. Cambios en MySQL

Nueva tabla `idempotency_keys` con:

- `id`
- `company_id`
- `operation`
- `idempotency_key`
- `request_hash`
- `resource_id` (movimiento creado)
- `created_at`

Restricción única: `(company_id, operation, idempotency_key)`.

La tabla se crea con `Base.metadata.create_all` al iniciar la API. No se eliminan datos existentes.

## 7. Operaciones GraphQL

Consultas usadas por el dashboard administrativo:

- `me`
- `companyUsers`
- `accounts`
- `concepts`
- `accountConcepts`

Mutaciones:

- `createCompanyUser`
- `deactivateCompanyUser`
- `createAccount`
- `createConcept`
- `assignConceptToAccount`
- `removeConceptFromAccount`
- `createTransaction` (ahora con `idempotencyKey`)

`companyUsers` ahora incluye el rol activo de la membresía.

## 8. Dashboard administrativo

Se amplió la aplicación existente. El menú lateral distingue:

- Dashboard financiero
- Dashboard administrativo
  - Usuarios
  - Cuentas
  - Conceptos

Se conservan encabezado, nombre de empresa, cierre de sesión y el dashboard financiero.

## 9. Módulo de usuarios

- Contadores de activos, administrador principal e inactivos.
- Tabla con nombre, correo, rol, administrador y estado.
- Búsqueda y filtro de activos/inactivos.
- Alta con nombre, correo y contraseña.
- Desactivación lógica (`isActive=false`).
- Acciones de escritura ocultas sin `company.users.write`.

## 10. Módulo de cuentas

- Tabla con nombre, tipo traducido, banco, referencia enmascarada y estado.
- Filtros por tipo y activas.
- Alta con nombre, tipo, banco, CLABE y descripción corta.
- Botón de alta oculto sin `accounts.write`.

## 11. Módulo de conceptos

Pantalla dividida:

- Izquierda: catálogo de conceptos.
- Derecha: conceptos permitidos por cuenta seleccionada.

Se permiten asignar y quitar (baja lógica de la relación) con `concepts.write`.

## 12. Seguridad y RBAC

- El backend sigue exigiendo permisos reales en cada operación.
- El frontend solo oculta botones; no es la fuente de autorización.
- El usuario de demostración `admin@dashboard.example.com` tiene rol `ADMINISTRADOR`.
- El usuario `consulta@dashboard.example.com` conserva solo permisos de lectura.

## 13. Pruebas realizadas

1. Suite unitaria completa (`unittest discover`), incluyendo `test_idempotency` y `test_admin_operations`.
2. Prueba funcional GraphQL contra API local:
   - login administrador
   - consulta de usuarios
   - alta, correo duplicado y baja lógica
   - alta de cuenta y concepto
   - asignación, duplicado y remoción
   - denegación de escritura para rol consulta
   - idempotencia de `createTransaction`

## 14. Resultados reales

Archivo: `evidencias/actividad2/pruebas_funcionales.json`

Resultados relevantes:

- Reintento con la misma llave devolvió el mismo `id` de movimiento.
- Llave con datos distintos produjo error de conflicto.
- Correo duplicado rechazado.
- Concepto duplicado en cuenta rechazado.
- Tras quitar la asignación, el concepto permaneció activo en el catálogo.
- Rol `CONSULTA` sin `accounts.write`.

Las capturas de pantalla del navegador quedaron pendientes de obtención manual porque el entorno no permitió levantar Docker/MySQL ni automatizar un navegador gráfico de forma fiable. Las instrucciones están en `evidencias/actividad2/INSTRUCCIONES_CAPTURAS.md`.

## 15. Dificultades encontradas

1. El daemon de Docker no estaba disponible en el entorno de ejecución.
2. El token de GitHub CLI (`gh`) resultó inválido para autenticación de API.
3. La demo histórica usaba el tipo de cuenta `BANK`, incompatible con el enum GraphQL; se agregó alias de compatibilidad y se actualizó el seed a tipos válidos.
4. El repositorio local de la actividad no tenía `.git`; la entrega se versionó dentro de `Tareas_backend` como `U3_Actividad2`.

## 16. Soluciones implementadas

1. Pruebas ORM/API con SQLite manteniendo el mismo código de negocio.
2. Commits locales en el clon de `Tareas_backend`, con intento de push documentado.
3. Mapeo `BANK -> DEBIT` para lecturas legacy y seed corregido para instalaciones nuevas.
4. Consulta `me` para que el frontend obtenga permisos reales de la sesión.

## 17. Conclusiones

La Actividad 2 quedó integrada sobre la Actividad 1: la idempotencia protege `createTransaction`, el backend administrativo expone rol y sesión, y el dashboard permite gestionar usuarios, cuentas y conceptos respetando RBAC. La verificación automatizada cubrió los flujos críticos; la comprobación visual con MySQL/Docker debe completarse en la máquina del equipo siguiendo el README.
