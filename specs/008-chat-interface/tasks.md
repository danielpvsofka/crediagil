# Tasks: Interfaz de chat

**Input**: Design documents from `specs/008-chat-interface/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/api.md](./contracts/api.md), [quickstart.md](./quickstart.md)

**Tests**: obligatorios (FR-026, Principio VII). Los tests van junto al código, se escriben
primero y deben fallar. Los de lo determinista no usan el modelo, la red ni la clave: la sesión se
prueba con un cliente SDK falso que emite mensajes **reales** del SDK (el mismo patrón de
`src/crediagil/agent/test_orquestador.py`) y la API con `TestClient` de Starlette. Los fixtures de
`src/crediagil/chat/` ponen una clave ficticia en el entorno cuando la sesión la exige. La única
prueba con el modelo real lleva `@pytest.mark.live`, se salta sin clave y usa estado temporal,
datos ficticios y un tope de coste.

**Sin navegador**: no hay herramienta de pruebas de navegador. Todo lo verificable por código vive
en la API, la serialización y los archivos estáticos (`test_estaticos.py` los lee como texto). El
comportamiento del JavaScript lo valida a mano el recorrido de `quickstart.md` (T036).

**Orden de las fases**: US1, US2 y US3 son P1, pero todas se apoyan en el hilo y en la API de
turnos, así que US1 va primero. US2 y US3 solo añaden a esa base; US4, US5 y US6 (P2) también.
La prueba con el modelo real y el recorrido manual van al final porque necesitan todo lo anterior.

**La clave**: `ANTHROPIC_API_KEY` en el entorno o en el archivo local ignorado por git. Nadie la
imprime ni la lee: solo la lee el programa. La tarea con el modelo real (T034) consume saldo y se
ejecuta con confirmación; informa el coste (`costo_usd`).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: paralelizable (archivo distinto, sin dependencias pendientes)
- **[Story]**: historia de spec.md (US1–US6)
- Todas las rutas son relativas a la raíz del repositorio; `chat/` es `src/crediagil/chat/`.

---

## Phase 1: Setup

- [x] T001 En `pyproject.toml`, añadir `"starlette"` y `"uvicorn"` a `dependencies`. Crear `src/crediagil/chat/__init__.py` (docstring de una línea) y la carpeta `src/crediagil/chat/static/` con un `.gitkeep`. Ejecutar `uv sync --group dev` y comprobar que `uv run pytest -q` sigue en verde y que `uv run python -c "import starlette, uvicorn"` funciona.

---

## Phase 2: Foundational (bloquea US1–US6)

**Purpose**: la serialización del resultado del turno y el esqueleto de la API, que todas las
historias usan.

- [x] T002 [P] Tests de la serialización, que deben fallar, en `src/crediagil/chat/test_serializacion.py` (data-model.md "Turno", research R7), con `ResultadoTurno`, `Aviso`, `EventoTraza` y `Negacion` reales de #7:
  - `turno_a_dict(resultado, id_turno)` devuelve exactamente las claves `id_turno`, `respuesta`, `error`, `parada`, `razon_parada`, `costo_usd`, `avisos`, `traza`, `negaciones` y `pedidos_informacion`; `parada` es el valor del enum (`"fin_de_turno"`, …);
  - cada aviso lleva `tipo`, `rotulo` y `contenido`; `ROTULOS_AVISO` tiene los cuatro tipos con estos rótulos exactos: `credito_preaprobado` → "Crédito preaprobado", `informacion_solicitada` → "Información solicitada", `escalamiento` → "Escalado a un analista", `bloqueo_regla` → "Bloqueado por una regla de negocio"; un tipo desconocido usa el propio tipo como rótulo;
  - un resultado sin avisos da `avisos == []` (nunca se inventa uno);
  - la traza conserva el orden, `de_subagente`, `es_error`, `entrada`, `salida` y `stop_reason`;
  - las negaciones salen como `herramienta`, `codigo`, `mensaje` y `accion`; los pedidos como `datos` y `motivo`;
  - con una clave ficticia en el entorno (`ANTHROPIC_API_KEY`), ningún texto de la salida la contiene (se serializa a JSON y se busca), aunque aparezca en `respuesta`, `error`, `entrada` o `salida`;
  - la salida es serializable con `json.dumps` sin errores.
- [x] T003 Implementar `src/crediagil/chat/serializacion.py`: `ROTULOS_AVISO`, y `turno_a_dict(resultado, id_turno) -> dict` que convierte con `dataclasses`, serializa a JSON, aplica `crediagil.config.redactar` al texto completo y vuelve a cargarlo. Hacer pasar T002.
- [x] T004 [P] Tests del esqueleto de la API, que deben fallar, en `src/crediagil/chat/test_app.py` (contracts/api.md "Convenciones"), con `TestClient(crear_app(...))` y un fixture que arme la app con un cliente falso:
  - `GET /` devuelve `200`, `text/html` y contiene los `id` `hilo`, `formulario`, `mensaje` y `enviar`;
  - `GET /static/app.js` y `GET /static/estilos.css` devuelven `200` con sus tipos de contenido; `GET /static/inexistente.js` da `404`;
  - un error de la API tiene la forma `{"error": {"codigo": "...", "mensaje": "..."}}`; un cuerpo que no es un objeto JSON (`[]`, `"x"`, texto no JSON) en una ruta POST da `400 JSON_INVALIDO`;
  - el mensaje de ningún error trae una traza ni la clave ficticia del entorno.
- [x] T005 Implementar el esqueleto en `src/crediagil/chat/app.py` y los tres archivos de `src/crediagil/chat/static/`: `crear_app(config=None, cliente_factory=ClaudeSDKClient) -> Starlette`, `ErrorApi(estado, codigo, mensaje)` con su manejador que responde la forma de error (aplicando `redactar`), lectura estricta del cuerpo JSON (`JSON_INVALIDO`), y las rutas `GET /`, `GET /static/app.js` y `GET /static/estilos.css` servidas con `importlib.resources`. `index.html` incluye por ahora los elementos de T004 y enlaza `app.js` y `estilos.css`, que empiezan vacíos. Hacer pasar T004.

**Checkpoint**: `uv run pytest src/crediagil/chat -q` en verde; hay una API que sirve la página y sabe fallar con el formato acordado.

---

## Phase 3: User Story 1 - Conversar con el agente turno a turno (Priority: P1) 🎯 MVP

**Goal**: un hilo con continuidad, un turno a la vez y errores claros.

**Independent Test**: `uv run pytest src/crediagil/chat/test_sesion.py src/crediagil/chat/test_app.py src/crediagil/chat/test_estaticos.py`; y el caso real con T034.

- [x] T006 [P] [US1] Tests de la sesión, que deben fallar, en `src/crediagil/chat/test_sesion.py` (data-model.md "Sesion", research R3-R4), con un cliente SDK falso que reproduce mensajes reales (copiar el patrón de `src/crediagil/agent/test_orquestador.py`) y una clave ficticia en el entorno:
  - el primer `turno` abre el agente (apertura perezosa) y devuelve un `ResultadoTurno`; `estado()` pasa a `activa == True`, `turnos == 1` y un `id` de conversación;
  - dos turnos seguidos usan **el mismo cliente** (una sola instancia, la segunda consulta llega al mismo objeto) y `turnos == 2`;
  - `nueva()` cierra el agente (el cliente falso queda desconectado), pone `turnos == 0`, cambia el `id` y no abre otro hasta el siguiente turno;
  - con un turno en curso (el cliente falso espera un `asyncio.Event`), un segundo `turno`, `nueva()` y `reiniciar_datos()` lanzan `TurnoEnCurso` sin alterar nada; cuando el primero termina, el siguiente funciona;
  - `cerrar()` desconecta el agente y es idempotente;
  - sin `ANTHROPIC_API_KEY`, `turno` lanza `ConfiguracionError` y no abre el agente;
  - si el agente falla al abrirse (el cliente falso lanza en `connect`), `turno` propaga el error y la sesión queda sin agente y sin cerrojo tomado, lista para reintentar;
  - un turno cuyo `ResultMessage` es de error devuelve un `ResultadoTurno` con `error` (no lanza) y cuenta como turno.
- [x] T007 [US1] Implementar `src/crediagil/chat/sesion.py`: `TurnoEnCurso`, `Sesion(config, cliente_factory)` con el cerrojo `asyncio.Lock` (no bloqueante: si está tomado, `TurnoEnCurso`), `turno(mensaje, documentos)`, `nueva()`, `cerrar()` y `estado()`. El agente se abre con `Agente.__aenter__` y se cierra con `__aexit__`. Hacer pasar T006.
- [x] T008 [P] [US1] Añadir a `src/crediagil/chat/test_app.py` los tests de turnos y conversaciones, que deben fallar (contracts/api.md "Errores" y "Garantías de POST /api/turnos"), con un agente falso:
  - `POST /api/turnos` con `{"mensaje": "hola"}` devuelve `200` con el Turno (`id_turno` 1, la respuesta del falso) y el siguiente devuelve `id_turno` 2 con el mismo agente;
  - `mensaje` vacío, solo espacios o ausente da `400 MENSAJE_VACIO` y **no abre** el agente ni consume un turno;
  - `POST /api/conversaciones` devuelve `201` con `id`, reinicia el contador de turnos y el siguiente turno empieza otra vez en 1;
  - `TurnoEnCurso` se traduce a `409 TURNO_EN_CURSO` tanto en turnos como en conversaciones;
  - `ConfiguracionError` da `503 CLAVE_NO_CONFIGURADA` y su mensaje contiene `ANTHROPIC_API_KEY` y no contiene ningún valor de clave;
  - una excepción al abrir el agente da `502 ERROR_AGENTE` con el mensaje redactado;
  - un turno cuyo modelo falla (resultado con `error`) da `200` con `error` y `parada == "error_api"`, no un error HTTP.
- [x] T009 [US1] En `src/crediagil/chat/app.py` añadir `POST /api/turnos` y `POST /api/conversaciones` con el orden de comprobaciones de contracts/api.md (JSON, mensaje y luego el cerrojo y el agente) y la traducción de excepciones de T008; crear `src/crediagil/chat/__main__.py` que ejecute la app con `uvicorn.run` en `127.0.0.1` y el puerto de `CREDIAGIL_CHAT_PUERTO` (8000 por defecto, con `crediagil.config.cargar_entorno()` antes). Hacer pasar T008.
- [x] T010 [US1] Frontend del hilo en `src/crediagil/chat/static/index.html`, `app.js` y `estilos.css`: hilo `id="hilo"` con `role="log"` y `aria-live="polite"`; mensajes del solicitante y respuestas del agente diferenciados; formulario con `id="mensaje"` (Enter envía, Shift+Enter salta de línea) y `id="enviar"`; indicador `id="estado-agente"` con `role="status"` mientras el turno está en curso y controles deshabilitados hasta que termine (sin doble envío); mensaje vacío no se envía; un error (HTTP o del turno) se pinta como mensaje de error del agente en el hilo; botón `id="nueva-conversacion"` que llama a `POST /api/conversaciones` y vacía el hilo. **Todo texto se inserta con `textContent`**, con `white-space: pre-wrap` en CSS. Diseño adaptable a 360 px, usable con teclado.
- [x] T011 [P] [US1] Tests de los archivos estáticos, en `src/crediagil/chat/test_estaticos.py`, que deben fallar: `app.js` no contiene `innerHTML`, `outerHTML`, `insertAdjacentHTML`, `eval(`, `new Function` ni `document.write`; `index.html` tiene los `id` `hilo`, `formulario`, `mensaje`, `enviar`, `estado-agente` y `nueva-conversacion`; el hilo tiene `role="log"`; el indicador tiene `role="status"`. (Las siguientes historias amplían este archivo.)

**Checkpoint**: se conversa con el agente turno a turno; MVP = Fases 1 a 3.

---

## Phase 4: User Story 2 - Adjuntar documentos .txt o .md (Priority: P1)

**Goal**: adjuntos validados por el servidor y entregados al agente con nombre y texto completo.

**Independent Test**: `uv run pytest src/crediagil/chat/test_adjuntos.py src/crediagil/chat/test_app.py -k adjunto`.

- [x] T012 [P] [US2] Tests de adjuntos, que deben fallar, en `src/crediagil/chat/test_adjuntos.py` (data-model.md "Adjunto", research R6). Citar las reglas literales: `nombre` "No vacío tras quitar rutas; extensión `.txt` o `.md` (sin distinguir mayúsculas)"; `contenido_b64` "Base64 válido; decodifica a UTF-8 (BOM tolerado); como máximo 100 KiB; no vacío ni solo espacios"; "Como máximo 5 por mensaje". Casos de borde:
  - un adjunto válido `.txt` y uno `.MD` producen `DocumentoAdjunto(nombre, texto)` con el texto exacto; con BOM al inicio, el BOM no queda en el texto;
  - exactamente 102.400 bytes se aceptan y 102.401 dan `ADJUNTO_DEMASIADO_GRANDE`;
  - exactamente 5 adjuntos se aceptan y 6 dan `ADJUNTOS_DEMASIADOS`;
  - `.pdf`, `.txt.exe`, sin extensión o `.mdx` dan `EXTENSION_NO_ADMITIDA`;
  - contenido vacío, solo espacios o solo saltos de línea dan `ADJUNTO_VACIO`;
  - base64 inválido y bytes que no son UTF-8 (por ejemplo `b"\xff\xfe\x00"` sin BOM válido) dan `ADJUNTO_ILEGIBLE`;
  - elementos que no son diccionario, sin `nombre`, sin `contenido_b64` o con tipos distintos de texto dan `ADJUNTO_INVALIDO`;
  - un nombre con ruta (`../../x.txt`, `C:\\carpeta\\x.md`) se reduce al nombre base; un nombre que queda vacío da `ADJUNTO_INVALIDO`;
  - nombres repetidos se conservan todos;
  - cada `ErrorAdjunto` trae `codigo` y un `mensaje` claro en español que nombra el archivo y no contiene el contenido.
- [x] T013 [US2] Implementar `src/crediagil/chat/adjuntos.py`: constantes `LIMITE_BYTES_ADJUNTO = 100 * 1024`, `LIMITE_ADJUNTOS = 5` y `EXTENSIONES = (".txt", ".md")`, `ErrorAdjunto(codigo, mensaje)` y `decodificar_adjuntos(entradas) -> list[DocumentoAdjunto]` (usa `crediagil.agent.documentos.DocumentoAdjunto`; decodifica con `utf-8-sig`). Hacer pasar T012.
- [x] T014 [P] [US2] Añadir a `src/crediagil/chat/test_app.py` los tests de adjuntos en `POST /api/turnos`, que deben fallar: cada código de T012 llega como `400` con su `codigo` y **no abre el agente ni cuenta un turno**; un adjunto válido llega al agente (el cliente falso recibe en la consulta `<documento id="DOC-1" nombre="...">texto</documento>` con el texto completo); varios adjuntos válidos llegan todos, con ids `DOC-1`, `DOC-2`; sin adjuntos el mensaje queda igual.
- [x] T015 [US2] En `src/crediagil/chat/app.py`, validar los adjuntos con `decodificar_adjuntos` después del mensaje y antes del cerrojo; traducir `ErrorAdjunto` a `400` con su código. Hacer pasar T014.
- [x] T016 [US2] Frontend de adjuntos en `src/crediagil/chat/static/index.html`, `app.js` y `estilos.css`: selector `id="adjuntar"` (`type="file"`, `multiple`, `accept=".txt,.md"`) y lista `id="adjuntos"` con una ficha por archivo y un botón accesible para quitarla antes de enviar; comprobación previa en el navegador de extensión, tamaño y cantidad con los mismos límites (solo como ayuda: el servidor decide); leer cada archivo como bytes y enviarlo en base64 en `adjuntos`; el mensaje enviado muestra en el hilo los nombres de sus adjuntos; un rechazo (previo o del servidor) se muestra con su mensaje y **no borra el texto escrito**.
- [x] T017 [P] [US2] Ampliar `src/crediagil/chat/test_estaticos.py`: `index.html` tiene `id="adjuntar"` con `accept=".txt,.md"` y `id="adjuntos"`; `app.js` menciona los límites de la API o los lee de `/api/estado`, no los repite con otros valores.

**Checkpoint**: se envían `.txt` y `.md`; lo inválido se rechaza sin perder el mensaje.

---

## Phase 5: User Story 3 - Avisos destacados para lo que importa (Priority: P1)

**Goal**: cuatro avisos diferenciados que salen solo del resultado estructurado del turno.

**Independent Test**: `uv run pytest src/crediagil/chat/test_app.py src/crediagil/chat/test_estaticos.py -k aviso`.

- [x] T018 [P] [US3] Tests de avisos, que deben fallar: en `src/crediagil/chat/test_app.py`, con un agente falso que produce resultados reales de herramientas:
  - un turno con `preaprobar_credito` exitoso devuelve el aviso `credito_preaprobado` con `rotulo` "Crédito preaprobado" y `monto`, `plazo_meses`, `cuota` y `tasa_mensual` en el contenido; `solicitar_informacion` da `informacion_solicitada` con `datos` y `motivo`; `escalar_a_analista` exitoso da `escalamiento` con `id_escalamiento` y `causa`; una negación del registro da `bloqueo_regla` con `herramienta`, `codigo` y `mensaje`;
  - un turno con varios avisos los devuelve todos, en orden;
  - un turno sin avisos devuelve `avisos == []`;
  - **el texto de la respuesta afirma "quedó preaprobado" pero no hay `preaprobar_credito` exitoso** → `avisos == []` (no se inventa el aviso);
  - una preaprobación fallida (`ok: false`) no da aviso.

  En `src/crediagil/chat/test_estaticos.py`: `app.js` contiene un tratamiento para cada uno de los cuatro tipos (`credito_preaprobado`, `informacion_solicitada`, `escalamiento`, `bloqueo_regla`) con su icono y `estilos.css` tiene una clase distinta para cada uno; cada aviso se pinta con el `rotulo` que trae la API (no escrito a mano); el código del aviso no depende solo del color (hay icono y rótulo en el DOM).
- [x] T019 [US3] Frontend de avisos en `src/crediagil/chat/static/app.js` y `estilos.css`: por cada elemento de `avisos` de un turno, pintar una tarjeta destacada con icono, el `rotulo` de la API, una clase por `tipo` y su contenido en lenguaje claro (crédito: monto, plazo, cuota y tasa tal como llegan; información: los datos pedidos y el motivo; escalamiento: la referencia y la causa; bloqueo: qué se intentó, el código y el motivo, y la acción indicada); ningún aviso si `avisos` está vacío; nunca generar un aviso a partir del texto de la respuesta. Contraste suficiente y legible a 360 px. Hacer pasar T018.

**Checkpoint**: los cuatro avisos se ven distintos y solo aparecen los que trae el resultado.

---

## Phase 6: User Story 4 - Detalle técnico en un desplegable (Priority: P2)

**Goal**: la traza de cada turno, cerrada por defecto.

**Independent Test**: `uv run pytest src/crediagil/chat/test_app.py src/crediagil/chat/test_estaticos.py -k detalle`.

- [x] T020 [P] [US4] Tests del detalle técnico, que deben fallar: en `src/crediagil/chat/test_app.py`, un turno con tres herramientas (una de ellas llamada por el subagente y una fallida) devuelve la traza completa **en orden**, con `entrada`, `salida`, `es_error`, `de_subagente` y `stop_reason`, más `razon_parada` y `costo_usd`; un turno sin herramientas devuelve `traza == []` y conserva `parada`; la clave ficticia que aparezca en una entrada o salida **no sale** en la respuesta de la API. En `src/crediagil/chat/test_estaticos.py`: `app.js` crea el detalle con un elemento `details` **sin** el atributo `open` y con un `summary`; marca las llamadas del subagente y las fallidas; muestra la razón de parada y el coste; las entradas y salidas se muestran como texto con `pre-wrap` o equivalente, con desplazamiento propio para lo largo (`overflow` en `estilos.css`).
- [x] T021 [US4] Frontend del detalle en `src/crediagil/chat/static/app.js` y `estilos.css`: tras cada respuesta, un `<details>` cerrado con un `<summary>` ("Detalle técnico") que al abrirse lista cada herramienta en orden con su entrada y su salida (JSON legible), marca las del subagente de extracción y las fallidas, y muestra la razón de parada y el coste si existen; con `traza` vacía, un texto "Sin llamadas a herramientas" y la razón de parada. Textos largos y estructuras anidadas no rompen la disposición. Hacer pasar T020.

**Checkpoint**: el detalle está cerrado por defecto y es completo.

---

## Phase 7: User Story 5 - Preparar y operar la demostración (Priority: P2)

**Goal**: casos de prueba, falla transitoria simulada y reinicio de datos, sin comandos.

**Independent Test**: `uv run pytest src/crediagil/chat/test_casos.py src/crediagil/chat/test_sesion.py src/crediagil/chat/test_app.py src/crediagil/mcp_server/test_estado.py -k "caso or falla or reiniciar"`.

- [x] T022 [P] [US5] Tests del catálogo de casos, que deben fallar, en `src/crediagil/chat/test_casos.py` (data-model.md "CasoPrueba", research R8): hay al menos los seis casos (`dentro_de_politica`, `pedir_persona`, `dato_ausente`, `mensaje_mixto`, `preaprobar_sin_identidad`, `falla_transitoria`); `id` único y en `snake_case`; `nombre`, `descripcion` y `mensaje` no vacíos; los adjuntos son `.txt` o `.md` con texto no vacío; todo identificador de solicitante con forma de documento empieza por `TEST-`; **no aparecen la tasa ni los umbrales** de `crediagil.policy.params` (el monto máximo de preaprobación en varios formatos, ni los porcentajes) en ningún mensaje ni adjunto; `falla_sugerida` es `0` salvo en `falla_transitoria`, que es `1`; un caso "dato ausente" tiene un certificado sin salario; el caso "mensaje mixto" pide simular un monto distinto del solicitado.
- [x] T023 [US5] Implementar `src/crediagil/chat/casos.py`: `CasoPrueba` (`@dataclass(frozen=True)`: `id`, `nombre`, `descripcion`, `mensaje`, `adjuntos`, `falla_sugerida=0`), `CASOS` y `caso_por_id`. Los documentos salen de `crediagil.mcp_server.documentos_prueba.doc_certificado`; los identificadores ficticios (por ejemplo `TEST-100001`) llevan `pragma: dato-ficticio` en la misma línea. Hacer pasar T022.
- [x] T024 [P] [US5] Test de `AlmacenEstado.reiniciar()`, que debe fallar, en `src/crediagil/mcp_server/test_estado.py`: tras registrar una solicitud, un escalamiento y bloquear a un solicitante, `reiniciar()` deja el estado igual a `estado_semilla()`; funciona si el archivo no existe (lo crea con la semilla); se hace bajo el bloqueo del archivo (otra instancia sobre la misma ruta ve la semilla); si el archivo estaba corrupto, `reiniciar()` lo repara.
- [x] T025 [US5] Añadir `AlmacenEstado.reiniciar(self) -> None` en `src/crediagil/mcp_server/estado.py`: con el bloqueo del archivo, escribe `estado_semilla()` con `_escribir`. Hacer pasar T024.
- [x] T026 [P] [US5] Tests de operación, que deben fallar. En `src/crediagil/chat/test_sesion.py`: `nueva(falla_llamadas=N)` pasa `CREDIAGIL_MCP_FALLAS_N=N` en `entorno_core` de la configuración con la que se abre el siguiente agente (se comprueba en las opciones que recibe la fábrica del cliente falso) y `nueva(0)` no la pasa; `estado()` informa las llamadas simuladas; `reiniciar_datos()` deja el estado del core igual a la semilla, cierra el agente, pone `turnos == 0` y abre una conversación nueva. En `src/crediagil/chat/test_app.py`: `GET /api/casos` devuelve `{"casos": [...]}` con `id`, `nombre`, `descripcion`, `mensaje`, `adjuntos` (`nombre` y `texto`) y `falla_sugerida` de cada caso de `CASOS`; `POST /api/conversaciones` con `{"falla_llamadas": N}` acepta los bordes `0` y `20` y rechaza `21`, `-1`, `1.5`, `"x"`, `true` y `null` con `422 PARAMETRO_INVALIDO`; sin cuerpo o con `{}` usa `0`; `POST /api/datos/reiniciar` sin `confirmar: true` (ausente, `false` o `"true"`) da `400 CONFIRMACION_REQUERIDA` y **no borra nada**; con `confirmar: true` devuelve `200`, deja el core en la semilla y la conversación en 0 turnos; durante un turno en curso ambos dan `409`.
- [x] T027 [US5] Implementar en `src/crediagil/chat/sesion.py` `nueva(falla_llamadas=0)` (valida `0 <= n <= 20` entero no booleano, pasa `entorno_core={"CREDIAGIL_MCP_FALLAS_N": str(n)}` con `dataclasses.replace` solo si `n > 0`) y `reiniciar_datos()` (con el cerrojo, `AlmacenEstado(config.ruta_estado).reiniciar()` y `nueva(0)`); en `src/crediagil/chat/app.py`, `GET /api/casos`, el cuerpo `falla_llamadas` de `POST /api/conversaciones` con su validación y `POST /api/datos/reiniciar`. Hacer pasar T026.
- [x] T028 [US5] Frontend de operación en `src/crediagil/chat/static/index.html`, `app.js` y `estilos.css`: selector `id="casos"` poblado desde `GET /api/casos` (nombre y descripción visibles; elegir uno **rellena** mensaje y adjuntos sin enviarlos, y propone la falla sugerida); campo numérico `id="falla"` (0 a 20) junto al botón `nueva-conversacion` de T010, que ahora envía `falla_llamadas` y muestra un indicador mientras la simulación esté activa; botón `id="reiniciar"` que pide `confirm()` antes de llamar a `POST /api/datos/reiniciar` con `confirmar: true`, vacía el hilo y muestra el resultado; ambos botones deshabilitados con un turno en curso. Un valor inválido en `falla` se rechaza con un mensaje claro antes de llamar.

**Checkpoint**: se carga un caso, se simula una falla y se reinician los datos desde la interfaz.

---

## Phase 8: User Story 6 - Arrancar y fallar con claridad (Priority: P2)

**Goal**: la interfaz explica qué falta sin mostrar secretos.

**Independent Test**: `uv run pytest src/crediagil/chat/test_app.py -k estado`.

- [x] T029 [P] [US6] Tests de `GET /api/estado`, que deben fallar, en `src/crediagil/chat/test_app.py` (data-model.md "Estado"): con la clave ficticia definida, `clave_configurada` es `true`; sin clave es `false`; la respuesta **nunca contiene el valor de la clave**; `estado_core_legible` es `true` si el archivo de estado no existe, `true` si es una semilla válida y `false` si existe pero está corrupto; `conversacion` trae `id`, `turnos` y `activa` y cambia tras un turno y tras `nueva`; `falla_simulada.llamadas` refleja la última conversación; `limites` trae `max_adjuntos` 5, `max_bytes_adjunto` 102400 y `extensiones` `[".txt", ".md"]`, iguales a las constantes de `adjuntos.py`.
- [x] T030 [US6] Implementar `GET /api/estado` en `src/crediagil/chat/app.py` (usa `Sesion.estado()` y `AlmacenEstado.leer_existente()` solo si el archivo existe; un `ErrorCore` da `estado_core_legible: false`; nunca incluye el valor de la clave). Hacer pasar T029.
- [x] T031 [US6] Frontend de arranque en `src/crediagil/chat/static/index.html`, `app.js` y `estilos.css`: al cargar, consultar `GET /api/estado` y rellenar `id="aviso-sistema"`: sin clave, un mensaje que dice qué variable falta (`ANTHROPIC_API_KEY`) y cómo definirla, sin valores, y con el envío deshabilitado; con el estado del core ilegible, un mensaje claro que ofrece el botón de reiniciar datos; un `503 CLAVE_NO_CONFIGURADA` o `502 ERROR_AGENTE` al enviar también se muestra ahí o en el hilo con su mensaje; los límites de adjuntos se leen de `limites`. Ampliar `src/crediagil/chat/test_estaticos.py` con la presencia de `id="aviso-sistema"` y de la consulta a `/api/estado` en `app.js`.

**Checkpoint**: sin clave o con el estado ilegible, la interfaz lo explica y no falla en silencio.

---

## Phase 9: Polish & Cross-Cutting

- [x] T032 [P] Prueba con el modelo real, en `src/crediagil/chat/test_vivo.py` (`@pytest.mark.live`; llama a `cargar_entorno()`, se salta si no hay clave, estado temporal y tope de coste): arma la app con `ConfigAgente` real y un `ruta_estado` temporal, usa el caso `dentro_de_politica` de `CASOS` y lo envía por `POST /api/turnos` con sus adjuntos en base64. Se comprueba en el JSON, no en el texto: `avisos` incluye `credito_preaprobado` con rótulo "Crédito preaprobado", `error` es `None`, `parada == "fin_de_turno"`, la traza incluye `registrar_solicitud` y `preaprobar_credito`, y la clave no aparece en la respuesta.
- [x] T033 [P] Actualizar `CLAUDE.md`, sección "Stack y comandos": cómo arrancar la interfaz (`uv run python -m crediagil.chat`, `CREDIAGIL_CHAT_PUERTO`), que escucha solo en `127.0.0.1` y no comprueba `Origin`, que el hilo vive en memoria, que los avisos salen solo del resultado del turno, que el JavaScript no tiene pruebas automáticas (recorrido manual en el quickstart) y la prueba live (`uv run pytest -m live -k chat`).
- [x] T034 Ejecutar `uv run pytest` (suite por defecto, sin las pruebas con modelo real), `uv run ruff check` y `uv run ruff format --check`; todo en verde. Después, con confirmación del usuario porque consume saldo, `uv run pytest -m live -k chat -s`; informar `costo_usd` y registrar el resultado en `specs/008-chat-interface/quickstart.md`.
- [x] T035 Comprobar que no hay claves ni umbrales en lo nuevo: `git grep -n "sk-ant-"` debe salir vacío; `git grep -n -i "innerHTML" -- src/crediagil/chat/static` debe salir vacío; los archivos estáticos y los casos no contienen la tasa ni los umbrales de `crediagil.policy.params` (ya lo comprueban T011 y T022); el archivo local de la clave sigue ignorado por git (se revisa `.gitignore`, sin abrir el archivo de la clave).
- [ ] T036 Recorrido manual del `quickstart.md` por el usuario en su navegador (12 pasos): el asistente arranca la interfaz y el usuario ejecuta cada paso, incluidos los de teclado y 360 px; anotar en el quickstart lo que no coincida y corregirlo antes de dar la feature por terminada. Esta tarea no puede automatizarla el asistente.

---

## Dependencies & Execution Order

```text
Setup (T001) → Foundational (T002–T005)
                    └─▶ US1 (T006–T011) 🎯 MVP
                            ├─▶ US2 (T012–T017)
                            ├─▶ US3 (T018–T019)
                            ├─▶ US4 (T020–T021)
                            ├─▶ US5 (T022–T028)
                            └─▶ US6 (T029–T031)
                                    └─▶ Polish (T032–T036)
```

- US2 a US6 dependen de US1 (el hilo, la sesión y la API de turnos) y de la serialización; entre sí
  son independientes en el backend, pero comparten `app.py`, `app.js` e `index.html`, así que se
  implementan en secuencia aunque sus tests puedan escribirse en paralelo.
- T019 y T021 reutilizan el renderizado de turnos de T010; T028 reutiliza el botón de T010; T031
  reutiliza el envío de T010.
- T034 (parte con modelo real) y T036 necesitan la clave y todo lo anterior.

## Parallel Opportunities

- T002 ∥ T004 (archivos de test distintos).
- T006 ∥ T008 ∥ T011 (tests de US1 en archivos distintos); T012 ∥ T014 ∥ T017.
- T022 ∥ T024 ∥ T026 (tests de US5 en archivos distintos); T029 en paralelo con los demás tests.
- T032 ∥ T033.

## Implementation Strategy

1. **Setup y Foundational**: dependencias, serialización y esqueleto de la API.
2. **MVP (US1)**: sesión con cerrojo, turnos y hilo; se puede conversar con el agente.
3. **US2 y US3 (P1)**: adjuntos y avisos, lo que convierte el chat en un recorrido de originación.
4. **US4, US5 y US6 (P2)**: detalle técnico, operación de la demostración y arranque claro.
5. **Polish**: prueba con el modelo real, documentación, suite completa y recorrido manual.
