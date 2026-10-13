# API REST

El motor se expone como una API HTTP **sin estado**: en cada llamada el cliente envía todas las respuestas
que lleva y recibe la siguiente pregunta o el diagnóstico. No hay sesiones en el servidor, así que cada
cliente (frontend web, app móvil, un script recolector) decide cómo guardar la consulta.

## Ejecutarla

```bash
pip install -r requirements-api.txt
```
```bash
python -m uvicorn sistema_experto.api:app --reload
```

Se usa `python -m uvicorn` (y no `uvicorn` a secas) porque en Windows pip suele instalar los scripts fuera del PATH.

La documentación interactiva (Swagger) queda en <http://localhost:8000/docs> y el esquema OpenAPI en `/openapi.json`.

## Configuración

| Variable | Efecto |
|---|---|
| `SISTEMA_EXPERTO_API_KEYS` | Claves válidas separadas por comas. Se envían en la cabecera `X-API-Key`. **Sin esta variable la API queda abierta**: úsalo solo en desarrollo. |
| `SISTEMA_EXPERTO_CONOCIMIENTO` | Ruta de otra base de conocimiento JSON (por ejemplo, la de un cliente). |
| `SISTEMA_EXPERTO_CORS` | Orígenes permitidos separados por comas, si el frontend vive en otro dominio. |

`/salud` nunca pide clave, para que balanceadores y monitoreo puedan consultarla.

## Rutas

| Método y ruta | Qué hace |
|---|---|
| `GET /salud` | Estado del servicio y versión. |
| `GET /v1/conocimiento` | Todas las preguntas (tipo, opciones, unidad, rango, ayuda) y cuántos diagnósticos cubre. |
| `POST /v1/consulta/siguiente` | Dadas las respuestas, devuelve la próxima pregunta o `terminada: true`. |
| `POST /v1/consulta/resultado` | Diagnósticos ordenados por certeza, con evidencias, razonamiento y descartados. |
| `POST /v1/consulta/informe` | El mismo diagnóstico como **PDF** con la marca del taller (ver abajo). |
| `GET /v1/precision` | Precisión medida con los casos de referencia. |

### El cuerpo de las consultas

```json
{
  "respuestas": { "enciende": false, "tipo_equipo": "escritorio" },
  "completo": false,
  "omitir_pruebas": false
}
```

- `respuestas`: `hecho → valor`. El valor es `true`/`false` (sí/no), la **clave** de una opción
  (`"escritorio"`), un número, o `null` para "no sé".
- `completo`: hace todas las preguntas en orden, sin consulta dinámica.
- `omitir_pruebas`: termina sin las pruebas de verificación que falten.

Un hecho desconocido o un valor que el hecho no admite responde `422` con el motivo de cada error.

### El bucle del cliente

```
respuestas = {}
repetir:
    r = POST /v1/consulta/siguiente  {respuestas}
    si r.terminada: salir
    mostrar r.pregunta ; respuestas[r.pregunta.hecho] = lo que responda el usuario
POST /v1/consulta/resultado  {respuestas}
```

"Deshacer" es quitar la última respuesta y volver a llamar. `pregunta.hipotesis` alimenta el "¿por qué me
preguntas esto?" y `pregunta.rivales` marca una pregunta de diagnóstico diferencial.

### Ejemplo

```bash
curl -X POST http://localhost:8000/v1/consulta/resultado \
  -H "Content-Type: application/json" -H "X-API-Key: mi-clave" \
  -d '{"respuestas": {"enciende": false, "tipo_equipo": "escritorio", "luces_led": false, "interruptor_fuente_encendido": true}}'
```

Devuelve, entre otros, `diagnosticos[0].descripcion` (`"Fuente de poder dañada"`), su `certeza`, las
`recomendaciones` y `advertencias` y el `razonamiento` paso a paso.

## Informe PDF

`POST /v1/consulta/informe` recibe el mismo cuerpo que las demás consultas, más la marca y los datos del
servicio, y devuelve un `application/pdf` descargable:

```json
{
  "respuestas": { "enciende": false, "tipo_equipo": "escritorio", "luces_led": false,
                  "interruptor_fuente_encendido": true },
  "marca": {
    "nombre": "Taller Los Pinos",
    "color": "#0b6e4f",
    "contacto": "Tel. 5555-1234 · Zona 10",
    "logo_base64": "iVBORw0KGgo..."
  },
  "servicio": {
    "cliente": "Ana López",
    "equipo": "Laptop HP 15, serie 8CG123",
    "tecnico": "Carlos Pérez",
    "observaciones": "No enciende desde ayer."
  }
}
```

Todos los campos de `marca` y `servicio` son opcionales. `color` es `#rrggbb`; `logo_base64` es un PNG o
JPG de hasta ~500 KB. Un color o un logo inválidos responden `422`.

El PDF trae el encabezado con la marca, los datos del servicio, el diagnóstico con su barra de certeza, las
recomendaciones y advertencias, otros diagnósticos posibles, los descartados con su motivo, lo que se
comprobó en el equipo, el razonamiento y el aviso de seguridad al pie. Sin diagnóstico, el informe lo dice y
recomienda una revisión presencial.

```bash
curl -X POST http://localhost:8000/v1/consulta/informe -H "Content-Type: application/json"   -d '{"respuestas": {"enciende": false, "tipo_equipo": "escritorio", "luces_led": false, "interruptor_fuente_encendido": true}, "marca": {"nombre": "Taller Los Pinos"}}'   --output informe.pdf
```

## Clientes, planes y facturación

Para operarla como servicio de pago, con una clave por cliente, planes y cuotas, ver [Modo comercial](comercial.md).

## Qué falta antes de ofrecerla a clientes

Ya están las claves por cliente, los planes, las cuotas y el conteo de consultas. Faltan el cobro automático
(pasarela de pagos), el despliegue con HTTPS y un portal para que el cliente vea su cuenta. Ver los límites
conocidos en [Modo comercial](comercial.md).
