# Tasks: Plugin reutilizable por otros equipos

**Input**: Design documents from `specs/010-reusable-plugin/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/plugin.md](./contracts/plugin.md), [quickstart.md](./quickstart.md)

**Tests**: obligatorios (FR-007, Principio VII). Esta feature es, en esencia, archivos de
configuración empaquetados y el test que los vigila: no hay código de producción bajo `src/`. El
único módulo nuevo de código es el test de integridad `.claude/hooks/test_plugin_devkit.py`. Los
tests no usan red, modelo ni clave.

**Sin cambios de reglas de negocio**: no se toca `src/`, la política, el core, los hooks del SDK
ni los prompts del agente de originación. La única edición de una pieza original es la línea de
constitución ausente de `compliance-reviewer` (T003, FR-010).

**Datos ficticios**: ningún número con forma de tarjeta o de documento como literal. Los tests
construyen la tarjeta con `luhn_valid_number` (de `.claude/hooks/conftest.py`) y la cédula en
ejecución (etiqueta + dígitos repetidos), como hace `test_block_sensitive_data.py`. El README
no lleva números con forma real. Ningún archivo del plugin repite la tasa ni los umbrales.

**Notas de ejecución**:
- `run_hook` (conftest) resuelve `HOOKS_DIR / script_name`; con una ruta absoluta el resultado es la
  propia ruta absoluta, así que sirve para ejecutar el hook empaquetado sin duplicar el arnés.
- Copiar archivos con `Copy-Item` (byte a byte) para que la comparación sea exacta; el test ignora
  de todos modos el fin de línea.
- Las rutas de los tests se calculan desde `Path(__file__)`, sin literales absolutos.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: paralelizable (archivo distinto, sin dependencias pendientes)
- **[Story]**: historia de spec.md (US1–US4)
- Rutas relativas a la raíz del repositorio; `plugin/` abrevia `plugins/crediagil-devkit/`.

---

## Phase 1: Setup

- [X] T001 Línea base: `uv run pytest -q` en verde y comprobar que `[tool.pytest.ini_options] testpaths` de `pyproject.toml` ya incluye `.claude/hooks` (el test nuevo se recoge solo; no cambiar `pyproject.toml`). Confirmar que `.claude/` contiene solo lo clasificado en `data-model.md` ("Piezas empaquetadas" y "Lista de exclusiones"): `ls .claude/agents .claude/commands .claude/skills .claude/hooks`; anotar cualquier pieza no prevista antes de seguir.

---

## Phase 2: Foundational (bloquea US1–US4)

**Purpose**: la única edición de un original. El resto de las piezas se copian sin cambiarlas.

- [X] T002 Test, que debe fallar, en `.claude/hooks/test_reviewers_config.py`: `test_compliance_reviewer_avisa_si_falta_constitucion` comprueba que el cuerpo de `.claude/agents/compliance-reviewer.md` (después del frontmatter) manda, cuando `.specify/memory/constitution.md` no existe, responder `VEREDICTO: BLOQUEANTE` con un hallazgo que diga que falta la constitución y dónde se espera (research.md R5; FR-010).
- [X] T003 Editar `.claude/agents/compliance-reviewer.md`, paso 1 del procedimiento: tras "Lee `.specify/memory/constitution.md` completa…", añadir una línea: si ese archivo no existe, no revises: responde `VEREDICTO: BLOQUEANTE` con el hallazgo `[bloqueante] — falta la constitución: se espera en .specify/memory/constitution.md` y nada más. No cambiar otra línea (el cuerpo es común con la variante del plugin). Hacer pasar T002 y todo `uv run pytest .claude/hooks`.

**Checkpoint**: el original ya avisa si falta la constitución; el cuerpo no volverá a cambiar en esta feature.

---

## Phase 3: User Story 1 - Instalar el plugin desde el repositorio (Priority: P1) 🎯 MVP

**Goal**: existe el plugin `crediagil-devkit` con subagente, skill y hook, y el catálogo que permite
instalarlo con `/plugin`.

**Independent Test**: `uv run pytest .claude/hooks/test_plugin_devkit.py -k "estructura or manifiestos or hook"`
y, con el usuario, la instalación en un repositorio vacío (T026).

### Tests para US1 (deben fallar hasta T006–T009)

- [X] T004 [US1] Crear `.claude/hooks/test_plugin_devkit.py` con las constantes de ruta (`RAIZ = Path(__file__).resolve().parents[2]`, `PLUGIN = RAIZ / "plugins" / "crediagil-devkit"`, `CATALOGO = RAIZ / ".claude-plugin" / "marketplace.json"`) y las clases `TestEstructura` y `TestManifiestos` (contracts/plugin.md filas 8 y 9): `plugin.json` y `marketplace.json` son JSON válido; `plugin.json` tiene `name == "crediagil-devkit"`, `version` con formato `MAYOR.MENOR.PARCHE` y `description` no vacía; el catálogo tiene `name`, `owner.name` y `plugins` con una entrada de `name == "crediagil-devkit"`, `source == "./plugins/crediagil-devkit"` (la carpeta existe y contiene `.claude-plugin/plugin.json`) y `version` igual a la de `plugin.json`; existen `agents/code-reviewer.md`, `agents/compliance-reviewer.md`, `skills/compliance-check/SKILL.md`, `hooks/hooks.json`, `hooks/block_sensitive_data.py`, `hooks/_hooklib.py` y `README.md`; `hooks.json` es JSON con un `PreToolUse` cuyo `matcher` es igual al del hook `block_sensitive_data.py` de `.claude/settings.json` y cuyo `command` referencia `${CLAUDE_PLUGIN_ROOT}/hooks/block_sensitive_data.py`, que existe en el plugin.
- [X] T005 [US1] En el mismo archivo, clase `TestHookEmpaquetado` (SC-004, FR-004; fila 12): ejecutar `plugin/hooks/block_sensitive_data.py` con el fixture `run_hook` pasando la ruta absoluta del script. Casos, con los números construidos en ejecución (`luhn_valid_number`; cédula = etiqueta + `"1" * 10`; cuenta = etiqueta + `"2" * 12`): tarjeta válida → salida 2; cédula con etiqueta → 2; cuenta con etiqueta → 2; la misma cédula con `dato-ficticio` en la misma línea → 0; un número largo sin etiqueta y sin forma de tarjeta → 0; un evento no JSON → falla cerrado (salida 2, como el original). Parametrizar el contenido para que los mismos casos puedan lanzarse contra el hook original y compararse (mismo código de salida).

### Implementación para US1

- [X] T006 [US1] Crear `.claude-plugin/marketplace.json` y `plugins/crediagil-devkit/.claude-plugin/plugin.json` con el contenido exacto de contracts/plugin.md (`name` `crediagil`, `owner.name` `Crediágil`; plugin `crediagil-devkit`, versión `0.1.0`, misma descripción en ambos; `source` `./plugins/crediagil-devkit`). La descripción no repite tasa ni umbrales.
- [X] T007 [P] [US1] Copiar byte a byte, con `Copy-Item`: `.claude/hooks/block_sensitive_data.py` → `plugin/hooks/block_sensitive_data.py`; `.claude/hooks/_hooklib.py` → `plugin/hooks/_hooklib.py`. No copiar tests, `conftest.py` ni `__pycache__`.
- [X] T008 [P] [US1] Crear las tres variantes (research.md R3, data-model.md "Piezas empaquetadas") partiendo de una copia del original y aplicando exactamente estas sustituciones, cada una una sola vez:
  - `plugin/agents/code-reviewer.md` (original `.claude/agents/code-reviewer.md`): quitar ` Lo invoca /open-pr.` de la descripción. El cuerpo queda igual.
  - `plugin/agents/compliance-reviewer.md` (original `.claude/agents/compliance-reviewer.md`): `tools: Read, Grep, Glob, Bash` → `tools: Read, Grep, Glob`; ` Lectura y pytest.` → ` Solo lectura.` en la descripción; y eliminar el bloque `hooks:` completo del frontmatter (las siete líneas desde `hooks:` hasta la línea `command: uv run --no-project python "$CLAUDE_PROJECT_DIR/.claude/hooks/allow_only_pytest.py"`). El cuerpo queda igual.
  - `plugin/skills/compliance-check/SKILL.md` (original `.claude/skills/compliance-check/SKILL.md`): `agent: compliance-reviewer` → `agent: crediagil-devkit:compliance-reviewer`; ` La invoca /open-pr cuando el diff toca lógica de negocio.` → ` Úsala cuando el diff toca lógica de negocio.` en la descripción; y `, Bash(uv run pytest:*)` → `` (vacío) en la línea `allowed-tools`. El cuerpo queda igual.
- [X] T009 [US1] Crear `plugins/crediagil-devkit/hooks/hooks.json` con el contenido exacto de contracts/plugin.md (`PreToolUse`, `matcher` `Write|Edit|MultiEdit|NotebookEdit`, `command` `uv run --no-project python "${CLAUDE_PLUGIN_ROOT}/hooks/block_sensitive_data.py"`).
- [X] T010 [US1] Hacer pasar T004 y T005 (el README lo escribe T019: hasta entonces añadir un `README.md` provisional de una línea para que `TestEstructura` pase, y sustituirlo en T019). `uv run pytest .claude/hooks/test_plugin_devkit.py`.

**Checkpoint**: el plugin y el catálogo existen y el hook empaquetado se comporta como el original.

---

## Phase 4: User Story 2 - Las copias no divergen de `.claude/` (Priority: P1)

**Goal**: el test falla, nombrando pieza y archivo, si una copia diverge, falta, sobra o queda sin
clasificar; y no falla por el fin de línea.

**Independent Test**: `uv run pytest .claude/hooks/test_plugin_devkit.py -k "diverg or negativo"`; cambiar
una línea de un original y ver el fallo (quickstart §2).

- [X] T011 [US2] En `.claude/hooks/test_plugin_devkit.py`, definir las tres tablas de data-model.md como constantes: `EMPAQUETADAS` (original → copia, con tipo `identica` o `variante` y, en las variantes, la lista de sustituciones de T008 como pares `(antes, despues)`), `EXCLUIDAS` (pieza → motivo) y los patrones ignorados (`test_*.py`, `conftest.py`, `__pycache__`, `rules/`). Implementar `comprobar(raiz: Path) -> list[Incumplimiento]` (con `Incumplimiento(pieza, archivo, motivo)` y un `__str__` que nombra pieza y archivo, FR-008), que no lee el repositorio real sino `raiz`: normaliza `\r\n` → `\n`, compara copias, aplica variantes exigiendo que cada `antes` aparezca exactamente una vez, detecta faltantes en ambos lados, archivos sobrantes del plugin (fuera de las tablas y de `plugin.json`, `hooks.json`, `README.md`), piezas de `.claude/` sin clasificar y excluidas presentes en el plugin. Motivos: `diverge`, `falta en el plugin`, `falta el original`, `sobra en el plugin`, `sin clasificar`, `sustitución no aplica`, `excluida presente`.
- [X] T012 [US2] Clase `TestDivergencia` (filas 1–7): `comprobar(RAIZ) == []` sobre el árbol real, con el mensaje de fallo que lista cada incumplimiento; y un test por pieza empaquetada (parametrizado por `EMPAQUETADAS`) para que un fallo nombre la pieza.
- [X] T013 [US2] Clase `TestControlesNegativos`: cada test copia `.claude/` y `plugins/` y el catálogo a `tmp_path` con `shutil.copytree` (nunca modifica el árbol real) y comprueba el motivo exacto de `comprobar(tmp_path)`: (a) cambiar un byte de una copia → `diverge` con su pieza; (b) cambiar un byte de un original → `diverge`; (c) borrar una copia → `falta en el plugin`; (d) borrar un original → `falta el original`; (e) añadir un archivo al plugin → `sobra en el plugin`; (f) añadir una pieza a `.claude/agents/` → `sin clasificar`; (g) copiar una pieza excluida al plugin (por ejemplo `commands/open-pr.md` o `hooks/require_specs.py`) → `excluida presente`; (h) cambiar una línea de un original de modo que una sustitución deje de aplicar → `sustitución no aplica`; (i) convertir un original de `\n` a `\r\n` (solo el fin de línea) → **sin** incumplimientos (FR-008).
- [X] T014 [US2] Clase `TestRevisoresEmpaquetados` (fila 10, Principio II): ningún subagente de `plugin/agents/` declara `Write`, `Edit`, `MultiEdit`, `NotebookEdit` ni `Bash` en `tools`, y ninguno tiene el campo `hooks:` (un plugin lo ignoraría y la restricción quedaría sin efecto); `compliance-check` del plugin referencia `agent: crediagil-devkit:compliance-reviewer`, mantiene `context: fork` y su `allowed-tools` no incluye herramientas de escritura ni `Bash(uv run pytest:*)`. Reutilizar `top_level`, `tool_set` y `frontmatter_lines` de `test_reviewers_config.py` si se pueden importar sin duplicar; si no, importarlos con `from test_reviewers_config import …` (misma carpeta).
- [X] T015 [US2] Ejecutar `uv run pytest .claude/hooks/test_plugin_devkit.py` y comprobar que corre en menos de 10 s (SC-005; `--durations=5`); hacer el cambio manual del quickstart §2 (una línea de `.claude/agents/code-reviewer.md`, ver el fallo nombrando `code-reviewer`, revertir).

**Checkpoint**: tocar un original sin su copia rompe la suite con un mensaje que dice qué arreglar.

---

## Phase 5: User Story 3 - Lo específico de este repositorio queda fuera (Priority: P2)

**Goal**: el plugin solo contiene piezas genéricas y no depende de archivos que solo existen aquí.

**Independent Test**: `uv run pytest .claude/hooks/test_plugin_devkit.py -k "excluid or aislamiento or dato"`.

- [X] T016 [US3] Clase `TestAislamiento` (fila 11, FR-006, FR-011, FR-005): (a) `git ls-files`-equivalente sobre `PLUGIN` (recorrer el árbol) no contiene `require_specs`, `format_python`, `block_secret_access`, `allow_only_pytest`, `open-pr`, `ticket` ni `speckit`; (b) ningún archivo del plugin referencia recursos que no viajan con él: no aparecen `$CLAUDE_PROJECT_DIR/.claude`, `.claude/hooks/`, `.claude/commands`, `/ticket`, `/open-pr` ni `require_spec` (las referencias permitidas, porque son convenciones del repositorio consumidor y el README las documenta, son `.specify/memory/constitution.md`, `src/`, `specs/` y `main`); (c) ningún archivo de texto del plugin contiene la tasa ni los umbrales de la política: importar `crediagil.policy.params` y buscar cada valor en los formatos de pesos con punto, coma y sin separador y de porcentaje con y sin espacio (misma comprobación de `crediagil/casos/test_catalogo.py`); (d) pasar cada línea de cada archivo de texto del plugin por `find_in_line` de `block_sensitive_data.py` (cargado por ruta con `importlib`, como hará `test_datos_ficticios.py` de #9) y fallar si hay un hallazgo en una línea sin `dato-ficticio`.
- [X] T017 [US3] Control negativo de T016 sobre copia temporal: (a) añadir al README copiado una línea con la tasa (valor tomado de `crediagil.policy.params`) → T016(c) falla; (b) añadir un archivo `ticket/SKILL.md` → T016(a) falla; (c) añadir al agente copiado una referencia a `.claude/hooks/` → T016(b) falla. Hacer pasar T016 y T017 contra el árbol real y corregir lo que aparezca en las copias (si es un original, no se corrige aquí: se documenta como variante o trabajo futuro).

**Checkpoint**: el plugin no arrastra nada de Crediágil y el test lo demuestra.

---

## Phase 6: User Story 4 - Instrucciones de instalación y uso (Priority: P2)

**Goal**: un README que permite instalar el plugin a quien no conoce el repositorio.

**Independent Test**: `uv run pytest .claude/hooks/test_plugin_devkit.py -k readme`; una persona sigue solo el README (T026).

- [X] T018 [US4] Test, que debe fallar, `TestReadme` en `.claude/hooks/test_plugin_devkit.py` (FR-009): el README contiene los comandos `/plugin marketplace add` y `/plugin install crediagil-devkit@crediagil`; nombra `code-reviewer`, `compliance-check` y `block_sensitive_data` (o "datos con forma real") con una línea cada uno; documenta los requisitos (`uv`; para `compliance-check`: `.specify/memory/constitution.md`, rama base `main` y código en `src/`), el comportamiento sin constitución (`VEREDICTO: BLOQUEANTE`), el prefijo `crediagil-devkit:` y la convivencia con piezas del mismo nombre, cómo actualizar (`/plugin marketplace update` o equivalente) y la limitación de la variante (el revisor empaquetado es de solo lectura y no ejecuta pytest); no contiene `crediagil.policy`, ni números con forma real (cubierto por T016).
- [X] T019 [US4] Escribir `plugins/crediagil-devkit/README.md` en español, para quien no conoce el repositorio, con las secciones: qué incluye (tabla de piezas con una línea cada una), requisitos del repositorio consumidor, instalación paso a paso (añadir el catálogo por ruta local y por `owner/repo`, instalar, comprobar con `/plugin`), uso (nombres con espacio de nombres y un ejemplo de invocación), convivencia con piezas propias del mismo nombre, sin constitución, limitaciones (revisor de solo lectura; sin `block_secret_access`; sin versionado automático) y cómo actualizar. Verificar los comandos exactos de `/plugin` con `claude plugin --help` o la documentación antes de escribirlos. Sustituir el README provisional de T010. Hacer pasar T018 y T016.
- [X] T020 [P] [US4] Documentación del repositorio: `README.md` (sección "Plugin reutilizable": qué es, enlace al README del plugin, comando del test de integridad, estado del #10); `CLAUDE.md` (una entrada en "Stack y comandos" o una sección breve: el plugin vive en `plugins/crediagil-devkit/`, las originales siguen en `.claude/`, cualquier cambio en una pieza empaquetada exige actualizar su copia y sube la versión, `uv run pytest .claude/hooks/test_plugin_devkit.py`; sin repetir tasa ni umbrales); `DECISIONES.md` (decisión: copias con variantes declaradas, no enlaces, y por qué). `CLAUDE.md` lo toca el flujo de la feature, no un hook bloquea: no modificar `.claude/settings.json`.

**Checkpoint**: alguien ajeno puede instalar el plugin con solo el README.

---

## Phase 7: Polish y validación

- [X] T021 Ejecutar `uv run ruff check` y `uv run ruff format --check` (los `.py` copiados al plugin son idénticos a sus originales, que ya cumplen) y `uv run pytest` completo; confirmar que la suite de #9 y las demás siguen en verde (FR-012: las piezas de este repositorio no cambian de comportamiento). Buscar la tasa y los umbrales como literales en `plugins/` y `.claude-plugin/`: no debe haber ninguno.
- [X] T022 Medir y anotar en `quickstart.md` "Resultado de las validaciones": `uv run pytest` completo (número de tests y duración), `uv run pytest .claude/hooks/test_plugin_devkit.py` (duración, SC-005 exige menos de 10 s) y el resultado de los pasos 1, 2, 3 y 6 del quickstart. Marcar en este archivo las tareas completadas.
- [ ] T023 Recorrido manual con el usuario (quickstart §4 y §5), en un directorio vacío fuera de este repositorio: añadir el catálogo, instalar `crediagil-devkit`, ver `crediagil-devkit:code-reviewer` y `/crediagil-devkit:compliance-check`, comprobar que el hook bloquea una tarjeta o una cédula con etiqueta (números inventados en el momento) y deja pasar la misma línea con `dato-ficticio`, y que sin constitución la skill responde `VEREDICTO: BLOQUEANTE` con el motivo. Anotar las discrepancias en `quickstart.md`; si algo del formato de plugin difiere de lo investigado, corregir `research.md` y el contrato antes de cerrar.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (T001)**: sin dependencias.
- **Foundational (T002–T003)**: depende de T001; **bloquea US1–US4** porque fija el cuerpo del revisor que la variante comparte.
- **US1 (T004–T010)**: depende de T003. T004 y T005 (tests, mismo archivo) primero y en orden; T006, T007, T008 y T009 son independientes entre sí (T007 y T008 paralelizables); T010 depende de todas.
- **US2 (T011–T015)**: depende de US1 (necesita el plugin completo). Mismo archivo que T004/T005, por lo que van en orden: T011 → T012 → T013 → T014 → T015.
- **US3 (T016–T017)**: depende de US2 (usa `comprobar` y las tablas) y del README de T019 para que (c) y (d) cubran todo el plugin; hasta entonces cubre el README provisional.
- **US4 (T018–T020)**: depende de US1; T018 → T019; T020 es paralelizable con T018–T019 (archivos distintos).
- **Polish (T021–T023)**: depende de las historias que se entreguen; T022 al final, T023 con el usuario.

### Parallel Opportunities

- T007 y T008 (copias y variantes) en paralelo tras T006.
- T020 (documentación del repositorio) en paralelo con T018–T019.
- Tras US1: US4 (README) puede avanzar a la vez que US2, salvo el archivo de test compartido.

### Parallel Example: US1

```bash
# Tras T006, las copias y las variantes a la vez:
Task: "Copiar code-reviewer, block_sensitive_data y _hooklib al plugin (T007)"
Task: "Crear las variantes compliance-reviewer y compliance-check (T008)"
```

---

## Implementation Strategy

### MVP primero (US1 + US2)

1. Setup y Foundational (la línea de constitución ausente).
2. US1: plugin, catálogo y hook funcionando, con sus tests.
3. US2: tablas y test de divergencia con controles negativos.
4. **Parar y validar**: `uv run pytest` completo; tocar un original hace fallar la suite (T015).
5. Con eso ya se cumplen los criterios del issue sobre plugin, catálogo y test de divergencia; el README y las exclusiones cierran los otros dos.

### Entrega incremental

1. + US3: exclusiones y aislamiento comprobados.
2. + US4: README del plugin y documentación del repositorio.
3. Medición final y recorrido manual de instalación.

---

## Notes

- [P] = archivo distinto y sin dependencias pendientes.
- Verificar que los tests fallan antes de implementar (T002, T004–T005, T018).
- No hacer commit ni push sin confirmación explícita del usuario.
- El revisor empaquetado es de solo lectura y no ejecuta pytest (research.md R3): coste conocido, fuera de alcance reescribir su cuerpo.
- Si un hook del flujo (`block_sensitive_data`) rechaza una línea al escribir tests o README, usar números construidos en ejecución o el marcador `dato-ficticio` en la misma línea solo si es deliberadamente ficticio.
- El comando exacto de actualización de plugins se verifica contra la documentación o la CLI en T019; no se inventa.
