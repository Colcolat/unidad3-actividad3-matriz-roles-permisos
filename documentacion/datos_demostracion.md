# Datos de demostración y comprobación manual

Usamos un conjunto de laboratorio reproducible para comprobar los valores de referencia de la consigna. No presentamos estos registros como operaciones de una empresa real. Se crean con `python -m app.demo` sobre una base vacía y después se consultan a través del API.

## Movimientos registrados

| Fecha y hora | Cuenta | Tipo | Importe MXN |
| --- | --- | --- | ---: |
| 25/10/2026 12:00:00 | Banco | Ingreso | 500.00 |
| 25/10/2026 12:00:00 | Caja | Ingreso | 300.00 |
| 25/10/2026 12:00:00 | Ahorro | Ingreso | 200.00 |
| 26/10/2026 00:00:00 | Banco | Ingreso | 2,000.00 |
| 26/10/2026 00:00:00 | Caja | Ingreso | 500.00 |
| 26/10/2026 00:00:00 | Ahorro | Ingreso | 1,000.00 |
| 30/10/2026 23:59:59 | Banco | Egreso | 1,700.00 |
| 30/10/2026 23:59:59 | Caja | Egreso | 1,000.00 |
| 30/10/2026 23:59:59 | Ahorro | Egreso | 200.00 |

## Período 26 al 30 de octubre de 2026

El saldo inicial reúne los movimientos anteriores al día 26. Los ingresos del período suman 2,000.00 + 500.00 + 1,000.00 = **3,500.00**. Los egresos suman 1,700.00 + 1,000.00 + 200.00 = **2,900.00**.

| Cuenta | Inicial | Ingresos | Egresos | Profit = ingresos - egresos | Final = inicial + profit |
| --- | ---: | ---: | ---: | ---: | ---: |
| Banco | 500.00 | 2,000.00 | 1,700.00 | 300.00 | 800.00 |
| Caja | 300.00 | 500.00 | 1,000.00 | -500.00 | -200.00 |
| Ahorro | 200.00 | 1,000.00 | 200.00 | 800.00 | 1,000.00 |
| **General** | **1,000.00** | **3,500.00** | **2,900.00** | **600.00** | **1,600.00** |

El saldo general es positivo y Caja termina con -200.00. Por eso `isInRed` es `false` y `accountsInRed` es `1`.

**Aclaración de la imagen de referencia:** el ejemplo visual de la consigna muestra 800.00 en la columna profit de Banco, aunque sus ingresos son 2,000.00 y sus egresos 1,700.00. Aplicando la fórmula escrita en la propia actividad, el profit correcto es **300.00**; los 800.00 corresponden al saldo final de Banco. Nuestra tabla, el API y el dashboard usan esa operación y coinciden con los totales generales solicitados.

## Otros períodos comprobados

| Período | Inicial | Ingresos | Egresos | Profit | Final | Lectura |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 26/10 al 26/10 | 1,000.00 | 3,500.00 | 0.00 | 3,500.00 | 4,500.00 | Incluye las entradas de las 00:00. |
| 30/10 al 30/10 | 4,500.00 | 0.00 | 2,900.00 | -2,900.00 | 1,600.00 | Profit negativo, general positivo. |
| 01/11 al 10/11 | 1,600.00 | 0.00 | 0.00 | 0.00 | 1,600.00 | Sin movimientos; se conserva el saldo previo. |

La respuesta real está en `evidencias/balance_mysql.json` y la extracción de movimientos en `evidencias/movimientos_mysql.csv`. La verificación de integración compara también una consulta SQL independiente con los valores de referencia.
