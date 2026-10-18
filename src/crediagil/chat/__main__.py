"""Arranque de la interfaz de chat: `uv run python -m crediagil.chat` (spec 008).

Escucha solo en 127.0.0.1: no tiene autenticación y usa la clave de la API del equipo.
"""

from __future__ import annotations

import os

import uvicorn

from crediagil.chat.app import crear_app
from crediagil.config import cargar_entorno

HOST = "127.0.0.1"
PUERTO_POR_DEFECTO = 8000


def puerto() -> int:
    valor = os.environ.get("CREDIAGIL_CHAT_PUERTO", "")
    try:
        numero = int(valor) if valor else PUERTO_POR_DEFECTO
    except ValueError:
        raise SystemExit(f"CREDIAGIL_CHAT_PUERTO no es un número válido: {valor!r}") from None
    if not 1 <= numero <= 65535:
        raise SystemExit(f"CREDIAGIL_CHAT_PUERTO fuera de rango: {numero}")
    return numero


def main() -> None:
    cargar_entorno()
    uvicorn.run(crear_app(), host=HOST, port=puerto(), log_level="info")


if __name__ == "__main__":
    main()
