# Continuidad del proyecto

Revisamos la rama `actividad4-permisos-roles` del repositorio `dramirez2006/Tareas_backend`, en el commit `856c84080a60598338b1368ac969fcce96aa0c21`. Ahí está el Sistema General de Ingresos en la carpeta `U2_Actividad3`.

Los archivos `models.py`, `financial_models.py` y `rbac_models.py` de esta entrega coinciden byte por byte con los de esa rama. Conservamos su esquema de empresas, usuarios, membresías, cuentas, conceptos, movimientos y permisos.

La rama todavía solicita `actorCompanyUserId` en varias operaciones y su JWT solo incluye el usuario. Para cumplir la continuidad del Parcial II, tomamos la actualización de autenticación de la entrega local `unidad2_actividad6_equipo.zip`. Esa versión ya contiene `companyUserId` y `companyId` en el token, resuelve la identidad desde el encabezado Bearer y elimina el actor libre en el cliente. También conservamos sus pruebas de acceso y de permisos.

En las dos versiones revisadas faltaban las consultas de balance. Para esta actividad agregamos `app/balances.py` y los campos `generalBalance` y `accountBalance` en el esquema GraphQL. Ajustamos los errores de autenticación y permisos para que el cliente distinga una sesión inválida de un acceso denegado.

Finalmente, incorporamos el cliente web, el servicio de archivos estáticos en FastAPI, una configuración local sin secretos compartidos, el cargador de datos de demostración y las pruebas de balances e integración. El repositorio de origen no fue modificado.
