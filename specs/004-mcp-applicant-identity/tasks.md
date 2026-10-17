# Tasks: Servidor MCP: identificación del solicitante

**Input**: Design documents from `specs/004-mcp-applicant-identity/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/tools.md](./contracts/tools.md), [quickstart.md](./quickstart.md)

**Tests**: obligatorios (spec FR-018, constitución Principio VII). Van junto al código en
`src/crediagil/mcp_server/test_*.py`, se escriben primero y deben fallar. Usan `tmp_path` como
ruta de estado y nunca `.data/`. Los documentos se importan de `semilla.py`, sin repetir
literales. Una línea con forma "documento + número" lleva `# pragma: dato-ficticio`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: paralelizable (archivo distinto, sin dependencias pendientes)
- **[Story]**: historia de spec.md (US1–US4)

---

## Phase 1: Setup

- [X] T001 En `pyproject.toml`, añadir `"mcp>=2.3,<3"` y `"filelock"` a `dependencies`. En `.gitignore`, añadir `.data/`. Ejecutar `uv sync --group dev` y comprobar `uv run python -c "from mcp.server import MCPServer; import filelock"`.
- [X] T002 Crear `src/crediagil/mcp_server/__init__.py` con el docstring "Core de originación simulado como servidor MCP (datos ficticios)."

---

## Phase 2: Foundational (bloquea US1–US4)

**Purpose**: contrato de errores, almacén de estado y semilla, que usan todas las historias.

### Tests (primero)

- [X] T003 [P] Escribir `src/crediagil/mcp_server/test_errores.py`:
  - `TipoError` tiene exactamente `transitorio`, `validacion`, `negocio` y `permisos`.
  - `ErrorCore(TipoError.X, "CODIGO", "mensaje")` tiene `reintentable` en `True` solo para `transitorio`.
  - `exito(coincidencias=[])` devuelve `{"ok": True, "coincidencias": []}`.
  - `fallo(err)` devuelve `{"ok": False, "error": {...}}` con exactamente las claves `tipo`, `codigo`, `mensaje`, `reintentable` y `detalles`. `detalles` es `{}` si no se pasa.
  - `tipo` se serializa como texto.
- [X] T004 [P] Escribir `src/crediagil/mcp_server/test_estado.py`:
  - **Creación y persistencia:**
    - Si el archivo no existe, `AlmacenEstado(ruta).leer()` lo crea con la semilla: `version == 1` y los 4 solicitantes, con `intentos_fallidos == 0` y `bloqueado is False`.
    - Crea los directorios intermedios.
    - Lo escrito en una `transaccion()` persiste al reabrir con otra instancia.
  - **Escritura atómica:** si dentro de `transaccion()` se lanza una excepción, el archivo queda igual que antes y no quedan temporales.
  - **Archivo corrupto:** si contiene `"{no json"`, `leer()` lanza `ErrorCore` `transitorio`/`ESTADO_ILEGIBLE` y el contenido del archivo no cambia.
  - **Concurrencia:** dos procesos (`multiprocessing`, contexto `spawn`) incrementan 50 veces cada uno un contador dentro de `transaccion()` y el resultado final es 100.
  - **Ruta por defecto:** sin `CREDIAGIL_MCP_ESTADO` es `./.data/core_estado.json`; con la variable, se usa su valor.

### Implementación

- [X] T005 [P] Implementar `src/crediagil/mcp_server/errores.py`:
  - `TipoError(StrEnum)`.
  - `ErrorCore(Exception)` con `tipo`, `codigo`, `mensaje`, `detalles: dict` y la propiedad `reintentable` (`tipo is TRANSITORIO`).
  - `exito(**datos) -> dict` y `fallo(error) -> dict`.

  Hacer pasar T003.
- [X] T006 [P] Crear `src/crediagil/mcp_server/semilla.py` con `SOLICITANTES_SEMILLA`, 4 dicts ficticios con `id_solicitante` (`SOL-0001`…`SOL-0004`), `documento` (`TEST-` + 6 dígitos), `nombre` y `fecha_nacimiento` (`AAAA-MM-DD`):
  - Dos nombres contienen "Prueba" (p. ej. "Ana Prueba Ficticia", "Luis Prueba Inventado").
  - Uno contiene "Pérez" con tilde.
  - Cada línea con `documento` lleva `# pragma: dato-ficticio`.
  - Docstring: "Datos 100% ficticios para el core simulado."
