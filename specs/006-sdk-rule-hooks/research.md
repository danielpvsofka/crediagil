# Research: Hooks del Agent SDK para las reglas 1 y 2

Decisiones de la Fase 0. No quedan `NEEDS CLARIFICATION`. La API del SDK se inspeccionó en un
entorno temporal (`claude-agent-sdk` 0.2.168), sin tocar el proyecto.

## R1. API de hooks del SDK

- **Decision**: usar las piezas públicas de `claude_agent_sdk`:
  - Registro: `ClaudeAgentOptions(hooks={"PreToolUse": [HookMatcher(matcher=..., hooks=[cb], timeout=...)]})`.
  - Callback: `async def cb(input_data, tool_use_id, context) -> dict`. La entrada de `PreToolUse` trae `hook_event_name`, `tool_name`, `tool_input` (dict), `tool_use_id`, `session_id`, `transcript_path` y `cwd`.
  - Negar: devolver `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "<motivo>"}}`. El motivo llega al modelo como resultado de su llamada.
  - Permitir: devolver `{}` (sin opinión). No se devuelve `allow` explícito para no saltarse el flujo de permisos que configure #7.
- **Rationale**: es el contrato que el SDK usa de verdad; los tests invocan el callback con ese mismo diccionario de entrada y comprueban esa salida (FR-013).
- **Alternatives considered**:
  - `can_use_tool` (callback de permisos): decide por herramienta, pero el issue exige hooks `PreToolUse`.
  - Decorar las herramientas del servidor MCP con las mismas comprobaciones: ya existe como segunda barrera en el core (#5); los hooks son la primera, fuera de la herramienta y del prompt (Principio II).

## R2. Nombre de las herramientas

- **Decision**: una herramienta MCP llega al hook como `mcp__<servidor>__<herramienta>`, con
  `<servidor>` la clave usada en `mcp_servers`. `crear_hooks(..., servidor="crediagil-core")` construye los
  nombres completos y registra un `HookMatcher` por herramienta con el nombre exacto; además
  cada callback comprueba `tool_name` y devuelve `{}` si no es el suyo (FR-011).
- **Rationale**: un matcher exacto evita que un hook se aplique a herramientas de nombre
  parecido, y la comprobación interna cubre una configuración equivocada.

## R3. Dónde vive el código

- **Decision**: paquete `crediagil.agent`, que también alojará el orquestador (#7).
  - `negaciones.py`: `Negacion` y `RegistroNegaciones`.
  - `hooks.py`: decisiones puras, callbacks y `crear_hooks`.
  - Tests junto al código.
- **Dependencia**: `claude-agent-sdk>=0.2.168,<0.3` en `pyproject.toml`. Hace falta ya para
  construir `HookMatcher`; #7 la usa para el agente completo.
- **Rationale**: el SDK es 0.x y puede cambiar entre menores; la cota superior evita sorpresas.

## R4. Lectura del estado, solo lectura y fail-closed

- **Decision**: `AlmacenEstado.leer_existente(timeout=5.0)`:
  - Toma el lock con tiempo máximo y lee **sin crear** el archivo.
  - Si no existe, está corrupto o no se obtiene el lock a tiempo, lanza `ErrorCore` `ESTADO_ILEGIBLE`.
  - Migra en memoria de v1 a v2 como `leer()`, sin escribir.
- **Rationale**: `leer()` crea el estado desde la semilla si falta, lo que sería una escritura
  escondida dentro de un hook (FR-010). Un estado ausente en el momento de decidir es un
  fallo, no un permiso. El lock con tiempo máximo evita bloquear el agente indefinidamente.

## R5. Una sola evaluación para tool y hook

- **Decision**: extraer de `preaprobar_credito` (#5) la función pública
  `evaluar_solicitud_guardada(solicitud) -> Resultado`: reconstruye los hallazgos y el ingreso
  de la solicitud guardada y combina regla 2, regla 3 y hallazgos con `crediagil.policy`. La
  usan la herramienta y el hook de preaprobación.
- **Rationale**: ambas barreras no pueden discrepar, y ninguna usa la evaluación guardada
  (FR-006). Es un cambio de refactor con los tests de #5 como red de seguridad.

## R6. Orden de las comprobaciones de preaprobación

- **Decision**: entrada válida → estado legible → solicitud existe → no escalada → identidad
  vigente → sin hallazgos documentales → política (reglas 2 y 3). Se informa la primera
  negación; el hook no acumula motivos.
- **Rationale**: es el orden de "lo más barato y específico primero"; el modelo recibe un único
  motivo accionable. Los hallazgos se comprueban antes que la política porque son más
  específicos (`HALLAZGOS_DOCUMENTALES` indica qué documento falla).
- **Solicitud ya `PREAPROBADA`**: pasa por las mismas comprobaciones. Es más estricta que la
  herramienta (idempotente) a propósito.

## R7. Registro de negaciones para la interfaz

- **Decision**: `RegistroNegaciones` guarda cada `Negacion` en memoria (herramienta, código,
  mensaje, acción, detalles, momento ISO-8601 UTC) y expone `listar()`, `ultima()` y un
  `al_negar` opcional (función a la que avisa en cada negación). Los hooks lo reciben por
  parámetro; #7 lo comparte con la interfaz (#8).
- **Rationale**: simple y suficiente para mostrar "bloqueo por regla de negocio"; persistirlo
  queda como mejora (Assumptions de la spec). Un error dentro de `al_negar` no cambia la
  decisión: se registra en el log y se ignora.

## R8. Entrada y motivo

- **Decision**:
  - Preaprobación: `tool_input` debe ser exactamente `{"id_solicitud": <str no vacío>}`; cualquier otra forma es `ENTRADA_INVALIDA`.
  - Registro: solo se exige `id_solicitante` (`str` no vacío); el resto de argumentos los valida la herramienta.
  - Motivo devuelto al modelo: `"[CODIGO] mensaje Acción: acción."`, en español y sin datos sensibles (nunca la fecha de nacimiento).
- **Rationale**: del modelo solo se toma el identificador (FR-007); lo demás se ignora.

## R9. Tests

- **Decision**:
  - Los tests llaman a los callbacks con el diccionario de entrada del SDK y comprueban la salida del SDK, sin modelo ni red.
  - Un test construye `ClaudeAgentOptions(hooks=crear_hooks(...))` para comprobar que la configuración es aceptada y que los matchers tienen los nombres completos.
  - Los documentos ficticios pasan a `crediagil/mcp_server/documentos_prueba.py` (antes en `conftest.py`) para importarlos desde otros paquetes de tests. Cierra el menor de la revisión de #5.
  - `anyio_backend` en `crediagil/agent/conftest.py`.
- **Prueba con modelo real**: corresponde a #7; este PR no usa la clave de la API.
