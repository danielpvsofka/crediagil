# Research: Política de crédito y esquemas de extracción

Decisiones de la Fase 0. No quedan `NEEDS CLARIFICATION` (FR-004 se aclaró en la spec: plazo
entero de 6 a 60 meses).

## R1. Ubicación del código y de los tests

- **Decision**: paquete `crediagil` en `src/crediagil/` (layout `src/`).
  - `policy/` contiene parámetros, cuota y reglas.
  - `extraction/` contiene esquemas e ingreso verificado.
  - Los tests van junto al código (`src/crediagil/**/test_*.py`), como pide `.claude/rules/tests.md`.
  - Se añade `src` a `testpaths` y a `pythonpath` de pytest.
- **Rationale**:
  - Es el primer código del agente.
  - `src/` lo protege `require_specs`.
  - Los issues #4–#6 importarán este paquete.
- **Alternatives considered**: `tests/` aparte. Se descarta porque la regla del repo exige
  tests junto al código.

## R2. Única fuente de parámetros (FR-001, FR-002)

- **Decision**: `src/crediagil/policy/params.py` define como constantes:
  - `TASA_MENSUAL`;
  - `MONTO_MAXIMO_PREAPROBACION`;
  - `PROPORCION_MAXIMA_CUOTA_INGRESO`;
  - `DISCREPANCIA_MAXIMA_INGRESO`;
  - `PLAZO_MINIMO_MESES` y `PLAZO_MAXIMO_MESES`.

  Todos son `Decimal` o `int` y es el único módulo que los define; el resto los importa.

  `test_params.py` lee `.specify/memory/constitution.md` y comprueba que la tasa (`1,8%
  mensual`) y los umbrales (`$5.000.000`, `30%`, `10%`) coinciden con las constantes. Si alguien
  cambia una constante sin enmendar la constitución, el test falla (SC-005).
- **Rationale**:
  - El Principio II pide garantía en código.
  - La constitución es la fuente normativa y el módulo es la fuente en código.
  - El test mantiene ambas sincronizadas.
- **Alternatives considered**:
  - Un archivo de configuración (YAML/env): permitiría cambiarlos sin código, y el Principio I
    lo prohíbe.
  - Leer la constitución en tiempo de ejecución: frágil, y acopla el agente a un documento.

## R3. Aritmética de dinero y redondeo

- **Decision**:
  - Todo cálculo con `decimal.Decimal`, con contexto de 28 dígitos.
  - La cuota usa el sistema francés, `M·i / (1 − (1+i)^−n)`, redondeada al peso con
    `ROUND_HALF_UP`.
  - Montos e ingresos son enteros de pesos (`int` o `Decimal` sin decimales).
- **Verificación**: $4.000.000, 1,8%, 24 meses → 206.723,34… → **$206.723**.
- **Comparaciones sin división**, para que los bordes sean exactos:
  - regla 2: `cuota ≤ PROPORCION · ingreso`;
  - regla 3: `|declarado − verificado| > DISCREPANCIA · verificado`.
- **Alternatives considered**: `float`. Se descarta porque da errores de representación justo
  en los bordes (p. ej. 30% exacto).

## R4. Esquemas de extracción

- **Decision**: Pydantic v2 (dependencia nueva, la pide el issue).
  - `CampoExtraido[T]` es genérico con `valor: T` y `fragmento: str` (no vacío), con
    `extra="forbid"`. Un campo ausente es `None` en el modelo del documento (dato faltante).
    Un dict con valor y sin fragmento, o con fragmento vacío, falla la validación.
  - Los documentos son una unión discriminada por `tipo`:
    - `certificado_laboral`;
    - `extracto_bancario`;
    - `no_soportado`.
  - Fragmento literal (FR-010): se valida pasando el texto del documento por el contexto de
    validación, `Documento.validar(datos, texto)` →
    `model_validate(..., context={"texto": texto})`. Un validador recorre los campos y exige
    `fragmento in texto`, sin normalizar. Sin texto en el contexto, la validación falla, para
    que nadie se salte la comprobación.
- **Rationale**: los esquemas los usará el subagente extractor (#7) como salida estructurada;
  Pydantic genera el JSON Schema.
- **Alternatives considered**: `dataclasses` con validación manual. Se descarta porque obliga a
  escribir el JSON Schema a mano para el extractor.

## R5. Decisión y motivos

- **Decision**: la evaluación devuelve `Decision` (enum) con tres valores: `PREAPROBABLE`,
  `ANALISTA` y `FUERA_DE_POLITICA`. Junto a ella va una lista de `Motivo` con regla, mensaje y
  valores.
  - `evaluar_preaprobacion(monto, plazo_meses, ingreso_verificado | None)` aplica la regla 2.
  - `evaluar_discrepancia(declarado, verificado)` aplica la regla 3.
  - `contrastar_nomina(salario, extractos)` detecta la inconsistencia documental.
  - `evaluar_solicitud(...)` combina las tres: si algo es fuera de política, gana
    `FUERA_DE_POLITICA`; si algo va a analista, gana `ANALISTA`.
  - Entradas inválidas lanzan `ValueError` con motivo: plazo fuera de 6–60 o no entero, monto
    ≤ 0.
- **Rationale**: los hooks del SDK (#6) y las herramientas MCP (#5) necesitan decisión y
  motivos trazables (FR-007).

## R6. Ingreso verificado (FR-012–FR-014)

- **Decision**: `derivar_ingreso(certificado | None, extractos)` devuelve `ResultadoIngreso`,
  con `ingreso: IngresoVerificado | None` y `hallazgos: list[Hallazgo]`.
  - Sin certificado o sin salario: `ingreso=None` más el hallazgo `DATO_FALTANTE`. Nunca usa
    los extractos.
  - Moneda distinta de `COP`, en el certificado o en un extracto: hallazgo
    `FUERA_DE_POLITICA`.
  - Inconsistencia: el promedio de los abonos de nómina de todos los extractos difiere del
    salario en más de 10%. Sin abonos de nómina no se evalúa. El borde exacto de 10% no se
    marca.
  - `IngresoVerificado` conserva valor, moneda y el `CampoExtraido` del salario (documento y
    fragmento de origen, Principio VI).

## R7. Datos de prueba y hooks

- **Decision**:
  - Los textos de documentos son ficticios.
  - Las líneas con forma de cédula o cuenta junto a su etiqueta llevan
    `# pragma: dato-ficticio`, o se construyen en tiempo de ejecución para que
    `block_sensitive_data` no bloquee.
  - Ningún número con forma de tarjeta.
- **Orden**: `require_specs` exige `spec.md`, `plan.md` y `tasks.md` no vacíos antes de
  escribir en `src/`, así que la implementación empieza después de `/speckit-tasks`.
