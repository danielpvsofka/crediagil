# Research: Automatización del flujo de tickets en GitHub

Decisiones de la Fase 0. No quedan `NEEDS CLARIFICATION`. Referencias: documentación de Claude
Code v2.1.x (skills, sub-agents, hooks).

## R1. Forma de cada pieza en Claude Code

- **Decision**:
  - `/ticket` es una skill: `.claude/skills/ticket/SKILL.md`.
  - `/open-pr` es un comando: `.claude/commands/open-pr.md`.
  - `compliance-check` es una skill: `.claude/skills/compliance-check/SKILL.md`.
  - Los dos revisores son subagentes: `.claude/agents/code-reviewer.md` y `.claude/agents/compliance-reviewer.md`.
- **Rationale**: el issue pide literalmente "skill `/ticket`", "comando `/open-pr`" y "skill
  `compliance-check`". `.claude/commands/` sigue soportado y admite el mismo frontmatter que
  las skills, salvo `name` y `paths`. Todo queda bajo `.claude/`, que está versionado (FR-006).
- **Alternatives considered**: hacer `/open-pr` también como skill. Se descartó porque el
  issue distingue explícitamente "comando". Si `.claude/commands/` llega a retirarse, migrar es
  mover el archivo.
- `/ticket` y `/open-pr` llevan `disable-model-invocation: true`, porque cambian estado en
  GitHub y solo deben ejecutarse cuando el desarrollador los invoca.

## R2. `compliance-check` en contexto aislado

- **Decision**: el frontmatter de la skill declara:
  - `context: fork` y `agent: compliance-reviewer`;
  - `argument-hint: "[issue o nota para el revisor]"`;
  - `allowed-tools: Read, Grep, Glob, Bash(git diff:*), Bash(uv run pytest:*)`.

  El diff se inyecta con `` !`git diff main...HEAD -- src/` `` más `` !`git diff HEAD -- src/` ``
  (cambios sin commit). La base queda fija en `main` (R7): la comprobación de permisos de la
  inyección `!` rechaza sustituciones `$(…)`, así que no se puede calcular una base por
  defecto. El argumento se pasa como contexto para el revisor (p. ej. `#n`). La skill pide revisar el diff contra los siete principios y responder con el
  formato de veredicto de [contracts/reviewers.md](./contracts/reviewers.md).
- **Rationale**: con `context: fork` y `agent`, el contenido de la skill se ejecuta como tarea
  del subagente en un contexto aparte, así que la revisión es independiente de la sesión que
  escribió el código (FR-015). La inyección `!` resuelve el diff antes de que empiece el
  subagente.
- **Alternatives considered**: que `/open-pr` invoque `compliance-reviewer` directamente. Se
  descartó porque el issue exige una skill con esas tres claves y porque así la skill también
  se puede ejecutar a mano.

## R3. Herramientas restringidas de los revisores

