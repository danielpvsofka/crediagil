# Implementation Plan: Servidor MCP: herramientas de originación

**Branch**: `develop` (feature dir `005-mcp-origination-tools`) | **Date**: 2026-10-17 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/005-mcp-origination-tools/spec.md` — Issue [#5](https://github.com/danielpvsofka/crediagil/issues/5)

## Summary

Añade cinco herramientas al servidor `crediagil-core` de #4. Reutilizan la política y la
extracción de #3, sin parámetros propios.

- **`validar_extraccion`**: valida con los esquemas de #3. Los errores `FRAGMENTO_NO_LITERAL` y
  `EXTRACCION_INVALIDA` son `validacion` reintentables (FR-001a).
- **`registrar_solicitud`**:
  - Exige identidad vigente; si no la hay, responde `permisos`.
  - Guarda cada dato con `id_documento` y fragmento.
  - Evalúa con `combinar` (regla 2, regla 3 y hallazgos de ingreso) y devuelve
    `preaprobable_automaticamente` con las causas.
  - Sin salario certificado responde `INGRESO_NO_VERIFICABLE` y no guarda nada.
- **`calcular_capacidad_pago`**: "SOLO SIMULA", no lee ni escribe estado.
- **`preaprobar_credito`**: "COMPROMETE A CREDIÁGIL". Revalida en el core la identidad y recalcula
  las reglas con los datos guardados antes de pasar la solicitud a `PREAPROBADA`. Es idempotente.
- **`escalar_a_analista`**: valida un resumen de 8 claves obligatorias y crea el escalamiento.

Ajustes a código existente:

- **#4**: `verificar_identidad` guarda `verificado_en`; el estado pasa a v2, con migración en
  memoria desde v1; `ErrorCore` acepta un `reintentable` explícito, restringido a FR-001a.
- **#3**: los fragmentos no literales emiten un error de Pydantic con tipo propio,
  `fragmento_no_literal`.

Detalle en [research.md](./research.md).

## Technical Context

**Language/Version**: Python ≥ 3.12

**Primary Dependencies**: las existentes (`mcp` 2.x, `filelock`, `pydantic`); sin dependencias
nuevas

**Storage**: el archivo de estado JSON de #4, en v2 (`solicitudes`, `escalamientos`,
`verificado_en`)

**Testing**: pytest + anyio; tests junto al código, en `src/crediagil/mcp_server/`

**Target Platform**: igual que #4

**Project Type**: servidor MCP (extensión)

**Performance Goals**: < 100 ms por llamada con estado pequeño

**Constraints**:
- Registro y preaprobación atómicos: una transacción, nada a medias.
- Parámetros solo de `crediagil.policy`.
- Toda decisión de negocio revalidada en el core.
- Solo datos ficticios.

**Scale/Scope**: 5 herramientas, 2 módulos nuevos y 4 modificados, con sus tests

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Evaluación pre-diseño | Post-diseño |
|-----------|-----------------------|-------------|
| I. Reglas de negocio | ✅ Las reglas 1, 2, 3 y 5 se aplican en el core con `crediagil.policy` y `crediagil.extraction`; ningún umbral se redefine. La regla 4 tiene una salida sin requisitos previos (`escalar_a_analista` sin identidad). | ✅ Bordes de las reglas 2 y 3 probados desde registro y preaprobación |
| II. Garantía en código | ✅ Registrar exige identidad y preaprobar revalida identidad y umbrales en código. Las descripciones solo guían (SOLO SIMULA / COMPROMETE). Los hooks del SDK (#6) son la primera barrera; esta es la segunda. | ✅ |
| III. Datos ficticios | ✅ Textos y documentos ficticios; `pragma` donde el hook lo pida. | ✅ |
| IV. Spec antes que código | ✅ La spec incluye los cambios a #3 y #4 (FR-001a, FR-007). | ✅ |
| V. No inventar datos | ✅ Sin salario certificado, `INGRESO_NO_VERIFICABLE` con los datos faltantes; nunca se infiere. | ✅ |
| VI. Trazabilidad | ✅ Cada dato guardado lleva `id_documento` y fragmento; el escalamiento exige procedencia en los datos. Reflejarlo como ticket de GitHub queda para #7. | ✅ |
| VII. Tests en los bordes | ✅ Umbral, −1 y +1 para monto, cuota y discrepancia en registro y preaprobación, más identidad no verificada, solicitud de humano y caso fuera de política. | ✅ Tablas en [contracts/tools.md](./contracts/tools.md) |

**Resultado**: PASA. Sin violaciones.

## Project Structure

### Documentation (this feature)

```text
specs/005-mcp-origination-tools/
├── plan.md, research.md, data-model.md, quickstart.md
├── contracts/tools.md
├── checklists/requirements.md
└── tasks.md            # /speckit-tasks
```

### Source Code (repository root)

```text
src/crediagil/extraction/
├── schemas.py              # PydanticCustomError("fragmento_no_literal" / "texto_faltante")
└── test_schemas.py         # + tipo de error estable
src/crediagil/mcp_server/
├── errores.py / test_errores.py           # reintentable explícito (FR-001a)
├── estado.py / test_estado.py             # v2 + migración desde v1
├── identidad.py / test_identidad.py       # verificado_en; identidad_vigente()
├── originacion.py / test_originacion.py   # extraer, registrar, simular, preaprobar  (nuevo)
├── escalamiento.py / test_escalamiento.py # ResumenEscalamiento, escalar             (nuevo)
├── server.py / test_server.py             # 5 herramientas nuevas + descripciones
└── test_server_stdio.py                   # 7 herramientas
specs/004-mcp-applicant-identity/contracts/tools.md   # nota de FR-001a y verificado_en
```

**Structure Decision**: la lógica de originación vive en dos módulos puros (`originacion.py`,
`escalamiento.py`) que reciben un `AlmacenEstado` y lanzan `ErrorCore`. `server.py` solo los
expone. Así #6 y #7 pueden reutilizar la evaluación sin pasar por el protocolo.

## Complexity Tracking

Sin violaciones de la constitución que justificar.
