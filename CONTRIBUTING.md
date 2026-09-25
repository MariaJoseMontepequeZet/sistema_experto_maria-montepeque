# Guía de contribución

Este proyecto usa un **GitFlow simplificado** con dos ramas permanentes y
ramas cortas por cada cambio. Todo se integra mediante Pull Requests.

```
feat/*, fix/*, docs/* ...  ──PR──►  dev  ──PR (versión)──►  main
```

## Ramas

| Rama | Propósito |
|---|---|
| `main` | Versiones estables publicadas. Solo recibe PRs desde `dev` (o `hotfix/*`). **Nunca se hace commit directo.** |
| `dev` | Rama de integración: aquí se juntan y prueban los cambios antes de publicarlos. **Nunca se hace commit directo.** |
| `<tipo>/<descripcion-corta>` | Una rama por tarea, creada desde `dev` actualizada. |

Tipos de rama (coinciden con los tipos de commit):

| Prefijo | Uso | Ejemplo |
|---|---|---|
| `feat/` | Funcionalidad nueva | `feat/preguntas-dinamicas` |
| `fix/` | Corrección de un error | `fix/validacion-meta-vacia` |
| `refactor/` | Cambio interno sin alterar el comportamiento | `refactor/arquitectura-motor` |
| `docs/` | Solo documentación | `docs/flujo-de-trabajo` |
| `test/` | Solo pruebas | `test/casos-backward-chaining` |
| `chore/` | Mantenimiento (configuración, CI, dependencias) | `chore/github-actions` |
| `hotfix/` | Corrección urgente sobre `main` (sale de `main`, no de `dev`) | `hotfix/crash-al-cargar-json` |

Reglas para los nombres: minúsculas, palabras separadas con guiones, sin
tildes ni espacios, y descriptivos (nada de `cambios`, `prueba2` o `maria`).

## Flujo de trabajo

### Día a día: una tarea

```bash
# 1. Partir de dev actualizada
git switch dev
git pull

# 2. Crear la rama de la tarea
git switch -c feat/preguntas-dinamicas

# 3. Trabajar en commits pequeños
git add -p
git commit -m "feat: preguntar solo por hipótesis que siguen vivas"

# 4. Verificar antes de subir
python -m unittest
ruff check .        # opcional: el CI también lo revisa

# 5. Subir la rama
git push -u origin feat/preguntas-dinamicas
```

6. Abrir un Pull Request con **base: `dev`** (¡no `main`!).
7. Revisar el PR (aunque sea en solitario: leer el diff completo es la revisión).
8. Integrar con **Create a merge commit**.
9. Actualizar `dev` local (`git switch dev` y `git pull`) y **solo entonces**
   borrar la rama local con `git branch -d feat/preguntas-dinamicas`.

Si `dev` avanzó mientras trabajabas, trae esos cambios a tu rama con
`git merge dev` antes de abrir el PR.

### Publicar una versión: `dev` → `main`

Cuando `dev` tiene un conjunto de cambios probado y estable:

1. Abrir un PR con **base: `main`** y **compare: `dev`**, titulado con la versión (`Versión 1.1.0`).
2. Integrar con **Create a merge commit** (no Squash: así `dev` y `main` comparten historial
   y el siguiente PR de versión solo muestra lo nuevo).
3. Etiquetar la versión en `main` (ver [Versiones](#versiones)).

### Corrección urgente: `hotfix/*`

1. Crear la rama desde `main`: `git switch main`, `git pull`, `git switch -c hotfix/descripcion`.
2. PR con **base: `main`**, integrar y etiquetar un PATCH (`v1.1.1`).
3. Llevar la corrección a `dev` con un PR **base: `dev`** ← **compare: `main`**.

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
