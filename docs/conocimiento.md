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

Cada hecho de entrada tiene un nombre (en `snake_case`, sin tildes) y su pregunta:

```json
"calor_excesivo": { "pregunta": "¿El chasis está muy caliente al tacto?" }
```

- La pregunta debe poder responderse con **sí / no / no sé**.
- Formúlala en positivo (`hay_video`, no `sin_video`). La negación se expresa en las reglas.

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
| `si` | ✅ | Condiciones que deben cumplirse **todas** (AND). `true` = el hecho debe ser verdadero, `false` = debe ser falso |
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
- advertencias en reglas que no tienen recomendación.

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
