"""Tests del orquestador con un cliente falso que emite mensajes reales del SDK (spec 007)."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest
from claude_agent_sdk import (
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)

from crediagil.agent.canal import PedidoInformacion
from crediagil.agent.documentos import DocumentoAdjunto
from crediagil.agent.negaciones import Negacion, RegistroNegaciones
from crediagil.agent.opciones import ConfigAgente
from crediagil.agent.orquestador import Agente
from crediagil.agent.parada import Parada
from crediagil.config import ConfiguracionError
from crediagil.mcp_server.estado import AlmacenEstado

pytestmark = pytest.mark.anyio

CORE = "mcp__crediagil-core__"
CLAVE = "sk-ficticia-orquestador"


@pytest.fixture(autouse=True)
def clave(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", CLAVE)


@pytest.fixture
def config(tmp_path):
    return ConfigAgente(ruta_estado=tmp_path / "estado.json", max_continuaciones=2)


class ClienteFalso:
    """Reproduce un guion: una lista de mensajes (o funciones) por cada `query`."""

    def __init__(self, guion, opciones):
        self.opciones = opciones
        self._guion = list(guion)
        self.consultas: list[str] = []
        self.conectado = False
        self.desconectado = False
        self._actual: list = []

    async def connect(self):
        self.conectado = True

    async def query(self, prompt):
        self.consultas.append(prompt)
        accion = self._guion.pop(0)
        if isinstance(accion, Exception):
            raise accion
        self._actual = accion

    async def receive_response(self):
        for elemento in self._actual:
            if callable(elemento):
                elemento()
            else:
                yield elemento

    async def disconnect(self):
        self.desconectado = True


def fabrica(*guion):
    clientes: list[ClienteFalso] = []

    def crear(opciones):
        cliente = ClienteFalso(guion, opciones)
        clientes.append(cliente)
        return cliente

    return crear, clientes


def texto(contenido, stop="end_turn"):
    return AssistantMessage(content=[TextBlock(text=contenido)], model="m", stop_reason=stop)


def uso(id_, nombre, entrada):
    return AssistantMessage(
        content=[ToolUseBlock(id=id_, name=nombre, input=entrada)],
        model="m",
        stop_reason="tool_use",
    )


def respuesta_herramienta(id_, salida):
    bloque = ToolResultBlock(
        tool_use_id=id_, content=[{"type": "text", "text": json.dumps(salida)}], is_error=False
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


async def test_fin_de_turno_con_herramientas(config):
    crear, _ = fabrica(
        [
            uso("t1", CORE + "preaprobar_credito", {"id_solicitud": "SLC-1"}),
            respuesta_herramienta(
                "t1",
                {
                    "ok": True,
                    "id_solicitud": "SLC-1",
                    "monto": 1,
                    "plazo_meses": 12,
                    "cuota": 2,
                    "tasa_mensual": "x",
                },
            ),
            texto("Tu crédito quedó preaprobado."),
            resultado(),
        ]
    )
    async with Agente(config, cliente_factory=crear) as agente:
        r = await agente.turno("Quiero un crédito")
    assert r.parada is Parada.FIN_DE_TURNO
    assert r.razon_parada == "end_turn"
    assert r.respuesta == "Tu crédito quedó preaprobado."
    assert [e.nombre for e in r.traza] == ["preaprobar_credito"]
    assert [a.tipo for a in r.avisos] == ["credito_preaprobado"]
    assert r.costo_usd == 0.01
    assert r.error is None


async def test_truncada_continua_y_termina(config):
    crear, clientes = fabrica(
        [texto("Tu trámi", stop="max_tokens"), resultado(stop="max_tokens")],
        [texto("te sigue en curso."), resultado()],
    )
    async with Agente(config, cliente_factory=crear) as agente:
        r = await agente.turno("hola")
    assert clientes[0].consultas == ["hola", "Continúa."]
    assert r.parada is Parada.FIN_DE_TURNO
    assert r.respuesta == "Tu trámite sigue en curso."


async def test_truncada_persistente_escala_por_codigo(config):
    truncado = [texto("x", stop="max_tokens"), resultado(stop="max_tokens")]
    crear, clientes = fabrica(truncado, truncado, truncado)
    async with Agente(config, cliente_factory=crear) as agente:
        r = await agente.turno("hola")
    assert clientes[0].consultas == ["hola", "Continúa.", "Continúa."]
    assert r.parada is Parada.TRUNCADA
    assert [a.tipo for a in r.avisos] == ["escalamiento"]
    assert len(AlmacenEstado(config.ruta_estado).leer()["escalamientos"]) == 1


@pytest.mark.parametrize(
    ("final", "esperada"),
    [
        (resultado(stop="refusal"), Parada.RECHAZO),
        (resultado(stop="end_turn", terminal="max_turns"), Parada.TOPE),
        (resultado(stop="tool_use"), Parada.DESCONOCIDA),
        (resultado(stop=None), Parada.DESCONOCIDA),
    ],
)
async def test_incidentes_escalan_por_codigo(config, final, esperada):
    crear, _ = fabrica([texto("algo"), final])
    async with Agente(config, cliente_factory=crear) as agente:
        r = await agente.turno("hola")
    assert r.parada is esperada
    assert r.error is None
    assert [a.tipo for a in r.avisos] == ["escalamiento"]
    assert r.avisos[0].contenido["causa"] == "otro"
    (escalamiento,) = AlmacenEstado(config.ruta_estado).leer()["escalamientos"].values()
    resumen = escalamiento["resumen"]
    assert resumen["solicitante"] == "sin identificar"
    assert resumen["causa"] == "otro"
    assert esperada.value in resumen["detalle"]


async def test_incidente_con_solicitante_conocido(config):
    crear, _ = fabrica(
        [
            uso("v", CORE + "verificar_identidad", {"id_solicitante": "SOL-0001"}),
            respuesta_herramienta("v", {"ok": True}),
            resultado(stop="refusal"),
        ]
    )
    async with Agente(config, cliente_factory=crear) as agente:
        await agente.turno("hola")
    (escalamiento,) = AlmacenEstado(config.ruta_estado).leer()["escalamientos"].values()
    assert escalamiento["resumen"]["solicitante"] == "SOL-0001"


async def test_error_de_api_sin_clave_ni_respuesta_inventada(config):
    crear, _ = fabrica([texto("a medias"), resultado(es_error=True, api_error_status=529)])
    async with Agente(config, cliente_factory=crear) as agente:
        r = await agente.turno("hola")
    assert r.parada is Parada.ERROR_API
    assert r.respuesta == ""
    assert "529" in r.error
    assert r.avisos == []


async def test_excepcion_del_cliente_se_redacta(config, caplog):
    caplog.set_level(logging.DEBUG)
    crear, _ = fabrica(RuntimeError(f"401 con la clave {CLAVE}"))
    async with Agente(config, cliente_factory=crear) as agente:
        r = await agente.turno("hola")
    assert r.parada is Parada.ERROR_API
    assert r.respuesta == ""
    assert CLAVE not in r.error
    assert "[REDACTADO]" in r.error
    assert CLAVE not in caplog.text


async def test_error_del_asistente_es_error_de_api(config):
    mensaje = AssistantMessage(content=[], model="m", error="rate_limit")
    crear, _ = fabrica([mensaje, resultado()])
    async with Agente(config, cliente_factory=crear) as agente:
        r = await agente.turno("hola")
    assert r.parada is Parada.ERROR_API


async def test_adjuntos_con_ids_y_omitidos(config):
    crear, clientes = fabrica([texto("a"), resultado()], [texto("b"), resultado()])
    async with Agente(config, cliente_factory=crear) as agente:
        await agente.turno(
            "mira",
            [DocumentoAdjunto("a.txt", "contenido a"), DocumentoAdjunto("vacio.txt", " ")],
        )
        await agente.turno("otro", [DocumentoAdjunto("b.txt", "contenido b")])
    primera, segunda = clientes[0].consultas
    assert '<documento id="DOC-1" nombre="a.txt">contenido a</documento>' in primera
    assert "vacio.txt" in primera and "reenvíe" in primera
    assert 'id="DOC-2"' in segunda


async def test_el_hook_de_delegacion_ve_los_documentos_de_todos_los_turnos(config):
    crear, clientes = fabrica([texto("a"), resultado()], [texto("b"), resultado()])
    async with Agente(config, cliente_factory=crear) as agente:
        await agente.turno("uno", [DocumentoAdjunto("a.txt", "texto a")])
        await agente.turno("dos", [DocumentoAdjunto("b.txt", "texto b")])
        hook = clientes[0].opciones.hooks["PreToolUse"][2].hooks[0]
        evento = {
            "tool_name": "Agent",
            "tool_input": {
                "subagent_type": "extractor-documentos",
                "prompt": "DOC-1 a.txt texto a",
            },
        }
        assert await hook(evento, "id", {}) == {}
        evento["tool_input"]["prompt"] = "DOC-2 b.txt texto b"
        assert await hook(evento, "id", {}) == {}


async def test_negaciones_del_turno_son_solo_las_nuevas(config):
    registro = RegistroNegaciones()
    registro.registrar(Negacion("registrar_solicitud", "ENTRADA_INVALIDA", "vieja", "a"))
    nueva = Negacion("preaprobar_credito", "IDENTIDAD_NO_VERIFICADA", "nueva", "a")
    crear, _ = fabrica([lambda: registro.registrar(nueva), texto("no se pudo"), resultado()])
    async with Agente(config, registro, cliente_factory=crear) as agente:
        r = await agente.turno("hola")
    assert r.negaciones == [nueva]
    assert [a.tipo for a in r.avisos] == ["bloqueo_regla"]


async def test_pedidos_de_informacion_del_turno(config):
    anterior = PedidoInformacion(("fecha",), "antes")
    nuevo = PedidoInformacion(("salario",), "falta")
    agentes = []
    crear, _ = fabrica(
        [lambda: agentes[0]._pedidos.append(nuevo), texto("ok"), resultado()],
    )
    async with Agente(config, cliente_factory=crear) as agente:
        agentes.append(agente)
        agente._pedidos.append(anterior)  # de un turno previo
        r = await agente.turno("hola")
    assert r.pedidos_informacion == [nuevo]


async def test_la_clave_no_aparece_en_ninguna_salida(config, caplog):
    caplog.set_level(logging.DEBUG)
    crear, _ = fabrica(
        [
            uso("t", CORE + "buscar_solicitante", {"documento": f"x {CLAVE}"}),
            respuesta_herramienta("t", {"ok": True, "eco": CLAVE}),
            texto(f"tu clave es {CLAVE}"),
            resultado(texto_final=f"tu clave es {CLAVE}"),
        ]
    )
    async with Agente(config, cliente_factory=crear) as agente:
        r = await agente.turno("hola")
    volcado = json.dumps(
        [r.respuesta, [vars(e) for e in r.traza], r.error, caplog.text], default=str
    )
    assert CLAVE not in volcado


async def test_conecta_y_al_salir_desconecta_y_borra_el_directorio(config):
    crear, clientes = fabrica()
    async with Agente(config, cliente_factory=crear):
        cliente = clientes[0]
        assert cliente.conectado
        cwd = Path(cliente.opciones.cwd)
        assert cwd.exists()
    assert cliente.desconectado
    assert not cwd.exists()


async def test_limpia_tambien_si_hubo_excepcion(config):
    crear, clientes = fabrica()
    cwd = None
    with pytest.raises(ValueError):
        async with Agente(config, cliente_factory=crear):
            cwd = Path(clientes[0].opciones.cwd)
            raise ValueError("falla del llamador")
    assert clientes[0].desconectado
    assert not cwd.exists()


async def test_sin_clave_no_conecta(config, monkeypatch, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    monkeypatch.chdir(tmp_path)
    crear, clientes = fabrica()
    with pytest.raises(ConfiguracionError):
        async with Agente(config, cliente_factory=crear):
            pass
    assert clientes == []


async def test_la_decision_no_depende_del_texto(config):
    crear, _ = fabrica([texto("listo"), resultado(stop="refusal", texto_final="listo")])
    async with Agente(config, cliente_factory=crear) as agente:
        r = await agente.turno("hola")
    assert r.parada is Parada.RECHAZO


async def test_turno_fuera_de_la_conversacion_falla(config):
    crear, _ = fabrica()
    with pytest.raises(RuntimeError):
        await Agente(config, cliente_factory=crear).turno("hola")
