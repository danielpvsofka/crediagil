# Data Model: Automatización del flujo de tickets en GitHub

No hay persistencia propia: el estado vive en GitHub (Project, issues, PR) y en `specs/`.

## Ítem del Project

| Campo | Origen | Notas |
|-------|--------|-------|
| `item_id` | `projects_list` → `list_project_items` | Necesario para `projects_write` |
| `issue_number` | contenido del ítem | Solo ítems de tipo issue de `danielpvsofka/crediagil` |
| `Status` | campo de selección única | `Todo`, `In progress`, `In review`, `Done` |
| posición | orden de `list_project_items` | Define "siguiente" (FR-002) |

### Transiciones de estado

```text
Todo ──/ticket──▶ In progress ──/open-pr (sin bloqueantes)──▶ In review ──merge (workflow)──▶ Done
```

| Desde | Hacia | Quién | Condición |
|-------|-------|-------|-----------|
| Todo | In progress | `/ticket` | Antes de generar la spec (FR-003) |
| In progress | In progress | `/ticket <n>` | No se mueve; avisa (edge case) |
| In progress | In review | `/open-pr <n>` | Tests verdes y revisiones sin bloqueantes; PR creado |
| In review | Done | Workflow integrado del Project | Issue cerrado por merge con `Closes #n` |

Otra transición (p. ej. Todo → In review) no la hace ningún comando.

## Feature de Spec Kit

| Campo | Valor |
|-------|-------|
| Directorio | `specs/NNN-<short-name>/` (numeración secuencial de Spec Kit) |
| Enlace al issue | línea `**Issue**: #n` en `spec.md` (la entrada termina con `Issue: #n`) |
| Activa | `.specify/feature.json` → `feature_directory` |

Búsqueda de la feature de un issue: `grep -l "Issue: #n\b\|issues/n)" specs/*/spec.md`. La usan
`/ticket <n>` (si ya existe, no crear otra) y `/open-pr <n>` (para el comentario).

## Revisión

| Campo | Tipo | Regla |
|-------|------|-------|
| `revisor` | `code-reviewer` \| `compliance-check` | |
| `veredicto` | `BLOQUEANTE` \| `NO BLOQUEANTE` | Obligatorio; si falta o no se reconoce → se trata como `BLOQUEANTE` (edge case) |
| `hallazgos[]` | lista | `archivo:línea`, `severidad` (`bloqueante`/`menor`), `motivo` |

Formato exacto en [contracts/reviewers.md](./contracts/reviewers.md).

## Comentario de seguimiento

| Tipo | Autor | Contenido mínimo |
|------|-------|------------------|
| Spec | `/ticket` | Ruta de `spec.md`, historias de usuario (título + prioridad), requisitos principales |
| PR | `/open-pr` | Enlace al PR; **Especificado** (resumen de spec), **Decidido** (decisiones de `research.md`/`plan.md`), **Pendiente** (tareas `- [ ]` de `tasks.md` y hallazgos menores) |

Plantillas en [contracts/commands.md](./contracts/commands.md).

## "Lógica de negocio" (FR-009)

Un diff toca lógica de negocio si `git diff --name-only <base>...HEAD` incluye al menos una ruta
que empiece por `src/`. Sin `src/` en el diff, `compliance-check` no se ejecuta.
