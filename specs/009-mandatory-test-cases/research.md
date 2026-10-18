# Research: Casos de prueba obligatorios

Todo lo marcado como decisión sale de leer el código de #3 a #8 (no de suposiciones); los
puntos que dependen de la clave se verifican en la implementación.

## R1 — Dónde vive el catálogo

- **Decision**: `src/crediagil/casos/`, una carpeta por caso, como datos del paquete.
- **Rationale**: la interfaz (#8) sirve los casos en ejecución; si estuvieran fuera de
  `src/crediagil` dependerían del directorio de trabajo y no viajarían con el paquete. Dentro,
  `hatchling` los incluye sin configuración (`packages = ["src/crediagil"]`). Los tests quedan
  junto a los datos (Principio VII).
- **Alternatives considered**: carpeta `casos/` en la raíz (no se instala y exige rutas
  relativas al repositorio); construir los documentos en código como hace `documentos_prueba.py`
  (incumple "cada caso tiene su carpeta con el mensaje y sus documentos" y no se pueden revisar
  sin leer Python); un único `casos.json` (mezcla mensajes largos y documentos en un archivo
  difícil de revisar).

## R2 — Qué lleva una carpeta de caso

- **Decision**: `caso.json` (id, número, nombre, descripción, obligatorio, falla simulada,
  solicitud estructurada y resultado esperado), `mensaje.md` (lo que escribe el solicitante),
  `documentos/` (lo que adjunta) y `extraccion/` (lo que el extractor debe devolver de cada
  documento: el JSON de `validar_extraccion`, con `{valor, fragmento}`).
- **Rationale**: sin modelo, los tests no pueden ejecutar al extractor; necesitan su salida
  esperada. Guardarla junto al documento la hace revisable y permite validar que cada fragmento
  sea literal del texto (Principio VI). La solicitud estructurada (monto, plazo, ingreso
  declarado, id del solicitante) es lo que el agente pasaría a `registrar_solicitud`; un test de
  coherencia comprueba que los números aparecen en el mensaje, para que no diverjan.
- **Alternatives considered**: derivar la extracción con una heurística en los tests (sería
  reimplementar al extractor); omitir la extracción y probar solo política (dejaría fuera la
  regla de datos ausentes y de moneda, que viven en la validación y el ingreso verificado).

## R3 — Vocabulario cerrado del resultado esperado

- **Decision**: `esperado.resultado` ∈ {`preaprobar`, `solicitar_dato`, `escalar`, `bloquear`,
  `reintentar`}; `esperado.causa` obligatoria cuando es `escalar`: `regla_2` (monto o cuota),
  `regla_3` (discrepancia), `moneda` (fuera de política) o `solicitud_humano`.
- **Rationale**: son exactamente los desenlaces de los ocho casos y coinciden con los códigos
  que ya devuelven el core (`NO_PREAPROBABLE`, `INGRESO_NO_VERIFICABLE`), los hallazgos de
  ingreso (`regla`, `campo`) y la causa del escalamiento. Un vocabulario cerrado deja que el
  cargador rechace errores de escritura y que cada valor tenga un único test que lo resuelve.
- **Alternatives considered**: texto libre (no se puede comprobar); un enum por caso (acopla el
  catálogo a los tests y no escala a casos nuevos).

## R4 — Cómo se resuelve cada caso sin modelo

- **Decision**: `test_casos.py` define un resolutor por valor de `esperado.resultado`, que usa las
  piezas reales con un `AlmacenEstado` temporal:
  - `preaprobar`: verifica identidad con `verificar_identidad` (datos de la semilla), registra
    con las extracciones esperadas, comprueba la evaluación y la preaprobación efectiva, y que el
    hook de preaprobación la permite.
  - `solicitar_dato`: valida la extracción (campo nulo, sin inferencia) y comprueba que registrar
    da `INGRESO_NO_VERIFICABLE` con el dato faltante; nada se compromete ni se escala.
  - `escalar` con `regla_2`, `regla_3` o `moneda`: registra, comprueba la causa en la evaluación,
    que `preaprobar_credito` da `NO_PREAPROBABLE` y que el hook la niega.
  - `escalar` con `solicitud_humano`: `escalar_a_analista` funciona sin identidad, sin solicitud
    previa y sin ninguna otra llamada, y deja el escalamiento en el estado.
  - `bloquear`: con identidad sin verificar, los hooks niegan `registrar_solicitud` y
    `preaprobar_credito`, y cada negación queda en el registro.
  - `reintentar`: con `InyectorFallas(restantes=n)` la primera llamada da un error transitorio
    reintentable, el reintento tiene éxito y el estado final es idéntico al de una ejecución sin
    falla; un error de negocio o de permisos no es reintentable.
- **Rationale**: prueba las reglas con las mismas funciones que usan el core y los hooks, de modo
  que ningún test reimplementa lógica de negocio (Principio II). Todo en memoria o con el
  servidor MCP en proceso: segundos.
- **Alternatives considered**: mockear la política (probaría el mock); lanzar el servidor MCP por
  stdio en cada caso (lento; solo `test_server_stdio.py` lo necesita).

## R5 — Bordes de las reglas

- **Decision**: `test_bordes.py` parte del documento del caso 1 y varía una sola cosa por prueba,
  con valores **derivados** de `crediagil.policy.params` y de `calcular_cuota`, sin literales:
  monto = tope y tope + 1; ingreso verificado tal que cuota = proporción máxima exacta y un peso
  menos; ingreso declarado a diferencia exacta del máximo y un peso más. Más identidad no
  verificada, solicitud de humano y caso fuera de política (los tres ya son casos).
- **Rationale**: Principio VII exige exactamente en el umbral, justo por debajo y justo por
  encima. Derivar los valores hace que una enmienda de la constitución se refleje en un solo
  lugar (`params.py`, que `test_params.py` ya verifica contra la constitución).
- **Alternatives considered**: repetir los literales de `test_originacion.py` (violaría "no
  repitas umbrales"); ampliar solo `test_originacion.py` (dejaría el borde fuera de la suite de
  casos que pide el issue).

## R6 — Pruebas con el modelo real dirigidas por el catálogo

- **Decision**: `casos/test_vivo.py` parametrizado por el catálogo; cada caso declara en
  `esperado.herramientas` lo que debe cumplirse sobre la traza: `primera`, `debe_llamar`,
  `no_debe_llamar`, `en_orden` (subsecuencia) y `avisos` / `sin_avisos` por tipo. Una función
  única evalúa esa declaración. Se retiran de `agent/test_vivo.py` las pruebas por caso que pasan
  al catálogo (dentro de política, humano, dato ausente, preaprobar sin identidad, falla
  transitoria); el mensaje mixto sigue allí con su comprobación propia, porque su aserción
  (simulación de 10 millones sin registrarla) no es declarativa.
- **Rationale**: un solo lugar describe lo esperado del caso, para las pruebas deterministas, la
  prueba viva y la documentación. No se paga dos veces el mismo escenario (cada prueba viva
  cuesta del orden de USD 0,05 a 0,10). Las aserciones específicas que hoy tienen las pruebas de
  #7 (causa `solicitud_humano` en la primera llamada, a lo sumo una validación aceptada en el
  dato ausente, ninguna llamada repetida tras la falla) se trasladan como claves opcionales de
  `esperado.herramientas` para no perder fuerza.
