"""Prueba con el modelo real a través de la API de la interfaz (spec 008, T032).

Opt-in: `uv run pytest -m live -k chat -s`. Consume saldo de la API: usa un estado temporal, datos
ficticios y un tope de coste. Se salta si no hay `ANTHROPIC_API_KEY`. Las comprobaciones son sobre
el JSON del turno (avisos, traza, parada), nunca sobre las palabras del modelo.
"""

from __future__ import annotations

import base64
import os

import pytest
from starlette.testclient import TestClient

from crediagil.agent.opciones import ConfigAgente
from crediagil.chat.app import crear_app
from crediagil.chat.casos import caso_por_id
from crediagil.config import cargar_entorno

pytestmark = pytest.mark.live

TOPE_USD = 0.75


@pytest.fixture
def config(tmp_path):
    cargar_entorno()
    if not os.environ.get("ANTHROPIC_API_KEY", "").strip():
        pytest.skip("Falta ANTHROPIC_API_KEY: las pruebas con el modelo real no se ejecutan.")
    return ConfigAgente(ruta_estado=tmp_path / "estado.json", max_presupuesto_usd=TOPE_USD)


def _adjuntos_en_base64(caso) -> list[dict]:
    return [
        {
            "nombre": adjunto.nombre,
            "contenido_b64": base64.b64encode(adjunto.texto.encode("utf-8")).decode("ascii"),
        }
        for adjunto in caso.adjuntos
    ]


def test_solicitud_dentro_de_politica_por_la_api(config):
    caso = caso_por_id("dentro_de_politica")
    with TestClient(crear_app(config=config)) as http:
        respuesta = http.post(
            "/api/turnos",
            json={"mensaje": caso.mensaje, "adjuntos": _adjuntos_en_base64(caso)},
        )
        estado = http.get("/api/estado").json()

    assert respuesta.status_code == 200
    turno = respuesta.json()
    print(f"\ncosto_usd={turno['costo_usd']} parada={turno['parada']}")
    print("herramientas:", [e["nombre"] for e in turno["traza"] if not e["de_subagente"]])

    assert turno["error"] is None
    assert turno["parada"] == "fin_de_turno"
    avisos = {a["tipo"]: a for a in turno["avisos"]}
    assert "credito_preaprobado" in avisos, turno["avisos"]
    assert avisos["credito_preaprobado"]["rotulo"] == "Crédito preaprobado"
    llamadas = [e["nombre"] for e in turno["traza"] if not e["de_subagente"]]
    assert "registrar_solicitud" in llamadas and "preaprobar_credito" in llamadas
    assert any(e["tipo"] == "delegacion" for e in turno["traza"])
    assert os.environ["ANTHROPIC_API_KEY"] not in respuesta.text
    assert estado["conversacion"]["turnos"] == 1
