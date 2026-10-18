# Feature Specification: Agente orquestador y subagente extractor

**Feature Branch**: `develop` (sin hook de rama; directorio de spec: `specs/007-agent-orchestrator-extractor`)

**Created**: 2026-10-18

**Status**: Draft

**Issue**: [#7](https://github.com/danielpvsofka/crediagil/issues/7) · **Depende de**: #6 (y #3, #4, #5) · **Habilita**: #8, #9

**Input**: User description: "Agente orquestador y subagente extractor — El agente atiende el mensaje del solicitante, delega la extracción de cada documento y decide si preaprueba, pide información o escala. Alcance: orquestador con el Claude Agent SDK, subagente `extractor-documentos`, prompts y herramienta de canal `solicitar_informacion`. Criterios: el ciclo continúa o termina según el `stop_reason` del modelo, no por un número fijo de iteraciones ni por palabras en el texto; cada documento se delega al subagente pasando de forma explícita documento_id, nombre y texto completo; el subagente solo puede usar `validar_extraccion` y reintenta corrigiendo el error específico; si un dato no está en el documento, el agente no reintenta: lo pide con `solicitar_informacion`; el agente separa los asuntos del mensaje (solicitud, pregunta por la cuota) y responde de forma unificada; pedir hablar con una persona escala de inmediato, sin buscar ni verificar antes; escala por umbral, discrepancia de ingresos y casos que la política no cubre, y no escala lo que puede resolver; ante errores transitorios reintenta, ante errores de negocio o permisos no reintenta; el agente no hereda la configuración de Claude Code del repositorio. Depende de #6. Issue: #7"

> **Nota de alcance**: los nombres `extractor-documentos`, `solicitar_informacion` y `stop_reason`
> son contrato del issue. Los modelos concretos, el texto exacto de los prompts y la forma de la
> API del orquestador se deciden en `/speckit-plan`. Las reglas de negocio no se repiten aquí: las
> aplican el core (#5), la política (#3) y los hooks del SDK (#6).

## User Scenarios & Testing *(mandatory)*

Actores: **solicitante** (escribe y adjunta documentos desde el chat de #8), **agente
orquestador**, **subagente extractor** y **analista** (recibe lo escalado).

### User Story 1 - Atender una solicitud de principio a fin (Priority: P1)

El solicitante escribe, por ejemplo, que quiere un crédito de cierto monto y plazo, y adjunta su
certificado laboral. El agente lo identifica, verifica su identidad, extrae los datos del
documento, registra la solicitud y, si la evaluación lo permite, la preaprueba; si no, escala o
pide lo que falta. Responde con un único mensaje claro.

**Why this priority**: es el flujo de valor completo de Crediágil.

**Independent Test**: con el modelo real, una conversación ficticia completa dentro de política;
sin modelo, el control del ciclo con secuencias de mensajes del SDK guionizadas.

**Acceptance Scenarios**:

1. **Given** un solicitante que pide un crédito dentro de política, con identidad verificable y un certificado laboral válido, **When** el agente procesa el mensaje, **Then** registra la solicitud, la preaprueba y responde con cuota y condiciones, y el resultado del turno incluye el aviso "crédito preaprobado".
2. **Given** una respuesta del modelo cuya razón de parada indica uso de herramientas, **When** el orquestador la recibe, **Then** el ciclo continúa; **Given** una razón de parada de fin de turno, **Then** entrega la respuesta. En ningún caso decide por un número fijo de iteraciones ni por palabras del texto.
3. **Given** una razón de parada de truncamiento por longitud, **When** se recibe, **Then** la respuesta no se entrega como final: se continúa y, si persiste, se escala.
4. **Given** una razón de parada de rechazo del modelo o una desconocida, **When** se recibe, **Then** se trata como incidente y se escala a un analista.
5. **Given** una conversación de varios turnos, **When** el solicitante responde a un pedido de información, **Then** el agente continúa el mismo trámite sin volver a pedir lo ya verificado.

---

### User Story 2 - Delegar la extracción de cada documento (Priority: P1)

El orquestador no lee los documentos: delega cada uno a un subagente que solo sabe extraer y
validar. Si falta un dato en el documento, no se inventa ni se reintenta: se pide al solicitante.

**Why this priority**: es la garantía de no inventar datos (Principio V) y de procedencia
(Principio VI) en el lado del agente.

**Independent Test**: delegar documentos ficticios completos, con un dato ausente y con un
fragmento erróneo; comprobar qué recibe el subagente y qué puede usar.

**Acceptance Scenarios**:

1. **Given** un mensaje con dos documentos, **When** el agente delega, **Then** cada documento va al subagente de forma explícita con `documento_id`, nombre y texto completo, sin depender de contexto implícito.
2. **Given** el subagente `extractor-documentos`, **When** se inspecciona su definición, **Then** su única herramienta es `validar_extraccion` (sin archivos, shell, red ni otras herramientas del core).
3. **Given** que `validar_extraccion` devuelve un error reintentable, **When** el subagente lo recibe, **Then** corrige el campo señalado y vuelve a validar, sin repetir la misma extracción.
4. **Given** un dato que el documento no contiene, **When** el subagente lo detecta, **Then** lo devuelve como faltante y el orquestador lo pide al solicitante con `solicitar_informacion`, sin reintentar ni inventarlo.
5. **Given** una extracción validada, **When** el orquestador registra la solicitud, **Then** pasa los documentos con su identificador y texto, de modo que cada dato guardado conserva documento y fragmento de origen.

---

### User Story 3 - Escalar cuando corresponde y no cuando no (Priority: P1)

El agente escala a un analista en los casos que la política no resuelve y atiende por sí mismo
todo lo que puede resolver. Si el solicitante pide hablar con una persona, se escala de
inmediato.

**Why this priority**: escalar mal es un cliente desatendido o un crédito mal otorgado
(Principio I, reglas 4 y 5).

**Independent Test**: conversaciones ficticias para cada causa de escalamiento y para casos que
deben resolverse sin escalar.

**Acceptance Scenarios**:

1. **Given** un mensaje en el que el solicitante pide hablar con una persona, **When** el agente lo procesa, **Then** su primera y única acción es `escalar_a_analista` con causa `solicitud_humano`, sin buscar, verificar, simular ni hacer preguntas antes.
2. **Given** que la evaluación del registro no es preaprobable por monto, cuota o discrepancia de ingreso, **When** el agente decide, **Then** escala con las causas de esa evaluación y un resumen completo con procedencia de los datos.
3. **Given** moneda distinta de COP o un documento no soportado, **When** se registra, **Then** el agente escala por caso fuera de política.
4. **Given** un dato faltante, un documento ilegible o un mensaje ambiguo, **When** el agente lo detecta, **Then** pide la información o la aclaración en lugar de escalar.
5. **Given** que el solicitante queda bloqueado por intentos fallidos de verificación, **When** ocurre, **Then** el agente escala por identidad bloqueada.
6. **Given** que el modelo intenta preaprobar sin identidad verificada (por error o inducido), **When** llega al hook del SDK de #6, **Then** la llamada se niega, el agente recibe el motivo y escala o pide verificar, sin insistir.

---

### User Story 4 - Separar los asuntos del mensaje y responder unificado (Priority: P2)

Un mismo mensaje puede mezclar una solicitud y una pregunta ("quiero un crédito y además
¿cuánto sería la cuota de tal monto a tal plazo?"). El agente separa los asuntos, resuelve cada
uno con la herramienta adecuada y responde una sola vez.

**Why this priority**: evita confundir simular con comprometer, el error más costoso.

**Independent Test**: mensajes mixtos con el modelo real; en la traza, la simulación no
compromete y la respuesta distingue lo simulado de lo comprometido.

**Acceptance Scenarios**:

1. **Given** un mensaje con una solicitud y una pregunta por la cuota, **When** el agente responde, **Then** atiende ambas en un único mensaje.
2. **Given** una pregunta de cuota sin solicitud, **When** se responde, **Then** el agente solo simula: no registra ni preaprueba nada.
3. **Given** una respuesta con una simulación y un resultado del trámite, **When** se lee, **Then** deja claro qué es una simulación y qué quedó comprometido.

---

### User Story 5 - Reintentar solo lo que se puede reintentar (Priority: P2)

El agente distingue entre fallas pasajeras y decisiones del negocio: reintenta las primeras y no
insiste con las segundas.

**Why this priority**: reintentar un error de negocio no lo arregla y quema tiempo y saldo.

**Independent Test**: simular respuestas de herramientas de cada tipo de error y observar el
comportamiento (sin modelo para el control; con modelo real para la conducta).

**Acceptance Scenarios**:

1. **Given** un error `transitorio` reintentable, **When** ocurre, **Then** el agente reintenta de forma acotada y, si persiste, informa y escala.
2. **Given** un error `negocio` o `permisos`, **When** ocurre, **Then** el agente no reintenta y actúa según el código (informar, pedir un dato o escalar).
3. **Given** un error de extracción reintentable, **When** ocurre, **Then** el subagente corrige y reintenta (US2).
4. **Given** una falla del modelo o de la red (por ejemplo, clave inválida), **When** ocurre, **Then** el turno termina con un error claro para la interfaz, sin trazas internas ni la clave, y sin inventar una respuesta.

---

### User Story 6 - Aislar al agente de la configuración del repositorio (Priority: P2)

El agente de producción no debe heredar nada de Claude Code del repositorio ni del usuario
(instrucciones, reglas, hooks, skills, permisos), y solo dispone de las herramientas que el
código le entrega.

**Why this priority**: si hereda configuración de desarrollo, su comportamiento cambia según
dónde se ejecute y podría usar herramientas que no debe.

**Independent Test**: inspeccionar las opciones con las que se crea el agente y comprobar la
lista de herramientas permitidas, sin llamar al modelo.

**Acceptance Scenarios**:

1. **Given** las opciones del agente, **When** se inspeccionan, **Then** no incluyen ninguna fuente de configuración de Claude Code.
2. **Given** las herramientas permitidas, **When** se listan, **Then** son solo las del core, `solicitar_informacion` y la delegación al subagente; ninguna de archivos, shell ni red.
3. **Given** los hooks de #6, **When** se crea el agente, **Then** van registrados con el nombre del servidor MCP del core, sin que dependa de configuración externa.
4. **Given** la clave de la API, **When** el agente arranca, **Then** se lee del entorno y no aparece en logs, respuestas ni traza técnica.

### Edge Cases

- Mensaje sin intención clara: el agente pide una aclaración (no escala).
- Documento adjunto vacío o ilegible: pide que lo reenvíe; no se delega texto vacío.
- Solicitante no encontrado o con varias coincidencias: pide el documento; no adivina.
- Fecha de nacimiento incorrecta: informa los intentos restantes; al bloquearse, escala por identidad bloqueada.
- Petición de hablar con una persona a mitad de un trámite: escala de inmediato, aunque haya pasos pendientes.
- Falla del modelo, de la red o clave inválida: error claro hacia la interfaz, sin datos sensibles.
- Bucle o reintentos sin fin: existe un tope de seguridad que nunca decide el fin normal; si se alcanza, se registra como incidente y se escala.
- Dos documentos en el mismo mensaje, uno válido y otro con dato faltante: se procesa el válido y se pide solo lo que falta del otro.

## Requirements *(mandatory)*

### Functional Requirements

**Ciclo del agente**

- **FR-001**: Cada turno MUST ejecutarse como un ciclo que continúa o termina según el `stop_reason` del modelo: continúa tras uso de herramientas y termina en fin de turno. MUST NOT terminar por un número fijo de iteraciones ni por palabras en el texto. Un tope de seguridad MAY existir solo como protección; si se alcanza, se registra como incidente y se escala.
- **FR-002**: Una razón de parada de truncamiento por longitud MUST NOT entregarse como respuesta final (se continúa y, si persiste, se escala); una de rechazo o desconocida MUST tratarse como incidente y escalarse.

**Subagente extractor**

- **FR-003**: MUST existir el subagente `extractor-documentos`. El orquestador MUST delegar cada documento pasando de forma explícita `documento_id`, nombre y texto completo.
- **FR-004**: El subagente MUST tener como única herramienta `validar_extraccion`.
- **FR-005**: Ante un error de extracción reintentable, el subagente MUST corregir el campo señalado y reintentar, con un tope de seguridad por documento.
- **FR-006**: Si un dato no está en el documento, el agente MUST NOT reintentar ni inventarlo (Principio V): MUST pedirlo al solicitante con `solicitar_informacion`.

**Herramienta de canal**

- **FR-007**: `solicitar_informacion` MUST ser una herramienta local del agente (no del core) que recibe los datos que se piden y el motivo, no modifica el estado del core y deja constancia del pedido en el resultado del turno.

**Decisiones**

- **FR-008**: El agente MUST separar los asuntos de un mensaje (trámite, pregunta por la cuota) y responder de forma unificada. Una pregunta de cuota MUST resolverse solo con la simulación, sin registrar ni preaprobar.
- **FR-009**: Si el solicitante pide hablar con una persona, el agente MUST escalar de inmediato: su primera y única acción es `escalar_a_analista` con causa `solicitud_humano`, sin buscar, verificar, simular ni preguntar antes.
- **FR-010**: El agente MUST escalar por umbral, discrepancia de ingresos, inconsistencia documental, identidad bloqueada y casos que la política no cubre, usando las causas que devuelve el core, con un resumen completo y con procedencia. MUST NOT escalar lo que puede resolver (datos faltantes, aclaraciones, errores transitorios).
- **FR-011**: El agente MUST NOT comunicar una preaprobación que `preaprobar_credito` no haya registrado: la respuesta se basa solo en el resultado de esa herramienta.
- **FR-012**: Ante un error `transitorio` reintentable, el agente MUST reintentar de forma acotada; ante `negocio` o `permisos`, MUST NOT reintentar y MUST actuar según el código.
- **FR-013**: Las reglas 1 y 2 MUST seguir garantizadas por los hooks de #6, que el orquestador registra al crear el agente; los prompts las mencionan como guía, no como garantía (Principio II).

**Aislamiento y configuración**

- **FR-014**: El agente MUST NOT heredar configuración de Claude Code del repositorio ni del usuario y MUST disponer solo de las herramientas de una lista permitida: las del core, `solicitar_informacion` y la delegación al subagente; ninguna de archivos, shell ni red.
- **FR-015**: La clave de la API MUST leerse de la variable de entorno `ANTHROPIC_API_KEY` (la aplicación puede cargarla desde un archivo local ignorado por git) y MUST NOT aparecer en logs, respuestas ni traza técnica.

**Salida hacia la interfaz (#8)**

- **FR-016**: Cada turno MUST devolver un resultado estructurado con la respuesta al solicitante, los avisos (crédito preaprobado, información solicitada, escalamiento, bloqueo por regla de negocio), la traza técnica (herramientas con entrada y salida, delegaciones y razón de parada) y las negaciones de los hooks de #6.

**Prompts**

- **FR-017**: Los prompts MUST estar en español y versionados en el repositorio, y describir cuándo simular, pedir información, escalar o preaprobar; el contenido determinista (reglas, umbrales) MUST NOT vivir en ellos.

**Pruebas**

- **FR-018**: MUST haber pruebas sin modelo del control del ciclo (todas las razones de parada, con secuencias de mensajes del SDK guionizadas), de la definición del subagente, de las opciones del agente (aislamiento, lista de herramientas, hooks), de `solicitar_informacion`, del ensamblado del resultado y del manejo de errores.
- **FR-019**: MUST haber un conjunto pequeño de pruebas con el modelo real que no formen parte de la suite por defecto y requieran la clave: solicitud dentro de política que se preaprueba, petición de hablar con una persona que escala de inmediato, dato ausente que se pide, mensaje mixto con solicitud y pregunta, y un intento de preaprobar sin identidad que bloquea el hook. Usan estado temporal y datos ficticios.

**Escalamientos en GitHub**

- **FR-020**: Los escalamientos MUST quedar guardados en el core con su resumen completo (#5). Reflejarlos como ticket en GitHub (Principio VI) queda **fuera de esta feature** y se atiende en una posterior, anotada como trabajo futuro.

### Key Entities

- **Mensaje del solicitante**: texto y documentos adjuntos.
- **Documento adjunto**: `documento_id`, nombre y texto completo.
- **Delegación**: encargo de extracción de un documento al subagente, con su resultado (extracción validada o datos faltantes).
- **Pedido de información**: datos que se piden al solicitante y motivo.
- **Resultado del turno**: respuesta, avisos, traza técnica, razón de parada y negaciones de los hooks.
- **Aviso**: tipo (crédito preaprobado, información solicitada, escalamiento, bloqueo por regla) y contenido.
- **Conversación**: sesión que conserva el estado del trámite entre turnos.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El 100% de los turnos terminan por la razón de parada del modelo o por un incidente registrado; ninguno por un conteo fijo de iteraciones en la operación normal.
- **SC-002**: En las pruebas con el modelo real, el 100% de las peticiones de hablar con una persona escalan sin haber buscado ni verificado antes.
- **SC-003**: 0 preaprobaciones comunicadas al solicitante que el core no haya registrado.
- **SC-004**: El 100% de los documentos se delegan con `documento_id`, nombre y texto completo.
- **SC-005**: 0 herramientas disponibles fuera de la lista permitida y 0 fuentes de configuración heredadas.
- **SC-006**: El valor de la clave de la API no aparece en ningún log, respuesta ni traza (se comprueba en un test con una clave ficticia).
- **SC-007**: Un intento de preaprobar sin identidad verificada es bloqueado por el hook en el 100% de las pruebas con el modelo real.

## Assumptions

- **Clave de la API**: la define quien ejecuta el agente en el entorno o en un archivo local ignorado por git; el asistente de desarrollo no la lee. Las pruebas con el modelo real consumen saldo y se ejecutan de forma explícita.
- **Modelos y parámetros**: se eligen en el plan (research); la spec no fija ninguno.
- **Interfaz**: #7 entrega el agente como una biblioteca con un resultado estructurado por turno; el chat visual es #8.
- **Dato ausente**: un campo nulo en la extracción es la señal de "no está en el documento"; el agente lo pide, no lo reintenta.
- **Topes de seguridad** (iteraciones y reintentos): protegen contra bucles y coste; sus valores se fijan en el plan y nunca deciden el fin normal del ciclo.
- **Reglas de negocio**: viven en el core (#5), la política (#3) y los hooks (#6); los prompts solo guían el juicio (Principio II).
- **Casos de prueba obligatorios** de la constitución a nivel de agente: se completan en #9; las pruebas con modelo real de esta feature son un conjunto de humo.
- **Tickets de escalamiento en GitHub**: fuera de alcance (decisión del usuario); el escalamiento ya se guarda en el core. El Principio VI queda pendiente hasta esa feature.
- **Sesión**: una conversación atiende a un solo solicitante y su estado vive en memoria mientras dura.
- Los textos y datos de prueba son 100% ficticios.
