"""Sesión de la interfaz: un agente abierto entre peticiones HTTP y un turno a la vez (spec 008).

Verificado en research R3: el `Agente` se puede abrir, usar en turnos y cerrar desde tareas
distintas, así que no hace falta una tarea de fondo dueña del agente. El cerrojo (R4) impide que
dos peticiones mezclen el contexto del agente; el que llega con otro turno en marcha recibe
`TurnoEnCurso`, no espera.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace

import anyio
from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

from crediagil.agent.documentos import DocumentoAdjunto
from crediagil.agent.opciones import ConfigAgente
from crediagil.agent.orquestador import Agente, ClienteSDK
from crediagil.agent.traza import ResultadoTurno
from crediagil.config import redactar
from crediagil.mcp_server.errores import ErrorCore
from crediagil.mcp_server.estado import AlmacenEstado

registro_log = logging.getLogger("crediagil.chat")


FALLA_MAXIMA = 20
VARIABLE_FALLAS = "CREDIAGIL_MCP_FALLAS_N"


class TurnoEnCurso(Exception):
    """Hay un turno, una conversación nueva o un reinicio en marcha."""


class FallaInvalida(ValueError):
    """El número de llamadas que fallan debe ser un entero de 0 a 20."""


def _validar_falla(valor: object) -> int:
    # `bool` es un `int` en Python: se rechaza a propósito (`true` no es un número de llamadas).
    if isinstance(valor, bool) or not isinstance(valor, int) or not 0 <= valor <= FALLA_MAXIMA:
        raise FallaInvalida(
            f"El número de llamadas que fallan debe ser un entero de 0 a {FALLA_MAXIMA}."
        )
    return valor


@dataclass(frozen=True)
class TurnoHecho:
    id_turno: int
    resultado: ResultadoTurno


class Sesion:
    def __init__(
        self,
        config: ConfigAgente | None = None,
        cliente_factory: Callable[[ClaudeAgentOptions], ClienteSDK] = ClaudeSDKClient,
    ) -> None:
        self._config = config if config is not None else ConfigAgente()
        self._cliente_factory = cliente_factory
        self._cerrojo = asyncio.Lock()
        self._agente: Agente | None = None
        self._conversacion_id: str | None = None
        self._turnos = 0
        self._falla = 0

    def estado(self) -> dict:
        return {
            "conversacion": {
                "id": self._conversacion_id,
                "turnos": self._turnos,
                "activa": self._agente is not None,
            },
            "falla_simulada": {"llamadas": self._falla},
        }

    def estado_core_legible(self) -> bool:
        """`True` si el estado del core no existe todavía (se creará) o se puede leer."""
        almacen = AlmacenEstado(self._config.ruta_estado)
        if not almacen.ruta.exists():
            return True
        try:
            almacen.leer_existente()
        except ErrorCore:
            return False
        return True

    def _config_de_la_conversacion(self) -> ConfigAgente:
        """La configuración base, con la falla transitoria simulada en el entorno del core."""
        if self._falla == 0:
            return self._config
        entorno = {**self._config.entorno_core, VARIABLE_FALLAS: str(self._falla)}
        return replace(self._config, entorno_core=entorno)

    def _tomar(self) -> None:
        # Sin `await` entre la comprobación y la toma: en asyncio es atómico.
        if self._cerrojo.locked():
            raise TurnoEnCurso("Hay un turno en curso.")

    async def turno(self, mensaje: str, documentos: Sequence[DocumentoAdjunto] = ()) -> TurnoHecho:
        self._tomar()
        async with self._cerrojo:
            if self._agente is None:
                agente = Agente(
                    self._config_de_la_conversacion(), cliente_factory=self._cliente_factory
                )
                await agente.__aenter__()  # ConfiguracionError o fallo de conexión: se propagan
                self._agente = agente
            if self._conversacion_id is None:
                self._conversacion_id = _nuevo_id()
            resultado = await self._agente.turno(mensaje, documentos)
            self._turnos += 1
            return TurnoHecho(self._turnos, resultado)

    async def nueva(self, falla_llamadas: object = 0) -> None:
        """Cierra el agente y empieza una conversación vacía; el siguiente turno abre otro.

        `falla_llamadas` simula esa cantidad de fallas transitorias del core en la conversación
        nueva (0 las desactiva). Un valor inválido se rechaza sin cambiar nada.
        """
        falla = _validar_falla(falla_llamadas)
        self._tomar()
        async with self._cerrojo:
            await self._cerrar_agente()
            self._conversacion_id = _nuevo_id()
            self._turnos = 0
            self._falla = falla

    async def reiniciar_datos(self) -> None:
        """Devuelve el core a la semilla y empieza una conversación nueva sin falla simulada."""
        self._tomar()
        async with self._cerrojo:
            await self._cerrar_agente()  # primero el core hijo, que podría estar leyendo el estado
            almacen = AlmacenEstado(self._config.ruta_estado)
            await anyio.to_thread.run_sync(almacen.reiniciar)
            self._conversacion_id = _nuevo_id()
            self._turnos = 0
            self._falla = 0

    async def cerrar(self) -> None:
        """Cierra el agente al apagar la aplicación. Idempotente."""
        async with self._cerrojo:
            await self._cerrar_agente()

    async def _cerrar_agente(self) -> None:
        agente, self._agente = self._agente, None
        if agente is None:
            return
        try:
            await agente.__aexit__(None, None, None)
        except Exception as exc:  # noqa: BLE001 — cerrar no debe impedir seguir
            registro_log.warning("No se pudo cerrar el agente: %s", redactar(str(exc)))


def _nuevo_id() -> str:
    return uuid.uuid4().hex[:8]
