"""Contrato de respuesta del core: `{ok: true, ...}` u `{ok: false, error: {...}}` (FR-001–003).

La lógica lanza `ErrorCore`; solo `exito` y `fallo` construyen respuestas, así no hay otra forma
posible.
"""

from __future__ import annotations

from enum import StrEnum


class TipoError(StrEnum):
    TRANSITORIO = "transitorio"
    VALIDACION = "validacion"
    NEGOCIO = "negocio"
    PERMISOS = "permisos"


class ErrorCore(Exception):
    """Error de dominio con código estable y mensaje en español."""

    def __init__(
        self, tipo: TipoError, codigo: str, mensaje: str, detalles: dict | None = None
    ) -> None:
        super().__init__(mensaje)
        self.tipo = tipo
        self.codigo = codigo
        self.mensaje = mensaje
        self.detalles = detalles or {}

    @property
    def reintentable(self) -> bool:
        return self.tipo is TipoError.TRANSITORIO


def exito(**datos) -> dict:
    return {"ok": True, **datos}


def fallo(error: ErrorCore) -> dict:
    return {
        "ok": False,
        "error": {
            "tipo": str(error.tipo),
            "codigo": error.codigo,
            "mensaje": error.mensaje,
            "reintentable": error.reintentable,
            "detalles": dict(error.detalles),
        },
    }
