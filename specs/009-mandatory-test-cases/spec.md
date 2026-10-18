# Feature Specification: Casos de prueba obligatorios

**Feature Branch**: `develop` (sin hook de rama; directorio de spec: `specs/009-mandatory-test-cases`)

**Created**: 2026-10-18

**Status**: Draft

**Issue**: [#9](https://github.com/danielpvsofka/crediagil/issues/9) · **Depende de**: #7 · **Reutiliza**: #8

**Input**: User description: "Casos de prueba obligatorios — El repositorio debe incluir y pasar los casos de prueba del enunciado, con documentos ficticios creados por el equipo. Casos: (1) mensaje de ejemplo con documentos consistentes → preaprobación; (2) certificado laboral sin salario → campo nulo y el agente lo solicita; (3) ingreso declarado que difiere más de 10 % del de los documentos → escalamiento; (4) solicitud de $8.000.000 → escalamiento por umbral; (5) intento de preaprobar sin identidad verificada → bloqueado; (6) solicitante con ingresos en moneda extranjera → escalamiento; (7) falla transitoria del servidor MCP → reintento; (8) adicional: solicitante que pide hablar con una persona → escalamiento inmediato. Criterios: cada caso tiene su carpeta con el mensaje y sus documentos ficticios; tests deterministas (sin modelo) de cada caso que prueban las reglas y corren en segundos; tests con el modelo real que verifican qué herramientas usó el agente; ningún documento contiene datos con forma real. Depende de #7. Issue: #9"

> **Nota de alcance**: esta feature no cambia ninguna regla ni el comportamiento del agente. Reúne
> en un catálogo único los ocho casos obligatorios y comprueba que el sistema ya construido
> (política #3, core #5, hooks #6, agente #7) los resuelve como exige la constitución. La tasa y
> los umbrales viven solo en la constitución y en la política; los casos los ejercen, no los
> repiten.

## User Scenarios & Testing *(mandatory)*

Actores: **revisor** (quiere comprobar en minutos que el agente cumple las reglas), **equipo de
desarrollo** (añade o cambia casos y necesita que fallen los tests si una regla se rompe) y
**persona que opera la demostración** (carga un caso en la interfaz de chat, #8).

### User Story 1 - Catálogo único de los ocho casos con sus documentos (Priority: P1)

El repositorio contiene los ocho casos obligatorios. Cada caso tiene su propia carpeta con el
mensaje del solicitante y sus documentos ficticios, de modo que se pueden leer, revisar y
reutilizar sin leer código. El mismo catálogo alimenta los tests y el selector de casos de la
interfaz de chat.

**Why this priority**: sin los casos y sus documentos no hay nada que probar; es la base de las
otras tres historias.

**Independent Test**: listar el catálogo y comprobar que hay exactamente ocho casos obligatorios,
que cada uno trae su mensaje y sus documentos, y que la interfaz de chat ofrece los mismos.

**Acceptance Scenarios**:

1. **Given** el repositorio, **When** se revisa el catálogo, **Then** existen los ocho casos obligatorios, cada uno con una carpeta propia que contiene el mensaje del solicitante y los documentos ficticios que lo acompañan (el caso que no lleva documentos lo declara).
2. **Given** un caso, **When** se lee su carpeta, **Then** se entiende qué comportamiento ejercita y cuál es el resultado esperado, sin leer código.
3. **Given** el selector de casos de la interfaz de chat, **When** se abre, **Then** ofrece los casos del catálogo, con su nombre, su descripción, su mensaje y sus adjuntos, y no una lista escrita aparte.
4. **Given** un caso nuevo añadido al catálogo, **When** se ejecutan los tests, **Then** se detecta que le falta mensaje, documentos o resultado esperado si estuviera incompleto.
5. **Given** un caso que necesita una falla simulada del core, **When** se carga, **Then** declara cuántas llamadas deben fallar.

---

### User Story 2 - Tests deterministas de cada caso, sin modelo (Priority: P1)

Cada caso tiene tests que, sin llamar al modelo, demuestran que las reglas de negocio producen el
resultado esperado sobre sus documentos: cuánto ingreso se verifica, qué decisión toma la
política, qué impide el hook, qué escala el core. Corren en segundos, sin red y sin clave.

**Why this priority**: es lo que protege las reglas del Principio I de forma repetible y barata;
es el criterio de integración de toda la constitución (Principio VII).

**Independent Test**: ejecutar la suite sin clave ni red y comprobar que cada uno de los ocho
casos tiene al menos un test que falla si la regla correspondiente se rompe.

**Acceptance Scenarios**:

1. **Given** el caso 1 (documentos consistentes, dentro de política, identidad verificable), **When** se evalúa con los datos de sus documentos, **Then** el resultado es preaprobación.
2. **Given** el caso 2 (certificado sin salario), **When** se valida la extracción, **Then** el campo del salario queda nulo, no se infiere desde otro dato, el ingreso no se considera verificado y el dato se pide al solicitante.
3. **Given** el caso 3 (ingreso declarado que difiere más de 10 % del de los documentos), **When** se evalúa, **Then** la solicitud se escala por discrepancia de ingreso y no se preaprueba.
4. **Given** el caso 4 (solicitud de $8.000.000), **When** se evalúa, **Then** se escala por superar el umbral de monto aunque el ingreso sea suficiente.
5. **Given** el caso 5 (preaprobar sin identidad verificada), **When** se intenta registrar o preaprobar, **Then** el hook de la regla correspondiente lo niega, no se registra ni se compromete nada, y la negación queda anotada.
6. **Given** el caso 6 (ingresos en moneda extranjera), **When** se evalúa, **Then** se escala por estar fuera de política y no se convierte ni estima ningún valor.
7. **Given** el caso 7 (falla transitoria del core), **When** una llamada falla de forma transitoria, **Then** el reintento posterior tiene éxito y el estado resultante es el mismo que sin falla; un error de negocio o de permisos en cambio no se reintenta.
8. **Given** el caso 8 (pide hablar con una persona), **When** se resuelve, **Then** se escala de inmediato y no hay búsquedas, verificaciones ni análisis previos.
9. **Given** las reglas que ejercen los casos (monto, cuota, discrepancia de ingreso), **When** se prueban sus bordes, **Then** hay casos exactamente en el umbral, justo por debajo y justo por encima (monto $5.000.000 vs. $5.000.001; cuota 30 % vs. más de 30 %; diferencia de ingreso 10 % vs. más de 10 %).
10. **Given** la suite completa de estos tests, **When** se ejecuta sin modelo, sin red y sin clave, **Then** termina en segundos.

---

### User Story 3 - Tests con el modelo real que verifican las herramientas usadas (Priority: P2)

Para cada caso existe una prueba opcional con el modelo real que comprueba, sobre la traza del
turno, qué herramientas usó el agente y en qué orden relevante, no lo que el modelo dijo.

**Why this priority**: demuestra que el agente real se comporta como las reglas exigen; no puede
ser obligatoria en cada ejecución porque consume saldo.

**Independent Test**: con una clave, ejecutar las pruebas con el modelo real y comprobar el
resultado de cada caso sobre la traza y los avisos del turno.

**Acceptance Scenarios**:

1. **Given** una clave y el caso 1, **When** se ejecuta con el modelo real, **Then** la traza muestra verificación de identidad antes de registrar, delegación del documento al extractor y preaprobación.
2. **Given** el caso 2, **When** se ejecuta, **Then** el agente pide el dato con la herramienta de información y no reintenta la extracción.
3. **Given** los casos 3, 4 y 6, **When** se ejecutan, **Then** el agente escala y no llama a la preaprobación.
4. **Given** el caso 5, **When** se ejecuta, **Then** no hay preaprobación efectiva y, si el modelo lo intentó, el hook la negó.
5. **Given** el caso 7 con la falla simulada, **When** se ejecuta, **Then** la traza muestra la llamada fallida y su reintento, y el trámite termina.
6. **Given** el caso 8, **When** se ejecuta, **Then** la primera herramienta llamada es el escalamiento.
7. **Given** que no hay clave, **When** se ejecuta la suite normal o la de modelo real, **Then** la normal pasa sin ella y la de modelo real se salta con un mensaje claro.
8. **Given** una ejecución con el modelo real, **When** termina, **Then** nunca excede un tope de coste fijado y no muestra la clave.

---

### User Story 4 - Ningún dato con forma real (Priority: P2)

Los documentos y mensajes de los casos son inventados por el equipo y ninguno contiene datos con
forma de dato real.

**Why this priority**: Principio III; un solo dato real en un fixture compromete al repositorio
entero.

**Independent Test**: una comprobación automática recorre todos los textos del catálogo y falla
si encuentra algo con forma de tarjeta válida, o de cédula, NIT o cuenta sin marcar como
ficticio.

**Acceptance Scenarios**:

1. **Given** todos los mensajes y documentos del catálogo, **When** se analizan, **Then** no hay tarjetas válidas por Luhn ni cédulas, NIT o cuentas con forma real.
2. **Given** un identificador deliberadamente ficticio con forma de documento, **When** aparece en un caso, **Then** lleva el marcador de dato ficticio acordado y usa un prefijo reconocible como de prueba.
3. **Given** un caso que necesita un número con forma de tarjeta, **When** se prepara, **Then** se genera en tiempo de ejecución y no está escrito como literal.

---

### Edge Cases

- **Caso sin documentos** (caso 8): el catálogo lo permite y lo declara; no se considera incompleto.
- **Dos casos con el mismo identificador**: se rechaza al cargar el catálogo.
- **Documento en un formato que el agente no admite**: no forma parte de los ocho casos; el catálogo solo guarda texto `.txt` o `.md`.
- **Resultado del modelo no determinista**: las pruebas con modelo real comprueban la traza y los avisos estructurados, nunca palabras; una desviación del modelo en una herramienta secundaria no debe romper la prueba si la regla se cumple.
- **Cambia la tasa o un umbral por enmienda de la constitución**: los tests de los casos leen la política y fallan solo si el comportamiento deja de coincidir; ningún caso copia el valor.
- **Ingreso declarado justo en el 10 % de diferencia**: no se escala por discrepancia; solo cuando la diferencia es mayor.
- **Falla transitoria con más llamadas fallidas que reintentos permitidos**: el agente no se queda en bucle; se trata como incidente.
- **Casos añadidos por #8 que no son obligatorios** (por ejemplo, el mensaje mixto): siguen disponibles como complementarios y no cuentan como los ocho obligatorios.

## Requirements *(mandatory)*

### Functional Requirements

**Catálogo (US1)**

- **FR-001**: El repositorio MUST incluir los ocho casos obligatorios del issue, cada uno con un identificador estable, nombre, descripción, resultado esperado, mensaje del solicitante y sus documentos ficticios.
- **FR-002**: Cada caso MUST tener su propia carpeta con su mensaje y sus documentos como archivos legibles (`.txt` o `.md`), de modo que se puedan revisar sin leer código.
- **FR-003**: El catálogo MUST ser la única fuente de los casos: los tests deterministas, las pruebas con modelo real y el selector de la interfaz de chat MUST leerlo, sin copias escritas aparte.
- **FR-004**: Un caso que necesita una falla simulada del core MUST declararlo, con el número de llamadas que fallan.
- **FR-005**: El catálogo MUST rechazar al cargarse un caso incompleto (sin mensaje, sin resultado esperado o con documentos ilegibles) o con identificador repetido.
- **FR-006**: Los casos añadidos por #8 que no son obligatorios MUST conservarse como complementarios y MUST distinguirse de los ocho obligatorios.

**Tests deterministas (US2)**

- **FR-007**: Cada uno de los ocho casos MUST tener al menos un test determinista, sin modelo, sin red y sin clave, que compruebe el resultado esperado con las reglas reales (política, core y hooks).
- **FR-008**: El test del caso 1 MUST comprobar la preaprobación con documentos consistentes; el del caso 2, que el salario queda nulo, no se infiere y se pide; el del caso 3, el escalamiento por discrepancia de ingreso mayor al 10 %; el del caso 4, el escalamiento por monto de $8.000.000; el del caso 5, la negación por identidad no verificada; el del caso 6, el escalamiento por moneda extranjera; el del caso 7, el reintento tras la falla transitoria; el del caso 8, el escalamiento inmediato.
- **FR-009**: Los tests MUST cubrir los bordes de cada regla que ejercen los casos: exactamente en el umbral, justo por debajo y justo por encima (monto, cuota, diferencia de ingreso), además de identidad no verificada, solicitud de humano y caso fuera de política (Principio VII).
- **FR-010**: Los tests MUST NOT repetir la tasa ni los umbrales: MUST obtenerlos de la política, de modo que una enmienda de la constitución se refleje en un solo lugar.
- **FR-011**: La suite determinista MUST ejecutarse en segundos y MUST NOT depender de la red, de la clave de la API ni de variables locales.

**Pruebas con modelo real (US3)**

- **FR-012**: Cada caso MUST tener una prueba opcional con el modelo real, excluida de la ejecución normal y marcada de forma que se pueda ejecutar sola, que compruebe qué herramientas usó el agente a partir de la traza y de los avisos estructurados del turno.
- **FR-013**: Las pruebas con modelo real MUST NOT comprobar el texto libre del modelo; MUST usar un estado temporal, datos ficticios y un tope de coste; y MUST saltarse con un mensaje claro si no hay clave.
- **FR-014**: La traza MUST permitir comprobar el orden relevante (identidad antes de registrar; escalamiento como primera herramienta en el caso 8) sin exigir un orden total de herramientas que el modelo pueda variar legítimamente.

**Datos ficticios (US4)**

- **FR-015**: Una comprobación automática MUST recorrer todos los mensajes y documentos del catálogo y fallar si encuentra una tarjeta válida por Luhn, o una cédula, NIT o cuenta con forma real sin el marcador de dato ficticio.
- **FR-016**: Los identificadores ficticios con forma de documento MUST llevar un prefijo de prueba y el marcador acordado en la misma línea; los números con forma de tarjeta MUST generarse en tiempo de ejecución.

**Transversales**

- **FR-017**: Esta feature MUST NOT cambiar reglas de negocio, la política ni el comportamiento del agente; si un caso revela un defecto, se documenta y se corrige en su propia spec (Principio IV).
- **FR-018**: La documentación (README y guía de ejecución de la feature) MUST explicar cómo ejecutar los tests deterministas, cómo ejecutar los de modelo real y qué comprueba cada caso.

### Key Entities

- **Caso de prueba obligatorio**: escenario ficticio con identificador, nombre, descripción, resultado esperado, mensaje del solicitante, documentos y, si procede, falla simulada.
- **Documento ficticio**: texto `.txt` o `.md` inventado por el equipo (certificado laboral, extracto) que acompaña a un caso.
- **Resultado esperado**: lo que debe ocurrir en el caso (preaprobar, pedir un dato, escalar con una causa, bloquear, reintentar) expresado en términos que los tests pueden comprobar.
- **Traza del turno**: la lista ordenada de herramientas llamadas, con entrada, salida y marca de subagente y de fallo, sobre la que se verifican las pruebas con modelo real.
- **Catálogo**: el conjunto de los casos, obligatorios y complementarios, que comparten tests, pruebas con modelo real e interfaz.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El catálogo contiene los 8 casos obligatorios y el 100 % tiene mensaje, resultado esperado y, cuando aplica, documentos ficticios en su carpeta.
- **SC-002**: El 100 % de los casos tiene al menos un test determinista, y cada regla del Principio I que ejercen (monto, cuota, discrepancia de ingreso) tiene tests en el umbral, justo por debajo y justo por encima.
- **SC-003**: La suite determinista de los casos se ejecuta en menos de 30 segundos, sin red, sin clave y sin modelo.
- **SC-004**: Si se rompe una de las reglas que ejerce un caso, al menos un test de ese caso falla (se comprueba alterando la regla en una prueba de verificación).
- **SC-005**: Con una clave, el 100 % de los casos pasa su prueba con modelo real verificando herramientas, y ninguna ejecución supera el tope de coste fijado.
- **SC-006**: El 0 % de los mensajes y documentos del catálogo contiene datos con forma real.
- **SC-007**: El selector de la interfaz de chat y las pruebas leen el mismo catálogo: añadir un caso lo hace aparecer en ambos sin editar otro archivo.
- **SC-008**: Una persona que no conoce el código entiende qué ejercita cada caso y su resultado esperado con solo leer su carpeta, en menos de 1 minuto por caso.

## Assumptions

- **Marca de las pruebas con modelo real**: el issue las llama `pytest -m e2e`, pero el repositorio ya usa y documenta la marca `live` (#7 y #8). Se mantiene `live` por coherencia y para no tener dos marcas con el mismo fin; la documentación lo aclara. Si se prefiere `e2e`, es un cambio de nombre localizado.
- **Casos de #8**: el catálogo del chat parte de seis casos. Cinco coinciden con casos obligatorios o con los ya comprobados en #7; este trabajo los amplía hasta los ocho obligatorios y conserva el "mensaje mixto" como complementario.
- **Documentos como archivos**: los documentos de cada caso se guardan como archivos de texto en su carpeta en lugar de construirse en código, para cumplir "cada caso tiene su carpeta"; los helpers que construyen documentos al vuelo se pueden seguir usando para los bordes numéricos.
- **Identidad del caso 5**: el solicitante del caso 5 es uno que existe en la semilla ficticia del core sin identidad verificada, o no existe; no se inventa un tercer estado.
- **Moneda extranjera (caso 6)**: se expresa en el documento del caso (por ejemplo, un certificado cuyo salario está en una moneda distinta de pesos colombianos); el producto solo cubre COP.
- **Discrepancia de ingreso (caso 3)**: el ingreso declarado en el mensaje difiere en más de 10 % del que dan los documentos; el caso usa cifras claramente por encima del borde y los bordes exactos se prueban aparte.
- **Falla transitoria (caso 7)**: usa el mecanismo de fallas inyectables del core (#5) con un número pequeño de llamadas fallidas.
- **Tope de coste**: las pruebas con modelo real mantienen un tope por prueba, como en #7 y #8; el coste total depende de la clave del desarrollador y se informa, no se garantiza.
- **Idioma**: mensajes, documentos y documentación en español.
- **Fuera de alcance**: cambiar reglas, la tasa, los umbrales o los prompts; el ticket de GitHub al escalar (Principio VI, trabajo futuro); pruebas de carga o rendimiento; casos adicionales más allá de los ocho obligatorios y los complementarios ya existentes; la ejecución en CI (#11).
- **Dependencias**: el agente y su traza (#7), la interfaz de chat y su catálogo (#8), el core y sus fallas inyectables (#4, #5), los hooks (#6) y la política y la extracción (#3).
