"""Tests de los archivos estáticos (spec 008, research R2 y R9).

No hay pruebas de navegador: aquí se verifica por texto lo que se puede verificar por código. El
resto del comportamiento del JavaScript lo cubre el recorrido manual de `quickstart.md`.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from importlib.resources import files

import pytest

INSEGURO = [
    r"\binnerHTML\b",
    r"\bouterHTML\b",
    r"\binsertAdjacentHTML\b",
    r"\beval\s*\(",
    r"\bnew\s+Function\b",
    r"\bdocument\.write\b",
]


def _leer(nombre: str) -> str:
    return files("crediagil.chat").joinpath("static", nombre).read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def html() -> str:
    return _leer("index.html")


@pytest.fixture(scope="module")
def js() -> str:
    return _leer("app.js")


@pytest.mark.parametrize("patron", INSEGURO)
def test_el_javascript_no_interpreta_contenido_como_marcado(js, patron):
    assert not re.search(patron, js), f"app.js usa {patron}"


def test_la_pagina_no_tiene_manejadores_en_linea(html):
    assert not re.search(r"\son[a-z]+\s*=", html, re.IGNORECASE)
    assert "javascript:" not in html.lower()


@pytest.mark.parametrize(
    "identificador",
    ["hilo", "formulario", "mensaje", "enviar", "estado-agente", "nueva-conversacion"],
)
def test_la_pagina_tiene_los_elementos_de_la_conversacion(html, identificador):
    assert f'id="{identificador}"' in html


def test_el_hilo_es_un_registro_y_el_indicador_un_estado(html):
    assert re.search(r'id="hilo"[^>]*role="log"|role="log"[^>]*id="hilo"', html)
    assert re.search(
        r'id="estado-agente"[^>]*role="status"|role="status"[^>]*id="estado-agente"', html
    )
    assert 'lang="es"' in html
    assert "viewport" in html


def test_el_contenido_se_inserta_como_texto(js):
    assert "textContent" in js


def test_el_css_conserva_los_saltos_de_linea_y_se_adapta():
    css = _leer("estilos.css")
    assert "pre-wrap" in css
    assert "@media" in css or "max-width" in css


@pytest.mark.skipif(shutil.which("node") is None, reason="Node no está instalado")
def test_el_javascript_tiene_sintaxis_valida(tmp_path):
    archivo = tmp_path / "app.js"
    archivo.write_text(_leer("app.js"), encoding="utf-8")
    resultado = subprocess.run(
        ["node", "--check", str(archivo)], capture_output=True, text=True, check=False
    )
    assert resultado.returncode == 0, resultado.stderr


# ---------------------------------------------------------------- adjuntos (US2)


def test_la_pagina_permite_adjuntar_solo_txt_y_md(html):
    assert 'id="adjuntar"' in html
    assert 'accept=".txt,.md"' in html
    assert "multiple" in html
    assert 'id="adjuntos"' in html
    assert 'id="error-adjuntos"' in html


def test_los_limites_por_defecto_del_javascript_coinciden_con_los_del_servidor(js):
    from crediagil.chat.adjuntos import EXTENSIONES, LIMITE_ADJUNTOS, LIMITE_BYTES_ADJUNTO

    assert re.search(rf"max_adjuntos:\s*{LIMITE_ADJUNTOS}\b", js)
    assert re.search(rf"max_bytes_adjunto:\s*{LIMITE_BYTES_ADJUNTO}\b", js)
    for extension in EXTENSIONES:
        assert f'"{extension}"' in js


def test_el_javascript_envia_los_adjuntos_en_base64(js):
    assert "contenido_b64" in js
    assert "btoa" in js


# ---------------------------------------------------------------- avisos (US3)

TIPOS_DE_AVISO = (
    "credito_preaprobado",
    "informacion_solicitada",
    "escalamiento",
    "bloqueo_regla",
)


@pytest.fixture(scope="module")
def css() -> str:
    return _leer("estilos.css")


@pytest.mark.parametrize("tipo", TIPOS_DE_AVISO)
def test_cada_tipo_de_aviso_tiene_tratamiento_y_estilo_propios(js, css, tipo):
    assert tipo in js, f"app.js no trata el aviso {tipo}"
    assert f".aviso.{tipo}" in css, f"estilos.css no tiene una clase para {tipo}"


def test_los_avisos_se_pintan_con_el_rotulo_de_la_api_y_un_icono(js):
    from crediagil.chat.serializacion import ROTULOS_AVISO

    assert re.search(r"\.rotulo\b", js)
    assert re.search(r"\bICONOS\b", js)
    for rotulo in ROTULOS_AVISO.values():
        assert rotulo not in js, f"app.js repite a mano el rótulo {rotulo!r}"


def test_los_iconos_son_distintos_por_tipo(js):
    bloque = re.search(r"ICONOS\s*=\s*\{(.*?)\}", js, re.DOTALL)
    assert bloque, "falta la tabla ICONOS"
    iconos = re.findall(r':\s*"([^"]+)"', bloque.group(1))
    assert len(iconos) == len(TIPOS_DE_AVISO)
    assert len(set(iconos)) == len(iconos)


def test_los_avisos_salen_solo_de_la_lista_de_avisos_del_turno(js):
    assert "turno.avisos" in js
    # Nunca se deducen del texto de la respuesta.
    for sospechoso in ("preaprob", "escal"):
        assert not re.search(
            rf"respuesta[^\n]*(match|includes|test|indexOf)\([^)]*{sospechoso}", js
        )


# ---------------------------------------------------------------- detalle técnico (US4)


def test_el_detalle_es_un_details_cerrado_con_summary(js):
    assert '"details"' in js
    assert '"summary"' in js
    # Nunca se abre por defecto: ni el atributo ni la propiedad.
    assert not re.search(r"""setAttribute\(\s*["']open["']""", js)
    assert not re.search(r"\.open\s*=\s*true", js)


def test_el_detalle_marca_subagente_y_fallos_y_muestra_parada_y_coste(js, css):
    for campo in ("de_subagente", "es_error", "razon_parada", "costo_usd", "traza"):
        assert campo in js, f"el detalle no usa {campo}"
    assert "Sin llamadas a herramientas" in js
    assert ".subagente" in css and ".fallida" in css


def test_el_detalle_no_rompe_la_pagina_con_textos_largos(css):
    assert re.search(r"\.detalle[^{]*pre[^{]*\{[^}]*overflow", css, re.DOTALL)
    assert "overflow-wrap" in css


# ---------------------------------------------------------------- operación (US5)


@pytest.mark.parametrize(
    "identificador", ["casos", "falla", "reiniciar", "falla-activa", "error-falla"]
)
def test_la_pagina_tiene_los_controles_de_operacion(html, identificador):
    assert f'id="{identificador}"' in html


def test_el_campo_de_falla_es_numerico_de_0_a_20(html):
    campo = re.search(r"<input[^>]*id=\"falla\"[^>]*>", html)
    assert campo, "falta el campo id=falla"
    texto = campo.group(0)
    assert 'type="number"' in texto and 'min="0"' in texto and 'max="20"' in texto


def test_el_javascript_usa_la_api_de_operacion(js):
    assert "/api/casos" in js
    assert "/api/datos/reiniciar" in js
    assert "falla_llamadas" in js
    assert "confirmar: true" in js


def test_reiniciar_pide_confirmacion_antes_de_llamar(js):
    bloque = js[js.index("async function reiniciarDatos") :]
    assert bloque.index("confirm(") < bloque.index("/api/datos/reiniciar")


def test_elegir_un_caso_no_envia_el_mensaje(js):
    bloque = js[js.index("function cargarCaso") : js.index("async function reiniciarDatos")]
    assert "enviar(" not in bloque
    assert "/api/turnos" not in bloque


# ---------------------------------------------------------------- arranque (US6)


def test_la_pagina_tiene_el_aviso_de_sistema(html):
    assert re.search(
        r'id="aviso-sistema"[^>]*role="alert"|role="alert"[^>]*id="aviso-sistema"', html
    )


def test_el_javascript_consulta_el_estado_al_cargar(js):
    assert "/api/estado" in js
    for campo in ("clave_configurada", "estado_core_legible", "limites", "falla_simulada"):
        assert campo in js, f"app.js no usa {campo} del estado"


def test_el_aviso_sin_clave_nombra_la_variable_y_no_muestra_valores(js):
    assert "ANTHROPIC_API_KEY" in js
    assert not re.search(r"sk-[A-Za-z0-9_-]{6,}", js)


def test_el_estado_ilegible_ofrece_reiniciar_los_datos(js):
    bloque = js[js.index("estado_core_legible") :]
    assert "reiniciarDatos" in bloque
