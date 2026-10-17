"""Tests del ingreso verificado: contracts/extraction.md §income (FR-012–FR-014).

Documentos ficticios construidos y validados contra su propio texto.
"""

from __future__ import annotations

import pytest

from crediagil.extraction.income import (
    TipoHallazgo,
    derivar_ingreso,
    resultado_de_hallazgos,
)
from crediagil.extraction.schemas import validar_documento
from crediagil.policy.reglas import Decision

SALARIO = 2_000_000


def pesos(valor: int) -> str:
    return f"${valor:,}".replace(",", ".")


def certificado(salario: int | None = SALARIO, moneda: str | None = "COP"):
    texto = (
        f"Empresa Ficticia S.A.S. certifica un salario mensual de {pesos(salario or 0)} {moneda}."
    )
    datos = {"tipo": "certificado_laboral"}
    if salario is not None:
        datos["salario_mensual"] = {
            "valor": salario,
            "fragmento": f"salario mensual de {pesos(salario)}",
        }
    if moneda is not None:
        datos["moneda"] = {"valor": moneda, "fragmento": f"{pesos(salario or 0)} {moneda}"}
    return validar_documento(datos, texto)


def extracto(*abonos: int, moneda: str | None = "COP"):
    lineas = [f"ABONO NOMINA EMPRESA FICTICIA {pesos(a)} #{i}" for i, a in enumerate(abonos)]
    texto = f"Banco Imaginario. Moneda: {moneda}.\n" + "\n".join(lineas)
    datos = {
        "tipo": "extracto_bancario",
        "abonos_nomina": [{"valor": a, "fragmento": linea} for a, linea in zip(abonos, lineas)],
    }
    if moneda is not None:
        datos["moneda"] = {"valor": moneda, "fragmento": f"Moneda: {moneda}"}
    return validar_documento(datos, texto)


def no_soportado():
    return validar_documento({"tipo": "no_soportado", "tipo_detectado": "pasaporte"}, "")


def tipos(resultado):
    return [h.tipo for h in resultado.hallazgos]


class TestIngresoVerificado:
    def test_sale_del_salario_certificado_con_su_origen(self):
        cert = certificado()
        r = derivar_ingreso([cert, extracto(SALARIO)])
        assert r.ingreso.valor == SALARIO
        assert r.ingreso.moneda == "COP"
        assert r.ingreso.origen == cert.salario_mensual
        assert r.hallazgos == []

    def test_sin_certificado_es_dato_faltante_aunque_haya_nomina(self):
        r = derivar_ingreso([extracto(SALARIO, SALARIO)])
        assert r.ingreso is None
        assert tipos(r) == [TipoHallazgo.DATO_FALTANTE]
        assert r.hallazgos[0].campo == "salario_mensual"

    def test_certificado_sin_salario_no_usa_los_extractos(self):
        r = derivar_ingreso([certificado(salario=None), extracto(SALARIO)])
        assert r.ingreso is None
        assert tipos(r) == [TipoHallazgo.DATO_FALTANTE]

    def test_certificado_sin_moneda_es_dato_faltante(self):
        r = derivar_ingreso([certificado(moneda=None)])
        assert r.ingreso is None
        assert tipos(r) == [TipoHallazgo.DATO_FALTANTE]
        assert r.hallazgos[0].campo == "moneda"

    def test_salario_en_otra_moneda_esta_fuera_de_politica(self):
        r = derivar_ingreso([certificado(moneda="USD")])
        assert r.ingreso is None
        assert tipos(r) == [TipoHallazgo.FUERA_DE_POLITICA]

    def test_extracto_en_otra_moneda_esta_fuera_de_politica(self):
        r = derivar_ingreso([certificado(), extracto(SALARIO, moneda="USD")])
        assert TipoHallazgo.FUERA_DE_POLITICA in tipos(r)

    def test_extracto_en_otra_moneda_no_entra_en_el_promedio(self):
        r = derivar_ingreso([certificado(), extracto(9_000_000, moneda="USD")])
        assert tipos(r) == [TipoHallazgo.FUERA_DE_POLITICA]

    def test_extracto_sin_moneda_no_entra_en_el_promedio(self):
        r = derivar_ingreso([certificado(), extracto(9_000_000, moneda=None)])
        assert r.ingreso.valor == SALARIO
        assert r.hallazgos == []

    def test_varios_certificados_con_salarios_distintos_es_dato_faltante(self):
        r = derivar_ingreso([certificado(), certificado(salario=2_500_000)])
        assert r.ingreso is None
        assert tipos(r) == [TipoHallazgo.DATO_FALTANTE]
        assert r.hallazgos[0].campo == "salario_mensual"
        assert "ambiguo" in r.hallazgos[0].mensaje

    @pytest.mark.parametrize("orden", [1, -1])
    def test_varios_certificados_uno_en_otra_moneda_en_cualquier_orden(self, orden):
        r = derivar_ingreso([certificado(), certificado(moneda="USD")][::orden])
        assert r.ingreso is None
        assert tipos(r) == [TipoHallazgo.FUERA_DE_POLITICA]

    @pytest.mark.parametrize("orden", [1, -1])
    def test_varios_certificados_uno_sin_moneda_en_cualquier_orden(self, orden):
        r = derivar_ingreso([certificado(), certificado(moneda=None)][::orden])
        assert r.ingreso is None
        assert tipos(r) == [TipoHallazgo.DATO_FALTANTE]
        assert r.hallazgos[0].campo == "moneda"

    @pytest.mark.parametrize("orden", [1, -1])
    def test_salarios_distintos_y_uno_en_otra_moneda(self, orden):
        docs = [certificado(), certificado(salario=3_000, moneda="USD")][::orden]
        r = derivar_ingreso(docs)
        assert r.ingreso is None
        assert set(tipos(r)) == {TipoHallazgo.FUERA_DE_POLITICA, TipoHallazgo.DATO_FALTANTE}
        assert resultado_de_hallazgos(r).decision is Decision.FUERA_DE_POLITICA

    def test_certificado_en_otra_moneda_sin_salario(self):
        r = derivar_ingreso([certificado(salario=None, moneda="USD")])
        assert r.ingreso is None
        assert set(tipos(r)) == {TipoHallazgo.FUERA_DE_POLITICA, TipoHallazgo.DATO_FALTANTE}
        assert resultado_de_hallazgos(r).decision is Decision.FUERA_DE_POLITICA

    def test_varios_certificados_con_el_mismo_salario(self):
        r = derivar_ingreso([certificado(), certificado()])
        assert r.ingreso.valor == SALARIO
        assert r.hallazgos == []

    def test_documento_no_soportado_esta_fuera_de_politica(self):
        r = derivar_ingreso([no_soportado(), certificado()])
        assert r.ingreso.valor == SALARIO
        assert tipos(r) == [TipoHallazgo.FUERA_DE_POLITICA]
        assert "pasaporte" in r.hallazgos[0].mensaje


