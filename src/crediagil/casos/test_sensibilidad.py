"""Los tests de los casos detectan una regla rota (spec 009, SC-004).

Cada prueba altera una regla con `monkeypatch` y comprueba que el resolutor del caso que la ejerce
falla. Sin esto, un caso podría seguir en verde aunque la regla ya no se cumpliera.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from crediagil.casos import catalogo, resolutores
from crediagil.extraction import income
from crediagil.mcp_server import originacion
from crediagil.mcp_server.errores import ErrorCore, TipoError
from crediagil.mcp_server.fallas import InyectorFallas
from crediagil.policy import reglas

FALLOS = (AssertionError, ErrorCore)


def _sin_limite_de_monto(monkeypatch):
    monkeypatch.setattr(reglas, "MONTO_MAXIMO_PREAPROBACION", 10**12)


def _sin_discrepancia(monkeypatch):
    monkeypatch.setattr(reglas, "DISCREPANCIA_MAXIMA_INGRESO", Decimal(100))


def _cuota_siempre_excesiva(monkeypatch):
    monkeypatch.setattr(reglas, "PROPORCION_MAXIMA_CUOTA_INGRESO", Decimal(0))


def _identidad_siempre_vigente(monkeypatch):
    monkeypatch.setattr("crediagil.agent.hooks.identidad_vigente", lambda _s: True)


def _core_sin_identidad(monkeypatch):
    monkeypatch.setattr(originacion, "identidad_vigente", lambda _s: True)
    monkeypatch.setattr("crediagil.agent.hooks.identidad_vigente", lambda _s: True)


def _moneda_extranjera_aceptada(monkeypatch):
    monkeypatch.setattr(income, "MONEDA", "USD")


def _ingreso_inventado(monkeypatch):
    def inventa(certificados, hallazgos):
        return income.IngresoVerificado(valor=1_000_000, moneda="COP", origen=None)

    monkeypatch.setattr(income, "_ingreso_de_certificados", inventa)


def _sin_fallas(monkeypatch):
    monkeypatch.setattr(InyectorFallas, "debe_fallar", lambda self: False)


def _escalar_exige_identidad(monkeypatch):
    def exige(*_args, **_kwargs):
        raise ErrorCore(TipoError.PERMISOS, "IDENTIDAD_NO_VERIFICADA", "exige identidad")

    monkeypatch.setattr(resolutores, "escalar_a_analista", exige)


ALTERACIONES = [
    pytest.param("monto_sobre_umbral", _sin_limite_de_monto, id="regla_2_monto"),
    pytest.param("ingreso_discrepante", _sin_discrepancia, id="regla_3_discrepancia"),
    pytest.param("dentro_de_politica", _cuota_siempre_excesiva, id="regla_2_cuota"),
    pytest.param("preaprobar_sin_identidad", _identidad_siempre_vigente, id="regla_1_hook"),
    pytest.param("preaprobar_sin_identidad", _core_sin_identidad, id="regla_1_core_y_hook"),
    pytest.param("moneda_extranjera", _moneda_extranjera_aceptada, id="regla_5_moneda"),
    pytest.param("dato_ausente", _ingreso_inventado, id="no_inventar_datos"),
    pytest.param("falla_transitoria", _sin_fallas, id="falla_transitoria_inexistente"),
    pytest.param("pedir_persona", _escalar_exige_identidad, id="regla_4_sin_condiciones"),
]


@pytest.mark.parametrize(("id_caso", "alterar"), ALTERACIONES)
@pytest.mark.anyio
async def test_romper_la_regla_hace_fallar_el_caso(id_caso, alterar, almacen, monkeypatch):
    caso = catalogo().por_id(id_caso)
    # Sin alterar nada el caso pasa (si no, la prueba no distinguiría nada).
    await resolutores.resolver(caso, almacen)

    alterar(monkeypatch)
    with pytest.raises(FALLOS):
        await resolutores.resolver(caso, _almacen_nuevo(almacen))


def _almacen_nuevo(almacen):
    """Otro estado limpio junto al primero: el caso se vuelve a resolver desde cero."""
    from crediagil.mcp_server.estado import AlmacenEstado

    nuevo = AlmacenEstado(almacen.ruta.with_name("alterado.json"))
    nuevo.leer()
    return nuevo
