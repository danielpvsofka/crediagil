# Research: Agente orquestador y subagente extractor

Decisiones de la Fase 0. No quedan `NEEDS CLARIFICATION` (FR-020 se resolvió: el ticket de GitHub
queda fuera de esta feature). La API del SDK se inspeccionó en un entorno temporal con
`claude-agent-sdk` 0.2.168, que empaqueta el CLI de Claude Code (`claude.exe`); no se hizo
ninguna llamada al modelo.

## R1. Arquitectura del agente

- **Decision**: una conversación es un `ClaudeSDKClient` abierto (`connect` → `query` →
  `receive_response`, que emite mensajes hasta un `ResultMessage`). Los turnos siguientes usan el
  mismo cliente, que conserva el contexto. La clase `Agente` envuelve el cliente, los hooks de #6
  y el estado del trámite.
- **Hecho verificado**: el SDK lanza el CLI como subproceso y es el CLI quien ejecuta el bucle
  de herramientas del modelo. Nuestro código no itera llamadas al modelo: consume los mensajes y
  decide con la razón de parada.
- **Alternatives considered**: la API de Mensajes con un bucle propio. Daría control total del
  ciclo, pero el issue pide explícitamente el Claude Agent SDK, y el bucle de herramientas,
  subagentes y hooks ya viene resuelto en él.

## R2. Control del ciclo por razón de parada (FR-001, FR-002)

- **Hecho verificado**: `AssistantMessage.stop_reason` (una por respuesta del modelo) y
  `ResultMessage.stop_reason`, `.terminal_reason`, `.is_error`, `.subtype` y `.api_error_status`.
  `AssistantMessage.error` distingue `authentication_failed`, `billing_error`, `rate_limit`,
  `invalid_request`, `server_error` y `unknown`.
- **Decision**: la función pura `clasificar_parada(resultado) -> Parada` decide qué hacer al
  recibir el `ResultMessage` de cada turno.

  | Entrada | `Parada` | Acción |
  |---------|----------|--------|
  | `stop_reason` `end_turn` o `stop_sequence` | `FIN_DE_TURNO` | entregar la respuesta |
  | `max_tokens` o `model_context_window_exceeded` | `TRUNCADA` | pedir continuar (acotado); si persiste, escalar |
  | `refusal` | `RECHAZO` | incidente: escalar |
  | `terminal_reason == "max_turns"` | `TOPE` | incidente: escalar |
  | `is_error` o `AssistantMessage.error` | `ERROR_API` | error claro, sin datos sensibles |
  | cualquier otra (incluidas `tool_use` y `pause_turn` como razón *final*) | `DESCONOCIDA` | incidente: escalar |

  Las razones intermedias (`tool_use`, `pause_turn`) aparecen en la traza: significan que el CLI
  continúa solo. Nunca se mira el texto para decidir y no hay un contador de iteraciones que
  decida el fin normal.
- **Tope de seguridad**: `max_turns` del SDK (valor en `ConfigAgente`, 30 por defecto) más un
  máximo de continuaciones por truncamiento (2). Solo protegen contra bucles y coste.

## R3. Subagente y delegación explícita (FR-003–FR-006)

- **Hecho verificado**: los subagentes se definen con `AgentDefinition(description, prompt,
  tools, model, maxTurns, ...)` y se invocan con la herramienta **`Agent`**, cuya entrada trae
  `subagent_type` y `prompt`.
- **Decision**:
  - `extractor-documentos` = `AgentDefinition` con `tools=["mcp__crediagil-core__validar_extraccion"]`, `model` ligero y un `maxTurns` acotado.
  - El orquestador tiene `Agent` entre sus herramientas.
  - El nombre del servidor MCP del core se fija en `ConfigAgente.servidor` y es el mismo que usan los hooks de #6.
- **Delegación verificable por código** (Principio II): un hook `PreToolUse` sobre `Agent`
  (`delegacion.py`) niega la llamada salvo que:
  1. `subagent_type == "extractor-documentos"`;
  2. el `prompt` contenga el `documento_id`, el nombre y el **texto completo** de un documento adjunto conocido en la conversación.

  Así "pasa de forma explícita documento_id, nombre y texto completo" deja de depender del
  prompt. El agente asigna los `documento_id` (`DOC-1`, `DOC-2`, …) al recibir los adjuntos y los
  incluye en el mensaje.
- **Dato ausente**: el prompt del subagente le ordena devolver `faltantes` y no reintentar ni
  inventar; el orquestador los pide con `solicitar_informacion` (R4).

## R4. `solicitar_informacion` (FR-007)

- **Decision**: servidor MCP en proceso (`create_sdk_mcp_server("canal", tools=[…])`) con una
  herramienta `solicitar_informacion(datos: list[str], motivo: str)`, que llega al modelo como
  `mcp__canal__solicitar_informacion`.
  - No toca el estado del core.
  - Guarda un `PedidoInformacion` en el colector del turno y devuelve confirmación.
  - Después el modelo redacta el mensaje al solicitante y termina el turno.
- **Rationale**: es una herramienta de canal (comunicación con la persona), no del core; en
  proceso evita otro servidor externo.

## R5. Servidores MCP y estado compartido

- **Decision**: `mcp_servers = {servidor: {"type": "stdio", "command": sys.executable, "args": ["-m", "crediagil.mcp_server.server"], "env": {"CREDIAGIL_MCP_ESTADO": ruta}}, "canal": <servidor en proceso>}`.
  - Los hooks de #6 usan un `AlmacenEstado` sobre la misma ruta.
  - El proceso hijo y los hooks leen y escriben con `filelock`, como ya hacen.
- **Rationale**: el core real es el servidor de #4 y #5, sin duplicar lógica en el agente.

