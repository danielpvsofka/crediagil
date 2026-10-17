"""Tests de escalamiento a analista: contracts/tools.md de spec 005 (FR-016–FR-018)."""

from __future__ import annotations

import pytest

from crediagil.mcp_server.errores import ErrorCore, TipoError
from crediagil.mcp_server.escalamiento import CLAVES_RESUMEN, escalar_a_analista
from crediagil.mcp_server.estado import AlmacenEstado


def resumen(**cambios):
    base = {
        "solicitante": "SOL-0001 (Ana Prueba Ficticia)",
        "monto": 5_000_000,
        "plazo": 12,
        "datos": [
            {
                "campo": "salario_mensual",
                "valor": 1_556_699,
                "documento": "cert-1",
                "fragmento": "salario mensual de $1.556.699",
            }
        ],
        "discrepancias": ["La cuota supera la proporción máxima del ingreso verificado."],
        "causa": "regla_2",
        "detalle": "La cuota de 467.010 supera el 30% del ingreso verificado.",
        "accion_recomendada": "Revisar capacidad de pago o proponer un plazo mayor.",
    }
    base.update(cambios)
    return base


def error_de(*args, **kwargs) -> ErrorCore:
    with pytest.raises(ErrorCore) as info:
        escalar_a_analista(*args, **kwargs)
    return info.value


@pytest.fixture
def almacen(tmp_path):
    return AlmacenEstado(tmp_path / "estado.json")


def crear_solicitud(almacen, estado="REGISTRADA"):
    with almacen.transaccion() as datos:
        datos["solicitudes"]["SLC-0001"] = {"id_solicitud": "SLC-0001", "estado": estado}
    return "SLC-0001"


def test_las_ocho_claves():
    assert set(CLAVES_RESUMEN) == {
        "solicitante",
        "monto",
        "plazo",
        "datos",
        "discrepancias",
        "causa",
        "detalle",
        "accion_recomendada",
    }


def test_resumen_completo_sin_solicitud(almacen):
    resultado = escalar_a_analista(almacen, resumen())
    assert resultado == {"id_escalamiento": "ESC-0001", "id_solicitud": None}
    escalamiento = almacen.leer()["escalamientos"]["ESC-0001"]
    assert escalamiento["resumen"]["causa"] == "regla_2"
    assert escalamiento["creado_en"]


def test_solicitud_de_humano_con_campos_vacios(almacen):
    vacio = resumen(causa="solicitud_humano", monto=None, plazo=None, datos=[], discrepancias=[])
    assert escalar_a_analista(almacen, vacio)["id_escalamiento"] == "ESC-0001"


@pytest.mark.parametrize("clave", sorted(CLAVES_RESUMEN))
def test_falta_una_clave(almacen, clave):
    incompleto = resumen()
    del incompleto[clave]
    error = error_de(almacen, incompleto)
    assert (error.tipo, error.codigo) == (TipoError.VALIDACION, "RESUMEN_INCOMPLETO")
    assert error.reintentable is False
    assert clave in error.detalles["campos_faltantes"]
    assert almacen.leer()["escalamientos"] == {}


@pytest.mark.parametrize(
    ("cambio", "campo"),
    [
        ({"solicitante": ""}, "solicitante"),
        ({"detalle": "   "}, "detalle"),
        ({"accion_recomendada": ""}, "accion_recomendada"),
        ({"causa": "otra_cosa"}, "causa"),
        ({"monto": 0}, "monto"),
        ({"datos": [{"campo": "salario_mensual", "valor": 1, "documento": "cert-1"}]}, "datos"),
        (
            {"datos": [{"campo": "x", "valor": 1, "documento": "", "fragmento": "f"}]},
            "datos",
        ),
        ({"extra": "no permitido"}, "extra"),
        (
            {"datos": [{"campo": "x", "valor": None, "documento": "d", "fragmento": "f"}]},
            "datos",
        ),
        ({"discrepancias": [""]}, "discrepancias"),
        ({"plazo": 0}, "plazo"),
        ({"plazo": -12}, "plazo"),
        ({"monto": "5000000"}, "monto"),
    ],
)
def test_resumen_invalido(almacen, cambio, campo):
    error = error_de(almacen, resumen(**cambio))
    assert error.codigo == "RESUMEN_INCOMPLETO"
    assert campo in error.detalles["campos_faltantes"]


def test_resumen_no_es_objeto(almacen):
    assert error_de(almacen, "texto").codigo == "RESUMEN_INCOMPLETO"


def test_con_solicitud_la_escala(almacen):
    id_solicitud = crear_solicitud(almacen)
    resultado = escalar_a_analista(almacen, resumen(), id_solicitud)
    assert resultado == {"id_escalamiento": "ESC-0001", "id_solicitud": id_solicitud}
    solicitud = almacen.leer()["solicitudes"][id_solicitud]
    assert solicitud["estado"] == "ESCALADA"
    assert solicitud["escalada_en"]


def test_solicitud_preaprobada(almacen):
    id_solicitud = crear_solicitud(almacen, "PREAPROBADA")
    error = error_de(almacen, resumen(), id_solicitud)
    assert (error.tipo, error.codigo) == (TipoError.NEGOCIO, "SOLICITUD_PREAPROBADA")
    assert almacen.leer()["escalamientos"] == {}


def test_solicitud_inexistente(almacen):
    assert error_de(almacen, resumen(), "SLC-9999").codigo == "SOLICITUD_NO_ENCONTRADA"
