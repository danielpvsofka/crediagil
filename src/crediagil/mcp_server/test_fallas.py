"""Tests de la inyección de fallas transitorias: research.md R4 (FR-015)."""

from __future__ import annotations

import pytest

from crediagil.mcp_server.errores import TipoError
from crediagil.mcp_server.fallas import InyectorFallas

VARIABLES = ("CREDIAGIL_MCP_FALLAS_N", "CREDIAGIL_MCP_FALLAS_PROB", "CREDIAGIL_MCP_FALLAS_SEMILLA")


@pytest.fixture(autouse=True)
def entorno_limpio(monkeypatch):
    for variable in VARIABLES:
        monkeypatch.delenv(variable, raising=False)


def secuencia(inyector, n=20):
    return [inyector.debe_fallar() for _ in range(n)]


def test_desactivado_por_defecto():
    assert not any(secuencia(InyectorFallas.desde_entorno()))


def test_fallar_las_proximas_n(monkeypatch):
    monkeypatch.setenv("CREDIAGIL_MCP_FALLAS_N", "2")
    assert secuencia(InyectorFallas.desde_entorno(), 4) == [True, True, False, False]


@pytest.mark.parametrize(("probabilidad", "esperado"), [("1", True), ("0", False)])
def test_probabilidad_extremos(monkeypatch, probabilidad, esperado):
    monkeypatch.setenv("CREDIAGIL_MCP_FALLAS_PROB", probabilidad)
    assert set(secuencia(InyectorFallas.desde_entorno())) == {esperado}


def test_probabilidad_con_semilla_es_reproducible(monkeypatch):
    monkeypatch.setenv("CREDIAGIL_MCP_FALLAS_PROB", "0.5")
    monkeypatch.setenv("CREDIAGIL_MCP_FALLAS_SEMILLA", "7")
    primera = secuencia(InyectorFallas.desde_entorno(), 50)
    assert primera == secuencia(InyectorFallas.desde_entorno(), 50)
    assert True in primera and False in primera


@pytest.mark.parametrize(
    ("variable", "valor"),
    [
        ("CREDIAGIL_MCP_FALLAS_N", "-1"),
        ("CREDIAGIL_MCP_FALLAS_N", "abc"),
        ("CREDIAGIL_MCP_FALLAS_PROB", "2"),
        ("CREDIAGIL_MCP_FALLAS_PROB", "x"),
        ("CREDIAGIL_MCP_FALLAS_SEMILLA", "x"),
    ],
)
def test_valores_invalidos(monkeypatch, variable, valor):
    monkeypatch.setenv(variable, valor)
    with pytest.raises(ValueError, match=variable):
        InyectorFallas.desde_entorno()


def test_error_inyectado_es_transitorio_reintentable():
    error = InyectorFallas.error_inyectado()
    assert error.tipo is TipoError.TRANSITORIO
    assert error.codigo == "SERVICIO_NO_DISPONIBLE"
    assert error.reintentable is True
