# Contrato: `crediagil.policy`

API pública que consumirán el servidor MCP (#4, #5), los hooks del Agent SDK (#6) y los tests.
Montos en pesos COP enteros.

## `crediagil.policy.params`

Constantes de [data-model.md](../data-model.md#parámetros-de-política-crediagilpolicyparams). Ningún otro módulo
las define; se importan.

## `crediagil.policy.cuota`

```python
def calcular_cuota(monto: int, plazo_meses: int) -> int
```

- Sistema francés con `TASA_MENSUAL`, redondeo `ROUND_HALF_UP` al peso.
- `ValueError` si `monto <= 0`, si `plazo_meses` no es `int` o está fuera de 6–60.

| Caso | Entrada | Salida |
|------|---------|--------|
| Ejemplo del issue | 4.000.000, 24 | 206.723 |
| Plazo mínimo | 4.000.000, 6 | 709.291 |
| Plazo máximo | 4.000.000, 60 | 109.568 |
| Plazo 5 / 61 | — | `ValueError` |
| Monto 0 / negativo / no entero (`4000000.0`, `True`) | — | `ValueError` |

## `crediagil.policy.reglas`

```python
class Decision(StrEnum): PREAPROBABLE, ANALISTA, FUERA_DE_POLITICA

@dataclass(frozen=True)
class Motivo: regla: str; mensaje: str; valores: dict

@dataclass(frozen=True)
class Resultado: decision: Decision; cuota: int | None; motivos: list[Motivo]

def evaluar_preaprobacion(monto: int, plazo_meses: int, ingreso_verificado: int | None) -> Resultado
def evaluar_discrepancia(declarado: int, verificado: int) -> Resultado
def combinar(*resultados: Resultado) -> Resultado
```

### Regla 2: `evaluar_preaprobacion`

Casos de borde (cuota de 5.000.000 a 12 meses = 467.010; 30% exacto con ingreso 1.556.700):

| Monto | Plazo | Ingreso | Decisión |
|-------|-------|---------|----------|
| 5.000.000 | 12 | 1.556.700 | `PREAPROBABLE` (monto = tope, cuota = 30%) |
| 5.000.000 | 12 | 1.556.699 | `ANALISTA` (cuota > 30%) |
| 5.000.000 | 12 | 1.556.701 | `PREAPROBABLE` (cuota < 30%) |
| 5.000.001 | 12 | 10.000.000 | `ANALISTA` (monto > tope) |
| 4.999.999 | 12 | 10.000.000 | `PREAPROBABLE` |
| 4.000.000 | 24 | `None` | `ANALISTA` (sin ingreso verificado) |
| 4.000.000 | 24 | 0 | `ANALISTA` (sin división por cero) |
| 4.000.000 | 24 | `2000000.0` / `True` | `ValueError` (ingreso no entero) |

`PREAPROBABLE` ⇒ `motivos == []`; cada condición incumplida añade un `Motivo` con
`regla="regla_2"` y los valores comparados.

### Regla 3: `evaluar_discrepancia`

Base: el ingreso verificado. Con verificado 2.000.000:

| Declarado | Decisión |
|-----------|----------|
| 2.200.000 / 1.800.000 (10% exacto) | `PREAPROBABLE` (no escala) |
| 2.199.999 / 1.800.001 (justo bajo 10%) | `PREAPROBABLE` |
| 2.200.001 / 1.799.999 | `ANALISTA` |

`ValueError` si `verificado` no es un entero > 0 o `declarado` no es un entero ≥ 0 (bool y float se rechazan). Quien la invoque (hooks del SDK, #6) debe evaluar antes la regla 2: sin ingreso verificado, la solicitud ya va a analista y la regla 3 no se llama.

### `combinar`

Precedencia `FUERA_DE_POLITICA` > `ANALISTA` > `PREAPROBABLE`; concatena motivos; conserva la
cuota del primer resultado que la tenga.
