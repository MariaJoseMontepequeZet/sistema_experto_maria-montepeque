# Guía para escribir la base de conocimiento

Todo lo que el sistema "sabe" está en [`conocimiento/diagnostico_pc.json`](../conocimiento/diagnostico_pc.json).
Para agregar o corregir un diagnóstico **no hace falta programar**: solo editar ese archivo.

## Estructura del archivo

```json
{
  "nombre": "Diagnóstico de PC",
  "hechos": { ... },
  "reglas": [ ... ]
}
```

### `hechos`: lo que se le pregunta al usuario

Cada hecho de entrada tiene un nombre (en `snake_case`, sin tildes), su pregunta y un **tipo de
respuesta**. Todos admiten además la respuesta **"no sé"**.

| Tipo | Cuándo usarlo | Campos extra |
|---|---|---|
| `si_no` (por defecto) | La respuesta es sí o no | — |
| `opcion` | Hay varias respuestas posibles y excluyentes | `opciones`: `{valor: etiqueta}`, al menos 2 |
| `numero` | Un valor medido | `unidad`, `minimo`, `maximo` (opcionales) |

Cualquier tipo puede llevar `ayuda`: una explicación de cómo averiguar la respuesta, que se muestra
junto a la pregunta.

```json
"calor_excesivo": { "pregunta": "¿El chasis está muy caliente al tacto?" },

"tipo_equipo": {
  "pregunta": "¿Qué tipo de equipo es?",
  "tipo": "opcion",
  "opciones": { "escritorio": "Computadora de escritorio", "laptop": "Laptop" }
},

"temperatura_cpu": {
  "pregunta": "¿Qué temperatura marca el procesador cuando el equipo está en uso?",
  "tipo": "numero", "unidad": "°C", "minimo": 0, "maximo": 125,
  "ayuda": "Puedes verla con HWMonitor o Core Temp."
}
```

- Formula las preguntas de sí/no en positivo (`hay_video`, no `sin_video`). La negación se expresa en las reglas.
- **Prefiere una opción múltiple a varias preguntas de sí/no** cuando las respuestas son excluyentes. Por ejemplo, un solo `patron_pitidos` distingue RAM, video y monitor, mientras que un simple "¿hay pitidos?" confundía un arranque normal (un pitido corto) con una falla de RAM.
- Usa preguntas numéricas cuando un umbral objetivo sea más confiable que una impresión ("¿el procesador supera los 90 °C?" en lugar de "¿está muy caliente?").

### Condiciones según el tipo del hecho

| Tipo del hecho | Condición en `si` | Significa |
|---|---|---|
| `si_no` | `true` / `false` | Debe ser sí / debe ser no |
| `opcion` | `"laptop"` | Debe ser esa opción |
| `opcion` | `["ninguno", "uno_corto"]` | Debe ser cualquiera de esas opciones |
| `numero` | `{">=": 90}` | Debe cumplir la comparación. Operadores: `>`, `>=`, `<`, `<=` |
| `numero` | `{">=": 80, "<": 90}` | Debe cumplir **todas** las comparaciones (un rango) |
| hecho intermedio | `true` | Debe haberse deducido |

### `reglas`: SI condiciones ENTONCES conclusión

```json
{
  "id": "R07",
  "descripcion": "Sobrecalentamiento",
  "si": { "enciende": true, "se_apaga_solo": true, "calor_excesivo": true },
  "entonces": "sobrecalentamiento",
  "recomendacion": "Limpiar ventiladores y reaplicar pasta térmica",
  "advertencia": "Apaga y desconecta el equipo antes de abrirlo.",
  "confianza": 0.90
}
```

| Campo | Obligatorio | Qué es |
|---|---|---|
| `id` | ✅ | Identificador único. Convención: `R01`, `R02`… para diagnósticos; `I01`, `I02`… para reglas intermedias |
| `descripcion` | ✅ | Nombre legible del diagnóstico, se muestra al usuario |
| `si` | ✅ | Condiciones que deben cumplirse **todas** (AND), según la tabla anterior |
| `entonces` | ✅ | Hecho que se concluye cuando la regla se dispara |
| `confianza` | ✅ | Qué tan seguro es el diagnóstico si se cumplen las condiciones, entre 0 y 1 |
| `recomendacion` | — | Qué hacer. **Si la regla la tiene, es un diagnóstico final**; si no, produce un hecho intermedio |
| `advertencia` | — | Aviso de seguridad. Obligatorio en la práctica si la recomendación implica abrir el equipo o arriesgar datos |

## Reglas intermedias

Cuando varios diagnósticos comparten condiciones, conviene agruparlas en una regla intermedia:

```json
{ "id": "I01", "descripcion": "Arranca pero no muestra imagen",
  "si": { "enciende": true, "hay_video": false },
  "entonces": "arranque_sin_video", "confianza": 1.0 }
```

Después, otras reglas usan `"arranque_sin_video": true` como condición. Así el motor encadena el
razonamiento y la explicación muestra los pasos intermedios.

> Los hechos intermedios solo pueden usarse como `true` en otras reglas, nunca como `false`.

## Cómo elegir la confianza

| Valor | Cuándo usarlo |
|---|---|
| 0.90 – 1.00 | Los síntomas prácticamente solo se explican por esta causa |
| 0.75 – 0.89 | Causa más probable, pero hay alternativas razonables |
| 0.50 – 0.74 | Posible; conviene confirmarlo con una prueba |
| 1.00 en intermedias | Cuando la regla solo resume hechos (no es una suposición) |

## Validación automática

Al cargar el archivo, el sistema revisa todo y **muestra todos los errores juntos**:

- condiciones que no tienen pregunta ni regla que las produzca,
- IDs duplicados o campos desconocidos (por ejemplo, un error de tipeo en `advertencia`),
- dos reglas con exactamente las mismas condiciones,
- confianza fuera de rango,
- dependencias circulares entre hechos,
- preguntas que ninguna regla usa,
- advertencias en reglas que no tienen recomendación,
- condiciones que no corresponden al tipo del hecho (por ejemplo, `true` sobre una pregunta de opción),
- opciones que el hecho no tiene (por ejemplo, `"tablet"` si solo existen escritorio y laptop),
- rangos numéricos imposibles (por ejemplo, `{">": 90, "<": 80}`) u operadores desconocidos,
- campos que no corresponden al tipo del hecho (por ejemplo, `unidad` en una pregunta de sí/no).

Para comprobar tus cambios:

```bash
python -c "from sistema_experto import cargar; b = cargar(); print(len(b.reglas), 'reglas OK')"
```
```bash
python -m unittest
```

El CI hace la misma verificación en cada Pull Request.

## Buenas prácticas

- **Un diagnóstico, una causa.** Si una regla sugiere dos causas distintas, sepárala o agrega la pregunta que las distingue.
- **Condiciones que discriminen.** Cada condición debe ayudar a separar este diagnóstico de otros parecidos.
- **Recomendaciones accionables.** "Probar con un solo módulo de RAM" es mejor que "revisar la RAM".
- **Seguridad primero.** Toda recomendación que implique abrir el equipo lleva `advertencia`.
- **Cita la fuente** (manual del fabricante, documentación técnica) en el Pull Request.
