# Contrato: `/ticket` y `/open-pr`

Configuración compartida en `CLAUDE.md`, sección "Flujo de tickets":

- Repositorio: `danielpvsofka/crediagil`.
- Project: owner `danielpvsofka` (usuario), número `<N>`, campo `Status`.
- Estados: `Todo`, `In progress`, `In review`, `Done`.

## `/ticket` (`.claude/skills/ticket/SKILL.md`)

```yaml
---
name: ticket
description: Toma un issue del Project (el siguiente en Todo o el indicado), lo mueve a In progress y genera su spec con Spec Kit.
argument-hint: "[n|siguiente]"
disable-model-invocation: true
---
```

| Paso | Acción | Si falla |
|------|--------|----------|
| 1 | Si el argumento está vacío, usa `siguiente`. Si no es número ni `siguiente`, muestra el uso y termina. | — |
| 2 | Lee campos e ítems del Project (`Status`). | Sin acceso o 403: explica el permiso que falta y no cambia nada. |
| 3 | `siguiente`: toma el primer ítem en `Todo`. `n`: toma el ítem del issue `n`. | No hay `Todo`: "No hay trabajo pendiente". Issue cerrado, inexistente o fuera del Project: informa el motivo. En ambos casos no cambia nada. |
| 4 | Busca una feature existente (`Issue: #n` en `specs/*/spec.md`). | Si ya existe: indica su ruta y no crea otra. Si el ítem ya está `In progress`, no lo mueve. Termina. |
| 5 | Mueve el ítem a `In progress`. | Error de escritura: informa y termina. |
| 6 | Ejecuta `speckit-specify` con `<título>\n\n<cuerpo>\n\nIssue: #n`. | Informa el error. El ítem queda `In progress` y no se comenta. |
| 7 | Comenta en el issue (plantilla abajo). | Informa que la spec existe pero el comentario falló. |

Plantilla del comentario:

```markdown
### Spec generada con `/ticket`

**Spec**: `specs/NNN-nombre/spec.md`

**Historias de usuario**
- US1 (P1): …
- US2 (P2): …

**Requisitos principales**: FR-001 …, FR-002 …

Siguiente paso: `/speckit-plan`.
```

## `/open-pr` (`.claude/commands/open-pr.md`)

```yaml
---
description: Ejecuta tests y revisiones independientes; si no hay bloqueantes, abre el PR del issue y lo mueve a In review.
argument-hint: "<n>"
disable-model-invocation: true
---
```

| Paso | Acción | Si falla o bloquea → no se abre el PR |
|------|--------|----------------------------------------|
| 1 | Valida que `n` sea un número de issue abierto del Project. | Muestra el uso o el motivo. |
| 2 | Comprueba la rama actual (no `main`) y el diff `main...HEAD` (no vacío, incluidos los cambios sin commit). | Explica el motivo. |
| 3 | `uv run pytest`. | Muestra el fallo. No invoca revisiones. |
| 4 | Invoca `code-reviewer` (Agent tool) con la base, los archivos y el diff. | `BLOQUEANTE` o veredicto ilegible: lista los hallazgos. |
| 5 | Si el diff incluye `src/`, ejecuta `/compliance-check #n`. Si no, lo omite y lo dice. | Igual que el paso 4. |
| 6 | Si hay cambios sin commit o la rama no está publicada, los muestra y **pide confirmación** para `git commit` o `git push`. | Si no hay confirmación, se detiene sin PR. |
| 7 | Si ya hay un PR abierto para la rama, informa su enlace y salta al paso 9 sin crear otro. | — |
| 8 | Crea el PR `head=<rama>`, `base=main`. Título: el del issue. Cuerpo según la plantilla. | Informa el error de la API. |
| 9 | Mueve el ítem a `In review`. | Informa; el PR ya existe. |
| 10 | Comenta en el issue (plantilla abajo). | Informa. |

Cuerpo del PR:

```markdown
Closes #n

## Resumen
<qué cambia, desde spec.md>

## Revisión
- Tests: ✅ `uv run pytest`
- code-reviewer: NO BLOQUEANTE (<k> hallazgos menores)
- compliance-check: NO BLOQUEANTE | no aplica (sin cambios en src/)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

Comentario en el issue:

```markdown
### PR abierto: #<pr>

**Especificado**: <resumen de historias y requisitos de spec.md>

**Decidido**: <decisiones clave de research.md / plan.md>

**Pendiente**: <tareas `- [ ]` de tasks.md> · <hallazgos menores de las revisiones>
```

La feature del issue se localiza con `Issue: #n` en `specs/*/spec.md`. Si no se encuentra, el
comentario lo indica y usa el diff como resumen.
