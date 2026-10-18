# Data Model: Agente orquestador y subagente extractor

El agente no persiste nada propio: el trámite vive en el estado del core (spec 004 y 005). Lo
que sigue es el estado en memoria de la conversación y lo que devuelve cada turno.

## DocumentoAdjunto

| Campo | Tipo | Regla |
|-------|------|-------|
| `nombre` | `str` | No vacío (nombre del archivo) |
| `texto` | `str` | No vacío ni solo espacios; `.txt` o `.md` |
| `documento_id` | `str` | Lo asigna el agente: `DOC-1`, `DOC-2`, … (único en la conversación) |

Un adjunto vacío o ilegible no se delega: se pide que lo reenvíen.

## ConfigAgente

| Campo | Tipo | Defecto |
|-------|------|---------|
| `ruta_estado` | `Path` | `crediagil.mcp_server.estado.ruta_por_defecto()` |
| `servidor` | `str` | `"crediagil-core"` |
| `modelo` | `str` | `claude-sonnet-5-5` (o `CREDIAGIL_MODELO_ORQUESTADOR`) |
| `modelo_extractor` | `str` | `claude-haiku-4-5-20251001` (o `CREDIAGIL_MODELO_EXTRACTOR`) |
| `max_turnos` | `int` | 30 (tope de seguridad) |
| `max_continuaciones` | `int` | 2 (tope tras truncamiento) |
| `max_presupuesto_usd` | `float \| None` | `None` |
| `entorno_core` | `Mapping[str, str]` | vacío (variables extra para el servidor del core, p. ej. una falla inyectada en pruebas) |

## Parada (resultado de `clasificar_parada`)

`FIN_DE_TURNO`, `TRUNCADA`, `RECHAZO`, `TOPE`, `ERROR_API`, `DESCONOCIDA` (tabla en
[research.md](./research.md) R2). Se guarda junto con la razón cruda (`stop_reason`,
`terminal_reason`).

## EventoTraza

| Campo | Tipo | Notas |
|-------|------|-------|
| `tipo` | `herramienta` \| `delegacion` \| `parada` | `delegacion` = llamada a `Agent` |
| `nombre` | `str` | Sin el prefijo del servidor para las herramientas del core |
| `entrada` | `dict` | Redactada (sin la clave) |
| `salida` | `dict \| str \| None` | Resultado correlacionado por `tool_use_id` |
| `es_error` | `bool` | |
| `de_subagente` | `bool` | El mensaje tenía `parent_tool_use_id` |
| `stop_reason` | `str \| None` | Razón de parada de la respuesta del modelo que lo originó |

## PedidoInformacion

| Campo | Tipo | Regla |
|-------|------|-------|
| `datos` | `list[str]` | Al menos uno, no vacíos |
| `motivo` | `str` | No vacío |

## Aviso

| `tipo` | Origen | Contenido |
|--------|--------|-----------|
| `credito_preaprobado` | `preaprobar_credito` con `ok: true` | monto, plazo, cuota, tasa |
| `informacion_solicitada` | `solicitar_informacion` | datos y motivo |
| `escalamiento` | `escalar_a_analista` con `ok: true` | `id_escalamiento`, causa |
| `bloqueo_regla` | negación de un hook de #6 | herramienta, código, mensaje |

## ResultadoTurno

| Campo | Tipo | Notas |
|-------|------|-------|
| `respuesta` | `str` | Texto para el solicitante; vacío si hubo error |
| `avisos` | `list[Aviso]` | Derivados de resultados de herramientas |
| `traza` | `list[EventoTraza]` | Desplegable técnico de #8 |
| `parada` | `Parada` | |
| `razon_parada` | `str \| None` | `stop_reason` crudo del `ResultMessage` |
| `negaciones` | `list[Negacion]` | Nuevas en este turno (`RegistroNegaciones` de #6) |
| `pedidos_informacion` | `list[PedidoInformacion]` | |
| `costo_usd` | `float \| None` | `total_cost_usd` del `ResultMessage` |
| `error` | `str \| None` | Mensaje claro y redactado si `parada` es `ERROR_API` |

## Códigos de negación de la delegación (hook sobre `Agent`)

| Código | Cuándo | Acción indicada al modelo |
|--------|--------|---------------------------|
| `SUBAGENTE_NO_PERMITIDO` | `subagent_type` distinto de `extractor-documentos` | Solo puedes delegar en `extractor-documentos`. |
| `DOCUMENTO_DESCONOCIDO` | el `prompt` no menciona ningún `documento_id` conocido | Indica el `documento_id` del adjunto. |
| `DELEGACION_INCOMPLETA` | falta el nombre o el texto completo del documento | Pasa `documento_id`, nombre y texto completo, sin resumir. |
| `ENTRADA_INVALIDA` | entrada que no es un diccionario o sin `prompt` | Corrige los argumentos de la delegación. |

## Flujo de un turno

```text
mensaje + adjuntos → asignar documento_id → query(mensaje con <documento id=… nombre=…>texto</documento>)
   → receive_response():  AssistantMessage* / UserMessage* (traza)  →  ResultMessage
   → clasificar_parada(ResultMessage)
        FIN_DE_TURNO → ResultadoTurno
        TRUNCADA     → query("Continúa.") hasta max_continuaciones, luego escalar
        RECHAZO / TOPE / DESCONOCIDA → incidente: escalar y devolver el aviso
        ERROR_API    → ResultadoTurno con error claro y redactado
```
