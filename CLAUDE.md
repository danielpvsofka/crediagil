# Crediágil — convenciones del equipo

Agente de originación de crédito de libre inversión para Crediágil, una fintech **ficticia**.
La constitución del proyecto prevalece sobre todo lo demás:

@.specify/memory/constitution.md

Tasa, umbrales y reglas de negocio viven **solo** en la constitución; no los repitas ni los
cambies aquí, en código ni en prompts.

## Flujo de trabajo

- Spec antes que código: `/speckit-specify` → `/speckit-plan` → `/speckit-tasks` →
  `/speckit-implement`. Un cambio de comportamiento actualiza primero la spec.
- La feature activa es la de `.specify/feature.json` (`feature_directory`).
- Artefactos (specs, planes, tareas, documentación) en español.
- Nunca hacer commit ni push sin confirmación explícita.

## Stack y comandos

- Python ≥ 3.12 gestionado con `uv`: `uv sync --group dev` instala pytest y ruff.
- Tests: `uv run pytest`. Todo cambio de código incluye sus tests en el mismo cambio, junto al
  código, y cubre los bordes exactos de cada umbral.
- Formato: `ruff format` se aplica solo tras editar cualquier `.py` (hook). Lint:
  `uv run ruff check`.

## Datos ficticios

- Solo datos ficticios en código, tests, fixtures, logs y documentación.
- Un fixture con forma de cédula o cuenta deliberadamente ficticio se marca en **la misma
  línea** con `pragma: dato-ficticio`. Si es una edición, el marcador debe estar dentro del
  texto editado. No uses el marcador para nada que pueda ser real.
- Los números con forma de tarjeta para tests se generan en tiempo de ejecución, nunca como
  literal.

## Secretos

- Los secretos van en `.env` (ignorado por git). Claude no puede leer `.env*` ni `secrets/`:
  si necesitas un valor, pídelo al usuario.
- `GITHUB_PAT` se define en el entorno de cada desarrollador; `.mcp.json` solo lo referencia.

## Hooks activos (`.claude/settings.json`)

| Hook | Cuándo | Bloquea si… | Qué hacer |
|------|--------|-------------|-----------|
| `require_specs` | Antes de escribir/editar | el archivo está bajo `src/` y la feature activa no tiene `spec.md`, `plan.md` y `tasks.md` no vacíos | Completar el flujo Spec Kit o corregir `.specify/feature.json` |
| `block_sensitive_data` | Antes de escribir/editar | el contenido tiene una tarjeta válida por Luhn, o una cédula/NIT/cuenta junto a su etiqueta | Usar datos ficticios generados, o `pragma: dato-ficticio` si es deliberado |
| `block_secret_access` | Antes de Bash/PowerShell | el comando menciona `.env*` o `secrets/` | Pedir el valor al usuario |
| `format_python` | Después de escribir/editar | nunca bloquea; avisa si ruff no está disponible | Ejecutar `uv sync --group dev` |
| `allow_only_pytest` | Antes de Bash, solo en el subagente `compliance-reviewer` (frontmatter, no `settings.json`) | el comando no es `pytest`/`uv run pytest`, o encadena/redirige | Nada: el revisor solo debe leer y ejecutar tests |

Los hooks y sus tests viven en `.claude/hooks/`. Las reglas por ruta, en `.claude/rules/`.

## Flujo de tickets

- Repositorio: `danielpvsofka/crediagil`. Rama base de los PR: `main`.
- Project: "Crediágil", owner `danielpvsofka` (usuario), número **1**, campo `Status`. El
  `GITHUB_PAT` necesita un token classic con scopes `repo` y `project`. La opción `Ready` del
  Project no la usa ningún comando.
- Estados: `Todo` → `In progress` (`/ticket`) → `In review` (`/open-pr`) → `Done` (workflows
  integrados "Item closed" y "Pull request merged" del Project, activados a mano).
  `Closes #n` solo cierra el issue al fusionar en `main`.
- Lógica de negocio = cualquier ruta bajo `src/` en el diff; dispara `compliance-check`.
- Piezas:
  - `/ticket [n|siguiente]` (`.claude/skills/ticket/`): mueve a In progress, genera la spec y
    comenta en el issue.
  - `/open-pr <n>` (`.claude/commands/open-pr.md`): tests, revisiones, PR, In review y
    comentario.
  - `code-reviewer` (`.claude/agents/`): Read, Grep, Glob.
  - `compliance-reviewer` (`.claude/agents/`): lectura y pytest (hook `allow_only_pytest`).
  - `compliance-check` (`.claude/skills/`): `context: fork` con `compliance-reviewer`.

## Personal

Preferencias propias en `CLAUDE.local.md` y `.claude/settings.local.json` (ambos ignorados por
git).
