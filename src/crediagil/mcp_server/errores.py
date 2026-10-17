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


# Errores de validación que el agente corrige reenviando datos (spec 005, FR-001a).
CODIGOS_VALIDACION_REINTENTABLES = frozenset({"EXTRACCION_INVALIDA", "FRAGMENTO_NO_LITERAL"})


class ErrorCore(Exception):
    """Error de dominio con código estable y mensaje en español.

    Regla de reintento (FR-001a): `transitorio` siempre; `validacion` solo en los códigos de
    extracción corregibles y si se pide explícitamente; `negocio` y `permisos` nunca.
    """

    def __init__(
        self,
        tipo: TipoError,
        codigo: str,
        mensaje: str,
        detalles: dict | None = None,
        reintentable: bool | None = None,
    ) -> None:
        super().__init__(mensaje)
        self.tipo = tipo
        self.codigo = codigo
        self.mensaje = mensaje
        self.detalles = detalles or {}
        por_defecto = tipo is TipoError.TRANSITORIO
        if reintentable is not None and reintentable != por_defecto:
            permitido = (
                tipo is TipoError.VALIDACION
                and reintentable
                and codigo in CODIGOS_VALIDACION_REINTENTABLES
            )
            if not permitido:
                raise ValueError(f"reintentable={reintentable} no permitido para {tipo}/{codigo}")
        self.reintentable = por_defecto if reintentable is None else reintentable


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
