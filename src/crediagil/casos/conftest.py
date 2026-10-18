"""Arnés compartido de los tests del catálogo de casos (spec 009)."""

from __future__ import annotations

import pytest

from crediagil.mcp_server.estado import AlmacenEstado


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def almacen(tmp_path):
    """Un estado del core temporal; el core lo crea al arrancar, así que se lee una vez."""
    almacen = AlmacenEstado(tmp_path / "estado.json")
    almacen.leer()
    return almacen
