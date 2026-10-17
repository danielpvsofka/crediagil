# Feature Specification: Servidor MCP: herramientas de originación

**Feature Branch**: `develop` (sin hook de rama; directorio de spec: `specs/005-mcp-origination-tools`)

**Created**: 2026-10-17

**Status**: Draft

**Issue**: [#5](https://github.com/danielpvsofka/crediagil/issues/5) · **Depende de**: #4 (y #3) · **Habilita**: #6, #7

**Input**: User description: "Servidor MCP: herramientas de originación — El core debe permitir registrar solicitudes con procedencia de datos, simular cuotas, preaprobar y escalar. Las descripciones deben evitar que el modelo confunda simular con comprometer. Alcance: validar_extraccion, registrar_solicitud, calcular_capacidad_pago, preaprobar_credito y escalar_a_analista. Criterios: calcular_capacidad_pago se describe como 'SOLO SIMULA', no requiere identidad y no compromete nada; preaprobar_credito se describe como 'COMPROMETE A CREDIÁGIL' e indica cuándo usar la otra herramienta; registrar_solicitud exige identidad verificada (error de permisos si no) y guarda cada dato con documento y fragmento de origen; registrar_solicitud devuelve una evaluación con preaprobable_automaticamente y las causas de escalamiento; si el ingreso no es verificable, devuelve INGRESO_NO_VERIFICABLE no reintentable con los datos faltantes; validar_extraccion devuelve errores específicos y reintentables cuando el esquema o los fragmentos no cuadran; preaprobar_credito revalida identidad y umbrales en el core (defensa en profundidad); escalar_a_analista valida un resumen con solicitante, monto, plazo, datos con procedencia, discrepancias, causa, detalle y acción recomendada; un resumen incompleto se rechaza. Depende de #4. Issue: #5"

> **Nota de alcance**: nombres de herramientas, textos obligatorios de las descripciones
> ("SOLO SIMULA", "COMPROMETE A CREDIÁGIL") y códigos de error son contrato del issue. Las
> reglas de negocio se evalúan con `crediagil.policy` y `crediagil.extraction` (#3); el
> servidor y el contrato de respuesta son los de #4. Los parámetros de la constitución no se
> repiten aquí.

## User Scenarios & Testing *(mandatory)*

Actores: **agente de originación** (llama a las herramientas), **analista** (recibe los casos
escalados), **solicitante** (cuyos datos se registran).

### User Story 1 - Validar una extracción antes de registrarla (Priority: P1)

El agente envía los datos que extrajo de un documento junto con el texto del documento. El core
le dice si la extracción es válida o qué está mal, para que pueda corregirla y reintentar.

**Why this priority**: es la puerta para no inventar datos (Principio V); todo registro parte
de extracciones validadas.

**Independent Test**: validar extracciones ficticias correctas, con un campo sin fragmento, con
un fragmento que no está en el texto y con un tipo de documento desconocido.

**Acceptance Scenarios**:

1. **Given** una extracción de certificado laboral con fragmentos literales, **When** se valida, **Then** la respuesta es `ok: true` con la extracción normalizada y la lista de datos faltantes (campos nulos).
2. **Given** un campo cuyo fragmento no aparece en el texto, **When** se valida, **Then** el error es específico (código `FRAGMENTO_NO_LITERAL`, campo afectado en `detalles`) y reintentable.
3. **Given** una extracción que no cumple el esquema (campo extra, valor sin fragmento, tipo de dato inválido), **When** se valida, **Then** el error es específico (`EXTRACCION_INVALIDA` con la lista de campos y motivos) y reintentable.
4. **Given** un documento de tipo no soportado, **When** se valida, **Then** es `ok: true` y la respuesta indica "política no cubre el caso" (no es un error de extracción).

---

### User Story 2 - Registrar la solicitud con procedencia y evaluarla (Priority: P1)

El agente registra la solicitud de un solicitante con identidad verificada: monto, plazo,
ingreso declarado y documentos. El core guarda cada dato con su documento y fragmento de origen
y devuelve la evaluación: si es preaprobable automáticamente y, si no, las causas.

**Why this priority**: es el corazón de la originación y aplica en el core las reglas 1, 2, 3
y 5 de la constitución.

**Independent Test**: con un solicitante verificado, registrar solicitudes que caen en cada
resultado (preaprobable, analista por monto, por cuota, por discrepancia, por inconsistencia,
fuera de política) y una con ingreso no verificable; con uno no verificado, intentar registrar.

**Acceptance Scenarios**:

1. **Given** un solicitante sin identidad verificada (o bloqueado), **When** se intenta registrar, **Then** la respuesta es un error `permisos` `IDENTIDAD_NO_VERIFICADA` y no se guarda nada.
2. **Given** identidad verificada y documentos válidos dentro de los umbrales, **When** se registra, **Then** se devuelve `id_solicitud` y una evaluación con `preaprobable_automaticamente: true` y sin causas.
3. **Given** un caso que supera algún umbral o tiene discrepancia o inconsistencia, **When** se registra, **Then** la solicitud queda registrada y la evaluación trae `preaprobable_automaticamente: false` con cada causa de escalamiento (regla, mensaje y valores).
4. **Given** documentos sin salario certificado (ingreso no verificable), **When** se registra, **Then** la respuesta es un error `negocio` `INGRESO_NO_VERIFICABLE`, no reintentable, con los datos faltantes en `detalles`, y no se registra la solicitud.
5. **Given** un registro exitoso, **When** se consulta lo guardado, **Then** cada dato extraído figura con su valor, identificador del documento y fragmento de origen.
6. **Given** una extracción inválida dentro del registro, **When** se registra, **Then** se devuelve el mismo error específico que `validar_extraccion` y no se registra nada.

---

### User Story 3 - Simular sin comprometer y preaprobar con revalidación (Priority: P1)

El agente puede simular cuotas cuantas veces quiera sin ningún efecto. Solo cuando la solicitud
registrada es preaprobable, usa la herramienta que compromete a Crediágil, que vuelve a validar
todo en el core antes de comprometer.

**Why this priority**: confundir simular con comprometer es el error más costoso; la
revalidación en el core es la defensa en profundidad que pide el issue.

**Independent Test**: simular sin identidad ni solicitud; preaprobar una solicitud preaprobable
y otras que ya no lo son (identidad bloqueada después del registro, solicitud no preaprobable,
solicitud escalada).

**Acceptance Scenarios**:

1. **Given** cualquier monto y plazo válidos, **When** se simula, **Then** se devuelve la cuota (y, si se da un ingreso, la proporción cuota/ingreso) sin requerir identidad ni cambiar ningún estado.
2. **Given** la lista de herramientas, **When** se leen las descripciones, **Then** la de simulación contiene "SOLO SIMULA" y la de preaprobación contiene "COMPROMETE A CREDIÁGIL" e indica que para simular se use `calcular_capacidad_pago`.
3. **Given** una solicitud registrada preaprobable con identidad vigente, **When** se preaprueba, **Then** queda en estado `PREAPROBADA` y se devuelven monto, plazo, cuota y tasa aplicada.
4. **Given** una solicitud cuya identidad ya no es válida (p. ej. el solicitante quedó bloqueado), **When** se preaprueba, **Then** es un error `permisos` y no se compromete nada.
5. **Given** una solicitud que no cumple los umbrales al recalcular en el core, **When** se preaprueba, **Then** es un error `negocio` `NO_PREAPROBABLE` con las causas, aunque el agente lo pida.
6. **Given** una solicitud escalada o ya preaprobada, **When** se preaprueba, **Then** escalada → error `negocio` `SOLICITUD_ESCALADA`; ya preaprobada → `ok: true` con el mismo resultado (idempotente).

---

### User Story 4 - Escalar a un analista con un resumen completo (Priority: P1)

El agente escala un caso con un resumen estructurado que el analista puede leer sin repetir
preguntas al solicitante. Un resumen incompleto se rechaza.

**Why this priority**: las reglas 2–5 terminan en escalamiento; sin un resumen completo el
analista no puede actuar.

**Independent Test**: escalar con un resumen completo, con cada campo obligatorio ausente, y
con una solicitud de humano antes de registrar nada.

**Acceptance Scenarios**:

1. **Given** un resumen con solicitante, monto, plazo, datos con procedencia, discrepancias, causa, detalle y acción recomendada, **When** se escala, **Then** se devuelve un `id_escalamiento` y, si hay solicitud asociada, esta queda en estado `ESCALADA`.
2. **Given** un resumen al que le falta cualquier campo obligatorio, **When** se escala, **Then** es un error `validacion` `RESUMEN_INCOMPLETO` con la lista de campos faltantes, y no se crea el escalamiento.
3. **Given** que el solicitante pidió hablar con una persona antes de dar monto o plazo, **When** se escala con causa `solicitud_humano` y monto/plazo nulos y sin datos, **Then** se acepta (los campos están presentes aunque vacíos).
4. **Given** un dato en el resumen sin documento o fragmento de origen, **When** se escala, **Then** es `RESUMEN_INCOMPLETO` (Principio VI).

### Edge Cases

- Registrar dos veces la misma solicitud: se crean dos registros distintos (el core no deduplica); el agente decide.
- Monto o plazo inválidos (no enteros, monto ≤ 0, plazo fuera de rango) en simular o registrar: error `validacion`, no se registra nada.
- Ingreso declarado ausente: la regla 3 no puede evaluarse → error `validacion` en el registro.
- Moneda distinta de COP o documento no soportado: la solicitud se registra con decisión `fuera_de_politica` (se debe escalar), no como `INGRESO_NO_VERIFICABLE`.
- Preaprobar una solicitud inexistente: `negocio` `SOLICITUD_NO_ENCONTRADA`.
- Fallas inyectadas (#4) aplican a todas las herramientas nuevas y nunca dejan un registro, preaprobación o escalamiento a medias.

## Requirements *(mandatory)*

### Functional Requirements

**Generales**

- **FR-001**: Las cinco herramientas MUST usar el contrato de respuesta, los tipos de error y la inyección de fallas de #4, y añadirse al mismo servidor.
- **FR-001a**: Regla de reintento (ajusta FR-002 de #4): `transitorio` siempre es reintentable; `validacion` es reintentable solo en los códigos que se corrigen reenviando datos (`FRAGMENTO_NO_LITERAL`, `EXTRACCION_INVALIDA`); `negocio` y `permisos` nunca. El resto de errores `validacion` de #4 siguen sin ser reintentables.
- **FR-002**: Las reglas de negocio MUST evaluarse con `crediagil.policy` y `crediagil.extraction` (única fuente de parámetros); las herramientas MUST NOT redefinir tasa ni umbrales.

**`validar_extraccion`**

- **FR-003**: MUST recibir el tipo de documento, los datos extraídos y el texto completo del documento, y validarlos con los esquemas de #3.
- **FR-004**: Una extracción válida MUST devolver `ok: true` con la extracción normalizada y la lista de campos faltantes; un documento no soportado MUST indicarse como "política no cubre el caso".
- **FR-005**: Una extracción inválida MUST devolver un error específico — `FRAGMENTO_NO_LITERAL` o `EXTRACCION_INVALIDA` — con los campos y motivos en `detalles`, y `reintentable: true`. Estos errores son de tipo `validacion` con `reintentable: true`: el agente los corrige reenviando una extracción corregida.

**`registrar_solicitud`**

- **FR-006**: MUST exigir que el solicitante tenga identidad verificada y no esté bloqueado; si no, error `permisos` `IDENTIDAD_NO_VERIFICADA` sin guardar nada.
- **FR-007**: `verificar_identidad` (#4) MUST dejar constancia en el core de la verificación exitosa (fecha y hora), que es lo que consulta el registro.
- **FR-008**: MUST recibir identificador del solicitante, monto, plazo, ingreso declarado y documentos (cada uno con identificador, tipo, datos extraídos y texto); MUST validar cada extracción como en FR-003–FR-005.
- **FR-009**: MUST guardar la solicitud con cada dato extraído como `{valor, id_documento, fragmento}`.
- **FR-010**: MUST devolver `id_solicitud` y una evaluación con `preaprobable_automaticamente`, `decision` (`preaprobable` / `analista` / `fuera_de_politica`), `cuota` y `causas_escalamiento` (regla, mensaje y valores de cada causa).
- **FR-011**: Si el ingreso no es verificable (sin salario certificado o ambiguo), MUST devolver `negocio` `INGRESO_NO_VERIFICABLE`, `reintentable: false`, con los datos faltantes en `detalles`, sin registrar la solicitud.

**`calcular_capacidad_pago`**

- **FR-012**: MUST calcular la cuota (y la proporción cuota/ingreso si se da un ingreso) sin requerir identidad y sin cambiar ningún estado; su descripción MUST contener "SOLO SIMULA" y aclarar que no compromete nada.

**`preaprobar_credito`**

- **FR-013**: Su descripción MUST contener "COMPROMETE A CREDIÁGIL" e indicar que para simular se usa `calcular_capacidad_pago` y que solo se llama cuando la evaluación del registro fue preaprobable.
- **FR-014**: MUST revalidar en el core, al momento de la llamada, la identidad (verificada y no bloqueada) y recalcular las reglas con los datos guardados; solo si todo se cumple MUST pasar la solicitud a `PREAPROBADA`.
- **FR-015**: Errores: identidad no válida → `permisos` `IDENTIDAD_NO_VERIFICADA`; reglas no cumplidas → `negocio` `NO_PREAPROBABLE` con causas; solicitud escalada → `negocio` `SOLICITUD_ESCALADA`; inexistente → `negocio` `SOLICITUD_NO_ENCONTRADA`. Una solicitud ya preaprobada MUST devolver el mismo resultado (idempotente).

**`escalar_a_analista`**

- **FR-016**: MUST validar un resumen con los campos `solicitante`, `monto`, `plazo`, `datos` (cada uno con valor, documento y fragmento), `discrepancias`, `causa`, `detalle` y `accion_recomendada`. Todos MUST estar presentes; `solicitante`, `causa`, `detalle` y `accion_recomendada` MUST tener contenido; `monto`, `plazo`, `datos` y `discrepancias` MAY ser nulos o vacíos cuando no se conocen.
- **FR-017**: `causa` MUST ser una de: `solicitud_humano`, `fuera_de_politica`, `regla_2`, `regla_3`, `ingreso_no_verificable`, `inconsistencia_documental`, `identidad_bloqueada`, `otro`.
- **FR-018**: Un resumen incompleto MUST devolver `validacion` `RESUMEN_INCOMPLETO` con los campos faltantes; uno válido MUST crear un escalamiento con `id_escalamiento` y, si se indica una solicitud, pasarla a `ESCALADA`.

**Pruebas**

- **FR-019**: Cada herramienta MUST tener tests de éxito y de cada error, incluidos los bordes de las reglas 2 y 3 vistos desde el registro y la preaprobación.

### Key Entities

- **Solicitud**: `id_solicitud`, solicitante, monto, plazo, ingreso declarado, ingreso verificado, documentos, datos con procedencia, evaluación, estado (`REGISTRADA`, `PREAPROBADA`, `ESCALADA`).
- **Dato con procedencia**: valor, identificador del documento, fragmento literal.
- **Evaluación**: `preaprobable_automaticamente`, decisión, cuota, causas de escalamiento.
- **Verificación de identidad**: constancia (fecha y hora) de la última verificación exitosa del solicitante.
- **Escalamiento**: `id_escalamiento`, resumen, solicitud asociada (opcional), fecha.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 0 solicitudes registradas o preaprobadas sin identidad verificada y vigente.
- **SC-002**: El 100% de los datos guardados en una solicitud tienen documento y fragmento de origen.
- **SC-003**: 0 preaprobaciones de solicitudes que no cumplen las reglas al recalcular en el core, aunque el agente las pida.
- **SC-004**: Simular no cambia ningún estado en el 100% de las llamadas.
- **SC-005**: El 100% de los escalamientos creados tienen un resumen completo; el 100% de los incompletos se rechazan con la lista de campos faltantes.
- **SC-006**: Las descripciones de simular y preaprobar contienen literalmente "SOLO SIMULA" y "COMPROMETE A CREDIÁGIL".

## Assumptions

- La verificación de identidad no caduca dentro de este alcance; deja de ser válida solo si el solicitante queda bloqueado. (Caducidad por tiempo: posible mejora.)
- Moneda distinta de COP o documento no soportado ⇒ la solicitud se registra con decisión `fuera_de_politica` y causas; solo la falta de salario certificado (dato faltante o ambiguo) produce `INGRESO_NO_VERIFICABLE`.
- Una inconsistencia documental (nómina vs. salario) no impide registrar: la solicitud queda con decisión `analista`.
- La evaluación combina regla 2, regla 3 y hallazgos de ingreso con `combinar` (#3), como recomendó la revisión de #3.
- El escalamiento se guarda en el estado del core; reflejarlo como ticket en GitHub (Principio VI) corresponde a la feature del agente (#7).
- Los textos de documentos y datos de prueba son ficticios; las líneas con forma "documento + número" llevan `pragma: dato-ficticio`.
- Hacer cumplir las reglas 1 y 2 en hooks del Agent SDK sigue siendo #6; aquí el core las revalida como segunda barrera.
