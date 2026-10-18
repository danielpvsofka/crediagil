"""Tests de `clasificar_parada`: una fila por cada fila de la tabla de contracts/agente.md."""

from __future__ import annotations

import pytest
from claude_agent_sdk import ResultMessage

from crediagil.agent.parada import Parada, clasificar_parada


def _resultado(stop_reason=None, terminal_reason=None, is_error=False, result="texto"):
    return ResultMessage(
        subtype="success",
        duration_ms=1,
        duration_api_ms=1,
        is_error=is_error,
        num_turns=1,
        session_id="s",
        stop_reason=stop_reason,
        terminal_reason=terminal_reason,
        result=result,
    )


@pytest.mark.parametrize(
    ("stop_reason", "terminal_reason", "is_error", "esperada"),
    [
        ("end_turn", "completed", False, Parada.FIN_DE_TURNO),
        ("stop_sequence", "completed", False, Parada.FIN_DE_TURNO),
        ("end_turn", None, False, Parada.FIN_DE_TURNO),
        ("max_tokens", None, False, Parada.TRUNCADA),
        ("model_context_window_exceeded", None, False, Parada.TRUNCADA),
        ("refusal", None, False, Parada.RECHAZO),
        ("end_turn", "max_turns", False, Parada.TOPE),
        ("tool_use", "max_turns", False, Parada.TOPE),
        (None, "max_turns", False, Parada.TOPE),
        ("end_turn", "completed", True, Parada.ERROR_API),
        (None, None, True, Parada.ERROR_API),
        ("tool_use", None, True, Parada.ERROR_API),
        ("tool_use", None, False, Parada.DESCONOCIDA),
        ("pause_turn", None, False, Parada.DESCONOCIDA),
        (None, None, False, Parada.DESCONOCIDA),
        ("razon_nueva", None, False, Parada.DESCONOCIDA),
    ],
)
def test_tabla_de_clasificacion(stop_reason, terminal_reason, is_error, esperada):
    resultado = _resultado(stop_reason, terminal_reason, is_error)
    assert clasificar_parada(resultado) is esperada


def test_error_prima_sobre_tope():
    resultado = _resultado("end_turn", "max_turns", is_error=True)
    assert clasificar_parada(resultado) is Parada.ERROR_API


def test_error_del_asistente_es_error_de_api():
    resultado = _resultado("end_turn", "completed")
    assert clasificar_parada(resultado, error_del_asistente=True) is Parada.ERROR_API


@pytest.mark.parametrize("texto", ["listo", "error", "", None, "Quiero hablar con una persona"])
def test_el_texto_de_la_respuesta_no_interviene(texto):
    assert clasificar_parada(_resultado("refusal", result=texto)) is Parada.RECHAZO
    assert clasificar_parada(_resultado("end_turn", result=texto)) is Parada.FIN_DE_TURNO