- **Alternatives considered**: dejar ambas suites (duplica coste y mantenimiento); orden total de
  herramientas (el modelo puede variar legítimamente el orden de las secundarias, como se vio
  en #7).
- **Verificación pendiente en la implementación**: los casos 3, 4 y 6 solo se conocen con el
  modelo real; si el modelo se comporta distinto de lo esperado, se ajusta el prompt solo si
  el defecto es real y se documenta (FR-017 prohíbe cambiar reglas, no corregir un defecto del
  prompt, que en tal caso va en su propia spec).

### Resultado de la primera ejecución con el modelo real (2026-10-18)

`uv run pytest -m live -k casos -s`: **5 pasan y 3 fallan**; coste total USD 0,33 (entre 0,014 y
0,073 por caso). Pasan `dentro_de_politica`, `dato_ausente`, `monto_sobre_umbral`,
`preaprobar_sin_identidad` y `falla_transitoria`. Fallan `ingreso_discrepante`, `moneda_extranjera`
y `pedir_persona`, las tres con el mismo incumplimiento: `avisos: falta el aviso escalamiento`.

**Causa (defecto del agente, no de la prueba)**: el modelo llamó de 3 a 5 veces a
`escalar_a_analista` y todas las llamadas devolvieron `RESUMEN_INCOMPLETO`. El parámetro `resumen`
de la herramienta es un `dict` sin tipos para el modelo, que inventa nombres de campo
(`plazo_meses` o `cuota_estimada` en lugar de `plazo`; `datos` como objeto en lugar de lista;
causas como `moneda_no_soportada` u `otra_moneda`), y el error devuelve en `campos_faltantes`
tanto los que sobran como los que faltan, sin distinguirlos, así que no converge. En
`monto_sobre_umbral` la segunda llamada sí funcionó; en `pedir_persona`, que sí pasó en #7, falló
las cinco veces: el defecto es de contrato (herramienta mal descrita), no de un caso concreto. El
resultado para el solicitante es grave: **no se registra el escalamiento** aunque el agente diga
que lo hizo.

**Decisión**: FR-017 prohíbe cambiar aquí reglas, prompts o comportamiento del agente, así que las
tres pruebas quedan **rojas a propósito** (son las que detectan el defecto) y no se debilitan. La
corrección va en su propia spec: tipar `resumen` en el esquema de la herramienta (campos, tipos y
valores de `causa` visibles para el modelo) y hacer que `RESUMEN_INCOMPLETO` separe `campos_faltantes`
de `campos_desconocidos`; al terminar, las tres pruebas deben pasar sin cambios. Mientras tanto se
ejecutan con `-k casos` y se esperan estos tres fallos.

## R7 — Marca de las pruebas con el modelo real

- **Decision**: se mantiene `live` (ya configurada, con `addopts = "-m 'not live'"`, en la
  documentación y en #7 y #8). La documentación explica que equivale al `e2e` del enunciado.
- **Rationale**: dos marcas para lo mismo confundirían, y renombrar rompería los comandos
  documentados. El criterio del issue ("pruebas e2e con el modelo real que verifican qué
  herramientas usó el agente") se cumple en fondo.
- **Alternatives considered**: renombrar a `e2e` (cambio transversal sin beneficio funcional);
  registrar `e2e` como alias (dos nombres para una cosa).
- **A confirmar con el usuario**: si prefiere `e2e` literal, es un cambio de nombre localizado
  (marca, `addopts`, `-k`, README y CLAUDE.md).

## R8 — Datos con forma real

- **Decision**: `test_datos_ficticios.py` importa por ruta `block_sensitive_data.py` (el detector
  `find_in_line` y `luhn_valid`) y lo aplica a cada línea de cada texto del catálogo (mensaje,
  documentos, extracciones y `caso.json`); falla si hay hallazgos sin el marcador `dato-ficticio`
  en la misma línea. Además, todo identificador largo con forma de documento debe llevar el
  prefijo `TEST-`.
- **Rationale**: la misma regla que el hook de Claude Code, sin copiarla; así el repositorio
  cumple por una vía que no depende de que Claude escriba el archivo (el CI de #11 podrá
  ejecutarla).
- **Alternatives considered**: reescribir el detector en `src/` (dos implementaciones que
  divergirán); solo confiar en el hook (no cubre archivos creados fuera de Claude).
- **Detalle**: el detector marca la palabra "documento" seguida de un número (hasta 30
  caracteres sin dígitos entre ambos), de modo que una frase del estilo "mi documento es" más el
  id de prueba exigiría el marcador `dato-ficticio` dentro del mensaje, que vería el usuario en
  la interfaz. Los mensajes del catálogo usan "identificación" en lugar de esa palabra (el id
  `TEST-…` no activa ninguna otra etiqueta), y los documentos solo llevan nombres y montos. Así
  ningún texto necesita el marcador y el test no admite excepciones: cualquier hallazgo sin
  marcador falla.

## R9 — La interfaz sigue leyendo un solo catálogo

- **Decision**: `chat/casos.py` conserva `CasoPrueba`, `CASOS`, `caso_por_id` y `casos_publicos()`
  con la misma forma de `GET /api/casos`, pero construidos desde `crediagil.casos`. Se añade el
  campo `obligatorio` y el número al JSON público para distinguir los complementarios.
  `chat/test_casos.py` pasa a exigir los ocho ids obligatorios y conserva sus comprobaciones
  (ficticio, sin umbrales).
- **Rationale**: SC-007; añadir un caso aparece en la interfaz y en los tests sin editar otro
  archivo. La API es compatible hacia atrás.
- **Alternatives considered**: que la interfaz lea el catálogo directamente (la capa HTTP no
  debería conocer el formato de carpeta); mantener la lista duplicada (viola FR-003).

## R10 — Identificadores de los casos de #8

- **Decision**: se conservan `dentro_de_politica`, `pedir_persona`, `dato_ausente`,
  `preaprobar_sin_identidad`, `falla_transitoria` y `mensaje_mixto`; se añaden
  `ingreso_discrepante`, `monto_sobre_umbral` y `moneda_extranjera`. Los números 1 a 8 siguen el
  orden del issue.
- **Rationale**: ningún id publicado por la API cambia; solo se añaden.

## Preguntas resueltas

No quedan `NEEDS CLARIFICATION`. R7 queda como decisión por defecto, a confirmar.
