"""Definición del subagente `extractor-documentos` (spec 007, FR-005)."""

from __future__ import annotations

from claude_agent_sdk import AgentDefinition

from crediagil.agent.hooks import nombre_herramienta
from crediagil.agent.prompts import PROMPT_EXTRACTOR

SUBAGENTE = "extractor-documentos"
MAX_TURNOS_EXTRACTOR = 8


def crear_extractor(servidor: str, modelo: str) -> AgentDefinition:
    """Subagente cuya única herramienta es `validar_extraccion` del servidor `servidor`."""
    return AgentDefinition(
        description=(
            "Extrae y valida los datos de un único documento. Recibe documento_id, nombre y "
            "texto completo; devuelve los datos con su fragmento de origen y los faltantes."
        ),
        prompt=PROMPT_EXTRACTOR,
        tools=[nombre_herramienta(servidor, "validar_extraccion")],
        model=modelo,
        maxTurns=MAX_TURNOS_EXTRACTOR,
        background=False,  # el turno no puede terminar antes de que el extractor responda
    )
