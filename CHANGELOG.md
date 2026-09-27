# Historial de cambios

Todos los cambios relevantes del proyecto se documentan aquí.
El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el proyecto usa
[Versionado Semántico](https://semver.org/lang/es/).

## [1.6.0] - 2026-09-26

### Agregado
- Pruebas de verificación (`"prueba": true`): el sistema las propone al final, después de los
  síntomas, y su resultado es evidencia fuerte. Seis pruebas nuevas: otra fuente de poder, otro
  cargador, otro monitor o cable, un solo módulo de RAM, estado SMART del disco y análisis antivirus.
  La temperatura del procesador pasa a ser una prueba.
- En la web y en la consola, las pruebas se marcan como tales y se pueden omitir ("No puedo
  hacerla"); en la web, "Ver el diagnóstico sin más pruebas".

### Cambiado
- Las reglas que usan la temperatura exigen que haya imagen (hace falta para medirla).
- Las certezas se muestran como máximo en 99 % salvo que sean exactamente 1: un diagnóstico casi
  seguro no se presenta como infalible por redondeo.
- El validador permite que la evidencia sobre distintos diagnósticos tenga las mismas condiciones.

### Corregido
- La consulta ya no pregunta evidencia de un diagnóstico que solo podría confirmarse con preguntas
  respondidas con "no sé".

## [1.5.0] - 2026-09-26

### Agregado
- Evidencia a favor y en contra: las reglas aceptan confianza entre -1 y 1 y todas las evidencias
  sobre un diagnóstico se combinan con los factores de certeza de MYCIN.
- Diagnósticos descartados: los que una regla sugirió pero la evidencia en contra dejó bajo el umbral
  (0.2) se muestran aparte, con el motivo, en la consola y en la web.
- Desglose "¿Por qué X % de certeza?" en la web y en la consola; la evidencia en contra se dibuja en
  rojo en los diagramas.
- Conocimiento: la temperatura normal del procesador resta certeza al sobrecalentamiento; el
  ventilador al máximo la refuerza; si otros dispositivos tampoco se conectan, se descarta la falla del
  adaptador de red y se diagnostica un problema del router o del proveedor.
- Validación de la evidencia: sin recomendación, solo sobre diagnósticos, confianza distinta de 0.

### Cambiado
- El motor completa cada nivel de hechos antes de pasar al siguiente: toda la evidencia de un hecho
  se reúne antes de usarlo, y el resultado no depende del orden de las reglas.
- La consulta dinámica también pregunta por la evidencia de los diagnósticos que siguen siendo posibles.
- La prueba exhaustiva usa un valor por región de cada umbral numérico y se ejecuta en el CI
  (localmente con `PRUEBAS_EXHAUSTIVAS=1`).
- `CONTRIBUTING.md`: reiniciar la demo en Streamlit Cloud después de publicar una versión.

## [1.4.0] - 2026-09-25

### Agregado
- Tres tipos de pregunta: sí/no, opción múltiple y numérica (con unidad, rango y texto de ayuda),
  en la consola y en la interfaz web. El formato anterior del JSON sigue siendo válido.
- Condiciones por tipo: una opción, una lista de opciones o comparaciones numéricas (`>`, `>=`, `<`, `<=`).
- Nuevos diagnósticos: cargador o batería de laptop, problema de monitor o cable de video,
  sobrecalentamiento confirmado por temperatura y fuente de poder inestable.
- El validador comprueba que cada condición corresponda al tipo de su hecho, que las opciones
  existan y que los rangos numéricos se puedan cumplir.

### Cambiado
- "¿Hay pitidos?" pasa a ser el **patrón de pitidos**: un pitido corto (arranque normal) ya no se
  diagnostica como falla de RAM, y cada patrón apunta a su causa (RAM, video o monitor).
- La pila del BIOS se detecta sin exigir pitidos.
- La fuente de poder se distingue del cargador según el tipo de equipo.
- El motor descarta de entrada las reglas que contradicen alguna respuesta: la inferencia es varias
  veces más rápida.
- La prueba exhaustiva recorre el árbol de decisión completo con opciones y valores límite numéricos.

### Corregido
- La interfaz web fallaba con límites numéricos enteros en el JSON (tipos mezclados en Streamlit).

## [1.3.0] - 2026-09-25

### Agregado
- Advertencias de seguridad en los diagnósticos que implican abrir el equipo o arriesgar datos
  (campo opcional `advertencia` en las reglas), visibles en la consola y en la interfaz web.
- Aviso general: el sistema orienta y no reemplaza a un técnico.
- Licencia MIT, este historial de cambios, `pyproject.toml` y plantillas de issues.
- Revisión de estilo con `ruff` en el CI.
- Documentación separada en `docs/`: arquitectura, guía para escribir reglas y la actividad original.

### Cambiado
- El validador rechaza campos desconocidos en las reglas (por ejemplo, errores de tipeo).
- README reorganizado para visitantes: demo, características, instalación y arquitectura en resumen.

## [1.2.1] - 2026-09-24

### Agregado
- Enlace a la demo pública en Streamlit Community Cloud.

## [1.2.0] - 2026-09-24

### Agregado
- Interfaz web con Streamlit: consulta dinámica, deshacer, diagnóstico con certeza, diagrama del
  razonamiento, explorador de hipótesis y mapa de la base de conocimiento.
- Diagramas Graphviz (DOT) del razonamiento y de la red de inferencia.
- Pruebas de la interfaz web con `streamlit.testing` en el CI.

## [1.1.0] - 2026-09-24

### Agregado
- Integración continua con GitHub Actions en Python 3.10, 3.12 y 3.14.
- Badges en el README.

### Corregido
- Sintaxis YAML del workflow de pruebas.

## [1.0.0] - 2026-09-24

### Agregado
- Base de conocimiento en JSON con validación completa.
- Encadenamiento hacia adelante hasta punto fijo con hechos intermedios y propagación de certeza.
- Encadenamiento hacia atrás recursivo.
- Consulta dinámica: solo se pregunta lo relevante, con respuestas "no sé" y "¿por qué?".
- Suite de pruebas, incluida la verificación exhaustiva de las 16 384 combinaciones de respuestas.

### Cambiado
- Arquitectura separada en conocimiento, motor e interfaz; hechos booleanos con negación.

[1.6.0]: https://github.com/MariaJoseMontepequeZet/sistema_experto_maria-montepeque/compare/v1.5.0...v1.6.0
[1.5.0]: https://github.com/MariaJoseMontepequeZet/sistema_experto_maria-montepeque/compare/v1.4.0...v1.5.0
[1.4.0]: https://github.com/MariaJoseMontepequeZet/sistema_experto_maria-montepeque/compare/v1.3.0...v1.4.0
[1.3.0]: https://github.com/MariaJoseMontepequeZet/sistema_experto_maria-montepeque/compare/v1.2.1...v1.3.0
[1.2.1]: https://github.com/MariaJoseMontepequeZet/sistema_experto_maria-montepeque/compare/v1.2.0...v1.2.1
[1.2.0]: https://github.com/MariaJoseMontepequeZet/sistema_experto_maria-montepeque/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/MariaJoseMontepequeZet/sistema_experto_maria-montepeque/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/MariaJoseMontepequeZet/sistema_experto_maria-montepeque/releases/tag/v1.0.0
