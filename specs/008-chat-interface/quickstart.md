# Quickstart: validar la interfaz de chat

## Prerrequisitos

```bash
uv sync --group dev        # starlette y uvicorn ya vienen con el entorno
```

La clave de la API va en `ANTHROPIC_API_KEY`: en tu entorno o en el archivo local ignorado por
git. El asistente de desarrollo no la lee; la lee el programa con
`crediagil.config.cargar_entorno()`.

## Validación automática, sin modelo, sin red y sin clave

```bash
uv run pytest src/crediagil/chat     # adjuntos, casos, serialización, sesión, API y estáticos
uv run pytest                        # suite completa (excluye las pruebas con modelo real)
uv run ruff check
```

Casos en [contracts/api.md](./contracts/api.md).

## Arrancar la interfaz

```bash
uv run python -m crediagil.chat      # http://127.0.0.1:8000 (CREDIAGIL_CHAT_PUERTO cambia el puerto)
```

## Recorrido manual en el navegador (el JavaScript no tiene prueba automática)

| # | Qué hacer | Esperado |
|---|-----------|----------|
| 1 | Abrir la página sin clave definida | Mensaje que dice qué variable falta, sin ningún valor |
| 2 | Elegir el caso "Solicitud dentro de política" y enviar | Se rellenan mensaje y adjunto sin enviarse; al enviar, el hilo muestra el mensaje y, al terminar, la respuesta con el aviso **Crédito preaprobado** |
| 3 | Abrir el desplegable del turno | Herramientas en orden con entrada y salida, la delegación al extractor marcada como de subagente, razón de parada y coste; estaba cerrado antes de abrirlo |
| 4 | Elegir "Pedir hablar con una persona" y enviar | Aviso **Escalado a un analista** con referencia y causa; primera herramienta del detalle: `escalar_a_analista` |
| 5 | Elegir "Dato ausente" y enviar | Aviso **Información solicitada** con el dato y el motivo |
| 6 | Elegir "Preaprobar sin identidad" y enviar | Ningún aviso de preaprobación; si el modelo lo intentó, aviso **Bloqueado por una regla de negocio** con el código y el motivo |
| 7 | Adjuntar un `.pdf`, un archivo vacío y uno de más de 100 KiB | Cada uno se rechaza con su mensaje y el mensaje escrito no se pierde |
| 8 | Poner 1 en la falla simulada y pulsar "Nueva conversación", luego enviar el caso 1 | Indicador de simulación activa; el detalle muestra una llamada fallida y su reintento |
| 9 | Pulsar "Reiniciar datos" y cancelar la confirmación | No cambia nada |
| 10 | Pulsar "Reiniciar datos" y confirmar | Hilo vacío; una nueva solicitud del mismo caso vuelve a empezar desde la semilla |
| 11 | Enviar un mensaje largo y pulsar enviar de nuevo mientras trabaja | Los controles quedan deshabilitados y se ve el indicador de "trabajando"; no se duplica el mensaje |
| 12 | Reducir la ventana a 360 px | Hilo, avisos y desplegable sin desplazamiento horizontal; se usa con teclado |

## Prueba con el modelo real (opt-in, consume saldo)

```bash
uv run pytest -m live -k chat -s     # una solicitud completa a través de la API
```

Se salta si no hay clave. El coste exacto lo informa el campo `costo_usd` del turno.

## Resultado de las validaciones automáticas (2026-10-18)

| Comprobación | Resultado |
|--------------|-----------|
| `uv run pytest` | 850 pasan, 7 con modelo real deseleccionados |
| `uv run ruff check` y `ruff format --check` | limpios |
| `uv run pytest -m live -k chat -s` | 1 pasa: solicitud completa por la API, aviso **Crédito preaprobado**, delegación al extractor en la traza; coste USD 0,049 |
| Arranque real (`python -m crediagil.chat`, otro puerto) | `GET /` 200 `text/html`, `/api/estado`, `/api/casos` (6 casos) y `/static/app.js` responden; reiniciar sin confirmar da `CONFIRMACION_REQUERIDA` |
| Sintaxis de `app.js` (`node --check`) | válida (la comprueba `test_estaticos.py` si hay Node) |
| Claves, `innerHTML` y umbrales en lo nuevo | no hay |

**Recorrido manual** (T036): los 12 pasos de la tabla anterior, incluidos teclado y 360 px, los
ejecutó una persona en el navegador (2026-10-18) y no se anotaron discrepancias.
