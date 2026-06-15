# Sistema Experto: Diagnóstico de PC 🖥️

Este fue mi primer acercamiento a los sistemas expertos. La actividad consistía en recibir un código base generado con IA, entenderlo, corregirlo si era necesario y extenderlo con desafíos adicionales. Aquí explico qué hace cada parte y qué aprendí en el proceso.

---

## Cómo ejecutar el programa

```bash
python3 sistema_experto.py
```

El programa te va haciendo preguntas de sí/no sobre los síntomas del equipo y al final te dice qué podría estar fallando y qué hacer.

---

## ¿Qué es un sistema experto?

Antes de empezar no tenía muy claro el concepto. Lo que entendí es que un sistema experto intenta imitar cómo razona un técnico o especialista humano. En lugar de que el programador escriba paso a paso "si pasa esto, haz aquello", el sistema tiene separadas dos cosas: las reglas del experto y el motor que las aplica. Eso fue lo que más me llamó la atención, que el motor no sabe nada de computadoras, solo sabe cómo comparar condiciones con hechos.

---

## Los 5 componentes del código

### 1. Base de Conocimiento

Es una lista de reglas. Cada regla dice: "si se dan estos síntomas, entonces probablemente el problema es este". También tiene un número de confianza (entre 0 y 1) que indica qué tan seguro está el sistema de ese diagnóstico.

```python
{
    "id": "R07",
    "descripcion": "Sobrecalentamiento",
    "condiciones": ["enciende", "se_apaga_solo", "calor_excesivo"],
    "conclusion": "Limpiar ventiladores y reaplicar pasta térmica",
    "confianza": 0.90
}
```

### 2. Base de Hechos

Es un `set` de Python donde se van guardando los síntomas que el usuario confirma con "sí" durante la consulta. Elegí `set` porque el código original lo usaba así y tiene sentido: no puede haber síntomas repetidos y la búsqueda es rápida.

### 3. Motor de Inferencia

Aquí está la lógica principal. Tiene tres funciones:

- `equiparar()` — revisa cuáles reglas se cumplen con los síntomas ingresados
- `resolver_conflictos()` — si varias reglas aplican, elige la de mayor confianza
- `inferir()` — las orquesta y muestra el resultado final

### 4. Interfaz de Explicación

Después del diagnóstico el sistema muestra qué síntomas activaron la regla y cuáles otras reglas fueron descartadas. Esto me pareció muy útil porque puedes ver el "por qué" de la decisión, no solo el resultado.

### 5. Interfaz de Usuario

La función `consultar()` recorre todas las preguntas y va llenando la base de hechos según las respuestas. Le agregué validación para que solo acepte `s` o `n`, porque el código original no la tenía y cualquier tecla incorrecta dejaba el síntoma sin registrar sin avisar nada.

---

## Ajustes que le hice al código original

El código base funcionaba, pero le hice dos cambios pequeños:

**Validación de entrada:** si escribías cualquier cosa que no fuera `s` o `n`, el programa simplemente lo ignoraba. Agregué un bucle `while` que repite la pregunta hasta recibir una respuesta válida.

**`if __name__ == '__main__':`:** sin esto, importar el archivo para hacer pruebas ejecutaba automáticamente toda la interfaz interactiva. Con este cambio puedo probar las funciones por separado sin que me aparezcan las preguntas.

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

Agregué la función `resolver_todos()` que ordena todos los diagnósticos posibles de mayor a menor confianza y los muestra como un ranking. Al final de la consulta el programa pregunta si quieres verlos todos.

```
#1 [R04] Problemas de almacenamiento — 85%
#2 [R05] Infección por malware — 72%
```

### Desafío 3 — Encadenamiento hacia atrás

Este fue el más difícil de entender al principio. La idea es poder preguntar al revés: en lugar de "dados estos síntomas, ¿qué problema es?", preguntar "para que sea sobrecalentamiento, ¿qué síntomas necesito confirmar?".

La función `backward_chain()` recibe el ID de una regla y los hechos que ya tienes, y te dice cuáles síntomas ya confirmaste y cuáles todavía faltan. Si faltan síntomas, te dice que la regla no se puede activar aún.

```
Regla objetivo : R07 — Sobrecalentamiento
Ya confirmados : ['enciende', 'se_apaga_solo']
Pendientes     : ['calor_excesivo']
¿Se activa?    : ✗ NO (faltan síntomas)
```

### Desafío 4 — Exportar la red como JSON

Agregué `exportar_red()` que recorre todas las reglas y arma un grafo: los síntomas y conclusiones son nodos, y las reglas son las conexiones entre ellos. Se guarda en `red_inferencia.json`. La idea es que ese archivo se podría abrir en herramientas de visualización de grafos. La base actual genera 28 nodos y 29 aristas.

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