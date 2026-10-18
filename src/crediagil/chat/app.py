"""API y página de la interfaz de chat (spec 008, contracts/api.md).

La interfaz solo muestra y opera: no aplica reglas de negocio. Cada ruta traduce HTTP a la
sesión del agente o a una función pura; los errores tienen siempre la forma
`{"error": {"codigo": ..., "mensaje": ...}}` y pasan por `redactar` (sin clave).
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from importlib.resources import files

import anyio
from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from crediagil.agent.opciones import ConfigAgente
from crediagil.agent.orquestador import ClienteSDK
from crediagil.chat.adjuntos import (
    EXTENSIONES,
    LIMITE_ADJUNTOS,
    LIMITE_BYTES_ADJUNTO,
    ErrorAdjunto,
    decodificar_adjuntos,
)
from crediagil.chat.casos import casos_publicos
from crediagil.chat.serializacion import turno_a_dict
from crediagil.chat.sesion import FallaInvalida, Sesion, TurnoEnCurso
from crediagil.config import ConfiguracionError, cargar_entorno, obtener_api_key, redactar

registro_log = logging.getLogger("crediagil.chat")

ESTATICOS = {
    "app.js": "text/javascript; charset=utf-8",
    "estilos.css": "text/css; charset=utf-8",
}


class ErrorApi(Exception):
    """Error de la API con su estado HTTP y su código estable."""

    def __init__(self, estado: int, codigo: str, mensaje: str) -> None:
        super().__init__(mensaje)
        self.estado = estado
        self.codigo = codigo
        self.mensaje = mensaje


def _respuesta_error(estado: int, codigo: str, mensaje: str) -> JSONResponse:
    cuerpo = {"error": {"codigo": codigo, "mensaje": redactar(mensaje)}}
    return JSONResponse(cuerpo, status_code=estado, headers={"Cache-Control": "no-store"})


async def manejar_error_api(_request: Request, exc: Exception) -> Response:
    assert isinstance(exc, ErrorApi)
    return _respuesta_error(exc.estado, exc.codigo, exc.mensaje)


async def manejar_excepcion(_request: Request, exc: Exception) -> Response:
    """Cualquier fallo no previsto: mensaje genérico, sin traza ni valores internos."""
    registro_log.error("Error inesperado en la API: %s", redactar(repr(exc)))
    return _respuesta_error(500, "ERROR_INTERNO", "Ocurrió un error interno. Inténtalo de nuevo.")


async def leer_json(request: Request, opcional: bool = False) -> dict:
    """Cuerpo JSON que debe ser un objeto. Con `opcional`, un cuerpo vacío equivale a `{}`."""
    crudo = await request.body()
    if opcional and not crudo.strip():
        return {}
    try:
        datos = json.loads(crudo)
    except ValueError:
        datos = None
    if not isinstance(datos, dict):
        raise ErrorApi(400, "JSON_INVALIDO", "El cuerpo debe ser un objeto JSON.")
    return datos


def _recurso(nombre: str) -> bytes:
    return files("crediagil.chat").joinpath("static", nombre).read_bytes()


async def pagina(_request: Request) -> Response:
    return Response(
        _recurso("index.html"),
        media_type="text/html",
        headers={"Cache-Control": "no-store"},
    )


async def estatico(request: Request) -> Response:
    nombre = request.path_params["nombre"]
    if nombre not in ESTATICOS:
        raise ErrorApi(404, "NO_ENCONTRADO", "No existe ese archivo.")
    return Response(
        _recurso(nombre),
        media_type=ESTATICOS[nombre].split(";")[0],
        headers={"Cache-Control": "no-store"},
    )


def _turno_en_curso() -> ErrorApi:
    return ErrorApi(
        409,
        "TURNO_EN_CURSO",
        "El agente está trabajando en un turno. Espera a que termine.",
    )


async def crear_turno(request: Request) -> Response:
    sesion: Sesion = request.app.state.sesion
    datos = await leer_json(request)

    mensaje = datos.get("mensaje")
    if not isinstance(mensaje, str) or not mensaje.strip():
        raise ErrorApi(400, "MENSAJE_VACIO", "Escribe un mensaje antes de enviarlo.")

    try:
        documentos = decodificar_adjuntos(datos.get("adjuntos"))
    except ErrorAdjunto as exc:
        raise ErrorApi(400, exc.codigo, exc.mensaje) from None

    try:
        hecho = await sesion.turno(mensaje, documentos)
    except TurnoEnCurso:
        raise _turno_en_curso() from None
    except ConfiguracionError as exc:
        raise ErrorApi(503, "CLAVE_NO_CONFIGURADA", str(exc)) from None
    except Exception as exc:  # noqa: BLE001 — el agente no pudo abrirse: error claro y redactado
        registro_log.error("No se pudo abrir el agente: %s", redactar(repr(exc)))
        raise ErrorApi(
            502, "ERROR_AGENTE", f"No se pudo abrir el agente: {redactar(str(exc))}"
        ) from None
    return JSONResponse(
        turno_a_dict(hecho.resultado, hecho.id_turno), headers={"Cache-Control": "no-store"}
    )


async def crear_conversacion(request: Request) -> Response:
    sesion: Sesion = request.app.state.sesion
    datos = await leer_json(request, opcional=True)
    try:
        await sesion.nueva(datos.get("falla_llamadas", 0))
    except FallaInvalida as exc:
        raise ErrorApi(422, "PARAMETRO_INVALIDO", str(exc)) from None
    except TurnoEnCurso:
        raise _turno_en_curso() from None
    estado = sesion.estado()
    return JSONResponse(
        {
            "id": estado["conversacion"]["id"],
            "falla_llamadas": estado["falla_simulada"]["llamadas"],
        },
        status_code=201,
        headers={"Cache-Control": "no-store"},
    )


def _clave_configurada() -> bool:
    cargar_entorno()
    try:
        obtener_api_key()
    except ConfiguracionError:
        return False
    return True


async def estado(request: Request) -> Response:
    """Lo que la página necesita al abrir: nunca incluye el valor de la clave (FR-021)."""
    sesion: Sesion = request.app.state.sesion
    legible = await anyio.to_thread.run_sync(sesion.estado_core_legible)
    cuerpo = {
        "clave_configurada": _clave_configurada(),
        "estado_core_legible": legible,
        **sesion.estado(),
        "limites": {
            "max_adjuntos": LIMITE_ADJUNTOS,
            "max_bytes_adjunto": LIMITE_BYTES_ADJUNTO,
            "extensiones": list(EXTENSIONES),
        },
    }
    return JSONResponse(cuerpo, headers={"Cache-Control": "no-store"})


async def listar_casos(_request: Request) -> Response:
    return JSONResponse({"casos": casos_publicos()}, headers={"Cache-Control": "no-store"})


async def reiniciar_datos(request: Request) -> Response:
    sesion: Sesion = request.app.state.sesion
    datos = await leer_json(request, opcional=True)
    if datos.get("confirmar") is not True:
        raise ErrorApi(
            400,
            "CONFIRMACION_REQUERIDA",
            "Reiniciar borra las solicitudes y los escalamientos guardados: confirma la acción.",
        )
    try:
        await sesion.reiniciar_datos()
    except TurnoEnCurso:
        raise _turno_en_curso() from None
    return JSONResponse(
        {"conversacion": sesion.estado()["conversacion"]}, headers={"Cache-Control": "no-store"}
    )


def crear_app(
    config: ConfigAgente | None = None,
    cliente_factory: Callable[[ClaudeAgentOptions], ClienteSDK] = ClaudeSDKClient,
    sesion: Sesion | None = None,
) -> Starlette:
    sesion = sesion if sesion is not None else Sesion(config, cliente_factory)

    @asynccontextmanager
    async def ciclo_de_vida(_app: Starlette) -> AsyncIterator[None]:
        try:
            yield
        finally:
            await sesion.cerrar()

    app = Starlette(
        routes=[
            Route("/", pagina),
            Route("/static/{nombre}", estatico),
            Route("/api/turnos", crear_turno, methods=["POST"]),
            Route("/api/conversaciones", crear_conversacion, methods=["POST"]),
            Route("/api/estado", estado),
            Route("/api/casos", listar_casos),
            Route("/api/datos/reiniciar", reiniciar_datos, methods=["POST"]),
        ],
        exception_handlers={ErrorApi: manejar_error_api, Exception: manejar_excepcion},
        lifespan=ciclo_de_vida,
    )
    app.state.sesion = sesion
    return app