- [X] T007 Implementar `src/crediagil/mcp_server/estado.py`:
  - `ruta_por_defecto()` lee `CREDIAGIL_MCP_ESTADO` o devuelve `Path.cwd() / ".data" / "core_estado.json"`.
  - `AlmacenEstado(ruta)`:
    - `_lock = FileLock(str(ruta) + ".lock")`.
    - `leer() -> dict`: con el lock; crea el archivo desde la semilla si no existe.
    - `transaccion()`: context manager que con el lock lee, entrega el dict y, si no hubo excepción, escribe con `tempfile.NamedTemporaryFile(dir=ruta.parent, delete=False)` + `os.replace`.
    - Si el JSON es inválido o el esquema no tiene `solicitantes`: `ErrorCore(TRANSITORIO, "ESTADO_ILEGIBLE", ...)`, sin escribir.
    - Los documentos de la semilla se guardan normalizados.

  Hacer pasar T004.

**Checkpoint**: `uv run pytest src/crediagil/mcp_server -k "errores or estado"` en verde.

---

## Phase 3: User Story 1 - Buscar al solicitante (Priority: P1) 🎯 MVP

**Goal**: `buscar_solicitante` por documento o nombre parcial.

**Independent Test**: `uv run pytest src/crediagil/mcp_server/test_identidad.py -k buscar`.

- [X] T008 [US1] Escribir los tests de búsqueda en `src/crediagil/mcp_server/test_identidad.py` (tabla de `buscar_solicitante` en contracts/tools.md), importando la semilla:
  - documento exacto → 1 coincidencia con `id_solicitante`, `documento`, `nombre`, `bloqueado`;
  - documento en minúsculas o con espacios → 1;
  - `nombre="prueba"` → ≥ 2;
  - `"perez"` → encuentra "Pérez";
  - sin resultados → `[]`;
  - ninguno, ambos, `"ab"` o `"  ab "` → `ErrorCore` `validacion`/`PARAMETROS_INVALIDOS`;
  - ninguna coincidencia tiene la clave `fecha_nacimiento`.
- [X] T009 [US1] Implementar en `src/crediagil/mcp_server/identidad.py`:
  - `normalizar_documento(texto)`: quita espacios y pasa a mayúsculas.
  - `normalizar_nombre(texto)`: aplica NFKD, quita marcas diacríticas y `casefold`.
  - `buscar_solicitante(almacen, documento=None, nombre=None) -> list[dict]`:
    - Exactamente uno de los dos.
    - `nombre.strip()` con ≥ 3 caracteres.
    - Proyecta solo `id_solicitante`, `documento`, `nombre` y `bloqueado`.

  Hacer pasar T008.

---

## Phase 4: User Story 2 - Verificar la identidad con bloqueo por intentos (Priority: P1)

**Goal**: `verificar_identidad` con 3 intentos y bloqueo persistente.

**Independent Test**: `uv run pytest src/crediagil/mcp_server/test_identidad.py -k verificar`.

- [X] T010 [US2] Añadir a `src/crediagil/mcp_server/test_identidad.py` los tests de verificación (tabla de `verificar_identidad` en contracts/tools.md), con `hoy` fijo:
  - **Fecha correcta:**
    - con 0 y con 2 fallos → `{"verificado": True, "id_solicitante": ...}` e intentos de vuelta a 0;
    - con el solicitante bloqueado → `permisos` `SOLICITANTE_BLOQUEADO`.
  - **Fechas incorrectas sucesivas:**
    - la 1.ª da `negocio` `IDENTIDAD_NO_COINCIDE` con `intentos_restantes == 2`;
    - la 2.ª da `intentos_restantes == 1` y **no** bloquea;
    - la 3.ª da `permisos` `SOLICITANTE_BLOQUEADO` y bloquea.
  - **Persistencia:** 2 fallos, nueva instancia de `AlmacenEstado` sobre la misma ruta (reinicio) y 3.er fallo → bloqueado.
  - **Errores sin efecto en el contador:**
    - id inexistente → `negocio` `SOLICITANTE_NO_ENCONTRADO`;
    - `"17/03/1990"`, `"1990-02-30"`, `"1990-01-01T00:00"` y una fecha posterior a `hoy` → `validacion` `FECHA_INVALIDA`, sin cambiar `intentos_fallidos`.
