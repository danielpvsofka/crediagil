# Contrato: revisores y `compliance-check`

## `code-reviewer` (`.claude/agents/code-reviewer.md`)

```yaml
---
name: code-reviewer
description: Revisa un diff de forma independiente (corrección, tests junto al código, datos ficticios). Solo lectura.
tools: Read, Grep, Glob
---
```

- **Entrada**: la escribe `/open-pr` en el prompt de la tarea. Incluye la rama base, la lista
  de archivos cambiados y el diff completo (`git diff <base>...HEAD`).
- Revisa:
  - errores de lógica;
  - tests que faltan o no cubren bordes (Principio VII);
  - datos no ficticios o secretos (Principio III);
  - código de producción sin spec, plan o tareas (Principio IV);
  - reglas de negocio que dependen solo del prompt (Principio II).
- No puede ejecutar comandos ni modificar archivos.

## `compliance-reviewer` (`.claude/agents/compliance-reviewer.md`)

```yaml
---
name: compliance-reviewer
description: Verifica que un diff cumpla los siete principios de la constitución. Lectura y pytest.
tools: Read, Grep, Glob, Bash
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: uv run --no-project python "$CLAUDE_PROJECT_DIR/.claude/hooks/allow_only_pytest.py"
---
```

- Lee `.specify/memory/constitution.md` y revisa el diff contra los principios I–VII.
- Para el Principio I verifica que los parámetros de tasa y umbrales no se hayan alterado y
  que existan tests en el umbral, justo por debajo y justo por encima.
- Puede ejecutar `uv run pytest` para confirmar los tests.

## `compliance-check` (`.claude/skills/compliance-check/SKILL.md`)

```yaml
---
name: compliance-check
description: Revisión de cumplimiento de la constitución sobre los cambios en src/ de la rama actual, en contexto aislado.
context: fork
agent: compliance-reviewer
argument-hint: "[issue o nota para el revisor]"
allowed-tools: Read, Grep, Glob, Bash(git diff:*), Bash(git ls-files:*), Bash(uv run pytest:*)
---
```

- Cuerpo: inyecta `` !`git diff main...HEAD -- src/` `` y `` !`git diff HEAD -- src/` `` (base fija
  `main`; la inyección `!` no admite `$(…)`), incluye `$ARGUMENTS` como contexto y pide el
  veredicto en el formato de abajo.
- También inyecta `` !`git ls-files --others --exclude-standard -- src/` `` (archivos nuevos sin
  seguimiento, que no salen en ningún diff) y pide al revisor leerlos con Read.
- `Bash(git diff:*)` en `allowed-tools` autoriza la inyección `!`, que la ejecuta el harness
  antes del fork. No es para el subagente, al que `allow_only_pytest` le bloquea `git diff`.
- Si el diff de `src/` está vacío, responde `VEREDICTO: NO BLOQUEANTE` con el hallazgo
  "sin cambios de lógica de negocio".

## Formato de salida (los dos revisores)

```text
VEREDICTO: BLOQUEANTE | NO BLOQUEANTE

HALLAZGOS:
- [bloqueante] src/ruta.py:42 — Principio VII: falta test en el borde exacto del umbral.
- [menor] src/otra.py:10 — nombre poco claro.
```

- Hay `BLOQUEANTE` si existe al menos un hallazgo `[bloqueante]`.
- Son siempre bloqueantes:
  - una violación del Principio I;
  - datos reales o secretos;
  - tests rotos o ausentes para una regla afectada;
  - lógica de negocio que depende solo del prompt.
- `/open-pr` busca la primera línea que empiece por `VEREDICTO:`. Si no existe, o su valor no
  es uno de los dos anteriores, la revisión cuenta como **bloqueante**.
- Sin hallazgos se escribe `HALLAZGOS: ninguno`.

## Hook `allow_only_pytest.py`

PreToolUse que solo usa el frontmatter de `compliance-reviewer`. Lee `tool_input.command`.

| Entrada | Salida |
|---------|--------|
| `uv run pytest` | 0 |
| `uv run pytest .claude/hooks -q` | 0 |
| `pytest -k umbral` | 0 |
| `  uv run pytest` (espacios iniciales) | 0 |
| `git status` | 2 |
| `rm -rf src` | 2 |
| `uv run pytest; rm -rf src` | 2 |
| `uv run pytest && git push` | 2 |
| `uv run pytest \| tee out.txt` | 2 |
| `uv run pytest > out.txt` | 2 |
| `uv run pytest $(cat x)` / `` `x` `` | 2 |
| `uv run pytestx` | 2 |
| `uv run python -m pytest` | 2 (fuera de la lista; simple a propósito) |
| `command` ausente o vacío | 2 |
| stdin no JSON | 2 |

Mensaje en stderr: `[allow_only_pytest] compliance-reviewer solo puede ejecutar pytest: <comando>`.

## Test de configuración `test_reviewers_config.py`

| Caso | Esperado |
|------|----------|
| `tools` de `code-reviewer` | exactamente `{Read, Grep, Glob}` |
| `tools` de `compliance-reviewer` | exactamente `{Read, Grep, Glob, Bash}` |
| hook de `compliance-reviewer` | `PreToolUse` con matcher `Bash` que invoca `allow_only_pytest.py` |
| ningún revisor | sin `Write`, `Edit`, `MultiEdit`, `NotebookEdit` |
| `compliance-check` | `context: fork`, `agent: compliance-reviewer`, `allowed-tools` y `argument-hint` presentes; `allowed-tools` sin `Write`/`Edit` |

El frontmatter se parsea con un lector mínimo de biblioteca estándar, sin PyYAML (rules/hooks.md).
