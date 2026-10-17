# Research: Servidor MCP: identificación del solicitante

Decisiones de la Fase 0. No quedan `NEEDS CLARIFICATION`.

## R1. SDK de MCP

- **Decision**: usar el SDK oficial `mcp` en la versión 2.x (`mcp>=2.3,<3`).
  - Servidor: `from mcp.server import MCPServer`. Las herramientas se registran con `@servidor.tool(name=..., description=...)` y se arranca con `servidor.run()` (stdio por defecto).
  - Tests en proceso: `await servidor.list_tools()` y `await servidor.call_tool(nombre, args)`.
  - Test de extremo a extremo: `mcp.client.stdio.stdio_client` + `ClientSession`, lanzando `python -m crediagil.mcp_server.server` como subproceso.
- **Verificación**: API inspeccionada en un entorno temporal. La v2 renombró `FastMCP` a `MCPServer` (`mcp.server.fastmcp` ya no existe).
- **Alternatives considered**:
  - Fijar `mcp<2` para usar `FastMCP`: se descarta para no nacer sobre una API obsoleta.
  - Implementar JSON-RPC a mano: se descarta porque el issue exige el protocolo MCP.

## R2. Forma de la respuesta

- **Decision**: cada herramienta devuelve un `dict` con el contrato del issue: `{"ok": True, ...}` o `{"ok": False, "error": {...}}`.
  - Los errores de dominio **no** se elevan como errores MCP (`isError`). Van en el contenido, para que el agente lea `tipo` y `reintentable`.
  - La lógica lanza `ErrorCore(tipo, codigo, mensaje, detalles)`, y una envoltura común en `server.py` la convierte en respuesta.
  - Cualquier otra excepción se convierte en `transitorio` / `ERROR_INTERNO`, sin traza (FR-004); el detalle solo se registra en el log.
- **Rationale**: es un único punto de conversión, así no hay forma de devolver otra estructura (SC-001).

## R3. Estado persistido con lock

- **Decision**: un archivo JSON con este esquema:

  ```text
  {"version": 1, "solicitantes": {id: {...}}}
  ```

  - Se protege con `filelock.FileLock(<archivo>.lock)` (dependencia nueva, multiplataforma; Windows es el entorno actual).
  - Escritura atómica: se escribe a un temporal en el mismo directorio y se aplica `os.replace`.
  - Toda operación que cambia el estado ocurre dentro de `with almacen.transaccion() as datos:`, que bloquea, lee, entrega el dict, escribe y libera. Las lecturas también toman el lock para no leer a medias.
  - Ruta: variable `CREDIAGIL_MCP_ESTADO`, por defecto `./.data/core_estado.json`. `.data/` se añade a `.gitignore`.
  - Si el archivo no existe, se crea con la semilla (FR-014).
  - Si el JSON es ilegible, se devuelve un error `transitorio` / `ESTADO_ILEGIBLE` y no se sobrescribe nada.
- **Alternatives considered**:
  - `fcntl` o `msvcrt` a mano: dos implementaciones distintas y fáciles de equivocar.
  - SQLite: el issue pide un archivo JSON.

## R4. Inyección de fallas (FR-015)

- **Decision**: el `InyectorFallas` se configura por variables de entorno al arrancar:
  - `CREDIAGIL_MCP_FALLAS_N=<n>`: falla las próximas *n* llamadas a herramientas. Es determinista y la opción preferida en tests.
  - `CREDIAGIL_MCP_FALLAS_PROB=<0..1>` con `CREDIAGIL_MCP_FALLAS_SEMILLA=<int>`: falla con esa probabilidad, con un generador sembrado y reproducible.

  Por defecto está desactivado. Se evalúa **antes** de tocar el estado, así que la falla no lo modifica. Devuelve `transitorio` / `SERVICIO_NO_DISPONIBLE` con `reintentable: true`.
- **Rationale**: el modo N da exactitud para tests y la probabilidad sirve para probar reintentos del agente (#7).

## R5. Búsqueda y verificación

- **Búsqueda por documento**: se normaliza con `strip()`, se quitan los espacios internos, se pasa a mayúsculas y la comparación es exacta.
- **Búsqueda por nombre**: se normaliza con `unicodedata.normalize("NFKD")`, se quitan las marcas diacríticas, se aplica `casefold()` y se busca la subcadena. El texto debe tener ≥ 3 caracteres no blancos tras `strip()`.
- **Identificador**: `SOL-NNNN`, asignado en la semilla y devuelto por la búsqueda.
- **Verificación**:
  1. La fecha se parsea con `date.fromisoformat`, sin aceptar hora. Si es inválida o futura (respecto de `hoy`, inyectable para tests), se devuelve `validacion` y no cuenta como intento.
  2. Si el solicitante no existe: `negocio` / `SOLICITANTE_NO_ENCONTRADO`.
  3. Si está bloqueado: `permisos` / `SOLICITANTE_BLOQUEADO`, sin cambiar el estado.
  4. Si la fecha coincide: `intentos_fallidos = 0` y `{ok, verificado: true, id_solicitante}`.
  5. Si no coincide: `intentos_fallidos += 1`. Con menos de 3, `negocio` / `IDENTIDAD_NO_COINCIDE` con `intentos_restantes = 3 − n`. Al llegar a 3, `bloqueado = true` y `permisos` / `SOLICITANTE_BLOQUEADO`.
- **Límite**: `MAX_INTENTOS_VERIFICACION = 3` vive en `crediagil/mcp_server/identidad.py`. Es un parámetro del core simulado, no de la política de crédito de la constitución.

## R6. Datos semilla y hook de datos sensibles

- **Decision**: la semilla vive en `crediagil/mcp_server/semilla.py` como lista de dicts.
  - Hay 4 solicitantes ficticios. Dos comparten "Prueba" en el nombre, y otro tiene tilde ("Pérez") para probar la normalización.
  - Los documentos son `TEST-` seguido de 6 dígitos.
  - Cada línea con documento lleva `# pragma: dato-ficticio`.
  - Los tests no repiten literales: importan la semilla.
- **Rationale**: `block_sensitive_data` (#1) reconoce "documento" + número; el pragma es el mecanismo previsto para fixtures deliberadamente ficticios.
- **Alternatives considered**: que el hook exima `TEST-`. Requiere cambiar la feature 001; queda como mejora posible.

## R7. Tests

- **Unitarios** junto al código, en `src/crediagil/mcp_server/test_*.py`, con `tmp_path` como ruta de estado:
  - `errores`, `estado` (atomicidad, archivo corrupto, concurrencia con 2 procesos que incrementan un contador bajo lock), `fallas`, `identidad` (bordes 2 y 3 fallos, reinicio, bloqueo con fecha correcta) y `server` (forma de respuesta y `list_tools` en proceso).
- **Extremo a extremo**: `test_server_stdio.py` arranca el servidor por stdio con el SDK cliente y lista las herramientas.
- Async con `pytest.mark.anyio` (plugin de `anyio`, que ya trae `mcp`).
