# Research: Interfaz de chat

Decisiones de Phase 0 para la [spec](./spec.md). Lo verificado contra el código y el SDK
instalados (Claude Agent SDK 0.2.168, Starlette 1.8, uvicorn 0.54) lo está indicado.

## R1. Tecnología: aplicación web local con Starlette + uvicorn

**Decisión**: una aplicación web local que sirve una página estática y una API JSON pequeña,
con Starlette y uvicorn, en `crediagil.chat`. Se arranca con `uv run python -m crediagil.chat` y
escucha solo en `127.0.0.1`.

**Por qué**:
- Starlette y uvicorn ya están instalados como dependencias transitivas de `mcp`; se declaran de
  forma explícita y no añaden nada nuevo al entorno. `TestClient` de Starlette funciona sin
  instalar nada más (verificado).
- Un único proceso Python, sin Node ni paso de compilación.
- El desplegable, los avisos con rótulo y el hilo se resuelven bien en HTML; en terminal no.

**Alternativas descartadas**:
- Streamlit, Gradio o NiceGUI: dependencias grandes y nuevas, menos control del HTML (avisos,
  accesibilidad, no interpretar contenido) y más superficie.
- FastAPI: no está instalado y no aporta nada que Starlette no dé aquí.
- Interfaz de terminal: no cubre bien desplegables ni avisos destacados (FR-010, FR-014).
- Aplicación de una sola página con framework (React, etc.): exige Node y compilación para una
  demostración local.

## R2. Interfaz sin framework: HTML, CSS y JavaScript estáticos

**Decisión**: tres archivos estáticos (`index.html`, `app.js`, `estilos.css`) servidos desde el
paquete. El desplegable es el elemento nativo `<details>`, cerrado por defecto. Todo texto de
usuario, de documentos o del modelo se inserta con `textContent`, nunca con `innerHTML`.

**Por qué**: `<details>` es accesible con teclado y no requiere código (FR-014, FR-025); usar
`textContent` hace imposible ejecutar el contenido (FR-024). Un test recorre `app.js` y falla si
aparece `innerHTML`, `outerHTML`, `insertAdjacentHTML`, `eval(` o `document.write`.

**Alternativa descartada**: renderizar markdown. Añade una librería y un riesgo de inyección; el
texto se muestra con saltos de línea preservados (`white-space: pre-wrap`), que basta para leer
listas y párrafos.

## R3. El agente vive entre peticiones HTTP (verificado)

**Pregunta**: el SDK usa `anyio`; cada petición web corre en una tarea distinta. ¿Se puede abrir
el `Agente` en una petición, usarlo en turnos de otras y cerrarlo en una tercera?

**Verificación** (asyncio, SDK 0.2.168, sin servidor): abrir con `__aenter__` en una tarea, hacer
dos turnos, cada uno en una tarea nueva, y cerrar con `__aexit__` en otra. Resultado: los dos
turnos terminan en `fin_de_turno`, el segundo conserva el contexto del primero y el cierre no
lanza errores. Coste: unos USD 0,04 en total. También funciona conectar y desconectar en tareas
distintas sin consulta.

**Decisión**: la sesión de la interfaz guarda un único `Agente` abierto con `__aenter__` y lo
cierra con `__aexit__`; no hace falta una tarea de fondo dueña del agente.

**Límite conocido**: la prueba cubre dos turnos y asyncio. Si en el futuro el SDK exigiera la
misma tarea, la corrección es una tarea dueña del agente con una cola; queda como plan B.

## R4. Concurrencia: una conversación y un turno a la vez

**Decisión**: la sesión tiene un `asyncio.Lock`. Mientras haya un turno en curso, nuevos turnos,
conversaciones nuevas y reinicios devuelven `409 TURNO_EN_CURSO` (FR-003). La interfaz también
deshabilita los controles, pero el servidor es la autoridad.

**Por qué**: el agente conserva un contexto secuencial; dos turnos simultáneos lo mezclarían.

## R5. Conversación nueva, falla simulada y reinicio de datos

- **Conversación nueva**: cierra el agente actual y deja la sesión sin agente; el siguiente turno
  abre uno nuevo (apertura perezosa), con el hilo vacío y los datos del core intactos.
