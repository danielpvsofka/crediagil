"""Orquestador del agente de originación sobre el Claude Agent SDK (spec 007).

Una conversación es un `ClaudeSDKClient`; el CLI ejecuta el bucle de herramientas. Este módulo
solo compone: envía el turno, traduce los mensajes, clasifica la razón de parada y, ante un
incidente (rechazo, tope, razón desconocida, truncado persistente), escala por código. Nada se
decide con el texto del modelo (Principio II).
"""

from __future__ import annotations

import logging
import shutil
import tempfile
from collections.abc import AsyncIterator, Callable, Sequence
from pathlib import Path
from typing import Any, Protocol, Self

import anyio
from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, ResultMessage

from crediagil.agent.canal import crear_canal
from crediagil.agent.documentos import DocumentoAdjunto, asignar_ids, renderizar_mensaje
from crediagil.agent.negaciones import RegistroNegaciones
from crediagil.agent.opciones import ConfigAgente, construir_opciones
from crediagil.agent.parada import Parada, clasificar_parada
from crediagil.agent.traza import EventoTraza, ResultadoTurno, TrazaTurno, derivar_avisos
from crediagil.config import cargar_entorno, obtener_api_key, redactar
from crediagil.mcp_server import escalamiento
from crediagil.mcp_server.errores import ErrorCore
from crediagil.mcp_server.estado import AlmacenEstado

registro_log = logging.getLogger("crediagil.agent")

CONTINUAR = "Continúa."
SIN_IDENTIFICAR = "sin identificar"
RESPUESTA_ESCALADO = "Pasé tu caso a un analista, que lo continuará contigo."
INCIDENTES = {Parada.TRUNCADA, Parada.RECHAZO, Parada.TOPE, Parada.DESCONOCIDA}


class ClienteSDK(Protocol):
    async def connect(self) -> None: ...
    async def query(self, prompt: str) -> None: ...
    def receive_response(self) -> AsyncIterator[Any]: ...
    async def disconnect(self) -> None: ...


