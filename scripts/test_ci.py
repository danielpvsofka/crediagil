"""Tests del workflow de CI (spec 011, contracts/ci.md).

El workflow se lee como texto: el proyecto no depende de una biblioteca de YAML. Cada comprobación
es una función que recibe el texto y devuelve sus problemas, para poder probarla también con textos
alterados en memoria (controles negativos).
"""

from __future__ import annotations

import re

import pytest
from prueba_comun import RAIZ, parametros_de_la_politica

WORKFLOW = RAIZ / ".github" / "workflows" / "ci.yml"
TRABAJOS = {"formato", "pruebas", "escaneo"}
TIEMPO_MAXIMO_MINUTOS = 10
COMANDOS = (
    "uv sync --group dev --locked",
    "uv run ruff format --check",
    "uv run ruff check",
    "uv run pytest",
    "uv run --no-project python scripts/scan_repo.py --github",
)
PROHIBIDOS = ("secrets.", "ANTHROPIC", "GITHUB_PAT", "-m live")
# `uses: dueño/acción@<40 hexadecimales> # vX.Y.Z`
USO_FIJADO = re.compile(
    r"^\s*(?:-\s*)?uses:\s*[\w.-]+/[\w./-]+@[0-9a-f]{40}\s+#\s*v\d+(?:\.\d+)*\s*$"
)


def problemas_de_disparadores(texto: str) -> list[str]:
    problemas = []
    for evento in ("pull_request", "push"):
        if not re.search(rf"^  {evento}:\s*\n\s+branches:\s*\[main\]", texto, re.MULTILINE):
            problemas.append(f"falta el disparador {evento} para main")
    if not re.search(r"^  workflow_dispatch:", texto, re.MULTILINE):
        problemas.append("falta workflow_dispatch")
    return problemas


def nombres_de_trabajos(texto: str) -> set[str]:
    bloque = texto.split("\njobs:\n", 1)[-1] if "\njobs:\n" in texto else ""
    return set(re.findall(r"^  ([a-z_]+):\s*$", bloque, re.MULTILINE))


def problemas_de_trabajos(texto: str) -> list[str]:
    problemas = []
    nombres = nombres_de_trabajos(texto)
    if nombres != TRABAJOS:
        problemas.append(f"los trabajos deben ser {sorted(TRABAJOS)} y son {sorted(nombres)}")
    if re.search(r"^[ \t]+needs:", texto, re.MULTILINE):
        problemas.append("ningún trabajo debe declarar needs: corren en paralelo")
    return problemas


def problemas_de_permisos_y_tiempos(texto: str) -> list[str]:
    problemas = []
    if not re.search(r"^permissions:\s*\n  contents: read\s*$", texto, re.MULTILINE):
        problemas.append("permissions debe ser solo contents: read a nivel del workflow")
    if re.search(r"^[ \t]+permissions:", texto, re.MULTILINE):
        problemas.append("ningún trabajo debe ampliar los permisos")
    tiempos = [int(minutos) for minutos in re.findall(r"timeout-minutes:\s*(\d+)", texto)]
    if len(tiempos) != len(TRABAJOS):
        problemas.append(f"cada trabajo necesita timeout-minutes (hay {len(tiempos)})")
    if any(tiempo > TIEMPO_MAXIMO_MINUTOS for tiempo in tiempos):
        problemas.append(f"timeout-minutes no puede superar {TIEMPO_MAXIMO_MINUTOS}")
    if "cancel-in-progress: true" not in texto:
        problemas.append("concurrency debe cancelar la ejecución anterior")
    return problemas


def problemas_de_acciones(texto: str) -> list[str]:
    usos = [linea for linea in texto.splitlines() if "uses:" in linea]
    problemas = [
        f"acción sin SHA de 40 hexadecimales y versión: {uso.strip()}"
        for uso in usos
        if not USO_FIJADO.match(uso)
    ]
    if len(usos) != 2 * len(TRABAJOS):
        problemas.append(f"se esperaban {2 * len(TRABAJOS)} usos de acciones y hay {len(usos)}")
    if "persist-credentials: false" not in texto:
        problemas.append("checkout debe llevar persist-credentials: false")
    return problemas


