# Contrato: agente orquestador

API de `crediagil.agent` y `crediagil.config`. Entidades en [data-model.md](../data-model.md) y
decisiones en [research.md](../research.md).

## API

```python
# crediagil/config.py
class ConfiguracionError(Exception): ...
def cargar_entorno() -> None                    # carga el archivo local sin pisar variables ya definidas
def obtener_api_key() -> str                    # ConfiguracionError si falta ANTHROPIC_API_KEY
def redactar(texto: str) -> str                 # sustituye el valor de la clave por [REDACTADO]

# crediagil/agent/orquestador.py
class Agente:
    def __init__(self, config: ConfigAgente, registro: RegistroNegaciones | None = None,
                 cliente_factory: Callable[[ClaudeAgentOptions], ClienteSDK] = ClaudeSDKClient)
    async def __aenter__(self) -> Agente        # conecta
    async def __aexit__(self, *excepcion) -> None
    async def turno(self, mensaje: str, documentos: Sequence[DocumentoAdjunto] = ()) -> ResultadoTurno

# crediagil/agent/parada.py
def clasificar_parada(resultado: ResultMessage) -> Parada

# crediagil/agent/opciones.py
def construir_opciones(config, registro, canal, documentos, almacen) -> ClaudeAgentOptions

# crediagil/agent/delegacion.py
def crear_hook_delegacion(documentos: Mapping[str, DocumentoAdjunto]) -> HookCallback

# crediagil/agent/canal.py
def crear_canal() -> tuple[McpSdkServerConfig, list[PedidoInformacion]]
```

## `clasificar_parada`

Entrada: un `ResultMessage` real del SDK. Cada fila es un test.

| `stop_reason` | `terminal_reason` | `is_error` | Resultado |
|---------------|-------------------|------------|-----------|
| `end_turn` | `completed` | no | `FIN_DE_TURNO` |
| `stop_sequence` | `completed` | no | `FIN_DE_TURNO` |
| `max_tokens` | — | no | `TRUNCADA` |
| `model_context_window_exceeded` | — | no | `TRUNCADA` |
| `refusal` | — | no | `RECHAZO` |
| cualquiera | `max_turns` | no | `TOPE` |
| cualquiera | — | sí | `ERROR_API` |
| `tool_use` o `pause_turn` | — | no | `DESCONOCIDA` (como razón **final**) |
| `None` o texto nuevo | — | no | `DESCONOCIDA` |

Prioridad: `ERROR_API` > `TOPE` > el resto. Ninguna fila depende del texto de la respuesta.

## `Agente.turno`

| Caso | Resultado |
|------|-----------|
| Mensaje con razón de parada de fin de turno | `ResultadoTurno` con `parada == FIN_DE_TURNO`, `respuesta` no vacía |
| Razón de parada `TRUNCADA` | se envía `"Continúa."` hasta `max_continuaciones`; si persiste, se escala por incidente y se informa |
| `RECHAZO`, `TOPE` o `DESCONOCIDA` | se escala **por código** con `escalar_a_analista` del core (causa `otro`, detalle con la razón y `solicitante` = `"sin identificar"` si no se conoce) y se devuelve el aviso `escalamiento` |
| `ERROR_API` | `ResultadoTurno` con `error` claro y redactado; sin trazas internas |
| Adjuntos | se asignan `documento_id` (`DOC-1`, …) y se incluyen en el mensaje como `<documento id="DOC-1" nombre="…">texto</documento>`; un adjunto sin texto no se incluye y se avisa para pedirlo |
| Varios turnos | el mismo cliente conserva el contexto; los `documento_id` siguen contando |
| La clave | nunca aparece en `respuesta`, `traza`, `error` ni logs |

### Avisos y traza

| Resultado de herramienta | Aviso |
|--------------------------|-------|
| `preaprobar_credito` con `ok: true` | `credito_preaprobado` |
| `solicitar_informacion` | `informacion_solicitada` |
| `escalar_a_analista` con `ok: true` | `escalamiento` |
| negación nueva del registro de #6 | `bloqueo_regla` |

Una preaprobación nunca se avisa por el texto del modelo: sin `preaprobar_credito` con `ok: true`
en la traza, no hay aviso (FR-011).

## `construir_opciones` (aislamiento)

| Campo | Valor esperado |
|-------|----------------|
| `setting_sources` | `[]` (no `None`) |
| `tools` | `["Agent"]` |
| `allowed_tools` | las 7 del core con prefijo, `mcp__canal__solicitar_informacion` y `Agent` |
| `disallowed_tools` | `Bash`, `Read`, `Write`, `Edit`, `WebFetch`, `WebSearch` |
| `permission_mode` | `dontAsk` |
| `strict_mcp_config` | `True` |
| `mcp_servers` | `{servidor: stdio del core con la ruta de estado, "canal": en proceso}` |
| `agents` | `{"extractor-documentos": AgentDefinition(tools=[validar_extraccion], model=extractor)}` |
| `hooks["PreToolUse"]` | los 2 de #6 y el de delegación sobre `Agent` |
| `system_prompt` | el prompt del orquestador (texto) |
| `cwd` | directorio temporal vacío |
| `max_turns` | `config.max_turnos` |

Contrato con el SDK: el comando que construye el transporte para estas opciones contiene
`--setting-sources=` (vacío) y `--tools Agent`.

## Hook de delegación (`PreToolUse` sobre `Agent`)

Con documentos adjuntos conocidos `DOC-1` ("certificado.txt", texto T):

| Entrada (`tool_input`) | Salida |
|------------------------|--------|
| `subagent_type="extractor-documentos"`, prompt con `DOC-1`, `certificado.txt` y T completo | `{}` |
| `subagent_type="general-purpose"` | `deny` `SUBAGENTE_NO_PERMITIDO` |
| prompt sin ningún `documento_id` conocido | `deny` `DOCUMENTO_DESCONOCIDO` |
| prompt con `DOC-1` y el nombre pero con un resumen del texto | `deny` `DELEGACION_INCOMPLETA` |
| prompt con `DOC-1` y el texto pero sin el nombre | `deny` `DELEGACION_INCOMPLETA` |
| `tool_input` que no es un diccionario o sin `prompt` | `deny` `ENTRADA_INVALIDA` |
| `tool_name` distinto de `Agent` | `{}` |

## `solicitar_informacion`

| Entrada | Resultado |
|---------|-----------|
| `datos=["salario mensual"]`, `motivo="El certificado no lo indica"` | confirmación y un `PedidoInformacion` en el colector |
| `datos=[]` o con textos vacíos, `motivo` vacío | error de herramienta; nada en el colector |
| El estado del core | no cambia |

## Prompts

- `orquestador.md` y `extractor.md`: en español, no vacíos y versionados.
- Ninguno contiene la tasa ni los umbrales de `crediagil.policy.params` (en ningún formato
  de pesos, porcentaje o coma decimal).
- Orden de comprobaciones del test: el prompt del orquestador menciona, como guía, buscar,
  verificar, extraer, registrar, preaprobar o escalar, simular y pedir información.
