"""Los parámetros en código deben coincidir con la constitución (FR-002, SC-005).

Los valores esperados se leen del texto de la constitución: si alguien cambia una constante sin
enmendarla, este test falla.
"""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

from crediagil.policy import params

CONSTITUCION = Path(__file__).resolve().parents[3] / ".specify" / "memory" / "constitution.md"
TEXTO = CONSTITUCION.read_text(encoding="utf-8")


def porcentaje(texto: str) -> Decimal:
    """'1,8' → Decimal('0.018')."""
    return Decimal(texto.replace(",", ".")) / 100


def parametros_fijos() -> re.Match:
    match = re.search(
        r"tasa fija de (?P<tasa>\d+,\d+)% mensual\. La tasa y los umbrales "
        r"\(\$(?P<monto>[\d.]+) COP, (?P<cuota>\d+)%,\s*(?P<discrepancia>\d+)%\)",
        TEXTO,
    )
    assert match, "No se encontraron los parámetros fijos en la constitución"
    return match


def test_tasa_coincide_con_la_constitucion():
    assert params.TASA_MENSUAL == porcentaje(parametros_fijos()["tasa"])


def test_monto_maximo_coincide_con_la_constitucion():
    monto = int(parametros_fijos()["monto"].replace(".", ""))
    assert params.MONTO_MAXIMO_PREAPROBACION == monto


def test_proporcion_cuota_ingreso_coincide_con_la_constitucion():
    assert params.PROPORCION_MAXIMA_CUOTA_INGRESO == porcentaje(parametros_fijos()["cuota"])


def test_discrepancia_maxima_coincide_con_la_constitucion():
    esperado = porcentaje(parametros_fijos()["discrepancia"])
    assert params.DISCREPANCIA_MAXIMA_INGRESO == esperado


def test_moneda_es_cop():
    assert "pesos colombianos (COP)" in TEXTO
    assert params.MONEDA == "COP"


def test_plazos_de_la_spec():
    # Spec 003, FR-004: plazo entero de 6 a 60 meses (la constitución delega los plazos a la spec).
    assert (params.PLAZO_MINIMO_MESES, params.PLAZO_MAXIMO_MESES) == (6, 60)


def test_tipos_exactos():
    for valor in (
        params.TASA_MENSUAL,
        params.PROPORCION_MAXIMA_CUOTA_INGRESO,
        params.DISCREPANCIA_MAXIMA_INGRESO,
    ):
        assert isinstance(valor, Decimal)
    assert isinstance(params.MONTO_MAXIMO_PREAPROBACION, int)
