# Tasks: Automatización del flujo de tickets en GitHub

**Input**: Design documents from `specs/002-github-ticket-flow/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: obligatorios por constitución (Principio VII) para el único código Python
(`allow_only_pytest.py`) y para la configuración de revisores (SC-005). Los comandos y skills
en Markdown se validan con los escenarios de [quickstart.md](./quickstart.md).

**Organization**: tareas agrupadas por historia de usuario.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: paralelizable (archivo distinto, sin dependencias pendientes)
- **[Story]**: historia de spec.md (US1–US4)

---

## Phase 1: Setup

**Purpose**: prerrequisitos de acceso y configuración compartida.

- [X] T001 Pedir al usuario que dé al `GITHUB_PAT` el permiso de Projects con lectura y escritura (classic: scope `project`; fine-grained: *Projects: Read and write*), según research.md R4. No leer `.env*`: el usuario confirma cuando esté listo.
- [X] T002 Con acceso, ejecutar `projects_list` (`list_projects`, owner `danielpvsofka`) y luego `list_project_fields`. Confirmar el número del Project y que `Status` tiene exactamente `Todo`, `In progress`, `In review`, `Done`. Si falta un estado, informarlo al usuario y no continuar con US1/US2.
- [X] T003 Crear los directorios `.claude/agents/` y `.claude/commands/`, y los de las skills `.claude/skills/ticket/` y `.claude/skills/compliance-check/`.

---

## Phase 2: Foundational (bloquea US1 y US2)

**Purpose**: la fuente única de configuración que leen `/ticket` y `/open-pr`.

- [X] T004 Añadir a `CLAUDE.md` la sección "Flujo de tickets", según contracts/commands.md. Debe incluir:
  - repositorio `danielpvsofka/crediagil`;
  - Project con owner `danielpvsofka` (usuario), el número confirmado en T002 y el campo `Status`;
  - los estados `Todo` → `In progress` (`/ticket`) → `In review` (`/open-pr`) → `Done` (workflow);
  - la regla "lógica de negocio = rutas bajo `src/`";
  - una línea por pieza: `/ticket`, `/open-pr`, `code-reviewer`, `compliance-reviewer`, `compliance-check`.

  No repetir tasa ni umbrales.

**Checkpoint**: `CLAUDE.md` tiene el número del Project. Ya se puede trabajar en US1, US2 y US4.

---

## Phase 3: User Story 1 - Tomar un ticket y arrancar su spec (Priority: P1) 🎯 MVP

**Goal**: `/ticket [n|siguiente]` mueve el ítem a In progress, genera la spec y comenta en el
issue.

**Independent Test**: escenarios 1–4 de quickstart.md con un issue de prueba ficticio en `Todo`.

- [X] T005 [US1] Crear `.claude/skills/ticket/SKILL.md`. El frontmatter va exactamente como en contracts/commands.md: `name: ticket`, `description`, `argument-hint: "[n|siguiente]"`, `disable-model-invocation: true`. El cuerpo sigue los pasos 1–7 de la tabla `/ticket`:
  - argumento vacío equivale a `siguiente`, y un argumento inválido muestra el uso;
  - lee owner y número del Project desde `CLAUDE.md` ("Flujo de tickets");
  - lee ítems con `projects_list` `list_project_items` y `field_names: ["Status"]`;
  - `siguiente` toma el primer ítem en `Todo`, en el orden devuelto (research R5);
  - si una llamada al Project falla (403 o sin acceso), explica el permiso que falta y no cambia nada;
  - antes de mover nada, busca una feature existente con `Issue: #n` en `specs/*/spec.md`. Si existe, indica la ruta y termina; si el ítem ya está `In progress`, no lo mueve;
  - issue cerrado, inexistente o fuera del Project: informa el motivo y no cambia nada;
  - mueve el ítem a `In progress` con `projects_write` antes de generar la spec (FR-003);
  - invoca la skill `speckit-specify` (con guion) con `<título>\n\n<cuerpo completo>\n\nIssue: #<n>`, leídos con `issue_read`;
  - si `speckit-specify` falla, informa el error, deja el ítem en `In progress` y no comenta;
  - comenta con `add_issue_comment` usando la plantilla "Spec generada con `/ticket`": ruta, historias con prioridad, requisitos principales y "Siguiente paso: `/speckit-plan`".

  No crea ramas ni hace commit.

