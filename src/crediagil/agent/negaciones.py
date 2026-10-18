"""Registro de negaciones de los hooks, consultable por la interfaz (spec 006, FR-009)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field

registro_log = logging.getLogger("crediagil.agent")


@dataclass(frozen=True)
class Negacion:
    """Una llamada que un hook impidió, con lo que la interfaz necesita para mostrarla."""

    herramienta: str  # sin el prefijo del servidor MCP
    codigo: str
    mensaje: str
    accion: str
    detalles: dict = field(default_factory=dict)
    momento: str = ""  # ISO-8601 UTC


class RegistroNegaciones:
    """Guarda en memoria las negaciones de la sesión y avisa a `al_negar`, si se indicó."""

    def __init__(self, al_negar: Callable[[Negacion], None] | None = None) -> None:
        self._negaciones: list[Negacion] = []
        self._al_negar = al_negar

    def registrar(self, negacion: Negacion) -> None:
        self._negaciones.append(negacion)
        if self._al_negar is not None:
            try:
                self._al_negar(negacion)
            except Exception:  # noqa: BLE001 — un fallo de la interfaz no cambia la decisión
                registro_log.exception("Falló el aviso de la negación %s", negacion.codigo)

    def listar(self) -> list[Negacion]:
        return list(self._negaciones)

    def ultima(self) -> Negacion | None:
        return self._negaciones[-1] if self._negaciones else None
