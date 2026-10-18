"""Tests de la API de la interfaz de chat (spec 008, contracts/api.md)."""

from __future__ import annotations

import base64
import json

import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from crediagil.agent.opciones import ConfigAgente
from crediagil.chat.adjuntos import LIMITE_ADJUNTOS, LIMITE_BYTES_ADJUNTO
from crediagil.chat.app import ErrorApi, crear_app, leer_json, manejar_error_api, manejar_excepcion
from crediagil.chat.casos import casos_publicos
from crediagil.chat.clientes_falsos import (
    fabrica,
    respuesta_herramienta,
    resultado,
    texto,
    turno_simple,
    uso,
)
from crediagil.chat.sesion import TurnoEnCurso
from crediagil.mcp_server.estado import AlmacenEstado, estado_semilla

CLAVE = "sk-ficticia-app"


@pytest.fixture(autouse=True)
def clave(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", CLAVE)


@pytest.fixture
def cliente():
    with TestClient(crear_app(), raise_server_exceptions=False) as c:
        yield c


# ---------------------------------------------------------------- esqueleto (T004)


def test_la_pagina_se_sirve_con_sus_elementos(cliente):
    respuesta = cliente.get("/")
    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"].startswith("text/html")
    for identificador in ("hilo", "formulario", "mensaje", "enviar"):
        assert f'id="{identificador}"' in respuesta.text


@pytest.mark.parametrize(
    ("ruta", "tipo"),
    [("/static/app.js", "javascript"), ("/static/estilos.css", "css")],
)
def test_archivos_estaticos(cliente, ruta, tipo):
    respuesta = cliente.get(ruta)
    assert respuesta.status_code == 200
    assert tipo in respuesta.headers["content-type"]


@pytest.mark.parametrize("ruta", ["/static/inexistente.js", "/static/../app.py", "/static/"])
def test_estatico_desconocido_da_404(cliente, ruta):
    assert cliente.get(ruta).status_code == 404


def _app_de_prueba(endpoint):
    return TestClient(
        Starlette(
            routes=[Route("/p", endpoint, methods=["POST"])],
            exception_handlers={ErrorApi: manejar_error_api, Exception: manejar_excepcion},
        ),
        raise_server_exceptions=False,
    )


def test_un_error_de_la_api_tiene_la_forma_acordada():
    async def endpoint(request):
        raise ErrorApi(409, "TURNO_EN_CURSO", f"Espera. {CLAVE}")

    respuesta = _app_de_prueba(endpoint).post("/p", json={})
    assert respuesta.status_code == 409
    assert set(respuesta.json()) == {"error"}
    assert respuesta.json()["error"]["codigo"] == "TURNO_EN_CURSO"
    assert CLAVE not in respuesta.text


@pytest.mark.parametrize("cuerpo", [b"[]", b'"x"', b"no es json", b"3", b"null"])
def test_cuerpo_que_no_es_un_objeto_json_da_400(cuerpo):
    async def endpoint(request):
        return JSONResponse(await leer_json(request))

    respuesta = _app_de_prueba(endpoint).post("/p", content=cuerpo)
    assert respuesta.status_code == 400
    assert respuesta.json()["error"]["codigo"] == "JSON_INVALIDO"


def test_leer_json_acepta_un_objeto_y_un_cuerpo_vacio_opcional():
    async def endpoint(request):
        return JSONResponse(await leer_json(request, opcional=True))

    cliente = _app_de_prueba(endpoint)
    assert cliente.post("/p", json={"a": 1}).json() == {"a": 1}
    assert cliente.post("/p", content=b"").json() == {}


def test_un_error_inesperado_no_filtra_trazas_ni_la_clave():
    async def endpoint(request):
        raise RuntimeError(f"fallo interno con {CLAVE}")

    respuesta = _app_de_prueba(endpoint).post("/p", json={})
    assert respuesta.status_code == 500
    assert respuesta.json()["error"]["codigo"] == "ERROR_INTERNO"
    assert CLAVE not in respuesta.text
    assert "Traceback" not in respuesta.text
    assert "fallo interno" not in respuesta.text


# ---------------------------------------------------------------- turnos y conversaciones (T008)


@pytest.fixture
def agente_falso(tmp_path):
    """`(cliente_http, clientes_sdk)`: la API con un agente falso que responde "Hola" y "Dos"."""

    def armar(*guion, **opciones):
        crear, clientes = fabrica(
            *(guion or (turno_simple("Hola"), turno_simple("Dos"))), **opciones
        )
        config = ConfigAgente(ruta_estado=tmp_path / "estado.json")
        app = crear_app(config=config, cliente_factory=crear)
        return TestClient(app, raise_server_exceptions=False), clientes

    return armar


def test_un_turno_devuelve_el_resultado_y_el_siguiente_continua(agente_falso):
    http, clientes = agente_falso()
    with http:
        primero = http.post("/api/turnos", json={"mensaje": "hola"})
        segundo = http.post("/api/turnos", json={"mensaje": "otra cosa"})
    assert primero.status_code == 200
    assert primero.json()["respuesta"] == "Hola"
    assert primero.json()["id_turno"] == 1
    assert segundo.json()["id_turno"] == 2
    assert len(clientes) == 1
    assert clientes[0].consultas == ["hola", "otra cosa"]


@pytest.mark.parametrize(
    "cuerpo", [{"mensaje": ""}, {"mensaje": "   \n "}, {}, {"mensaje": 3}, {"mensaje": None}]
)
def test_mensaje_vacio_no_abre_el_agente(agente_falso, cuerpo):
    http, clientes = agente_falso()
    with http:
        respuesta = http.post("/api/turnos", json=cuerpo)
    assert respuesta.status_code == 400
    assert respuesta.json()["error"]["codigo"] == "MENSAJE_VACIO"
    assert clientes == []


def test_conversacion_nueva_reinicia_el_contador(agente_falso):
    http, clientes = agente_falso(turno_simple("a"), turno_simple("b"))
    with http:
        http.post("/api/turnos", json={"mensaje": "hola"})
        nueva = http.post("/api/conversaciones", json={})
        despues = http.post("/api/turnos", json={"mensaje": "hola"})
    assert nueva.status_code == 201
    assert isinstance(nueva.json()["id"], str) and nueva.json()["id"]
    assert clientes[0].desconectado is True
    assert despues.json()["id_turno"] == 1
    assert len(clientes) == 2


def test_conversacion_nueva_acepta_un_cuerpo_vacio(agente_falso):
    http, _ = agente_falso()
    with http:
        assert http.post("/api/conversaciones", content=b"").status_code == 201


class _SesionOcupada:
    async def turno(self, *_args, **_kwargs):
        raise TurnoEnCurso("ocupada")

    async def nueva(self, *_args, **_kwargs):
        raise TurnoEnCurso("ocupada")

    async def reiniciar_datos(self):
        raise TurnoEnCurso("ocupada")

    async def cerrar(self):
        return None

    def estado(self):
        return {"conversacion": {"id": None, "turnos": 0, "activa": False}}


def test_un_turno_en_curso_da_409():
    with TestClient(crear_app(sesion=_SesionOcupada()), raise_server_exceptions=False) as http:
        turno = http.post("/api/turnos", json={"mensaje": "hola"})
        nueva = http.post("/api/conversaciones", json={})
    for respuesta in (turno, nueva):
        assert respuesta.status_code == 409
        assert respuesta.json()["error"]["codigo"] == "TURNO_EN_CURSO"


def test_sin_clave_da_503_sin_valores(agente_falso, monkeypatch, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    monkeypatch.chdir(tmp_path)  # sin archivo local de claves a la vista
    http, clientes = agente_falso()
    with http:
        respuesta = http.post("/api/turnos", json={"mensaje": "hola"})
    assert respuesta.status_code == 503
    error = respuesta.json()["error"]
    assert error["codigo"] == "CLAVE_NO_CONFIGURADA"
    assert "ANTHROPIC_API_KEY" in error["mensaje"]
    assert CLAVE not in respuesta.text
    assert clientes == []


def test_un_fallo_al_abrir_el_agente_da_502_redactado(agente_falso):
    http, _ = agente_falso(falla_connect=RuntimeError(f"no conecta con {CLAVE}"))
    with http:
        respuesta = http.post("/api/turnos", json={"mensaje": "hola"})
    assert respuesta.status_code == 502
    assert respuesta.json()["error"]["codigo"] == "ERROR_AGENTE"
    assert CLAVE not in respuesta.text
    assert "Traceback" not in respuesta.text


def test_un_turno_con_error_del_modelo_es_un_200_con_error(agente_falso):
    http, _ = agente_falso([texto("a medias"), resultado(es_error=True, api_error_status=529)])
    with http:
        respuesta = http.post("/api/turnos", json={"mensaje": "hola"})
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["parada"] == "error_api"
    assert cuerpo["error"]
    assert cuerpo["respuesta"] == ""


# ---------------------------------------------------------------- adjuntos (T014)


def _adjunto(nombre="certificado.txt", contenido: str | bytes = "Salario: $6.000.000 COP"):
    crudo = contenido.encode("utf-8") if isinstance(contenido, str) else contenido
    return {"nombre": nombre, "contenido_b64": base64.b64encode(crudo).decode("ascii")}


def test_un_adjunto_valido_llega_al_agente_con_nombre_y_texto_completo(agente_falso):
    http, clientes = agente_falso()
    with http:
        respuesta = http.post("/api/turnos", json={"mensaje": "mira", "adjuntos": [_adjunto()]})
    assert respuesta.status_code == 200
    consulta = clientes[0].consultas[0]
    assert consulta.startswith("mira")
    assert (
        '<documento id="DOC-1" nombre="certificado.txt">Salario: $6.000.000 COP</documento>'
        in consulta
    )


def test_varios_adjuntos_llegan_todos_con_ids_consecutivos(agente_falso):
    http, clientes = agente_falso()
    with http:
        http.post(
            "/api/turnos",
            json={
                "mensaje": "mira",
                "adjuntos": [_adjunto("a.txt", "uno"), _adjunto("b.md", "dos")],
            },
        )
    consulta = clientes[0].consultas[0]
    assert 'id="DOC-1" nombre="a.txt">uno<' in consulta
    assert 'id="DOC-2" nombre="b.md">dos<' in consulta


def test_sin_adjuntos_el_mensaje_queda_igual(agente_falso):
    http, clientes = agente_falso()
    with http:
        http.post("/api/turnos", json={"mensaje": "hola", "adjuntos": []})
    assert clientes[0].consultas == ["hola"]


@pytest.mark.parametrize(
    ("adjuntos", "codigo"),
    [
        ([_adjunto("a.pdf")], "EXTENSION_NO_ADMITIDA"),
        ([_adjunto("a.txt", "  ")], "ADJUNTO_VACIO"),
        ([_adjunto("a.txt", b"\xff\xfe\x00")], "ADJUNTO_ILEGIBLE"),
        ([_adjunto("a.txt", "a" * (LIMITE_BYTES_ADJUNTO + 1))], "ADJUNTO_DEMASIADO_GRANDE"),
        ([_adjunto(f"a{i}.txt") for i in range(LIMITE_ADJUNTOS + 1)], "ADJUNTOS_DEMASIADOS"),
        ([{"nombre": "a.txt"}], "ADJUNTO_INVALIDO"),
        ("a.txt", "ADJUNTO_INVALIDO"),
    ],
)
def test_un_adjunto_invalido_da_400_y_no_abre_el_agente_ni_cuenta_turno(
    agente_falso, adjuntos, codigo
):
    http, clientes = agente_falso()
    with http:
        respuesta = http.post("/api/turnos", json={"mensaje": "hola", "adjuntos": adjuntos})
        siguiente = http.post("/api/turnos", json={"mensaje": "hola"})
    assert respuesta.status_code == 400
    assert respuesta.json()["error"]["codigo"] == codigo
    assert respuesta.json()["error"]["mensaje"]
    assert siguiente.json()["id_turno"] == 1  # el rechazo no consumió un turno
    assert len(clientes) == 1
    assert clientes[0].consultas == ["hola"]


# ---------------------------------------------------------------- avisos (T018)

AVISOS_CORE = "mcp__crediagil-core__"
PREAPROBACION = {
    "ok": True,
    "id_solicitud": "SLC-0001",
    "monto": 3_000_000,
    "plazo_meses": 24,
    "cuota": 155_043,
    "tasa_mensual": "0.018",
}


def _tipos(cuerpo):
    return [a["tipo"] for a in cuerpo["avisos"]]


def _turno_con(agente_falso, *mensajes):
    http, clientes = agente_falso(list(mensajes))
    with http:
        respuesta = http.post("/api/turnos", json={"mensaje": "hola"})
    assert respuesta.status_code == 200
    return respuesta.json(), clientes


def test_aviso_de_credito_preaprobado(agente_falso):
    cuerpo, _ = _turno_con(
        agente_falso,
        uso("p", AVISOS_CORE + "preaprobar_credito", {"id_solicitud": "SLC-0001"}),
        respuesta_herramienta("p", PREAPROBACION),
        texto("Listo"),
        resultado(),
    )
    (aviso,) = cuerpo["avisos"]
    assert aviso["tipo"] == "credito_preaprobado"
    assert aviso["rotulo"] == "Crédito preaprobado"
    contenido = aviso["contenido"]
    assert contenido["monto"] == 3_000_000
    assert contenido["plazo_meses"] == 24
    assert contenido["cuota"] == 155_043
    assert contenido["tasa_mensual"] == "0.018"


def test_aviso_de_informacion_solicitada(agente_falso):
    cuerpo, _ = _turno_con(
        agente_falso,
        uso("i", "mcp__canal__solicitar_informacion", {"datos": ["salario"], "motivo": "falta"}),
        respuesta_herramienta("i", "Solicitud de información registrada: salario"),
        texto("Necesito tu salario"),
        resultado(),
    )
    (aviso,) = cuerpo["avisos"]
    assert aviso["tipo"] == "informacion_solicitada"
    assert aviso["rotulo"] == "Información solicitada"
    assert aviso["contenido"] == {"datos": ["salario"], "motivo": "falta"}


def test_aviso_de_escalamiento(agente_falso):
    cuerpo, _ = _turno_con(
        agente_falso,
        uso("e", AVISOS_CORE + "escalar_a_analista", {"resumen": {"causa": "solicitud_humano"}}),
        respuesta_herramienta(
            "e", {"ok": True, "id_escalamiento": "ESC-0001", "id_solicitud": None}
        ),
        texto("Te paso con una persona"),
        resultado(),
    )
    (aviso,) = cuerpo["avisos"]
    assert aviso["tipo"] == "escalamiento"
    assert aviso["rotulo"] == "Escalado a un analista"
    assert aviso["contenido"] == {"id_escalamiento": "ESC-0001", "causa": "solicitud_humano"}


def test_aviso_de_bloqueo_por_regla_de_negocio(agente_falso, tmp_path):
    from crediagil.mcp_server.estado import AlmacenEstado

    AlmacenEstado(tmp_path / "estado.json").leer()  # crea la semilla que leen los hooks
    clientes = []  # se llena al crear el agente; el intento de registro usa sus hooks reales

    async def intento_de_registro():
        hook = clientes[0][0].opciones.hooks["PreToolUse"][0].hooks[0]
        evento = {
            "tool_name": AVISOS_CORE + "registrar_solicitud",
            "tool_input": {"id_solicitante": "SOL-9999"},
        }
        await hook(evento, "id", {})

    http, creados = agente_falso([intento_de_registro, texto("No pude registrar"), resultado()])
    clientes.append(creados)  # referencia a la lista viva de clientes creados
    with http:
        cuerpo = http.post("/api/turnos", json={"mensaje": "hola"}).json()
    (aviso,) = cuerpo["avisos"]
    assert aviso["tipo"] == "bloqueo_regla"
    assert aviso["rotulo"] == "Bloqueado por una regla de negocio"
    assert aviso["contenido"]["herramienta"] == "registrar_solicitud"
    assert aviso["contenido"]["codigo"] == "IDENTIDAD_NO_VERIFICADA"
    assert aviso["contenido"]["mensaje"]
    (negacion,) = cuerpo["negaciones"]
    assert negacion["codigo"] == "IDENTIDAD_NO_VERIFICADA"
    assert negacion["accion"]


def test_varios_avisos_se_devuelven_todos_en_orden(agente_falso):
    cuerpo, _ = _turno_con(
        agente_falso,
        uso("i", "mcp__canal__solicitar_informacion", {"datos": ["x"], "motivo": "m"}),
        respuesta_herramienta("i", "registrado"),
        uso("p", AVISOS_CORE + "preaprobar_credito", {"id_solicitud": "SLC-0001"}),
        respuesta_herramienta("p", PREAPROBACION),
        texto("Hecho"),
        resultado(),
    )
    assert _tipos(cuerpo) == ["informacion_solicitada", "credito_preaprobado"]


def test_un_turno_sin_avisos_devuelve_la_lista_vacia(agente_falso):
    cuerpo, _ = _turno_con(agente_falso, texto("Hola, ¿en qué te ayudo?"), resultado())
    assert cuerpo["avisos"] == []


def test_el_texto_que_afirma_una_preaprobacion_no_inventa_el_aviso(agente_falso):
    cuerpo, _ = _turno_con(
        agente_falso, texto("¡Listo! Tu crédito quedó preaprobado."), resultado()
    )
    assert cuerpo["avisos"] == []
    assert "preaprobado" in cuerpo["respuesta"]


def test_una_preaprobacion_fallida_no_da_aviso(agente_falso):
    cuerpo, _ = _turno_con(
        agente_falso,
        uso("p", AVISOS_CORE + "preaprobar_credito", {"id_solicitud": "SLC-0001"}),
        respuesta_herramienta("p", {"ok": False, "error": {"codigo": "NO_PREAPROBABLE"}}),
        texto("Tu crédito quedó preaprobado"),
        resultado(),
    )
    assert cuerpo["avisos"] == []


# ---------------------------------------------------------------- detalle técnico (T020)


def test_la_traza_llega_completa_en_orden_con_sus_marcas(agente_falso):
    cuerpo, _ = _turno_con(
        agente_falso,
        uso("t1", AVISOS_CORE + "buscar_solicitante", {"documento": "TEST-1"}),
        respuesta_herramienta("t1", {"ok": True, "coincidencias": []}),
        uso("a", "Agent", {"subagent_type": "extractor-documentos", "prompt": "DOC-1"}),
        uso("b", AVISOS_CORE + "validar_extraccion", {"datos": {}}, padre="a"),
        respuesta_herramienta("b", {"ok": False, "error": {"codigo": "EXTRACCION_INVALIDA"}}, True),
        respuesta_herramienta("a", "extraído"),
        uso("v", AVISOS_CORE + "verificar_identidad", {"id_solicitante": "SOL-0001"}),
        respuesta_herramienta("v", {"ok": True, "verificado": True}),
        texto("Hecho"),
        resultado(),
    )
    traza = cuerpo["traza"]
    assert [e["nombre"] for e in traza] == [
        "buscar_solicitante",
        "Agent",
        "validar_extraccion",
        "verificar_identidad",
    ]
    assert [e["tipo"] for e in traza] == ["herramienta", "delegacion", "herramienta", "herramienta"]
    assert [e["de_subagente"] for e in traza] == [False, False, True, False]
    assert [e["es_error"] for e in traza] == [False, False, True, False]
    assert traza[0]["entrada"] == {"documento": "TEST-1"}
    assert traza[0]["salida"] == {"ok": True, "coincidencias": []}
    assert traza[2]["salida"]["error"]["codigo"] == "EXTRACCION_INVALIDA"
    assert traza[0]["stop_reason"] == "tool_use"
    assert cuerpo["razon_parada"] == "end_turn"
    assert cuerpo["parada"] == "fin_de_turno"
    assert cuerpo["costo_usd"] == 0.01


def test_un_turno_sin_herramientas_tiene_traza_vacia_y_conserva_la_parada(agente_falso):
    cuerpo, _ = _turno_con(agente_falso, texto("Hola"), resultado())
    assert cuerpo["traza"] == []
    assert cuerpo["parada"] == "fin_de_turno"
    assert cuerpo["razon_parada"] == "end_turn"


def test_la_clave_no_sale_en_el_detalle_tecnico(agente_falso):
    cuerpo, _ = _turno_con(
        agente_falso,
        uso("t1", AVISOS_CORE + "buscar_solicitante", {"documento": f"x {CLAVE}"}),
        respuesta_herramienta("t1", {"ok": True, "eco": CLAVE}),
        texto(f"la clave es {CLAVE}"),
        resultado(),
    )
    volcado = json.dumps(cuerpo)
    assert CLAVE not in volcado
    assert "[REDACTADO]" in volcado


# ---------------------------------------------------------------- operación (T026)


def test_el_listado_de_casos_es_el_catalogo(cliente):
    respuesta = cliente.get("/api/casos")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"casos": casos_publicos()}
    casos = respuesta.json()["casos"]
    assert len(casos) == 9
    assert {"dentro_de_politica", "falla_transitoria", "moneda_extranjera"} <= {
        c["id"] for c in casos
    }
    assert all({"numero", "obligatorio", "falla_sugerida"} <= set(c) for c in casos)


@pytest.mark.parametrize("valor", [0, 1, 20])
def test_falla_en_los_bordes_validos(agente_falso, valor):
    http, _ = agente_falso()
    with http:
        respuesta = http.post("/api/conversaciones", json={"falla_llamadas": valor})
    assert respuesta.status_code == 201
    assert respuesta.json()["falla_llamadas"] == valor


def test_sin_falla_se_usa_cero(agente_falso):
    http, _ = agente_falso()
    with http:
        con_objeto = http.post("/api/conversaciones", json={})
        sin_cuerpo = http.post("/api/conversaciones", content=b"")
    for respuesta in (con_objeto, sin_cuerpo):
        assert respuesta.status_code == 201
        assert respuesta.json()["falla_llamadas"] == 0


@pytest.mark.parametrize("valor", [21, -1, 1.5, "x", "3", True, None])
def test_falla_invalida_da_422_y_no_cambia_nada(agente_falso, valor):
    http, clientes = agente_falso(turno_simple("a"), turno_simple("b"))
    with http:
        http.post("/api/turnos", json={"mensaje": "hola"})
        respuesta = http.post("/api/conversaciones", json={"falla_llamadas": valor})
        sigue_abierto = clientes[0].desconectado is False  # antes del apagado de la app
        siguiente = http.post("/api/turnos", json={"mensaje": "otra"})
    assert respuesta.status_code == 422
    assert respuesta.json()["error"]["codigo"] == "PARAMETRO_INVALIDO"
    assert sigue_abierto  # la conversación siguió su curso
    assert siguiente.json()["id_turno"] == 2


def test_la_falla_simulada_llega_al_core_de_la_conversacion_nueva(agente_falso):
    http, clientes = agente_falso(turno_simple("a"))
    with http:
        http.post("/api/conversaciones", json={"falla_llamadas": 2})
        http.post("/api/turnos", json={"mensaje": "hola"})
    entorno = clientes[0].opciones.mcp_servers["crediagil-core"]["env"]
    assert entorno["CREDIAGIL_MCP_FALLAS_N"] == "2"


def _datos_sucios(tmp_path):
    almacen = AlmacenEstado(tmp_path / "estado.json")
    with almacen.transaccion() as datos:
        datos["escalamientos"]["ESC-0001"] = {"id_escalamiento": "ESC-0001"}
    return almacen


@pytest.mark.parametrize(
    "cuerpo", [{}, {"confirmar": False}, {"confirmar": "true"}, {"confirmar": 1}]
)
def test_reiniciar_sin_confirmacion_no_borra_nada(agente_falso, tmp_path, cuerpo):
    almacen = _datos_sucios(tmp_path)
    http, _ = agente_falso()
    with http:
        respuesta = http.post("/api/datos/reiniciar", json=cuerpo)
    assert respuesta.status_code == 400
    assert respuesta.json()["error"]["codigo"] == "CONFIRMACION_REQUERIDA"
    assert "ESC-0001" in almacen.leer()["escalamientos"]


def test_reiniciar_con_confirmacion_deja_la_semilla_y_cero_turnos(agente_falso, tmp_path):
    almacen = _datos_sucios(tmp_path)
    http, clientes = agente_falso(turno_simple("a"), turno_simple("b"))
    with http:
        http.post("/api/turnos", json={"mensaje": "hola"})
        respuesta = http.post("/api/datos/reiniciar", json={"confirmar": True})
        despues = http.post("/api/turnos", json={"mensaje": "hola"})
    assert respuesta.status_code == 200
    conversacion = respuesta.json()["conversacion"]
    assert conversacion["turnos"] == 0 and conversacion["activa"] is False
    assert almacen.leer() == estado_semilla()
    assert clientes[0].desconectado is True
    assert despues.json()["id_turno"] == 1


def test_reiniciar_con_un_turno_en_curso_da_409():
    with TestClient(crear_app(sesion=_SesionOcupada()), raise_server_exceptions=False) as http:
        respuesta = http.post("/api/datos/reiniciar", json={"confirmar": True})
    assert respuesta.status_code == 409
    assert respuesta.json()["error"]["codigo"] == "TURNO_EN_CURSO"


# ---------------------------------------------------------------- estado y arranque (T029)


def _estado(http):
    respuesta = http.get("/api/estado")
    assert respuesta.status_code == 200
    return respuesta.json()


def test_con_clave_configurada_nunca_se_muestra_su_valor(agente_falso):
    http, _ = agente_falso()
    with http:
        respuesta = http.get("/api/estado")
    assert respuesta.json()["clave_configurada"] is True
    assert CLAVE not in respuesta.text


def test_sin_clave_se_informa_sin_valores(agente_falso, monkeypatch, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    monkeypatch.chdir(tmp_path)  # sin archivo local de claves a la vista
    http, _ = agente_falso()
    with http:
        respuesta = http.get("/api/estado")
    assert respuesta.json()["clave_configurada"] is False
    assert CLAVE not in respuesta.text


def test_el_estado_del_core_es_legible_si_no_existe_o_es_valido(agente_falso, tmp_path):
    http, _ = agente_falso()
    with http:
        assert _estado(http)["estado_core_legible"] is True  # el archivo aún no existe
        AlmacenEstado(tmp_path / "estado.json").leer()  # crea la semilla
        assert _estado(http)["estado_core_legible"] is True


def test_un_estado_corrupto_no_es_legible_y_no_se_toca(agente_falso, tmp_path):
    ruta = tmp_path / "estado.json"
    ruta.write_text("{ no es json", encoding="utf-8")
    http, _ = agente_falso()
    with http:
        assert _estado(http)["estado_core_legible"] is False
    assert ruta.read_text(encoding="utf-8") == "{ no es json"


def test_la_conversacion_cambia_tras_un_turno_y_tras_una_nueva(agente_falso):
    http, _ = agente_falso(turno_simple("a"))
    with http:
        inicial = _estado(http)["conversacion"]
        http.post("/api/turnos", json={"mensaje": "hola"})
        tras_turno = _estado(http)["conversacion"]
        http.post("/api/conversaciones", json={})
        tras_nueva = _estado(http)["conversacion"]
    assert inicial == {"id": None, "turnos": 0, "activa": False}
    assert tras_turno["turnos"] == 1 and tras_turno["activa"] is True
    assert isinstance(tras_turno["id"], str) and tras_turno["id"]
    assert tras_nueva["turnos"] == 0 and tras_nueva["activa"] is False
    assert tras_nueva["id"] != tras_turno["id"]


def test_la_falla_simulada_se_refleja_en_el_estado(agente_falso):
    http, _ = agente_falso()
    with http:
        assert _estado(http)["falla_simulada"] == {"llamadas": 0}
        http.post("/api/conversaciones", json={"falla_llamadas": 4})
        assert _estado(http)["falla_simulada"] == {"llamadas": 4}


def test_los_limites_son_los_de_las_constantes_del_servidor(agente_falso):
    http, _ = agente_falso()
    with http:
        limites = _estado(http)["limites"]
    assert limites == {
        "max_adjuntos": LIMITE_ADJUNTOS,
        "max_bytes_adjunto": LIMITE_BYTES_ADJUNTO,
        "extensiones": [".txt", ".md"],
    }
    assert (LIMITE_ADJUNTOS, LIMITE_BYTES_ADJUNTO) == (5, 102_400)


def test_el_estado_tiene_exactamente_las_claves_del_contrato(agente_falso):
    http, _ = agente_falso()
    with http:
        assert set(_estado(http)) == {
            "clave_configurada",
            "estado_core_legible",
            "conversacion",
            "falla_simulada",
            "limites",
        }
