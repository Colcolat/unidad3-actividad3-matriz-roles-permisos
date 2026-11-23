# Unidad III · Actividad 3 — Matriz de roles y permisos del sistema

Extensión del cliente `dashboard/` (Actividades 1 y 2) y del backend GraphQL (`ingresos/`) para visualizar y gestionar la matriz de roles y permisos y asignar puestos en la tabla de Usuarios.

**Repositorio de entrega:** https://github.com/Colcolat/unidad3-actividad3-matriz-roles-permisos

## Integrantes del equipo

| Nombre | Matrícula |
| --- | --- |
| Angel Abraham Lugo Saenz | SW2409052 |
| Juan Jose Zapata Buenfil | SW2509044 |
| Josue Enmanuel Poot Mateo | SW2509033 |
| Sergio Origion Huerta Martinez | SW2509012 |
| Diego Ramirez Magaña | SW2509051 |

**Docente:** Gimer Amilcar Cervera Evia.  
**Asignatura:** Fundamentos de arquitectura de software y desarrollo backend.

## Cómo ejecutar el proyecto

1. Desde la carpeta `ingresos/`, activar el entorno virtual e instalar dependencias:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. Configurar `.env` (a partir de `ingresos/.env.example`) con la conexión a MySQL y `JWT_SECRET`.
3. Iniciar el servidor:
   ```bash
   uvicorn app.main:app --reload
   ```
4. Abrir el dashboard en `http://127.0.0.1:8000/dashboard/` (GraphiQL en `http://127.0.0.1:8000/graphql`).

## Cómo se abre Roles y permisos

1. Inicia sesión con un usuario cuyo rol tenga el permiso `roles.read` (por ejemplo, **Administrador** o **Contador**).
2. En el menú lateral izquierdo, haz clic en **Dashboard administrativo** y luego en el sub-ítem **Roles y permisos**.
   - Si el usuario no tiene `roles.read` (como **Capturista** o **Consulta**), el ítem **Roles y permisos** no aparece en el menú y el API rechaza la consulta directa con `FORBIDDEN`.

## Con qué usuario se edita la matriz

- **Administrador** (cuenta con `roles.read` y `roles.write`, por ejemplo `admin@dashboard.example.com` / `ana@demo.mx`).
- La columna **Administrador** se muestra en solo lectura y nunca se envía a `setRolePermissions`.
- Para editar **Contador**, **Capturista** o **Consulta**: marca o desmarca celdas, pulsa **Vista previa** al pie de la columna (`previewRolePermissions`) y luego **Guardar columna** (`setRolePermissions`). Al guardar una segunda vez sin cambios, el API responde `changed: false` sin duplicar filas.
- En **Usuarios**, el mismo administrador puede cambiar el puesto de una membresía desde el selector de la columna **Rol** y pulsar **Guardar** (`assignRole`), sin modificar `isAdmin`.

## Con qué usuarios se comprueba el efecto

- **Capturista** (sin `accounts.write` inicialmente):
  - Antes de activar `accounts.write` en la columna **Capturista**, entra a **Dashboard administrativo → Cuentas** y comprueba que no aparece el botón **Nueva cuenta**.
  - Después de activar `accounts.write` y guardar la columna **Capturista**, vuelve a iniciar sesión como **Capturista** (y con un segundo Capturista) y comprueba que **Nueva cuenta** ya aparece para todo el puesto.
- **Consulta**:
  - Después de que el administrador cambie su puesto de **Consulta** a **Capturista** en **Usuarios**, comprueba que `isAdmin` sigue en `No`, que la columna **Consulta** de la matriz no cambió y que con su mismo token ya puede registrar movimientos.
- **Contador** (tiene `roles.read`, pero no `roles.write`):
  - Abre **Roles y permisos** y comprueba que ve la cuadrícula en modo solo lectura (casillas deshabilitadas y sin botones de guardado).

## Pruebas automatizadas

- Frontend:
  ```bash
  node dashboard/format.test.mjs
  node dashboard/matrix.test.mjs
  ```
- Backend:
  ```bash
  cd ingresos && python3 -m unittest discover -s tests -p "test_*.py" -v
  ```
