# Quickstart: validar el flujo de tickets

## Prerrequisitos (una vez)

1. Usar en `GITHUB_PAT` un token **classic** con scopes `repo` y `project` (completo, no solo
   `read:project`). Un token fine-grained devuelve 403 en los Projects de una cuenta de
   usuario. No definas `GITHUB_PAT` en `.claude/settings.local.json`: tiene prioridad sobre la
   variable de entorno.
2. Comprobar que el Project del repositorio tiene el campo `Status` con `Todo`, `In progress`,
   `In review` y `Done`. Anotar su número en `CLAUDE.md`, sección "Flujo de tickets".
3. En **Project → ⋯ → Workflows**, activar dos workflows con `Status: Done`: "Item closed" y
   "Pull request merged".
4. Ejecutar `uv sync --group dev`.

## Validación automática

```bash
uv run pytest                 # incluye test_allow_only_pytest.py y test_reviewers_config.py
uv run ruff check
```

Resultado esperado: todo en verde. Los casos están en
[contracts/reviewers.md](./contracts/reviewers.md).

## Escenarios manuales

Usa un issue de prueba ficticio, por ejemplo "Prueba flujo de tickets", agregado al Project en
`Todo`.

| # | Escenario | Pasos | Resultado esperado |
|---|-----------|-------|--------------------|
| 1 | US1 siguiente | `/ticket` | El ítem queda en `In progress`. Se crea `specs/NNN-*/spec.md` con `Issue: #n`. El issue recibe un comentario con la ruta y el resumen. |
| 2 | US1 explícito | `/ticket <n>` sobre un ítem que no es el primero | Se toma ese issue. |
| 3 | US1 repetido | `/ticket <n>` sobre el mismo issue | No se mueve ni se crea otra spec; indica la ruta existente. |
| 4 | US1 vacío | `/ticket` sin ítems en `Todo` | "No hay trabajo pendiente"; nada cambia. |
| 5 | US2 tests rojos | En una rama de prueba, romper un test y ejecutar `/open-pr <n>` | Muestra el fallo; no se invocan revisores; no hay PR. |
| 6 | US2 bloqueante | Introducir un literal con forma de secreto ficticio en un `.md` y ejecutar `/open-pr <n>` | `code-reviewer` devuelve `BLOQUEANTE`; no hay PR. |
| 7 | US2 sin `src/` | Cambio solo en docs; `/open-pr <n>` | `compliance-check` "no aplica"; pide confirmación de push; crea el PR con `Closes #n`; ítem en `In review`; comentario con Especificado/Decidido/Pendiente. |
| 8 | US2 con `src/` | Cambio en `src/` con su feature completa | Se ejecuta `compliance-check` en contexto aislado; un bloqueante impide el PR. |
| 9 | US3 | Merge del PR del escenario 7 | El issue se cierra y el ítem pasa a `Done` sin intervención. |
| 10 | US4 | En una sesión, pedir a `code-reviewer` editar un archivo y a `compliance-reviewer` ejecutar `git status` | El primero no tiene la herramienta. El segundo recibe el bloqueo de `allow_only_pytest`. |

Al terminar, cerrar o borrar el issue de prueba y su rama.
