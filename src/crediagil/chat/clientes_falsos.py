"""Soporte de los tests: un cliente del Agent SDK falso que emite mensajes reales del SDK.

Mismo patrón que `crediagil.agent.test_orquestador`. Cada `query` consume un guion: una lista de
mensajes del SDK, de `asyncio.Event` (el cliente espera a que se active, para simular un turno en
curso) o de funciones, síncronas o asíncronas (se ejecutan, para simular efectos como un hook).
"""

from __future__ import annotations

import asyncio
import inspect
import json

from claude_agent_sdk import (
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)

CORE = "mcp__crediagil-core__"


class ClienteFalso:
    def __init__(self, guion, opciones, falla_connect: Exception | None = None):
        self.opciones = opciones
        self._guion = list(guion)
        self._falla_connect = falla_connect
        self.consultas: list[str] = []
        self.conectado = False
        self.desconectado = False
        self._actual: list = []

    async def connect(self):
        if self._falla_connect is not None:
            raise self._falla_connect
        self.conectado = True

    async def query(self, prompt):
        self.consultas.append(prompt)
        accion = self._guion.pop(0) if self._guion else turno_simple("(sin guion)")
        if isinstance(accion, Exception):
            raise accion
        self._actual = accion

    async def receive_response(self):
        for elemento in self._actual:
            if isinstance(elemento, asyncio.Event):
                await elemento.wait()
            elif callable(elemento):
                efecto = elemento()
                if inspect.isawaitable(efecto):
                    await efecto
            else:
                yield elemento

    async def disconnect(self):
        self.desconectado = True


def fabrica(*guion, falla_connect: Exception | None = None):
    """`(crear, clientes)`: `crear` es la fábrica para `Agente`/`Sesion`; `clientes` los creados."""
    clientes: list[ClienteFalso] = []

    def crear(opciones):
        cliente = ClienteFalso(guion, opciones, falla_connect)
        clientes.append(cliente)
        return cliente

    return crear, clientes


def texto(contenido, stop="end_turn"):
    return AssistantMessage(content=[TextBlock(text=contenido)], model="m", stop_reason=stop)


def uso(id_, nombre, entrada, padre=None):
    """Llamada a una herramienta; con `padre`, la hace un subagente (cuelga de esa delegación)."""
    return AssistantMessage(
        content=[ToolUseBlock(id=id_, name=nombre, input=entrada)],
        model="m",
        stop_reason="tool_use",
        parent_tool_use_id=padre,
    )


def respuesta_herramienta(id_, salida, es_error=False):
    bloque = ToolResultBlock(
        tool_use_id=id_,
        content=[{"type": "text", "text": json.dumps(salida)}],
        is_error=es_error,
    )
    return UserMessage(content=[bloque])


def resultado(stop="end_turn", terminal="completed", es_error=False, texto_final="ok", **extra):
    return ResultMessage(
        subtype="success",
        duration_ms=1,
        duration_api_ms=1,
        is_error=es_error,
        num_turns=1,
        session_id="s",
        stop_reason=stop,
        terminal_reason=terminal,
        result=texto_final,
        total_cost_usd=0.01,
        **extra,
    )


def turno_simple(respuesta: str) -> list:
    """Un turno sin herramientas que termina bien."""
    return [texto(respuesta), resultado()]
