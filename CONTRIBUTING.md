# Guía de contribución

Este proyecto sigue **GitHub Flow**: una rama principal siempre estable y
ramas cortas por cada cambio, que se integran mediante Pull Requests.

## Ramas

| Rama | Propósito |
|---|---|
| `main` | Código estable y funcionando. **Nunca se hace commit directo.** |
| `<tipo>/<descripcion-corta>` | Una rama por tarea, creada desde `main` actualizada. |

Tipos de rama (coinciden con los tipos de commit):

| Prefijo | Uso | Ejemplo |
|---|---|---|
| `feat/` | Funcionalidad nueva | `feat/preguntas-dinamicas` |
| `fix/` | Corrección de un error | `fix/validacion-meta-vacia` |
| `refactor/` | Cambio interno sin alterar el comportamiento | `refactor/arquitectura-motor` |
| `docs/` | Solo documentación | `docs/flujo-de-trabajo` |
| `test/` | Solo pruebas | `test/casos-backward-chaining` |
| `chore/` | Mantenimiento (configuración, CI, dependencias) | `chore/github-actions` |

Reglas para los nombres: minúsculas, palabras separadas con guiones, sin
tildes ni espacios, y descriptivos (nada de `cambios`, `prueba2` o `maria`).

## Flujo de trabajo

```bash
# 1. Partir de main actualizada
git switch main
git pull

# 2. Crear la rama de la tarea
git switch -c feat/preguntas-dinamicas

# 3. Trabajar en commits pequeños
git add -p
git commit -m "feat: preguntar solo por hipótesis que siguen vivas"

# 4. Verificar antes de subir
python -m unittest

# 5. Subir la rama y abrir un Pull Request hacia main
git push -u origin feat/preguntas-dinamicas
```

6. Revisar el PR (aunque sea en solitario: leer el diff completo es la revisión).
7. Integrar con **Squash and merge** o **Rebase and merge** para mantener un historial lineal.
8. Borrar la rama después de integrarla.

Si `main` avanzó mientras trabajabas, actualiza tu rama con `git rebase main`
antes de abrir el PR. Nunca hagas rebase de una rama que otra persona ya usa.

## Mensajes de commit

Se usa [Conventional Commits](https://www.conventionalcommits.org/es/v1.0.0/):

```
<tipo>: <resumen en imperativo, minúsculas, sin punto final>

<cuerpo opcional: qué cambió y por qué, no cómo>
```

Ejemplos:

```
feat: agregar respuesta "no sé" en la consulta
fix: evitar recursión infinita en encadenamiento hacia atrás
docs: documentar el formato del JSON de conocimiento
```

- Un commit = un cambio lógico. Si el mensaje necesita "y", probablemente son dos commits.
- Nunca subas archivos generados (`red_inferencia.json`, `__pycache__/`); ya están en `.gitignore`.

## Versiones

Las versiones estables se marcan con etiquetas [SemVer](https://semver.org/lang/es/) sobre `main`:

```bash
git tag -a v1.0.0 -m "Primera versión estable"
git push origin v1.0.0
```

- **MAJOR** (`2.0.0`): cambios incompatibles, por ejemplo en el formato del JSON de conocimiento.
- **MINOR** (`1.1.0`): funcionalidad nueva compatible.
- **PATCH** (`1.0.1`): correcciones.
