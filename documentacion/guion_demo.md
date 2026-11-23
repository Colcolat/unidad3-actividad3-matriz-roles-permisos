# Guion de demostración · Unidad III, actividad 1

**Duración aproximada: 3 a 4 minutos.** Antes de comenzar, dejamos MySQL y el API encendidos y consultamos la contraseña local indicada en el README.

1. **Entramos al sistema.** Abrimos el dashboard e iniciamos sesión con `consulta@dashboard.example.com`. Explicamos que el acceso usa un usuario registrado en MySQL y que el servidor entrega un token para las siguientes consultas.
2. **Mostramos el período de referencia.** Elegimos del 26 al 30 de octubre de 2026. Señalamos el saldo inicial de 1,000.00, los ingresos de 3,500.00, los egresos de 2,900.00, el profit de 600.00 y el saldo final de 1,600.00. Todos los importes están en MXN y vienen de `generalBalance`.
3. **Revisamos las cuentas.** Bajamos a la tabla y mostramos Caja con -200.00. Aclaramos que una cuenta puede estar en rojo aunque el general sea positivo. Comparamos Banco, Caja y Ahorro con la tabla manual del reporte.
4. **Cambiamos las fechas.** Consultamos solamente el 26 de octubre: el saldo final cambia a 4,500.00 porque los egresos son del día 30. Después invertimos el rango y mostramos que aparece una advertencia sin enviar una consulta inválida.
5. **Mostramos el control de acceso.** Cerramos sesión y entramos con `sinpermiso@dashboard.example.com`. Se muestra acceso denegado y no aparecen balances. Comentamos que los permisos se comprueban en el backend.
6. **Cerramos la demostración.** Mostramos dónde están el README, las evidencias y la consulta GraphQL. Finalizamos cerrando sesión.

Cada integrante debe poder relacionar los indicadores con los campos GraphQL. El orden de intervención entre personas se acuerda antes de la presentación.
