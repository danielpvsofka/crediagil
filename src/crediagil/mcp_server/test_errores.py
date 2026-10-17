"""Tests del contrato de respuesta: data-model.md §Respuesta (FR-001–FR-003)."""

from __future__ import annotations

import pytest

from crediagil.mcp_server.errores import ErrorCore, TipoError, exito, fallo

CLAVES_ERROR = {"tipo", "codigo", "mensaje", "reintentable", "detalles"}


def test_tipos_de_error():
    assert {t.value for t in TipoError} == {"transitorio", "validacion", "negocio", "permisos"}


@pytest.mark.parametrize(
    ("tipo", "reintentable"),
    [
        (TipoError.TRANSITORIO, True),
        (TipoError.VALIDACION, False),
        (TipoError.NEGOCIO, False),
        (TipoError.PERMISOS, False),
    ],
)
def test_solo_transitorio_es_reintentable(tipo, reintentable):
    assert ErrorCore(tipo, "CODIGO", "mensaje").reintentable is reintentable


def test_exito():
    assert exito(coincidencias=[]) == {"ok": True, "coincidencias": []}


def test_fallo_tiene_exactamente_las_cinco_claves():
    respuesta = fallo(ErrorCore(TipoError.NEGOCIO, "IDENTIDAD_NO_COINCIDE", "No coincide."))
    assert respuesta["ok"] is False
    assert set(respuesta["error"]) == CLAVES_ERROR
    assert respuesta["error"]["tipo"] == "negocio"
    assert type(respuesta["error"]["tipo"]) is str
    assert respuesta["error"]["detalles"] == {}
    assert respuesta["error"]["reintentable"] is False


def test_fallo_conserva_detalles():
    error = ErrorCore(TipoError.NEGOCIO, "X", "m", {"intentos_restantes": 2})
    assert fallo(error)["error"]["detalles"] == {"intentos_restantes": 2}


@pytest.mark.parametrize("codigo", ["EXTRACCION_INVALIDA", "FRAGMENTO_NO_LITERAL"])
def test_validacion_reintentable_solo_en_codigos_de_extraccion(codigo):
    error = ErrorCore(TipoError.VALIDACION, codigo, "m", reintentable=True)
    assert error.reintentable is True
    assert fallo(error)["error"]["reintentable"] is True


@pytest.mark.parametrize(
    ("tipo", "codigo"),
    [
        (TipoError.VALIDACION, "PARAMETROS_INVALIDOS"),
        (TipoError.NEGOCIO, "EXTRACCION_INVALIDA"),
        (TipoError.PERMISOS, "IDENTIDAD_NO_VERIFICADA"),
    ],
)
def test_reintentable_no_permitido(tipo, codigo):
    with pytest.raises(ValueError, match="reintentable"):
        ErrorCore(tipo, codigo, "m", reintentable=True)


def test_transitorio_siempre_reintentable():
    with pytest.raises(ValueError, match="reintentable"):
        ErrorCore(TipoError.TRANSITORIO, "X", "m", reintentable=False)
    assert ErrorCore(TipoError.TRANSITORIO, "X", "m").reintentable is True