class Agente:
    """Conversación con el agente: `async with Agente(config) as agente: await agente.turno(...)`."""

    def __init__(
        self,
        config: ConfigAgente,
        registro: RegistroNegaciones | None = None,
        cliente_factory: Callable[[ClaudeAgentOptions], ClienteSDK] = ClaudeSDKClient,
    ) -> None:
        self._config = config
        self._registro = registro if registro is not None else RegistroNegaciones()
        self._cliente_factory = cliente_factory
        self._almacen = AlmacenEstado(config.ruta_estado)
        self._documentos: dict[str, DocumentoAdjunto] = {}
        self._pedidos: list = []
        self._cliente: ClienteSDK | None = None
        self._cwd: Path | None = None

    async def __aenter__(self) -> Self:
        cargar_entorno()
        obtener_api_key()  # falla pronto y sin imprimir ningún valor
        self._cwd = Path(tempfile.mkdtemp(prefix="crediagil-agente-"))
        try:
            canal, self._pedidos = crear_canal()
            opciones = construir_opciones(
                self._config, self._registro, canal, self._documentos, self._almacen, self._cwd
            )
            self._cliente = self._cliente_factory(opciones)
            await self._cliente.connect()
        except BaseException:
            self._limpiar()
            raise
        return self

    async def __aexit__(self, *excepcion: object) -> None:
        try:
            if self._cliente is not None:
                await self._cliente.disconnect()
        except Exception as exc:  # noqa: BLE001 — cerrar no debe ocultar la excepción original
            registro_log.warning("No se pudo desconectar el cliente: %s", redactar(str(exc)))
        finally:
            self._cliente = None
            self._limpiar()

    def _limpiar(self) -> None:
        if self._cwd is not None:
            shutil.rmtree(self._cwd, ignore_errors=True)
            self._cwd = None

    async def turno(
        self, mensaje: str, documentos: Sequence[DocumentoAdjunto] = ()
    ) -> ResultadoTurno:
        if self._cliente is None:
            raise RuntimeError("El agente no está conectado: úsalo con `async with`.")

        con_id, omitidos = asignar_ids(documentos, ya_asignados=len(self._documentos))
        self._documentos.update({d.documento_id: d for d in con_id})
        texto = renderizar_mensaje(mensaje, con_id)
        for omitido in omitidos:
            texto += (
                f'\n\n[El adjunto "{omitido.nombre}" no trae texto legible: '
                "pide al solicitante que lo reenvíe.]"
            )

        negaciones_previas = len(self._registro.listar())
        pedidos_previos = len(self._pedidos)
        traza = TrazaTurno()
        resultado: ResultMessage | None = None
        continuaciones = 0
        prompt = texto
        try:
            while True:
                await self._cliente.query(prompt)
                resultado = None
                async for mensaje_sdk in self._cliente.receive_response():
                    traza.procesar(mensaje_sdk)
                    if isinstance(mensaje_sdk, ResultMessage):
                        resultado = mensaje_sdk
                parada = (
                    clasificar_parada(resultado, traza.hubo_error_del_asistente)
                    if resultado is not None
                    else Parada.DESCONOCIDA
                )
                if parada is Parada.TRUNCADA and continuaciones < self._config.max_continuaciones:
                    continuaciones += 1
                    prompt = CONTINUAR
                    continue
                break
        except Exception as exc:  # noqa: BLE001 — cualquier falla del SDK se devuelve sin la clave
            error = redactar(str(exc)) or exc.__class__.__name__
            registro_log.error("Falló el turno del agente: %s", error)
            return self._resultado(
                traza,
                Parada.ERROR_API,
                None,
                resultado,
                negaciones_previas,
                pedidos_previos,
                respuesta="",
                error=f"No se pudo completar el turno: {error}",
            )

        razon = resultado.stop_reason if resultado is not None else None
        if parada is Parada.ERROR_API:
            return self._resultado(
                traza,
                parada,
                razon,
                resultado,
                negaciones_previas,
                pedidos_previos,
                respuesta="",
                error=self._mensaje_error_api(resultado),
            )
        if parada in INCIDENTES:
            error = await self._escalar_incidente(traza, parada, resultado)
            return self._resultado(
                traza,
                parada,
                razon,
                resultado,
                negaciones_previas,
                pedidos_previos,
                respuesta="" if error else RESPUESTA_ESCALADO,
                error=error,
            )
        respuesta = traza.respuesta or redactar((resultado.result or "").strip())
        return self._resultado(
            traza,
            parada,
            razon,
            resultado,
            negaciones_previas,
            pedidos_previos,
            respuesta=respuesta,
        )

    def _resultado(
        self,
        traza: TrazaTurno,
        parada: Parada,
        razon: str | None,
        resultado: ResultMessage | None,
        negaciones_previas: int,
        pedidos_previos: int,
        respuesta: str,
        error: str | None = None,
    ) -> ResultadoTurno:
        negaciones = self._registro.listar()[negaciones_previas:]
        return ResultadoTurno(
            respuesta=respuesta,
            avisos=derivar_avisos(traza.eventos, negaciones),
            traza=traza.eventos,
            parada=parada,
            razon_parada=razon,
            negaciones=negaciones,
            pedidos_informacion=self._pedidos[pedidos_previos:],
            costo_usd=resultado.total_cost_usd if resultado is not None else None,
            error=error,
        )

    @staticmethod
    def _mensaje_error_api(resultado: ResultMessage | None) -> str:
        if resultado is None:
            return "Error del servicio del modelo."
        detalle = redactar("; ".join(resultado.errors or [])) if resultado.errors else ""
        estado = f" (HTTP {resultado.api_error_status})" if resultado.api_error_status else ""
        return f"Error del servicio del modelo{estado}." + (f" {detalle}" if detalle else "")

    async def _escalar_incidente(
        self, traza: TrazaTurno, parada: Parada, resultado: ResultMessage | None
    ) -> str | None:
        """Escala por código un incidente del ciclo; devuelve el error si no se pudo escalar."""
        solicitante = next(
            (
                e.entrada["id_solicitante"]
                for e in reversed(traza.eventos)
                if isinstance(e.entrada.get("id_solicitante"), str)
            ),
            SIN_IDENTIFICAR,
        )
        razon = resultado.stop_reason if resultado is not None else None
        terminal = resultado.terminal_reason if resultado is not None else None
        resumen = {
            "solicitante": solicitante,
            "monto": None,
            "plazo": None,
            "datos": [],
            "discrepancias": [],
            "causa": "otro",
            "detalle": (
                f"Incidente del agente: el turno terminó con la razón {parada.value} "
                f"(stop_reason={razon}, terminal_reason={terminal})."
            ),
            "accion_recomendada": "Revisar la conversación y continuar el caso con el solicitante.",
        }
        try:
            salida = await anyio.to_thread.run_sync(
                escalamiento.escalar_a_analista, self._almacen, resumen
            )
        except ErrorCore as exc:
            registro_log.error("No se pudo escalar el incidente: %s", exc.codigo)
            return f"No se pudo escalar el incidente: {exc.codigo}"
        traza.agregar(
            EventoTraza(
                tipo="herramienta",
                nombre="escalar_a_analista",
                entrada={"resumen": resumen},
                salida={"ok": True, **salida},
            )
        )
        return None
