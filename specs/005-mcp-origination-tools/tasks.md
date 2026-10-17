# Tasks: Servidor MCP: herramientas de originación

**Input**: Design documents from `specs/005-mcp-origination-tools/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/tools.md](./contracts/tools.md), [quickstart.md](./quickstart.md)

**Tests**: obligatorios (FR-019, Principio VII).

- Van junto al código, se escriben primero y deben fallar.
- Usan `tmp_path` para el estado.
- Los documentos de prueba son textos ficticios construidos con helpers, con pragma si una línea tiene forma "documento + número".
- Cada historia expone su herramienta en `server.py` y la prueba en `test_server.py`. Como esos dos archivos son compartidos, esas tareas van en secuencia entre historias.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: paralelizable (archivo distinto, sin dependencias pendientes)
- **[Story]**: historia de spec.md (US1–US4)

---

## Phase 1: Setup

- [X] T001 Comprobar que el punto de partida está limpio: `uv run pytest` en verde (311) y `.specify/feature.json` apuntando a `specs/005-mcp-origination-tools`. No hay dependencias nuevas.

---

## Phase 2: Foundational (bloquea US1–US4)

**Purpose**: ajustes a #3 y #4 que necesitan todas las historias (research R1–R4).

- [X] T002 [P] Hacer que el error de fragmento no literal tenga un tipo propio, en `src/crediagil/extraction/schemas.py`.
  - **Test primero**, en `src/crediagil/extraction/test_schemas.py`. Un fragmento no literal produce un `ValidationError` cuyo `errors()[0]["type"] == "fragmento_no_literal"`, con `ctx["campo"]` igual al nombre del campo. Validar sin texto da el tipo `texto_faltante`. Los tests existentes (que buscan el nombre del campo en el mensaje) deben seguir pasando.
  - **Implementación**: lanzar `PydanticCustomError("fragmento_no_literal", "El fragmento de '{campo}' no aparece literalmente en el documento: {fragmento}", {...})` y `PydanticCustomError("texto_faltante", ...)` en `DocumentoBase.fragmentos_literales`.
- [X] T003 [P] Hacer configurable el campo `reintentable` de `ErrorCore`, en `src/crediagil/mcp_server/errores.py` (FR-001a).
  - **Test primero**, en `src/crediagil/mcp_server/test_errores.py`:
    - `ErrorCore(VALIDACION, "EXTRACCION_INVALIDA", ..., reintentable=True).reintentable is True`, y lo mismo con `FRAGMENTO_NO_LITERAL`.
    - `reintentable=True` con `VALIDACION`/`PARAMETROS_INVALIDOS`, con `NEGOCIO` o con `PERMISOS` lanza `ValueError`.
    - `TRANSITORIO` es reintentable siempre.
    - `fallo()` refleja el valor.
  - **Implementación**:
    - Parámetro `reintentable: bool | None = None`.
    - Constante `CODIGOS_VALIDACION_REINTENTABLES = {"EXTRACCION_INVALIDA", "FRAGMENTO_NO_LITERAL"}`.
    - Si el valor no es `None` y la combinación no está permitida, lanza `ValueError`.
- [X] T004 Pasar el estado a v2, en `src/crediagil/mcp_server/estado.py`.
  - **Test primero**, en `src/crediagil/mcp_server/test_estado.py`:
    - La semilla nueva tiene `version == 2`, `solicitudes == {}`, `escalamientos == {}` y `verificado_en is None` en cada solicitante.
    - Un archivo v1 escrito a mano (sin esas claves) se carga con ellas añadidas y, tras una `transaccion()`, queda guardado como v2 sin perder `intentos_fallidos` ni `bloqueado`.
    - `siguiente_id(datos["solicitudes"], "SLC")` da `SLC-0001` y luego `SLC-0002`.
  - **Implementación**: `VERSION = 2`; `_migrar(datos)` dentro de `_cargar`; la función `siguiente_id(coleccion, prefijo) -> str` (formato `{prefijo}-{n:04d}`).
- [X] T005 Guardar la constancia de verificación, en `src/crediagil/mcp_server/identidad.py` (FR-007).
  - **Test primero**, en `src/crediagil/mcp_server/test_identidad.py`:
    - Una verificación exitosa guarda `verificado_en` (texto ISO con zona UTC).
    - Un 3.er fallo (bloqueo) lo deja en `None`.
    - `identidad_vigente(s)` es `True` solo si `verificado_en` no es nulo y el solicitante no está bloqueado; se prueban las 3 combinaciones.
    - Un fallo de verificación con 0 o 1 fallos previos no borra una verificación anterior.
  - **Implementación**: `verificar_identidad` acepta `ahora: datetime | None = None` (por defecto `datetime.now(UTC)`) y guarda el valor; se añade `identidad_vigente(solicitante) -> bool`.
- [X] T006 [P] Actualizar `specs/004-mcp-applicant-identity/contracts/tools.md` y su `data-model.md`. Documentar:
  - `verificado_en`;
  - la regla de reintento FR-001a: `validacion` reintentable solo en `EXTRACCION_INVALIDA` y `FRAGMENTO_NO_LITERAL`;
  - que el estado es v2.

**Checkpoint**: `uv run pytest` en verde, con los tests de #3 y #4 intactos salvo los ampliados.

---

## Phase 3: User Story 1 - Validar una extracción (Priority: P1) 🎯 MVP

**Goal**: `validar_extraccion` con errores específicos y reintentables.

**Independent Test**: `uv run pytest src/crediagil/mcp_server/test_originacion.py -k extraer` y los casos de `validar_extraccion` en `test_server.py`.

- [X] T007 [US1] Escribir `src/crediagil/mcp_server/test_originacion.py` (sección extracción):
  - Helpers `texto_certificado(salario, moneda="COP")`, `certificado(salario=..., moneda=...)` y `extracto(*abonos)`, que construyen datos y texto ficticios coherentes, como en `extraction/test_income.py`.
  - Casos de `extraer(datos, texto)`:
    - Certificado válido: devuelve `(documento, datos_faltantes)` con los campos nulos listados.
    - `no_soportado`: el documento es `DocumentoNoSoportado`.
    - Fragmento no literal: `ErrorCore` `validacion`/`FRAGMENTO_NO_LITERAL`, `reintentable is True`, `detalles["campos"]` contiene `"salario_mensual"`.
    - Valor sin fragmento, campo extra, salario 0 o tipo desconocido: `EXTRACCION_INVALIDA` reintentable, con `detalles["errores"]` de `{campo, motivo}`.
- [X] T008 [US1] Implementar `extraer(datos, texto)` en `src/crediagil/mcp_server/originacion.py`.
  - Llama a `crediagil.extraction.validar_documento`.
  - Convierte el `ValidationError` según research R2:
    - `type == "fragmento_no_literal"`: `FRAGMENTO_NO_LITERAL`, con `campos` sacados de `ctx`;
    - cualquier otro: `EXTRACCION_INVALIDA`, con `campo` formado por la `loc` unida con "." y sin el discriminador, y con `motivo` igual a `msg`.
  - Los dos errores van con `reintentable=True`.
  - `datos_faltantes` son los campos `CampoExtraido` que quedan en `None`.

  Hacer pasar T007.
- [X] T009 [US1] Exponer `validar_extraccion(datos: dict, texto: str)` en `src/crediagil/mcp_server/server.py`, con la descripción exacta de contracts/tools.md. Devuelve `exito(extraccion=doc.model_dump(mode="json"), datos_faltantes=[...], politica_no_cubre=<bool>)`. Añadir sus casos a `src/crediagil/mcp_server/test_server.py`: éxito, `FRAGMENTO_NO_LITERAL` con `reintentable: True` y `politica_no_cubre: True`.

---

## Phase 4: User Story 2 - Registrar con procedencia y evaluar (Priority: P1)

**Goal**: `registrar_solicitud` exige identidad, guarda la procedencia y devuelve la evaluación.

**Depends on**: Foundational y US1 (`extraer`).

**Independent Test**: `uv run pytest src/crediagil/mcp_server/test_originacion.py -k registrar`.

- [X] T010 [US2] Añadir a `src/crediagil/mcp_server/test_originacion.py` los casos de registro.
  - **Preparación**: fixture `verificado` que ejecuta `verificar_identidad` de SOL-0001 con la fecha de la semilla.
  - **Identidad**: sin verificar, con el solicitante bloqueado o con un id inexistente → `permisos`/`IDENTIDAD_NO_VERIFICADA`; el archivo de estado no cambia.
  - **Bordes de la regla 2** (certificado + declarado = salario, monto 5.000.000 a 12 meses):
    - salario 1.556.700 → `preaprobable_automaticamente: True`, `decision: "preaprobable"`, `cuota: 467010`, sin causas;
    - salario 1.556.699 → `False`, causa con `regla: "regla_2"`;
    - salario 1.556.701 → `True`;
    - monto 5.000.001 (salario 10.000.000) → causa `regla_2`.
  - **Bordes de la regla 3** (4.000.000 a 24 meses, salario 2.000.000):
    - declarado 2.200.000 y 1.800.000 → preaprobable;
    - 2.200.001 y 1.799.999 → causa `regla_3`.
  - **Hallazgos de ingreso**:
    - nómina 2.200.001 → `decision: "analista"`, causa `nomina`;
    - certificado en USD → registrada con `decision: "fuera_de_politica"`;
    - sin certificado o con salario nulo → `negocio`/`INGRESO_NO_VERIFICABLE`, `reintentable is False`, `"salario_mensual" in detalles["datos_faltantes"]`, sin guardar nada.
  - **Errores de entrada**:
    - extracción inválida → el mismo error de US1, sin guardar nada;
    - monto 0, plazo 61 o declarado −1 → `validacion`/`PARAMETROS_INVALIDOS`, no reintentable.
  - **Procedencia** de lo guardado:
    - `estado == "REGISTRADA"`;
    - cada elemento de `datos` tiene `id_documento` y un `fragmento` que está en el texto enviado;
    - aparece `abonos_nomina[0]`;
    - `ingreso_verificado` lleva `id_documento` y `fragmento`.
  - **Identificadores**: dos registros dan `SLC-0001` y `SLC-0002`.
- [X] T011 [US2] Implementar en `src/crediagil/mcp_server/originacion.py` la función `registrar_solicitud(almacen, id_solicitante, monto, plazo_meses, ingreso_declarado, documentos, ahora=None) -> dict`, siguiendo research R5:
  1. Comprueba la identidad vigente leyendo el estado.
  2. Valida monto y plazo con `crediagil.policy.cuota.validar_monto` y `validar_plazo`, y que el ingreso declarado sea un entero ≥ 0. Si falla: `PARAMETROS_INVALIDOS`.
  3. Llama a `extraer` por cada documento `{id_documento, datos, texto}` (lista no vacía e `id_documento` no vacío y único; si no, `PARAMETROS_INVALIDOS`).
  4. Llama a `derivar_ingreso`. Si no hay ingreso y no hay hallazgo `FUERA_DE_POLITICA`: `INGRESO_NO_VERIFICABLE` con `datos_faltantes` tomados de los campos de los hallazgos `DATO_FALTANTE`.
  5. Calcula la evaluación con `combinar`.
  6. Dentro de una `transaccion()`, vuelve a comprobar la identidad, asigna `SLC-NNNN` y guarda la solicitud según data-model.md.
  7. Devuelve `{"id_solicitud", "evaluacion"}`.

  Funciones auxiliares: `_datos_con_procedencia(documento, id_documento)` y `_evaluacion(resultado)`.

  Hacer pasar T010.
- [X] T012 [US2] Exponer `registrar_solicitud(id_solicitante: str, monto: int, plazo_meses: int, ingreso_declarado: int, documentos: list[dict])` en `src/crediagil/mcp_server/server.py`, con la descripción de contracts/tools.md. Añadir a `test_server.py`: registro sin identidad → `permisos`; registro preaprobable → `ok` con `evaluacion`.

---

## Phase 5: User Story 3 - Simular y preaprobar con revalidación (Priority: P1)

**Goal**: `calcular_capacidad_pago` sin efectos y `preaprobar_credito` con defensa en profundidad.

**Depends on**: US2 (para preaprobar hace falta una solicitud registrada).

**Independent Test**: `uv run pytest src/crediagil/mcp_server/test_originacion.py -k "simular or preaprobar"`.

- [X] T013 [US3] Añadir a `src/crediagil/mcp_server/test_originacion.py`:
  - **`simular`**:
    - (4.000.000, 24) → `cuota == 206723`, `tasa_mensual == "0.018"`;
    - con 5.000.000/12 e ingreso 1.556.700 → `proporcion_cuota_ingreso == "0.3000"` y `dentro_de_proporcion_maxima is True`; con 1.556.699 → `False`;
    - plazo 61 → `PARAMETROS_INVALIDOS`;
    - el archivo de estado no existe ni se crea, porque no se usa almacén.
  - **`preaprobar_credito`**:
    - solicitud preaprobable → estado `PREAPROBADA` con `monto`, `plazo_meses`, `cuota` y `tasa_mensual`; una segunda llamada da el mismo resultado;
    - bloquear al solicitante después de registrar (3 fallos) → `permisos`/`IDENTIDAD_NO_VERIFICADA`, con el estado sin cambios;
    - solicitud con causa `regla_2` (salario 1.556.699) → `negocio`/`NO_PREAPROBABLE` con `detalles["causas"]`;
    - solicitud con causa `regla_3` (declarado 2.200.001) → `NO_PREAPROBABLE`;
    - solicitud escalada (estado puesto a `ESCALADA` en una transacción) → `SOLICITUD_ESCALADA`;
    - id inexistente → `SOLICITUD_NO_ENCONTRADA`;
    - **defensa en profundidad**: si se edita en el estado la evaluación guardada de una solicitud con causa `regla_2` para marcarla preaprobable, `preaprobar_credito` sigue dando `NO_PREAPROBABLE`.
- [X] T014 [US3] Implementar en `src/crediagil/mcp_server/originacion.py`:
  - `simular(monto, plazo_meses, ingreso_mensual=None) -> dict`: proporción con `Decimal`, redondeada a 4 decimales y devuelta como texto; `dentro_de_proporcion_maxima` como `cuota <= PROPORCION_MAXIMA_CUOTA_INGRESO * ingreso`; el ingreso debe ser un entero > 0 si se envía.
  - `preaprobar_credito(almacen, id_solicitud, ahora=None) -> dict`, según research R6. Recalcula desde los datos guardados y reconstruye los `Hallazgo` guardados con `TipoHallazgo(h["tipo"])`; nunca usa `evaluacion` guardada para decidir.

  Hacer pasar T013.
- [X] T015 [US3] Exponer en `src/crediagil/mcp_server/server.py` las herramientas `calcular_capacidad_pago(monto: int, plazo_meses: int, ingreso_mensual: int | None = None)` y `preaprobar_credito(id_solicitud: str)`, con las descripciones exactas de contracts/tools.md. En `test_server.py`:
  - la descripción de simular contiene "SOLO SIMULA";
  - la de preaprobar contiene "COMPROMETE A CREDIÁGIL" y "calcular_capacidad_pago";
  - un flujo verificar → registrar → preaprobar da `ok`.

---

## Phase 6: User Story 4 - Escalar con resumen completo (Priority: P1)

**Goal**: `escalar_a_analista` con un resumen validado.

**Depends on**: Foundational. La lógica es independiente de US1–US3; la exposición en `server.py` va después de T015.

**Independent Test**: `uv run pytest src/crediagil/mcp_server/test_escalamiento.py`.

- [X] T016 [P] [US4] Escribir `src/crediagil/mcp_server/test_escalamiento.py`.
  - **Helper**: `resumen(**cambios)` arma un resumen completo y ficticio, con 1 dato `{campo, valor, documento, fragmento}`.
  - **Casos válidos**:
    - completo y sin solicitud → `ESC-0001`, guardado con `creado_en`;
    - `solicitud_humano` con `monto: None`, `plazo: None`, `datos: []` y `discrepancias: []` → válido.
  - **`RESUMEN_INCOMPLETO`** (`validacion`, no reintentable), con el campo dentro de `campos_faltantes`:
    - falta cualquiera de las 8 claves (parametrizado);
    - `solicitante`, `detalle` o `accion_recomendada` vacíos o solo espacios;
    - `causa` desconocida;
    - un dato sin `fragmento` o con `documento` vacío;
    - una clave extra.
  - **Con solicitud asociada** (creada directamente en el estado):
    - queda `ESCALADA`, con `escalada_en`;
    - si estaba `PREAPROBADA` → `negocio`/`SOLICITUD_PREAPROBADA`;
    - si no existe → `SOLICITUD_NO_ENCONTRADA`.
- [X] T017 [P] [US4] Implementar `src/crediagil/mcp_server/escalamiento.py`:
  - `ResumenEscalamiento` (Pydantic, `extra="forbid"`, todas las claves sin valor por defecto) con:
    - `solicitante`, `detalle` y `accion_recomendada` como `str` con al menos un carácter no blanco;
    - `monto: PositiveInt | None` y `plazo: PositiveInt | None` (estricto, sin coerción);
    - `datos: list[DatoResumen]` y `discrepancias: list[str]`;
    - `causa: Literal["solicitud_humano", "fuera_de_politica", "regla_2", "regla_3", "ingreso_no_verificable", "inconsistencia_documental", "identidad_bloqueada", "otro"]`.
  - `escalar_a_analista(almacen, resumen: dict, id_solicitud=None, ahora=None) -> dict` convierte el `ValidationError` en `RESUMEN_INCOMPLETO` con `campos_faltantes` (la primera parte de cada `loc`, sin duplicados) y, en una sola transacción, comprueba la solicitud y guarda el escalamiento.

  Hacer pasar T016.
- [X] T018 [US4] Exponer `escalar_a_analista(resumen: dict, id_solicitud: str | None = None)` en `src/crediagil/mcp_server/server.py`, con la descripción de contracts/tools.md, y añadir sus casos a `test_server.py`: completo → `ok` con `id_escalamiento`; incompleto → `RESUMEN_INCOMPLETO`.

---

## Phase 7: Polish & Cross-Cutting

- [X] T019 Actualizar `src/crediagil/mcp_server/test_server_stdio.py` (`list_tools` con exactamente 7 herramientas) y la prueba de `list_tools` de `test_server.py` (7 herramientas, todas con descripción en español no vacía).
- [X] T020 [P] Añadir a la línea "Core de originación simulado" de `CLAUDE.md` las 5 herramientas nuevas, y que solo `preaprobar_credito` compromete.
- [X] T021 Ejecutar `uv run pytest`, `uv run ruff check` y `uv run ruff format --check`; todo en verde.
- [X] T022 Repetir el flujo manual 1, 2 y 6 de quickstart.md con un script que use las funciones de `originacion.py` sobre `$TEMP`. Los pasos 3–5 en un cliente MCP quedan para el usuario.

---

## Trabajo futuro (revisión de `/open-pr 5`, no bloqueante)

- Hooks del Agent SDK para las reglas 1 y 2 (#6) y ticket de escalamiento en GitHub (#7).
- Escalar dos veces una solicitud ya `ESCALADA`: hoy crea otro escalamiento; decidir y documentar.
- `_migrar` del estado: rechazar versiones futuras o desconocidas y registros mal formados con
  `ESTADO_ILEGIBLE`.
- Idempotencia de `preaprobar_credito` cuando el solicitante se bloquea después de preaprobar:
  hacerlo explícito en la spec.
- Comprobar que los documentos pertenecen al solicitante verificado (nombre del certificado).
- Decidir si `ingreso_declarado == 0` equivale a "ausente".

---

## Dependencies & Execution Order

```text
Setup (T001) → Foundational (T002–T006)
                    ├─▶ US1 (T007–T009)  🎯 MVP
                    │      └─▶ US2 (T010–T012)
                    │             └─▶ US3 (T013–T015)
                    └─▶ US4 lógica (T016–T017) ∥ US1–US3
                                     └─▶ T018 (server.py, tras T015)
                                              └─▶ Polish (T019–T022)
```

- US1, US2 y US3 comparten `originacion.py`, `test_originacion.py`, `server.py` y `test_server.py`, así que van en secuencia.
- La lógica de US4 (`escalamiento.py` y su test) es paralela a US1–US3.

## Parallel Opportunities

- T002 ∥ T003 ∥ T006; T004 y T005 van en secuencia (T005 usa el estado v2).
- T016 + T017 (US4) ∥ T007–T015.
- T020 ∥ T019.

## Implementation Strategy

1. **Foundational**: reintento, estado v2 y constancia de verificación.
2. **MVP (US1)**: validar extracciones, porque el agente las necesita antes que nada.
3. **US2**: registrar y evaluar; aquí están el núcleo de las reglas y la procedencia.
4. **US3**: simular y preaprobar con revalidación.
5. **US4**: escalar.
6. **Polish**: listado completo, documentación, suite completa y quickstart.
