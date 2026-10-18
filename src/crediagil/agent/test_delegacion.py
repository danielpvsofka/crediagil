"""Tests del hook de delegación (spec 007, contracts/agente.md)."""

from __future__ import annotations

import pytest

from crediagil.agent.delegacion import crear_hook_delegacion
from crediagil.agent.documentos import DocumentoAdjunto
from crediagil.agent.negaciones import RegistroNegaciones

pytestmark = pytest.mark.anyio

TEXTO = "Certificado laboral ficticio.\nSalario mensual: 3.000.000 COP."
DOCS = {"DOC-1": DocumentoAdjunto("certificado.txt", TEXTO, "DOC-1")}


def _evento(prompt, subagente="extractor-documentos", tool_name="Agent"):
    entrada = {"description": "extraer", "prompt": prompt}
    if subagente is not None:
        entrada["subagent_type"] = subagente
    return {"hook_event_name": "PreToolUse", "tool_name": tool_name, "tool_input": entrada}


def _codigo(salida):
    motivo = salida["hookSpecificOutput"]["permissionDecisionReason"]
    assert salida["hookSpecificOutput"]["permissionDecision"] == "deny"
    return motivo[1 : motivo.index("]")], motivo


async def _llamar(evento, documentos=DOCS, registro=None):
    return await crear_hook_delegacion(documentos, registro)(evento, "id", {})


async def test_delegacion_completa_pasa():
    prompt = f"documento_id: DOC-1\nnombre: certificado.txt\n\n{TEXTO}"
    assert await _llamar(_evento(prompt)) == {}


async def test_otro_subagente_se_niega():
    codigo, motivo = _codigo(await _llamar(_evento("DOC-1", "general-purpose")))
    assert codigo == "SUBAGENTE_NO_PERMITIDO"
    assert "Acción:" in motivo


async def test_sin_documento_id_conocido():
    codigo, _ = _codigo(await _llamar(_evento(f"certificado.txt\n{TEXTO}")))
    assert codigo == "DOCUMENTO_DESCONOCIDO"


async def test_id_de_otro_documento_no_cuenta_como_conocido():
    codigo, _ = _codigo(await _llamar(_evento(f"DOC-10 certificado.txt\n{TEXTO}")))
    assert codigo == "DOCUMENTO_DESCONOCIDO"


async def test_texto_resumido_es_incompleto():
    codigo, _ = _codigo(await _llamar(_evento("DOC-1 certificado.txt: salario 3 millones")))
    assert codigo == "DELEGACION_INCOMPLETA"


async def test_sin_el_nombre_es_incompleto():
    codigo, _ = _codigo(await _llamar(_evento(f"DOC-1\n{TEXTO}")))
    assert codigo == "DELEGACION_INCOMPLETA"


@pytest.mark.parametrize(
    "tool_input",
    ["texto", None, {"subagent_type": "extractor-documentos"}, {"prompt": 3}, {"prompt": " "}],
)
async def test_entrada_invalida(tool_input):
    evento = {"tool_name": "Agent", "tool_input": tool_input}
    codigo, _ = _codigo(await _llamar(evento))
    assert codigo == "ENTRADA_INVALIDA"


async def test_otra_herramienta_no_tiene_opinion():
    assert await _llamar(_evento("x", tool_name="Read")) == {}


async def test_usa_el_mapa_vivo_de_documentos():
    documentos = {}
    hook = crear_hook_delegacion(documentos)
    prompt = f"DOC-1 certificado.txt\n{TEXTO}"
    codigo, _ = _codigo(await hook(_evento(prompt), "id", {}))
    assert codigo == "DOCUMENTO_DESCONOCIDO"
    documentos.update(DOCS)
    assert await hook(_evento(prompt), "id", {}) == {}


async def test_la_negacion_queda_en_el_registro():
    registro = RegistroNegaciones()
    await _llamar(_evento("DOC-1", "general-purpose"), registro=registro)
    assert registro.ultima().codigo == "SUBAGENTE_NO_PERMITIDO"
    assert registro.ultima().herramienta == "Agent"


async def test_fail_closed_ante_error_interno():
    class Roto(dict):
        def items(self):
            raise RuntimeError("fallo")

    salida = await crear_hook_delegacion(Roto())(_evento(f"DOC-1 {TEXTO}"), "id", {})
    codigo, _ = _codigo(salida)
    assert codigo == "ERROR_INTERNO"


async def test_delegacion_en_segundo_plano_se_niega():
    prompt = f"DOC-1 certificado.txt {TEXTO}"
    evento = _evento(prompt)
    evento["tool_input"]["run_in_background"] = True
    codigo, _ = _codigo(await _llamar(evento))
    assert codigo == "ENTRADA_INVALIDA"
    evento["tool_input"]["run_in_background"] = False
    assert await _llamar(evento) == {}
