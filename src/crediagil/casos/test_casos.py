"""Un test determinista por caso obligatorio, sin modelo, red ni clave (spec 009, US2).

Cada caso se resuelve con las piezas reales (extracción, core, hooks e inyector de fallas) según el
resultado que declara su carpeta; los resolutores viven en `resolutores.py`.
"""

from __future__ import annotations

import pytest

from crediagil.casos import catalogo
from crediagil.casos.resolutores import (
    resolver,
    resolver_bloquear,
    resolver_escalar_humano,
    resolver_escalar_por_regla,
    resolver_preaprobar,
    resolver_reintentar,
    resolver_solicitar_dato,
)
from crediagil.mcp_server.originacion import extraer

OBLIGATORIOS = catalogo().obligatorios
POR_ID = {caso.id: caso for caso in catalogo().casos}


@pytest.mark.parametrize("caso", OBLIGATORIOS, ids=lambda c: c.id)
@pytest.mark.anyio
async def test_cada_caso_obligatorio_se_resuelve_como_declara_su_carpeta(caso, almacen):
    await resolver(caso, almacen)


# ---------------------------------------------------------------- uno por número del enunciado


@pytest.mark.anyio
async def test_caso_1_documentos_consistentes_se_preaprueban(almacen):
    await resolver_preaprobar(POR_ID["dentro_de_politica"], almacen)


@pytest.mark.anyio
async def test_caso_2_certificado_sin_salario_deja_el_campo_nulo_y_lo_pide(almacen):
    await resolver_solicitar_dato(POR_ID["dato_ausente"], almacen)


@pytest.mark.anyio
async def test_caso_3_ingreso_declarado_discrepante_se_escala(almacen):
    await resolver_escalar_por_regla(POR_ID["ingreso_discrepante"], almacen)


@pytest.mark.anyio
async def test_caso_4_monto_sobre_el_umbral_se_escala(almacen):
    await resolver_escalar_por_regla(POR_ID["monto_sobre_umbral"], almacen)


@pytest.mark.anyio
async def test_caso_5_preaprobar_sin_identidad_lo_bloquean_los_hooks(almacen):
    await resolver_bloquear(POR_ID["preaprobar_sin_identidad"], almacen)


@pytest.mark.anyio
async def test_caso_6_moneda_extranjera_queda_fuera_de_politica(almacen):
    await resolver_escalar_por_regla(POR_ID["moneda_extranjera"], almacen)


@pytest.mark.anyio
async def test_caso_7_la_falla_transitoria_se_reintenta(almacen):
    await resolver_reintentar(POR_ID["falla_transitoria"], almacen)


@pytest.mark.anyio
async def test_caso_8_pedir_una_persona_escala_de_inmediato(almacen):
    """La regla 4 ("sin más preguntas ni consultas") es de juicio: aquí se prueba solo que el
    escalamiento funciona sin identidad, sin solicitud y sin ninguna otra llamada. Que el agente
    no consulte antes se comprueba con el modelo real (`test_vivo.py`)."""
    await resolver_escalar_humano(POR_ID["pedir_persona"], almacen)


@pytest.mark.anyio
async def test_el_complementario_tambien_se_resuelve(almacen):
    await resolver_preaprobar(POR_ID["mensaje_mixto"], almacen)


# ---------------------------------------------------------------- trazabilidad (Principios V y VI)


@pytest.mark.parametrize("caso", catalogo().casos, ids=lambda c: c.id)
def test_cada_dato_extraido_lleva_su_documento_y_su_fragmento(caso):
    for documento in caso.documentos:
        extraido, _ = extraer(documento.extraccion, documento.texto)
        campos = list(extraido.campos_extraidos())
        assert campos, f"{documento.nombre} no tiene ningún dato extraído"
        for nombre, campo in campos:
            assert campo.fragmento in documento.texto, f"{nombre} no es literal"


@pytest.mark.parametrize("caso", catalogo().casos, ids=lambda c: c.id)
def test_lo_que_el_documento_no_trae_queda_nulo(caso):
    for documento in caso.documentos:
        extraido, faltantes = extraer(documento.extraccion, documento.texto)
        for nombre in faltantes:
            assert getattr(extraido, nombre) is None
        # Todo campo extraído aparece de verdad en el texto: no hay valores inventados.
        for _, campo in extraido.campos_extraidos():
            assert campo.fragmento in documento.texto
