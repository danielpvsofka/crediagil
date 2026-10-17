"""Tests de calcular_cuota: contracts/policy.md §cuota."""

from __future__ import annotations

import pytest

from crediagil.policy.cuota import calcular_cuota


@pytest.mark.parametrize(
    ("monto", "plazo", "esperado"),
    [
        (4_000_000, 24, 206_723),  # ejemplo del issue #3
        (4_000_000, 6, 709_291),  # plazo mínimo
        (4_000_000, 60, 109_568),  # plazo máximo
        (5_000_000, 12, 467_010),
    ],
)
def test_cuota_sistema_frances(monto, plazo, esperado):
    assert calcular_cuota(monto, plazo) == esperado


def test_cuota_es_entero():
    assert isinstance(calcular_cuota(4_000_000, 24), int)


@pytest.mark.parametrize("plazo", [5, 61, 0, -12])
def test_plazo_fuera_de_rango(plazo):
    with pytest.raises(ValueError, match="plazo"):
        calcular_cuota(4_000_000, plazo)


@pytest.mark.parametrize("plazo", [12.0, True, "12"])
def test_plazo_no_entero(plazo):
    with pytest.raises(ValueError, match="plazo"):
        calcular_cuota(4_000_000, plazo)


@pytest.mark.parametrize("monto", [0, -1, 4_000_000.0, True])
def test_monto_no_positivo(monto):
    with pytest.raises(ValueError, match="monto"):
        calcular_cuota(monto, 24)
