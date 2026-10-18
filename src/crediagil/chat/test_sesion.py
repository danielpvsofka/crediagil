"""Tests de la sesión del chat (spec 008, research R3-R4)."""

from __future__ import annotations

import asyncio

import pytest

from crediagil.agent.opciones import ConfigAgente
from crediagil.agent.parada import Parada
from crediagil.chat.clientes_falsos import fabrica, resultado, texto, turno_simple
from crediagil.chat.sesion import FallaInvalida, Sesion, TurnoEnCurso
from crediagil.config import ConfiguracionError
from crediagil.mcp_server.estado import AlmacenEstado, estado_semilla

pytestmark = pytest.mark.anyio


@pytest.fixture
def config(tmp_path):
    return ConfigAgente(ruta_estado=tmp_path / "estado.json")


async def _esperar_consulta(clientes):
    """Cede el control hasta que el cliente falso haya recibido la consulta del turno."""
    for _ in range(200):
        if clientes and clientes[0].consultas:
            return
        await asyncio.sleep(0.005)
    raise AssertionError("el turno no llegó al cliente")


async def test_el_primer_turno_abre_el_agente(config):
    crear, clientes = fabrica(turno_simple("Hola"))
    sesion = Sesion(config, crear)
    assert sesion.estado()["conversacion"]["activa"] is False
    assert clientes == []

    hecho = await sesion.turno("hola")

    assert hecho.id_turno == 1
    assert hecho.resultado.respuesta == "Hola"
    estado = sesion.estado()["conversacion"]
    assert estado["activa"] is True
    assert estado["turnos"] == 1
    assert isinstance(estado["id"], str) and estado["id"]
    await sesion.cerrar()


async def test_dos_turnos_usan_el_mismo_agente(config):
    crear, clientes = fabrica(turno_simple("uno"), turno_simple("dos"))
    sesion = Sesion(config, crear)

    primero = await sesion.turno("a")
    segundo = await sesion.turno("b")

    assert len(clientes) == 1
    assert clientes[0].consultas == ["a", "b"]
    assert (primero.id_turno, segundo.id_turno) == (1, 2)
    assert sesion.estado()["conversacion"]["turnos"] == 2
    await sesion.cerrar()


async def test_nueva_cierra_el_agente_y_no_abre_otro_hasta_el_siguiente_turno(config):
    crear, clientes = fabrica(turno_simple("uno"))
    sesion = Sesion(config, crear)
    await sesion.turno("a")
    antes = sesion.estado()["conversacion"]["id"]

    await sesion.nueva()

    assert clientes[0].desconectado is True
    despues = sesion.estado()["conversacion"]
    assert despues["turnos"] == 0
    assert despues["activa"] is False
    assert despues["id"] != antes
    assert len(clientes) == 1

    hecho = await sesion.turno("b")

    assert len(clientes) == 2
    assert hecho.id_turno == 1
    await sesion.cerrar()


async def test_con_un_turno_en_curso_se_rechaza_todo_lo_demas(config):
    espera = asyncio.Event()
    crear, clientes = fabrica([espera, *turno_simple("a")], turno_simple("b"))
    sesion = Sesion(config, crear)

    en_curso = asyncio.create_task(sesion.turno("a"))
    await _esperar_consulta(clientes)

    with pytest.raises(TurnoEnCurso):
        await sesion.turno("otro")
    with pytest.raises(TurnoEnCurso):
        await sesion.nueva()
    assert clientes[0].desconectado is False
    assert clientes[0].consultas == ["a"]

    espera.set()
    assert (await en_curso).id_turno == 1
    assert (await sesion.turno("b")).id_turno == 2
    await sesion.cerrar()


async def test_cerrar_desconecta_y_es_idempotente(config):
    crear, clientes = fabrica(turno_simple("a"))
    sesion = Sesion(config, crear)
    await sesion.turno("a")

    await sesion.cerrar()
    await sesion.cerrar()

    assert clientes[0].desconectado is True
    assert sesion.estado()["conversacion"]["activa"] is False