- **Falla transitoria**: el core se lanza junto con el agente, así que `CREDIAGIL_MCP_FALLAS_N` se
  pasa por `ConfigAgente.entorno_core` (ya existe desde #7) al crear la conversación. Cambiarla
  implica una conversación nueva (supuesto de la spec). Rango admitido: 0 a 20; 0 la desactiva.
- **Reiniciar datos**: un método nuevo `AlmacenEstado.reiniciar()` escribe la semilla bajo el
  bloqueo del archivo (reutiliza `estado_semilla()`); después se abre una conversación nueva.
  Se exige `confirmar: true` en la petición.

**Alternativa descartada**: borrar el archivo de estado. Compite con el servidor del core, que
puede estar leyéndolo; escribir la semilla bajo el mismo bloqueo no.

## R6. Adjuntos: el servidor decide

**Decisión**: el navegador lee cada archivo como bytes y los envía en base64 dentro del JSON; el
servidor los valida y decodifica de forma estricta. Así no se necesita procesar formularios
`multipart` y la decodificación UTF-8 estricta (con BOM tolerado) detecta archivos ilegibles que
`File.text()` del navegador taparía con caracteres de reemplazo.

| Regla | Valor |
|-------|-------|
| Extensiones | `.txt` y `.md` (sin distinguir mayúsculas) |
| Tamaño máximo por archivo | 100 KiB |
| Adjuntos por mensaje | 5 |
| Vacío | texto vacío o solo espacios → rechazado |
| Codificación | UTF-8 (con o sin BOM); otra cosa → ilegible |
| Nombre | se quita cualquier ruta; no puede quedar vacío |

Los límites sobran para certificados y extractos de prueba y evitan enviar al modelo archivos
enormes por error. El navegador repite las comprobaciones solo como ayuda (FR-008).

## R7. Avisos y detalle técnico: salen del resultado, nunca del texto

**Decisión**: la API serializa el `ResultadoTurno` de #7 tal cual (avisos, traza, negaciones,
parada, coste) y le añade el rótulo de cada tipo de aviso desde una única tabla en Python
(`ROTULOS_AVISO`). La interfaz pinta un aviso por cada elemento de `avisos` y ninguno más
(FR-012). Los avisos se distinguen por rótulo e icono además de color (FR-013).

| Tipo de aviso | Rótulo |
|---------------|--------|
| `credito_preaprobado` | Crédito preaprobado |
| `informacion_solicitada` | Información solicitada |
| `escalamiento` | Escalado a un analista |
| `bloqueo_regla` | Bloqueado por una regla de negocio |

Toda la respuesta JSON pasa por `redactar` antes de salir (defensa en profundidad: la traza ya
viene redactada de #7) (FR-016).

## R8. Catálogo de casos de prueba

**Decisión**: `crediagil.chat.casos.CASOS`, una tupla de `CasoPrueba` con nombre, descripción,
mensaje, adjuntos y, opcionalmente, una falla sugerida. Parte de los escenarios ya comprobados
con el modelo real en #7: solicitud dentro de política, pedir hablar con una persona, dato
ausente, mensaje mixto, preaprobar sin identidad y falla transitoria. Los textos de los
documentos salen de `crediagil.mcp_server.documentos_prueba` y los identificadores llevan el
prefijo `TEST-` con `pragma: dato-ficticio`.

**Por qué**: la lista la sirve la API (`GET /api/casos`), así que la interfaz no tiene casos
escritos a mano y #9 puede ampliar el catálogo sin tocar la interfaz.

## R9. Pruebas

- **Sin modelo, red ni clave**: funciones puras (`adjuntos`, `casos`, `serializacion`), la sesión
  con un cliente SDK falso (el mismo patrón de #7) y la aplicación con `TestClient`. Un test
  recorre los archivos estáticos buscando construcciones inseguras y comprobando los elementos
  que la interfaz necesita.
- **Con modelo real**: una sola prueba opt-in (`@pytest.mark.live`) que hace una solicitud
  completa a través de la API y comprueba el aviso de preaprobación.
- **Sin navegador**: no hay herramienta de pruebas de navegador instalada. El comportamiento del
  JavaScript se valida a mano con `quickstart.md`; lo verificable por código vive en la API y en
  la serialización, y el JavaScript se mantiene fino a propósito.

## R10. Qué queda fuera y los riesgos conocidos

- Sin autenticación: la aplicación solo escucha en `127.0.0.1`. **Hueco conocido**: no comprueba
  `Origin` ni `Host`, así que una página web abierta en el mismo equipo podría enviar peticiones
  a la API local y gastar saldo. Se deja como trabajo futuro, junto con el ticket de GitHub al
  escalar (Principio VI) heredado de #7.
- Sin historial entre sesiones ni persistencia del hilo (supuesto de la spec).
