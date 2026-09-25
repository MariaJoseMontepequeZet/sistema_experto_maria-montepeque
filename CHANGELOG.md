# Historial de cambios

Todos los cambios relevantes del proyecto se documentan aquí.
El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el proyecto usa
[Versionado Semántico](https://semver.org/lang/es/).

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

[1.3.0]: https://github.com/MariaJoseMontepequeZet/sistema_experto_maria-montepeque/compare/v1.2.1...v1.3.0
[1.2.1]: https://github.com/MariaJoseMontepequeZet/sistema_experto_maria-montepeque/compare/v1.2.0...v1.2.1
[1.2.0]: https://github.com/MariaJoseMontepequeZet/sistema_experto_maria-montepeque/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/MariaJoseMontepequeZet/sistema_experto_maria-montepeque/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/MariaJoseMontepequeZet/sistema_experto_maria-montepeque/releases/tag/v1.0.0
