"""Tests del registro de negaciones: data-model.md §Negacion (FR-009)."""

from __future__ import annotations

import logging

from crediagil.agent.negaciones import Negacion, RegistroNegaciones


def negacion(codigo="IDENTIDAD_NO_VERIFICADA", herramienta="registrar_solicitud") -> Negacion:
    return Negacion(
        herramienta=herramienta,
        codigo=codigo,
        mensaje="El solicitante no tiene la identidad verificada.",
        accion="Verifica la identidad con verificar_identidad.",
        detalles={"id_solicitante": "SOL-0001"},
        momento="2026-10-17T15:30:00+00:00",
    )


def test_registrar_y_listar():
    registro = RegistroNegaciones()
    primera, segunda = negacion(), negacion("SOLICITUD_NO_ENCONTRADA", "preaprobar_credito")
    registro.registrar(primera)
    registro.registrar(segunda)
    assert registro.listar() == [primera, segunda]


def test_listar_devuelve_una_copia():
    registro = RegistroNegaciones()
    registro.registrar(negacion())
    registro.listar().clear()
    assert len(registro.listar()) == 1


def test_ultima():
    registro = RegistroNegaciones()
    assert registro.ultima() is None
    registro.registrar(negacion())
    ultima = negacion("NO_PREAPROBABLE", "preaprobar_credito")
    registro.registrar(ultima)
    assert registro.ultima() is ultima


def test_al_negar_se_llama_una_vez_por_negacion():
    avisos = []
    registro = RegistroNegaciones(al_negar=avisos.append)
    entrada = negacion()
    registro.registrar(entrada)
    assert avisos == [entrada]


def test_error_en_al_negar_no_se_propaga(caplog):
    def falla(_):
        raise RuntimeError("falla de la interfaz")

    registro = RegistroNegaciones(al_negar=falla)
    with caplog.at_level(logging.ERROR, logger="crediagil.agent"):
        registro.registrar(negacion())
    assert len(registro.listar()) == 1
    assert "falla de la interfaz" in caplog.text
