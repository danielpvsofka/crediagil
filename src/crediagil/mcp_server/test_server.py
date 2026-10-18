"""Tests del servidor MCP en proceso: contracts/tools.md §Comunes y §Protocolo (FR-001, FR-004)."""

from __future__ import annotations

import pytest

from crediagil.mcp_server import identidad
from crediagil.mcp_server.documentos_prueba import doc_certificado
from crediagil.mcp_server.estado import AlmacenEstado
from crediagil.mcp_server.fallas import InyectorFallas
from crediagil.mcp_server.semilla import SOLICITANTES_SEMILLA
from crediagil.mcp_server.server import crear_servidor

ANA = SOLICITANTES_SEMILLA[0]
CLAVES_ERROR = {"tipo", "codigo", "mensaje", "reintentable", "detalles"}
HERRAMIENTAS = {
    "buscar_solicitante",
    "verificar_identidad",
    "validar_extraccion",
    "registrar_solicitud",
    "calcular_capacidad_pago",
    "preaprobar_credito",
    "escalar_a_analista",
}


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def almacen(tmp_path):
    return AlmacenEstado(tmp_path / "estado.json")


async def llamar(servidor, herramienta, argumentos):
    resultado = await servidor.call_tool(herramienta, argumentos)
    assert resultado.is_error is False
    return resultado.structured_content


def es_error(respuesta, tipo, codigo):
    assert respuesta["ok"] is False
    assert set(respuesta["error"]) == CLAVES_ERROR
    assert (respuesta["error"]["tipo"], respuesta["error"]["codigo"]) == (tipo, codigo)


@pytest.mark.anyio
async def test_busqueda_exitosa(almacen):
    servidor = crear_servidor(almacen, InyectorFallas())
    respuesta = await llamar(servidor, "buscar_solicitante", {"nombre": "prueba"})
    assert respuesta["ok"] is True
    assert len(respuesta["coincidencias"]) >= 2


@pytest.mark.anyio
async def test_busqueda_sin_resultados(almacen):
    servidor = crear_servidor(almacen, InyectorFallas())
    respuesta = await llamar(servidor, "buscar_solicitante", {"nombre": "zzzz"})
    assert respuesta == {"ok": True, "coincidencias": []}


@pytest.mark.anyio
async def test_error_de_dominio_va_en_el_contenido(almacen):
    servidor = crear_servidor(almacen, InyectorFallas())
    respuesta = await llamar(servidor, "buscar_solicitante", {})
    es_error(respuesta, "validacion", "PARAMETROS_INVALIDOS")
    assert respuesta["error"]["reintentable"] is False


@pytest.mark.anyio
async def test_verificacion_exitosa_y_fallida(almacen):
    servidor = crear_servidor(almacen, InyectorFallas())
    argumentos = {"id_solicitante": ANA["id_solicitante"]}
    ok = await llamar(
        servidor, "verificar_identidad", {**argumentos, "fecha_nacimiento": ANA["fecha_nacimiento"]}
    )
    assert ok == {"ok": True, "verificado": True, "id_solicitante": ANA["id_solicitante"]}
    fallida = await llamar(
        servidor, "verificar_identidad", {**argumentos, "fecha_nacimiento": "2000-01-01"}
    )
    es_error(fallida, "negocio", "IDENTIDAD_NO_COINCIDE")
    assert fallida["error"]["detalles"] == {"intentos_restantes": 2}


@pytest.mark.anyio
async def test_falla_inyectada_es_transitoria_y_no_cambia_el_estado(almacen):
    servidor = crear_servidor(almacen, InyectorFallas(restantes=1))
    argumentos = {"id_solicitante": ANA["id_solicitante"], "fecha_nacimiento": "2000-01-01"}
    inyectada = await llamar(servidor, "verificar_identidad", argumentos)
    es_error(inyectada, "transitorio", "SERVICIO_NO_DISPONIBLE")
    assert inyectada["error"]["reintentable"] is True
    assert almacen.leer()["solicitantes"][ANA["id_solicitante"]]["intentos_fallidos"] == 0
    normal = await llamar(servidor, "verificar_identidad", argumentos)
    es_error(normal, "negocio", "IDENTIDAD_NO_COINCIDE")


@pytest.mark.anyio
async def test_excepcion_inesperada_no_expone_detalles(almacen, monkeypatch):
    def explota(*args, **kwargs):
        raise RuntimeError("secreto interno")

    monkeypatch.setattr(identidad, "buscar_solicitante", explota)
    servidor = crear_servidor(almacen, InyectorFallas())
    respuesta = await llamar(servidor, "buscar_solicitante", {"nombre": "prueba"})
    es_error(respuesta, "transitorio", "ERROR_INTERNO")
    assert respuesta["error"]["detalles"] == {}
    assert "secreto" not in str(respuesta)


