"""Tests de la documentación de entrega (spec 011): README y DECISIONES.md.

Cada comprobación es una función que recibe el texto y devuelve sus problemas, para probarla también
con textos alterados en memoria (controles negativos).
"""

from __future__ import annotations

import re

import pytest
from prueba_comun import RAIZ, parametros_de_la_politica

README = RAIZ / "README.md"
URL_DEL_PROJECT = "https://github.com/users/danielpvsofka/projects/1"
URL_DEL_CLON = "https://github.com/danielpvsofka/crediagil.git"
VIDEO = re.compile(r"https://youtu\.be/[\w-]+")
COMANDOS_DEL_README = (
    "uv sync --group dev",
    "uv run pytest",
    "uv run python -m crediagil.chat",
    "uv run ruff format --check",
    "uv run ruff check",
    "uv run --no-project python scripts/scan_repo.py",
)


def leer(ruta) -> str:
    return ruta.read_text(encoding="utf-8").replace("\r\n", "\n")


def problemas_del_readme(texto: str) -> list[str]:
    problemas = []
    if URL_DEL_PROJECT not in texto:
        problemas.append("falta el enlace al Project")
    if not VIDEO.search(texto):
        problemas.append("falta el enlace al video de funcionamiento (o está vacío)")
    problemas += [
        f"falta el comando: {comando}" for comando in COMANDOS_DEL_README if comando not in texto
    ]
    if "ANTHROPIC_API_KEY" not in texto:
        problemas.append("falta explicar cómo se aporta ANTHROPIC_API_KEY")
    if "ignorado por git" not in texto:
        problemas.append("falta decir que la clave no se versiona (ignorado por git)")
    if URL_DEL_CLON not in texto:
        problemas.append("falta la URL real del clon")
    if "<repo>" in texto:
        problemas.append("queda el marcador <repo> en lugar de la URL del clon")
    if "actions/workflows/ci.yml" not in texto:
        problemas.append("falta la insignia del workflow de CI")
    problemas += [
        f"repite un parámetro de la política: {valor}"
        for valor in parametros_de_la_politica()
        if valor in texto
    ]
    return problemas


@pytest.fixture(scope="module")
def texto_del_readme() -> str:
    return leer(README)


class TestReadme:
    def test_cumple_lo_exigido(self, texto_del_readme):
        problemas = problemas_del_readme(texto_del_readme)
        assert not problemas, "\n".join(problemas)

    def test_el_enlace_del_video_no_es_un_marcador_de_posicion(self, texto_del_readme):
        enlace = VIDEO.search(texto_del_readme).group()
        assert len(enlace) > len("https://youtu.be/") + 5, enlace


def mutaciones_del_readme() -> dict[str, tuple]:
    return {
        "quitar el enlace del Project": (
            lambda t: t.replace(URL_DEL_PROJECT, "", 1),
            "falta el enlace al Project",
        ),
        "quitar el enlace del video": (lambda t: VIDEO.sub("", t), "falta el enlace al video"),
        "vaciar el enlace del video": (
            lambda t: VIDEO.sub("https://youtu.be/", t),
            "falta el enlace al video",
        ),
        "quitar un comando": (
            lambda t: t.replace("uv run pytest", "uv pytest"),
            "falta el comando: uv run pytest",
        ),
        "quitar el comando del escaneo": (
            lambda t: t.replace("scripts/scan_repo.py", "scripts/otro.py"),
            "scan_repo.py",
        ),
        "volver al marcador <repo>": (
            lambda t: t.replace(URL_DEL_CLON, "<repo>"),
            "falta la URL real del clon",
        ),
        "quitar la insignia": (lambda t: t.replace("actions/workflows/ci.yml", "x"), "insignia"),
        "repetir un parámetro": (
            lambda t: t + f"\n{parametros_de_la_politica()[0]}\n",
            "parámetro de la política",
        ),
    }


class TestControlesNegativosDelReadme:
    @pytest.mark.parametrize("nombre", mutaciones_del_readme())
    def test_la_alteracion_se_detecta(self, texto_del_readme, nombre):
        alterar, fragmento = mutaciones_del_readme()[nombre]
        alterado = alterar(texto_del_readme)
        assert alterado != texto_del_readme, f"«{nombre}» no cambió el texto"
        problemas = problemas_del_readme(alterado)
        assert any(fragmento in problema for problema in problemas), (nombre, problemas)


# --- DECISIONES.md: dos páginas, con todas las necesidades (US4) ----------------------------------

DECISIONES = RAIZ / "DECISIONES.md"
LIMITE_DE_PALABRAS = 1000  # equivalente a dos páginas (spec.md «Assumptions»)
NECESIDADES = tuple(range(1, 12))  # las 11 necesidades del ecosistema
CELDAS_CON_CONTENIDO = 4  # número, necesidad, mecanismo y motivo
FILA_NUMERADA = re.compile(r"^\| *(\d+) *\|", re.MULTILINE)


def contar_palabras(texto: str) -> int:
    """Palabras del texto; los símbolos de las tablas no cuentan, los acentos sí."""
    return len(re.findall(r"\w+", texto))


