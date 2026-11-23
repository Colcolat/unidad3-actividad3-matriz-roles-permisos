# Evidencia de idempotencia (GraphiQL)

Mutación utilizada (mismo cuerpo y misma llave en dos envíos):

```graphql
mutation CrearMovimiento($input: CreateTransactionInput!) {
  createTransaction(input: $input) {
    id
    amount
    transactionType
  }
}
```

Resultado real de la prueba automatizada (`pruebas_funcionales.json`):

- Primera ejecución: id `10`
- Reintento con la misma llave: id `10`
- Misma llave con monto distinto: error `La llave de idempotencia ya fue utilizada con otros datos.`
- Llave nueva con el mismo monto: id `11`

Nota: en este entorno Docker/MySQL no estuvo disponible; la comprobación se realizó sobre SQLite local con la misma lógica de UniqueConstraint y transacción única. En entrega con Docker Compose la tabla `idempotency_keys` se crea automáticamente al iniciar el API.
