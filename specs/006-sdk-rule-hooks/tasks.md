# Tasks: Hooks del Agent SDK para las reglas 1 y 2

**Input**: Design documents from `specs/006-sdk-rule-hooks/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/hooks.md](./contracts/hooks.md), [quickstart.md](./quickstart.md)

**Tests**: obligatorios (FR-013, Principio VII). Van junto al código, se escriben primero y deben
fallar. Los tests de los hooks invocan los callbacks **como lo hace el SDK**: con el diccionario de
entrada de `PreToolUse` y comprobando la salida del SDK, sin modelo, sin red y sin la clave de la
API. Usan `tmp_path` para el estado y los documentos ficticios de `documentos_prueba.py`. Una línea
con forma de documento o cuenta junto a su etiqueta lleva `# pragma: dato-ficticio`.

**Orden dentro de `hooks.py` y `test_hooks.py`**: US1 → US2 → US3 → US4 comparten esos dos
archivos, así que van en secuencia.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: paralelizable (archivo distinto, sin dependencias pendientes)
- **[Story]**: historia de spec.md (US1–US4)

---

## Phase 1: Setup

- [X] T001 En `pyproject.toml`, añadir `"claude-agent-sdk>=0.2.168,<0.3"` a `dependencies` y ejecutar `uv sync --group dev` (descarga grande, ~110 MB). Comprobar `uv run python -c "from claude_agent_sdk import ClaudeAgentOptions, HookMatcher"` y que `uv run pytest -q` sigue en verde (414).
- [X] T002 Crear `src/crediagil/agent/__init__.py` con el docstring "Agente de originación: hooks del Agent SDK y (en #7) el orquestador." y `src/crediagil/agent/conftest.py` con el fixture `anyio_backend` que devuelve `"asyncio"`.

---

## Phase 2: Foundational (bloquea US1–US4)

**Purpose**: soporte en el core, registro de negaciones y piezas comunes de los hooks (research R4, R5, R7, R8).

