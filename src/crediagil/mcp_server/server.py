"""Servidor MCP del core de originación simulado (stdio).

Arranque: `python -m crediagil.mcp_server.server`. Cada herramienta pasa por `_responder`, el
único punto que construye respuestas: así toda salida cumple el contrato `{ok, ...}` /
`{ok: false, error}` y ninguna excepción interna se filtra (FR-001, FR-004). Las reglas de
negocio de la constitución no viven aquí: se hacen cumplir en hooks del Agent SDK (#6).
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from typing import Any

from mcp.server import MCPServer

from crediagil.mcp_server import identidad
from crediagil.mcp_server.errores import ErrorCore, TipoError, exito, fallo
from crediagil.mcp_server.estado import AlmacenEstado, ruta_por_defecto
from crediagil.mcp_server.fallas import InyectorFallas

registro = logging.getLogger("crediagil.mcp_server")

DESCRIPCION_BUSCAR = (
    "Busca solicitantes en el core por número de documento o por parte del nombre. Úsala antes "
    "de verificar la identidad. Puede devolver varias coincidencias o ninguna; si hay varias, "
    "pide al solicitante su documento. No devuelve la fecha de nacimiento."
)
DESCRIPCION_VERIFICAR = (
    "Verifica la identidad de un solicitante encontrado con buscar_solicitante, comparando la "
    "fecha de nacimiento que da el solicitante (AAAA-MM-DD). Tras 3 intentos fallidos el "
    "solicitante queda bloqueado: no reintentes; escala a un analista. Ante un error "
    "transitorio, reintenta."
)
INSTRUCCIONES = (
    "Core de originación de Crediágil (simulado, datos ficticios). Toda respuesta es "
    "{ok: true, ...} u {ok: false, error: {tipo, codigo, mensaje, reintentable, detalles}}: "
    "reintenta solo si reintentable es true."
)


def crear_servidor(almacen: AlmacenEstado, inyector: InyectorFallas) -> MCPServer:
    servidor = MCPServer("crediagil-core", instructions=INSTRUCCIONES)

    def _responder(operacion: Callable[[], dict]) -> dict[str, Any]:
        if inyector.debe_fallar():
            return fallo(InyectorFallas.error_inyectado())
        try:
            return exito(**operacion())
        except ErrorCore as error:
            return fallo(error)
        except Exception:  # noqa: BLE001 — FR-004: ningún error interno sale sin contrato
            registro.exception("Error interno en una herramienta del core")
            return fallo(
                ErrorCore(
                    TipoError.TRANSITORIO,
                    "ERROR_INTERNO",
                    "Error interno del core; reintenta o escala si persiste.",
                )
            )

    @servidor.tool(
        name="buscar_solicitante", description=DESCRIPCION_BUSCAR, structured_output=True
    )
    def buscar_solicitante(
        documento: str | None = None, nombre: str | None = None
    ) -> dict[str, Any]:
        return _responder(
            lambda: {
                "coincidencias": identidad.buscar_solicitante(
                    almacen, documento=documento, nombre=nombre
                )
            }
        )

    @servidor.tool(
        name="verificar_identidad", description=DESCRIPCION_VERIFICAR, structured_output=True
    )
    def verificar_identidad(id_solicitante: str, fecha_nacimiento: str) -> dict[str, Any]:
        return _responder(
            lambda: identidad.verificar_identidad(almacen, id_solicitante, fecha_nacimiento)
        )

    return servidor


def main() -> None:
    # stdout es el canal MCP: los logs van solo a stderr.
    logging.basicConfig(stream=sys.stderr, level=logging.INFO)
    try:
        inyector = InyectorFallas.desde_entorno()
    except ValueError as exc:
        print(f"Configuración de fallas inválida: {exc}", file=sys.stderr)
        sys.exit(2)
    almacen = AlmacenEstado(ruta_por_defecto())
    try:
        almacen.leer()  # crea el estado desde la semilla si no existe (FR-014)
    except ErrorCore as error:
        # Estado ilegible: se arranca igual; cada llamada devolverá el error estructurado.
        registro.warning("%s (%s)", error.mensaje, almacen.ruta)
    crear_servidor(almacen, inyector).run()


if __name__ == "__main__":
    main()
