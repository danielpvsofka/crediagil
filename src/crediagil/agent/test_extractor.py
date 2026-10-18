"""Tests del subagente extractor (spec 007, FR-005)."""

from __future__ import annotations

from crediagil.agent.extractor import crear_extractor
from crediagil.agent.prompts import PROMPT_EXTRACTOR


def test_solo_puede_usar_validar_extraccion():
    agente = crear_extractor("crediagil-core", "modelo-x")
    assert agente.tools == ["mcp__crediagil-core__validar_extraccion"]
    assert agente.model == "modelo-x"
    assert agente.prompt == PROMPT_EXTRACTOR
    assert agente.maxTurns is not None and agente.maxTurns > 0
    assert agente.background is False


def test_el_nombre_depende_del_servidor():
    agente = crear_extractor("otro", "m")
    assert agente.tools == ["mcp__otro__validar_extraccion"]
