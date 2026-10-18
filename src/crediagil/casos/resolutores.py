"""Resuelve cada caso del catálogo con las piezas reales, sin modelo (spec 009, research R4).

Cada resolutor usa la extracción esperada del caso, el core (`registrar_solicitud`,
`preaprobar_credito`, `escalar_a_analista`), los hooks de #6 y el inyector de fallas de #5, y
comprueba con aserciones el resultado que declara el caso. Ninguno reimplementa una regla: la
decisión sale siempre de la política y del core; si una regla se rompe, falla el resolutor.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from crediagil.agent.hooks import (
    SERVIDOR_POR_DEFECTO,
    crear_hook_preaprobacion,
    crear_hook_registro,
    crear_hooks,
    nombre_herramienta,
)
from crediagil.agent.negaciones import RegistroNegaciones
from crediagil.casos.catalogo import Caso, Causa, Resultado
from crediagil.extraction.income import derivar_ingreso
from crediagil.extraction.schemas import CertificadoLaboral
from crediagil.mcp_server.documentos_prueba import doc_certificado
from crediagil.mcp_server.errores import ErrorCore, TipoError
from crediagil.mcp_server.escalamiento import escalar_a_analista
from crediagil.mcp_server.estado import AlmacenEstado
from crediagil.mcp_server.fallas import InyectorFallas
from crediagil.mcp_server.identidad import verificar_identidad
from crediagil.mcp_server.originacion import extraer, preaprobar_credito, registrar_solicitud
from crediagil.mcp_server.semilla import SOLICITANTES_SEMILLA
from crediagil.mcp_server.server import crear_servidor
from crediagil.policy import Decision
from crediagil.policy.params import TASA_MENSUAL

HOY = date(2026, 10, 17)  # fecha fija: la verificación compara solo la fecha de nacimiento


# ---------------------------------------------------------------- piezas comunes


def solicitante_de(caso: Caso) -> dict:
    id_solicitante = caso.solicitud.id_solicitante
    return next(s for s in SOLICITANTES_SEMILLA if s["id_solicitante"] == id_solicitante)


def documentos_extraidos(caso: Caso) -> list[dict]:
    """Lo que el agente enviaría a `registrar_solicitud`: la extracción esperada de cada documento."""
    return [
        {"id_documento": Path(d.nombre).stem, "datos": d.extraccion, "texto": d.texto}
        for d in caso.documentos
    ]


def verificar(almacen: AlmacenEstado, caso: Caso) -> None:
    """Verifica la identidad del solicitante del caso con los datos de la semilla ficticia."""
    persona = solicitante_de(caso)
    verificar_identidad(almacen, persona["id_solicitante"], persona["fecha_nacimiento"], hoy=HOY)


def registrar(almacen: AlmacenEstado, caso: Caso, ingreso_declarado: int | None = None) -> dict:
    s = caso.solicitud
    declarado = s.ingreso_declarado if ingreso_declarado is None else ingreso_declarado
    return registrar_solicitud(
        almacen, s.id_solicitante, s.monto, s.plazo_meses, declarado, documentos_extraidos(caso)
    )


def entrada_hook(herramienta: str, **tool_input) -> dict:
    """Entrada de `PreToolUse` tal como la entrega el SDK."""
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": nombre_herramienta(SERVIDOR_POR_DEFECTO, herramienta),
        "tool_input": tool_input,
        "tool_use_id": "t1",
        "session_id": "s1",
        "transcript_path": "",
        "cwd": ".",
    }


async def invocar(hook, herramienta: str, **tool_input) -> dict:
    return await hook(entrada_hook(herramienta, **tool_input), "t1", {"signal": None})


def veredicto(salida: dict) -> tuple[str | None, str]:
    """(decisión de permiso, motivo) de la salida de un hook; (None, "") si permite sin opinar."""
    especifica = salida.get("hookSpecificOutput", {})
    return especifica.get("permissionDecision"), especifica.get("permissionDecisionReason", "")


def error_de(funcion, *args, **kwargs) -> ErrorCore:
    try:
        funcion(*args, **kwargs)
    except ErrorCore as error:
        return error
    raise AssertionError("se esperaba un ErrorCore y la llamada tuvo éxito")


def causas(evaluacion: dict) -> list[str]:
    return [c["regla"] for c in evaluacion["causas_escalamiento"]]


def estado_de(almacen: AlmacenEstado, id_solicitud: str) -> dict:
    return almacen.leer()["solicitudes"][id_solicitud]


# ---------------------------------------------------------------- resolutores


async def resolver_preaprobar(caso: Caso, almacen: AlmacenEstado) -> None:
    """Documentos consistentes y dentro de política: se registra y se preaprueba."""
    s = caso.solicitud
    verificar(almacen, caso)
    registro = RegistroNegaciones()
    hook_registro = crear_hook_registro(almacen, registro=registro)
    hook_preaprobacion = crear_hook_preaprobacion(almacen, registro=registro)

    assert (
        await invocar(hook_registro, "registrar_solicitud", id_solicitante=s.id_solicitante) == {}
    )
    registrada = registrar(almacen, caso)
    evaluacion = registrada["evaluacion"]
    assert evaluacion["preaprobable_automaticamente"] is True, evaluacion
    assert causas(evaluacion) == []

    id_solicitud = registrada["id_solicitud"]
    permitido = await invocar(hook_preaprobacion, "preaprobar_credito", id_solicitud=id_solicitud)
    assert permitido == {}, permitido
    preaprobacion = preaprobar_credito(almacen, id_solicitud)
    assert preaprobacion["monto"] == s.monto and preaprobacion["plazo_meses"] == s.plazo_meses
    assert preaprobacion["cuota"] == evaluacion["cuota"]
    assert preaprobacion["tasa_mensual"] == str(TASA_MENSUAL)
    assert estado_de(almacen, id_solicitud)["estado"] == "PREAPROBADA"
    assert registro.listar() == []


async def resolver_solicitar_dato(caso: Caso, almacen: AlmacenEstado) -> None:
    """El documento no trae el dato: queda nulo, no se infiere y se pide (no se escala)."""
    for documento in caso.documentos:
        extraido, faltantes = extraer(documento.extraccion, documento.texto)
        assert isinstance(extraido, CertificadoLaboral)
        assert extraido.salario_mensual is None, "el salario ausente no se inventa"
        assert set(caso.esperado.datos_faltantes) <= set(faltantes), faltantes
        assert derivar_ingreso([extraido]).ingreso is None, "no hay ingreso verificado"

    verificar(almacen, caso)
    error = error_de(registrar, almacen, caso, 0)  # el ingreso declarado no llega a usarse
    assert (error.tipo, error.codigo) == (TipoError.NEGOCIO, "INGRESO_NO_VERIFICABLE")
    assert error.reintentable is False
    assert set(caso.esperado.datos_faltantes) <= set(error.detalles["datos_faltantes"])
    estado = almacen.leer()
    assert estado["solicitudes"] == {}, "no se registra nada sin ingreso verificado"
    assert estado["escalamientos"] == {}, "se pide el dato, no se escala"


async def resolver_escalar_por_regla(caso: Caso, almacen: AlmacenEstado) -> None:
    """Monto, discrepancia de ingreso o moneda: se registra, no es preaprobable y nada se compromete."""
    s = caso.solicitud
    causa = caso.esperado.causa
    verificar(almacen, caso)
    registro = RegistroNegaciones()
    hook_registro = crear_hook_registro(almacen, registro=registro)
    hook_preaprobacion = crear_hook_preaprobacion(almacen, registro=registro)

    assert (
        await invocar(hook_registro, "registrar_solicitud", id_solicitante=s.id_solicitante) == {}
    )
    registrada = registrar(almacen, caso)
    evaluacion = registrada["evaluacion"]
    assert evaluacion["preaprobable_automaticamente"] is False, evaluacion
    esperada = {Causa.REGLA_2: "regla_2", Causa.REGLA_3: "regla_3", Causa.MONEDA: "moneda"}[causa]
    assert esperada in causas(evaluacion), evaluacion

    guardada = estado_de(almacen, registrada["id_solicitud"])
    if causa is Causa.MONEDA:
        assert evaluacion["decision"] == str(Decision.FUERA_DE_POLITICA)
        assert guardada["ingreso_verificado"] is None, "no se convierte ni se estima ningún ingreso"
    else:
        assert evaluacion["decision"] == str(Decision.ANALISTA)
        assert guardada["ingreso_verificado"] is not None
    if causa is Causa.REGLA_3:
        assert "regla_2" not in causas(evaluacion), "solo escala por la discrepancia"
    if causa is Causa.REGLA_2:
        assert "regla_3" not in causas(evaluacion), "solo escala por la regla 2"

    id_solicitud = registrada["id_solicitud"]
    salida = await invocar(hook_preaprobacion, "preaprobar_credito", id_solicitud=id_solicitud)
    decision, _ = veredicto(salida)
    assert decision == "deny", salida
    assert registro.ultima() is not None
    error = error_de(preaprobar_credito, almacen, id_solicitud)
    assert (error.tipo, error.codigo) == (TipoError.NEGOCIO, "NO_PREAPROBABLE")
    assert estado_de(almacen, id_solicitud)["estado"] == "REGISTRADA", "nada se compromete"


async def resolver_bloquear(caso: Caso, almacen: AlmacenEstado) -> None:
    """Sin identidad verificada nada se registra ni se preaprueba, diga lo que diga el mensaje."""
    s = caso.solicitud
    registro = RegistroNegaciones()
    hook_registro = crear_hook_registro(almacen, registro=registro)
    hook_preaprobacion = crear_hook_preaprobacion(almacen, registro=registro)

    # Regla 1 en el hook: se niega registrar y el core también lo rechaza.
    salida = await invocar(hook_registro, "registrar_solicitud", id_solicitante=s.id_solicitante)
    decision, motivo = veredicto(salida)
    assert decision == "deny" and motivo.startswith("[IDENTIDAD_NO_VERIFICADA]"), salida
    error = error_de(
        registrar_solicitud,
        almacen,
        s.id_solicitante,
        s.monto,
        s.plazo_meses,
        s.ingreso_declarado,
        [doc_certificado(salario=s.ingreso_declarado)],
    )
    assert (error.tipo, error.codigo) == (TipoError.PERMISOS, "IDENTIDAD_NO_VERIFICADA")
    assert almacen.leer()["solicitudes"] == {}

    # Una solicitud ya guardada de alguien cuya identidad no está vigente tampoco se preaprueba.
    persona = solicitante_de(caso)
    verificar_identidad(almacen, persona["id_solicitante"], persona["fecha_nacimiento"], hoy=HOY)
    guardada = registrar_solicitud(
        almacen,
        s.id_solicitante,
        s.monto,
        s.plazo_meses,
        s.ingreso_declarado,
        [doc_certificado(salario=s.ingreso_declarado)],
    )
    with almacen.transaccion() as datos:
        datos["solicitantes"][s.id_solicitante]["verificado_en"] = None
    id_solicitud = guardada["id_solicitud"]
    salida = await invocar(hook_preaprobacion, "preaprobar_credito", id_solicitud=id_solicitud)
    decision, motivo = veredicto(salida)
    assert decision == "deny" and motivo.startswith("[IDENTIDAD_NO_VERIFICADA]"), salida
    error = error_de(preaprobar_credito, almacen, id_solicitud)
    assert (error.tipo, error.codigo) == (TipoError.PERMISOS, "IDENTIDAD_NO_VERIFICADA")
    assert estado_de(almacen, id_solicitud)["estado"] == "REGISTRADA"

    assert [(n.herramienta, n.codigo) for n in registro.listar()] == [
        ("registrar_solicitud", "IDENTIDAD_NO_VERIFICADA"),
        ("preaprobar_credito", "IDENTIDAD_NO_VERIFICADA"),
    ]


def _sin_marcas(valor):
    """Estado sin los campos de momento (`*_en`), que cambian de una ejecución a otra."""
    if isinstance(valor, dict):
        return {k: _sin_marcas(v) for k, v in valor.items() if not k.endswith("_en")}
    if isinstance(valor, list):
        return [_sin_marcas(v) for v in valor]
    return valor


async def _llamar(servidor, herramienta: str, argumentos: dict) -> dict:
    resultado = await servidor.call_tool(herramienta, argumentos)
    assert resultado.is_error is False
    return resultado.structured_content


async def _tramite(servidor, caso: Caso, fallas: int) -> None:
    """Verifica, registra y preaprueba por el servidor MCP; las primeras `fallas` llamadas fallan."""
    s = caso.solicitud
    persona = solicitante_de(caso)
    argumentos = {
        "id_solicitante": s.id_solicitante,
        "fecha_nacimiento": persona["fecha_nacimiento"],
    }
    for _ in range(fallas):
        respuesta = await _llamar(servidor, "verificar_identidad", argumentos)
        assert respuesta["ok"] is False
        assert respuesta["error"]["tipo"] == "transitorio"
        assert respuesta["error"]["reintentable"] is True
    assert (await _llamar(servidor, "verificar_identidad", argumentos))["ok"] is True
    registrada = await _llamar(
        servidor,
        "registrar_solicitud",
        {
            "id_solicitante": s.id_solicitante,
            "monto": s.monto,
            "plazo_meses": s.plazo_meses,
            "ingreso_declarado": s.ingreso_declarado,
            "documentos": documentos_extraidos(caso),
        },
    )
    assert registrada["ok"] is True, registrada
    preaprobada = await _llamar(
        servidor, "preaprobar_credito", {"id_solicitud": registrada["id_solicitud"]}
    )
    assert preaprobada["ok"] is True, preaprobada


async def resolver_reintentar(caso: Caso, almacen: AlmacenEstado) -> None:
    """Una falla transitoria se reintenta y deja el mismo estado que sin falla; el resto no."""
    fallas = caso.falla_simulada
    assert fallas > 0, "un caso de reintento declara cuántas llamadas fallan"
    servidor = crear_servidor(almacen, InyectorFallas(restantes=fallas))
    await _tramite(servidor, caso, fallas)

    referencia = AlmacenEstado(almacen.ruta.with_name("sin_falla.json"))
    await _tramite(crear_servidor(referencia, InyectorFallas()), caso, 0)
    assert _sin_marcas(almacen.leer()) == _sin_marcas(referencia.leer())

    # Un error de negocio o de permisos no es reintentable: reintentar daría el mismo resultado.
    limpio = AlmacenEstado(almacen.ruta.with_name("limpio.json"))
    servidor = crear_servidor(limpio, InyectorFallas())
    inexistente = await _llamar(servidor, "preaprobar_credito", {"id_solicitud": "SLC-9999"})
    assert inexistente["ok"] is False
    assert (inexistente["error"]["tipo"], inexistente["error"]["reintentable"]) == (
        "negocio",
        False,
    )
    s = caso.solicitud
    sin_identidad = await _llamar(
        servidor,
        "registrar_solicitud",
        {
            "id_solicitante": s.id_solicitante,
            "monto": s.monto,
            "plazo_meses": s.plazo_meses,
            "ingreso_declarado": s.ingreso_declarado,
            "documentos": documentos_extraidos(caso),
        },
    )
    assert sin_identidad["ok"] is False
    assert (sin_identidad["error"]["tipo"], sin_identidad["error"]["reintentable"]) == (
        "permisos",
        False,
    )


async def resolver_escalar_humano(caso: Caso, almacen: AlmacenEstado) -> None:
    """Pedir una persona escala de inmediato: sin identidad, sin solicitud y sin otra llamada."""
    almacen.leer()  # el core crea el estado al arrancar
    resumen = {
        "solicitante": "Solicitante sin identificar",
        "monto": None,
        "plazo": None,
        "datos": [],
        "discrepancias": [],
        "causa": "solicitud_humano",
        "detalle": "El solicitante pidió hablar con una persona antes de dar ningún dato.",
        "accion_recomendada": "Contactar al solicitante.",
    }
    escalado = escalar_a_analista(almacen, resumen)
    assert escalado["id_solicitud"] is None
    estado = almacen.leer()
    (escalamiento,) = estado["escalamientos"].values()
    assert escalamiento["resumen"]["causa"] == caso.esperado.causa.value
    assert estado["solicitudes"] == {}
    assert all(s.get("verificado_en") is None for s in estado["solicitantes"].values())

    # Ningún hook bloquea el escalamiento: solo se vigilan registrar y preaprobar.
    matchers = [m.matcher for m in crear_hooks(almacen)["PreToolUse"]]
    assert nombre_herramienta(SERVIDOR_POR_DEFECTO, "escalar_a_analista") not in matchers


async def resolver(caso: Caso, almacen: AlmacenEstado) -> None:
    """Elige el resolutor según el resultado esperado del caso."""
    resultado = caso.esperado.resultado
    if resultado is Resultado.PREAPROBAR:
        await resolver_preaprobar(caso, almacen)
    elif resultado is Resultado.SOLICITAR_DATO:
        await resolver_solicitar_dato(caso, almacen)
    elif resultado is Resultado.BLOQUEAR:
        await resolver_bloquear(caso, almacen)
    elif resultado is Resultado.REINTENTAR:
        await resolver_reintentar(caso, almacen)
    elif caso.esperado.causa is Causa.SOLICITUD_HUMANO:
        await resolver_escalar_humano(caso, almacen)
    else:
        await resolver_escalar_por_regla(caso, almacen)