- [X] T011 [US2] Implementar en `src/crediagil/mcp_server/identidad.py`:
  - `MAX_INTENTOS_VERIFICACION = 3`.
  - `verificar_identidad(almacen, id_solicitante, fecha_nacimiento, hoy=None) -> dict`:
    1. Valida la fecha **antes** de abrir la transacción, con `date.fromisoformat` y longitud exacta de 10.
    2. Dentro de `transaccion()`: no existe → `negocio`; bloqueado → `permisos`; fecha correcta → reinicia el contador.
    3. Fecha incorrecta: suma 1 al contador; al llegar al máximo, bloquea.
    4. Las excepciones se lanzan **después** de que la transacción guarde: el contador debe persistir aunque se responda con error. Por eso se decide dentro de la transacción y se lanza fuera.

  Hacer pasar T010.

**Checkpoint**: US1 y US2 completas a nivel de lógica.

---

## Phase 5: User Story 3 - Contrato de errores e inyección de fallas (Priority: P1)

**Goal**: envoltura única de respuesta, servidor MCP en proceso e inyección de fallas.

**Independent Test**: `uv run pytest src/crediagil/mcp_server/test_fallas.py src/crediagil/mcp_server/test_server.py`.

- [X] T012 [P] [US3] Escribir `src/crediagil/mcp_server/test_fallas.py`:
  - sin variables, `InyectorFallas.desde_entorno()` nunca falla;
  - con `CREDIAGIL_MCP_FALLAS_N=2`, `debe_fallar()` da `True, True, False, False`;
  - con `PROB=1` siempre falla y con `PROB=0` nunca;
  - con `PROB=0.5` y `SEMILLA=7`, dos inyectores producen la misma secuencia;
  - valores inválidos (`N=-1`, `N=abc`, `PROB=2`) → `ValueError` con el nombre de la variable.
- [X] T013 [P] [US3] Implementar `src/crediagil/mcp_server/fallas.py`:
  - `InyectorFallas(restantes: int = 0, probabilidad: float = 0.0, semilla: int | None = None)` con `random.Random(semilla)`.
  - `debe_fallar() -> bool`.
  - `desde_entorno()`.
  - `error_inyectado() -> ErrorCore(TRANSITORIO, "SERVICIO_NO_DISPONIBLE", ...)`.

  Hacer pasar T012.
- [X] T014 [US3] Escribir `src/crediagil/mcp_server/test_server.py`, con `pytest.mark.anyio` y `anyio_backend = "asyncio"`:
  - **Creación y forma de respuesta:**
    - `crear_servidor(AlmacenEstado(tmp_path/...), InyectorFallas())`.
    - `await servidor.call_tool("buscar_solicitante", {...})` devuelve contenido estructurado `{"ok": True, "coincidencias": [...]}`.
    - Un error de dominio llega como `{"ok": False, "error": {5 claves}}`, **no** como error del protocolo.
  - **Fallas inyectadas:** con `InyectorFallas(restantes=1)`, la 1.ª llamada da `transitorio`/`SERVICIO_NO_DISPONIBLE`/`reintentable: True` y la 2.ª es normal. Una verificación fallida por inyección no cambia `intentos_fallidos`.
  - **Errores inesperados:** una excepción no prevista (monkeypatch de `identidad.buscar_solicitante` para que lance `RuntimeError("secreto")`) da `transitorio`/`ERROR_INTERNO`, `detalles == {}` y sin "secreto" en la respuesta.
  - **Listado:** `await servidor.list_tools()` contiene ambas herramientas, con descripción en español no vacía y esquema de entrada.
