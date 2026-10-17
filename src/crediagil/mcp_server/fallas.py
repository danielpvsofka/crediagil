"""Inyección de fallas transitorias para pruebas (FR-015).

Desactivada por defecto. Se evalúa antes de tocar el estado, así una falla inyectada nunca lo
modifica.
"""

from __future__ import annotations

import os
import random

from crediagil.mcp_server.errores import ErrorCore, TipoError


class InyectorFallas:
    def __init__(
        self, restantes: int = 0, probabilidad: float = 0.0, semilla: int | None = None
    ) -> None:
        self.restantes = restantes
        self.probabilidad = probabilidad
        self._azar = random.Random(semilla)

    @classmethod
    def desde_entorno(cls) -> InyectorFallas:
        """`CREDIAGIL_MCP_FALLAS_N`, `_PROB` y `_SEMILLA`; valores inválidos → `ValueError`."""
        restantes = _leer("CREDIAGIL_MCP_FALLAS_N", int, 0, lambda v: v >= 0)
        probabilidad = _leer("CREDIAGIL_MCP_FALLAS_PROB", float, 0.0, lambda v: 0 <= v <= 1)
        semilla = _leer("CREDIAGIL_MCP_FALLAS_SEMILLA", int, None, lambda v: True)
        return cls(restantes, probabilidad, semilla)

    def debe_fallar(self) -> bool:
        if self.restantes > 0:
            self.restantes -= 1
            return True
        return self.probabilidad > 0 and self._azar.random() < self.probabilidad

    @staticmethod
    def error_inyectado() -> ErrorCore:
        return ErrorCore(
            TipoError.TRANSITORIO,
            "SERVICIO_NO_DISPONIBLE",
            "El core no está disponible en este momento; reintenta.",
        )


def _leer(variable, tipo, defecto, valido):
    texto = os.environ.get(variable)
    if texto is None or texto == "":
        return defecto
    try:
        valor = tipo(texto)
    except ValueError:
        raise ValueError(f"{variable} inválida: {texto!r}") from None
    if not valido(valor):
        raise ValueError(f"{variable} fuera de rango: {texto!r}")
    return valor
