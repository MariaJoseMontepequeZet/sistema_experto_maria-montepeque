# Sistema Experto: Diagnóstico de PC 🖥️

[![Tests](https://github.com/MariaJoseMontepequeZet/sistema_experto_maria-montepeque/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/MariaJoseMontepequeZet/sistema_experto_maria-montepeque/actions/workflows/tests.yml)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Motor sin dependencias](https://img.shields.io/badge/motor-sin%20dependencias-brightgreen)
![Streamlit](https://img.shields.io/badge/interfaz%20web-Streamlit-FF4B4B)

Este fue mi primer acercamiento a los sistemas expertos. La actividad consistía en recibir un código base generado con IA, entenderlo, corregirlo si era necesario y extenderlo con desafíos adicionales. Aquí explico qué hace cada parte y qué aprendí en el proceso.

---

## Cómo ejecutar el programa

Requiere Python 3.10 o superior. Hay dos interfaces sobre el mismo motor.

### Interfaz web (Streamlit)

```bash
pip install -r requirements.txt
```
```bash
streamlit run app.py
```

Se abre en el navegador con:
- botones Sí / No / No sé y la opción de deshacer;
- el diagnóstico con su certeza y otras posibilidades;
- el **diagrama de la cadena de razonamiento**;
- un explorador de hipótesis (encadenamiento hacia atrás);
- el mapa completo de la base de conocimiento.

### Consola (sin dependencias)

```bash
python main.py
```

También se puede ejecutar como módulo (`python -m sistema_experto`) y usar otra base de conocimiento:

```bash
python main.py --conocimiento conocimiento/diagnostico_pc.json --salida red_inferencia.json
```

El programa te hace preguntas sobre los síntomas del equipo y al final te dice qué podría estar fallando y qué hacer. Solo pregunta lo que sirve para las hipótesis que siguen abiertas. Por ejemplo, si el equipo no enciende, termina en 2 preguntas en lugar de 14.

| Respuesta | Significado |
|---|---|
| `s` / `n` | sí / no |
| `ns` | no sé (el síntoma queda desconocido y no se vuelve a preguntar) |
| `?` | ¿por qué me preguntas esto? (muestra qué diagnósticos se están evaluando) |

Para responder todas las preguntas en orden, como en la versión original:

```bash
python main.py --completo
```

Para correr las pruebas:

```bash
python -m unittest -v
```

## Estructura del proyecto

```
conocimiento/
  diagnostico_pc.json   ← reglas y preguntas (se editan sin tocar Python)
sistema_experto/
  modelo.py             ← Regla, BaseDeConocimiento, BaseDeHechos
  conocimiento.py       ← carga y validación del JSON
  motor.py              ← encadenamiento hacia adelante / atrás, consulta dinámica, exportación
  visualizacion.py      ← diagramas Graphviz (DOT) del razonamiento y de la red
  cli.py                ← interfaz por consola (única parte con input/print)
tests/
  test_motor.py
  test_consulta_dinamica.py
  test_visualizacion.py
  test_app.py           ← simula la interfaz web (se omite si no hay Streamlit)
app.py                  ← interfaz web (Streamlit)
main.py                 ← punto de entrada de la consola
requirements.txt        ← solo para la interfaz web
```

---

## ¿Qué es un sistema experto?

Antes de empezar no tenía muy claro el concepto. Lo que entendí es que un sistema experto intenta imitar cómo razona un técnico o especialista humano. En lugar de que el programador escriba paso a paso "si pasa esto, haz aquello", el sistema tiene separadas dos cosas: las reglas del experto y el motor que las aplica. Eso fue lo que más me llamó la atención, que el motor no sabe nada de computadoras, solo sabe cómo comparar condiciones con hechos.

---

## Los 5 componentes del código

### 1. Base de Conocimiento — `conocimiento/diagnostico_pc.json`

Vive en un archivo JSON, separado del código, con dos partes:

- **`hechos`**: los síntomas que se le preguntan al usuario, cada uno con su pregunta.
- **`reglas`**: "SI estas condiciones ENTONCES este hecho". Cada condición indica si el hecho tiene que ser verdadero (`true`) o falso (`false`), así que la negación sale natural. Las reglas que tienen `recomendacion` son diagnósticos finales; las que no la tienen producen **hechos intermedios** que usan otras reglas.

```json
{
  "id": "R02",
  "descripcion": "Falla de RAM",
  "si": { "arranque_sin_video": true, "pitidos_arranque": true },
  "entonces": "falla_ram",
  "recomendacion": "Probar con módulos de RAM de a uno",
  "confianza": 0.88
}
```

Al cargarse, `conocimiento.py` valida el archivo y reporta todos los errores juntos:
- condiciones sin pregunta ni regla que las produzca,
- IDs duplicados,
- reglas con condiciones idénticas,
- confianza fuera de rango,
- dependencias circulares,
- preguntas que ninguna regla usa.

### 2. Base de Hechos — `BaseDeHechos` en `modelo.py`

Guarda para cada hecho su valor (verdadero, falso o desconocido), su certeza y qué lo originó: el usuario o una regla. Se crea nueva en cada consulta, así que una consulta nunca contamina a la siguiente.

### 3. Motor de Inferencia — `motor.py`

- `equiparar()`: devuelve las reglas cuyas condiciones se cumplen y que todavía no se dispararon.
- `resolver_conflictos()`: elige la de mayor confianza y, si hay empate, la más específica.
- `encadenar_hacia_adelante()`: repite el ciclo *equiparar → resolver → disparar* hasta que ninguna regla nueva aplica. Cada conclusión se agrega a la base de hechos y puede activar otras reglas. La certeza se propaga por la cadena: `confianza de la regla × certeza mínima de sus condiciones`.

El motor no imprime nada, solo devuelve datos. Por eso se puede testear y se podría conectar a una interfaz web sin cambiarlo.

### 4. Interfaz de Explicación

`Inferencia.justificacion()` reconstruye la cadena de reglas que llevó a un diagnóstico, y la consola la muestra ciclo por ciclo:

```
Ciclo 1: [I01] Arranca pero no muestra imagen
    SI enciende=sí, hay_video=no
    ENTONCES arranque_sin_video  (100%)
Ciclo 2: [R02] Falla de RAM
    SI arranque_sin_video=sí, pitidos_arranque=sí
    ENTONCES falla_ram  (88%)
```

### 5. Interfaz de Usuario — `cli.py`

Es la única parte que usa `input()` y `print()`. En cada paso le pide al motor la siguiente pregunta (`siguiente_pregunta()`), valida la respuesta y, cuando ya no queda nada útil por preguntar, ejecuta la inferencia.

#### Consulta dinámica

`siguiente_pregunta()` usa el encadenamiento hacia atrás en cada paso:

1. Analiza cada diagnóstico y descarta los que ya contradice alguna respuesta, igual que los ya confirmados.
2. Junta las preguntas que les faltan a los diagnósticos que siguen abiertos.
3. Elige la que necesitan más hipótesis a la vez. Si hay empate, prefiere la de mayor confianza y luego el orden del JSON.
4. Si no queda ninguna, termina la consulta.

Una prueba recorre todo el árbol de decisión y verifica las 2^14 = 16 384 combinaciones posibles de respuestas. En todas, el resultado es el mismo que si se hubieran hecho todas las preguntas: preguntar menos nunca hace perder un diagnóstico.

---

## Ajustes que le hice al código original

El código base funcionaba, pero le hice dos cambios pequeños:

**Validación de entrada:** si escribías cualquier cosa que no fuera `s` o `n`, el programa simplemente lo ignoraba. Agregué un bucle `while` que repite la pregunta hasta recibir una respuesta válida.

**`if __name__ == '__main__':`:** sin esto, importar el archivo para hacer pruebas ejecutaba automáticamente toda la interfaz interactiva. Con este cambio puedo probar las funciones por separado sin que me aparezcan las preguntas.

### Refactor de arquitectura

Después de los desafíos reorganicé el proyecto:

- **El conocimiento pasó a JSON.** Así, quien sabe de hardware puede editarlo sin saber programar, y el validador avisa si algo está mal.
- **Hechos booleanos en lugar de pares opuestos.** Antes existían `enciende` y `no_enciende`, o `pitidos_arranque` y `sin_pitidos`, y se podía responder "sí" a los dos. Ahora hay un solo hecho y las reglas piden `true` o `false`. Se unificaron los pares redundantes (`sin_video` y `pantalla_negra` pasaron a ser `hay_video`; `sin_luces` pasó a ser `luces_led`), así que las preguntas bajaron de 18 a 14.
- **Encadenamiento hacia adelante real.** Antes el motor hacía una sola pasada y las conclusiones eran frases de texto. Ahora las conclusiones son hechos que alimentan a otras reglas. Por ejemplo, `I01` deduce `arranque_sin_video`, y de ahí `R02` (RAM) y `R03` (video) se distinguen solo por los pitidos.
- **El motor quedó separado de la interfaz**, y se agregaron pruebas unitarias.

---

## Desafíos implementados

### Desafío 1 — Agregar 3 reglas nuevas

Agregué tres diagnósticos que el sistema original no cubría:

| ID | ¿Qué detecta? | Síntomas |
|---|---|---|
| R08 | Batería de BIOS agotada | fecha/hora se reinician + pitidos |
| R09 | Falla de red/WiFi | sin conexión + todo lo demás funciona |
| R10 | Controlador USB dañado | teclado o mouse no responden al arrancar |

Lo verifiqué probando cada combinación de síntomas manualmente y confirmando que el sistema activaba la regla correcta.

### Desafío 2 — Mostrar todos los diagnósticos posibles

El sistema original solo mostraba el diagnóstico con mayor confianza. El problema es que a veces un equipo puede tener varios problemas al mismo tiempo. Por ejemplo, si el equipo inicia lento y el disco está al 100% Y el ventilador está siempre activo, tanto "problemas de almacenamiento" como "posible malware" podrían aplicar.

`Inferencia.diagnosticos` devuelve todos los diagnósticos a los que llegó el motor, ordenados de mayor a menor certeza. Si dos reglas llegan al mismo diagnóstico, sus certezas se combinan con la fórmula de MYCIN (`cf1 + cf2 × (1 − cf1)`). Al final de la consulta el programa pregunta si quieres ver el ranking completo.

```
#1 Problemas de almacenamiento  (85%)
    → Verificar salud del disco duro con herramienta SMART

#2 Infección por malware  (72%)
    → Escanear con antivirus y revisar procesos en segundo plano
```

### Desafío 3 — Encadenamiento hacia atrás

Este fue el más difícil de entender al principio. La idea es poder preguntar al revés: en lugar de "dados estos síntomas, ¿qué problema es?", preguntar "para que sea sobrecalentamiento, ¿qué síntomas necesito confirmar?".

La función `encadenar_hacia_atras()` recibe la hipótesis (ID de regla, descripción o nombre del hecho) y las respuestas que ya tienes. Para cada condición indica si está cumplida, contradicha o pendiente. Si la condición es un hecho intermedio, baja recursivamente a las reglas que lo producen. Al final lista qué preguntas faltan para confirmar la hipótesis.

```
Regla objetivo : R02 — Falla de RAM (88%)
¿Se activa?    : … AÚN NO (faltan síntomas)
  ? arranque_sin_video = sí  [pendiente]
    Regla objetivo : I01 — Arranca pero no muestra imagen (100%)
    ¿Se activa?    : … AÚN NO (faltan síntomas)
      ✓ enciende = sí  [cumplida]
      ? hay_video = no  [pendiente]
  ? pitidos_arranque = sí  [pendiente]
Falta confirmar: hay_video, pitidos_arranque
```

### Desafío 4 — Exportar la red como JSON

Agregué `exportar_red()`, que recorre todas las reglas y arma un grafo dirigido. Los nodos son los hechos (de entrada, intermedios y diagnósticos) y también las reglas. Las aristas van de cada condición a su regla, indicando el valor esperado, y de cada regla al hecho que concluye. Se guarda en `red_inferencia.json` y se puede abrir en herramientas de visualización de grafos. La base actual genera 38 nodos y 40 aristas.

---

## Preguntas de reflexión

### 1. ¿Cuál es la diferencia principal entre un sistema experto y un programa de software tradicional?

Un programa normal el programador escribe exactamente qué tiene que pasar en cada caso.
Un sistema experto separa las reglas del experto del motor que las aplica, así el motor no necesita saber nada del tema para funcionar.
Eso significa que para agregar un diagnóstico nuevo no hay que tocar el motor, solo agregar una regla a la lista.

### 2. ¿Por qué se dice que el conocimiento está separado del motor de razonamiento?

Porque son dos piezas independientes que se pueden modificar sin tocarse entre sí.
Alguien que sabe de hardware puede editar las reglas sin saber programar, y un programador puede mejorar el motor sin entender de hardware.
En este ejercicio lo comprobé: agregar las tres reglas nuevas no requirió cambiar ninguna función del motor.

### 3. ¿Qué es la base de hechos y en qué se diferencia de la base de conocimiento?

La base de conocimiento tiene reglas generales que siempre están ahí, válidas para cualquier caso.
La base de hechos tiene los síntomas concretos que el usuario reporta en *esta* consulta específica y se vacía al terminar.
Una es permanente (el "saber"), la otra es temporal (el "caso actual").

### 4. ¿Qué significa que un sistema experto pueda "explicar su razonamiento"?

Significa que no solo da un resultado, sino que muestra exactamente qué síntomas activaron la regla y por qué descartó las demás.
En este sistema eso se ve en la sección "TRAZABILIDAD DEL RAZONAMIENTO".
Es clave en medicina y derecho porque una decisión que no puedes justificar no tiene validez: el médico necesita saber el "por qué" para poder corregirlo si está mal.

### 5. ¿Por qué fracasaron los sistemas expertos en los años 90?

Primero, era muy difícil extraer el conocimiento de los expertos porque ellos deciden por intuición y no siempre pueden explicarlo en reglas.
Segundo, eran frágiles: funcionaban bien en su área pero fallaban ante cualquier caso fuera de sus reglas.
Tercero, el mantenimiento era insostenible: cada cambio en el dominio requería actualizar manualmente cientos de reglas.

### 6. ¿Se activa la regla SI (fiebre AND tos) OR perdida_olfato con {fiebre=True, tos=False, perdida_olfato=True}?

Sí se activa. La primera parte `(True AND False)` da `False`, pero la segunda `perdida_olfato` es `True`.
Con OR basta que una parte sea verdadera, así que el resultado final es `True`.
La pérdida de olfato sola es suficiente para disparar la regla.

### 7. Tabla de verdad para (A AND NOT B) OR (NOT A AND B)

Esta expresión es un XOR: verdadera solo cuando A y B tienen valores distintos.

| A | B | NOT A | NOT B | A AND NOT B | NOT A AND B | Resultado |
|---|---|---|---|---|---|---|
| F | F | V | V | F | F | **F** |
| F | V | V | F | F | V | **V** |
| V | F | F | V | V | F | **V** |
| V | V | F | F | F | F | **F** |

### 8. ¿Cuál es la diferencia entre encadenamiento hacia adelante y hacia atrás?

Hacia adelante parte de los hechos y busca una conclusión ("tengo estos síntomas, ¿qué problema es?"). Es el modo normal de este sistema.
Hacia atrás parte de una conclusión y busca qué hechos la confirmarían ("sospecho sobrecalentamiento, ¿qué síntomas confirman eso?"). Es lo que implementé en el Desafío 3.
Ejemplo real: un sistema de alarmas usa hacia adelante; un médico que ya tiene una hipótesis usa hacia atrás.

### 9. Tres reglas para asesorar qué lenguaje aprender

```
SI quiero_hacer = desarrollo_web   Y me_gusta_lo_visual = sí  → aprender HTML, CSS y JavaScript
SI quiero_hacer = análisis_datos   Y me_gustan_matematicas = sí → aprender Python
SI quiero_hacer = videojuegos      Y plataforma = PC_consola   → aprender C# con Unity
```

### 10. Red de inferencia de las 3 reglas

```
[quiero_hacer=web]      ──┐
[me_gusta_lo_visual]    ──┤── R-A ──► [HTML/CSS/JavaScript]

[quiero_hacer=datos]    ──┐
[me_gustan_matematicas] ──┤── R-B ──► [Python]

[quiero_hacer=juegos]   ──┐
[plataforma=PC_consola] ──┤── R-C ──► [C# con Unity]
```

Los nodos de la izquierda son los hechos, las etiquetas R-A/B/C son las reglas que se activan, y las flechas apuntan al resultado recomendado.

### 11. ¿Qué pasa si dos reglas tienen las mismas condiciones pero conclusiones distintas?

Ambas entrarían siempre juntas al conflict set y si tienen la misma confianza, el sistema elegiría una de forma arbitraria según el orden en la lista.
Eso es un problema de diseño: el sistema daría respuestas distintas dependiendo de un detalle de implementación, no del conocimiento real.
La solución es agregar algún síntoma adicional que las diferencie, o fusionarlas en una sola regla si describen el mismo problema.