- [X] T015 [US3] Implementar `src/crediagil/mcp_server/server.py`:
  - `crear_servidor(almacen, inyector) -> MCPServer("crediagil-core", instructions=...)`.
  - Las herramientas `buscar_solicitante(documento: str | None = None, nombre: str | None = None) -> dict` y `verificar_identidad(id_solicitante: str, fecha_nacimiento: str) -> dict` llevan las descripciones exactas de contracts/tools.md.
  - Cada una pasa por `_responder(fn)`:
    1. Si `inyector.debe_fallar()`, devuelve `fallo(error_inyectado())`.
    2. Si no, devuelve `exito(...)`.
    3. Captura `ErrorCore` y devuelve `fallo(e)`.
    4. Captura `Exception`: la registra con `logging.exception` hacia stderr y devuelve `fallo(ERROR_INTERNO)`.

  Hacer pasar T014. Comprobar con el test el formato real del resultado de `call_tool` en mcp 2.x (contenido estructurado) y ajustar la extracción en el test.

---

## Phase 6: User Story 4 - Arranque y descubrimiento de herramientas (Priority: P2)

**Goal**: `python -m crediagil.mcp_server.server` por stdio.

**Independent Test**: `uv run pytest src/crediagil/mcp_server/test_server_stdio.py`.

- [X] T016 [US4] Escribir `src/crediagil/mcp_server/test_server_stdio.py` (anyio):
  - Usar `StdioServerParameters(command=sys.executable, args=["-m", "crediagil.mcp_server.server"], env={**os.environ, "CREDIAGIL_MCP_ESTADO": str(tmp_path / "estado.json")})`, con `stdio_client` y `ClientSession`.
  - Ejecutar `initialize()` y `list_tools()` y comprobar que aparecen las 2 herramientas.
  - Llamar a `call_tool("buscar_solicitante", {"nombre": "prueba"})` y comprobar `ok`.
  - Comprobar que el archivo de estado se creó en `tmp_path`.
- [X] T017 [US4] Añadir a `src/crediagil/mcp_server/server.py` la función `main()`:
  - construye `AlmacenEstado(ruta_por_defecto())` e `InyectorFallas.desde_entorno()`;
  - si la configuración de fallas es inválida, escribe el motivo en stderr y sale con código 2;
  - llama a `crear_servidor(...).run()` (stdio).

  Añadir también `if __name__ == "__main__": main()`. Los logs van solo a stderr, porque stdout es el canal MCP. Hacer pasar T016.

---

## Phase 7: Polish & Cross-Cutting

- [X] T018 [P] Actualizar `CLAUDE.md`, sección "Stack y comandos":
  - el servidor del core se ejecuta con `uv run python -m crediagil.mcp_server.server`;
  - el estado está en `.data/` (ignorado) y se reinicia borrando ese archivo;
  - las variables `CREDIAGIL_MCP_ESTADO` y `CREDIAGIL_MCP_FALLAS_*`.
- [X] T019 Ejecutar `uv run pytest`, `uv run ruff check` y `uv run ruff format --check`; todo en verde.
- [X] T020 Ejecutar las comprobaciones 1, 2, 4 y 5 de quickstart.md. La 3, que registra el servidor en un cliente MCP, queda para el usuario. Comprobar que `.data/` no aparece en `git status`.

---

## Dependencies & Execution Order

```text
Setup (T001–T002) → Foundational (T003–T007)
                         ├─▶ US1 (T008–T009)  🎯 MVP
                         ├─▶ US2 (T010–T011)   (mismo archivo que US1: después de US1)
                         └─▶ US3 (T012–T015)   (T014–T015 usan identidad: después de US1+US2)
                                   └─▶ US4 (T016–T017)
                                            └─▶ Polish (T018–T020)
```

- T005 y T006 no dependen entre sí. T007 depende de T005 y T006.
- US1 y US2 comparten `identidad.py` y `test_identidad.py`, así que van en secuencia.
- T012 y T013 (fallas) pueden ir en paralelo con US1 y US2.

## Parallel Opportunities

- T003 ∥ T004; después, T005 ∥ T006.
- Tras Foundational: (T008 → T009 → T010 → T011) ∥ (T012 → T013).
- T018 ∥ T019.

## Implementation Strategy

1. **MVP**: Setup, Foundational y US1. Búsqueda probada a nivel de lógica.
2. **US2**: verificación con bloqueo, la base de la regla 1.
3. **US3**: contrato, envoltura MCP y fallas; las herramientas ya se pueden llamar por MCP en proceso.
4. **US4**: arranque por stdio y descubrimiento por un cliente real.
5. **Polish**: documentación, suite completa y quickstart.
