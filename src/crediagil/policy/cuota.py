"""Cuota mensual por sistema francés con la tasa fija de la política."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from crediagil.policy.params import PLAZO_MAXIMO_MESES, PLAZO_MINIMO_MESES, TASA_MENSUAL


def validar_plazo(plazo_meses: int) -> None:
    # bool es subclase de int: se rechaza explícitamente.
    if type(plazo_meses) is not int:
        raise ValueError(f"El plazo debe ser un número entero de meses: {plazo_meses!r}")
    if not PLAZO_MINIMO_MESES <= plazo_meses <= PLAZO_MAXIMO_MESES:
        raise ValueError(
            f"El plazo debe estar entre {PLAZO_MINIMO_MESES} y {PLAZO_MAXIMO_MESES} meses: "
            f"{plazo_meses}"
        )


def validar_monto(monto: int) -> None:
    if type(monto) is not int:
        raise ValueError(f"El monto debe ser un número entero de pesos: {monto!r}")
    if monto <= 0:
        raise ValueError(f"El monto debe ser positivo: {monto}")


def calcular_cuota(monto: int, plazo_meses: int) -> int:
    """Cuota = M·i / (1 − (1+i)^−n), redondeada al peso más cercano (mitad hacia arriba)."""
    validar_monto(monto)
    validar_plazo(plazo_meses)
    i = TASA_MENSUAL
    cuota = Decimal(monto) * i / (1 - (1 + i) ** -plazo_meses)
    return int(cuota.quantize(Decimal(1), rounding=ROUND_HALF_UP))
