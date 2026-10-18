"""Razón de parada de un turno (spec 007, FR-001, research R2).

El ciclo del agente continúa o termina según la razón de parada que reporta el SDK, no por un
número fijo de iteraciones ni por palabras del texto. `clasificar_parada` es pura: la respuesta
del modelo (`result`) nunca interviene.
"""

from __future__ import annotations

from enum import StrEnum

from claude_agent_sdk import ResultMessage


class Parada(StrEnum):
    FIN_DE_TURNO = "fin_de_turno"
    TRUNCADA = "truncada"
    RECHAZO = "rechazo"
    TOPE = "tope"
    ERROR_API = "error_api"
    DESCONOCIDA = "desconocida"


_FIN = {"end_turn", "stop_sequence"}
_TRUNCADA = {"max_tokens", "model_context_window_exceeded"}


def clasificar_parada(resultado: ResultMessage, error_del_asistente: bool = False) -> Parada:
    """Prioridad: ERROR_API > TOPE > el resto.

    `error_del_asistente` indica que algún `AssistantMessage` del turno trajo un error de la API.
    Una razón final `tool_use` o `pause_turn` (o una desconocida) no se da por terminada: es
    `DESCONOCIDA` y se trata como incidente.
    """
    if resultado.is_error or error_del_asistente:
        return Parada.ERROR_API
    if resultado.terminal_reason == "max_turns":
        return Parada.TOPE
    razon = resultado.stop_reason
    if razon in _FIN:
        return Parada.FIN_DE_TURNO
    if razon in _TRUNCADA:
        return Parada.TRUNCADA
    if razon == "refusal":
        return Parada.RECHAZO
    return Parada.DESCONOCIDA
