# Contrato: API de la interfaz de chat

API JSON local de `crediagil.chat`, consumida solo por la página incluida. Entidades en
[data-model.md](../data-model.md), decisiones en [research.md](../research.md).

## Convenciones

- Base: `http://127.0.0.1:<puerto>` (puerto por defecto 8000, variable `CREDIAGIL_CHAT_PUERTO`).
- Cuerpos y respuestas JSON en UTF-8. Todo texto saliente pasa por `redactar` (sin clave).
- Errores: estado HTTP y cuerpo `{"error": {"codigo": "...", "mensaje": "..."}}`; el mensaje es
  legible y nunca trae trazas ni secretos.

## Rutas

| Método y ruta | Cuerpo | Respuesta |
|---------------|--------|-----------|
| `GET /` | — | La página (`index.html`) |
| `GET /static/app.js`, `GET /static/estilos.css` | — | Archivos estáticos |
| `GET /api/estado` | — | `200` con el Estado de [data-model.md](../data-model.md) |
| `GET /api/casos` | — | `200 {"casos": [{id, nombre, descripcion, mensaje, adjuntos: [{nombre, texto}], falla_sugerida}]}` |
| `POST /api/conversaciones` | `{"falla_llamadas": 0}` (opcional, entero de 0 a 20) | `201 {"id", "falla_llamadas"}`; cierra el agente anterior |
| `POST /api/turnos` | `{"mensaje": "...", "adjuntos": [{"nombre", "contenido_b64"}]}` | `200` con el Turno; abre la conversación si no hay |
| `POST /api/datos/reiniciar` | `{"confirmar": true}` | `200 {"conversacion": {"id", "turnos", "activa"}}`; vuelve el core a la semilla y abre una conversación nueva |

## Errores

| Estado | `codigo` | Cuándo |
|--------|----------|--------|
| 400 | `MENSAJE_VACIO` | `mensaje` vacío o solo espacios, o ausente |
| 400 | `ADJUNTOS_DEMASIADOS` | más de 5 adjuntos |
| 400 | `ADJUNTO_INVALIDO` | un adjunto sin `nombre` o `contenido_b64`, o con otro tipo de dato |
| 400 | `EXTENSION_NO_ADMITIDA` | extensión distinta de `.txt` y `.md` |
| 400 | `ADJUNTO_VACIO` | el texto está vacío o solo tiene espacios |
| 400 | `ADJUNTO_ILEGIBLE` | no es base64 válido o no decodifica como UTF-8 |
| 400 | `ADJUNTO_DEMASIADO_GRANDE` | supera 100 KiB |
| 400 | `CONFIRMACION_REQUERIDA` | reiniciar sin `confirmar: true` |
| 400 | `JSON_INVALIDO` | cuerpo que no es un objeto JSON |
| 422 | `PARAMETRO_INVALIDO` | `falla_llamadas` no entero, negativo o mayor que 20 |
| 409 | `TURNO_EN_CURSO` | hay un turno en marcha (turno, conversación nueva o reinicio) |
| 503 | `CLAVE_NO_CONFIGURADA` | falta `ANTHROPIC_API_KEY`; el mensaje dice qué definir, sin valores |
| 502 | `ERROR_AGENTE` | el agente no pudo abrirse o falló fuera del turno; mensaje redactado |

Un turno cuyo modelo falla **no** es un error HTTP: devuelve `200` con `error` y `parada`
(`error_api`), porque el hilo lo muestra como un mensaje de error del agente.

## Garantías de `POST /api/turnos`

| Caso | Comportamiento |
|------|----------------|
| Orden de las comprobaciones | JSON, mensaje, adjuntos y, solo después, el cerrojo y el agente; una entrada inválida no abre ni consume nada |
| Adjuntos | se entregan al agente con nombre y texto completo; los ids `DOC-n` los asigna el agente |
| Resultado | los avisos son exactamente los de `ResultadoTurno.avisos`; el texto de la respuesta no genera avisos |
| Concurrencia | un segundo turno, una conversación nueva o un reinicio durante un turno devuelven `409` sin tocar nada |
| Sin clave | `503` antes de abrir el agente |

## Página (`index.html`)

Elementos mínimos, con estos `id` para las pruebas:

| `id` | Qué es |
|------|--------|
| `hilo` | Región del hilo (`role="log"`, `aria-live="polite"`) |
| `formulario`, `mensaje`, `enviar` | Cuadro de mensaje y botón de enviar |
| `adjuntar`, `adjuntos` | Selector de archivos (`accept=".txt,.md"`) y lista de elegidos, con botón para quitar cada uno |
| `estado-agente` | Indicador de "trabajando" (`role="status"`) |
| `casos` | Selector de casos de prueba |
| `falla`, `nueva-conversacion` | Número de llamadas que fallan y botón para empezar una conversación con esa falla |
| `reiniciar` | Botón de reiniciar datos (pide confirmación) |
| `aviso-sistema` | Mensajes de arranque (falta la clave, estado ilegible) |

Cada respuesta del agente se pinta con sus avisos (cada uno con rótulo, icono y su clase por tipo)
y un `<details>` cerrado por defecto con el detalle técnico del turno.