@pytest.mark.anyio
async def test_estado_ilegible(tmp_path):
    ruta = tmp_path / "estado.json"
    ruta.write_text("{no json", encoding="utf-8")
    servidor = crear_servidor(AlmacenEstado(ruta), InyectorFallas())
    respuesta = await llamar(servidor, "buscar_solicitante", {"nombre": "prueba"})
    es_error(respuesta, "transitorio", "ESTADO_ILEGIBLE")
    assert ruta.read_text(encoding="utf-8") == "{no json"


@pytest.mark.anyio
async def test_lista_herramientas_con_descripcion_en_espanol(almacen):
    herramientas = {h.name: h for h in await crear_servidor(almacen, InyectorFallas()).list_tools()}
    assert set(herramientas) == HERRAMIENTAS
    assert "escala" in herramientas["verificar_identidad"].description
    assert "varias coincidencias" in herramientas["buscar_solicitante"].description
    for herramienta in herramientas.values():
        assert herramienta.input_schema["type"] == "object"
    assert set(herramientas["verificar_identidad"].input_schema["required"]) == {
        "id_solicitante",
        "fecha_nacimiento",
    }


# ---------------------------------------------------------------- spec 005: originación


@pytest.mark.anyio
async def test_descripciones_simular_y_comprometer(almacen):
    herramientas = {h.name: h for h in await crear_servidor(almacen, InyectorFallas()).list_tools()}
    assert herramientas["calcular_capacidad_pago"].description.startswith("SOLO SIMULA")
    preaprobar = herramientas["preaprobar_credito"].description
    assert preaprobar.startswith("COMPROMETE A CREDIÁGIL")
    assert "calcular_capacidad_pago" in preaprobar
    for herramienta in herramientas.values():
        assert herramienta.description.strip()


@pytest.mark.anyio
async def test_validar_extraccion(almacen):
    servidor = crear_servidor(almacen, InyectorFallas())
    doc = doc_certificado()
    ok = await llamar(
        servidor, "validar_extraccion", {"datos": doc["datos"], "texto": doc["texto"]}
    )
    assert ok["ok"] is True
    assert ok["extraccion"]["salario_mensual"]["valor"] == 2_000_000
    assert ok["politica_no_cubre"] is False
    assert "nombre_empleado" in ok["datos_faltantes"]

    doc["datos"]["salario_mensual"]["fragmento"] = "inventado"
    error = await llamar(
        servidor, "validar_extraccion", {"datos": doc["datos"], "texto": doc["texto"]}
    )
    es_error(error, "validacion", "FRAGMENTO_NO_LITERAL")
    assert error["error"]["reintentable"] is True

    no_soportado = await llamar(
        servidor,
        "validar_extraccion",
        {"datos": {"tipo": "no_soportado", "tipo_detectado": "pasaporte"}, "texto": ""},
    )
    assert no_soportado["politica_no_cubre"] is True


@pytest.mark.anyio
async def test_simular_no_cambia_el_estado(almacen):
    servidor = crear_servidor(almacen, InyectorFallas())
    almacen.leer()
    antes = almacen.ruta.read_bytes()
    respuesta = await llamar(
        servidor, "calcular_capacidad_pago", {"monto": 4_000_000, "plazo_meses": 24}
    )
    assert respuesta == {"ok": True, "cuota": 206_723, "tasa_mensual": "0.018"}
    assert almacen.ruta.read_bytes() == antes


@pytest.mark.anyio
async def test_flujo_verificar_registrar_preaprobar_escalar(almacen):
    servidor = crear_servidor(almacen, InyectorFallas())
    registro = {
        "id_solicitante": ANA["id_solicitante"],
        "monto": 4_000_000,
        "plazo_meses": 24,
        "ingreso_declarado": 2_000_000,
        "documentos": [doc_certificado()],
    }
    sin_identidad = await llamar(servidor, "registrar_solicitud", registro)
    es_error(sin_identidad, "permisos", "IDENTIDAD_NO_VERIFICADA")

    await llamar(
        servidor,
        "verificar_identidad",
        {"id_solicitante": ANA["id_solicitante"], "fecha_nacimiento": ANA["fecha_nacimiento"]},
    )
    registrada = await llamar(servidor, "registrar_solicitud", registro)
    assert registrada["evaluacion"]["preaprobable_automaticamente"] is True

    preaprobada = await llamar(
        servidor, "preaprobar_credito", {"id_solicitud": registrada["id_solicitud"]}
    )
    assert preaprobada["ok"] is True
    assert preaprobada["cuota"] == 206_723

    incompleto = await llamar(servidor, "escalar_a_analista", {"resumen": {"causa": "otro"}})
    es_error(incompleto, "validacion", "RESUMEN_INCOMPLETO")
    humano = {
        "solicitante": ANA["id_solicitante"],
        "monto": None,
        "plazo": None,
        "datos": [],
        "discrepancias": [],
        "causa": "solicitud_humano",
        "detalle": "Pidió hablar con una persona.",
        "accion_recomendada": "Contactar al solicitante.",
    }
    escalado = await llamar(servidor, "escalar_a_analista", {"resumen": humano})
    assert escalado == {"ok": True, "id_escalamiento": "ESC-0001", "id_solicitud": None}
