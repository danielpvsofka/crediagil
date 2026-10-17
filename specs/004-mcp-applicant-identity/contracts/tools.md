# Contrato: herramientas MCP del core de originación

Servidor `crediagil-core`, transporte stdio, arranque `python -m crediagil.mcp_server.server`.
Formas de respuesta, tipos y códigos en [data-model.md](../data-model.md#respuesta).

## `buscar_solicitante`

**Descripción (es)**: "Busca solicitantes en el core por número de documento o por parte del
nombre. Úsala antes de verificar la identidad. Puede devolver varias coincidencias o ninguna;
si hay varias, pide al solicitante su documento. No devuelve la fecha de nacimiento."

| Parámetro | Tipo | Regla |
|-----------|------|-------|
| `documento` | `str \| null` | Exactamente uno de los dos |
| `nombre` | `str \| null` | ≥ 3 caracteres no blancos |

Respuesta de éxito:

```json
{"ok": true, "coincidencias": [{"id_solicitante": "SOL-0001", "documento": "TEST-…", "nombre": "…", "bloqueado": false}]}
```

| Caso | Resultado |
|------|-----------|
| Documento semilla exacto | 1 coincidencia |
| Documento en minúsculas o con espacios | 1 coincidencia (normalizado) |
| `nombre: "prueba"` | ≥ 2 coincidencias |
| `nombre: "perez"` | encuentra "Pérez" |
| Sin coincidencias | `{"ok": true, "coincidencias": []}` |
| Ni documento ni nombre / ambos | `validacion` `PARAMETROS_INVALIDOS` |
| `nombre: "ab"` o `"  ab "` | `validacion` `PARAMETROS_INVALIDOS` |
| Cualquier éxito | ninguna coincidencia contiene `fecha_nacimiento` |

## `verificar_identidad`

**Descripción (es)**: "Verifica la identidad de un solicitante encontrado con
`buscar_solicitante`, comparando la fecha de nacimiento que da el solicitante (AAAA-MM-DD).
Tras 3 intentos fallidos el solicitante queda bloqueado: no reintentes; escala a un analista.
Ante un error transitorio, reintenta."

| Parámetro | Tipo | Regla |
|-----------|------|-------|
| `id_solicitante` | `str` | Devuelto por la búsqueda |
| `fecha_nacimiento` | `str` | `AAAA-MM-DD`, no futura |

Respuesta de éxito: `{"ok": true, "verificado": true, "id_solicitante": "SOL-0001"}`.

| Caso (estado previo) | Resultado | Estado después |
|----------------------|-----------|----------------|
| 0 fallos, fecha correcta | `ok`, `verificado: true` | 0 |
| 2 fallos, fecha correcta | `ok`, `verificado: true` | 0 |
| 0 fallos, fecha incorrecta | `negocio` `IDENTIDAD_NO_COINCIDE`, `intentos_restantes: 2` | 1 |
| 1 fallo, fecha incorrecta | `negocio`, `intentos_restantes: 1` | 2 |
| 2 fallos, fecha incorrecta | `permisos` `SOLICITANTE_BLOQUEADO` | bloqueado |
| bloqueado, fecha correcta | `permisos` `SOLICITANTE_BLOQUEADO` | bloqueado |
| 2 fallos + reinicio, fecha incorrecta | `permisos` | bloqueado |
| id inexistente | `negocio` `SOLICITANTE_NO_ENCONTRADO` | — |
| `"17/03/1990"`, `"1990-02-30"`, fecha futura | `validacion` `FECHA_INVALIDA` | sin cambio |

## Comunes a ambas herramientas

| Caso | Resultado |
|------|-----------|
| `CREDIAGIL_MCP_FALLAS_N=2` | las 2 primeras llamadas: `transitorio` `SERVICIO_NO_DISPONIBLE`, `reintentable: true`; la 3.ª normal; estado intacto |
| Archivo de estado corrupto | `transitorio` `ESTADO_ILEGIBLE`; archivo sin modificar |
| Excepción inesperada | `transitorio` `ERROR_INTERNO`, `detalles: {}`, sin traza |
| Cualquier respuesta | exactamente `ok` + datos, o `ok: false` + `error` con las 5 claves |

## Protocolo

| Caso | Resultado |
|------|-----------|
| `list_tools` | `buscar_solicitante` y `verificar_identidad`, con descripción en español y esquema de entrada |
| Arranque sin archivo de estado | se crea con la semilla |
