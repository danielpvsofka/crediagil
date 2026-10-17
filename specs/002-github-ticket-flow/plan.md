# Implementation Plan: Automatización del flujo de tickets en GitHub

**Branch**: `develop` (feature dir `002-github-ticket-flow`) | **Date**: 2026-10-17 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/002-github-ticket-flow/spec.md` — Issue [#2](https://github.com/danielpvsofka/crediagil/issues/2)

## Summary

Los tickets quedan reflejados en el Project sin pasos manuales, y cada PR pasa por una
revisión independiente. La feature se arma con piezas versionadas en `.claude/`:

1. **`/ticket [n|siguiente]`** (skill): toma el ítem del Project, lo mueve a In progress,
   ejecuta `speckit-specify` con el issue y comenta la spec en el issue.
2. **`/open-pr <n>`** (comando): ejecuta `uv run pytest`, luego `code-reviewer` y, si el diff
   toca `src/`, `compliance-check`. Ante cualquier bloqueante se detiene. Si no hay
   bloqueantes, pide confirmación de commit y push, abre el PR con `Closes #n`, mueve el ítem a
   In review y comenta Especificado, Decidido y Pendiente.
3. **Revisores**:
   - `code-reviewer` (Read, Grep, Glob).
   - `compliance-reviewer` (Read, Grep, Glob, Bash). Bash queda limitado a pytest por el hook
     `allow_only_pytest.py`, declarado en el propio frontmatter del subagente.
4. **`compliance-check`** (skill): lleva `context: fork`, `agent: compliance-reviewer`,
   `allowed-tools` y `argument-hint`, e inyecta el diff de `src/`.
5. **Done**: lo hacen los workflows integrados del Project ("Item closed" / "PR merged" →
   Done), que se activan a mano.

El acceso a GitHub usa el MCP de #1. Prerrequisito detectado: el `GITHUB_PAT` actual no tiene
acceso a Projects (403). Decisiones en [research.md](./research.md).

## Technical Context

**Language/Version**: Markdown con frontmatter YAML (skills, comando, subagentes); Python
≥ 3.12, solo biblioteca estándar, para el hook nuevo y los tests

**Primary Dependencies**: Claude Code v2.1.x (skills, commands, subagents, hooks en
frontmatter); MCP `github` (toolsets `issues`, `pull_requests`, `projects`); Spec Kit
(`speckit-specify`); `uv`, `pytest`, `ruff` (de #1)

**Storage**: N/A. El estado vive en GitHub (Project, issues, PR) y en `specs/`; la
configuración del Project, en `CLAUDE.md`

**Testing**: pytest en `.claude/hooks/` (`test_allow_only_pytest.py`,
`test_reviewers_config.py`); escenarios manuales en [quickstart.md](./quickstart.md)

**Target Platform**: Claude Code en Windows (Git Bash/PowerShell) y macOS/Linux

**Project Type**: configuración de herramientas de desarrollo (prompts versionados + 1 hook)

**Performance Goals**: N/A (flujos interactivos); el hook decide en < 300 ms sin contar `uv`

**Constraints**:
- Ningún revisor puede modificar archivos.
- No se hace commit ni push sin confirmación explícita.
- Ningún comando cambia el estado en GitHub si falla una precondición.
- Un veredicto ilegible cuenta como bloqueante.

**Scale/Scope**: 2 skills, 1 comando, 2 subagentes, 1 hook con su test, 1 test de
configuración, actualización de `CLAUDE.md`

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Evaluación pre-diseño | Post-diseño |
|-----------|-----------------------|-------------|
| I. Reglas de negocio no negociables | N/A: no toca originación. `compliance-reviewer` verifica en cada PR que no cambien la tasa ni los umbrales y que existan tests de borde. | ✅ Checklist del Principio I en [contracts/reviewers.md](./contracts/reviewers.md) |
| II. Garantía en código, guía en instrucciones | ✅ La restricción de herramientas es determinista: `tools` en el frontmatter y el hook `allow_only_pytest`. El juicio de revisión se guía con prompts. | ✅ La regla "solo pytest" es un hook con tests, no texto del prompt |
| III. Datos exclusivamente ficticios | ✅ El issue de validación es ficticio; los hooks de #1 siguen activos; `code-reviewer` revisa datos reales y secretos. | ✅ |
| IV. Spec antes que código | ✅ La feature sigue el flujo; `/ticket` arranca Spec Kit para cada issue. | ✅ |
| V. No inventar datos | ✅ Los comentarios salen de spec, plan y tareas existentes. Si falta la feature, se indica en lugar de inventar un resumen. | ✅ |
| VI. Trazabilidad | ✅ Es el objetivo de la feature: estado del Project y comentarios automáticos, enlace `Issue: #n` ↔ `Closes #n`. | ✅ [data-model.md](./data-model.md) (transiciones) |
| VII. Tests junto al código y en los bordes | ✅ Hook y test en `.claude/hooks/`. Los bordes del hook son los comandos casi permitidos (`pytestx`, encadenados, redirecciones). | ✅ Tabla de casos en contracts |

**Resultado**: PASA. Sin violaciones.

**Nota**: el segundo punto del Principio VI, "cada ticket (escalamiento, caso a analista) se
refleja en GitHub", se refiere a tickets del agente. Queda para la feature del agente y no la
cubre esta.

## Project Structure

### Documentation (this feature)

```text
specs/002-github-ticket-flow/
├── plan.md              # Este archivo
├── research.md          # Fase 0
├── data-model.md        # Fase 1: ítem, transiciones, revisión, comentarios
├── quickstart.md        # Fase 1: prerrequisitos + escenarios
├── contracts/
│   ├── commands.md      # /ticket y /open-pr: pasos, fallos, plantillas
│   └── reviewers.md     # subagentes, compliance-check, formato de veredicto, hook
├── checklists/
│   └── requirements.md
└── tasks.md             # Fase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
CLAUDE.md                              # + sección "Flujo de tickets" (owner, nº de Project, estados)
.claude/
├── skills/
│   ├── ticket/SKILL.md                # /ticket
│   └── compliance-check/SKILL.md      # context: fork, agent: compliance-reviewer
├── commands/
│   └── open-pr.md                     # /open-pr
├── agents/
│   ├── code-reviewer.md               # tools: Read, Grep, Glob
│   └── compliance-reviewer.md         # tools: Read, Grep, Glob, Bash + hook PreToolUse
└── hooks/
    ├── allow_only_pytest.py           # PreToolUse del subagente: solo pytest
    ├── test_allow_only_pytest.py
    └── test_reviewers_config.py       # verifica frontmatter de revisores y compliance-check
```

**Structure Decision**: todo vive en `.claude/` y en `CLAUDE.md`. `allow_only_pytest.py` no se
registra en `settings.json` porque solo aplica a `compliance-reviewer` y va en su frontmatter.
Se documenta en la tabla de hooks de `CLAUDE.md` con esa aclaración. No se crea `src/`.

## Complexity Tracking

Sin violaciones de la constitución que justificar.
