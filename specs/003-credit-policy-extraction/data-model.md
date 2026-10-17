# Data Model: Política de crédito y esquemas de extracción

Montos e ingresos en pesos COP como enteros (`int`/`Decimal` sin decimales). Detalle de firmas
en [contracts/policy.md](./contracts/policy.md) y [contracts/extraction.md](./contracts/extraction.md).

## Parámetros de política (`crediagil.policy.params`)

| Constante | Valor | Fuente |
|-----------|-------|--------|
| `TASA_MENSUAL` | `Decimal("0.018")` | Constitución, Principio I |
| `MONTO_MAXIMO_PREAPROBACION` | `5_000_000` | Constitución, regla 2 |
| `PROPORCION_MAXIMA_CUOTA_INGRESO` | `Decimal("0.30")` | Constitución, regla 2 |
| `DISCREPANCIA_MAXIMA_INGRESO` | `Decimal("0.10")` | Constitución, regla 3 |
| `PLAZO_MINIMO_MESES` / `PLAZO_MAXIMO_MESES` | `6` / `60` | Spec FR-004 |
| `MONEDA` | `"COP"` | Constitución, restricciones de dominio |

Única definición en el código; `test_params.py` la verifica contra la constitución.

## Evaluación

| Entidad | Campos | Reglas |
|---------|--------|--------|
| `Decision` | `PREAPROBABLE`, `ANALISTA`, `FUERA_DE_POLITICA` | Precedencia al combinar: `FUERA_DE_POLITICA` > `ANALISTA` > `PREAPROBABLE` |
| `Motivo` | `regla` (`"regla_2"`, `"regla_3"`, `"nomina"`, `"moneda"`, `"documento"`, `"ingreso"`), `mensaje`, `valores: dict` | Uno por condición que no se cumple |
| `Resultado` | `decision`, `cuota: int \| None`, `motivos: list[Motivo]` | `PREAPROBABLE` ⇒ `motivos == []` |

### Reglas (comparaciones exactas, sin división)

| Regla | Condición para no escalar |
|-------|---------------------------|
| Plazo | `6 ≤ plazo ≤ 60`, entero; si no, `ValueError` |
| Monto | `monto > 0`; si no, `ValueError` |
| Regla 2 | `monto ≤ 5_000_000` **y** `ingreso` presente y `> 0` **y** `cuota ≤ 0.30 · ingreso` |
| Regla 3 | `|declarado − verificado| ≤ 0.10 · verificado` |
| Nómina | `|promedio_nomina − salario| ≤ 0.10 · salario` (si hay abonos de nómina) |

Cuota: `round_half_up(M·i / (1 − (1+i)^−n))` al peso.

## Extracción (`crediagil.extraction.schemas`)

### `CampoExtraido[T]`

| Campo | Tipo | Validación |
|-------|------|------------|
| `valor` | `T` | obligatorio |
| `fragmento` | `str` | obligatorio, no vacío; con contexto `texto`, MUST ser subcadena literal |

En el documento, un campo ausente es `None` (dato faltante), nunca un `CampoExtraido` vacío.

### Documentos (unión discriminada por `tipo`)

| `tipo` | Campos (`CampoExtraido` o `None`) |
|--------|-----------------------------------|
| `certificado_laboral` | `empleador: str`, `nombre_empleado: str`, `salario_mensual: int`, `moneda: str`, `fecha_expedicion: date` |
| `extracto_bancario` | `titular: str`, `periodo: str`, `moneda: str`, `abonos_nomina: list[CampoExtraido[int]]` (lista vacía si no hay) |
| `no_soportado` | `tipo_detectado: str` (texto libre, sin fragmento) |

## Ingreso verificado (`crediagil.extraction.income`)

| Entidad | Campos |
|---------|--------|
| `IngresoVerificado` | `valor: int`, `moneda: "COP"`, `origen: CampoExtraido[int]` (salario del certificado) |
| `Hallazgo` | `tipo` (`DATO_FALTANTE`, `INCONSISTENCIA_DOCUMENTAL`, `FUERA_DE_POLITICA`), `mensaje`, `campo: str \| None`, `regla: str` (regla del `Motivo` equivalente) |
| `ResultadoIngreso` | `ingreso: IngresoVerificado \| None`, `hallazgos: list[Hallazgo]` |

### Flujo

```text
documentos ──validar(texto)──▶ certificado?, extractos[], no_soportados[]
  no_soportados ≠ ∅                → Hallazgo FUERA_DE_POLITICA (documento)
  certificado sin salario / ausente → ingreso=None + DATO_FALTANTE
  moneda ≠ COP                      → FUERA_DE_POLITICA (moneda)
  nómina vs. salario > 10%          → INCONSISTENCIA_DOCUMENTAL
  si no                             → IngresoVerificado(salario)
```

Hallazgos → decisión: `FUERA_DE_POLITICA` → `FUERA_DE_POLITICA`; `DATO_FALTANTE` o
`INCONSISTENCIA_DOCUMENTAL` → `ANALISTA`.