def problemas_de_comandos(texto: str) -> list[str]:
    return [f"falta el comando: {comando}" for comando in COMANDOS if comando not in texto]


def problemas_de_secretos(texto: str) -> list[str]:
    return [f"no debe aparecer: {prohibido}" for prohibido in PROHIBIDOS if prohibido in texto]


def problemas_de_parametros(texto: str) -> list[str]:
    return [
        f"repite un parámetro de la política: {valor}"
        for valor in parametros_de_la_politica()
        if valor in texto
    ]


COMPROBACIONES = {
    "disparadores": problemas_de_disparadores,
    "trabajos": problemas_de_trabajos,
    "permisos y tiempos": problemas_de_permisos_y_tiempos,
    "acciones": problemas_de_acciones,
    "comandos": problemas_de_comandos,
    "secretos": problemas_de_secretos,
    "parámetros": problemas_de_parametros,
}


@pytest.fixture(scope="module")
def texto_ci() -> str:
    return WORKFLOW.read_text(encoding="utf-8").replace("\r\n", "\n")


class TestWorkflow:
    @pytest.mark.parametrize("nombre", COMPROBACIONES)
    def test_cumple_el_contrato(self, texto_ci, nombre):
        problemas = COMPROBACIONES[nombre](texto_ci)
        assert not problemas, "\n".join(problemas)

    def test_las_pruebas_con_el_modelo_real_no_corren_en_ci(self, texto_ci):
        assert "live" not in texto_ci


def mutaciones() -> dict[str, tuple]:
    """Alteraciones del texto y la comprobación que debe detectarlas."""
    return {
        "quitar un trabajo": (lambda t: t.replace("\n  escaneo:", "\n  otro:", 1), "trabajos"),
        "añadir needs": (
            lambda t: t.replace("  pruebas:\n", "  pruebas:\n    needs: formato\n", 1),
            "trabajos",
        ),
        "sha por un tag": (lambda t: re.sub(r"@[0-9a-f]{40}", "@v7", t, count=1), "acciones"),
        "usar secrets": (lambda t: t + "\n      TOKEN: ${{ secrets.X }}\n", "secretos"),
        "subir el tiempo": (
            lambda t: t.replace("timeout-minutes: 10", "timeout-minutes: 11", 1),
            "permisos y tiempos",
        ),
        "ampliar permisos": (
            lambda t: t.replace("contents: read", "contents: write", 1),
            "permisos y tiempos",
        ),
        "quitar un comando": (
            lambda t: t.replace("uv run ruff format --check", "uv run ruff format", 1),
            "comandos",
        ),
        "quitar un disparador": (
            lambda t: t.replace("workflow_dispatch:", "otro_evento:", 1),
            "disparadores",
        ),
        "repetir un parámetro": (
            lambda t: t + f"\n# {parametros_de_la_politica()[0]}\n",
            "parámetros",
        ),
        "pasar la clave del modelo": (lambda t: t + "\n      ANTHROPIC_API_KEY: x\n", "secretos"),
    }


class TestControlesNegativos:
    @pytest.mark.parametrize("nombre", mutaciones())
    def test_la_alteracion_se_detecta(self, texto_ci, nombre):
        alterar, comprobacion = mutaciones()[nombre]
        alterado = alterar(texto_ci)
        assert alterado != texto_ci, f"la alteración «{nombre}» no cambió el texto"
        assert COMPROBACIONES[comprobacion](alterado), f"«{nombre}» no fue detectada"

    def test_el_texto_original_no_se_modifica_entre_pruebas(self, texto_ci):
        assert all(not comprobar(texto_ci) for comprobar in COMPROBACIONES.values())
