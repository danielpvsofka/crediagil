# Tasks: Política de crédito y esquemas de extracción

**Input**: Design documents from `specs/003-credit-policy-extraction/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: obligatorios (spec FR-015, constitución Principio VII). Van junto al código en
`src/crediagil/**/test_*.py`, se escriben antes de la implementación y deben fallar primero.
Solo datos ficticios: una línea con forma de cédula o cuenta junto a su etiqueta lleva
`# dato-ficticio`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: paralelizable (archivo distinto, sin dependencias pendientes)
- **[Story]**: historia de spec.md (US1–US3)

---

## Phase 1: Setup

- [X] T001 Actualizar `pyproject.toml`:
  - `dependencies = ["pydantic>=2"]`;
  - build backend `hatchling` con `[tool.hatch.build.targets.wheel] packages = ["src/crediagil"]`;
  - `[tool.pytest.ini_options] testpaths = [".claude/hooks", "src"]` y `pythonpath = ["src"]`.

  Después ejecutar `uv sync --group dev` y confirmar que `uv run python -c "import pydantic"` funciona.
- [X] T002 Crear los paquetes vacíos `src/crediagil/__init__.py`, `src/crediagil/policy/__init__.py` y `src/crediagil/extraction/__init__.py`, cada uno con un docstring de una línea en español.

---

## Phase 2: Foundational (bloquea US1–US3)

**Purpose**: la única fuente de parámetros (FR-001, FR-002).

- [X] T003 [P] Escribir `src/crediagil/policy/test_params.py`:
  - Leer `.specify/memory/constitution.md` desde la raíz del repo (`Path(__file__).parents[3]`).
  - Extraer con regex la tasa (`(\d+,\d+)% mensual`) y los umbrales (`\$5\.000\.000`, `30%`, `10%`).
  - Afirmar que coinciden con `TASA_MENSUAL == Decimal("0.018")`, `MONTO_MAXIMO_PREAPROBACION == 5_000_000`, `PROPORCION_MAXIMA_CUOTA_INGRESO == Decimal("0.30")` y `DISCREPANCIA_MAXIMA_INGRESO == Decimal("0.10")`.

  Los valores se derivan del texto: convertir "1,8" a `Decimal("0.018")`, sin comparar contra literales duplicados. Afirmar también `PLAZO_MINIMO_MESES == 6`, `PLAZO_MAXIMO_MESES == 60` (spec FR-004) y `MONEDA == "COP"`.
- [X] T004 Crear `src/crediagil/policy/params.py` con las constantes de data-model.md (`TASA_MENSUAL`, `MONTO_MAXIMO_PREAPROBACION`, `PROPORCION_MAXIMA_CUOTA_INGRESO`, `DISCREPANCIA_MAXIMA_INGRESO`, `PLAZO_MINIMO_MESES`, `PLAZO_MAXIMO_MESES`, `MONEDA`). Docstring: "Única definición en código; debe coincidir con la constitución (test_params.py)". Hacer pasar T003.

**Checkpoint**: `uv run pytest src -k params` en verde.

---

## Phase 3: User Story 1 - Calcular la cuota y decidir la preaprobación (Priority: P1) 🎯 MVP

**Goal**: cuota por sistema francés y regla 2 (más regla 3 y `combinar`, que comparten
`Resultado`).

**Independent Test**: `uv run pytest src/crediagil/policy` con todos los casos de
[contracts/policy.md](./contracts/policy.md).

### Tests (primero; deben fallar)

- [X] T005 [P] [US1] Escribir `src/crediagil/policy/test_cuota.py` con la tabla de contracts/policy.md:
  - (4.000.000, 24) → 206.723;
  - (4.000.000, 6) → 709.291;
  - (4.000.000, 60) → 109.568;
  - (5.000.000, 12) → 467.010;
  - `ValueError` para plazo 5 y 61, plazo no entero (`12.0`, `True`), monto 0 y monto negativo.
- [X] T006 [P] [US1] Escribir `src/crediagil/policy/test_reglas.py`:
  - **Regla 2**, casos de contracts/policy.md:
    - 5.000.000/12/1.556.700 → `PREAPROBABLE` con `motivos == []`;
    - 5.000.000/12/1.556.699 → `ANALISTA`;
    - 5.000.001/12/10.000.000 → `ANALISTA`;
    - 4.999.999/12/10.000.000 → `PREAPROBABLE`;
    - ingreso `None` y 0 → `ANALISTA`, sin excepción.
  - **Regla 3**, verificado 2.000.000:
    - declarado 2.200.000 y 1.800.000 → `PREAPROBABLE`;
    - 2.200.001 y 1.799.999 → `ANALISTA`;
    - verificado 0 → `ValueError`.
  - **`combinar`**: precedencia `FUERA_DE_POLITICA` > `ANALISTA` > `PREAPROBABLE`, motivos concatenados y cuota del primero que la tenga.
  - Cada `ANALISTA` incluye un `Motivo` con `regla` `"regla_2"` o `"regla_3"` y los valores comparados.

