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
junto a la pregunta. Y cualquier tipo puede marcarse como **prueba de verificación** con
`"prueba": true` (ver [Pruebas de verificación](#pruebas-de-verificación)).

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
| `id` | ✅ | Identificador único. Convención: `R01`… diagnósticos, `I01`… reglas intermedias, `E01`… evidencias |
| `descripcion` | ✅ | Nombre legible del diagnóstico, se muestra al usuario |
| `si` | ✅ | Condiciones que deben cumplirse **todas** (AND), según la tabla anterior |
| `entonces` | ✅ | Hecho que se concluye cuando la regla se dispara |
| `confianza` | ✅ | Entre -1 y 1, distinta de 0. Positiva: cuánto apoya la conclusión; negativa: cuánto la contradice (ver [Evidencia](#evidencia-a-favor-y-en-contra)) |
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

## Evidencia a favor y en contra

Un diagnóstico no solo se confirma: también se puede **debilitar**. Una regla **sin recomendación** que
concluye un diagnóstico es *evidencia*: con confianza positiva lo refuerza, con confianza negativa lo
contradice.

```json
{
  "id": "E01",
  "descripcion": "La temperatura del procesador es normal",
  "si": { "enciende": true, "temperatura_cpu": { "<": 70 } },
  "entonces": "sobrecalentamiento",
  "confianza": -0.6
}
```

Todas las evidencias sobre un mismo diagnóstico se combinan con los **factores de certeza de MYCIN**:

| Caso | Fórmula | Ejemplo |
|---|---|---|
| Ambas a favor | `a + b × (1 − a)` | 0.9 y 0.3 → 0.93 |
| Ambas en contra | `a + b × (1 + a)` | −0.5 y −0.5 → −0.75 |
| Signos opuestos | `(a + b) / (1 − min(│a│, │b│))` | 0.9 y −0.6 → 0.75 |

Un diagnóstico se muestra si su certeza neta **supera 0.2** (el umbral de MYCIN). Si una regla lo sugirió
pero la evidencia en contra lo dejó por debajo, aparece como **descartado**, con el motivo.

Reglas de uso (el validador las comprueba):

- La evidencia **no lleva** `recomendacion` ni `advertencia`: las aporta la regla principal del diagnóstico.
- La evidencia en contra solo puede apuntar a un **diagnóstico** (un hecho que concluye alguna regla con
  recomendación), y ese diagnóstico no puede usarse como condición de otras reglas.
- La evidencia a favor, por sí sola, **nunca crea un diagnóstico**: solo refuerza uno que ya sugirió una
  regla con recomendación.
- La consulta dinámica también pregunta por la evidencia de los diagnósticos que todavía pueden superar el
  umbral, porque puede cambiar su certeza. Cuando la evidencia en contra ya deja a un diagnóstico sin
  posibilidad de superarlo, deja de preguntar por él (ver [arquitectura](arquitectura.md#consulta-dinámica)).
- Una prueba que suma a un diagnóstico y resta a otro (por ejemplo, otro monitor) es la que el sistema usa
  para el **diagnóstico diferencial** cuando esos dos están cerca: vale la pena escribirlas.

## Pruebas de verificación

Un síntoma describe lo que el usuario **observa**; una prueba le pide **hacer algo** y contar el resultado:
cambiar el monitor, probar otra fuente, revisar el estado SMART del disco. Es lo que hace un técnico
para confirmar un diagnóstico antes de reparar, y es la evidencia más fuerte que puede tener el sistema.

```json
"prueba_otro_monitor": {
  "pregunta": "Conecta otro monitor o usa otro cable de video. ¿Ahora aparece imagen?",
  "prueba": true,
  "ayuda": "Revisa también que el monitor tenga seleccionada la entrada correcta."
}
```

- Las pruebas se preguntan **al final**, después de agotar los síntomas, y solo si ayudan a alguna
  hipótesis que sigue abierta.
- Siempre son opcionales: el usuario puede responder *"No puedo hacerla"* o, en la web, ver el
  diagnóstico sin hacer más pruebas.
- Su resultado se conecta con reglas de **evidencia** (`E…`). Una misma prueba puede apoyar una causa y
  descartar otra: si con otro monitor aparece imagen, apoya "monitor o cable" y descarta "tarjeta de video".
- Una prueba que **descarta** una causa (el problema sigue igual tras cambiar la pieza sospechosa) debe
  tener una confianza de alrededor de **−0.95**, para superar incluso a un síntoma fuerte. Con −0.8, un
  diagnóstico de 0.92 quedaría en 60 %, y eso sería afirmar una causa que la prueba ya descartó.
- Pide solo pruebas que el usuario pueda hacer: por ejemplo, la temperatura del procesador solo se pide
  si la pantalla muestra imagen (hace falta para abrir el programa que la mide).

## Cómo elegir la confianza

| Valor | Cuándo usarlo |
|---|---|
| 0.90 – 1.00 | Los síntomas prácticamente solo se explican por esta causa |
| 0.75 – 0.89 | Causa más probable, pero hay alternativas razonables |
| 0.50 – 0.74 | Posible; conviene confirmarlo con una prueba |
| 1.00 en intermedias | Cuando la regla solo resume hechos (no es una suposición) |
| 0.20 – 0.40 | Evidencia a favor: un indicio que acompaña, pero no alcanza por sí solo |
| −0.40 – −0.60 | Evidencia en contra moderada: hace menos probable el diagnóstico |
| −0.70 – −0.90 | Evidencia en contra fuerte: hace muy poco probable el diagnóstico |
| 0.85 – 0.95 | Resultado de una prueba de verificación que confirma la causa |
| −0.95 | Resultado de una prueba de verificación que descarta la causa |

## Validación automática

Al cargar el archivo, el sistema revisa todo y **muestra todos los errores juntos**:

- condiciones que no tienen pregunta ni regla que las produzca,
- IDs duplicados o campos desconocidos (por ejemplo, un error de tipeo en `advertencia`),
- dos reglas con exactamente las mismas condiciones,
- confianza fuera de rango (debe estar entre -1 y 1, distinta de 0),
- evidencia en contra con recomendación, sobre algo que no es un diagnóstico, o sobre un diagnóstico que se usa como condición,
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
```bash
python main.py --validar
```

El CI hace la misma verificación en cada Pull Request. **Cada regla nueva debe llegar con al menos un caso de
referencia** que la cubra (ver [Validación](validacion.md)): así se sabe si mejora la precisión o si rompe
otro diagnóstico.

## Buenas prácticas

- **Un diagnóstico, una causa.** Si una regla sugiere dos causas distintas, sepárala o agrega la pregunta que las distingue.
- **Condiciones que discriminen.** Cada condición debe ayudar a separar este diagnóstico de otros parecidos.
- **Recomendaciones accionables.** "Probar con un solo módulo de RAM" es mejor que "revisar la RAM".
- **Seguridad primero.** Toda recomendación que implique abrir el equipo lleva `advertencia`.
- **Cita la fuente** (manual del fabricante, documentación técnica) en el Pull Request.