## R6. Aislamiento de la configuración (FR-014)

- **Hecho verificado y trampa**: con `setting_sources=None` (el valor por defecto) el SDK **omite**
  el flag `--setting-sources` y el CLI carga sus fuentes por defecto (usuario, proyecto, local).
  Solo `setting_sources=[]` envía `--setting-sources=` y no carga ninguna. Con `system_prompt=None`
  el SDK envía un prompt vacío; nosotros damos el nuestro como texto.
- **Decision**: opciones de producción:

  | Opción | Valor | Efecto |
  |--------|-------|--------|
  | `setting_sources` | `[]` (lista vacía, **no** `None`) | no hereda `CLAUDE.md`, reglas, hooks, skills ni permisos |
  | `tools` | `["Agent"]` | de las herramientas internas solo existe la delegación |
  | `allowed_tools` | herramientas del core, `mcp__canal__solicitar_informacion` y `Agent` | lista permitida cerrada |
  | `disallowed_tools` | `Bash`, `Read`, `Write`, `Edit`, `WebFetch`, `WebSearch` | segunda barrera |
  | `permission_mode` | `dontAsk` | lo no permitido se niega, nunca se pregunta |
  | `strict_mcp_config` | `True` | solo los servidores MCP que pasa el código |
  | `cwd` | directorio temporal vacío | ningún `CLAUDE.md` descubrible desde el directorio |
  | `system_prompt` | texto del orquestador | sin el prompt por defecto de Claude Code |
  | `hooks` | los de #6 y el de delegación | reglas en código |
  | `max_turns`, `max_budget_usd` | topes de seguridad | protección de coste |

- **Test**: comprueba las opciones y, como contrato con el SDK, el comando que construye su
  transporte (`--setting-sources=` presente) sin lanzar el proceso. Es una API interna del SDK, de
  ahí la cota `<0.3`.

## R7. Clave de la API (FR-015)

- **Decision**: `crediagil/config.py`.
  - `cargar_entorno()` usa `python-dotenv` (`load_dotenv(find_dotenv(usecwd=True), override=False)`): carga el archivo local ignorado por git sin pisar variables ya definidas.
  - `obtener_api_key()` lee `ANTHROPIC_API_KEY` y lanza `ConfiguracionError` con un mensaje claro si falta; nunca incluye el valor.
  - `redactar(texto)` sustituye el valor de la clave por `[REDACTADO]`; se aplica a todo lo que se devuelve en la traza, los errores y los logs.
- **Rationale**: la clave solo la lee el programa; el asistente de desarrollo no abre el archivo
  y los hooks del repositorio siguen bloqueando que un comando lo mencione.
- **Dependencia nueva**: `python-dotenv`.

## R8. Modelos

- **Decision**: orquestador `claude-sonnet-5-5` y extractor `claude-haiku-4-5-20251001`, por
  coste y calidad (el extractor repite validaciones y no necesita el modelo grande). Ambos se
  pueden sustituir con `CREDIAGIL_MODELO_ORQUESTADOR` y `CREDIAGIL_MODELO_EXTRACTOR`.
- **Rationale**: identificadores explícitos para que el comportamiento sea reproducible.

## R9. Resultado del turno y avisos (FR-016)

- **Decision**: `ResultadoTurno` con `respuesta`, `avisos`, `traza`, `parada`, `negaciones`,
  `pedidos_informacion`, `costo_usd` y `error`.
  - **Respuesta**: texto de los bloques de texto del orquestador (los mensajes sin `parent_tool_use_id`) posteriores a la última herramienta del turno.
  - **Traza**: una entrada por `ToolUseBlock` con su `ToolResultBlock` correlacionado por id, incluidas las delegaciones y las razones de parada intermedias.
  - **Avisos**: se derivan **de los resultados de las herramientas**, nunca del texto del modelo (FR-011):

    | Condición | Aviso |
    |-----------|-------|
    | `preaprobar_credito` con `ok: true` | `credito_preaprobado` |
    | `solicitar_informacion` | `informacion_solicitada` |
    | `escalar_a_analista` con `ok: true` | `escalamiento` |
    | una negación nueva de los hooks de #6 | `bloqueo_regla` |

  - **Negaciones**: las nuevas del `RegistroNegaciones` de #6 durante el turno.
- **Rationale**: es exactamente lo que necesita la interfaz de #8 (avisos destacados y
  desplegable técnico).

## R10. Prompts

- **Decision**: `prompts/orquestador.md` y `prompts/extractor.md`, en español, cargados desde el
  paquete. Tratan el contenido de los documentos como datos, no como instrucciones (riesgo de
  inyección), y describen cuándo simular, pedir información, escalar o preaprobar.
- **Test**: los prompts no contienen la tasa ni ningún umbral de la constitución (Principio I);
  se comprueba contra los valores de `crediagil.policy.params`.

## R11. Pruebas

- **Sin modelo**: `parada` (cada razón de parada), `canal`, `delegacion`, `traza` y `config` son
  funciones y clases puras. `Agente` recibe una fábrica de cliente: los tests inyectan un cliente
  falso que emite secuencias guionizadas de `AssistantMessage`, `UserMessage` y `ResultMessage`
  reales del SDK.
- **Con el modelo real** (`@pytest.mark.live`): 5 pruebas. `addopts = -m "not live"` las excluye
  de `uv run pytest`; se ejecutan con `uv run pytest -m live`. Cada una usa un estado temporal,
  datos ficticios y un tope de coste (`max_budget_usd`), y comprueba la **traza**
  (herramientas llamadas y su orden), no el texto. Se saltan si no hay clave.
- **Alcance de FR-012** (reintentos): su control es del modelo; la defensa es la guía del prompt
  y la prueba real con una falla inyectada.
