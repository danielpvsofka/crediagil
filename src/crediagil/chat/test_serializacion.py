"""Tests de la serialización del resultado del turno (spec 008, research R7)."""

from __future__ import annotations

import json

import pytest

from crediagil.agent.canal import PedidoInformacion
from crediagil.agent.negaciones import Negacion
from crediagil.agent.parada import Parada
from crediagil.agent.traza import Aviso, EventoTraza, ResultadoTurno
from crediagil.chat.serializacion import ROTULOS_AVISO, turno_a_dict

CLAVE = "sk-ficticia-serializacion"


def _resultado(**cambios) -> ResultadoTurno:
    base = {
        "respuesta": "Hola",
        "avisos": [],
        "traza": [],
        "parada": Parada.FIN_DE_TURNO,
        "razon_parada": "end_turn",
        "costo_usd": 0.01,
    }
    return ResultadoTurno(**{**base, **cambios})


def test_claves_exactas():
    datos = turno_a_dict(_resultado(), 3)
    assert set(datos) == {
        "id_turno",
        "respuesta",
        "error",
        "parada",
        "razon_parada",
        "costo_usd",
        "avisos",
        "traza",
        "negaciones",
        "pedidos_informacion",
    }
    assert datos["id_turno"] == 3
    assert datos["parada"] == "fin_de_turno"
    assert datos["razon_parada"] == "end_turn"
    assert datos["costo_usd"] == 0.01
    assert datos["error"] is None


def test_rotulos_exactos():
    assert ROTULOS_AVISO == {
        "credito_preaprobado": "Crédito preaprobado",
        "informacion_solicitada": "Información solicitada",
        "escalamiento": "Escalado a un analista",
        "bloqueo_regla": "Bloqueado por una regla de negocio",
    }


def test_avisos_llevan_tipo_rotulo_y_contenido():
    avisos = [
        Aviso("credito_preaprobado", {"monto": 1, "cuota": 2}),
        Aviso("escalamiento", {"id_escalamiento": "ESC-0001", "causa": "otro"}),
    ]
    datos = turno_a_dict(_resultado(avisos=avisos), 1)
    assert datos["avisos"] == [
        {
            "tipo": "credito_preaprobado",
            "rotulo": "Crédito preaprobado",
            "contenido": {"monto": 1, "cuota": 2},
        },
        {
            "tipo": "escalamiento",
            "rotulo": "Escalado a un analista",
            "contenido": {"id_escalamiento": "ESC-0001", "causa": "otro"},
        },
    ]


def test_tipo_desconocido_usa_el_tipo_como_rotulo():
    datos = turno_a_dict(_resultado(avisos=[Aviso("nuevo_tipo", {})]), 1)
    assert datos["avisos"][0]["rotulo"] == "nuevo_tipo"


def test_sin_avisos_no_se_inventa_ninguno():
    assert turno_a_dict(_resultado(), 1)["avisos"] == []


def test_la_traza_conserva_orden_y_marcas():
    traza = [
        EventoTraza(
            "herramienta", "buscar_solicitante", {"a": 1}, {"ok": True}, stop_reason="tool_use"
        ),
        EventoTraza("delegacion", "Agent", {"p": "x"}, "listo"),
        EventoTraza("herramienta", "validar_extraccion", {}, {"ok": False}, True, True),
    ]
    datos = turno_a_dict(_resultado(traza=traza), 1)["traza"]
    assert [e["nombre"] for e in datos] == ["buscar_solicitante", "Agent", "validar_extraccion"]
    assert datos[0] == {
        "tipo": "herramienta",
        "nombre": "buscar_solicitante",
        "entrada": {"a": 1},
        "salida": {"ok": True},
        "es_error": False,
        "de_subagente": False,
        "stop_reason": "tool_use",
    }
    assert datos[1]["tipo"] == "delegacion"
    assert datos[2]["es_error"] is True and datos[2]["de_subagente"] is True


def test_negaciones_y_pedidos():
    negacion = Negacion("preaprobar_credito", "IDENTIDAD_NO_VERIFICADA", "msg", "acc", {"x": 1})
    pedido = PedidoInformacion(("salario",), "falta")
    datos = turno_a_dict(_resultado(negaciones=[negacion], pedidos_informacion=[pedido]), 1)
    assert datos["negaciones"] == [
        {
            "herramienta": "preaprobar_credito",
            "codigo": "IDENTIDAD_NO_VERIFICADA",
            "mensaje": "msg",
            "accion": "acc",
        }
    ]
    assert datos["pedidos_informacion"] == [{"datos": ["salario"], "motivo": "falta"}]


def test_la_clave_no_sale_en_ningun_campo(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", CLAVE)
    traza = [EventoTraza("herramienta", "x", {"k": f"a {CLAVE}"}, {"eco": [CLAVE]})]
    resultado = _resultado(respuesta=f"clave {CLAVE}", error=f"fallo {CLAVE}", traza=traza)
    volcado = json.dumps(turno_a_dict(resultado, 1))
    assert CLAVE not in volcado
    assert "[REDACTADO]" in volcado


@pytest.mark.parametrize("parada", list(Parada))
def test_todas_las_paradas_son_serializables(parada):
    datos = turno_a_dict(_resultado(parada=parada), 1)
    json.dumps(datos)
    assert datos["parada"] == parada.value
