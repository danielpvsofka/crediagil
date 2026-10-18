# Contrato: hooks `PreToolUse` de las reglas 1 y 2

API pública de `crediagil.agent.hooks` y `crediagil.agent.negaciones`. Códigos, acciones y
flujos en [data-model.md](../data-model.md). Formato de entrada y salida: el del SDK
(`claude_agent_sdk`, ver [research.md](../research.md) R1).

## API

```python
class Negacion: herramienta, codigo, mensaje, accion, detalles, momento      # dataclass
class RegistroNegaciones:
    def __init__(self, al_negar: Callable[[Negacion], None] | None = None)
    def registrar(self, negacion: Negacion) -> None
    def listar(self) -> list[Negacion]          # copia
    def ultima(self) -> Negacion | None

def crear_hook_registro(almacen, registro=None, servidor="crediagil-core", ahora=None, timeout_lectura=5.0) -> HookCallback
def crear_hook_preaprobacion(almacen, registro=None, servidor="crediagil-core", ahora=None, timeout_lectura=5.0) -> HookCallback
def crear_hooks(almacen, registro=None, servidor="crediagil-core", ahora=None, timeout_lectura=5.0) -> dict[str, list[HookMatcher]]
```

`ahora` es un texto ISO-8601 UTC fijo para los tests (por defecto, la hora actual) y `timeout_lectura`
es el tiempo máximo para obtener el lock al leer el estado.

`crear_hooks` devuelve `{"PreToolUse": [HookMatcher(matcher="mcp__<servidor>__registrar_solicitud", hooks=[…], timeout=10),
HookMatcher(matcher="mcp__<servidor>__preaprobar_credito", hooks=[…], timeout=10)]}`, listo para
`ClaudeAgentOptions(hooks=…)`.

## Entrada que usan los tests (formato del SDK)

```python
{
    "hook_event_name": "PreToolUse",
    "tool_name": "mcp__crediagil-core__preaprobar_credito",
    "tool_input": {"id_solicitud": "SLC-0001"},
    "tool_use_id": "t1",
    "session_id": "s1",
    "transcript_path": "",
    "cwd": ".",
}
```

El callback se invoca como `await hook(entrada, "t1", {"signal": None})`.

## Hook de registro (`registrar_solicitud`)

| Caso | Salida |
|------|--------|
| Solicitante verificado y vigente | `{}` |
| Solicitante sin verificar | `deny` `IDENTIDAD_NO_VERIFICADA` |
| Solicitante bloqueado (verificó antes, luego se bloqueó) | `deny` `IDENTIDAD_NO_VERIFICADA` |
| `id_solicitante` inexistente | `deny` `IDENTIDAD_NO_VERIFICADA` |
| Solicitud no preaprobable (monto sobre el tope) con identidad vigente | `{}` (el hook no evalúa umbrales) |
| El modelo añade `"identidad_verificada": true` a los argumentos | ignorado: decide el estado |
| Sin `id_solicitante`, `null`, número o texto vacío | `deny` `ENTRADA_INVALIDA` |
| Estado ausente / corrupto | `deny` `ESTADO_ILEGIBLE` |

## Hook de preaprobación (`preaprobar_credito`)

Con una solicitud registrada de 5.000.000 a 12 meses y un salario de 1.556.700, que es el 30% exacto:

| Caso | Salida |
|------|--------|
| Solicitud válida, cuota en el 30% exacto, monto en el tope | `{}` |
| Salario 1.556.699 (cuota sobre el 30%) | `deny` `NO_PREAPROBABLE`, causa `regla_2` |
| Salario 1.556.701 (cuota bajo el 30%) | `{}` |
| Monto 5.000.001 | `deny` `NO_PREAPROBABLE`, causa `regla_2` |
| Declarado a 10% exacto del verificado / +1 | `{}` / `deny` `NO_PREAPROBABLE`, causa `regla_3` |
| Solicitud con hallazgos (nómina, USD, sin moneda) | `deny` `HALLAZGOS_DOCUMENTALES` con la lista |
| Evaluación guardada alterada a mano para marcarla preaprobable | `deny` (se recalcula) |
| Solicitante bloqueado después de registrar | `deny` `IDENTIDAD_NO_VERIFICADA` |
| Solicitud inexistente | `deny` `SOLICITUD_NO_ENCONTRADA` |
| Solicitud `ESCALADA` | `deny` `SOLICITUD_ESCALADA` |
| Solicitud ya `PREAPROBADA` con todo vigente | `{}` |
| Solicitud ya `PREAPROBADA` y solicitante bloqueado luego | `deny` `IDENTIDAD_NO_VERIFICADA` |
| `tool_input` con un campo adicional (`{"id_solicitud": "SLC-0001", "forzar": true}`) | `deny` `ENTRADA_INVALIDA` |
| Sin `id_solicitud`, número o `null` | `deny` `ENTRADA_INVALIDA` |
| Estado ausente / corrupto | `deny` `ESTADO_ILEGIBLE` |
| Excepción inesperada en el hook (monkeypatch) | `deny` `ERROR_INTERNO`, sin la traza en el motivo |

## Comunes

| Caso | Resultado |
|------|-----------|
| `tool_name` distinto del propio | `{}` y nada en el registro |
| Cualquier negación | motivo `"[CODIGO] mensaje Acción: acción."` y una entrada en el registro |
| Llamada permitida | nada en el registro |
| El estado antes y después de cualquier llamada (permitida o negada) | idéntico byte a byte |
| `al_negar` lanza una excepción | la negación se mantiene; el error se registra en el log |
| `crear_hooks(...)` | `ClaudeAgentOptions(hooks=…)` se construye y los matchers son los nombres completos exactos |
| El motivo | nunca contiene la fecha de nacimiento |
