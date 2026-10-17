"""Tests de las reglas 2 y 3 en sus bordes: contracts/policy.md §reglas (Principio VII)."""

from __future__ import annotations

import pytest

from crediagil.policy.reglas import (
    Decision,
    Motivo,
    Resultado,
    combinar,
    evaluar_discrepancia,
    evaluar_preaprobacion,
)

# Cuota de 5.000.000 a 12 meses = 467.010; el 30% exacto corresponde a un ingreso de 1.556.700.
INGRESO_30_EXACTO = 1_556_700


class TestRegla2:
    def test_monto_en_tope_y_cuota_en_30_exacto_preaprueba(self):
        resultado = evaluar_preaprobacion(5_000_000, 12, INGRESO_30_EXACTO)
        assert resultado.decision is Decision.PREAPROBABLE
        assert resultado.cuota == 467_010
        assert resultado.motivos == []

    def test_cuota_un_peso_sobre_30_va_a_analista(self):
        resultado = evaluar_preaprobacion(5_000_000, 12, INGRESO_30_EXACTO - 1)
        assert resultado.decision is Decision.ANALISTA
        assert [m.regla for m in resultado.motivos] == ["regla_2"]
        assert resultado.motivos[0].valores["cuota"] == 467_010

    def test_cuota_un_peso_bajo_30_preaprueba(self):
        resultado = evaluar_preaprobacion(5_000_000, 12, INGRESO_30_EXACTO + 1)
        assert resultado.decision is Decision.PREAPROBABLE
        assert resultado.motivos == []

    def test_monto_un_peso_sobre_el_tope_va_a_analista(self):
        resultado = evaluar_preaprobacion(5_000_001, 12, 10_000_000)
        assert resultado.decision is Decision.ANALISTA
        assert resultado.motivos[0].regla == "regla_2"
        assert resultado.motivos[0].valores["monto"] == 5_000_001

    def test_monto_un_peso_bajo_el_tope_preaprueba(self):
        resultado = evaluar_preaprobacion(4_999_999, 12, 10_000_000)
        assert resultado.decision is Decision.PREAPROBABLE

    @pytest.mark.parametrize("ingreso", [None, 0, -1])
    def test_sin_ingreso_verificado_va_a_analista(self, ingreso):
        resultado = evaluar_preaprobacion(4_000_000, 24, ingreso)
        assert resultado.decision is Decision.ANALISTA
        assert any("ingreso" in m.mensaje for m in resultado.motivos)

    def test_monto_y_cuota_fuera_dan_dos_motivos(self):
        resultado = evaluar_preaprobacion(5_000_001, 12, 1_000_000)
        assert resultado.decision is Decision.ANALISTA
        assert len(resultado.motivos) == 2

    @pytest.mark.parametrize("ingreso", [2_000_000.0, True])
    def test_ingreso_no_entero_es_error(self, ingreso):
        with pytest.raises(ValueError, match="ingreso"):
            evaluar_preaprobacion(4_000_000, 24, ingreso)

    def test_plazo_invalido_propaga_error(self):
        with pytest.raises(ValueError, match="plazo"):
            evaluar_preaprobacion(4_000_000, 61, 10_000_000)


class TestRegla3:
    VERIFICADO = 2_000_000

    @pytest.mark.parametrize("declarado", [2_200_000, 1_800_000, 2_199_999, 1_800_001])
    def test_diferencia_hasta_10_exacto_no_escala(self, declarado):
        resultado = evaluar_discrepancia(declarado, self.VERIFICADO)
        assert resultado.decision is Decision.PREAPROBABLE
        assert resultado.motivos == []

    @pytest.mark.parametrize("declarado", [2_200_001, 1_799_999])
    def test_diferencia_sobre_10_escala(self, declarado):
        resultado = evaluar_discrepancia(declarado, self.VERIFICADO)
        assert resultado.decision is Decision.ANALISTA
        assert resultado.motivos[0].regla == "regla_3"
        assert resultado.motivos[0].valores["declarado"] == declarado

    @pytest.mark.parametrize("verificado", [0, -1, 2_000_000.0, True])
    def test_verificado_no_entero_positivo_es_error(self, verificado):
        with pytest.raises(ValueError, match="verificado"):
            evaluar_discrepancia(2_000_000, verificado)

    @pytest.mark.parametrize("declarado", [-1, 2_200_000.0, True])
    def test_declarado_no_entero_o_negativo_es_error(self, declarado):
        with pytest.raises(ValueError, match="declarado"):
            evaluar_discrepancia(declarado, self.VERIFICADO)

    def test_declarado_cero_escala(self):
        assert evaluar_discrepancia(0, self.VERIFICADO).decision is Decision.ANALISTA


class TestCombinar:
    def _r(self, decision, regla=None, cuota=None):
        motivos = [Motivo(regla=regla, mensaje=regla, valores={})] if regla else []
        return Resultado(decision=decision, cuota=cuota, motivos=motivos)

    def test_fuera_de_politica_prevalece(self):
        r = combinar(
            self._r(Decision.ANALISTA, "regla_2"),
            self._r(Decision.FUERA_DE_POLITICA, "moneda"),
        )
        assert r.decision is Decision.FUERA_DE_POLITICA
        assert [m.regla for m in r.motivos] == ["regla_2", "moneda"]

    def test_analista_prevalece_sobre_preaprobable(self):
        r = combinar(self._r(Decision.PREAPROBABLE), self._r(Decision.ANALISTA, "regla_3"))
        assert r.decision is Decision.ANALISTA

    def test_todo_preaprobable(self):
        r = combinar(self._r(Decision.PREAPROBABLE, cuota=100), self._r(Decision.PREAPROBABLE))
        assert r.decision is Decision.PREAPROBABLE
        assert r.motivos == []

    def test_conserva_la_primera_cuota(self):
        r = combinar(self._r(Decision.PREAPROBABLE), self._r(Decision.PREAPROBABLE, cuota=7))
        assert r.cuota == 7

    def test_sin_resultados_es_error(self):
        with pytest.raises(ValueError):
            combinar()
