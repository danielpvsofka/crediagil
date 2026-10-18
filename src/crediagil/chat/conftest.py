"""Configuración compartida de los tests de la interfaz de chat."""

from __future__ import annotations

import pytest


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def clave_ficticia(request, monkeypatch):
    """Los tests nunca usan la clave real: la sesión exige una definida y esta es ficticia.

    Las pruebas con el modelo real (`live`) usan la clave del entorno y no pasan por aquí.
    """
    if request.node.get_closest_marker("live"):
        return
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ficticia-chat")
