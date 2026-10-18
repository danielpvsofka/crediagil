# Implementation Plan: Política de crédito y esquemas de extracción

**Branch**: `develop` (feature dir `003-credit-policy-extraction`) | **Date**: 2026-10-17 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/003-credit-policy-extraction/spec.md` — Issue [#3](https://github.com/danielpvsofka/crediagil/issues/3)

## Summary

Primer código del agente: el paquete `crediagil` en `src/` con dos módulos.

1. **`crediagil.policy`**:
   - Contiene la única definición en código de la tasa, los umbrales y los plazos (6–60
     meses), verificada por un test contra la constitución.
   - Calcula la cuota por sistema francés con `Decimal` y redondeo al peso.
   - Evalúa las reglas 2 y 3 con comparaciones exactas, sin división, y devuelve decisión y
     motivos.
2. **`crediagil.extraction`**:
   - Esquemas Pydantic v2 con campos `{valor, fragmento}`. El fragmento debe aparecer
     literalmente en el texto del documento, que se pasa como contexto de validación.
   - Documentos como unión discriminada: certificado laboral, extracto bancario y documento no
     soportado.
   - Derivación del ingreso verificado solo desde el salario certificado, con hallazgos de dato
     faltante, inconsistencia de nómina (> 10%) y fuera de política (moneda o documento).

Tests junto al código, en todos los bordes. Decisiones en [research.md](./research.md).

## Technical Context

**Language/Version**: Python ≥ 3.12 (entorno local 3.14.7)

**Primary Dependencies**: `pydantic` ≥ 2 (nueva, de runtime); biblioteca estándar (`decimal`,
`dataclasses`, `enum`). Dev: `pytest`, `ruff`.

**Storage**: N/A (funciones puras sobre datos en memoria)

**Testing**: pytest; tests `test_*.py` junto a cada módulo en `src/crediagil/**`; `src` añadido
a `testpaths` y `pythonpath`

**Target Platform**: biblioteca Python que importarán el servidor MCP y el agente (#4–#7)

**Project Type**: biblioteca (single project, layout `src/`)

**Performance Goals**: N/A (cálculos puntuales, microsegundos)

**Constraints**:
- `Decimal` en todo cálculo de dinero.
- Ningún parámetro fuera de `params.py`.
- Ningún valor inferido (Principio V).
- Solo datos ficticios en los tests.

**Scale/Scope**: 2 subpaquetes, ~5 módulos y sus tests; ~60 casos de prueba

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Evaluación pre-diseño | Post-diseño |
|-----------|-----------------------|-------------|
| I. Reglas de negocio | ✅ Implementa las reglas 2 y 3 y parte de la 5 (moneda y documento no soportado) con los parámetros de la constitución, sin modificarlos. Las reglas 1 y 4 quedan fuera (#6, #7). | ✅ `params.py` único y verificado contra la constitución (R2) |
| II. Garantía en código | ✅ Reglas deterministas en funciones puras que usarán los hooks del SDK (#6); nada depende del prompt. | ✅ |
| III. Datos ficticios | ✅ Documentos de prueba ficticios; marcador o construcción en tiempo de ejecución para cédula y cuenta (R7). | ✅ |
| IV. Spec antes que código | ✅ spec → plan → tasks antes de `src/`; `require_specs` lo hace cumplir. | ✅ |
| V. No inventar datos | ✅ Campo ausente = `None` más dato faltante; ingreso solo del certificado, nunca de extractos. | ✅ Validación de fragmento literal (R4) |
| VI. Trazabilidad | ✅ Cada campo lleva su fragmento; `IngresoVerificado.origen` conserva el campo de origen. | ✅ |
| VII. Tests en los bordes | ✅ Bordes exactos para monto, 30%, 10% (ambos sentidos), plazos 5/6/60/61 y nómina 10%. | ✅ Tablas en [contracts/](./contracts/) |

**Resultado**: PASA. Sin violaciones.

**Nota**: los valores numéricos aparecen en `params.py`, sus tests y los specs como criterio
de aceptación. Es la "única fuente" que pide el issue, verificada contra la constitución. No
contradice la regla de `CLAUDE.md`, que prohíbe repetirlos en otros lugares del código o en
prompts.

## Project Structure

### Documentation (this feature)

```text
specs/003-credit-policy-extraction/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── policy.md        # params, cuota, reglas: firmas y casos de borde
│   └── extraction.md    # esquemas, validación literal, ingreso verificado
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
pyproject.toml                         # + dependencies = ["pydantic>=2"], build src/, pytest testpaths/pythonpath
src/crediagil/
├── __init__.py
├── policy/
│   ├── __init__.py
│   ├── params.py                      # ÚNICA definición de tasa, umbrales, plazos, moneda
│   ├── test_params.py                 # verifica params contra .specify/memory/constitution.md
│   ├── cuota.py                       # calcular_cuota
│   ├── test_cuota.py
│   ├── reglas.py                      # Decision, Motivo, Resultado, evaluar_preaprobacion, evaluar_discrepancia, combinar
│   └── test_reglas.py
└── extraction/
    ├── __init__.py
    ├── schemas.py                     # CampoExtraido, documentos, validar_documento
    ├── test_schemas.py
    ├── income.py                      # derivar_ingreso, Hallazgo, resultado_de_hallazgos
    └── test_income.py
```

**Structure Decision**: un solo paquete `crediagil` con layout `src/`. `policy` no depende de
`extraction`; `extraction.income` depende de `policy` (parámetros y `Resultado`). La exposición
MCP va en #4 y #5.

## Complexity Tracking

Sin violaciones de la constitución que justificar.
