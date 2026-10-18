"""Prueba con el modelo real que no es declarativa (spec 007, FR-019; spec 009, research R6).

Opt-in: `uv run pytest -m live -s`. Consume saldo de la API: usa un estado temporal, datos
ficticios y un tope de coste. Se salta si no hay `ANTHROPIC_API_KEY`. Las comprobaciones son sobre
la traza (qué herramientas se llamaron y con qué resultado), nunca sobre las palabras del modelo.

Los escenarios obligatorios (dentro de política, dato ausente, pedir una persona, preaprobar sin
identidad, falla transitoria y el resto) viven en `crediagil/casos/` y los comprueba
`crediagil/casos/test_vivo.py`, dirigido por el catálogo. Aquí queda el mensaje mixto, cuya
aserción (simular un monto sin registrarlo ni preaprobarlo) no se puede declarar en una carpeta.
"""

from __future__ import annotations

import os

import pytest

from crediagil.agent.documentos import DocumentoAdjunto
from crediagil.agent.opciones import ConfigAgente
from crediagil.agent.orquestador import Agente
from crediagil.agent.parada import Parada
from crediagil.casos import catalogo
from crediagil.config import cargar_entorno

pytestmark = [pytest.mark.live, pytest.mark.anyio]

TOPE_USD = 0.75


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def config(tmp_path):
    cargar_entorno()
    if not os.environ.get("ANTHROPIC_API_KEY", "").strip():
        pytest.skip("Falta ANTHROPIC_API_KEY: las pruebas con el modelo real no se ejecutan.")
    return ConfigAgente(ruta_estado=tmp_path / "estado.json", max_presupuesto_usd=TOPE_USD)


def mostrar(r) -> None:
    """Traza legible para ajustar los prompts (con -s)."""
    for e in r.traza:
        marca = "  (sub)" if e.de_subagente else ""
        print(f"- {e.nombre}{marca} entrada={str(e.entrada)[:200]} salida={str(e.salida)[:300]}")
    print(f"respuesta: {r.respuesta}")


def exitosas(resultado, nombre: str) -> list:
    return [
        e
        for e in resultado.traza
        if e.nombre == nombre and isinstance(e.salida, dict) and e.salida.get("ok") is True
    ]


async def test_mensaje_mixto_separa_los_asuntos(config):
    caso = catalogo().por_id("mensaje_mixto")
    adjuntos = [DocumentoAdjunto(d.nombre, d.texto) for d in caso.documentos]
    async with Agente(config) as agente:
        r = await agente.turno(caso.mensaje, adjuntos)

    mostrar(r)
    print(f"\ncosto_usd={r.costo_usd}")
    simulaciones = [e for e in r.traza if e.nombre == "calcular_capacidad_pago"]
    assert any(
        e.entrada.get("monto") == 10_000_000 and e.entrada.get("plazo_meses") == 48
        for e in simulaciones
    ), [e.entrada for e in simulaciones]
    # La pregunta no registra ni preaprueba nada: solo la solicitud real.
    for e in r.traza:
        if e.nombre == "registrar_solicitud":
            assert e.entrada.get("monto") == caso.solicitud.monto, e.entrada
    assert len(exitosas(r, "preaprobar_credito")) <= 1
    assert r.respuesta.strip()
    assert r.parada is Parada.FIN_DE_TURNO