### Implementación

- [X] T007 [US1] Implementar `src/crediagil/policy/cuota.py`:
  - Firma `calcular_cuota(monto: int, plazo_meses: int) -> int`.
  - `Decimal` con fórmula `M·i / (1 − (1+i)^−n)` y `quantize(Decimal(1), ROUND_HALF_UP)`.
  - Valida `type(plazo_meses) is int` (rechaza bool y float) y `PLAZO_MINIMO_MESES ≤ plazo ≤ PLAZO_MAXIMO_MESES`, y `monto > 0`. Si no, lanza `ValueError` con motivo en español.
  - Importa los parámetros de `params.py`. Hacer pasar T005.
- [X] T008 [US1] Implementar `src/crediagil/policy/reglas.py`:
  - `Decision(StrEnum)`, más `Motivo` y `Resultado` como `@dataclass(frozen=True)`.
  - `evaluar_preaprobacion`: condiciones exactas sin división, `cuota ≤ PROPORCION_MAXIMA_CUOTA_INGRESO · ingreso`. Un ingreso `None` o ≤ 0 añade el motivo "sin ingreso verificado".
  - `evaluar_discrepancia`: `|declarado − verificado| > DISCREPANCIA_MAXIMA_INGRESO · verificado` → `ANALISTA`.
  - `combinar(*resultados)`.

  Hacer pasar T006.

**Checkpoint**: US1 completa e independiente: cuota y reglas 2 y 3 con todos los bordes.

---

## Phase 4: User Story 2 - Extraer datos sin inventarlos (Priority: P1)

**Goal**: esquemas `{valor, fragmento}` con validación literal y documentos discriminados.

**Independent Test**: `uv run pytest src/crediagil/extraction/test_schemas.py` con los casos de
[contracts/extraction.md](./contracts/extraction.md).

### Tests (primero; deben fallar)

