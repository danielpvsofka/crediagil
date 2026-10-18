"""Tests de la traza y los avisos (spec 007, FR-011), con mensajes reales del SDK."""

from __future__ import annotations

import json

from claude_agent_sdk import (
    AssistantMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)

from crediagil.agent.negaciones import Negacion
from crediagil.agent.traza import TrazaTurno, derivar_avisos

CORE = "mcp__crediagil-core__"
CLAVE = "sk-ficticia-traza"


def _uso(id_, nombre, entrada, padre=None, stop="tool_use"):
    return AssistantMessage(
        content=[ToolUseBlock(id=id_, name=nombre, input=entrada)],
        model="m",
        parent_tool_use_id=padre,
        stop_reason=stop,
    )


def _resultado(id_, salida, es_error=False, como_lista=True):
    texto = salida if isinstance(salida, str) else json.dumps(salida)
    contenido = [{"type": "text", "text": texto}] if como_lista else texto
    return UserMessage(
        content=[ToolResultBlock(tool_use_id=id_, content=contenido, is_error=es_error)]
    )


def _texto(texto, padre=None):
    return AssistantMessage(content=[TextBlock(text=texto)], model="m", parent_tool_use_id=padre)


def _traza(*mensajes):
    traza = TrazaTurno()
    for mensaje in mensajes:
        traza.procesar(mensaje)
    return traza


def test_uso_y_resultado_se_correlacionan_por_id():
    traza = _traza(
        _uso("t1", CORE + "buscar_solicitante", {"documento": "x"}),
        _resultado("t1", {"ok": True, "encontrado": True}),
    )
    (evento,) = traza.eventos
    assert evento.tipo == "herramienta"
    assert evento.nombre == "buscar_solicitante"
    assert evento.entrada == {"documento": "x"}
    assert evento.salida == {"ok": True, "encontrado": True}
    assert evento.es_error is False
    assert evento.de_subagente is False
    assert evento.stop_reason == "tool_use"


def test_resultado_de_texto_plano_y_error():
    traza = _traza(
        _uso("t1", CORE + "verificar_identidad", {}),
        _resultado("t1", "falló", es_error=True, como_lista=False),
    )
    assert traza.eventos[0].salida == "falló"
    assert traza.eventos[0].es_error is True


def test_mensajes_de_subagente_quedan_marcados():
    traza = _traza(
        _uso("a", "Agent", {"subagent_type": "extractor-documentos", "prompt": "p"}),
        _uso("b", CORE + "validar_extraccion", {}, padre="a"),
        _resultado("b", {"ok": True}),
        _resultado("a", "listo", como_lista=False),
    )
    delegacion, interna = traza.eventos
    assert delegacion.tipo == "delegacion"
    assert delegacion.nombre == "Agent"
    assert delegacion.de_subagente is False
    assert interna.de_subagente is True


def test_la_respuesta_es_el_texto_tras_la_ultima_herramienta_sin_subagentes():
    traza = _traza(
        _texto("Voy a revisar."),
        _uso("t1", CORE + "buscar_solicitante", {}),
        _resultado("t1", {"ok": True}),
        _texto("texto del subagente", padre="t1"),
        _texto("Tu trámite quedó registrado."),
    )
    assert traza.respuesta == "Tu trámite quedó registrado."


def test_error_del_asistente_se_marca():
    mensaje = AssistantMessage(content=[], model="m", error="rate_limit")
    assert _traza(mensaje).hubo_error_del_asistente is True
    assert _traza(_texto("hola")).hubo_error_del_asistente is False


def test_avisos_solo_de_resultados_de_herramientas():
    traza = _traza(
        _uso("p", CORE + "preaprobar_credito", {"id_solicitud": "SLC-1"}),
        _resultado(
            "p",
            {
                "ok": True,
                "id_solicitud": "SLC-1",
                "monto": 1,
                "plazo_meses": 12,
                "cuota": 2,
                "tasa_mensual": "t",
            },
        ),
        _uso("i", "mcp__canal__solicitar_informacion", {"datos": ["salario"], "motivo": "falta"}),
        _resultado("i", "registrado", como_lista=False),
        _uso("e", CORE + "escalar_a_analista", {"resumen": {"causa": "solicitud_humano"}}),
        _resultado("e", {"ok": True, "id_escalamiento": "ESC-1", "id_solicitud": None}),
    )
    avisos = derivar_avisos(traza.eventos, [])
    assert [a.tipo for a in avisos] == [
        "credito_preaprobado",
        "informacion_solicitada",
        "escalamiento",
    ]
    assert avisos[0].contenido["id_solicitud"] == "SLC-1"
    assert avisos[1].contenido == {"datos": ["salario"], "motivo": "falta"}
    assert avisos[2].contenido == {"id_escalamiento": "ESC-1", "causa": "solicitud_humano"}


def test_preaprobacion_fallida_no_da_aviso():
    traza = _traza(
        _uso("p", CORE + "preaprobar_credito", {}),
        _resultado("p", {"ok": False, "error": {"codigo": "NO_PREAPROBABLE"}}),
        _texto("¡Tu crédito fue preaprobado!"),
    )
    assert derivar_avisos(traza.eventos, []) == []


def test_preaprobacion_sin_resultado_no_da_aviso():
    traza = _traza(_uso("p", CORE + "preaprobar_credito", {}))
    assert derivar_avisos(traza.eventos, []) == []


def test_escalamiento_fallido_no_da_aviso():
    traza = _traza(
        _uso("e", CORE + "escalar_a_analista", {}),
        _resultado("e", {"ok": False, "error": {"codigo": "RESUMEN_INCOMPLETO"}}),
    )
    assert derivar_avisos(traza.eventos, []) == []


def test_negaciones_nuevas_dan_bloqueo_regla():
    negacion = Negacion("preaprobar_credito", "IDENTIDAD_NO_VERIFICADA", "msg", "acc")
    (aviso,) = derivar_avisos([], [negacion])
    assert aviso.tipo == "bloqueo_regla"
    assert aviso.contenido["codigo"] == "IDENTIDAD_NO_VERIFICADA"


def test_los_resultados_del_subagente_no_dan_avisos():
    traza = _traza(
        _uso("p", CORE + "preaprobar_credito", {}, padre="a"),
        _resultado("p", {"ok": True}),
    )
    assert derivar_avisos(traza.eventos, []) == []


def test_entrada_salida_y_respuesta_se_redactan(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", CLAVE)
    traza = _traza(
        _uso("t1", CORE + "buscar_solicitante", {"documento": f"abc {CLAVE}"}),
        _resultado("t1", {"ok": True, "eco": [CLAVE]}),
        _texto(f"la clave es {CLAVE}"),
    )
    volcado = json.dumps([traza.eventos[0].entrada, traza.eventos[0].salida, traza.respuesta])
    assert CLAVE not in volcado
    assert "[REDACTADO]" in volcado
