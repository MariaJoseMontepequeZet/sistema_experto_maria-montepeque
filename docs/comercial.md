# Modo comercial: clientes, planes y facturación

La API tiene dos modos:

| Modo | Cuándo | Qué hace |
|---|---|---|
| **Abierto** | No existe `SISTEMA_EXPERTO_ADMIN_KEY` | Funciona como antes: abierta, o con las claves de `SISTEMA_EXPERTO_API_KEYS`. No cuenta consultas. Es para desarrollo. |
| **Comercial** | Existe `SISTEMA_EXPERTO_ADMIN_KEY` | Cada llamada exige la clave de un cliente dado de alta, aplica su plan y cuenta sus consultas. |

## Planes y precios

Salen de [configuracion/planes.json](../configuracion/planes.json), que se edita sin programar
(o de otro archivo, con `SISTEMA_EXPERTO_PLANES`):

| Plan | Precio | Incluye | Llamadas por minuto |
|---|---|---|---|
| `por_uso` | $5 por cada consulta | sin tope mensual | 30 |
| `basico` | $10 al mes | 50 consultas | 60 |
| `profesional` | $15 al mes | 150 consultas | 120 |

Hay dos tipos: `por_uso` (se cobra `precio_usd` por consulta) y `mensual` (se cobra `precio_usd` fijos
e incluye `consultas_incluidas`). El archivo se valida al arrancar y reporta todos los errores juntos.

### Qué es una consulta

Una **consulta** es un diagnóstico entregado: una llamada a `/v1/consulta/resultado` o a
`/v1/consulta/informe`. Se cuenta **una sola vez por cliente, mes y conjunto de respuestas**:

- Hacer las preguntas (`/v1/consulta/siguiente`) no cuesta nada.
- Pedir el PDF de un diagnóstico que ya se consultó no cobra otra vez, ni repetir la misma consulta.
- Un diagnóstico con respuestas distintas sí es otra consulta.
- Una petición rechazada (`422`) no cuenta.

Al agotar un plan mensual, la API responde `402` y **no entrega el diagnóstico**. Las consultas ya hechas
se pueden repetir. La cuota se renueva el primer día del mes (UTC). Cada respuesta de `/resultado` e
`/informe` trae `X-Consultas-Usadas` y `X-Consultas-Restantes`.

Superar las llamadas por minuto responde `429` con `Retry-After`.

## Puesta en marcha

```bash
export SISTEMA_EXPERTO_ADMIN_KEY="una-clave-larga-y-secreta"
python -m uvicorn sistema_experto.api:app
```

En PowerShell: `$env:SISTEMA_EXPERTO_ADMIN_KEY = "una-clave-larga-y-secreta"`.

La base de datos de clientes es un archivo SQLite en `datos/clientes.db` (cambia la ruta con
`SISTEMA_EXPERTO_BD`). Se crea sola y **no se sube a git**. Respáldala: ahí está lo que vas a facturar.

## Administración

Todas estas rutas piden la cabecera `X-Admin-Key`. Sin `SISTEMA_EXPERTO_ADMIN_KEY` no existen (`404`).

| Ruta | Qué hace |
|---|---|
| `POST /admin/clientes` | Da de alta `{"nombre": "Taller Los Pinos", "plan": "basico"}` y devuelve su clave. |
| `GET /admin/clientes` | Lista clientes con plan, consumo del mes y el prefijo de sus claves. |
| `PUT /admin/clientes/{id}` | Cambia el `plan` o suspende/reactiva la cuenta con `activo`. |
| `POST /admin/clientes/{id}/claves` | Emite otra clave (para rotarla). |
| `DELETE /admin/claves/{prefijo}` | Revoca una clave por sus primeros 11 caracteres. |
| `GET /admin/facturacion?periodo=2026-10` | Lo que se debe facturar a cada cliente en el mes. |

**La clave completa solo se ve al crearla**: en la base queda su huella SHA-256, así que ni tú puedes
recuperarla. Si un cliente la pierde, emite otra y revoca la anterior.

```bash
curl -X POST http://localhost:8000/admin/clientes -H "X-Admin-Key: una-clave-larga-y-secreta" \
  -H "Content-Type: application/json" -d '{"nombre": "Taller Los Pinos", "plan": "basico"}'
```

### Facturación

`/admin/facturacion` calcula, por cliente: `por_uso` = consultas × `precio_usd`; `mensual` = `precio_usd`
fijos (aunque no haya consultado, si la cuenta está activa). Un cliente `por_uso` sin consultas no aparece.
Un cliente suspendido aparece solo si consultó ese mes.

El sistema **mide y calcula, pero no cobra**: no hay pasarela de pagos. La factura la emites tú con esos
importes.

## Lo que el cliente ve

`GET /v1/uso` con su clave devuelve su plan, las consultas del mes, cuántas le quedan y el importe.

## Límites conocidos

- El límite por minuto vive en la memoria del proceso. Con varios procesos o servidores cada uno cuenta
  aparte; para escalar habría que pasarlo a Redis.
- SQLite aguanta bien un servicio pequeño con un solo servidor. Con varios servidores o mucho tráfico,
  conviene PostgreSQL.
- No hay pasarela de pagos (Stripe u otra), ni cobro automático, ni portal para que el cliente cambie de plan.
- Falta HTTPS: se pone delante con el servidor web o la plataforma donde se despliegue.
