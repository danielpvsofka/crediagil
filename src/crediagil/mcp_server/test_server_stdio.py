"""Extremo a extremo: arranca el servidor por stdio y lo usa con el cliente MCP (FR-017, SC-006)."""

from __future__ import annotations

import os
import subprocess
import sys

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_arranque_por_stdio_lista_y_ejecuta_herramientas(tmp_path):
    ruta_estado = tmp_path / "estado.json"
    parametros = StdioServerParameters(
        command=sys.executable,
        args=["-m", "crediagil.mcp_server.server"],
        env={**os.environ, "CREDIAGIL_MCP_ESTADO": str(ruta_estado)},
    )
    async with (
        stdio_client(parametros) as (lectura, escritura),
        ClientSession(lectura, escritura) as sesion,
    ):
        await sesion.initialize()
        # US4-3: el estado se crea al arrancar, antes de cualquier llamada a herramientas.
        assert ruta_estado.exists()
        herramientas = await sesion.list_tools()
        nombres = {h.name for h in herramientas.tools}
        assert nombres == {"buscar_solicitante", "verificar_identidad"}

        resultado = await sesion.call_tool("buscar_solicitante", {"nombre": "prueba"})
        assert resultado.structured_content["ok"] is True
        assert len(resultado.structured_content["coincidencias"]) >= 2

    assert ruta_estado.exists()


def test_configuracion_de_fallas_invalida_no_arranca(tmp_path):
    proceso = subprocess.run(
        [sys.executable, "-m", "crediagil.mcp_server.server"],
        env={
            **os.environ,
            "CREDIAGIL_MCP_ESTADO": str(tmp_path / "e.json"),
            "CREDIAGIL_MCP_FALLAS_N": "abc",
        },
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert proceso.returncode == 2
    assert "CREDIAGIL_MCP_FALLAS_N" in proceso.stderr
