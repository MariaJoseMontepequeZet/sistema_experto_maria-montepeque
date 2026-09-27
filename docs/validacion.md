# Validación: cómo se mide la precisión

Un sistema experto que dice "88 % de certeza" debe poder demostrar que acierta. Para eso existe una
colección de **casos de referencia** ([`casos/casos_referencia.json`](../casos/casos_referencia.json)) y una
evaluación automática que corre en cada cambio.

```bash
python main.py --validar
```

## Cómo se evalúa cada caso

Cada caso describe lo que el usuario **observaría** (y el resultado de las pruebas que haría) y el
**diagnóstico correcto**. La evaluación resuelve el caso con la **consulta dinámica completa**, igual que un
usuario real: el sistema elige qué preguntar y el caso responde; lo que el caso no indica se responde
"no sé". Así se mide el sistema completo (qué pregunta, cuándo se detiene y qué concluye), no solo las reglas.

## Métricas

| Métrica | Qué mide |
|---|---|
| **Precisión** | Casos en los que el diagnóstico principal es el correcto (sobre los casos que el conocimiento cubre). El CI exige como mínimo **90 %** |
| **Entre los 3 primeros** | Casos en los que el diagnóstico correcto aparece entre los tres primeros |
| **Falsos positivos** | Equipos sin falla a los que el sistema les atribuyó una. Debe ser **0** |
| **Preguntas promedio** | Cuántas preguntas necesita la consulta dinámica |
| **Calibración** | Para cada rango de certeza (por ejemplo 80–90 %), qué proporción de esos diagnósticos fue correcta. En un sistema bien calibrado, los que dicen 90 % aciertan alrededor del 90 % |

Los casos cuyo diagnóstico correcto **todavía no existe** en la base de conocimiento se reportan aparte,
como **fuera de cobertura**: no cuentan como fallos, pero muestran qué falta agregar.

## Tipos de casos

- **Diagnósticos:** al menos uno por cada falla que el sistema conoce (una prueba lo verifica).
- **Controles:** equipos sin falla (`"esperado": null`). El sistema no debe inventar un problema.
- **Casos difíciles:** varias causas posibles, o síntomas contradictorios resueltos por una prueba.
- **Fuera de cobertura:** fallas reales que el conocimiento aún no incluye.

## Formato

```json
{
  "id": "C11",
  "descripcion": "Sin imagen con un pitido corto; con otro monitor aparece imagen",
  "plantilla": "escritorio_sano",
  "respuestas": { "hay_video": false, "prueba_otro_monitor": true },
  "esperado": "falla_monitor",
  "fuente": "Sustitución del monitor o cable"
}
```

Las **plantillas** (`escritorio_sano`, `laptop_sana`…) evitan repetir las respuestas de un equipo normal:
el caso solo indica lo que cambia. El formato se valida al cargar: preguntas inexistentes, respuestas que no
corresponden al tipo de la pregunta, plantillas desconocidas, IDs duplicados o casos sin `esperado`.

## Un fallo encontrado por la validación

La primera evaluación dio **96.4 %**: el caso C12 (*un pitido largo y cortos, pero con otro monitor aparece
imagen*) terminaba **sin diagnóstico**. La prueba descartaba correctamente la tarjeta de video, pero la regla
del monitor exigía "un pitido corto", así que nadie proponía la causa real. Se agregó la regla **R17**
(monitor o cable según el resultado de la prueba) y la precisión pasó a **100 %**. Es el ciclo para el que
existe la validación: medir, encontrar el hueco, corregirlo y dejarlo cubierto por un caso.

## Limitación honesta

Los casos actuales se construyeron a partir de síntomas típicos documentados, **por la misma persona que
escribió las reglas**. Miden que el sistema es coherente con su conocimiento y detectan regresiones, pero
**no reemplazan una validación con casos reales** resueltos por técnicos, que es la única que mide la
precisión en el mundo real. Por eso:

- Cualquier diagnóstico equivocado reportado con la plantilla de *issues* "Proponer o corregir un
  diagnóstico" debe convertirse en un caso.
- Los casos reales deben indicar su origen en `fuente` (por ejemplo, "Caso real reportado en el issue #12").
- Cada regla nueva debe llegar con al menos un caso que la cubra.
