# Evidencias · Unidad III · Actividad 3 (Matriz de roles y permisos)

## 1. Matriz inicial coincidiendo con la sección 2.2
![Matriz inicial](evidencias/actividad3/01_matriz_inicial.png)
La pantalla **Roles y permisos** carga desde MySQL las cuatro columnas en orden (`Administrador` en solo lectura, `Contador`, `Capturista` y `Consulta`) y los diez permisos en cinco grupos coincidiendo exactamente con la matriz del Parcial II.

## 2. Columna de Capturista en GraphiQL (`rolePermissions`)
![Columna Capturista en GraphiQL](evidencias/actividad3/02_graphiql_capturista.png)
La consulta `rolePermissions(roleId)` en GraphiQL con `Authorization: Bearer <token>` devuelve los mismos cuatro permisos activos (`accounts.read`, `concepts.read`, `transactions.read`, `transactions.write`) que muestra la columna **Capturista** en el dashboard.

## 3. Vista previa anunciando activar `accounts.write`
![Vista previa activar accounts.write](evidencias/actividad3/03_vista_previa_accounts_write.png)
Al marcar **Crear cuentas (`accounts.write`)** en la columna **Capturista** y pulsar **Vista previa**, `previewRolePermissions` anuncia activar `accounts.write`, desactivar `ninguno`, `4` sin cambio y `5` de total final sin escribir todavía en la base de datos.

## 4. Pantalla de Cuentas del capturista antes y después del guardado
![Cuentas del capturista antes](evidencias/actividad3/04a_cuentas_capturista_antes.png)
![Cuentas del capturista después](evidencias/actividad3/04b_cuentas_capturista_despues.png)
Antes de guardar la columna **Capturista**, el capturista ve la tabla de **Cuentas** sin el botón **Nueva cuenta**; después de guardar `accounts.write`, el botón **Nueva cuenta** aparece para todos los usuarios con el puesto **Capturista**.

## 5. Cambio de puesto en Usuarios (Consulta → Capturista) sin mover la matriz
![Cambio de puesto en Usuarios](evidencias/actividad3/05a_usuarios_assign_role.png)
![Columna Consulta intacta](evidencias/actividad3/05b_matriz_consulta_intacta.png)
Al cambiar en **Usuarios** el puesto de la persona de **Consulta** a **Capturista** mediante `assignRole`, `isAdmin` permanece en `No` y la columna **Consulta** de la matriz conserva sus cuatro permisos intactos.

## 6. Segundo guardado de la misma columna (`changed: false`)
![Segundo guardado idempotente](evidencias/actividad3/06_segundo_guardado_changed_false.png)
Al guardar por segunda vez la misma columna **Capturista** sin cambios, `setRolePermissions` responde `changed: false` y el dashboard informa que no hubo modificaciones ni se duplicaron filas en `role_permissions`.

## 7. Contador en solo lectura o Capturista sin el ítem de menú
![Contador en solo lectura](evidencias/actividad3/07_contador_solo_lectura.png)
Al iniciar sesión como **Contador** (`roles.read` sin `roles.write`), la matriz se muestra en modo solo lectura con casillas deshabilitadas y sin botones de guardado (mientras que un **Capturista** sin `roles.read` ni siquiera ve el ítem **Roles y permisos** en el menú).
