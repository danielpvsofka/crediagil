"""Hook `PreToolUse` sobre `Agent`: la delegación al extractor se verifica en código (spec 007).

Principio II: que cada documento llegue al subagente con su `documento_id`, su nombre y su texto
completo no depende del prompt. El hook niega cualquier otra delegación. Falla cerrado.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from datetime import UTC, datetime

from claude_agent_sdk import HookMatcher

from crediagil.agent.documentos import DocumentoAdjunto
from crediagil.agent.extractor import SUBAGENTE
from crediagil.agent.hooks import PERMITIR, Decision, HookCallback, salida_deny
from crediagil.agent.negaciones import Negacion, RegistroNegaciones

HERRAMIENTA_DELEGACION = "Agent"
TIMEOUT_HOOK = 10

registro_log = logging.getLogger("crediagil.agent")


def decidir_delegacion(documentos: Mapping[str, DocumentoAdjunto], tool_input) -> Decision:
    """Permite solo delegar en el extractor con el documento completo."""
    prompt = tool_input.get("prompt") if isinstance(tool_input, dict) else None
    if not isinstance(prompt, str) or not prompt.strip():
        return Decision.negar(
            "ENTRADA_INVALIDA",
            "La delegación no trae un prompt válido.",
            {"campo": "prompt"},
        )
    subagente = tool_input.get("subagent_type")
    if subagente != SUBAGENTE:
        return Decision.negar(
            "SUBAGENTE_NO_PERMITIDO",
            f"No se permite delegar en {subagente!r}.",
            {"subagent_type": subagente},
        )
    if tool_input.get("run_in_background"):
        return Decision.negar(
            "ENTRADA_INVALIDA",
            "La delegación no puede ir en segundo plano: el turno terminaría sin el resultado.",
            {"campo": "run_in_background"},
        )
    mencionados = [
        documento
        for documento_id, documento in documentos.items()
        if re.search(rf"(?<![\w-]){re.escape(documento_id)}(?![\w-])", prompt)
    ]
    if not mencionados:
        return Decision.negar(
            "DOCUMENTO_DESCONOCIDO",
            "La delegación no menciona ningún documento_id conocido.",
        )
    for documento in mencionados:
        if documento.nombre not in prompt or documento.texto.strip() not in prompt:
            return Decision.negar(
                "DELEGACION_INCOMPLETA",
                f"La delegación de {documento.documento_id} no trae el nombre y el texto "
                "completo del documento.",
                {"documento_id": documento.documento_id},
            )
    return Decision.permitir_llamada()


def crear_hook_delegacion(
    documentos: Mapping[str, DocumentoAdjunto],
    registro: RegistroNegaciones | None = None,
    ahora: str | None = None,
) -> HookCallback:
    """`documentos` es el mapa vivo `documento_id -> adjunto`: el agente lo amplía en cada turno."""

    async def hook(input_data: dict, _tool_use_id: str | None, _context: dict) -> dict:
        if input_data.get("tool_name") != HERRAMIENTA_DELEGACION:
            return PERMITIR
        try:
            decision = decidir_delegacion(documentos, input_data.get("tool_input"))
        except Exception:  # noqa: BLE001 — fail-closed: ningún error interno deja pasar la llamada
            registro_log.exception("Error inesperado en el hook de delegación")
            decision = Decision.negar("ERROR_INTERNO", "Error interno al comprobar la llamada.")
        if decision.permitir:
            return PERMITIR
        if registro is not None:
            registro.registrar(
                Negacion(
                    herramienta=HERRAMIENTA_DELEGACION,
                    codigo=decision.codigo,
                    mensaje=decision.mensaje,
                    accion=decision.accion,
                    detalles=decision.detalles,
                    momento=ahora or datetime.now(UTC).isoformat(),
                )
            )
        return salida_deny(decision)

    return hook


def crear_matcher_delegacion(
    documentos: Mapping[str, DocumentoAdjunto], registro: RegistroNegaciones | None = None
) -> HookMatcher:
    return HookMatcher(
        matcher=HERRAMIENTA_DELEGACION,
        hooks=[crear_hook_delegacion(documentos, registro)],
        timeout=TIMEOUT_HOOK,
    )
