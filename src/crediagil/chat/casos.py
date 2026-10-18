"""Casos de prueba que la interfaz puede cargar (spec 008, research R8; spec 009, research R9).

Adaptador sobre el catálogo único de `crediagil.casos`: la interfaz no tiene casos escritos a mano,
así que añadir una carpeta de caso la hace aparecer aquí y en los tests sin editar otro archivo.
"""

from __future__ import annotations

from dataclasses import dataclass

from crediagil.agent.documentos import DocumentoAdjunto
from crediagil.casos import Caso, catalogo


@dataclass(frozen=True)
class CasoPrueba:
    id: str
    nombre: str
    descripcion: str
    mensaje: str
    adjuntos: tuple[DocumentoAdjunto, ...] = ()
    falla_sugerida: int = 0
    numero: int | None = None
    obligatorio: bool = False


def _desde_catalogo(caso: Caso) -> CasoPrueba:
    return CasoPrueba(
        id=caso.id,
        nombre=caso.nombre,
        descripcion=caso.descripcion,
        mensaje=caso.mensaje,
        adjuntos=tuple(DocumentoAdjunto(d.nombre, d.texto) for d in caso.documentos),
        falla_sugerida=caso.falla_simulada,
        numero=caso.numero,
        obligatorio=caso.obligatorio,
    )


CASOS: tuple[CasoPrueba, ...] = tuple(_desde_catalogo(caso) for caso in catalogo().casos)


def caso_por_id(id_caso: str) -> CasoPrueba | None:
    return next((caso for caso in CASOS if caso.id == id_caso), None)


def casos_publicos() -> list[dict]:
    """La forma que sirve `GET /api/casos`."""
    return [
        {
            "id": c.id,
            "nombre": c.nombre,
            "descripcion": c.descripcion,
            "mensaje": c.mensaje,
            "adjuntos": [{"nombre": a.nombre, "texto": a.texto} for a in c.adjuntos],
            "falla_sugerida": c.falla_sugerida,
            "numero": c.numero,
            "obligatorio": c.obligatorio,
        }
        for c in CASOS
    ]
