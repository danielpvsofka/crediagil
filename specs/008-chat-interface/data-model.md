# Data Model: Interfaz de chat

La interfaz no guarda nada propio en disco: el trámite vive en el estado del core (specs 004 y
005) y el hilo, solo en memoria de la página. Lo que sigue es el estado en memoria del servidor
y la forma de lo que viaja por la API. La forma de lo que devuelve el agente (`ResultadoTurno`,
`Aviso`, `EventoTraza`, `Negacion`) está en la [spec 007](../007-agent-orchestrator-extractor/data-model.md).

## Sesion (servidor, en memoria)

Una sola por proceso.

| Campo | Tipo | Notas |
|-------|------|-------|
| `config` | `ConfigAgente` | Base, de `crediagil.agent.opciones`; la falla simulada se añade en `entorno_core` |
| `conversacion_id` | `str \| None` | `None` hasta que se abre la primera conversación |
| `turnos` | `int` | Turnos completados en la conversación actual |
| `falla_llamadas` | `int` | Llamadas al core que fallan en esta conversación; `0` = sin simulación (0 a 20) |
| `agente` | `Agente \| None` | Se abre con el primer turno de la conversación y se cierra al cambiar de conversación |
| `ocupada` | `asyncio.Lock` | Un turno, una conversación nueva o un reinicio a la vez |

Operaciones: `turno(mensaje, adjuntos)`, `nueva(falla_llamadas)`, `reiniciar_datos()`,
`cerrar()`, `estado()`. Las tres primeras fallan con `TurnoEnCurso` si el cerrojo está tomado.

## Adjunto (entrada de la API)

| Campo | Tipo | Regla |
|-------|------|-------|
| `nombre` | `str` | No vacío tras quitar rutas; extensión `.txt` o `.md` (sin distinguir mayúsculas) |
| `contenido_b64` | `str` | Base64 válido; decodifica a UTF-8 (BOM tolerado); como máximo 100 KiB; no vacío ni solo espacios |

Se convierte en `DocumentoAdjunto(nombre, texto)` de `crediagil.agent.documentos`. Como máximo 5
por mensaje. Códigos de error en [contracts/api.md](./contracts/api.md).

## CasoPrueba

| Campo | Tipo | Regla |
|-------|------|-------|
| `id` | `str` | Único, en `snake_case` |
| `nombre` | `str` | No vacío |
| `descripcion` | `str` | Qué comportamiento ejercita |
| `mensaje` | `str` | No vacío; solo datos ficticios |
| `adjuntos` | `tuple[DocumentoAdjunto, ...]` | `.txt` o `.md` ficticios |
| `falla_sugerida` | `int` | `0` por defecto; si es mayor, la interfaz sugiere activarla |

## Turno (respuesta de la API)

| Campo | Tipo | Notas |
|-------|------|-------|
| `id_turno` | `int` | 1, 2, … dentro de la conversación |
| `respuesta` | `str` | Texto para el solicitante; vacío si hubo error |
| `error` | `str \| None` | Mensaje claro y redactado |
| `parada` | `str` | Valor de `Parada` (`fin_de_turno`, `truncada`, …) |
| `razon_parada` | `str \| None` | `stop_reason` crudo |
| `costo_usd` | `float \| None` | |
| `avisos` | `list[AvisoVista]` | Del resultado; ninguno más |
| `traza` | `list[EventoTraza]` | Como en #7, ya redactada |
| `negaciones` | `list[NegacionVista]` | De los hooks de #6 en este turno |
| `pedidos_informacion` | `list[PedidoVista]` | |

### AvisoVista

| Campo | Tipo | Notas |
|-------|------|-------|
| `tipo` | `str` | `credito_preaprobado`, `informacion_solicitada`, `escalamiento` o `bloqueo_regla` |
| `rotulo` | `str` | De `ROTULOS_AVISO` (una sola tabla en Python); si el tipo fuera desconocido, el propio tipo |
| `contenido` | `dict` | El de `Aviso.contenido` de #7 |

### NegacionVista y PedidoVista

- `NegacionVista`: `herramienta`, `codigo`, `mensaje`, `accion`.
- `PedidoVista`: `datos` (lista de textos) y `motivo`.

## Estado (respuesta de `GET /api/estado`)

| Campo | Tipo | Notas |
|-------|------|-------|
| `clave_configurada` | `bool` | Nunca el valor |
| `estado_core_legible` | `bool` | `true` si el archivo de estado no existe (se creará) o se lee bien |
| `conversacion` | `{id, turnos, activa}` | `activa` es `true` si hay un agente abierto |
| `falla_simulada` | `{llamadas}` | |
| `limites` | `{max_adjuntos, max_bytes_adjunto, extensiones}` | Para que la página los muestre; el servidor es la autoridad |

## Transiciones de la conversación

```text
sin conversación ──turno──▶ activa (agente abierto) ──turno──▶ activa
        ▲                          │
        └── nueva / reiniciar ─────┘   (cierra el agente; el hilo de la página se vacía)
```

`nueva` y `reiniciar` fallan con `TURNO_EN_CURSO` mientras haya un turno en marcha.
