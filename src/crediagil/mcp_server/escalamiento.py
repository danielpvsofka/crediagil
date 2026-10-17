"""Escalamiento a analista con resumen completo (spec 005, FR-016–FR-018).

No exige identidad: la regla 4 de la constitución pide escalar de inmediato cuando el
solicitante quiere hablar con una persona, aunque aún no se haya verificado nada.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, ValidationError, field_validator

from crediagil.mcp_server.errores import ErrorCore, TipoError
from crediagil.mcp_server.estado import AlmacenEstado, siguiente_id

# Al menos un carácter que no sea espacio.
Texto = Annotated[str, Field(pattern=r"\S")]

Causa = Literal[
    "solicitud_humano",
    "fuera_de_politica",
    "regla_2",
    "regla_3",
    "ingreso_no_verificable",
    "inconsistencia_documental",
    "identidad_bloqueada",
    "otro",
]


class DatoResumen(BaseModel):
    """Dato citado en el resumen, con su procedencia (Principio VI). `valor` no puede ser nulo."""

    model_config = ConfigDict(extra="forbid", strict=True)

    campo: Texto
    valor: Any
    documento: Texto
    fragmento: Texto

    @field_validator("valor")
    @classmethod
    def valor_presente(cls, valor):
        if valor is None:
            raise ValueError("el valor de un dato citado no puede ser nulo")
        return valor


class ResumenEscalamiento(BaseModel):
    """Todas las claves son obligatorias; monto, plazo, datos y discrepancias pueden ir vacíos."""

    model_config = ConfigDict(extra="forbid", strict=True)

    solicitante: Texto
    monto: PositiveInt | None
    plazo: PositiveInt | None
    datos: list[DatoResumen]
    discrepancias: list[Texto]
    causa: Causa
    detalle: Texto
    accion_recomendada: Texto


CLAVES_RESUMEN = tuple(ResumenEscalamiento.model_fields)


def escalar_a_analista(
    almacen: AlmacenEstado,
    resumen: dict,
    id_solicitud: str | None = None,
    ahora: datetime | None = None,
) -> dict:
    validado = _validar(resumen)
    marca = (ahora or datetime.now(UTC)).isoformat()
    with almacen.transaccion() as datos:
        if id_solicitud is not None:
            solicitud = datos["solicitudes"].get(id_solicitud)
            if solicitud is None:
                raise _negocio("SOLICITUD_NO_ENCONTRADA", "No existe esa solicitud.", id_solicitud)
            if solicitud["estado"] == "PREAPROBADA":
                raise _negocio(
                    "SOLICITUD_PREAPROBADA",
                    "La solicitud ya fue preaprobada; no se puede escalar.",
                    id_solicitud,
                )
            solicitud.update(estado="ESCALADA", escalada_en=marca)
        id_escalamiento = siguiente_id(datos["escalamientos"], "ESC")
        datos["escalamientos"][id_escalamiento] = {
            "id_escalamiento": id_escalamiento,
            "id_solicitud": id_solicitud,
            "resumen": validado.model_dump(mode="json"),
            "creado_en": marca,
        }
    return {"id_escalamiento": id_escalamiento, "id_solicitud": id_solicitud}


def _validar(resumen) -> ResumenEscalamiento:
    try:
        return ResumenEscalamiento.model_validate(resumen)
    except ValidationError as exc:
        errores = exc.errors(include_url=False)
        campos = list(dict.fromkeys(str(e["loc"][0]) if e["loc"] else "resumen" for e in errores))
        raise ErrorCore(
            TipoError.VALIDACION,
            "RESUMEN_INCOMPLETO",
            "El resumen está incompleto: completa los campos indicados antes de escalar.",
            {"campos_faltantes": campos},
        ) from None


def _negocio(codigo: str, mensaje: str, id_solicitud: str) -> ErrorCore:
    return ErrorCore(TipoError.NEGOCIO, codigo, mensaje, {"id_solicitud": id_solicitud})
