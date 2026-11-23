# Capturas manuales pendientes

Docker/MySQL no estuvo disponible en el entorno de automatización. Las pruebas GraphQL
de esta carpeta se ejecutaron contra el API local. Para completar capturas visuales:

1. Levantar MySQL y el API según el README.
2. Abrir http://127.0.0.1:8013/dashboard/
3. Iniciar sesión con admin@dashboard.example.com y DEMO_PASSWORD.
4. Capturar: Usuarios, Cuentas, Conceptos, error de correo duplicado, usuario consulta sin botones de alta.
5. En GraphiQL, repetir createTransaction con la misma idempotencyKey y capturar el mismo id.
