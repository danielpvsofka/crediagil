"""Hooks `PreToolUse` del Agent SDK que hacen cumplir las reglas 1 y 2 (spec 006).

Principio II: lo determinista se garantiza con código, no con el prompt. Los hooks deciden
leyendo el estado real del core y recalculando con `crediagil.policy`; del modelo solo toman el
identificador de lo que se les pide comprobar. Son de solo lectura y fallan cerrado: ante
cualquier duda, niegan.

Formato del SDK: un callback `async (input_data, tool_use_id, context) -> dict`. `{}` significa
"sin opinión" (la llamada sigue su flujo normal) y una negación es
`{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", ...}}`.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import partial

import anyio
from claude_agent_sdk import HookMatcher

from crediagil.agent.negaciones import Negacion, RegistroNegaciones
from crediagil.mcp_server.errores import ErrorCore
from crediagil.mcp_server.estado import AlmacenEstado
from crediagil.mcp_server.identidad import identidad_vigente
from crediagil.mcp_server.originacion import ESCALADA, evaluar_solicitud_guardada
from crediagil.policy import Decision as DecisionPolitica

SERVIDOR_POR_DEFECTO = "crediagil-core"
TIMEOUT_LECTURA = 5.0
TIMEOUT_HOOK = 10

registro_log = logging.getLogger("crediagil.agent")

# Qué debe hacer el modelo tras cada negación (data-model.md).
ACCIONES = {
    "IDENTIDAD_NO_VERIFICADA": (
        "Verifica la identidad con verificar_identidad; si el solicitante está bloqueado, "
        "escala a un analista."
    ),
    "SOLICITUD_NO_ENCONTRADA": "Usa el id_solicitud que devolvió registrar_solicitud.",
    "SOLICITUD_ESCALADA": "No preapruebes: un analista continúa el caso.",
    "HALLAZGOS_DOCUMENTALES": "Escala a un analista con los hallazgos.",
    "NO_PREAPROBABLE": "Escala a un analista con las causas.",
    "ESTADO_ILEGIBLE": "Reintenta una vez; si persiste, escala a un analista.",
    "ENTRADA_INVALIDA": "Corrige los argumentos de la llamada.",
    "ERROR_INTERNO": "No reintentes de inmediato; escala a un analista si persiste.",
    # Delegación al subagente (spec 007).
    "SUBAGENTE_NO_PERMITIDO": "Solo puedes delegar en extractor-documentos.",
    "DOCUMENTO_DESCONOCIDO": "Indica el documento_id del adjunto.",
    "DELEGACION_INCOMPLETA": "Pasa documento_id, nombre y texto completo, sin resumir.",
}

# Sin opinión: la llamada sigue su flujo normal de permisos (no se devuelve `allow` explícito).
PERMITIR: dict = {}


@dataclass(frozen=True)
class Decision:
    """Resultado de comprobar una llamada: permitirla o negarla con su motivo."""

    permitir: bool
    codigo: str | None = None
    mensaje: str | None = None
    accion: str | None = None
    detalles: dict = field(default_factory=dict)

    @classmethod
    def permitir_llamada(cls) -> Decision:
        return cls(permitir=True)

    @classmethod
    def negar(cls, codigo: str, mensaje: str, detalles: dict | None = None) -> Decision:
        if codigo not in ACCIONES:
            raise ValueError(f"código de negación desconocido: {codigo}")
        return cls(
            permitir=False,
            codigo=codigo,
            mensaje=mensaje,
            accion=ACCIONES[codigo],
            detalles=detalles or {},
        )


def formatear_motivo(decision: Decision) -> str:
    """Motivo que recibe el modelo: `[CODIGO] mensaje Acción: acción.`"""
    return f"[{decision.codigo}] {decision.mensaje} Acción: {decision.accion}"


def salida_deny(decision: Decision) -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": formatear_motivo(decision),
        }
    }


def nombre_herramienta(servidor: str, herramienta: str) -> str:
    """Nombre con el que el SDK entrega una herramienta MCP al hook."""
    return f"mcp__{servidor}__{herramienta}"


def _texto_no_vacio(valor) -> bool:
    return isinstance(valor, str) and bool(valor.strip())


def _entrada_invalida(campo: str, mensaje: str) -> Decision:
    return Decision.negar("ENTRADA_INVALIDA", mensaje, {"campo": campo})


# ---------------------------------------------------------------- decisiones (puras)


def decidir_registro(datos: dict, tool_input) -> Decision:
    """Regla 1: no se registra a un solicitante sin identidad verificada y vigente.

    No evalúa umbrales: registrar una solicitud no preaprobable es legítimo (se evalúa y se
    escala). Del modelo solo toma el identificador del solicitante.
    """
    id_solicitante = tool_input.get("id_solicitante") if isinstance(tool_input, dict) else None
    if not _texto_no_vacio(id_solicitante):
        return _entrada_invalida("id_solicitante", "Falta un id_solicitante válido.")
    solicitante = datos["solicitantes"].get(id_solicitante)
    if solicitante is None or not identidad_vigente(solicitante):
        return Decision.negar(
            "IDENTIDAD_NO_VERIFICADA",
            "El solicitante no tiene la identidad verificada.",
            {"id_solicitante": id_solicitante},
        )
    return Decision.permitir_llamada()


def decidir_preaprobacion(datos: dict, tool_input) -> Decision:
    """Reglas 1 y 2: solo se preaprueba una solicitud válida, vigente y dentro de la política.

    Orden: entrada, existencia, escalamiento, identidad, hallazgos y política. La política se
    recalcula con los datos guardados (`evaluar_solicitud_guardada`): ni la evaluación guardada
    ni lo que afirme el modelo cuentan. Del modelo solo se toma el id de la solicitud.
    """
    if not isinstance(tool_input, dict) or "id_solicitud" not in tool_input:
        return _entrada_invalida("id_solicitud", "Falta un id_solicitud válido.")
    if set(tool_input) != {"id_solicitud"}:
        return _entrada_invalida(
            "campos_adicionales", "preaprobar_credito solo admite el id_solicitud."
        )
    id_solicitud = tool_input["id_solicitud"]
    if not _texto_no_vacio(id_solicitud):
        return _entrada_invalida("id_solicitud", "Falta un id_solicitud válido.")

    detalles = {"id_solicitud": id_solicitud}
    solicitud = datos["solicitudes"].get(id_solicitud)
    if solicitud is None:
        return Decision.negar("SOLICITUD_NO_ENCONTRADA", "No existe esa solicitud.", detalles)
    if solicitud["estado"] == ESCALADA:
        return Decision.negar(
            "SOLICITUD_ESCALADA", "La solicitud ya fue escalada a un analista.", detalles
        )
    solicitante = datos["solicitantes"].get(solicitud["id_solicitante"])
    if solicitante is None or not identidad_vigente(solicitante):
        return Decision.negar(
            "IDENTIDAD_NO_VERIFICADA",
            "El solicitante de la solicitud no tiene la identidad verificada.",
            detalles | {"id_solicitante": solicitud["id_solicitante"]},
        )
    if solicitud["hallazgos"]:
        hallazgos = [
            {"tipo": h["tipo"], "mensaje": h["mensaje"], "campo": h["campo"]}
            for h in solicitud["hallazgos"]
        ]
        tipos = ", ".join(dict.fromkeys(h["tipo"] for h in hallazgos))
        return Decision.negar(
            "HALLAZGOS_DOCUMENTALES",
            f"La solicitud tiene hallazgos documentales ({tipos}).",
            detalles | {"hallazgos": hallazgos},
        )
    resultado = evaluar_solicitud_guardada(solicitud)
    if resultado.decision is not DecisionPolitica.PREAPROBABLE:
        causas = [
            {"regla": m.regla, "mensaje": m.mensaje, "valores": m.valores}
            for m in resultado.motivos
        ]
        reglas = ", ".join(dict.fromkeys(c["regla"] for c in causas))
        return Decision.negar(
            "NO_PREAPROBABLE",
            f"La solicitud no cumple las condiciones de preaprobación ({reglas}).",
            detalles | {"causas": causas},
        )
    return Decision.permitir_llamada()


# ---------------------------------------------------------------- callbacks del SDK

HookCallback = Callable[[dict, str | None, dict], Awaitable[dict]]


def _crear_hook(
    herramienta: str,
    decidir: Callable[[dict, object], Decision],
    almacen: AlmacenEstado,
    servidor: str,
    timeout_lectura: float,
    registro: RegistroNegaciones | None,
    ahora: str | None,
) -> HookCallback:
    nombre = nombre_herramienta(servidor, herramienta)

    async def hook(input_data: dict, _tool_use_id: str | None, _context: dict) -> dict:
        if input_data.get("tool_name") != nombre:
            return PERMITIR
        # Fail-closed (FR-008): ante cualquier duda, se niega.
        try:
            # Lectura en un hilo: el lock puede esperar y no debe bloquear el bucle del agente.
            datos = await anyio.to_thread.run_sync(partial(almacen.leer_existente, timeout_lectura))
            decision = decidir(datos, input_data.get("tool_input"))
        except ErrorCore:
            decision = Decision.negar("ESTADO_ILEGIBLE", "No se pudo leer el estado del core.")
        except Exception:  # noqa: BLE001 — FR-008: ningún error interno deja pasar la llamada
            registro_log.exception("Error inesperado en el hook de %s", herramienta)
            decision = Decision.negar("ERROR_INTERNO", "Error interno al comprobar la llamada.")
        if decision.permitir:
            return PERMITIR
        if registro is not None:
            registro.registrar(
                Negacion(
                    herramienta=herramienta,
                    codigo=decision.codigo,
                    mensaje=decision.mensaje,
                    accion=decision.accion,
                    detalles=decision.detalles,
                    momento=ahora or datetime.now(UTC).isoformat(),
                )
            )
        return salida_deny(decision)

    return hook


def crear_hook_registro(
    almacen: AlmacenEstado,
    registro: RegistroNegaciones | None = None,
    servidor: str = SERVIDOR_POR_DEFECTO,
    ahora: str | None = None,
    timeout_lectura: float = TIMEOUT_LECTURA,
) -> HookCallback:
    """Hook `PreToolUse` de `registrar_solicitud` (regla 1)."""
    return _crear_hook(
        "registrar_solicitud", decidir_registro, almacen, servidor, timeout_lectura, registro, ahora
    )


def crear_hook_preaprobacion(
    almacen: AlmacenEstado,
    registro: RegistroNegaciones | None = None,
    servidor: str = SERVIDOR_POR_DEFECTO,
    ahora: str | None = None,
    timeout_lectura: float = TIMEOUT_LECTURA,
) -> HookCallback:
    """Hook `PreToolUse` de `preaprobar_credito` (reglas 1 y 2)."""
    return _crear_hook(
        "preaprobar_credito",
        decidir_preaprobacion,
        almacen,
        servidor,
        timeout_lectura,
        registro,
        ahora,
    )


def crear_hooks(
    almacen: AlmacenEstado,
    registro: RegistroNegaciones | None = None,
    servidor: str = SERVIDOR_POR_DEFECTO,
    ahora: str | None = None,
    timeout_lectura: float = TIMEOUT_LECTURA,
) -> dict[str, list[HookMatcher]]:
    """Configuración lista para `ClaudeAgentOptions(hooks=...)` (FR-012).

    Un `HookMatcher` por herramienta, con su nombre completo exacto. `servidor` debe ser la
    clave con la que el agente registra el servidor MCP del core en `mcp_servers`.
    """
    opciones = {
        "registro": registro,
        "servidor": servidor,
        "ahora": ahora,
        "timeout_lectura": timeout_lectura,
    }
    return {
        "PreToolUse": [
            HookMatcher(
                matcher=nombre_herramienta(servidor, "registrar_solicitud"),
                hooks=[crear_hook_registro(almacen, **opciones)],
                timeout=TIMEOUT_HOOK,
            ),
            HookMatcher(
                matcher=nombre_herramienta(servidor, "preaprobar_credito"),
                hooks=[crear_hook_preaprobacion(almacen, **opciones)],
                timeout=TIMEOUT_HOOK,
            ),
        ]
    }
