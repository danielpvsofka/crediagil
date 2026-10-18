"""Adjuntos de la conversación: ids y mensaje con los documentos embebidos (spec 007, FR-004)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from html import escape


@dataclass(frozen=True)
class DocumentoAdjunto:
    nombre: str
    texto: str
    documento_id: str = ""  # lo asigna el agente: DOC-1, DOC-2, …


def asignar_ids(
    documentos: Sequence[DocumentoAdjunto], ya_asignados: int = 0
) -> tuple[list[DocumentoAdjunto], list[DocumentoAdjunto]]:
    """Asigna `DOC-n` a los adjuntos con texto; devuelve `(con_id, omitidos)`.

    `ya_asignados` es cuántos ids se dieron en turnos anteriores, para que la numeración siga.
    Un adjunto vacío o solo con espacios no se delega: se omite para pedir que lo reenvíen.
    """
    con_id: list[DocumentoAdjunto] = []
    omitidos: list[DocumentoAdjunto] = []
    for documento in documentos:
        if not documento.texto.strip():
            omitidos.append(documento)
            continue
        numero = ya_asignados + len(con_id) + 1
        con_id.append(replace(documento, documento_id=f"DOC-{numero}"))
    return con_id, omitidos


def renderizar_mensaje(mensaje: str, documentos: Sequence[DocumentoAdjunto]) -> str:
    """Mensaje seguido de `<documento id="…" nombre="…">texto</documento>` por adjunto."""
    bloques = [
        f'<documento id="{d.documento_id}" nombre="{escape(d.nombre, quote=True)}">'
        f"{d.texto}</documento>"
        for d in documentos
    ]
    return "\n\n".join([mensaje, *bloques])
