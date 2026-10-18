# Data Model: Hooks del Agent SDK para las reglas 1 y 2

Los hooks no tienen estado propio: leen el del core (spec 004 y 005) y solo escriben en el
registro de negaciones, que vive en memoria.

## Decisión de un hook

| Campo | Tipo | Regla |
|-------|------|-------|
| `permitir` | `bool` | `true` ⇒ el hook devuelve `{}` |
| `codigo` | `str \| None` | Obligatorio si `permitir` es `false` |
| `mensaje` | `str \| None` | Español, sin datos sensibles |
| `accion` | `str \| None` | Qué debe hacer el modelo |
| `detalles` | `dict` | Datos de apoyo (hallazgos, causas, ids) |

## Negacion (entrada del registro)

| Campo | Tipo | Notas |
|-------|------|-------|
| `herramienta` | `str` | `registrar_solicitud` \| `preaprobar_credito` (sin prefijo) |
| `codigo` | `str` | Ver tabla de códigos |
| `mensaje` | `str` | |
| `accion` | `str` | |
| `detalles` | `dict` | Serializable en JSON |
| `momento` | `str` | ISO-8601 UTC |

`RegistroNegaciones`: `registrar(negacion)`, `listar() -> list[Negacion]` (copia),
`ultima() -> Negacion | None`, `al_negar: Callable[[Negacion], None] | None`.

## Códigos de negación

| Código | Herramienta | Cuándo | `detalles` |
|--------|-------------|--------|------------|
| `IDENTIDAD_NO_VERIFICADA` | ambas | Solicitante inexistente, sin verificar o bloqueado | `{id_solicitante}` |
| `SOLICITUD_NO_ENCONTRADA` | preaprobar | La solicitud no existe | `{id_solicitud}` |
| `SOLICITUD_ESCALADA` | preaprobar | La solicitud está `ESCALADA` | `{id_solicitud}` |
| `HALLAZGOS_DOCUMENTALES` | preaprobar | La solicitud tiene hallazgos | `{id_solicitud, hallazgos: [{tipo, mensaje, campo}]}` |
| `NO_PREAPROBABLE` | preaprobar | Reglas 2 o 3 no cumplidas al recalcular | `{id_solicitud, causas: [{regla, mensaje, valores}]}` |
| `ESTADO_ILEGIBLE` | ambas | Estado ausente, corrupto o sin lock a tiempo | `{}` |
| `ENTRADA_INVALIDA` | ambas | Falta el identificador, tipo incorrecto, o (preaprobar) campos adicionales | `{campo}` |
| `ERROR_INTERNO` | ambas | Excepción inesperada en el hook | `{}` |

### Acción por código

| Código | Acción indicada al modelo |
|--------|---------------------------|
| `IDENTIDAD_NO_VERIFICADA` | Verifica la identidad con `verificar_identidad`; si el solicitante está bloqueado, escala a un analista. |
| `SOLICITUD_NO_ENCONTRADA` | Usa el `id_solicitud` que devolvió `registrar_solicitud`. |
| `SOLICITUD_ESCALADA` | No preapruebes: un analista continúa el caso. |
| `HALLAZGOS_DOCUMENTALES` | Escala a un analista con los hallazgos. |
| `NO_PREAPROBABLE` | Escala a un analista con las causas. |
| `ESTADO_ILEGIBLE` | Reintenta una vez; si persiste, escala a un analista. |
| `ENTRADA_INVALIDA` | Corrige los argumentos de la llamada. |
| `ERROR_INTERNO` | No reintentes de inmediato; escala a un analista si persiste. |

## Flujo de decisión de `preaprobar_credito`

```text
tool_input == {"id_solicitud": str no vacío}?      no → ENTRADA_INVALIDA
leer_existente()                                    falla → ESTADO_ILEGIBLE
solicitud existe?                                   no → SOLICITUD_NO_ENCONTRADA
estado == ESCALADA?                                 sí → SOLICITUD_ESCALADA
identidad_vigente(solicitante)?                     no → IDENTIDAD_NO_VERIFICADA
solicitud.hallazgos != []?                          sí → HALLAZGOS_DOCUMENTALES
evaluar_solicitud_guardada(solicitud) preaprobable? no → NO_PREAPROBABLE
                                                    sí → permitir ({})
```

## Flujo de decisión de `registrar_solicitud`

```text
tool_input["id_solicitante"] es str no vacío?       no → ENTRADA_INVALIDA
leer_existente()                                    falla → ESTADO_ILEGIBLE
identidad_vigente(solicitante existente)?           no → IDENTIDAD_NO_VERIFICADA
                                                    sí → permitir ({})
```

## Salida del SDK

| Caso | Valor devuelto por el callback |
|------|-------------------------------|
| Permitir | `{}` |
| Negar | `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "[CODIGO] mensaje Acción: acción."}}` |
