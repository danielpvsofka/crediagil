---

description: "Lista de tareas para el ecosistema base de Claude Code"
---

# Tasks: Ecosistema base de Claude Code

**Input**: Documentos de diseño en `specs/001-claude-code-ecosystem/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/hooks.md](./contracts/hooks.md),
[contracts/config.md](./contracts/config.md), [quickstart.md](./quickstart.md)

**Tests**: OBLIGATORIOS. FR-016 y el Principio VII los exigen. Cada test de hook va junto al
hook, lo ejecuta como subproceso con JSON por stdin y se escribe ANTES del hook (debe fallar
primero).

**Organization**: tareas agrupadas por historia de usuario (US1–US6 de spec.md).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: paralelizable (archivo distinto, sin dependencias pendientes)
- **[Story]**: historia de usuario de spec.md
- Rutas relativas a la raíz del repositorio

## Convenciones transversales (aplican a todas las tareas)

- Hooks: Python con solo biblioteca estándar, ejecutados como
  `uv run --no-project python "$CLAUDE_PROJECT_DIR/.claude/hooks/<hook>.py"` (research R1).
- Protocolo (research R2): salida 0 permite, 2 bloquea con motivo en stderr prefijado
  `[<hook>]`, 1 avisa sin bloquear (solo PostToolUse). Entrada malformada en un hook de
  bloqueo → salida 2 (FR-017).
- Ningún literal con forma de tarjeta, cédula o cuenta real en el código ni en los tests: los
  números válidos por Luhn se generan en tiempo de ejecución (research R4, Principio III).
- `.claude/settings.json` lo tocan varias historias. Sus ediciones son secuenciales y nunca
  llevan [P].

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: dependencias de desarrollo y configuración base

- [X] T001 Crear `pyproject.toml` en la raíz según contracts/config.md: `[project] name = "crediagil"`, `version = "0.1.0"`, `requires-python = ">=3.12"`, `dependencies = []`; `[dependency-groups] dev = ["pytest", "ruff"]`; `[tool.ruff] line-length = 100`, `target-version = "py312"`; `[tool.pytest.ini_options] testpaths = [".claude/hooks"]`
- [X] T002 Ejecutar `uv sync --group dev` para generar `uv.lock` y `.venv/`, y añadir `.venv/`, `__pycache__/` y `.pytest_cache/` a `.gitignore` (versionar `uv.lock`)
- [X] T003 Crear el directorio `.claude/hooks/` y el directorio `.claude/rules/`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: utilidades compartidas por todos los hooks y su arnés de tests

**⚠️ CRITICAL**: ningún hook (US2–US5) puede empezar hasta completar esta fase

- [X] T004 Implementar `.claude/hooks/_hooklib.py` (stdlib): `read_event() -> dict` (lee stdin, lanza `HookInputError` si no es JSON objeto o falta `tool_name`/`tool_input`); `project_root(event) -> Path` (`CLAUDE_PROJECT_DIR` o, en su defecto, `event["cwd"]`); `target_path(event) -> str | None` (`tool_input.file_path` o `tool_input.notebook_path`); `new_content(event) -> list[str]` (`content` de Write, `new_string` de Edit, cada `edits[].new_string` de MultiEdit, `new_source` de NotebookEdit); `is_under(path, root, "src") -> bool` (normaliza a absoluta, `\` → `/`, sin distinguir mayúsculas en Windows, compara segmentos completos para que `srcx/` no cuente); `block(hook_name, message)` (escribe `[hook_name] message` en stderr y sale con 2); `allow()` (sale con 0)
- [X] T005 Implementar `.claude/hooks/conftest.py` con el fixture `run_hook` que devuelve una función `(script_name: str, payload: dict | str, project_dir: Path, extra_env: dict | None = None) -> tuple[int, str, str]`: ejecuta `[sys.executable, <ruta absoluta del hook>]` con `subprocess.run`, pasa `json.dumps(payload)` (o el string tal cual, para probar entrada malformada) por stdin, `env` con `CLAUDE_PROJECT_DIR=project_dir` y timeout de 30 s; y el helper `luhn_valid_number(prefix: str, length: int) -> str`, que completa con dígitos y calcula el dígito de control
- [X] T006 Crear `.claude/settings.json` inicial con `{"permissions": {"deny": []}, "hooks": {"PreToolUse": [], "PostToolUse": []}}`, JSON válido; las historias lo completan

**Checkpoint**: `uv run pytest` corre (0 tests) sin errores de recolección

---

## Phase 3: User Story 1 - Convenciones del equipo al clonar (Priority: P1) 🎯 MVP

**Goal**: un clon limpio carga convenciones y constitución sin configurar nada; lo personal no
se versiona.

**Independent Test**: clonar en un directorio limpio, abrir Claude Code, `/memory` muestra
`CLAUDE.md` y la constitución importada; `CLAUDE.local.md` y `.claude/settings.local.json`
no aparecen en `git status` (quickstart §2).

- [X] T007 [P] [US1] Crear `CLAUDE.md` en la raíz, en español, con: (1) `@.specify/memory/constitution.md` en la primera sección; (2) flujo obligatorio `/speckit-specify` → `/speckit-plan` → `/speckit-tasks` → `/speckit-implement`; (3) stack: Python ≥ 3.12 con `uv`, formato con `ruff` (automático vía hook), tests con `uv run pytest` junto al código; (4) datos ficticios y uso del marcador `dato-ficticio` solo para fixtures deliberadamente ficticios; (5) tabla de hooks activos (qué bloquea cada uno y qué hacer si bloquea); (6) los secretos van en `.env`, que el modelo no puede leer; `GITHUB_PAT` se define en el entorno; (7) lo personal va en `CLAUDE.local.md`. No duplicar tasa ni umbrales: remitir a la constitución
- [X] T008 [P] [US1] Actualizar `.gitignore` con las líneas de contracts/config.md que falten: `CLAUDE.local.md`, `.env.*`, `secrets/` (ya existen `.env` y `.claude/settings.local.json`; conservar `.vscode/`)
- [X] T009 [P] [US1] Crear `.claude/rules/tests.md` con frontmatter `paths: ["**/test_*.py", "**/*_test.py", "tests/**"]` y guía: tests como subproceso para hooks, bordes exactos de umbrales (Principio VII), datos ficticios generados o marcados con `dato-ficticio`, sin red ni secretos
- [X] T010 [P] [US1] Crear `.claude/rules/mcp-server.md` con frontmatter `paths: ["src/**/mcp/**", "src/**/mcp_server/**"]` y guía: herramientas MCP sin lógica de negocio fuera de los hooks del SDK (Principio II), sin credenciales en código, trazabilidad de origen (Principio VI)
- [X] T011 [P] [US1] Crear `.claude/rules/hooks.md` con frontmatter `paths: [".claude/hooks/**"]` y guía: solo stdlib, usar `_hooklib.py`, fallo seguro con salida 2, test `test_<hook>.py` obligatorio junto al hook, registro en `.claude/settings.json`
- [X] T012 [US1] Verificar que `git status --ignored` lista como ignorados `CLAUDE.local.md` y `.claude/settings.local.json` creados de prueba, y luego borrar los archivos de prueba

**Checkpoint**: US1 verificable por sí sola (sin hooks)

---

## Phase 4: User Story 2 - Spec antes que código (Priority: P1)

**Goal**: bloquear cambios en `src/` si la feature activa no tiene spec, plan y tareas no
vacíos (FR-005–007).

**Independent Test**: casos 1–8 de `require_specs` en contracts/hooks.md.

### Tests for User Story 2 ⚠️ (escribir primero, deben fallar)

- [X] T013 [US2] Escribir `.claude/hooks/test_require_specs.py` con los casos 1–8 de contracts/hooks.md §require_specs. Cada test construye en `tmp_path` un `.specify/feature.json` con `{"feature_directory": "specs/999-demo"}` y los documentos según el caso, y usa `run_hook("require_specs.py", ...)` con eventos `Write`, `Edit` y `NotebookEdit`; afirma código de salida y que stderr menciona la feature y los documentos faltantes

### Implementation for User Story 2

- [X] T014 [US2] Implementar `.claude/hooks/require_specs.py` usando `_hooklib`. Si `target_path` no está bajo `<root>/src`, sale con 0. Si no, lee `<root>/.specify/feature.json`; si falta, no es JSON, no tiene `feature_directory` o el directorio no existe, bloquea con "No hay feature activa: ejecuta /speckit-specify o define feature_directory en .specify/feature.json". Si no, comprueba que `spec.md`, `plan.md` y `tasks.md` existen y que `read_text().strip()` no está vacío, y bloquea listando la feature y los faltantes. Cualquier `HookInputError` bloquea
- [X] T015 [US2] Registrar en `.claude/settings.json` → `hooks.PreToolUse` la entrada `{"matcher": "Write|Edit|MultiEdit|NotebookEdit", "hooks": [{"type": "command", "command": "uv run --no-project python \"$CLAUDE_PROJECT_DIR/.claude/hooks/require_specs.py\""}]}`
- [X] T016 [US2] Ejecutar `uv run pytest .claude/hooks/test_require_specs.py`: todo en verde

**Checkpoint**: US2 funcional; los cambios en `src/` quedan protegidos

---

## Phase 5: User Story 3 - Ningún dato con forma real (Priority: P1)

**Goal**: bloquear tarjetas válidas por Luhn y cédulas/cuentas etiquetadas, con exención
`dato-ficticio` (FR-008–010a).

**Independent Test**: casos 1–13 de `block_sensitive_data` en contracts/hooks.md.

### Tests for User Story 3 ⚠️ (escribir primero, deben fallar)

- [X] T017 [US3] Escribir `.claude/hooks/test_block_sensitive_data.py` con los casos 1–13 de contracts/hooks.md §block_sensitive_data. Todos los números válidos por Luhn se construyen con `luhn_valid_number` de conftest, y las cédulas y cuentas se arman concatenando dígitos en tiempo de ejecución (p. ej. `"1" * 10`). El código fuente del test NO MUST contener literales de 6 o más dígitos junto a una etiqueta ni secuencias Luhn válidas. El caso 12 afirma que stderr no contiene el número completo

### Implementation for User Story 3

- [X] T018 [US3] Implementar `.claude/hooks/block_sensitive_data.py` usando `_hooklib.new_content`, línea por línea, saltando las líneas que contienen `dato-ficticio`. Tarjeta: regex `(?<!\d)\d(?:[ -]?\d){12,18}(?!\d)`, dígitos sin separadores de 13 a 19, primer dígito en `2–6` y Luhn válido. Documento: etiqueta `(?i)\b(c[ée]dula|c\.\s?c\.?|cc|nit|documento|doc)\b` seguida en ≤ 30 caracteres no numéricos de un número que, sin `.` ni `-`, tenga 6–10 dígitos (NIT con DV opcional). Cuenta: etiqueta `(?i)\b(cuenta|cta|ahorros|corriente|account)\b` con 9–20 dígitos y la misma regla de distancia. Si hay hallazgos, bloquea con una línea por hallazgo: `<kind> en línea <n>: ••••<últimos 4>`
- [X] T019 [US3] Registrar `block_sensitive_data.py` en `.claude/settings.json` como segundo hook dentro de la misma entrada `Write|Edit|MultiEdit|NotebookEdit` de `PreToolUse` creada en T015
- [X] T020 [US3] Ejecutar `uv run pytest .claude/hooks/test_block_sensitive_data.py`: todo en verde; confirmar con `git grep` que ningún archivo del repo (salvo regexes) contiene secuencias Luhn válidas

**Checkpoint**: US3 funcional

---

## Phase 6: User Story 4 - Secretos inaccesibles (Priority: P2)

**Goal**: `.env*` y `secrets/` inaccesibles por herramientas de archivo y por terminal; MCP
sin credenciales (FR-011–013).

**Independent Test**: casos 1–9 de `block_secret_access` en contracts/hooks.md, más los pasos
de secretos de quickstart §3 y §4.

### Tests for User Story 4 ⚠️ (escribir primero, deben fallar)

- [X] T021 [US4] Escribir `.claude/hooks/test_block_secret_access.py` con los casos 1–9 de contracts/hooks.md §block_secret_access, parametrizado sobre `tool_name` en `["Bash", "PowerShell"]`

### Implementation for User Story 4

- [X] T022 [US4] Implementar `.claude/hooks/block_secret_access.py`. Toma `tool_input.command` (si falta, bloquea) y bloquea si coincide `(?:^|[\s/\\'"=<>|;&(])\.env(?:\.[\w.-]+)?(?=$|[\s'"|;&)<>])` o `(?:^|[\s/\\'"=<>|;&(])secrets[/\\]`, con el mensaje "Acceso a archivos de secretos bloqueado (.env*, secrets/). Pide al usuario el valor que necesites." No bloquea `.envelope` ni `src/environment.py` (casos 8)
- [X] T023 [US4] Registrar en `.claude/settings.json` → `hooks.PreToolUse` la entrada `{"matcher": "Bash|PowerShell", "hooks": [{"type": "command", "command": "uv run --no-project python \"$CLAUDE_PROJECT_DIR/.claude/hooks/block_secret_access.py\""}]}`
- [X] T024 [US4] Completar `permissions.deny` en `.claude/settings.json` con exactamente: `"Read(./.env)"`, `"Read(./.env.*)"`, `"Read(./secrets/**)"`, `"Edit(./.env)"`, `"Edit(./.env.*)"`, `"Edit(./secrets/**)"`
- [X] T025 [P] [US4] Verificar `.mcp.json`: servidor `github` con `"Authorization": "Bearer ${GITHUB_PAT}"` y `projects` dentro de `X-MCP-Toolsets`; ajustar solo si falta algo
- [X] T026 [US4] Ejecutar `uv run pytest .claude/hooks/test_block_secret_access.py` y el `git grep` de quickstart §4: tests en verde y ningún token literal

**Checkpoint**: US4 funcional

---

## Phase 7: User Story 5 - Formato automático tras editar Python (Priority: P3)

**Goal**: `ruff format` en cada `.py` creado o editado, sin bloquear nunca (FR-014–015).

**Independent Test**: casos 1–4 de `format_python` en contracts/hooks.md.

### Tests for User Story 5 ⚠️ (escribir primero, deben fallar)

- [X] T027 [US5] Escribir `.claude/hooks/test_format_python.py` con los casos 1–4 de contracts/hooks.md §format_python. El caso 1 escribe en `tmp_path` un `.py` con `x=1;y = [1,2 ,3]` y verifica que queda formateado. El caso 3 usa `extra_env` con `PATH` vacío y verifica la salida 1 y el archivo intacto

### Implementation for User Story 5

- [X] T028 [US5] Implementar `.claude/hooks/format_python.py`. Si `target_path` no termina en `.py` o no existe, sale con 0. Si no, ejecuta `uv run --quiet --project <root> ruff format <archivo>` y, si falla porque no encuentra `uv`, `ruff format <archivo>`. Si ambos fallan, escribe un aviso en stderr y sale con 1. Entrada malformada: salida 1. Nunca sale con 2
- [X] T029 [US5] Registrar en `.claude/settings.json` → `hooks.PostToolUse` la entrada `{"matcher": "Write|Edit|MultiEdit", "hooks": [{"type": "command", "command": "uv run --no-project python \"$CLAUDE_PROJECT_DIR/.claude/hooks/format_python.py\""}]}`
- [X] T030 [US5] Ejecutar `uv run pytest .claude/hooks/test_format_python.py`: todo en verde

**Checkpoint**: US5 funcional

---

## Phase 8: User Story 6 - Hooks verificables (Priority: P2)

**Goal**: suite completa de hooks en verde y con cobertura mínima por hook (FR-016, SC-007).

**Independent Test**: `uv run pytest` desde la raíz.

- [X] T031 [US6] Ejecutar `uv run pytest` desde la raíz y confirmar que recoge los 4 archivos `test_*.py` de `.claude/hooks/` (pytest ignora directorios ocultos al recursar; `testpaths` debe resolverlo) y que todo pasa
- [X] T032 [US6] Revisar cada test contra contracts/hooks.md: todos los casos numerados existen, y cada hook tiene al menos un caso de permitir y uno de bloquear (o de formatear y no formatear); añadir los que falten en el `test_<hook>.py` correspondiente
- [X] T033 [US6] Validar `.claude/settings.json` con `uv run --no-project python -c "import json; json.load(open('.claude/settings.json'))"` y comprobar que registra los 4 hooks y las 6 reglas de `deny`

**Checkpoint**: todas las historias verificadas

---

## Phase 9: Polish & Cross-Cutting Concerns

- [X] T034 Ejecutar `uv run ruff format --check .claude/hooks` y `uv run ruff check .claude/hooks` y corregir lo que reporten
- [ ] T035 Ejecutar la validación manual de quickstart.md §3 en una sesión nueva de Claude Code (Bash y PowerShell) y anotar resultados en el PR
- [X] T036 [P] Actualizar la tabla de hooks de `CLAUDE.md` con los mensajes reales de bloqueo, si difieren de lo escrito en T007
- [ ] T037 Marcar como completados en el issue #1 los criterios de aceptación cumplidos y enlazar el PR

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (1)** → **Foundational (2)** → historias.
- **US1 (Phase 3)** solo depende de Setup (no usa `_hooklib` ni `settings.json`).
- **US2, US3, US4, US5** dependen de Foundational y son independientes entre sí, salvo las
  ediciones secuenciales de `.claude/settings.json` (T015 → T019 → T023 → T024 → T029). T019
  añade a la entrada creada en T015.
- **US6 (Phase 8)** depende de US2–US5.
- **Polish (Phase 9)** depende de todo lo anterior.

### Within Each User Story

- Test (debe fallar) → hook → registro en `settings.json` → test en verde.

### Parallel Opportunities

- T007, T008, T009, T010 y T011 (US1) en paralelo: archivos distintos.
- Tras Foundational, los pares test + hook de US2 (T013–T014), US3 (T017–T018), US4
  (T021–T022) y US5 (T027–T028) pueden desarrollarse en paralelo. Solo los registros en
  `settings.json` se serializan.
- T025 en paralelo con el resto de US4.

---

## Parallel Example: User Story 1

```bash
Task: "Crear CLAUDE.md en la raíz ..."                (T007)
Task: "Actualizar .gitignore ..."                      (T008)
Task: "Crear .claude/rules/tests.md ..."               (T009)
Task: "Crear .claude/rules/mcp-server.md ..."          (T010)
Task: "Crear .claude/rules/hooks.md ..."               (T011)
```

## Parallel Example: hooks tras Foundational

```bash
Task: "Escribir test_require_specs.py + require_specs.py"               (T013, T014)
Task: "Escribir test_block_sensitive_data.py + block_sensitive_data.py" (T017, T018)
Task: "Escribir test_block_secret_access.py + block_secret_access.py"   (T021, T022)
Task: "Escribir test_format_python.py + format_python.py"               (T027, T028)
```

---

## Implementation Strategy

### MVP First

1. Phase 1 + Phase 3 (US1): convenciones y separación de lo personal. Ya aporta valor sin hooks.
2. Phase 2 + US2 + US3: los dos controles P1 (spec obligatoria y datos ficticios).
3. **STOP and VALIDATE**: `uv run pytest` y quickstart §2.

### Incremental Delivery

1. US1 → MVP de convenciones.
2. US2 → US3 → controles P1.
3. US4 → secretos.
4. US5 → formato.
5. US6 + Polish → suite completa y validación manual.

### Nota sobre el auto-bloqueo

Al registrar `block_sensitive_data` (T019), cualquier escritura posterior con números con forma
real se bloquea, incluidos los propios tests. Por eso T017 genera los números en tiempo de
ejecución. Al registrar `block_secret_access` (T023), ningún comando puede mencionar `.env`; si
hace falta tocar `.gitignore`, hacerlo con las herramientas de edición, no por terminal.

---

## Notes

- [P] = archivos distintos, sin dependencias pendientes
- Commit por historia completada, siempre con confirmación explícita del usuario
- Evitar: tareas vagas, conflictos en `.claude/settings.json`, literales de datos con forma real
