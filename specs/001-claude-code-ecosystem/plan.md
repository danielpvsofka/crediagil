# Implementation Plan: Ecosistema base de Claude Code

**Branch**: `develop` (feature dir `001-claude-code-ecosystem`) | **Date**: 2026-10-14 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/001-claude-code-ecosystem/spec.md` — Issue [#1](https://github.com/danielpvsofka/crediagil/issues/1)

## Summary

Dejar el repositorio listo para que cualquier clon reciba, sin configuración, las convenciones
del equipo (`CLAUDE.md` raíz que importa la constitución, reglas con alcance por ruta en
`.claude/rules/`) y para que las reglas deterministas de desarrollo se hagan cumplir con hooks
de Claude Code registrados en `.claude/settings.json`:

1. `require_specs.py` (PreToolUse, escritura): bloquea cambios en `src/` si la feature activa
   (`.specify/feature.json`) no tiene `spec.md`, `plan.md` y `tasks.md` no vacíos.
2. `block_sensitive_data.py` (PreToolUse, escritura): bloquea tarjetas válidas por Luhn y
   cédulas/cuentas etiquetadas, con exención por línea `pragma: dato-ficticio`.
3. `block_secret_access.py` (PreToolUse, Bash y PowerShell): bloquea comandos que toquen
   `.env*` o `secrets/`; `permissions.deny` cubre las herramientas de archivo.
4. `format_python.py` (PostToolUse, escritura): `ruff format` sobre cada `.py` editado, sin
   bloquear.

Hooks en Python con solo biblioteca estándar, ejecutados con `uv`; tests pytest junto a cada
hook que lo invocan como subproceso con JSON por stdin. Detalle de decisiones en
[research.md](./research.md).

## Technical Context

**Language/Version**: Python ≥ 3.12 (entorno local: 3.14.7), solo biblioteca estándar en los hooks

**Primary Dependencies**: Claude Code (hooks, permisos, reglas, MCP); `uv` 0.13 como lanzador;
`ruff` (formato) y `pytest` (tests) como grupo de dependencias `dev` en `pyproject.toml`

**Storage**: N/A (archivos de configuración versionados; `.specify/feature.json` como fuente de
la feature activa)

**Testing**: pytest; tests `test_*.py` en `.claude/hooks/`, cada uno ejecuta el hook con
`subprocess` y JSON por stdin

**Target Platform**: Windows 10+ (Git Bash/PowerShell, entorno actual) y macOS/Linux

**Project Type**: configuración de herramientas de desarrollo + scripts CLI (hooks)

**Performance Goals**: cada hook de bloqueo decide en < 300 ms sin contar el arranque de `uv`
(se ejecutan en cada edición)

**Constraints**: hooks de bloqueo con fallo seguro (exit 2) ante entrada malformada; el hook de
formato nunca bloquea; ningún secreto ni dato real en el repo, tampoco en tests

**Scale/Scope**: 4 hooks, 3 reglas, 1 `CLAUDE.md`, 1 `settings.json`, `.mcp.json`, `.gitignore`,
`pyproject.toml`

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Evaluación pre-diseño | Post-diseño |
|-----------|-----------------------|-------------|
| I. Reglas de negocio no negociables | N/A: la feature no toca originación ni tasa/umbrales. `CLAUDE.md` los importa vía la constitución sin duplicarlos. | ✅ Sin cambios |
| II. Garantía en código, guía en instrucciones | ✅ Cada regla determinista de desarrollo (specs, datos, secretos, formato) es un hook o `permissions.deny`; `CLAUDE.md` y `.claude/rules/` solo guían el juicio. | ✅ Mapeo regla→hook en [data-model.md](./data-model.md) |
| III. Datos exclusivamente ficticios | ✅ Hook de datos sensibles; los tests generan números Luhn en tiempo de ejecución; `.mcp.json` usa `${GITHUB_PAT}`. | ✅ `pragma: dato-ficticio` explícito y revisable (FR-010a) |
| IV. Spec antes que código | ✅ Esta feature sigue specify→plan→tasks; el hook `require_specs` lo garantiza para `src/` en adelante. | ✅ |
| V. No inventar datos | N/A: sin extracción de documentos. | ✅ |
| VI. Trazabilidad | ✅ Spec y plan enlazan el issue #1. Automatización de tickets fuera de alcance (issue #2). | ✅ |
| VII. Tests junto al código y en los bordes | ✅ Test por hook, junto al hook; bordes de Luhn (válido vs. dígito alterado) y de longitud (12/13/19/20). | ✅ Casos en [contracts/hooks.md](./contracts/hooks.md) |

**Resultado**: PASA. Sin violaciones; no se requiere Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/001-claude-code-ecosystem/
├── plan.md              # Este archivo
├── research.md          # Fase 0
├── data-model.md        # Fase 1
├── quickstart.md        # Fase 1
├── contracts/
│   ├── hooks.md         # Contrato stdin/exit/stderr de cada hook + casos de prueba
│   └── config.md        # Forma de settings.json, reglas, .mcp.json, .gitignore
├── checklists/
│   └── requirements.md
└── tasks.md             # Fase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
CLAUDE.md                        # Convenciones del equipo + @.specify/memory/constitution.md
pyproject.toml                   # requires-python, grupo dev (pytest, ruff), config ruff/pytest
.gitignore                       # + CLAUDE.local.md, .env.*, secrets/
.mcp.json                        # GitHub MCP, toolset projects, ${GITHUB_PAT} (ya existe; verificar)
.claude/
├── settings.json                # permissions.deny + registro de hooks (versionado)
├── rules/
│   ├── tests.md                 # paths: tests
│   ├── mcp-server.md            # paths: servidor MCP del agente
│   └── hooks.md                 # paths: .claude/hooks/**
└── hooks/
    ├── _hooklib.py              # lectura de stdin, normalización de rutas, block()/allow()
    ├── require_specs.py
    ├── test_require_specs.py
    ├── block_sensitive_data.py
    ├── test_block_sensitive_data.py
    ├── block_secret_access.py
    ├── test_block_secret_access.py
    ├── format_python.py
    ├── test_format_python.py
    └── conftest.py              # helper run_hook(script, payload) -> (code, stdout, stderr)
```

**Structure Decision**: todo vive en `.claude/` y en la raíz. No se crea `src/`: el código del
agente llega en features posteriores y quedará protegido por `require_specs`.

## Complexity Tracking

Sin violaciones de la constitución que justificar.
