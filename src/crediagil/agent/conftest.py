"""Configuración compartida de los tests del agente."""

from __future__ import annotations

import pytest


@pytest.fixture
def anyio_backend():
    return "asyncio"
