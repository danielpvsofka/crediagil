"""Búsqueda y verificación de identidad del solicitante en el core simulado (FR-005–FR-012).

Lógica pura sobre `AlmacenEstado`: lanza `ErrorCore` y no sabe nada del protocolo MCP.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import UTC, date, datetime

from crediagil.mcp_server.errores import ErrorCore, TipoError
from crediagil.mcp_server.estado import AlmacenEstado, normalizar_documento

# Parámetro del core simulado (no de la política de crédito de la constitución).
MAX_INTENTOS_VERIFICACION = 3
MIN_CARACTERES_NOMBRE = 3
FECHA_ISO = re.compile(r"\d{4}-\d{2}-\d{2}")


def normalizar_nombre(texto: str) -> str:
    descompuesto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in descompuesto if not unicodedata.combining(c)).casefold()


def buscar_solicitante(
    almacen: AlmacenEstado, documento: str | None = None, nombre: str | None = None
) -> list[dict]:
    """Coincidencias por documento exacto (normalizado) o por nombre parcial. Nunca la fecha."""
    if (documento is None) == (nombre is None):
        raise _parametros_invalidos("Indica exactamente uno: documento o nombre.", "documento")
    if nombre is not None and len(nombre.strip()) < MIN_CARACTERES_NOMBRE:
        raise _parametros_invalidos(
            f"El nombre debe tener al menos {MIN_CARACTERES_NOMBRE} caracteres.", "nombre"
        )

    solicitantes = almacen.leer()["solicitantes"].values()
    if documento is not None:
        buscado = normalizar_documento(documento)
        encontrados = [s for s in solicitantes if s["documento"] == buscado]
    else:
        buscado = normalizar_nombre(nombre.strip())
        encontrados = [s for s in solicitantes if buscado in normalizar_nombre(s["nombre"])]
    return [
        {
            "id_solicitante": s["id_solicitante"],
            "documento": s["documento"],
            "nombre": s["nombre"],
            "bloqueado": s["bloqueado"],
        }
        for s in encontrados
    ]


def verificar_identidad(
    almacen: AlmacenEstado,
    id_solicitante: str,
    fecha_nacimiento: str,
    hoy: date | None = None,
    ahora: datetime | None = None,
) -> dict:
    """Compara la fecha de nacimiento; bloquea al alcanzar el máximo de intentos fallidos.

    El resultado se decide dentro de la transacción y el error se lanza después, para que el
    contador de intentos quede guardado aunque la respuesta sea un error.
    """
    fecha = _validar_fecha(fecha_nacimiento, hoy or date.today())
    error = None
    with almacen.transaccion() as datos:
        solicitante = datos["solicitantes"].get(id_solicitante)
        if solicitante is None:
            error = ErrorCore(
                TipoError.NEGOCIO,
                "SOLICITANTE_NO_ENCONTRADO",
                "No existe un solicitante con ese identificador; búscalo primero.",
                {"id_solicitante": id_solicitante},
            )
        elif solicitante["bloqueado"]:
            error = _bloqueado(id_solicitante)
        elif solicitante["fecha_nacimiento"] == fecha.isoformat():
            solicitante["intentos_fallidos"] = 0
            # Constancia que consultan registro y preaprobación (spec 005, FR-007).
            solicitante["verificado_en"] = (ahora or datetime.now(UTC)).isoformat()
        else:
            solicitante["intentos_fallidos"] += 1
            restantes = MAX_INTENTOS_VERIFICACION - solicitante["intentos_fallidos"]
            if restantes <= 0:
                solicitante["bloqueado"] = True
                solicitante["verificado_en"] = None
                error = _bloqueado(id_solicitante)
            else:
                error = ErrorCore(
                    TipoError.NEGOCIO,
                    "IDENTIDAD_NO_COINCIDE",
                    "La fecha de nacimiento no coincide con la registrada.",
                    {"intentos_restantes": restantes},
                )
    if error is not None:
        raise error
    return {"verificado": True, "id_solicitante": id_solicitante}


def identidad_vigente(solicitante: dict) -> bool:
    """Verificada alguna vez y no bloqueada desde entonces (la verificación no caduca)."""
    return solicitante.get("verificado_en") is not None and not solicitante.get("bloqueado")


def _validar_fecha(texto: str, hoy: date) -> date:
    error = ErrorCore(
        TipoError.VALIDACION,
        "FECHA_INVALIDA",
        "La fecha de nacimiento debe ser una fecha válida AAAA-MM-DD y no futura.",
        {"fecha_nacimiento": texto},
    )
    if not isinstance(texto, str) or not FECHA_ISO.fullmatch(texto):
        raise error
    try:
        fecha = date.fromisoformat(texto)
    except ValueError:
        raise error from None
    if fecha > hoy:
        raise error
    return fecha


def _bloqueado(id_solicitante: str) -> ErrorCore:
    return ErrorCore(
        TipoError.PERMISOS,
        "SOLICITANTE_BLOQUEADO",
        "El solicitante está bloqueado por intentos fallidos de verificación; escala a un "
        "analista.",
        {"id_solicitante": id_solicitante},
    )


def _parametros_invalidos(mensaje: str, campo: str) -> ErrorCore:
    return ErrorCore(TipoError.VALIDACION, "PARAMETROS_INVALIDOS", mensaje, {"campo": campo})
