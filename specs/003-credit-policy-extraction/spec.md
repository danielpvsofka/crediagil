# Feature Specification: Política de crédito y esquemas de extracción

**Feature Branch**: `develop` (sin hook de rama; directorio de spec: `specs/003-credit-policy-extraction`)

**Created**: 2026-10-17

**Status**: Draft

**Issue**: [#3](https://github.com/danielpvsofka/crediagil/issues/3) · **Habilita**: #4, #5, #6

**Input**: User description: "Política de crédito y esquemas de extracción — Las reglas de negocio y los umbrales deben tener una única fuente de verdad, consumida por el servidor MCP, los hooks del agente y los tests. La extracción de documentos necesita un esquema validado que impida inventar datos. Alcance: módulo de política (tasa, umbrales, cálculo de cuota y evaluación de reglas 2 y 3); esquemas Pydantic de extracción (certificado laboral, extracto bancario y documento no soportado); derivación del ingreso verificado a partir de los documentos. Criterios: tasa fija 1,8% mensual y cuota por sistema francés ($4.000.000 a 24 meses da $206.723); preaprobable solo si monto ≤ $5.000.000 y cuota ≤ 30% del ingreso verificado (test en el borde exacto); discrepancia declarado vs. verificado > 10% escala y exactamente 10% no escala; cada campo extraído es {valor, fragmento}, un valor sin fragmento se rechaza y lo ausente queda null; cada fragmento debe aparecer literalmente en el documento; el ingreso verificado sale del salario del certificado y, si falta, se reporta como dato faltante sin inferirlo de los extractos; ingresos en moneda distinta de COP o documento no soportado se marcan como 'política no cubre el caso'; extractos cuyo promedio de nómina difiere > 10% del salario certificado se marcan como inconsistencia documental. Fuera de alcance: exposición como herramientas MCP (#4, #5). Issue: #3"

> **Nota sobre parámetros**: la tasa y los umbrales los fija la constitución (Principio I). Esta
> spec los cita solo para definir los criterios de aceptación exigidos por el issue; la
> feature los centraliza en una única fuente en el código, verificada contra la constitución.

## User Scenarios & Testing *(mandatory)*

Actores: **agente de originación** (y sus hooks), que consulta la política y los datos
extraídos; **analista**, que recibe los casos escalados; **equipo de desarrollo**, que prueba
las reglas.

### User Story 1 - Calcular la cuota y decidir la preaprobación (Priority: P1)

Dado un monto, un plazo y el ingreso mensual verificado, la política calcula la cuota mensual
y decide si la solicitud es preaprobable automáticamente o va a analista (regla 2).

**Why this priority**: es la regla que decide un crédito; todo lo demás la alimenta.

**Independent Test**: evaluar combinaciones de monto, plazo e ingreso en los bordes exactos y
comprobar cuota y decisión.

**Acceptance Scenarios**:

1. **Given** monto $4.000.000 y plazo 24 meses, **When** se calcula la cuota, **Then** es $206.723.
2. **Given** monto exactamente $5.000.000 y cuota exactamente 30% del ingreso verificado, **When** se evalúa, **Then** es preaprobable.
3. **Given** monto $5.000.001 con cualquier ingreso, **When** se evalúa, **Then** va a analista.
4. **Given** cuota un peso por encima del 30% del ingreso verificado, **When** se evalúa, **Then** va a analista.
5. **Given** que no hay ingreso verificado, **When** se evalúa, **Then** va a analista.

---

### User Story 2 - Extraer datos sin inventarlos (Priority: P1)

Los datos extraídos de un certificado laboral o de un extracto bancario se representan con su
valor y el fragmento literal del documento del que salen. Lo que el documento no contiene
queda nulo.

**Why this priority**: sin esta garantía el ingreso verificado puede ser inventado
(Principios V y VI).

**Independent Test**: validar extracciones de documentos ficticios con campos completos,
faltantes, sin fragmento y con fragmentos que no están en el documento.

**Acceptance Scenarios**:

1. **Given** un campo con valor y sin fragmento, **When** se valida la extracción, **Then** se rechaza.
2. **Given** un campo cuyo fragmento no aparece literalmente en el texto del documento, **When** se valida, **Then** se rechaza indicando el campo.
3. **Given** un campo que el documento no contiene, **When** se valida, **Then** queda nulo y figura como dato faltante.
4. **Given** un documento de un tipo no soportado, **When** se clasifica, **Then** se marca como "política no cubre el caso".

---

### User Story 3 - Derivar el ingreso verificado y detectar discrepancias (Priority: P1)

A partir de los documentos validados se obtiene el ingreso verificado, se compara con el
declarado (regla 3) y se contrasta con los extractos bancarios.

**Why this priority**: el ingreso verificado es la entrada de la regla 2.

**Independent Test**: combinar certificados y extractos ficticios con ingresos declarados en
los bordes de 10%.

**Acceptance Scenarios**:

1. **Given** un certificado laboral con salario, **When** se deriva el ingreso, **Then** el ingreso verificado es ese salario, con su fragmento de origen.
2. **Given** un certificado sin salario y extractos con nómina, **When** se deriva el ingreso, **Then** el ingreso verificado queda faltante y no se toma de los extractos.
3. **Given** ingreso declarado que difiere exactamente 10% del verificado, **When** se evalúa la regla 3, **Then** no escala.
4. **Given** ingreso declarado que difiere más de 10% del verificado, **When** se evalúa, **Then** escala a analista.
5. **Given** extractos cuyo promedio de nómina difiere más de 10% del salario certificado, **When** se contrastan, **Then** se marca inconsistencia documental; exactamente 10% no se marca.
6. **Given** un ingreso en moneda distinta de COP, **When** se deriva, **Then** se marca "política no cubre el caso".

### Edge Cases

- Monto $4.999.999 / $5.000.000 / $5.000.001 y cuota en 30% − 1 peso / 30% / 30% + 1 peso.
- Discrepancia de ingreso en 10% exacto, por debajo y por encima, tanto si el declarado es mayor como menor que el verificado.
- Ingreso verificado cero o ausente: nunca preaprobable, sin división por cero.
- Plazo de 5 o 61 meses, no entero, o monto no positivo: se rechaza la evaluación con motivo; 6 y 60 meses se aceptan.
- Varios extractos: el promedio de nómina se calcula sobre los extractos aportados; meses sin nómina identificable no cuentan como cero.
- Fragmento presente en el documento pero con espacios distintos: no es literal y se rechaza.
- Certificado con varios salarios (p. ej. básico y total): ver Assumptions.
- Varios certificados laborales con salarios distintos: el salario es ambiguo y queda como dato faltante (no se elige uno). La moneda se revisa en **todos** los certificados: si alguno está en otra moneda, el caso queda fuera de política; si alguno no indica moneda, es dato faltante. El resultado no depende del orden de los documentos.
- Extracto sin moneda: sus abonos no entran en el promedio de nómina (no se asume COP).
- Salario o abono de nómina en 0 o negativo, o fragmento solo con espacios: la extracción se rechaza.

## Requirements *(mandatory)*

### Functional Requirements

**Política**

- **FR-001**: La tasa y los umbrales (monto máximo de preaprobación, proporción máxima cuota/ingreso y discrepancia máxima de ingreso) MUST definirse en una única fuente que consumen el servidor MCP, los hooks del agente y los tests; ningún otro lugar del código MAY redefinirlos.
- **FR-002**: Esa fuente MUST coincidir con los valores de la constitución (Principio I); una verificación automática MUST fallar si difieren.
- **FR-003**: El monto MUST ser un número entero de pesos. La cuota mensual MUST calcularse por sistema francés con la tasa fija mensual, redondeada al peso más cercano (con $4.000.000 a 24 meses da $206.723).
- **FR-004**: El plazo MUST ser un número entero de meses entre 6 y 60, ambos incluidos (bordes probados: 5, 6, 60, 61). Un plazo no permitido o un monto no positivo MUST rechazarse con motivo.
- **FR-005**: Regla 2: una solicitud MUST ser preaprobable solo si monto ≤ $5.000.000 **y** cuota ≤ 30% del ingreso verificado; en cualquier otro caso, incluido no tener ingreso verificado, MUST ir a analista.
- **FR-006**: Ingresos declarado y verificado MUST ser enteros de pesos (declarado ≥ 0, verificado > 0). Regla 3: si |declarado − verificado| / verificado > 10%, la solicitud MUST ir a analista; exactamente 10% MUST NOT escalar.
- **FR-007**: Cada evaluación MUST devolver la decisión y los motivos (qué regla y qué valores la causaron).

**Extracción**

- **FR-008**: MUST existir esquemas de extracción para certificado laboral, extracto bancario y documento no soportado.
- **FR-009**: Cada campo extraído MUST representarse como {valor, fragmento}. Un valor sin fragmento, o con un fragmento vacío o solo de espacios, MUST rechazarse; salarios y abonos de nómina MUST ser enteros positivos; un campo ausente MUST quedar nulo y reportarse como dato faltante.
- **FR-010**: Cada fragmento MUST aparecer literalmente en el texto del documento de origen; si no, la extracción MUST rechazarse indicando el campo.
- **FR-011**: Un documento de tipo no soportado MUST marcarse como "política no cubre el caso".

**Ingreso verificado**

- **FR-012**: El ingreso verificado MUST salir exclusivamente del salario del certificado laboral, con su fragmento de origen. Si falta, MUST reportarse como dato faltante y MUST NOT inferirse de los extractos ni de otra fuente.
- **FR-013**: Un ingreso en moneda distinta de COP MUST marcarse como "política no cubre el caso".
- **FR-014**: Si el promedio de nómina de los extractos difiere más de 10% del salario certificado, MUST marcarse inconsistencia documental (va a analista); exactamente 10% MUST NOT marcarse.

**Pruebas**

- **FR-015**: Cada regla MUST tener pruebas en el umbral exacto, justo por debajo y justo por encima (Principio VII), con datos exclusivamente ficticios.

### Key Entities

- **Parámetros de política**: tasa mensual, monto máximo de preaprobación, proporción máxima cuota/ingreso, discrepancia máxima de ingreso, plazos permitidos.
- **Evaluación**: monto, plazo, ingreso verificado, ingreso declarado → cuota, decisión (preaprobable / analista / fuera de política) y motivos.
- **Campo extraído**: valor (o nulo) y fragmento literal del documento.
- **Certificado laboral**: empleador, nombre, salario, moneda, fecha (campos extraídos).
- **Extracto bancario**: titular, periodo, moneda y abonos de nómina (campos extraídos).
- **Documento no soportado**: tipo detectado; siempre "política no cubre el caso".
- **Ingreso verificado**: valor, moneda, documento y fragmento de origen; o faltante.
- **Hallazgo documental**: dato faltante, inconsistencia documental o "política no cubre el caso".

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El 100% de las decisiones de preaprobación coinciden con la regla 2 en todos los bordes probados (monto y proporción cuota/ingreso en el umbral, −1 y +1).
- **SC-002**: El 100% de los casos con discrepancia de ingreso > 10% van a analista y ninguno con exactamente 10%.
- **SC-003**: 0 valores extraídos aceptados sin fragmento literal en su documento.
- **SC-004**: 0 ingresos verificados que no provengan de un salario certificado.
- **SC-005**: La tasa y los umbrales aparecen definidos en un solo lugar del código, y cambiarlos sin cambiar la constitución hace fallar la verificación.

## Assumptions

- **Redondeo**: la cuota se redondea al peso más cercano (mitad hacia arriba); las comparaciones de la regla 2 usan la cuota redondeada.
- **Base de la discrepancia**: la diferencia porcentual se calcula sobre el ingreso verificado.
- **Salario del certificado**: si el certificado muestra varios montos, se toma el salario mensual básico; si es ambiguo, el campo queda faltante en lugar de elegir uno.
- **Promedio de nómina**: media de los abonos identificados como nómina en los extractos aportados (por abono, no por periodo); si no hay ninguno, no se evalúa la inconsistencia. Una nómina quincenal sale como inconsistencia y va a analista (lado seguro); el cálculo por periodo queda como trabajo futuro.
- **Fragmento literal**: coincidencia exacta de subcadena con el texto del documento, sin normalizar espacios ni mayúsculas.
- **Moneda**: el extractor entrega el código ISO exacto (`COP`, `USD`…); no se normalizan mayúsculas ni espacios.
- **Documentos**: llegan como texto ya obtenido (la lectura de PDF/imagen queda fuera de esta feature).
- La regla 1 (identidad) y la exposición como herramientas MCP quedan fuera (#4, #5, #6).
