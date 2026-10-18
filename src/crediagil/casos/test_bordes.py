"""Bordes de las reglas que ejercen los casos (spec 009, FR-009, research R5; Principio VII).

Cada test parte de la solicitud y el certificado del caso 1 y varía una sola cosa. Los umbrales
salen de `crediagil.policy.params` y la cuota de `calcular_cuota`: ningún valor se copia aquí, así
que una enmienda de la constitución se refleja en un solo lugar.
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from crediagil.agent.hooks import crear_hook_preaprobacion
from crediagil.casos import catalogo
from crediagil.casos.resolutores import (
    HOY,
    causas,
    error_de,
    invocar,
    resolver_bloquear,
    resolver_escalar_humano,
    resolver_escalar_por_regla,
    verificar,
)
from crediagil.mcp_server.errores import ErrorCore
from crediagil.mcp_server.identidad import verificar_identidad
from crediagil.mcp_server.originacion import preaprobar_credito, registrar_solicitud
from crediagil.policy.cuota import calcular_cuota
from crediagil.policy.params import (
    DISCREPANCIA_MAXIMA_INGRESO,
    MONTO_MAXIMO_PREAPROBACION,
    PROPORCION_MAXIMA_CUOTA_INGRESO,
)

BASE = catalogo().por_id("dentro_de_politica")
SALARIO_BASE = BASE.solicitud.ingreso_declarado  # el ingreso certificado del caso 1
PLAZO_BASE = BASE.solicitud.plazo_meses


def _pesos(valor: int) -> str:
    return f"{valor:,}".replace(",", ".")


def certificado_con_salario(salario: int) -> dict:
    """El certificado del caso 1 con otro salario (texto y extracción coherentes)."""
    (documento,) = BASE.documentos
    viejo, nuevo = f"${_pesos(SALARIO_BASE)}", f"${_pesos(salario)}"
    texto = documento.texto.replace(viejo, nuevo)
    datos = json.loads(json.dumps(documento.extraccion).replace(viejo, nuevo))
    datos["salario_mensual"]["valor"] = salario
    return {"id_documento": "certificado_laboral", "datos": datos, "texto": texto}


def evaluar(almacen, monto=None, plazo=PLAZO_BASE, salario=SALARIO_BASE, declarado=None) -> dict:
    """Registra una solicitud con la identidad de Ana verificada y devuelve su evaluación."""
    verificar(almacen, BASE)
    registrada = registrar_solicitud(
        almacen,
        BASE.solicitud.id_solicitante,
        BASE.solicitud.monto if monto is None else monto,
        plazo,
        salario if declarado is None else declarado,
        [certificado_con_salario(salario)],
    )
    return registrada["evaluacion"]


def ingreso_holgado(monto: int, plazo: int) -> int:
    """Un ingreso al que cualquier cuota de `monto` le queda muy por debajo de la proporción."""
    return calcular_cuota(monto, plazo) * 10


# ---------------------------------------------------------------- la base es preaprobable


def test_la_solicitud_base_es_preaprobable(almacen):
    evaluacion = evaluar(almacen)
    assert evaluacion["preaprobable_automaticamente"] is True


# ---------------------------------------------------------------- regla 2: monto


class TestBordeDelMonto:
    @pytest.fixture
    def holgado(self):
        return ingreso_holgado(MONTO_MAXIMO_PREAPROBACION + 1, PLAZO_BASE)

    def test_un_peso_por_debajo_del_tope_se_preaprueba(self, almacen, holgado):
        evaluacion = evaluar(almacen, MONTO_MAXIMO_PREAPROBACION - 1, salario=holgado)
        assert evaluacion["preaprobable_automaticamente"] is True, evaluacion

    def test_exactamente_en_el_tope_se_preaprueba(self, almacen, holgado):
        evaluacion = evaluar(almacen, MONTO_MAXIMO_PREAPROBACION, salario=holgado)
        assert evaluacion["preaprobable_automaticamente"] is True, evaluacion

    def test_un_peso_por_encima_del_tope_va_a_analista_solo_por_el_monto(self, almacen, holgado):
        evaluacion = evaluar(almacen, MONTO_MAXIMO_PREAPROBACION + 1, salario=holgado)
        assert evaluacion["preaprobable_automaticamente"] is False
        assert causas(evaluacion) == ["regla_2"]
        (causa,) = evaluacion["causas_escalamiento"]
        assert causa["valores"]["monto"] == MONTO_MAXIMO_PREAPROBACION + 1
        assert causa["valores"]["maximo"] == MONTO_MAXIMO_PREAPROBACION


# ---------------------------------------------------------------- regla 2: cuota sobre el ingreso


def _monto_con_cuota_divisible(plazo: int) -> tuple[int, int]:
    """(monto, cuota) con una cuota cuya proporción máxima da un ingreso entero exacto."""
    proporcion = PROPORCION_MAXIMA_CUOTA_INGRESO
    for monto in range(BASE.solicitud.monto, MONTO_MAXIMO_PREAPROBACION):
        cuota = calcular_cuota(monto, plazo)
        if (Decimal(cuota) / proporcion) % 1 == 0:
            return monto, cuota
    raise AssertionError("no hay un monto con cuota exacta en el rango")


class TestBordeDeLaCuota:
    @pytest.fixture
    def exacto(self):
        monto, cuota = _monto_con_cuota_divisible(PLAZO_BASE)
        ingreso = int(Decimal(cuota) / PROPORCION_MAXIMA_CUOTA_INGRESO)
        # Es de verdad el borde: la cuota es exactamente la proporción máxima del ingreso.
        assert PROPORCION_MAXIMA_CUOTA_INGRESO * ingreso == cuota
        return monto, ingreso

    def test_cuota_exactamente_en_la_proporcion_maxima_se_preaprueba(self, almacen, exacto):
        monto, ingreso = exacto
        evaluacion = evaluar(almacen, monto, salario=ingreso)
        assert evaluacion["preaprobable_automaticamente"] is True, evaluacion

    def test_un_peso_mas_de_ingreso_se_preaprueba(self, almacen, exacto):
        monto, ingreso = exacto
        assert evaluar(almacen, monto, salario=ingreso + 1)["preaprobable_automaticamente"] is True

    def test_un_peso_menos_de_ingreso_supera_la_proporcion(self, almacen, exacto):
        monto, ingreso = exacto
        evaluacion = evaluar(almacen, monto, salario=ingreso - 1)
        assert evaluacion["preaprobable_automaticamente"] is False
        assert causas(evaluacion) == ["regla_2"]
        (causa,) = evaluacion["causas_escalamiento"]
        assert causa["valores"]["ingreso_verificado"] == ingreso - 1


# ---------------------------------------------------------------- regla 3: discrepancia de ingreso


class TestBordeDeLaDiscrepancia:
    @pytest.fixture
    def limite(self):
        """Diferencia máxima permitida, en pesos, sobre el ingreso verificado del caso 1."""
        diferencia = DISCREPANCIA_MAXIMA_INGRESO * SALARIO_BASE
        assert diferencia % 1 == 0, "el borde exacto exige una diferencia entera de pesos"
        return int(diferencia)

    @pytest.mark.parametrize("signo", [1, -1], ids=["declara_mas", "declara_menos"])
    def test_diferencia_exactamente_en_el_maximo_no_escala(self, almacen, limite, signo):
        evaluacion = evaluar(almacen, declarado=SALARIO_BASE + signo * limite)
        assert evaluacion["preaprobable_automaticamente"] is True, evaluacion

    @pytest.mark.parametrize("signo", [1, -1], ids=["declara_mas", "declara_menos"])
    def test_un_peso_por_debajo_del_maximo_no_escala(self, almacen, limite, signo):
        evaluacion = evaluar(almacen, declarado=SALARIO_BASE + signo * (limite - 1))
        assert evaluacion["preaprobable_automaticamente"] is True, evaluacion

    @pytest.mark.parametrize("signo", [1, -1], ids=["declara_mas", "declara_menos"])
    def test_un_peso_por_encima_del_maximo_escala_solo_por_la_discrepancia(
        self, almacen, limite, signo
    ):
        evaluacion = evaluar(almacen, declarado=SALARIO_BASE + signo * (limite + 1))
        assert evaluacion["preaprobable_automaticamente"] is False
        assert causas(evaluacion) == ["regla_3"]
        (causa,) = evaluacion["causas_escalamiento"]
        assert causa["valores"]["verificado"] == SALARIO_BASE


# ---------------------------------------------------------------- identidad, humano y fuera de política


@pytest.mark.anyio
async def test_identidad_no_verificada_se_bloquea_en_los_hooks_y_en_el_core(almacen):
    await resolver_bloquear(catalogo().por_id("preaprobar_sin_identidad"), almacen)


@pytest.mark.anyio
async def test_identidad_bloqueada_despues_de_registrar_no_se_preaprueba(almacen):
    evaluar(almacen)
    (id_solicitud,) = almacen.leer()["solicitudes"]
    persona = BASE.solicitud.id_solicitante
    for _ in range(3):
        with pytest.raises(ErrorCore):
            verificar_identidad(almacen, persona, "2000-01-01", hoy=HOY)
    salida = await invocar(
        crear_hook_preaprobacion(almacen), "preaprobar_credito", id_solicitud=id_solicitud
    )
    assert salida["hookSpecificOutput"]["permissionDecision"] == "deny"
    error = error_de(preaprobar_credito, almacen, id_solicitud)
    assert error.codigo == "IDENTIDAD_NO_VERIFICADA"


@pytest.mark.anyio
async def test_solicitud_de_una_persona_se_escala_sin_mas(almacen):
    await resolver_escalar_humano(catalogo().por_id("pedir_persona"), almacen)


@pytest.mark.anyio
async def test_caso_fuera_de_politica_se_escala_sin_estimar_nada(almacen):
    await resolver_escalar_por_regla(catalogo().por_id("moneda_extranjera"), almacen)
