# Data Model: Servidor MCP: identificación del solicitante

## Solicitante (en el archivo de estado)

| Campo | Tipo | Reglas |
|-------|------|--------|
| `id_solicitante` | `str` | `SOL-NNNN`, clave del mapa `solicitantes` |
| `documento` | `str` | `TEST-` + 6 dígitos, único; se guarda normalizado (mayúsculas, sin espacios) |
| `nombre` | `str` | Nombre completo ficticio |
| `fecha_nacimiento` | `str` (`AAAA-MM-DD`) | Secreta: nunca sale en respuestas |
| `intentos_fallidos` | `int` | 0–3 |
| `bloqueado` | `bool` | `true` ⇔ `intentos_fallidos == 3` |

### Estados de verificación

```text
            fecha correcta (reinicia a 0)
        ┌──────────────────────────────┐
        ▼                              │
  [0 fallos] ──fallo──▶ [1] ──fallo──▶ [2] ──fallo──▶ [BLOQUEADO]
        ▲                │              │                  │
        └─fecha correcta─┘──────────────┘    cualquier intento → permisos
```

| Desde | Evento | Hacia | Respuesta |
|-------|--------|-------|-----------|
| 0–2 fallos | fecha correcta | 0 fallos | `ok`, `verificado: true` |
| 0 / 1 fallos | fecha incorrecta | 1 / 2 | `negocio` `IDENTIDAD_NO_COINCIDE`, `intentos_restantes` 2 / 1 |
| 2 fallos | fecha incorrecta | BLOQUEADO | `permisos` `SOLICITANTE_BLOQUEADO` |
| BLOQUEADO | cualquiera | BLOQUEADO | `permisos` `SOLICITANTE_BLOQUEADO` |
| cualquiera | fecha inválida/futura | sin cambio | `validacion` `FECHA_INVALIDA` |
| cualquiera | falla inyectada | sin cambio | `transitorio` `SERVICIO_NO_DISPONIBLE` |

## Archivo de estado

```text
{"version": 1, "solicitantes": {"SOL-0001": {…}, …}}
```

Ruta: `CREDIAGIL_MCP_ESTADO` (por defecto `./.data/core_estado.json`, ignorado por git). Lock:
`<ruta>.lock`. Escritura: temporal + `os.replace`.

## Respuesta

| Caso | Forma |
|------|-------|
| Éxito | `{"ok": true, …datos}` |
| Error | `{"ok": false, "error": {"tipo", "codigo", "mensaje", "reintentable", "detalles"}}` |

### `TipoError`

| `tipo` | `reintentable` | Uso |
|--------|----------------|-----|
| `transitorio` | `true` | Falla inyectada, estado ilegible, error interno |
| `validacion` | `false` | Parámetros inválidos |
| `negocio` | `false` | Solicitante no encontrado, identidad no coincide |
| `permisos` | `false` | Solicitante bloqueado |

### Códigos

| `codigo` | `tipo` | `detalles` |
|----------|--------|------------|
| `PARAMETROS_INVALIDOS` | `validacion` | `{"campo": …}` |
| `FECHA_INVALIDA` | `validacion` | `{"fecha_nacimiento": <valor recibido>}` |
| `SOLICITANTE_NO_ENCONTRADO` | `negocio` | `{"id_solicitante": …}` |
| `IDENTIDAD_NO_COINCIDE` | `negocio` | `{"intentos_restantes": 1 \| 2}` |
| `SOLICITANTE_BLOQUEADO` | `permisos` | `{"id_solicitante": …}` |
| `SERVICIO_NO_DISPONIBLE` | `transitorio` | `{}` |
| `ESTADO_ILEGIBLE` | `transitorio` | `{}` |
| `ERROR_INTERNO` | `transitorio` | `{}` |

## Configuración de fallas

| Variable | Efecto |
|----------|--------|
| `CREDIAGIL_MCP_FALLAS_N` | Falla las próximas N llamadas (entero ≥ 0) |
| `CREDIAGIL_MCP_FALLAS_PROB` | Probabilidad 0–1 por llamada |
| `CREDIAGIL_MCP_FALLAS_SEMILLA` | Semilla del generador (reproducible) |

Sin variables: desactivada. Valores inválidos: el servidor no arranca y lo explica.

## Cambios introducidos por #5

- Solicitante: `verificado_en: str | null` (última verificación exitosa; `null` al bloquear).
- Estado `version: 2` con `solicitudes` y `escalamientos`
  (ver `specs/005-mcp-origination-tools/data-model.md`); migración automática desde v1.
- `reintentable`: ver FR-001a de #5 (excepción para errores de extracción).