- [X] T009 [P] [US2] Escribir `src/crediagil/extraction/test_schemas.py`:
  - **Texto de prueba**: un certificado laboral ficticio, p. ej. "Empresa Ficticia S.A.S. certifica que Ana Prueba devenga un salario de $2.500.000 COP mensuales…", y un extracto ficticio con dos abonos "NOMINA EMPRESA FICTICIA".
  - **Casos de la tabla de contracts/extraction.md**:
    - campo completo y literal → válido;
    - sin fragmento → error;
    - fragmento vacío → error;
    - fragmento no literal (espacio de más y mayúsculas distintas) → error que nombra el campo;
    - campo `None` → válido;
    - campo extra `confianza` → error;
    - `tipo: "pasaporte"` → error;
    - validación sin contexto → error "falta el texto del documento";
    - `no_soportado` válido con solo `tipo_detectado`.
  - **JSON Schema**: comprobar que `TypeAdapter(Documento).json_schema()` se genera, porque lo usará el extractor (#7).

### Implementación

- [X] T010 [US2] Implementar `src/crediagil/extraction/schemas.py`:
  - **`CampoExtraido[T]`**: `BaseModel` genérico con `model_config = ConfigDict(extra="forbid")`, `valor: T` y `fragmento: str = Field(min_length=1)`.
  - **`CertificadoLaboral`**: `tipo: Literal["certificado_laboral"]`, más `empleador`, `nombre_empleado`, `salario_mensual: CampoExtraido[int] | None`, `moneda` y `fecha_expedicion: CampoExtraido[date] | None`. Todos `CampoExtraido[...] | None`.
  - **`ExtractoBancario`**: `tipo: Literal["extracto_bancario"]`, más `titular`, `periodo`, `moneda` y `abonos_nomina: list[CampoExtraido[int]] = []`.
  - **`DocumentoNoSoportado`**: `tipo: Literal["no_soportado"]` y `tipo_detectado: str`.
  - **`Documento`**: `Annotated[... | ... | ..., Field(discriminator="tipo")]`.
  - **Fragmento literal**: un `model_validator(mode="after")` en cada documento recorre sus `CampoExtraido` (incluidos los de listas) y exige `info.context["texto"]`. Sin contexto → error "falta el texto del documento"; fragmento no contenido literalmente → error con el nombre del campo.
  - **`validar_documento(datos, texto)`**: usa `TypeAdapter(Documento).validate_python(datos, context={"texto": texto})`.

  Hacer pasar T009.

**Checkpoint**: US2 completa e independiente.

---

## Phase 5: User Story 3 - Derivar el ingreso verificado y detectar discrepancias (Priority: P1)

**Goal**: ingreso verificado solo desde el salario certificado, con hallazgos.

**Depends on**: US1 (`Resultado`, `Decision`, parámetros) y US2 (esquemas).

**Independent Test**: `uv run pytest src/crediagil/extraction/test_income.py`.

### Tests (primero; deben fallar)

- [X] T011 [US3] Escribir `src/crediagil/extraction/test_income.py` con la tabla de contracts/extraction.md:
  - certificado 2.000.000 COP → ingreso 2.000.000 con `origen` igual al campo salario;
  - sin certificado y con extractos con nómina → `None` más `DATO_FALTANTE` (`campo="salario_mensual"`);
  - certificado sin salario más extractos → `None` más `DATO_FALTANTE`, sin usar los extractos;
  - moneda `USD` → `FUERA_DE_POLITICA`;
  - `no_soportado` más certificado → `FUERA_DE_POLITICA` (documento);
  - nómina promedio 2.200.000 → sin hallazgo;
  - 2.200.001 y 1.799.999 → `INCONSISTENCIA_DOCUMENTAL`;
  - extracto sin abonos → sin hallazgo;
  - `resultado_de_hallazgos`: `FUERA_DE_POLITICA` → `FUERA_DE_POLITICA`, `DATO_FALTANTE` → `ANALISTA`, ninguno → `PREAPROBABLE`.

  Construir los documentos con `validar_documento` y textos ficticios.

### Implementación

- [X] T012 [US3] Implementar `src/crediagil/extraction/income.py`:
  - `TipoHallazgo(StrEnum)`, más `Hallazgo`, `IngresoVerificado` y `ResultadoIngreso` como `@dataclass(frozen=True)`.
  - `derivar_ingreso(documentos)` sigue el flujo de data-model.md:
    - `no_soportado` → `FUERA_DE_POLITICA`;
    - sin certificado o sin salario → `DATO_FALTANTE`, nunca usa extractos;
    - moneda distinta de `MONEDA` → `FUERA_DE_POLITICA`;
    - promedio de `abonos_nomina` de todos los extractos con `|promedio − salario| > DISCREPANCIA_MAXIMA_INGRESO · salario` → `INCONSISTENCIA_DOCUMENTAL`, comparando con `Decimal` sin dividir el umbral; sin abonos no se evalúa.
  - `resultado_de_hallazgos(r)` → `Resultado`, con un `Motivo` por hallazgo.

  Hacer pasar T011.

**Checkpoint**: las tres historias completas.

---

## Phase 6: Polish & Cross-Cutting

- [X] T013 [P] Reexportar la API pública en `src/crediagil/policy/__init__.py` y `src/crediagil/extraction/__init__.py` (con `__all__`).
- [X] T014 Ejecutar `uv run pytest` (suite completa), `uv run ruff check` y `uv run ruff format --check`; todo en verde.
- [X] T015 Ejecutar las comprobaciones 1–5 de quickstart.md. La 2 consiste en cambiar temporalmente `TASA_MENSUAL`, ver fallar `test_params.py` y revertir. La 3 es un `grep` de literales fuera de `params.py`, que debe salir vacío.
- [X] T016 Actualizar `CLAUDE.md`, sección "Stack y comandos": el código del agente vive en `src/crediagil/`, `pydantic` es dependencia, y la política se importa de `crediagil.policy` (nunca se redefinen parámetros). No repetir valores.

---

## Trabajo futuro (revisión de `/open-pr 3`, no bloqueante)

- Comprobar que el `valor` sale de su `fragmento` (al menos en montos: el número normalizado
  debe aparecer en el fragmento). Hoy solo se exige que el fragmento sea literal.
- Identificar el documento de origen en `IngresoVerificado` (Principio VI): los documentos aún
  no tienen identificador; resolver con el registro (#4/#5).
- Hacer cumplir las reglas 1 y 2 en hooks del Agent SDK (#6).
- Promedio de nómina por periodo (mes) en lugar de por abono, para nóminas quincenales.

---

## Dependencies & Execution Order

```text
Setup (T001–T002) → Foundational (T003–T004)
                         ├─▶ US1 (T005–T008)  🎯 MVP
                         ├─▶ US2 (T009–T010)
                         └─▶ US3 (T011–T012)  ← requiere US1 y US2
                                                    └─▶ Polish (T013–T016)
```

- US1 y US2 son independientes entre sí tras T004.
- US3 usa `Resultado` (US1) y los esquemas (US2).
- Dentro de cada historia: tests → implementación.

## Parallel Opportunities

- T003 junto con T002.
- Tras T004: T005 ∥ T006 ∥ T009, y luego T007/T008 (US1) ∥ T010 (US2).
- T013 ∥ T016.

```text
Agente A: T005 + T006 → T007 → T008   (US1)
Agente B: T009 → T010                  (US2)
Luego:    T011 → T012                  (US3)
```

## Implementation Strategy

1. **MVP**: Setup, Foundational y US1. Parámetros verificados, cuota y reglas 2 y 3, ya utilizables por los hooks del SDK (#6).
2. **US2**: esquemas para el extractor (#7).
3. **US3**: ingreso verificado, que conecta extracción y política.
4. **Polish**: API pública, suite completa, quickstart y `CLAUDE.md`.
