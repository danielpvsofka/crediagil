# Feature Specification: Interfaz de chat

**Feature Branch**: `develop` (sin hook de rama; directorio de spec: `specs/008-chat-interface`)

**Created**: 2026-10-18

**Status**: Draft

**Issue**: [#8](https://github.com/danielpvsofka/crediagil/issues/8) · **Depende de**: #7 · **Habilita**: #9

**Input**: User description: "Interfaz de chat — La interacción con el agente debe verse como un chat que alguien sin conocer el código pueda entender. Criterios: se ven los mensajes del solicitante y las respuestas del agente turno a turno, con continuidad de la conversación; se pueden adjuntar documentos .txt o .md; avisos destacados y diferenciados para crédito preaprobado, información solicitada, escalamiento a analista y bloqueo por regla de negocio; el detalle técnico (herramientas, entradas, salidas, razón de parada) queda en un desplegable, sin estorbar la lectura; se pueden cargar los casos de prueba, simular una falla transitoria y reiniciar los datos desde la interfaz. Depende de #7. Issue: #8"

> **Nota de alcance**: la interfaz solo **muestra y opera**. No aplica reglas de negocio ni decide
> nada: todo lo que enseña sale del resultado de cada turno del agente (#7), en particular los
> avisos, la traza y las negaciones de los hooks (#6). Las reglas, la tasa y los umbrales viven
> solo en la constitución, en la política (#3) y en el core (#5); la interfaz no los repite.
> La tecnología, el diseño visual y la forma de arrancar la interfaz se deciden en
> `/speckit-plan`.

## User Scenarios & Testing *(mandatory)*

Actores: **solicitante** (escribe y adjunta documentos), **agente** (#7), **persona que opera la
demostración** (carga casos, simula fallas y reinicia datos; puede ser la misma persona que el
solicitante) y **revisor técnico** (abre el detalle cuando quiere ver qué hizo el agente).

### User Story 1 - Conversar con el agente turno a turno (Priority: P1)

El solicitante escribe un mensaje y ve, en el mismo orden en que ocurrieron, sus mensajes y las
respuestas del agente, como en cualquier chat. La conversación conserva el contexto: no tiene que
repetir lo que ya dijo.

**Why this priority**: sin esto no hay interfaz; todo lo demás se apoya en el hilo de mensajes.

**Independent Test**: con un agente simulado (sin modelo), enviar varios mensajes seguidos y
comprobar el hilo visible y que cada turno se entrega al mismo agente; con el modelo real, una
solicitud completa de dos turnos.

**Acceptance Scenarios**:

1. **Given** una conversación nueva, **When** el solicitante envía un mensaje, **Then** aparece en el hilo como suyo y, al terminar el turno, aparece la respuesta del agente debajo, diferenciada visualmente.
2. **Given** una conversación con turnos previos, **When** el solicitante envía otro mensaje, **Then** el agente lo recibe dentro de la misma conversación (conserva el contexto) y el hilo mantiene el orden cronológico.
3. **Given** un turno en curso, **When** el agente aún no ha respondido, **Then** se ve claramente que está trabajando y no se puede enviar otro mensaje hasta que termine.
4. **Given** que el turno termina con un error (por ejemplo, el servicio del modelo no responde), **When** se muestra, **Then** el hilo enseña un mensaje de error claro en lugar de una respuesta, sin trazas internas ni la clave de la API, y la conversación sigue utilizable.
5. **Given** un mensaje vacío o solo con espacios, **When** el solicitante intenta enviarlo, **Then** no se envía.

---

### User Story 2 - Adjuntar documentos .txt o .md (Priority: P1)

El solicitante adjunta uno o varios documentos de texto (certificados, extractos) al mensaje y el
agente los recibe junto con él.

**Why this priority**: el agente decide a partir de los documentos; sin adjuntos no hay
originación.

**Independent Test**: adjuntar archivos válidos e inválidos y comprobar qué recibe el agente y
qué ve el usuario.

**Acceptance Scenarios**:

1. **Given** el cuadro de mensaje, **When** el solicitante adjunta uno o varios archivos `.txt` o `.md` y envía, **Then** el agente los recibe con su nombre y su texto completo, y el hilo muestra qué adjuntos acompañaron al mensaje.
2. **Given** un archivo con otra extensión, **When** se intenta adjuntar, **Then** se rechaza antes de enviar, con un mensaje que indica los formatos admitidos.
3. **Given** un archivo vacío, **When** se adjunta, **Then** se avisa de que no tiene contenido y no se envía como documento.
4. **Given** un archivo cuyo contenido no se puede leer como texto, o que supera el tamaño máximo admitido, **When** se adjunta, **Then** se rechaza con un mensaje claro y el resto del mensaje no se pierde.
5. **Given** adjuntos ya elegidos, **When** el solicitante cambia de opinión, **Then** puede quitar un adjunto antes de enviar.

---

### User Story 3 - Avisos destacados para lo que importa (Priority: P1)

Cuando ocurre algo que el solicitante o el analista deben notar —un crédito preaprobado, una
información que se pide, un escalamiento a un analista o un bloqueo por una regla de negocio—, la
interfaz lo destaca con un aviso propio y distinguible, aparte del texto de la respuesta.

**Why this priority**: es lo que permite entender de un vistazo el resultado sin leer todo, y
evita confiar en lo que el modelo diga en prosa.

**Independent Test**: con resultados de turno simulados que traigan cada tipo de aviso, comprobar
que cada uno se pinta distinto y con su contenido; y que un turno sin avisos no muestra ninguno.

**Acceptance Scenarios**:

1. **Given** un turno con crédito preaprobado, **When** se muestra, **Then** aparece un aviso de "crédito preaprobado" con monto, plazo, cuota y tasa tal como los devolvió el agente.
2. **Given** un turno en el que se pide información, **When** se muestra, **Then** aparece un aviso de "información solicitada" con los datos pedidos y el motivo.
3. **Given** un turno escalado, **When** se muestra, **Then** aparece un aviso de "escalamiento a analista" con la referencia del escalamiento y la causa.
4. **Given** una llamada impedida por una regla de negocio (hook), **When** se muestra, **Then** aparece un aviso de "bloqueo por regla de negocio" con qué se intentó, el código y el motivo en lenguaje claro.
5. **Given** un turno que no produjo ningún aviso, **When** se muestra, **Then** solo se ve la respuesta del agente.
6. **Given** que el texto de la respuesta afirma algo (por ejemplo, "quedó preaprobado") pero el resultado del turno no trae el aviso correspondiente, **When** se muestra, **Then** la interfaz no inventa el aviso: los avisos salen solo del resultado estructurado del turno.
7. **Given** un turno con varios avisos, **When** se muestra, **Then** todos aparecen, cada uno diferenciado.

---

### User Story 4 - Detalle técnico en un desplegable (Priority: P2)

Quien quiera ver cómo llegó el agente a su respuesta abre un desplegable por turno con las
herramientas llamadas, sus entradas y salidas y la razón de parada. Por defecto está cerrado y no
estorba la lectura de la conversación.

**Why this priority**: da trazabilidad (Principio VI) a quien la necesita sin ensuciar el chat
de quien no.

**Independent Test**: con un turno simulado con traza de varias herramientas, un subagente y un
error, comprobar el contenido del desplegable y que empieza cerrado.

**Acceptance Scenarios**:

1. **Given** un turno terminado, **When** se muestra, **Then** incluye un desplegable cerrado por defecto con el detalle técnico de ese turno.
2. **Given** el desplegable abierto, **When** se lee, **Then** lista en orden cada herramienta llamada con su entrada y su salida, marca las del subagente de extracción y las llamadas que fallaron, y muestra la razón de parada y el coste del turno si se conocen.
3. **Given** entradas o salidas con textos largos o estructuras anidadas, **When** se muestran, **Then** se leen sin romper la disposición de la página.
4. **Given** cualquier detalle técnico, **When** se muestra, **Then** no contiene la clave de la API ni valores de secretos.
5. **Given** un turno sin herramientas, **When** se muestra, **Then** el desplegable indica que no hubo llamadas y sigue mostrando la razón de parada.

---

### User Story 5 - Preparar y operar la demostración (Priority: P2)

Desde la propia interfaz, quien opera la demostración puede cargar casos de prueba ya preparados,
simular una falla transitoria del core y reiniciar los datos, sin tocar archivos ni comandos.

**Why this priority**: permite enseñar y probar cada comportamiento del agente en minutos y
repetirlo desde un estado limpio.

**Independent Test**: cargar un caso, comprobar que rellena el mensaje y sus adjuntos; activar la
falla y comprobar que el agente la sufre y se recupera; reiniciar y comprobar que el estado
vuelve al inicial.

**Acceptance Scenarios**:

1. **Given** el selector de casos de prueba, **When** se elige uno, **Then** se rellenan el mensaje y los adjuntos de ese caso para revisarlos y enviarlos (no se envían solos).
2. **Given** los casos disponibles, **When** se listan, **Then** cada uno muestra un nombre y una descripción de qué comportamiento ejercita, y todos usan datos ficticios.
3. **Given** la opción de simular una falla transitoria, **When** se activa e indica cuántas llamadas fallan, **Then** las siguientes llamadas al core fallan de forma transitoria ese número de veces y la interfaz muestra que la simulación está activa.
4. **Given** una falla simulada activa, **When** el agente la sufre, **Then** el detalle técnico muestra la llamada fallida y el reintento.
5. **Given** la acción de reiniciar los datos, **When** se confirma, **Then** se borran las solicitudes, escalamientos y verificaciones guardados, el estado vuelve al inicial y se empieza una conversación nueva.
6. **Given** la acción de reiniciar, **When** se pulsa, **Then** pide confirmación antes de borrar.
7. **Given** una nueva conversación sin reiniciar datos, **When** se inicia, **Then** el hilo parte vacío pero los datos guardados se conservan.

---

### User Story 6 - Arrancar y fallar con claridad (Priority: P2)

Si falta la clave de la API o el entorno no está listo, la interfaz lo dice con un mensaje
comprensible que indica qué hacer, sin mostrar ningún valor secreto, en lugar de fallar en
silencio o con trazas.

**Why this priority**: es lo primero que ve quien la ejecuta por primera vez.

**Independent Test**: arrancar sin clave y comprobar el mensaje; arrancar con una clave inválida
y comprobar el error del primer turno.

**Acceptance Scenarios**:

1. **Given** que no hay clave de la API configurada, **When** se abre la interfaz, **Then** muestra un mensaje que dice qué variable falta y cómo definirla, sin mostrar valores.
2. **Given** una clave inválida o un fallo del servicio del modelo, **When** se envía un mensaje, **Then** el hilo muestra un error claro y la clave nunca aparece (US1, escenario 4).
3. **Given** que el estado del core no se puede leer, **When** ocurre, **Then** la interfaz lo informa con un mensaje claro y ofrece reiniciar los datos.

---

### Edge Cases

- **Doble envío**: pulsar enviar varias veces mientras el turno está en curso no genera mensajes duplicados.
- **Cierre o recarga de la página a mitad de conversación**: la conversación puede perderse; la interfaz no debe dejar el agente colgado ni mostrar un turno a medias como si hubiera terminado. Los datos ya guardados en el core se conservan.
- **Turno muy largo**: se ve que sigue trabajando; no se queda sin señal de vida.
- **Respuesta con formato** (listas, negritas): se muestra legible, y nunca se interpreta como código ejecutable.
- **Contenido de documentos o respuestas con marcado o scripts**: se muestra como texto, sin ejecutarse.
- **Varios adjuntos con el mismo nombre**: se distinguen en el hilo y se envían todos.
- **Casos de prueba que cambian después**: la lista se construye a partir de lo definido, no está escrita a mano en la interfaz.
- **Reiniciar durante un turno en curso**: no se permite hasta que termine, o se cancela de forma explícita; nunca deja el estado a medias.
- **Simular una falla con un número inválido** (cero, negativo, no numérico): se rechaza con un mensaje claro.
- **Pantalla pequeña**: el hilo, los avisos y el desplegable siguen siendo legibles.

## Requirements *(mandatory)*

### Functional Requirements

**Conversación (US1)**

- **FR-001**: La interfaz MUST mostrar en el hilo los mensajes del solicitante y las respuestas del agente, turno a turno y en orden cronológico, diferenciando visualmente quién habla.
- **FR-002**: La conversación MUST conservar el contexto entre turnos: cada mensaje se entrega al mismo agente mientras la conversación siga abierta.
- **FR-003**: Mientras un turno está en curso, la interfaz MUST indicarlo y MUST impedir enviar otro mensaje o reiniciar hasta que termine.
- **FR-004**: La interfaz MUST NOT enviar mensajes vacíos o de solo espacios.
- **FR-005**: Cuando un turno termina con error, la interfaz MUST mostrar un mensaje de error claro en el hilo, sin trazas internas ni valores secretos, y la conversación MUST seguir siendo utilizable.
- **FR-006**: La interfaz MUST permitir iniciar una conversación nueva, que parte con el hilo vacío y conserva los datos guardados.

**Adjuntos (US2)**

- **FR-007**: La interfaz MUST permitir adjuntar uno o varios archivos `.txt` o `.md` a cada mensaje y entregarlos al agente con su nombre y su texto completo.
- **FR-008**: La interfaz MUST rechazar, antes de enviar y con un mensaje claro, los archivos con otra extensión, vacíos, ilegibles como texto o que superen el tamaño máximo admitido, sin perder el resto del mensaje.
- **FR-009**: La interfaz MUST mostrar en el hilo qué adjuntos acompañaron a cada mensaje y MUST permitir quitar un adjunto antes de enviar.

**Avisos (US3)**

- **FR-010**: La interfaz MUST destacar, con un aviso diferenciado por tipo, cada aviso que traiga el resultado del turno: crédito preaprobado, información solicitada, escalamiento a analista y bloqueo por regla de negocio.
- **FR-011**: Cada aviso MUST mostrar el contenido que trae el resultado: monto, plazo, cuota y tasa del crédito preaprobado; datos pedidos y motivo; referencia y causa del escalamiento; herramienta, código y motivo del bloqueo.
- **FR-012**: La interfaz MUST derivar los avisos únicamente del resultado estructurado del turno, nunca del texto de la respuesta, y MUST NOT mostrar un aviso que el resultado no trae.
- **FR-013**: Los avisos MUST ser distinguibles por algo más que el color (por ejemplo, un rótulo y un icono), de modo que no dependan de percibir el color.

**Detalle técnico (US4)**

- **FR-014**: Cada turno terminado MUST incluir un desplegable, cerrado por defecto, con su detalle técnico: herramientas llamadas en orden, con entrada y salida, razón de parada y, si se conoce, el coste.
- **FR-015**: El detalle MUST marcar las llamadas del subagente de extracción y las que fallaron, y MUST mostrar bien textos largos y estructuras anidadas sin romper la página.
- **FR-016**: Ni la conversación ni el detalle técnico MUST mostrar la clave de la API ni valores de secretos.

**Operación de la demostración (US5)**

- **FR-017**: La interfaz MUST ofrecer un selector de casos de prueba construido a partir de los casos definidos, con nombre y descripción; elegir uno MUST rellenar el mensaje y los adjuntos sin enviarlos.
- **FR-018**: Todos los casos de prueba MUST usar datos exclusivamente ficticios (Principio III).
- **FR-019**: La interfaz MUST permitir simular una falla transitoria del core indicando cuántas llamadas fallan, MUST rechazar valores inválidos y MUST mostrar cuándo la simulación está activa.
- **FR-020**: La interfaz MUST permitir reiniciar los datos, con confirmación previa, devolviendo el estado del core al inicial y empezando una conversación nueva.

**Arranque y errores (US6)**

- **FR-021**: Si falta la clave de la API, la interfaz MUST decir qué variable falta y cómo definirla, sin mostrar valores.
- **FR-022**: Si el estado del core no se puede leer, la interfaz MUST informarlo con un mensaje claro y ofrecer reiniciar los datos.

**Transversales**

- **FR-023**: La interfaz MUST NOT aplicar ni repetir reglas de negocio, la tasa ni los umbrales: solo muestra lo que devuelve el agente (Principios I y II).
- **FR-024**: El contenido de mensajes, documentos y respuestas MUST mostrarse como texto, sin interpretarse como código ejecutable.
- **FR-025**: La interfaz MUST ser legible en pantallas pequeñas y utilizable con teclado.
- **FR-026**: Todo comportamiento de la interfaz MUST tener pruebas sin modelo real (con un agente simulado) y las pruebas MUST NOT depender de la red ni de la clave; las comprobaciones con el modelo real son opcionales y quedan aparte (Principio VII).

### Key Entities

- **Conversación**: el hilo de turnos con un mismo agente; tiene un identificador, conserva el contexto y puede reiniciarse o cerrarse.
- **Mensaje**: lo que escribe el solicitante en un turno, con sus adjuntos y su hora.
- **Adjunto**: documento `.txt` o `.md` con nombre y texto completo.
- **Turno**: un mensaje del solicitante y el resultado del agente: respuesta, avisos, detalle técnico, razón de parada, coste y error si lo hubo.
- **Aviso**: destacado de uno de cuatro tipos (crédito preaprobado, información solicitada, escalamiento, bloqueo por regla) con su contenido.
- **Detalle técnico**: la traza del turno (herramientas, entradas, salidas, marcas de subagente y de fallo) y la razón de parada.
- **Caso de prueba**: un escenario ficticio con nombre, descripción, mensaje y adjuntos.
- **Simulación de falla**: la configuración, activa o no, de cuántas llamadas al core fallan de forma transitoria.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Una persona que no conoce el código completa, sin ayuda, una solicitud de dos turnos con un adjunto en menos de 3 minutos desde que abre la interfaz.
- **SC-002**: En una prueba con cada uno de los cuatro tipos de aviso, el 100 % se distinguen entre sí y de una respuesta normal por su rótulo, sin depender del color.
- **SC-003**: En el 100 % de los turnos, ningún aviso aparece si el resultado del turno no lo trae, y todo aviso del resultado aparece.
- **SC-004**: El detalle técnico está cerrado en el 100 % de los turnos al renderizarse y contiene todas las herramientas llamadas, en orden.
- **SC-005**: En el 100 % de las pruebas, la clave de la API no aparece en el hilo, los avisos, el detalle ni los mensajes de error.
- **SC-006**: Cargar un caso de prueba, simular una falla transitoria y reiniciar los datos se hace en menos de 1 minuto cada uno, sin comandos ni edición de archivos.
- **SC-007**: Tras reiniciar los datos, el estado del core coincide con el inicial en el 100 % de las veces.
- **SC-008**: La suite de pruebas de la interfaz se ejecuta sin modelo real, sin red y sin clave en menos de 1 minuto.
- **SC-009**: En una pantalla de 360 px de ancho, el hilo, los avisos y el desplegable se leen sin desplazamiento horizontal.

## Assumptions

- **Entrega de la interfaz**: es una aplicación local de uso individual, que se abre desde el navegador; no hay cuentas, autenticación ni varios usuarios simultáneos (se decide en `/speckit-plan`).
- **Una conversación a la vez**: la interfaz mantiene una conversación activa; los datos del core se comparten entre conversaciones hasta que se reinicien.
- **Casos de prueba**: son un catálogo pequeño de escenarios ficticios definido en el repositorio, que parte de los comportamientos ya comprobados con el modelo real en #7 (solicitud dentro de política, pedir una persona, dato ausente, mensaje mixto, preaprobar sin identidad). #9 los completa y verifica; aquí solo se cargan.
- **Simular falla**: usa el mecanismo de fallas transitorias del core (#5); como el core se lanza junto con el agente, activarla o cambiarla implica empezar una conversación nueva con la misma base de datos.
- **Reiniciar datos**: devuelve el estado a la semilla ficticia del core y empieza una conversación nueva.
- **Tamaño de adjuntos**: se fija un máximo razonable por archivo y por mensaje, y se rechaza lo que lo supere (el valor exacto se decide en el plan).
- **Sin persistencia del hilo**: el hilo vive mientras la conversación esté abierta; cerrar la página puede perderlo. Lo guardado en el core se conserva.
- **Idioma**: la interfaz está en español.
- **Fuera de alcance**: autenticación, múltiples usuarios, historial entre sesiones, edición o borrado de mensajes ya enviados, descarga de la conversación, ticket de GitHub al escalar (Principio VI, trabajo futuro desde #7) y los casos de prueba obligatorios completos (#9).
- **Dependencias**: el agente y su resultado estructurado de #7 (`Agente`, `ResultadoTurno`), la clave de la API configurada, y el core y sus fallas inyectables de #4 y #5.