**Checkpoint**: US1 se puede validar sola (escenarios 1–4 de quickstart.md).

---

## Phase 4: User Story 4 - Revisores con permisos mínimos (Priority: P2)

**Goal**: subagentes y skill de cumplimiento con herramientas restringidas. Va antes que US2,
porque `/open-pr` los invoca.

**Independent Test**: `uv run pytest .claude/hooks/test_allow_only_pytest.py .claude/hooks/test_reviewers_config.py`
en verde, más el escenario 10 de quickstart.md.

### Tests (escribir primero; deben fallar)

- [X] T006 [P] [US4] Crear `.claude/hooks/test_allow_only_pytest.py` con un caso parametrizado por fila de la tabla "Hook `allow_only_pytest.py`" de contracts/reviewers.md. Usar el fixture `run_hook` de `conftest.py`.
  - Salida 0: `uv run pytest`, `uv run pytest .claude/hooks -q`, `pytest -k umbral`, `  uv run pytest`.
  - Salida 2: `git status`, `rm -rf src`, `uv run pytest; rm -rf src`, `uv run pytest && git push`, `uv run pytest | tee out.txt`, `uv run pytest > out.txt`, `uv run pytest $(cat x)`, un comando con backticks, `uv run pytestx`, `uv run python -m pytest`, `command` ausente, `command` vacío, stdin no JSON.
  - Verificar que stderr empieza por `[allow_only_pytest]` en los bloqueos.
- [X] T007 [P] [US4] Crear `.claude/hooks/test_reviewers_config.py` con un lector mínimo de frontmatter en biblioteca estándar (sin PyYAML). Verifica:
  - `tools` de `code-reviewer` == `{Read, Grep, Glob}`;
  - `tools` de `compliance-reviewer` == `{Read, Grep, Glob, Bash}`;
  - `compliance-reviewer` declara un hook `PreToolUse` con matcher `Bash` cuyo comando contiene `allow_only_pytest.py`;
  - ningún revisor tiene `Write`, `Edit`, `MultiEdit` ni `NotebookEdit`;
  - `compliance-check` tiene `context: fork`, `agent: compliance-reviewer`, `argument-hint` y un `allowed-tools` sin `Write`/`Edit`.

### Implementación

