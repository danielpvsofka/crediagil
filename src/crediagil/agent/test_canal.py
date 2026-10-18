"""Tests de `solicitar_informacion` (spec 007, contracts/agente.md)."""

from __future__ import annotations

import pytest

from crediagil.agent.canal import crear_canal, crear_solicitar_informacion

pytestmark = pytest.mark.anyio


async def test_registra_el_pedido():
    colector = []
    herramienta = crear_solicitar_informacion(colector)
    resultado = await herramienta.handler(
        {"datos": ["salario mensual"], "motivo": "El certificado no lo indica"}
    )
    assert not resultado.get("is_error")
    assert len(colector) == 1
    assert colector[0].datos == ("salario mensual",)
    assert colector[0].motivo == "El certificado no lo indica"
    assert "salario mensual" in resultado["content"][0]["text"]


@pytest.mark.parametrize(
    "entrada",
    [
        {"datos": [], "motivo": "x"},
        {"datos": ["  "], "motivo": "x"},
        {"datos": [3], "motivo": "x"},
        {"datos": ["salario"], "motivo": ""},
        {"datos": ["salario"], "motivo": "   "},
        {"datos": ["salario"]},
        {"motivo": "x"},
        {},
    ],
)
async def test_entradas_invalidas_dan_error_y_no_dejan_nada(entrada):
    colector = []
    resultado = await crear_solicitar_informacion(colector).handler(entrada)
    assert resultado["is_error"] is True
    assert colector == []


def test_crear_canal_devuelve_servidor_en_proceso_y_colector():
    servidor, colector = crear_canal()
    assert servidor["type"] == "sdk"
    assert servidor["name"] == "canal"
    assert colector == []
