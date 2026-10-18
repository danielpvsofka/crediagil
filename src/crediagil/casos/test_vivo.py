"""Pruebas con el modelo real dirigidas por el catálogo (spec 009, US3, research R6).

Opt-in: `uv run pytest -m live -k casos -s`. Consumen saldo de la API: cada una usa un estado
temporal, datos ficticios y un tope de coste. Se saltan si no hay `ANTHROPIC_API_KEY`. Lo esperado
de cada caso está en su carpeta (`esperado.herramientas`) y se comprueba sobre la traza y los
avisos estructurados del turno, nunca sobre las palabras del modelo.
"""

from __future__ import annotations

import os
from dataclasses import replace

import pytest

from crediagil.agent.documentos import DocumentoAdjunto
from crediagil.agent.opciones import ConfigAgente
from crediagil.agent.orquestador import Agente
from crediagil.agent.parada import Parada
from crediagil.casos import catalogo
from crediagil.casos.verificacion import TOPE_USD, herramientas, verificar
from crediagil.config import cargar_entorno

pytestmark = [pytest.mark.live, pytest.mark.anyio]


@pytest.fixture
def config(tmp_path):
    cargar_entorno()
    if not os.environ.get("ANTHROPIC_API_KEY", "").strip():
        pytest.skip("Falta ANTHROPIC_API_KEY: las pruebas con el modelo real no se ejecutan.")
    return ConfigAgente(ruta_estado=tmp_path / "estado.json", max_presupuesto_usd=TOPE_USD)


def mostrar(resultado) -> None:
    """Traza legible para ajustar prompts o expectativas (con -s)."""
    for evento in resultado.traza:
        marca = "  (sub)" if evento.de_subagente else ""
        print(
            f"- {evento.nombre}{marca} entrada={str(evento.entrada)[:200]} "
            f"salida={str(evento.salida)[:300]}"
        )
    print(f"avisos: {[a.tipo for a in resultado.avisos]}")
    print(f"negaciones: {[n.codigo for n in resultado.negaciones]}")
    print(f"respuesta: {resultado.respuesta}")


@pytest.mark.parametrize("caso", catalogo().obligatorios, ids=lambda c: c.id)
async def test_caso_obligatorio_con_el_modelo_real(caso, config):
    if caso.falla_simulada:
        entorno = {"CREDIAGIL_MCP_FALLAS_N": str(caso.falla_simulada)}
        config = replace(config, entorno_core=entorno)
    adjuntos = [DocumentoAdjunto(d.nombre, d.texto) for d in caso.documentos]

    async with Agente(config) as agente:
        resultado = await agente.turno(caso.mensaje, adjuntos)

    mostrar(resultado)
    print(
        f"\n[{caso.id}] costo_usd={resultado.costo_usd} parada={resultado.parada} "
        f"herramientas={[e.nombre for e in herramientas(resultado)]}"
    )
    incumplimientos = verificar(caso, resultado)
    assert incumplimientos == [], incumplimientos
    assert resultado.error is None
    assert resultado.parada is Parada.FIN_DE_TURNO
    assert os.environ["ANTHROPIC_API_KEY"] not in repr(resultado)