- **Decision**:
  - `code-reviewer` lleva `tools: Read, Grep, Glob`.
  - `compliance-reviewer` lleva `tools: Read, Grep, Glob, Bash`, más un hook `PreToolUse` en su
    propio frontmatter (matcher `Bash`) que ejecuta `.claude/hooks/allow_only_pytest.py`.
  - El hook permite solo los comandos `uv run pytest …` o `pytest …`. Bloquea con salida 2
    cualquier otro comando, y también los encadenamientos (`;`, `&&`, `||`, `|`, `` ` ``,
    `$(`, `>`, `<`).
- **Rationale**: el campo `tools` de un subagente solo acepta nombres de herramienta. No
  admite `Bash(uv run pytest:*)`, así que la restricción a pytest tiene que ser un hook. Los
  hooks del frontmatter de un subagente se aplican solo a ese subagente. Esto sigue el
  Principio II: una regla determinista se aplica con código y se cubre con tests.
- **Alternatives considered**:
  - Un hook global que mire `agent_type` en el evento: funciona, pero afecta a todas las
    sesiones y es más difícil de razonar.
  - Confiar en el prompt del subagente: viola el Principio II.
- Sin `Write`/`Edit` y sin Bash libre, ningún revisor puede modificar archivos (SC-005). Lo
  verifica `test_reviewers_config.py`, que lee el frontmatter.

## R4. Acceso al Project y a los issues

- **Decision**:
  - El acceso es por el MCP `github` de #1. El Project se lee con `projects_list`
    (`list_project_fields` y `list_project_items` con `field_names: ["Status"]`) y se actualiza
    con `projects_write`.
  - Los comentarios usan `add_issue_comment` y el PR usa `create_pull_request`.
  - El owner (`danielpvsofka`) y el número del Project viven en una sola fuente: la sección
    "Flujo de tickets" de `CLAUDE.md`, que leen las dos piezas.
- **Hallazgo**: con el `GITHUB_PAT` actual, `list_projects` devuelve
  `403 Resource not accessible by personal access token`.
- **Prerrequisito**: el token necesita permiso de Projects con lectura y escritura (classic:
  scope `project`; fine-grained: *Projects: Read and write* de la cuenta). Además, el número
  del Project se completa en `CLAUDE.md` cuando el token tenga acceso. Ambos pasos están en
  [quickstart.md](./quickstart.md).
- **Comportamiento sin acceso**: si la primera llamada al Project falla, el comando se detiene
  antes de cambiar nada y explica qué falta (edge case de la spec).
- **Alternatives considered**: `gh project item-edit` desde Bash. Exige que cada
  desarrollador tenga `gh` instalado y autenticado aparte, y duplica la configuración del MCP.

## R5. Elección del "siguiente" ítem

- **Decision**: es el primer ítem con `Status = Todo` en el orden que devuelve
  `list_project_items`, que es el orden manual del Project. Se filtra con `query: "status:Todo"`
  cuando el servidor lo admite y, si no, en el cliente.
- **Rationale**: ese es el orden que el equipo ve y prioriza en el tablero.

## R6. `/ticket` y Spec Kit

- **Decision**:
  1. `/ticket` lee el issue con `issue_read`.
  2. Busca si ya existe una feature con `Issue: #n` en `specs/*/spec.md`.
  3. Si no existe: mueve el ítem a In progress e invoca la skill `speckit-specify` con
     `<título>\n\n<cuerpo>\n\nIssue: #<n>`.
  4. Comenta en el issue.
- **Rationale**: se reutiliza el flujo actual sin duplicarlo. El orden "mover → specify →
  comentar" sigue FR-003 y el edge case de fallo: si falla la spec, no se comenta.
- El nombre de la skill es `speckit-specify` con guion, porque `speckit.specify` no existe en
  este entorno. No se crea rama.

## R7. Rama base, push y PR en `/open-pr`

- **Decision**:
  - La base es la rama por defecto del repo (`main`); la cabeza es la rama actual. Si la rama
    actual es `main` o no tiene commits nuevos frente a la base, el comando se detiene.
  - Si hay cambios sin commit o la rama no está publicada, el comando los muestra y pide
    confirmación explícita antes de hacer `git commit` o `git push`. Si el usuario no
    confirma, se detiene sin abrir PR.
  - Antes de crear el PR busca uno abierto para la misma rama con `list_pull_requests`
    (`head`). Si existe, informa su enlace.
- **Rationale**: `Closes #n` solo cierra el issue cuando el PR se fusiona en la rama por
  defecto, y es ese cierre lo que dispara el workflow que pasa a Done (R8). La convención del
  equipo prohíbe hacer commit o push sin confirmación.

## R8. Done automático

- **Decision**: en la configuración del Project se activan dos workflows integrados:
  - "Item closed" → `Status: Done`;
  - "Pull request merged" → `Status: Done`.

  La activación es manual y está documentada en el quickstart.
- **Rationale**: es configuración del Project, sin código. Además, la API no permite
  activarlos.

## R9. Orden de las verificaciones en `/open-pr`

- **Decision**: el comando sigue este orden y se detiene en el primer bloqueo:
  1. precondiciones (rama, diff, acceso al Project);
  2. `uv run pytest`;
  3. `code-reviewer` (Agent tool);
  4. `compliance-check`, solo si el diff incluye `src/`;
  5. confirmación de commit y push;
  6. creación del PR;
  7. paso a In review;
  8. comentario en el issue.
- **Rationale**: los tests son lo más barato y determinista (acceptance US2-1 pide no invocar
  revisiones si fallan). Las revisiones van antes del push para no publicar código bloqueado.
- **Veredicto ilegible**: si una revisión no trae una línea `VEREDICTO:` reconocible, se trata
  como bloqueante.

## R10. Tests

- **Decision**: solo hay código Python en dos lugares, los dos con tests en `.claude/hooks/`
  (ya en `testpaths`):
  - `allow_only_pytest.py`, con `test_allow_only_pytest.py`. Cubre comandos permitidos,
    prohibidos, encadenados, vacíos y JSON malformado.
  - `test_reviewers_config.py`: parsea el frontmatter de los dos subagentes y de
    `compliance-check`. Verifica las herramientas exactas, el hook de `compliance-reviewer` y
    las claves `context: fork`, `agent`, `allowed-tools` y `argument-hint`.

  Los comandos y skills son instrucciones en Markdown y se validan con los escenarios de
  [quickstart.md](./quickstart.md).
- **Alternatives considered**: tests de extremo a extremo contra GitHub. Requieren red y
  token; quedan como validación manual.
