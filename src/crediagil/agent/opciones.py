"""Opciones del agente con aislamiento real (spec 007, FR-014, research R6).

`setting_sources=[]` (no `None`: el valor por defecto del SDK omite la bandera y el CLI cargaría
la configuración de usuario, proyecto y local), lista de herramientas cerrada y solo los
servidores MCP que define este código.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions
from claude_agent_sdk.types import McpSdkServerConfig

from crediagil.agent.canal import HERRAMIENTA_CANAL, SERVIDOR_CANAL
from crediagil.agent.delegacion import HERRAMIENTA_DELEGACION, crear_matcher_delegacion
from crediagil.agent.documentos import DocumentoAdjunto
from crediagil.agent.extractor import SUBAGENTE, crear_extractor
from crediagil.agent.hooks import SERVIDOR_POR_DEFECTO, crear_hooks, nombre_herramienta
from crediagil.agent.negaciones import RegistroNegaciones
from crediagil.agent.prompts import PROMPT_ORQUESTADOR
from crediagil.mcp_server.estado import AlmacenEstado, ruta_por_defecto

MODELO_ORQUESTADOR = "claude-sonnet-5-5"
MODELO_EXTRACTOR = "claude-haiku-4-5-20251001"

HERRAMIENTAS_CORE = (
    "buscar_solicitante",
    "verificar_identidad",
    "validar_extraccion",
    "registrar_solicitud",
    "calcular_capacidad_pago",
    "preaprobar_credito",
    "escalar_a_analista",
)
# Herramientas integradas que el agente nunca debe tener (defensa en profundidad con `tools`).
HERRAMIENTAS_PROHIBIDAS = ("Bash", "Read", "Write", "Edit", "WebFetch", "WebSearch")


@dataclass(frozen=True)
class ConfigAgente:
    ruta_estado: Path = field(default_factory=ruta_por_defecto)
    servidor: str = SERVIDOR_POR_DEFECTO
    modelo: str = field(
        default_factory=lambda: os.environ.get("CREDIAGIL_MODELO_ORQUESTADOR") or MODELO_ORQUESTADOR
    )
    modelo_extractor: str = field(
        default_factory=lambda: os.environ.get("CREDIAGIL_MODELO_EXTRACTOR") or MODELO_EXTRACTOR
    )
    max_turnos: int = 30  # tope de seguridad, no criterio de fin de ciclo
    max_continuaciones: int = 2
    max_presupuesto_usd: float | None = None
    entorno_core: Mapping[str, str] = field(default_factory=dict)


def construir_opciones(
    config: ConfigAgente,
    registro: RegistroNegaciones,
    canal: McpSdkServerConfig,
    documentos: Mapping[str, DocumentoAdjunto],
    almacen: AlmacenEstado,
    cwd: Path,
) -> ClaudeAgentOptions:
    core = [nombre_herramienta(config.servidor, h) for h in HERRAMIENTAS_CORE]
    permitidas = [
        *core,
        nombre_herramienta(SERVIDOR_CANAL, HERRAMIENTA_CANAL),
        HERRAMIENTA_DELEGACION,
    ]

    hooks = crear_hooks(almacen, registro, servidor=config.servidor)
    hooks["PreToolUse"].append(crear_matcher_delegacion(documentos, registro))

    return ClaudeAgentOptions(
        system_prompt=PROMPT_ORQUESTADOR,
        model=config.modelo,
        setting_sources=[],
        tools=[HERRAMIENTA_DELEGACION],
        allowed_tools=permitidas,
        disallowed_tools=list(HERRAMIENTAS_PROHIBIDAS),
        permission_mode="dontAsk",
        strict_mcp_config=True,
        mcp_servers={
            config.servidor: {
                "type": "stdio",
                "command": sys.executable,
                "args": ["-m", "crediagil.mcp_server.server"],
                "env": {"CREDIAGIL_MCP_ESTADO": str(config.ruta_estado), **config.entorno_core},
            },
            SERVIDOR_CANAL: canal,
        },
        agents={SUBAGENTE: crear_extractor(config.servidor, config.modelo_extractor)},
        hooks=hooks,
        cwd=cwd,
        max_turns=config.max_turnos,
        max_budget_usd=config.max_presupuesto_usd,
    )
