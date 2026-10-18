"""Herramienta de canal `solicitar_informacion` (spec 007, FR-006).

Registra lo que se le pide al solicitante sin tocar el core: pedir un dato no es un cambio de
estado del trámite.
"""

from __future__ import annotations

from dataclasses import dataclass

from claude_agent_sdk import SdkMcpTool, create_sdk_mcp_server, tool
from claude_agent_sdk.types import McpSdkServerConfig

SERVIDOR_CANAL = "canal"
HERRAMIENTA_CANAL = "solicitar_informacion"


@dataclass(frozen=True)
class PedidoInformacion:
    datos: tuple[str, ...]
    motivo: str


def _error(mensaje: str) -> dict:
    return {"content": [{"type": "text", "text": mensaje}], "is_error": True}


def crear_solicitar_informacion(colector: list[PedidoInformacion]) -> SdkMcpTool:
    @tool(
        HERRAMIENTA_CANAL,
        "Pide al solicitante datos que faltan o que no se pudieron extraer de sus documentos.",
        {"datos": list[str], "motivo": str},
    )
    async def solicitar_informacion(args: dict) -> dict:
        datos = args.get("datos") if isinstance(args, dict) else None
        motivo = args.get("motivo") if isinstance(args, dict) else None
        if not isinstance(datos, list) or not datos:
            return _error("Indica al menos un dato que pedir en `datos`.")
        if not all(isinstance(d, str) and d.strip() for d in datos):
            return _error("Cada dato pedido debe ser un texto no vacío.")
        if not isinstance(motivo, str) or not motivo.strip():
            return _error("Indica el `motivo` de la solicitud de información.")
        pedido = PedidoInformacion(tuple(d.strip() for d in datos), motivo.strip())
        colector.append(pedido)
        return {
            "content": [
                {
                    "type": "text",
                    "text": "Solicitud de información registrada: " + ", ".join(pedido.datos),
                }
            ]
        }

    return solicitar_informacion


def crear_canal() -> tuple[McpSdkServerConfig, list[PedidoInformacion]]:
    """Servidor MCP en proceso y el colector donde quedan los pedidos."""
    colector: list[PedidoInformacion] = []
    servidor = create_sdk_mcp_server(SERVIDOR_CANAL, tools=[crear_solicitar_informacion(colector)])
    return servidor, colector
