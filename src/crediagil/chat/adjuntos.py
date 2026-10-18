"""Validación de los adjuntos que llegan por la API (spec 008, research R6).

El servidor decide: el navegador repite estas comprobaciones solo como ayuda. Los archivos llegan
en base64 y se decodifican de forma estricta (UTF-8, con o sin BOM), de modo que un archivo
ilegible se rechaza en lugar de enviar al modelo caracteres de reemplazo.
"""

from __future__ import annotations

import base64
import binascii
import os
import re
from collections.abc import Sequence

from crediagil.agent.documentos import DocumentoAdjunto

LIMITE_BYTES_ADJUNTO = 100 * 1024
LIMITE_ADJUNTOS = 5
EXTENSIONES = (".txt", ".md")

# Un archivo de LIMITE bytes ocupa a lo sumo este largo en base64: sirve para rechazar lo enorme
# sin decodificarlo.
_MAX_B64 = ((LIMITE_BYTES_ADJUNTO + 2) // 3) * 4


class ErrorAdjunto(Exception):
    """Un adjunto no es válido; `codigo` es estable y `mensaje` está listo para mostrarse."""

    def __init__(self, codigo: str, mensaje: str) -> None:
        super().__init__(mensaje)
        self.codigo = codigo
        self.mensaje = mensaje


def _nombre_base(nombre: str) -> str:
    return re.split(r"[\\/]", nombre)[-1].strip()


def _decodificar(entrada) -> DocumentoAdjunto:
    if not isinstance(entrada, dict):
        raise ErrorAdjunto(
            "ADJUNTO_INVALIDO", "Cada adjunto debe indicar su nombre y su contenido."
        )
    nombre, contenido = entrada.get("nombre"), entrada.get("contenido_b64")
    if not isinstance(nombre, str) or not isinstance(contenido, str):
        raise ErrorAdjunto(
            "ADJUNTO_INVALIDO", "Cada adjunto debe indicar su nombre y su contenido."
        )
    base = _nombre_base(nombre)
    if not base:
        raise ErrorAdjunto("ADJUNTO_INVALIDO", "Un adjunto no tiene nombre de archivo.")

    admitidas = " y ".join(EXTENSIONES)
    if os.path.splitext(base)[1].lower() not in EXTENSIONES:
        raise ErrorAdjunto(
            "EXTENSION_NO_ADMITIDA",
            f'El archivo "{base}" no se puede adjuntar: solo se admiten archivos {admitidas}.',
        )

    demasiado_grande = ErrorAdjunto(
        "ADJUNTO_DEMASIADO_GRANDE",
        f'El archivo "{base}" supera el tamaño máximo de {LIMITE_BYTES_ADJUNTO // 1024} KiB.',
    )
    if len(contenido) > _MAX_B64:
        raise demasiado_grande
    try:
        crudo = base64.b64decode(contenido, validate=True)
    except (binascii.Error, ValueError):
        raise ErrorAdjunto("ADJUNTO_ILEGIBLE", f'No se pudo leer el archivo "{base}".') from None
    if len(crudo) > LIMITE_BYTES_ADJUNTO:
        raise demasiado_grande
    try:
        texto = crudo.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ErrorAdjunto(
            "ADJUNTO_ILEGIBLE",
            f'El archivo "{base}" no es texto UTF-8 legible.',
        ) from None
    if not texto.strip():
        raise ErrorAdjunto("ADJUNTO_VACIO", f'El archivo "{base}" está vacío.')
    return DocumentoAdjunto(nombre=base, texto=texto)


def decodificar_adjuntos(entradas: Sequence | None) -> list[DocumentoAdjunto]:
    """Valida y decodifica los adjuntos de un mensaje; lanza `ErrorAdjunto` con el primer fallo."""
    if entradas is None:
        return []
    if not isinstance(entradas, list | tuple):
        raise ErrorAdjunto("ADJUNTO_INVALIDO", "Los adjuntos deben enviarse como una lista.")
    if len(entradas) > LIMITE_ADJUNTOS:
        raise ErrorAdjunto(
            "ADJUNTOS_DEMASIADOS",
            f"Se pueden adjuntar como máximo {LIMITE_ADJUNTOS} archivos por mensaje.",
        )
    return [_decodificar(entrada) for entrada in entradas]