- [X] T008 [US4] Crear `.claude/hooks/allow_only_pytest.py` reutilizando `_hooklib` (`read_event`, `block`, `allow`, `HookInputError`). Debe:
  - permitir solo si el comando, sin espacios al inicio y al final, es exactamente `pytest` o `uv run pytest`, o empieza por `pytest ` o `uv run pytest `;
  - bloquear con salida 2 si contiene `;`, `&&`, `||`, `|`, `` ` ``, `$(`, `>` o `<`;
  - bloquear también si el comando falta, está vacío o el JSON es inválido.

  Mensaje: `[allow_only_pytest] compliance-reviewer solo puede ejecutar pytest: <comando>`. Docstring en el estilo de los otros hooks. Hacer pasar T006.
- [X] T009 [P] [US4] Crear `.claude/agents/code-reviewer.md` con el frontmatter exacto de contracts/reviewers.md (`tools: Read, Grep, Glob`). El cuerpo:
  - pide revisar el diff recibido en la tarea según los criterios de contracts/reviewers.md (lógica, tests y bordes, datos ficticios y secretos, spec antes que código, reglas solo en prompt);
  - prohíbe proponer ediciones directas;
  - exige responder solo con el formato `VEREDICTO:` / `HALLAZGOS:`, con `[bloqueante]`/`[menor]` y `archivo:línea`, o `HALLAZGOS: ninguno`.
- [X] T010 [P] [US4] Crear `.claude/agents/compliance-reviewer.md` con el frontmatter exacto de contracts/reviewers.md: `tools: Read, Grep, Glob, Bash` y el hook `PreToolUse` `Bash` → `uv run --no-project python "$CLAUDE_PROJECT_DIR/.claude/hooks/allow_only_pytest.py"`. El cuerpo:
  - pide leer `.specify/memory/constitution.md` y revisar el diff contra los principios I–VII;
  - para el Principio I, pide comprobar que tasa y umbrales no cambian y que hay tests en el umbral, justo por debajo y justo por encima;
  - permite usar `uv run pytest`;
  - marca como siempre bloqueantes los casos de contracts/reviewers.md;
  - exige el mismo formato de salida.
- [X] T011 [US4] Crear `.claude/skills/compliance-check/SKILL.md` con el frontmatter exacto de contracts/reviewers.md: `context: fork`, `agent: compliance-reviewer`, `argument-hint: "[issue o nota para el revisor]"`, `allowed-tools: Read, Grep, Glob, Bash(git diff:*), Bash(uv run pytest:*)`. El cuerpo:
  - inyecta el diff de `src/` frente a `main` (`` !`git diff main...HEAD -- src/` `` y `` !`git diff HEAD -- src/` ``) e incluye `$ARGUMENTS` como contexto; probar `/compliance-check` y ajustar;
  - pide el veredicto en el formato del contrato;
  - si el diff está vacío, responde `VEREDICTO: NO BLOQUEANTE` con "sin cambios de lógica de negocio".
- [X] T012 [US4] Ejecutar `uv run pytest .claude/hooks/test_allow_only_pytest.py .claude/hooks/test_reviewers_config.py`; T006 y T007 deben pasar.

**Checkpoint**: los revisores existen y no pueden modificar archivos (SC-005).

---

## Phase 5: User Story 2 - Abrir el PR solo si pasa la revisión independiente (Priority: P1)

**Goal**: `/open-pr <n>` con tests, revisiones, PR con `Closes #n`, In review y comentario.

**Depends on**: Phase 2 (configuración) y Phase 4 (revisores).

**Independent Test**: escenarios 5–8 de quickstart.md.

- [X] T013 [US2] Crear `.claude/commands/open-pr.md` con el frontmatter de contracts/commands.md (`description`, `argument-hint: "<n>"`, `disable-model-invocation: true`, sin `name`). El cuerpo sigue los pasos 1–10 de la tabla `/open-pr`, en orden, y se detiene en el primer bloqueo sin abrir el PR:
  1. Valida que `n` sea un issue abierto del Project. Si falla el acceso al Project, explica el permiso que falta antes de cambiar nada.
  2. Comprueba que la rama actual no sea `main` y que el diff `main...HEAD` más los cambios sin commit no esté vacío.
  3. Ejecuta `uv run pytest`; si falla, muestra el fallo y no invoca revisores (US2-1).
  4. Invoca el subagente `code-reviewer` (Agent tool) con la base, `git diff --name-only` y el diff completo.
  5. Solo si alguna ruta empieza por `src/`, ejecuta la skill `compliance-check` con `#n`; si no, dice "compliance-check: no aplica".
  6. Interpreta cada veredicto por la primera línea `VEREDICTO:`. Si falta o el valor no es reconocible, cuenta como `BLOQUEANTE`; con un bloqueante, lista los hallazgos y termina.
  7. Si hay cambios sin commit o la rama no está publicada, los muestra y pide confirmación explícita antes de `git commit` o `git push`; sin confirmación, termina.
  8. Busca un PR abierto para la rama (`list_pull_requests` con `head`); si existe, informa su enlace y no crea otro.
  9. Crea el PR con `create_pull_request` (`base=main`, título del issue) y el cuerpo de la plantilla. El cuerpo incluye `Closes #n`, la sección Revisión y la línea `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.
  10. Mueve el ítem a `In review` con `projects_write`.
  11. Comenta en el issue la plantilla "PR abierto", con Especificado (spec.md), Decidido (research.md/plan.md) y Pendiente (tareas `- [ ]` de tasks.md y hallazgos menores). La feature se localiza por `Issue: #n` en `specs/*/spec.md`; si no se encuentra, lo indica sin inventar el resumen (Principio V).

**Checkpoint**: US1 + US2 cubren el ciclo hasta In review.

---

## Phase 6: User Story 3 - Done automático al hacer merge (Priority: P2)

**Goal**: el ítem pasa a Done al fusionar el PR, sin código.

**Independent Test**: escenario 9 de quickstart.md.

- [X] T014 [US3] Pedir al usuario que active en **Project → ⋯ → Workflows** los workflows integrados "Item closed" y "Pull request merged" con `Status: Done` (research.md R8; no se pueden activar por API). Esperar su confirmación.
- [X] T015 [US3] Documentar en la sección "Flujo de tickets" de `CLAUDE.md` que la transición a Done la hacen esos workflows, y que `Closes #n` solo cierra el issue al fusionar en `main`.

---

## Phase 7: Polish & Cross-Cutting

- [X] T016 Actualizar la tabla de hooks de `CLAUDE.md` con la fila `allow_only_pytest`: cuándo (antes de Bash en `compliance-reviewer`), qué bloquea (cualquier comando que no sea pytest, o encadenado) y qué hacer. Aclarar que va en el frontmatter del subagente y no en `settings.json`.
- [X] T017 [P] Si es necesario, ampliar `.claude/rules/hooks.md` con la excepción: un hook que solo aplica a un subagente se registra en el frontmatter de ese subagente, no en `settings.json`.
- [X] T018 Ejecutar `uv run pytest` (suite completa, incluidos los 86 tests de #1), `uv run ruff format --check` y `uv run ruff check`. Todo en verde.
- [ ] T019 Validación manual en una sesión real: escenarios 1–10 de quickstart.md con un issue de prueba ficticio. Registrar los resultados y luego cerrar el issue y borrar la rama de prueba con confirmación del usuario.
  - **Resultado 2026-10-17** (issue de prueba #12, ya cerrado): pasan 2, 3, 5, 6 y 10, y "Item closed" → Done. 1 y 4 verificados en seco. Pendientes: 7 y 9 (PR real y merge, requieren commit/push confirmados) y 8 (sin `src/`).
- [X] T020 Con confirmación del usuario, comentar en el issue #2 lo especificado, lo decidido y lo pendiente. No hacer commit ni push sin confirmación explícita.

---

## Trabajo futuro (revisión de `/open-pr 2`, no bloqueante)

- `allow_only_pytest` acepta cualquier argumento de pytest (`--basetemp`, `-p`, `--junitxml`
  pueden escribir o cargar código): restringir a una lista de opciones permitidas.
- `block_secret_access` no detecta `secrets` sin `/` ni globs como `.e*`.
- `compliance-check` y `/open-pr` comparan contra la `main` local: hacer `git fetch` y usar
  `origin/main`.

---

## Dependencies & Execution Order

```text
Setup (T001–T003) → Foundational (T004)
                         ├─▶ US1 (T005)                    🎯 MVP
                         ├─▶ US4 (T006–T012) ─▶ US2 (T013)
                         └─▶ US3 (T014–T015, independiente; manual)
                                                    └─▶ Polish (T016–T020)
```

- T001 → T002 → T004: sin acceso al Project no hay número que configurar.
- US1 solo depende de T004.
- US2 depende de US4, porque invoca `code-reviewer` y `compliance-check`.
- US3 no depende de código; puede hacerse en cualquier momento después de T002.
- Dentro de US4: T006 y T007 (tests) antes que T008–T011; T012 al final.

## Parallel Opportunities

- T003 junto con T001 (no depende del token).
- US4: T006 ∥ T007; después, T009 ∥ T010 (y T008 en paralelo con ambos).
- US1 (T005) ∥ US4 (T006–T012) tras T004.
- T014 (manual del usuario) en paralelo con cualquier fase.

```text
# Ejemplo tras T004:
Agente A: T005 (/ticket)
Agente B: T006 + T007 (tests) → T008 → T012
Agente C: T009 + T010 → T011
```

## Implementation Strategy

1. **MVP**: Setup + Foundational + US1. `/ticket` ya mueve ítems y genera specs (escenarios 1–4).
2. **Revisión independiente**: US4 y luego US2. `/open-pr` completo (escenarios 5–8, 10).
3. **Cierre**: US3, que es solo configuración (escenario 9).
4. **Polish**: documentación, suite completa y validación manual.

Primer alcance mínimo: lo que queda fuera (CI, revisión automática en el PR, endurecer el
criterio "lógica de negocio") se anota como trabajo futuro, no como bloqueante.