def filas_de_necesidades(texto: str) -> dict[int, list[str]]:
    """Celdas de cada fila numerada de la tabla de necesidades."""
    filas = {}
    for linea in texto.splitlines():
        coincidencia = FILA_NUMERADA.match(linea)
        if coincidencia:
            filas[int(coincidencia.group(1))] = [
                c.strip() for c in linea.strip().strip("|").split("|")
            ]
    return filas


def problemas_de_decisiones(texto: str) -> list[str]:
    problemas = []
    palabras = contar_palabras(texto)
    if palabras > LIMITE_DE_PALABRAS:
        problemas.append(f"supera el límite: {palabras} palabras (máximo {LIMITE_DE_PALABRAS})")
    filas = filas_de_necesidades(texto)
    if tuple(sorted(filas)) != NECESIDADES:
        problemas.append(
            f"deben estar las necesidades {NECESIDADES} y están {tuple(sorted(filas))}"
        )
    for numero, celdas in filas.items():
        con_contenido = [celda for celda in celdas if celda]
        if len(con_contenido) < CELDAS_CON_CONTENIDO:
            problemas.append(f"la necesidad {numero} no tiene mecanismo y motivo")
    problemas += [
        f"repite un parámetro de la política: {valor}"
        for valor in parametros_de_la_politica()
        if valor in texto
    ]
    pendiente = re.search(r"#1[01][^\n]*pendiente|pendiente[^\n]*#1[01]", texto, re.IGNORECASE)
    if pendiente:
        problemas.append(f"presenta como pendiente el CI o el plugin: «{pendiente.group()[:60]}»")
    return problemas


@pytest.fixture(scope="module")
def texto_de_decisiones() -> str:
    return leer(DECISIONES)


class TestContarPalabras:
    """El borde del límite: 1.000 palabras pasa, 1.001 no."""

    @pytest.mark.parametrize(
        ("cantidad", "supera"), [(LIMITE_DE_PALABRAS, False), (LIMITE_DE_PALABRAS + 1, True)]
    )
    def test_el_limite_exacto(self, cantidad, supera):
        texto = " ".join(["palabra"] * cantidad)
        assert contar_palabras(texto) == cantidad
        assert (contar_palabras(texto) > LIMITE_DE_PALABRAS) is supera

    def test_los_simbolos_de_una_tabla_no_cuentan(self):
        assert contar_palabras("| 1 | uno | dos | tres |\n|---|---|---|---|") == 4

    def test_los_acentos_cuentan_como_parte_de_la_palabra(self):
        assert contar_palabras("conversación ñandú óptica") == 3


class TestDecisiones:
    def test_cumple_lo_exigido(self, texto_de_decisiones):
        problemas = problemas_de_decisiones(texto_de_decisiones)
        assert not problemas, "\n".join(problemas)

    def test_tiene_las_once_necesidades_con_mecanismo_y_motivo(self, texto_de_decisiones):
        filas = filas_de_necesidades(texto_de_decisiones)
        assert tuple(sorted(filas)) == NECESIDADES
        assert all(
            len([c for c in celdas if c]) >= CELDAS_CON_CONTENIDO for celdas in filas.values()
        )


def mutaciones_de_decisiones() -> dict[str, tuple]:
    def vaciar_la_fila_4(texto: str) -> str:
        return re.sub(
            r"^\| *4 *\|.*$", "| 4 | Sin código sin spec | | |", texto, flags=re.MULTILINE
        )

    def quitar_la_fila_7(texto: str) -> str:
        return re.sub(r"^\| *7 *\|.*\n", "", texto, flags=re.MULTILINE)

    return {
        "duplicar el documento": (lambda t: t + "\n" + t, "supera el límite"),
        "pasar de 1.000 a 1.001": (
            lambda t: (
                t + " " + " ".join(["relleno"] * (LIMITE_DE_PALABRAS - contar_palabras(t) + 1))
            ),
            "supera el límite",
        ),
        "quitar una necesidad": (quitar_la_fila_7, "deben estar las necesidades"),
        "vaciar mecanismo y motivo": (vaciar_la_fila_4, "la necesidad 4 no tiene mecanismo"),
        "repetir un parámetro": (
            lambda t: t + f"\n{parametros_de_la_politica()[0]}\n",
            "parámetro de la política",
        ),
        "presentar el CI como pendiente": (
            lambda t: t + "\nEl CI (issue #11) está pendiente.\n",
            "pendiente",
        ),
        "presentar el plugin como pendiente": (
            lambda t: t + "\nPlugin (issue #10, **pendiente**).\n",
            "pendiente",
        ),
    }


class TestControlesNegativosDeDecisiones:
    @pytest.mark.parametrize("nombre", mutaciones_de_decisiones())
    def test_la_alteracion_se_detecta(self, texto_de_decisiones, nombre):
        alterar, fragmento = mutaciones_de_decisiones()[nombre]
        alterado = alterar(texto_de_decisiones)
        assert alterado != texto_de_decisiones, f"«{nombre}» no cambió el texto"
        problemas = problemas_de_decisiones(alterado)
        assert any(fragmento in problema for problema in problemas), (nombre, problemas)
