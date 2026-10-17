# Data Model: Servidor MCP: herramientas de originación

Extiende el estado de #4 (`specs/004-mcp-applicant-identity/data-model.md`).

## Estado v2

```text
{"version": 2, "solicitantes": {...}, "solicitudes": {...}, "escalamientos": {...}}
```

Un archivo v1 se migra al cargarlo: se añaden colecciones vacías y `verificado_en: null`.

### Solicitante (cambios)

| Campo | Tipo | Regla |
|-------|------|-------|
| `verificado_en` | `str \| null` | ISO-8601 UTC de la última verificación exitosa; `null` al bloquear |

Identidad vigente ⇔ `verificado_en != null` y `bloqueado == false`.

### Solicitud

| Campo | Tipo | Regla |
|-------|------|-------|
| `id_solicitud` | `str` | `SLC-NNNN` secuencial |
| `id_solicitante` | `str` | Solicitante con identidad vigente al registrar |
| `monto` | `int` | > 0 (validado con `crediagil.policy`) |
| `plazo_meses` | `int` | 6–60 (política) |
| `ingreso_declarado` | `int` | ≥ 0 |
| `ingreso_verificado` | `{valor, id_documento, fragmento} \| null` | Del salario certificado; null solo si fuera de política |
| `datos` | `list[DatoConProcedencia]` | Todos los campos extraídos no nulos |
| `hallazgos` | `list[{tipo, mensaje, campo, regla}]` | De `derivar_ingreso` (#3) |
| `evaluacion` | `Evaluacion` | Al registrar |
| `estado` | `REGISTRADA \| PREAPROBADA \| ESCALADA` | Ver transiciones |
| `registrada_en`, `preaprobada_en`, `escalada_en` | `str \| null` | ISO-8601 UTC |

### DatoConProcedencia

| Campo | Tipo |
|-------|------|
| `documento_tipo` | `certificado_laboral \| extracto_bancario` |
| `campo` | `str` (p. ej. `salario_mensual`, `abonos_nomina[0]`) |
| `valor` | JSON (número, texto o fecha ISO) |
| `id_documento` | `str` (dado por el agente) |
| `fragmento` | `str` literal del documento |

### Evaluacion

| Campo | Tipo |
|-------|------|
| `preaprobable_automaticamente` | `bool` (`decision == preaprobable`) |
| `decision` | `preaprobable \| analista \| fuera_de_politica` |
| `cuota` | `int` |
| `causas_escalamiento` | `list[{regla, mensaje, valores}]` (vacía si preaprobable) |

### Transiciones de Solicitud

```text
           preaprobar_credito (revalida OK)
REGISTRADA ─────────────────────────────────▶ PREAPROBADA ──preaprobar──▶ PREAPROBADA (idempotente)
     │
     └── escalar_a_analista(id_solicitud) ──▶ ESCALADA ──preaprobar──▶ error SOLICITUD_ESCALADA
PREAPROBADA ──escalar──▶ error SOLICITUD_PREAPROBADA
```

### Escalamiento

| Campo | Tipo | Regla |
|-------|------|-------|
| `id_escalamiento` | `str` | `ESC-NNNN` secuencial |
| `id_solicitud` | `str \| null` | Opcional |
| `resumen` | `ResumenEscalamiento` | Validado completo |
| `creado_en` | `str` | ISO-8601 UTC |

### ResumenEscalamiento (todas las claves obligatorias)

| Campo | Tipo | Puede ser vacío |
|-------|------|-----------------|
| `solicitante` | `str` | No |
| `monto` | `int > 0 \| null` | Sí (null) |
| `plazo` | `int > 0 \| null` | Sí (null) |
| `datos` | `list[{campo, valor, documento, fragmento}]` | Sí (`[]`); cada elemento completo y `valor` no nulo |
| `discrepancias` | `list[str]` (cada una no vacía) | Sí (`[]`) |

Validación estricta: no se convierten tipos (p. ej. `"5000000"` no es un monto).
| `causa` | `solicitud_humano \| fuera_de_politica \| regla_2 \| regla_3 \| ingreso_no_verificable \| inconsistencia_documental \| identidad_bloqueada \| otro` | No |
| `detalle` | `str` | No |
| `accion_recomendada` | `str` | No |

## Códigos de error nuevos

| `codigo` | `tipo` | `reintentable` | `detalles` |
|----------|--------|----------------|------------|
| `EXTRACCION_INVALIDA` | `validacion` | **true** | `{errores: [{campo, motivo}]}` |
| `FRAGMENTO_NO_LITERAL` | `validacion` | **true** | `{campos: [..]}` |
| `PARAMETROS_INVALIDOS` | `validacion` | false | `{campo}` (reutilizado de #4) |
| `IDENTIDAD_NO_VERIFICADA` | `permisos` | false | `{id_solicitante}` |
| `INGRESO_NO_VERIFICABLE` | `negocio` | false | `{datos_faltantes: [campo..]}` |
| `NO_PREAPROBABLE` | `negocio` | false | `{causas: [...]}` |
| `SOLICITUD_NO_ENCONTRADA` | `negocio` | false | `{id_solicitud}` |
| `SOLICITUD_ESCALADA` | `negocio` | false | `{id_solicitud}` |
| `SOLICITUD_PREAPROBADA` | `negocio` | false | `{id_solicitud}` |
| `RESUMEN_INCOMPLETO` | `validacion` | false | `{campos_faltantes: [..]}` |

Regla de reintento (FR-001a): `transitorio` siempre; `validacion` solo en
`EXTRACCION_INVALIDA` y `FRAGMENTO_NO_LITERAL`; `negocio`/`permisos` nunca.
