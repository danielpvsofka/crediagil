"""Utilidades de los tests de scripts/ (spec 011). No se llama conftest.py a propósito: en este
directorio no hay `__init__.py` y `from conftest import …` resolvería el de `.claude/hooks/`."""

from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def tarjeta_ficticia(prefijo: str = "4", longitud: int = 16) -> str:
    """Número ficticio de `longitud` dígitos válido por Luhn, construido en ejecución.

    Nunca se escribe como literal para que ningún archivo del repositorio tenga forma de tarjeta.
    """
    cuerpo = (prefijo + "0" * longitud)[: longitud - 1]
    total = 0
    for indice, caracter in enumerate(reversed(cuerpo)):
        digito = int(caracter)
        if indice % 2 == 0:
            digito *= 2
            if digito > 9:
                digito -= 9
        total += digito
    return cuerpo + str((10 - total % 10) % 10)


def formatos_pesos(monto: int) -> list[str]:
    """Un monto en pesos con punto de miles, con coma de miles y sin separador."""
    return [f"{monto:,}".replace(",", "."), f"{monto:,}", str(monto)]


def formatos_porcentaje(proporcion) -> list[str]:
    """Una proporción como porcentaje, con punto o coma decimal, con y sin espacio antes de `%`."""
    numero = f"{(proporcion * 100).normalize():f}"
    variantes = {numero, numero.replace(".", ",")}
    return [f"{variante}{separador}%" for variante in variantes for separador in ("", " ")]


def parametros_de_la_politica() -> list[str]:
    """Formas en que el texto podría repetir la tasa o un umbral de la política (Principio I)."""
    from crediagil.policy import params

    return [
        *formatos_pesos(params.MONTO_MAXIMO_PREAPROBACION),
        *formatos_porcentaje(params.TASA_MENSUAL),
        *formatos_porcentaje(params.PROPORCION_MAXIMA_CUOTA_INGRESO),
        *formatos_porcentaje(params.DISCREPANCIA_MAXIMA_INGRESO),
    ]
