"""Traza y avisos de un turno, derivados de los mensajes reales del SDK (spec 007, FR-011).

Nada se deduce del texto del modelo: los avisos salen de los resultados de las herramientas y de
las negaciones de los hooks. La entrada y la salida de cada evento pasan por `redactar`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)

from crediagil.agent.canal import PedidoInformacion
from crediagil.agent.delegacion import HERRAMIENTA_DELEGACION
from crediagil.agent.negaciones import Negacion
from crediagil.agent.parada import Parada
from crediagil.config import redactar

PREFIJOS_SERVIDOR = ("mcp__crediagil-core__", "mcp__canal__")


@dataclass
class EventoTraza:
    tipo: str  # "herramienta" | "delegacion" | "parada"
    nombre: str
    entrada: dict = field(default_factory=dict)
    salida: Any = None
    es_error: bool = False
    de_subagente: bool = False
    stop_reason: str | None = None


@dataclass(frozen=True)
class Aviso:
    tipo: str  # credito_preaprobado | informacion_solicitada | escalamiento | bloqueo_regla
    contenido: dict = field(default_factory=dict)


@dataclass
class ResultadoTurno:
    respuesta: str
    avisos: list[Aviso]
    traza: list[EventoTraza]
    parada: Parada
    razon_parada: str | None = None
    negaciones: list[Negacion] = field(default_factory=list)
    pedidos_informacion: list[PedidoInformacion] = field(default_factory=list)
    costo_usd: float | None = None
    error: str | None = None


def _redactar_valor(valor: Any) -> Any:
    if isinstance(valor, str):
        return redactar(valor)
    if isinstance(valor, dict):
        return {k: _redactar_valor(v) for k, v in valor.items()}
    if isinstance(valor, list):
        return [_redactar_valor(v) for v in valor]
    return valor


def _sin_prefijo(nombre: str) -> str:
    for prefijo in PREFIJOS_SERVIDOR:
        if nombre.startswith(prefijo):
            return nombre[len(prefijo) :]
    return nombre


def _salida(contenido: str | list[dict[str, Any]] | None) -> Any:
    """Texto del resultado de una herramienta; si es JSON, el objeto."""
    if isinstance(contenido, list):
        texto = "\n".join(
            bloque.get("text", "") for bloque in contenido if isinstance(bloque, dict)
        )
    else:
        texto = contenido
    if texto is None:
        return None
    try:
        return json.loads(texto)
    except ValueError:
        return texto


class TrazaTurno:
    """Acumula los mensajes de un turno y los traduce a eventos, respuesta y avisos."""

    def __init__(self) -> None:
        self.eventos: list[EventoTraza] = []
        self.hubo_error_del_asistente = False
        self._por_id: dict[str, EventoTraza] = {}
        self._texto: list[str] = []

    def procesar(self, mensaje: object) -> None:
        if isinstance(mensaje, AssistantMessage):
            self._asistente(mensaje)
        elif isinstance(mensaje, UserMessage):
            self._usuario(mensaje)

    def _asistente(self, mensaje: AssistantMessage) -> None:
        de_subagente = mensaje.parent_tool_use_id is not None
        if mensaje.error is not None:
            self.hubo_error_del_asistente = True
        for bloque in mensaje.content:
            if isinstance(bloque, ToolUseBlock):
                evento = EventoTraza(
                    tipo="delegacion" if bloque.name == HERRAMIENTA_DELEGACION else "herramienta",
                    nombre=_sin_prefijo(bloque.name),
                    entrada=_redactar_valor(bloque.input),
                    de_subagente=de_subagente,
                    stop_reason=mensaje.stop_reason,
                )
                self.eventos.append(evento)
                self._por_id[bloque.id] = evento
                if not de_subagente:
                    self._texto.clear()  # la respuesta es lo que dice tras la última herramienta
            elif isinstance(bloque, TextBlock) and not de_subagente:
                self._texto.append(bloque.text)

    def _usuario(self, mensaje: UserMessage) -> None:
        if not isinstance(mensaje.content, list):
            return
        for bloque in mensaje.content:
            if isinstance(bloque, ToolResultBlock):
                evento = self._por_id.get(bloque.tool_use_id)
                if evento is not None:
                    evento.salida = _redactar_valor(_salida(bloque.content))
                    evento.es_error = bool(bloque.is_error)

    @property
    def respuesta(self) -> str:
        return redactar("".join(self._texto).strip())

    def agregar(self, evento: EventoTraza) -> None:
        self.eventos.append(evento)


def _ok(evento: EventoTraza) -> bool:
    return (
        not evento.es_error and isinstance(evento.salida, dict) and evento.salida.get("ok") is True
    )


def derivar_avisos(eventos: list[EventoTraza], negaciones: list[Negacion]) -> list[Aviso]:
    """Avisos a partir de resultados reales de herramientas, nunca del texto del modelo."""
    avisos: list[Aviso] = []
    for evento in eventos:
        if evento.de_subagente or evento.tipo != "herramienta":
            continue
        if evento.nombre == "preaprobar_credito" and _ok(evento):
            claves = ("id_solicitud", "monto", "plazo_meses", "cuota", "tasa_mensual")
            avisos.append(Aviso("credito_preaprobado", {k: evento.salida.get(k) for k in claves}))
        elif evento.nombre == "solicitar_informacion" and not evento.es_error:
            avisos.append(
                Aviso(
                    "informacion_solicitada",
                    {"datos": evento.entrada.get("datos"), "motivo": evento.entrada.get("motivo")},
                )
            )
        elif evento.nombre == "escalar_a_analista" and _ok(evento):
            resumen = evento.entrada.get("resumen")
            causa = resumen.get("causa") if isinstance(resumen, dict) else None
            avisos.append(
                Aviso(
                    "escalamiento",
                    {"id_escalamiento": evento.salida.get("id_escalamiento"), "causa": causa},
                )
            )
    for negacion in negaciones:
        avisos.append(
            Aviso(
                "bloqueo_regla",
                {
                    "herramienta": negacion.herramienta,
                    "codigo": negacion.codigo,
                    "mensaje": negacion.mensaje,
                },
            )
        )
    return avisos
