"""Tests del catálogo de casos de prueba (spec 008, data-model.md "CasoPrueba", research R8)."""

from __future__ import annotations

import re
from decimal import Decimal

import pytest

from crediagil.chat.casos import CASOS, caso_por_id, casos_publicos
from crediagil.policy import params

ESPERADOS = {
    "dentro_de_politica",
    "pedir_persona",
    "dato_ausente",
    "mensaje_mixto",
    "preaprobar_sin_identidad",
    "falla_transitoria",
}


def _textos(caso) -> list[str]:
    return [caso.mensaje, caso.nombre, caso.descripcion, *(a.texto for a in caso.adjuntos)]


def test_estan_los_casos_esperados_con_ids_unicos_en_snake_case():
    ids = [c.id for c in CASOS]
    assert ESPERADOS <= set(ids)
    assert len(ids) == len(set(ids))
    assert all(re.fullmatch(r"[a-z][a-z0-9_]*", i) for i in ids)


@pytest.mark.parametrize("caso", CASOS, ids=lambda c: c.id)
def test_cada_caso_esta_completo_y_es_ficticio(caso):
    assert caso.nombre.strip() and caso.descripcion.strip() and caso.mensaje.strip()
    for adjunto in caso.adjuntos:
        assert adjunto.nombre.lower().endswith((".txt", ".md"))
        assert adjunto.texto.strip()
    for texto in _textos(caso):
        # Todo identificador largo con forma de documento es ficticio y lleva el prefijo TEST-.
        assert not re.findall(r"(?<!TEST-)\b\d{6,}\b", texto), texto


def _formatos_pesos(monto: int) -> list[str]:
    return [f"{monto:,}".replace(",", "."), f"{monto:,}", str(monto)]


def _formatos_porcentaje(proporcion: Decimal) -> list[str]:
    numero = f"{(proporcion * 100).normalize():f}"
    variantes = {numero, numero.replace(".", ",")}
    return [f"{v}{sep}%" for v in variantes for sep in ("", " ")]


@pytest.mark.parametrize("caso", CASOS, ids=lambda c: c.id)
def test_ningun_caso_repite_la_tasa_ni_los_umbrales(caso):
    prohibidos = [
        *_formatos_pesos(params.MONTO_MAXIMO_PREAPROBACION),
        *_formatos_porcentaje(params.TASA_MENSUAL),
        *_formatos_porcentaje(params.PROPORCION_MAXIMA_CUOTA_INGRESO),
        *_formatos_porcentaje(params.DISCREPANCIA_MAXIMA_INGRESO),
    ]
    for texto in _textos(caso):
        for valor in prohibidos:
            assert valor not in texto, f"{caso.id} contiene {valor!r}"


def test_la_falla_sugerida_solo_esta_en_el_caso_de_falla_transitoria():
    for caso in CASOS:
        esperada = 1 if caso.id == "falla_transitoria" else 0
        assert caso.falla_sugerida == esperada, caso.id


def test_el_caso_de_dato_ausente_tiene_un_certificado_sin_salario():
    caso = caso_por_id("dato_ausente")
    assert caso.adjuntos
    texto = caso.adjuntos[0].texto.lower()
    assert "salario" not in texto and "$" not in texto


def test_el_caso_mixto_pide_simular_un_monto_distinto_del_solicitado():
    caso = caso_por_id("mensaje_mixto")
    assert "3.000.000" in caso.mensaje
    assert "10.000.000" in caso.mensaje
    assert caso.adjuntos


def test_el_caso_de_pedir_una_persona_no_trae_adjuntos():
    caso = caso_por_id("pedir_persona")
    assert caso.adjuntos == ()
    assert "persona" in caso.mensaje.lower()


def test_caso_por_id_desconocido_da_none():
    assert caso_por_id("no_existe") is None


def test_los_casos_publicos_tienen_la_forma_de_la_api():
    publicos = casos_publicos()
    assert [c["id"] for c in publicos] == [c.id for c in CASOS]
    for publico, caso in zip(publicos, CASOS, strict=True):
        assert set(publico) == {
            "id",
            "nombre",
            "descripcion",
            "mensaje",
            "adjuntos",
            "falla_sugerida",
        }
        assert publico["adjuntos"] == [
            {"nombre": a.nombre, "texto": a.texto} for a in caso.adjuntos
        ]
