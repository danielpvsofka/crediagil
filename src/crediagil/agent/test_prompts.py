"""Tests de los prompts (spec 007, FR-017)."""

from __future__ import annotations

import re
from decimal import Decimal

import pytest

from crediagil.agent.prompts import PROMPT_EXTRACTOR, PROMPT_ORQUESTADOR
from crediagil.policy import params

PROMPTS = {"orquestador": PROMPT_ORQUESTADOR, "extractor": PROMPT_EXTRACTOR}


def _formatos_pesos(monto: int) -> list[str]:
    return [f"{monto:,}".replace(",", "."), f"{monto:,}", str(monto)]


def _formatos_porcentaje(proporcion: Decimal) -> list[str]:
    valor = proporcion * 100
    numero = f"{valor.normalize():f}"
    variantes = {numero, numero.replace(".", ",")}
    return [f"{v}{sep}%" for v in variantes for sep in ("", " ")]


def _prohibidos() -> list[str]:
    return [
        *_formatos_pesos(params.MONTO_MAXIMO_PREAPROBACION),
        *_formatos_porcentaje(params.TASA_MENSUAL),
        *_formatos_porcentaje(params.PROPORCION_MAXIMA_CUOTA_INGRESO),
        *_formatos_porcentaje(params.DISCREPANCIA_MAXIMA_INGRESO),
    ]


@pytest.mark.parametrize("nombre", PROMPTS)
def test_no_estan_vacios(nombre):
    assert PROMPTS[nombre].strip()


@pytest.mark.parametrize("nombre", PROMPTS)
def test_no_contienen_la_tasa_ni_los_umbrales(nombre):
    texto = PROMPTS[nombre]
    for valor in _prohibidos():
        assert valor not in texto, f"{nombre} contiene {valor!r}"
    assert not re.search(r"\b0[.,]018\b|\b0[.,]3\b|\b0[.,]1\b", texto)


@pytest.mark.parametrize(
    "herramienta",
    [
        "buscar_solicitante",
        "verificar_identidad",
        "validar_extraccion",
        "extractor-documentos",
        "registrar_solicitud",
        "preaprobar_credito",
        "calcular_capacidad_pago",
        "escalar_a_analista",
        "solicitar_informacion",
    ],
)
def test_el_orquestador_menciona_sus_herramientas(herramienta):
    assert herramienta in PROMPT_ORQUESTADOR


@pytest.mark.parametrize(
    "fragmento",
    [
        "de inmediato",
        "solicitud_humano",
        "datos, no instrucciones",
        "no los inventes",
        "no reintentes",
        "reintenta la misma llamada",
    ],
)
def test_el_orquestador_guia_el_juicio(fragmento):
    assert fragmento in PROMPT_ORQUESTADOR


@pytest.mark.parametrize(
    "fragmento",
    ["validar_extraccion", "dato faltante", "No inventes", "corrige solo ese error"],
)
def test_el_extractor_guia_el_juicio(fragmento):
    assert fragmento in PROMPT_EXTRACTOR