class TestNomina:
    @pytest.mark.parametrize(
        "abonos",
        [(2_200_000,), (1_800_000,), (2_199_999,), (1_800_001,), (2_100_000, 2_300_000)],
    )
    def test_promedio_hasta_10_exacto_no_marca(self, abonos):
        assert derivar_ingreso([certificado(), extracto(*abonos)]).hallazgos == []

    @pytest.mark.parametrize("abonos", [(2_200_001,), (1_799_999,)])
    def test_promedio_sobre_10_es_inconsistencia(self, abonos):
        r = derivar_ingreso([certificado(), extracto(*abonos)])
        assert r.ingreso.valor == SALARIO
        assert tipos(r) == [TipoHallazgo.INCONSISTENCIA_DOCUMENTAL]

    def test_promedio_sobre_varios_extractos(self):
        r = derivar_ingreso([certificado(), extracto(2_000_000), extracto(2_400_002)])
        assert tipos(r) == [TipoHallazgo.INCONSISTENCIA_DOCUMENTAL]

    def test_sin_abonos_no_se_evalua(self):
        assert derivar_ingreso([certificado(), extracto()]).hallazgos == []


class TestResultadoDeHallazgos:
    def test_fuera_de_politica(self):
        r = resultado_de_hallazgos(derivar_ingreso([no_soportado(), certificado()]))
        assert r.decision is Decision.FUERA_DE_POLITICA
        assert r.motivos[0].regla == "documento"

    def test_dato_faltante_va_a_analista(self):
        r = resultado_de_hallazgos(derivar_ingreso([extracto(SALARIO)]))
        assert r.decision is Decision.ANALISTA
        assert r.motivos[0].regla == "ingreso"

    def test_inconsistencia_va_a_analista(self):
        r = resultado_de_hallazgos(derivar_ingreso([certificado(), extracto(2_200_001)]))
        assert r.decision is Decision.ANALISTA
        assert r.motivos[0].regla == "nomina"

    def test_sin_hallazgos(self):
        r = resultado_de_hallazgos(derivar_ingreso([certificado()]))
        assert r.decision is Decision.PREAPROBABLE
        assert r.motivos == []