async def test_sin_clave_no_abre_el_agente(config, monkeypatch, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    monkeypatch.chdir(tmp_path)  # sin archivo local de claves a la vista
    crear, clientes = fabrica(turno_simple("a"))
    sesion = Sesion(config, crear)

    with pytest.raises(ConfiguracionError):
        await sesion.turno("hola")

    assert clientes == []
    assert sesion.estado()["conversacion"]["activa"] is False
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ficticia-otra")
    assert (await sesion.turno("hola")).id_turno == 1  # el cerrojo quedó libre
    await sesion.cerrar()


async def test_un_fallo_al_abrir_deja_la_sesion_lista_para_reintentar(config):
    crear, clientes = fabrica(turno_simple("a"), falla_connect=RuntimeError("no conecta"))
    sesion = Sesion(config, crear)

    for _ in range(2):  # el segundo intento falla igual, pero no por el cerrojo
        with pytest.raises(RuntimeError, match="no conecta"):
            await sesion.turno("hola")

    assert len(clientes) == 2
    assert sesion.estado()["conversacion"]["activa"] is False
    assert sesion.estado()["conversacion"]["turnos"] == 0


async def test_un_turno_con_error_del_modelo_no_lanza_y_cuenta(config):
    crear, _ = fabrica([texto("a medias"), resultado(es_error=True, api_error_status=529)])
    sesion = Sesion(config, crear)

    hecho = await sesion.turno("hola")

    assert hecho.resultado.parada is Parada.ERROR_API
    assert hecho.resultado.error
    assert hecho.id_turno == 1
    assert sesion.estado()["conversacion"]["turnos"] == 1
    await sesion.cerrar()


# ---------------------------------------------------------------- operación (T026)


def _entorno_del_core(cliente) -> dict:
    return cliente.opciones.mcp_servers["crediagil-core"]["env"]


async def test_nueva_con_falla_pasa_la_variable_al_siguiente_agente(config):
    crear, clientes = fabrica(turno_simple("a"), turno_simple("b"))
    sesion = Sesion(config, crear)

    await sesion.nueva(3)
    assert sesion.estado()["falla_simulada"] == {"llamadas": 3}
    await sesion.turno("hola")
    assert _entorno_del_core(clientes[0])["CREDIAGIL_MCP_FALLAS_N"] == "3"
    await sesion.nueva(0)
    assert sesion.estado()["falla_simulada"] == {"llamadas": 0}
    await sesion.turno("hola")

    assert "CREDIAGIL_MCP_FALLAS_N" not in _entorno_del_core(clientes[1])
    await sesion.cerrar()


async def test_la_falla_simulada_arranca_desactivada(config):
    assert Sesion(config, fabrica()[0]).estado()["falla_simulada"] == {"llamadas": 0}


@pytest.mark.parametrize("valor", [0, 1, 20])
async def test_falla_dentro_del_rango_se_acepta(config, valor):
    sesion = Sesion(config, fabrica()[0])
    await sesion.nueva(valor)
    assert sesion.estado()["falla_simulada"]["llamadas"] == valor


@pytest.mark.parametrize("valor", [-1, 21, 1.5, "3", None, True, False])
async def test_falla_fuera_de_rango_o_de_otro_tipo_se_rechaza(config, valor):
    sesion = Sesion(config, fabrica()[0])
    with pytest.raises(FallaInvalida):
        await sesion.nueva(valor)
    assert sesion.estado()["falla_simulada"]["llamadas"] == 0


async def test_una_falla_invalida_no_cierra_el_agente_ni_cambia_la_conversacion(config):
    crear, clientes = fabrica(turno_simple("a"))
    sesion = Sesion(config, crear)
    await sesion.turno("hola")
    antes = sesion.estado()["conversacion"]

    with pytest.raises(FallaInvalida):
        await sesion.nueva(99)

    assert clientes[0].desconectado is False
    assert sesion.estado()["conversacion"] == antes
    await sesion.cerrar()


async def test_reiniciar_datos_deja_la_semilla_y_empieza_otra_conversacion(config):
    crear, clientes = fabrica(turno_simple("a"), turno_simple("b"))
    sesion = Sesion(config, crear)
    await sesion.turno("hola")
    antes = sesion.estado()["conversacion"]["id"]
    with AlmacenEstado(config.ruta_estado).transaccion() as datos:
        datos["escalamientos"]["ESC-0001"] = {"id_escalamiento": "ESC-0001"}
        datos["solicitantes"]["SOL-0001"]["bloqueado"] = True

    await sesion.reiniciar_datos()

    assert AlmacenEstado(config.ruta_estado).leer() == estado_semilla()
    assert clientes[0].desconectado is True
    despues = sesion.estado()["conversacion"]
    assert despues["turnos"] == 0 and despues["activa"] is False and despues["id"] != antes
    assert sesion.estado()["falla_simulada"] == {"llamadas": 0}
    assert (await sesion.turno("otra vez")).id_turno == 1
    await sesion.cerrar()


async def test_reiniciar_durante_un_turno_se_rechaza_sin_tocar_los_datos(config):
    espera = asyncio.Event()
    crear, clientes = fabrica([espera, *turno_simple("a")])
    sesion = Sesion(config, crear)
    en_curso = asyncio.create_task(sesion.turno("a"))
    await _esperar_consulta(clientes)
    with AlmacenEstado(config.ruta_estado).transaccion() as datos:
        datos["escalamientos"]["ESC-0001"] = {"id_escalamiento": "ESC-0001"}

    with pytest.raises(TurnoEnCurso):
        await sesion.reiniciar_datos()

    assert "ESC-0001" in AlmacenEstado(config.ruta_estado).leer()["escalamientos"]
    espera.set()
    await en_curso
    await sesion.cerrar()