- [X] T003 [P] Mover los helpers de documentos ficticios a `src/crediagil/mcp_server/documentos_prueba.py` (cierra el menor de la revisión de #5).
  - Crear el módulo con `pesos`, `doc_certificado` y `doc_extracto`, copiados de `src/crediagil/mcp_server/conftest.py`, con el docstring "Documentos 100% ficticios para los tests: se construyen al vuelo."
  - Borrar `conftest.py`.
  - Actualizar los imports en `test_originacion.py` y `test_server.py` a `crediagil.mcp_server.documentos_prueba`.
  - Comprobar que `uv run pytest src/crediagil/mcp_server -q` sigue en verde.
- [X] T004 [P] Lectura de solo lectura del estado, en `src/crediagil/mcp_server/estado.py` (research R4).
  - **Tests primero**, en `src/crediagil/mcp_server/test_estado.py`:
    - un archivo existente se lee y se migra en memoria: uno v1 sigue siendo v1 en disco tras `leer_existente()`;
    - un archivo que no existe lanza `ErrorCore` `transitorio`/`ESTADO_ILEGIBLE` y **no crea `e.json`** (el `.lock` puede aparecer);
    - un directorio inexistente → `ESTADO_ILEGIBLE`;
    - un JSON corrupto → `ESTADO_ILEGIBLE` y el contenido queda intacto;
    - con otro `FileLock` sosteniendo el lock, `leer_existente(timeout=0.2)` → `ESTADO_ILEGIBLE` en menos de 2 s.
  - **Implementación**: `AlmacenEstado.leer_existente(self, timeout: float = 5.0) -> dict`:
    - comprueba `self.ruta.exists()`;
    - toma el lock con `self._lock.acquire(timeout=timeout)`;
    - atrapa `filelock.Timeout` y `OSError`, y los convierte en `_ilegible()`;
    - llama a `_cargar(crear=False)`.
  - Añadir el parámetro `crear: bool = True` a `_cargar`; con `False`, un archivo ausente lanza `_ilegible()` en lugar de crear la semilla.
- [X] T005 Evaluación compartida de una solicitud guardada, en `src/crediagil/mcp_server/originacion.py` (research R5). Va después de T003, porque ambos tocan `test_originacion.py`.
  - **Tests primero**, en `src/crediagil/mcp_server/test_originacion.py`:
    - para una solicitud preaprobable guardada por `registrar_solicitud`, `evaluar_solicitud_guardada(solicitud)` devuelve `Resultado` con `decision is Decision.PREAPROBABLE`, `cuota == 467010` (5.000.000 a 12 meses con salario 1.556.700);
    - con salario 1.556.699, `ANALISTA` con motivo `regla_2`;
    - con declarado 2.200.001 sobre 2.000.000, motivo `regla_3`;
    - con nómina 2.200.001, motivo `nomina`;
    - **ignora la evaluación guardada**: tras editar `solicitud["evaluacion"]` para marcarla preaprobable, el resultado sigue siendo `ANALISTA`.
  - **Implementación**: función pública `evaluar_solicitud_guardada(solicitud: dict) -> Resultado` (reconstruye el ingreso con `ingreso_verificado` y los `Hallazgo` con `TipoHallazgo(h["tipo"])`, y llama a `_evaluar`). Hacer que `preaprobar_credito` la use. Los tests de #5 deben seguir en verde.
- [X] T006 [P] Registro de negaciones, en `src/crediagil/agent/negaciones.py` (research R7).
  - **Tests primero**, en `src/crediagil/agent/test_negaciones.py`:
    - `registrar` + `listar()` devuelve una copia (modificarla no altera el registro);
    - `ultima()` es `None` en vacío y la última entrada después;
    - `al_negar` se llama una vez por negación con la `Negacion`;
    - si `al_negar` lanza una excepción, `registrar` no la propaga y el error queda en el log (`caplog`).
  - **Implementación**:
    - `Negacion` como `@dataclass(frozen=True)` con `herramienta`, `codigo`, `mensaje`, `accion`, `detalles: dict` y `momento: str`.
    - `RegistroNegaciones(al_negar=None)` con `registrar`, `listar` y `ultima`.
    - Un `logging.getLogger("crediagil.agent")` para el error de `al_negar`.
- [X] T007 Piezas comunes de los hooks, en `src/crediagil/agent/hooks.py` (data-model.md).
  - **Tests primero**, en `src/crediagil/agent/test_hooks.py` (sección "base"):
    - `ACCIONES` tiene una acción para cada uno de los 8 códigos del data-model;
    - `formatear_motivo(Decision(...))` devuelve exactamente `"[CODIGO] mensaje Acción: acción."`;
    - `salida_deny(decision)` devuelve `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": <motivo>}}`;
    - `PERMITIR == {}`;
    - `Decision.permitir_llamada()` y `Decision.negar(codigo, mensaje, detalles)` crean las decisiones (el nombre `permitir` ya es el campo); `negar` con un código desconocido lanza `ValueError`.
  - **Implementación**: `Decision` como `@dataclass(frozen=True)` con `permitir`, `codigo`, `mensaje`, `accion` y `detalles`; las constantes `ACCIONES` y `PERMITIR`; `formatear_motivo` y `salida_deny`.

**Checkpoint**: `uv run pytest -q` en verde; el core tiene `leer_existente` y `evaluar_solicitud_guardada`.

---

## Phase 3: User Story 1 - Bloquear el registro sin identidad verificada (Priority: P1) 🎯 MVP

**Goal**: hook de `registrar_solicitud` (regla 1).

**Independent Test**: `uv run pytest src/crediagil/agent/test_hooks.py -k registro`.

- [X] T008 [US1] Añadir a `src/crediagil/agent/test_hooks.py` los tests del hook de registro (tabla "Hook de registro" de contracts/hooks.md). Helpers: `entrada(herramienta, **tool_input)` arma el diccionario del SDK con `tool_name="mcp__crediagil-core__" + herramienta`, `tool_use_id`, `session_id`, `transcript_path` y `cwd`; el hook se invoca con `await hook(entrada, "t1", {"signal": None})`.
  - Solicitante verificado y vigente (`verificar_identidad` de SOL-0001 con su fecha de la semilla) → `{}`.
  - Sin verificar → `permissionDecision == "deny"` y el motivo empieza por `[IDENTIDAD_NO_VERIFICADA]`.
  - Verificado y luego bloqueado (3 fechas incorrectas) → `deny` `IDENTIDAD_NO_VERIFICADA`.
  - `id_solicitante` inexistente → `deny` `IDENTIDAD_NO_VERIFICADA`.
  - Monto 5.000.001 con identidad vigente → `{}` (el hook no evalúa umbrales).
  - El modelo añade `"identidad_verificada": True` a los argumentos de un solicitante sin verificar → sigue negado.
  - Sin `id_solicitante`, con `None`, un número o un texto vacío → `deny` `ENTRADA_INVALIDA`.
- [X] T009 [US1] Implementar en `src/crediagil/agent/hooks.py`:
  - `decidir_registro(datos: dict, tool_input) -> Decision`: valida `id_solicitante` (str no vacío; si no, `ENTRADA_INVALIDA` con `detalles={"campo": "id_solicitante"}`) y comprueba `identidad_vigente` del solicitante existente (si no, `IDENTIDAD_NO_VERIFICADA` con `{"id_solicitante": ...}`).
  - `crear_hook_registro(almacen, ahora=None, servidor="crediagil-core")`, que devuelve el callback asíncrono `(input_data, tool_use_id, context)`.
    - Si `input_data["tool_name"]` no es `mcp__<servidor>__registrar_solicitud`, devuelve `PERMITIR`.
    - En otro caso lee con `almacen.leer_existente()` y devuelve `PERMITIR` o `salida_deny(decision)`.
  - Reutilizar `crediagil.mcp_server.identidad.identidad_vigente`.

  Hacer pasar T008.

**Checkpoint**: US1 completa e independiente.

---

## Phase 4: User Story 2 - Bloquear la preaprobación que no cumple las reglas (Priority: P1)

**Goal**: hook de `preaprobar_credito` (reglas 1 y 2, más la 3 al recalcular).

**Independent Test**: `uv run pytest src/crediagil/agent/test_hooks.py -k preaprobacion`.

- [X] T010 [US2] Añadir a `src/crediagil/agent/test_hooks.py` los tests del hook de preaprobación (tabla "Hook de preaprobación" de contracts/hooks.md). Helper `solicitud(almacen, salario, monto, plazo, declarado, documentos=None)` que verifica la identidad, llama a `registrar_solicitud` y devuelve el `id_solicitud`.
  - Bordes con 5.000.000 a 12 meses:
    - salario 1.556.700 (cuota en el 30% exacto y monto en el tope) → `{}`;
    - 1.556.699 → `deny` `NO_PREAPROBABLE` con una causa `regla_2` en `detalles["causas"]`;
    - 1.556.701 → `{}`;
    - monto 5.000.001 (salario 10.000.000) → `deny` `NO_PREAPROBABLE`, causa `regla_2`.
  - Regla 3 con 4.000.000 a 24 meses y salario 2.000.000: declarado 2.200.000 y 1.800.000 → `{}`; 2.200.001 y 1.799.999 → `deny` `NO_PREAPROBABLE`, causa `regla_3`.
  - Hallazgos (nómina 2.200.001, certificado en USD) → `deny` `HALLAZGOS_DOCUMENTALES`, con `detalles["hallazgos"]` no vacío.
  - **No usa la evaluación guardada**: tras editar la evaluación de una solicitud no preaprobable para marcarla preaprobable → sigue `deny`.
  - Solicitante bloqueado después de registrar → `deny` `IDENTIDAD_NO_VERIFICADA`.
  - Solicitud inexistente → `deny` `SOLICITUD_NO_ENCONTRADA`; solicitud con estado `ESCALADA` → `deny` `SOLICITUD_ESCALADA`.
  - Solicitud ya `PREAPROBADA`: con todo vigente → `{}`; con el solicitante bloqueado después → `deny` `IDENTIDAD_NO_VERIFICADA`.
  - `tool_input` con un campo adicional (`{"id_solicitud": ..., "forzar": True}`), sin `id_solicitud` o con un número → `deny` `ENTRADA_INVALIDA`.
- [X] T011 [US2] Implementar en `src/crediagil/agent/hooks.py`:
  - `decidir_preaprobacion(datos: dict, tool_input) -> Decision` con el orden de data-model.md: entrada exactamente `{"id_solicitud": str no vacío}`, solicitud existe, no `ESCALADA`, `identidad_vigente`, sin `hallazgos`, y al final `evaluar_solicitud_guardada(solicitud)` (si no es `PREAPROBABLE`, `NO_PREAPROBABLE` con `causas` tomadas de los `Motivo`). Los `detalles` llevan `id_solicitud`.
  - `crear_hook_preaprobacion(almacen, ahora=None, servidor="crediagil-core")`.
  - Extraer de T009 la parte común (comprobar el nombre, leer el estado y formatear la salida) a una función interna `_crear_hook(nombre_herramienta, decidir, almacen, servidor)`, que usan ambas fábricas.

  Hacer pasar T010; los tests de T008 deben seguir en verde.

**Checkpoint**: US1 y US2 completas.

---

## Phase 5: User Story 3 - Fallar cerrado (Priority: P1)

**Goal**: ninguna duda deja pasar la llamada.

**Independent Test**: `uv run pytest src/crediagil/agent/test_hooks.py -k "cerrado or fail"`.

- [X] T012 [US3] Añadir a `src/crediagil/agent/test_hooks.py` los tests de fail-closed, parametrizados con los dos hooks:
  - **Estado ausente**: el archivo no existe → `deny` `ESTADO_ILEGIBLE` y el archivo **no se crea**.
  - **Estado corrupto** (`"{no json"`) → `deny` `ESTADO_ILEGIBLE` y el archivo queda intacto.
  - **Lock ocupado**: con otro `FileLock` sosteniendo el lock y `timeout_lectura=0.2` → `deny` `ESTADO_ILEGIBLE`.
  - **`tool_input` que no es un diccionario** (`None`, una lista, un texto) → `deny` `ENTRADA_INVALIDA`.
  - **Error inesperado**: con `decidir_*` sustituido por una función que lanza `RuntimeError("secreto interno")`, el resultado es `deny` `ERROR_INTERNO` y el motivo no contiene "secreto".
  - **Herramienta ajena** (`mcp__crediagil-core__buscar_solicitante`, `Bash` o `mcp__otro__registrar_solicitud`) → `{}` y sin leer el estado (comprobable con un estado ausente: sigue sin crearse).
  - **Solo lectura**: el contenido del archivo de estado es idéntico, byte a byte, antes y después de una llamada permitida y de una negada.
- [X] T013 [US3] Implementar el fail-closed en `_crear_hook` de `src/crediagil/agent/hooks.py`:
  - Parámetro `timeout_lectura: float = 5.0`, pasado a `leer_existente`.
  - Si `tool_input` no es un `dict`, `ENTRADA_INVALIDA`.
  - Un `ErrorCore` al leer, `ESTADO_ILEGIBLE`.
  - Cualquier otra excepción: se registra con `logging.exception` y se devuelve `ERROR_INTERNO`, con `# noqa: BLE001` y el motivo, igual que en `server.py`.
  - Añadir `timeout_lectura` a las dos fábricas.

  Hacer pasar T012.

**Checkpoint**: US1–US3 completas; la garantía no se abre ante ninguna falla.

---

## Phase 6: User Story 4 - Motivo para el modelo y la interfaz, y configuración lista para el agente (Priority: P2)

**Goal**: cada negación queda registrada y la configuración se entrega en el formato del SDK (FR-009, FR-012).

**Independent Test**: `uv run pytest src/crediagil/agent -q`.

- [X] T014 [US4] Añadir a `src/crediagil/agent/test_hooks.py` los tests de registro y configuración.
  - **Registro** (con `ahora` fijo `2026-10-17T15:30:00+00:00`):
    - una negación del hook de preaprobación deja exactamente una `Negacion` con `herramienta == "preaprobar_credito"` (sin prefijo), el código, el mensaje, la acción, los `detalles` y el momento; el motivo devuelto al modelo empieza por `[CODIGO]`;
    - una llamada permitida no deja nada en el registro;
    - el hook de registro y el de preaprobación comparten el mismo registro;
    - `al_negar` se llama una vez por negación;
    - si `al_negar` lanza una excepción, la negación se mantiene (`deny`);
    - con el solicitante bloqueado, ni el motivo ni los `detalles` del registro contienen su fecha de nacimiento.
  - **Configuración**:
    - `crear_hooks(almacen, registro)` devuelve `{"PreToolUse": [...]}` con dos `HookMatcher` cuyos `matcher` son exactamente `mcp__crediagil-core__registrar_solicitud` y `mcp__crediagil-core__preaprobar_credito`, con `timeout == 10`;
    - con `servidor="otro"` los nombres cambian;
    - `ClaudeAgentOptions(hooks=crear_hooks(...))` se construye sin error;
    - un hook obtenido de `crear_hooks`, invocado con la entrada del SDK, niega una preaprobación sin identidad.
- [X] T015 [US4] Implementar en `src/crediagil/agent/hooks.py`:
  - El parámetro `registro: RegistroNegaciones | None = None` en `_crear_hook` y en las dos fábricas: cada `deny` crea una `Negacion` (herramienta sin prefijo, `momento` con `ahora` o la hora UTC actual) y la anota con `registro.registrar`. Con `registro=None` no se anota nada.
  - `crear_hooks(almacen, registro=None, servidor="crediagil-core", ahora=None, timeout_lectura=5.0) -> dict[str, list[HookMatcher]]`, con un `HookMatcher(matcher=<nombre completo>, hooks=[cb], timeout=10)` por herramienta.
  - Actualizar la sección API de `specs/006-sdk-rule-hooks/contracts/hooks.md` con las firmas finales (`servidor`, `ahora`, `timeout_lectura`).

  Hacer pasar T014.

**Checkpoint**: las cuatro historias completas.

---

## Phase 7: Polish & Cross-Cutting

- [X] T016 [P] Actualizar `CLAUDE.md`, sección "Stack y comandos".
  - `crediagil.agent`: los hooks `PreToolUse` de las reglas 1 y 2 y `crear_hooks(...)`, que se pasa a `ClaudeAgentOptions(hooks=...)`.
  - Son fail-closed y de solo lectura.
  - `claude-agent-sdk` es dependencia.
  - No repetir tasa ni umbrales.
- [X] T017 Ejecutar `uv run pytest`, `uv run ruff check` y `uv run ruff format --check`; todo en verde.
- [X] T018 Ejecutar las comprobaciones 1–5 de quickstart.md con un script sobre `$TEMP`: hook con solicitud inexistente, solicitud preaprobable → `{}`, solicitante bloqueado → `deny`, estado borrado → `ESTADO_ILEGIBLE` sin recrearlo, y `ClaudeAgentOptions` con los dos matchers. Borrar los temporales.

---

## Dependencies & Execution Order

```text
Setup (T001–T002) → Foundational (T003–T007)
                         └─▶ US1 (T008–T009) 🎯 MVP
                                └─▶ US2 (T010–T011)
                                       └─▶ US3 (T012–T013)
                                              └─▶ US4 (T014–T015)
                                                     └─▶ Polish (T016–T018)
```

- T003 → T005 (ambas tocan `test_originacion.py`); T004 y T006 son independientes de ellas.
- T007 no depende de T003–T006 (solo de T002).
- US1 necesita T004 (`leer_existente`) y T007; US2 necesita además T005 (`evaluar_solicitud_guardada`).
- US1–US4 comparten `hooks.py` y `test_hooks.py`: van en secuencia.
- La clave de la API no interviene en ninguna tarea.

## Parallel Opportunities

- T003 ∥ T004 ∥ T006 ∥ T007; T005 va después de T003.
- T016 ∥ T017 (T018 al final).

## Implementation Strategy

1. **Foundational**: lectura sin escritura, evaluación compartida, registro de negaciones y piezas comunes.
2. **MVP (US1)**: el hook de la regla 1, que ya bloquea el registro sin identidad.
3. **US2**: el hook de preaprobación, con las reglas recalculadas.
4. **US3**: fail-closed, que convierte las comprobaciones en una garantía.
5. **US4**: registro para la interfaz y la configuración lista para el agente (#7).
6. **Polish**: documentación, suite completa y quickstart.
