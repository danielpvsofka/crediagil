"""Tests de las opciones y el aislamiento del agente (spec 007, FR-014)."""

from __future__ import annotations

import sys

import pytest
from claude_agent_sdk._internal.transport.subprocess_cli import SubprocessCLITransport

from crediagil.agent.canal import crear_canal
from crediagil.agent.negaciones import RegistroNegaciones
from crediagil.agent.opciones import ConfigAgente, construir_opciones
from crediagil.agent.prompts import PROMPT_ORQUESTADOR
from crediagil.mcp_server.estado import AlmacenEstado

PREFIJO = "mcp__crediagil-core__"


def _construir(config, cwd):
    canal, _ = crear_canal()
    return construir_opciones(
        config, RegistroNegaciones(), canal, {}, AlmacenEstado(config.ruta_estado), cwd
    )


@pytest.fixture
def config(tmp_path):
    return ConfigAgente(ruta_estado=tmp_path / "estado.json")


@pytest.fixture
def opciones(config, tmp_path):
    return _construir(config, tmp_path / "cwd")


def test_aislamiento_de_configuracion(opciones):
    assert opciones.setting_sources == []
    assert isinstance(opciones.setting_sources, list)
    assert opciones.tools == ["Agent"]
    assert opciones.permission_mode == "dontAsk"
    assert opciones.strict_mcp_config is True


def test_herramientas_permitidas_son_exactamente_las_del_diseno(opciones):
    esperadas = {
        PREFIJO + nombre
        for nombre in (
            "buscar_solicitante",
            "verificar_identidad",
            "validar_extraccion",
            "registrar_solicitud",
            "calcular_capacidad_pago",
            "preaprobar_credito",
            "escalar_a_analista",
        )
    } | {"mcp__canal__solicitar_informacion", "Agent"}
    assert set(opciones.allowed_tools) == esperadas
    assert len(opciones.allowed_tools) == len(esperadas)


def test_herramientas_prohibidas(opciones):
    assert set(opciones.disallowed_tools) == {
        "Bash",
        "Read",
        "Write",
        "Edit",
        "WebFetch",
        "WebSearch",
    }


def test_servidores_mcp(opciones, config):
    core = opciones.mcp_servers["crediagil-core"]
    assert core["type"] == "stdio"
    assert core["command"] == sys.executable
    assert core["args"] == ["-m", "crediagil.mcp_server.server"]
    assert core["env"] == {"CREDIAGIL_MCP_ESTADO": str(config.ruta_estado)}
    assert opciones.mcp_servers["canal"]["type"] == "sdk"
    assert set(opciones.mcp_servers) == {"crediagil-core", "canal"}


def test_entorno_del_core_se_amplia(config, tmp_path):
    ampliada = ConfigAgente(
        ruta_estado=config.ruta_estado, entorno_core={"CREDIAGIL_MCP_FALLAS_N": "1"}
    )
    entorno = _construir(ampliada, tmp_path).mcp_servers["crediagil-core"]["env"]
    assert entorno["CREDIAGIL_MCP_FALLAS_N"] == "1"
    assert entorno["CREDIAGIL_MCP_ESTADO"] == str(config.ruta_estado)


def test_subagente_extractor(opciones, config):
    extractor = opciones.agents["extractor-documentos"]
    assert extractor.tools == [PREFIJO + "validar_extraccion"]
    assert extractor.model == config.modelo_extractor


def test_tres_hooks_pretooluse(opciones):
    matchers = [m.matcher for m in opciones.hooks["PreToolUse"]]
    assert matchers == [PREFIJO + "registrar_solicitud", PREFIJO + "preaprobar_credito", "Agent"]


def test_prompt_cwd_y_topes(opciones, config, tmp_path):
    assert opciones.system_prompt == PROMPT_ORQUESTADOR
    assert opciones.cwd == tmp_path / "cwd"
    assert opciones.max_turns == config.max_turnos
    assert opciones.model == config.modelo


def test_el_transporte_del_sdk_aisla_de_verdad(opciones):
    """Contrato con el SDK: la bandera de aislamiento llega al comando del CLI."""
    transporte = SubprocessCLITransport(prompt="", options=opciones)
    transporte._cli_path = "claude"  # sin lanzar el proceso: solo se construye el comando
    comando = transporte._build_command()
    assert "--setting-sources=" in comando
    indice = comando.index("--tools")
    assert comando[indice + 1] == "Agent"
    assert "--strict-mcp-config" in comando


def test_modelos_por_defecto_y_variables(monkeypatch):
    monkeypatch.delenv("CREDIAGIL_MODELO_ORQUESTADOR", raising=False)
    monkeypatch.delenv("CREDIAGIL_MODELO_EXTRACTOR", raising=False)
    base = ConfigAgente()
    assert base.modelo == "claude-sonnet-5-5"
    assert base.modelo_extractor == "claude-haiku-4-5-20251001"
    monkeypatch.setenv("CREDIAGIL_MODELO_ORQUESTADOR", "modelo-a")
    monkeypatch.setenv("CREDIAGIL_MODELO_EXTRACTOR", "modelo-b")
    otro = ConfigAgente()
    assert (otro.modelo, otro.modelo_extractor) == ("modelo-a", "modelo-b")
