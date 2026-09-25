# La actividad original

Este fue mi primer acercamiento a los sistemas expertos. La actividad consistía en recibir un código base generado con IA, entenderlo, corregirlo si era necesario y extenderlo con desafíos adicionales. Aquí explico qué hace cada parte y qué aprendí en el proceso.

> Este documento conserva el trabajo de la actividad tal como se entregó, más la evolución posterior del proyecto. Algunos ejemplos de salida corresponden a versiones anteriores.

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
