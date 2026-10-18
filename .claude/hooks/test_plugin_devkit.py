"""Tests de integridad del plugin `crediagil-devkit` (spec 010, contracts/plugin.md).

Ningún número con forma real aparece como literal: todo se construye en tiempo de ejecución.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest
from conftest import HOOKS_DIR, luhn_valid_number
from test_reviewers_config import WRITE_TOOLS, tool_set, top_level

RAIZ = Path(__file__).resolve().parents[2]
PLUGIN = RAIZ / "plugins" / "crediagil-devkit"
CATALOGO = RAIZ / ".claude-plugin" / "marketplace.json"
SETTINGS = RAIZ / ".claude" / "settings.json"
HOOK_EMPAQUETADO = PLUGIN / "hooks" / "block_sensitive_data.py"
NOMBRE = "crediagil-devkit"
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def cargar_json(ruta: Path) -> dict:
    return json.loads(ruta.read_text(encoding="utf-8"))


def matcher_de_settings() -> str:
    """`matcher` con el que `.claude/settings.json` registra block_sensitive_data."""
    for entrada in cargar_json(SETTINGS)["hooks"]["PreToolUse"]:
        if any("block_sensitive_data.py" in h["command"] for h in entrada["hooks"]):
            return entrada["matcher"]
    raise AssertionError("settings.json no registra block_sensitive_data")


class TestEstructura:
    @pytest.mark.parametrize(
        "relativa",
        [
            ".claude-plugin/plugin.json",
            "agents/code-reviewer.md",
            "agents/compliance-reviewer.md",
            "skills/compliance-check/SKILL.md",
            "hooks/hooks.json",
            "hooks/block_sensitive_data.py",
            "hooks/_hooklib.py",
            "README.md",
        ],
    )
    def test_existe_la_pieza(self, relativa):
        assert (PLUGIN / relativa).is_file(), f"falta en el plugin: {relativa}"

    def test_el_catalogo_esta_en_la_raiz(self):
        assert CATALOGO.is_file(), "falta .claude-plugin/marketplace.json en la raíz"


class TestManifiestos:
    def test_plugin_json(self):
        plugin = cargar_json(PLUGIN / ".claude-plugin" / "plugin.json")
        assert plugin["name"] == NOMBRE
        assert SEMVER.match(plugin["version"]), plugin["version"]
        assert plugin["description"].strip()

    def test_catalogo(self):
        catalogo = cargar_json(CATALOGO)
        assert catalogo["name"].strip()
        assert catalogo["owner"]["name"].strip()
        entradas = [p for p in catalogo["plugins"] if p["name"] == NOMBRE]
        assert len(entradas) == 1, "el catálogo debe listar crediagil-devkit una sola vez"
        assert entradas[0]["source"] == f"./plugins/{NOMBRE}"

    def test_la_ruta_del_catalogo_existe_y_es_un_plugin(self):
        entrada = cargar_json(CATALOGO)["plugins"][0]
        carpeta = RAIZ / entrada["source"]
        assert (carpeta / ".claude-plugin" / "plugin.json").is_file()

    def test_versiones_coinciden(self):
        plugin = cargar_json(PLUGIN / ".claude-plugin" / "plugin.json")
        entrada = cargar_json(CATALOGO)["plugins"][0]
        assert entrada["version"] == plugin["version"]
        assert entrada["description"] == plugin["description"]

    def test_hooks_json_apunta_a_un_script_del_plugin(self):
        entradas = cargar_json(PLUGIN / "hooks" / "hooks.json")["hooks"]["PreToolUse"]
        assert len(entradas) == 1
        assert entradas[0]["matcher"] == matcher_de_settings()
        comandos = [h["command"] for h in entradas[0]["hooks"]]
        assert len(comandos) == 1
        assert "${CLAUDE_PLUGIN_ROOT}/hooks/block_sensitive_data.py" in comandos[0]
        assert HOOK_EMPAQUETADO.is_file()


def evento(contenido: str) -> dict:
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": "Write",
        "tool_input": {"file_path": "tests/fixture.py", "content": contenido},
    }


def tarjeta() -> str:
    return luhn_valid_number("4", 16)


def cedula() -> str:
    return "cédula: " + "1" * 10


def cuenta() -> str:
    return "cuenta de ahorros " + "2" * 11


CASOS_HOOK = {
    "tarjeta_valida": (lambda: f"numero = '{tarjeta()}'\n", 2),
    "cedula_con_etiqueta": (lambda: f"cliente = {{'{cedula()}'}}\n", 2),
    "cuenta_con_etiqueta": (lambda: f"{cuenta()}\n", 2),
    "cedula_con_marcador": (lambda: f"{cedula()}  # dato-ficticio\n", 0),
    "numero_largo_sin_etiqueta": (lambda: "valor = " + "7" * 12 + "\n", 0),
    "texto_sin_datos": (lambda: "def suma(a, b):\n    return a + b\n", 0),
}


class TestHookEmpaquetado:
    """SC-004 y FR-004: el hook del plugin se comporta igual que el de este repositorio."""

    @pytest.mark.parametrize("caso", CASOS_HOOK)
    def test_resultado_esperado(self, run_hook, tmp_path, caso):
        construir, esperado = CASOS_HOOK[caso]
        codigo, _, stderr = run_hook(str(HOOK_EMPAQUETADO), evento(construir()), tmp_path)
        assert codigo == esperado, caso
        if esperado == 2:
            # Un script inexistente también sale con 2: exigir el motivo del propio hook.
            assert "[block_sensitive_data]" in stderr, stderr

    @pytest.mark.parametrize("caso", CASOS_HOOK)
    def test_igual_que_el_original(self, run_hook, tmp_path, caso):
        construir, _ = CASOS_HOOK[caso]
        carga = evento(construir())
        empaquetado = run_hook(str(HOOK_EMPAQUETADO), carga, tmp_path)
        original = run_hook(str(HOOKS_DIR / "block_sensitive_data.py"), carga, tmp_path)
        assert empaquetado == original, caso

    def test_evento_malformado_falla_cerrado(self, run_hook, tmp_path):
        codigo, _, stderr = run_hook(str(HOOK_EMPAQUETADO), "esto no es json", tmp_path)
        assert codigo == 2
        assert "[block_sensitive_data]" in stderr


# --- Qué se empaqueta, qué se excluye y cómo se compara (data-model.md) ---------------------


@dataclass(frozen=True)
class Pieza:
    """Pieza empaquetada: `original` relativo a `.claude/`, `copia` relativo al plugin.

    Sin sustituciones la copia es idéntica al original; con ellas es una variante declarada
    (research.md R3): el original con cada par (antes, después) aplicado exactamente una vez.
    """

    original: str
    copia: str
    sustituciones: tuple[tuple[str, str], ...] = ()


# Un plugin ignora `hooks` en el frontmatter de un subagente: sin este bloque el revisor deja de
# poder ejecutar pytest y queda de solo lectura en lugar de con `Bash` sin restricción.
BLOQUE_HOOKS_DEL_REVISOR = (
    "hooks:\n"
    "  PreToolUse:\n"
    '    - matcher: "Bash"\n'
    "      hooks:\n"
    "        - type: command\n"
    '          command: uv run --no-project python "$CLAUDE_PROJECT_DIR/.claude/hooks/'
    'allow_only_pytest.py"\n'
)

EMPAQUETADAS = (
    Pieza(
        "agents/code-reviewer.md",
        "agents/code-reviewer.md",
        ((" Solo lectura. Lo invoca /open-pr.\n", " Solo lectura.\n"),),
    ),
    Pieza(
        "agents/compliance-reviewer.md",
        "agents/compliance-reviewer.md",
        (
            (" Lectura y pytest.", " Solo lectura."),
            ("tools: Read, Grep, Glob, Bash\n", "tools: Read, Grep, Glob\n"),
            (BLOQUE_HOOKS_DEL_REVISOR, ""),
        ),
    ),
    Pieza(
        "skills/compliance-check/SKILL.md",
        "skills/compliance-check/SKILL.md",
        (
            (
                " La invoca /open-pr cuando el diff toca lógica de negocio.",
                " Úsala cuando el diff toca lógica de negocio.",
            ),
            ("agent: compliance-reviewer\n", "agent: crediagil-devkit:compliance-reviewer\n"),
            (", Bash(uv run pytest:*)", ""),
        ),
    ),
    Pieza("hooks/block_sensitive_data.py", "hooks/block_sensitive_data.py"),
    Pieza("hooks/_hooklib.py", "hooks/_hooklib.py"),
)

# Archivos propios del plugin, sin original en `.claude/`.
PROPIOS = frozenset({".claude-plugin/plugin.json", "hooks/hooks.json", "README.md"})

# Lo que NO se empaqueta, con el motivo. Cada entrada es un nombre de archivo o de carpeta;
# `speckit-` es un prefijo (las skills de Spec Kit).
EXCLUIDAS = {
    "require_specs.py": "exige la estructura de Spec Kit de este repositorio",
    "format_python.py": "formato de Python de este repositorio (ruff)",
    "block_secret_access.py": "supuestos del repositorio sobre archivos de secretos; futuro",
    "allow_only_pytest.py": "solo lo usa el frontmatter del revisor, que un plugin ignora",
    "open-pr.md": "flujo de tickets de este repositorio",
    "ticket": "flujo de tickets de este repositorio",
    "speckit-": "skills instaladas por Spec Kit, no son piezas propias",
}
# Carpetas de `.claude/` que se inventarían (rules/ y settings.json no son piezas).
CARPETAS_INVENTARIADAS = ("agents", "commands", "skills", "hooks")


@dataclass(frozen=True)
class Incumplimiento:
    pieza: str
    archivo: str
    motivo: str

    def __str__(self) -> str:
        return f"{self.motivo}: {self.pieza} ({self.archivo})"


def texto(ruta: Path) -> str:
    """Texto del archivo sin diferencias de fin de línea (FR-008)."""
    return ruta.read_bytes().decode("utf-8").replace("\r\n", "\n")


def es_excluida(relativa: str) -> bool:
    partes = Path(relativa).parts
    return any(
        parte == nombre or (nombre.endswith("-") and parte.startswith(nombre))
        for parte in partes
        for nombre in EXCLUIDAS
    )


def archivos(base: Path) -> set[str]:
    """Rutas relativas (con `/`) de los archivos bajo `base`, sin cachés."""
    return {
        ruta.relative_to(base).as_posix()
        for ruta in base.rglob("*")
        if ruta.is_file() and "__pycache__" not in ruta.parts
    }


def inventario_de_claude(claude: Path) -> set[str]:
    """Piezas de `.claude/` que hay que clasificar: sin tests ni `conftest.py`."""
    piezas = set()
    for carpeta in CARPETAS_INVENTARIADAS:
        base = claude / carpeta
        if not base.is_dir():
            continue
        for relativa in archivos(base):
            nombre = Path(relativa).name
            if nombre.startswith("test_") or nombre == "conftest.py":
                continue
            piezas.add(f"{carpeta}/{relativa}")
    return piezas


def comparar(pieza: Pieza, claude: Path, plugin: Path) -> list[Incumplimiento]:
    original, copia = claude / pieza.original, plugin / pieza.copia
    destino = f"plugins/{NOMBRE}/{pieza.copia}"
    if not original.is_file():
        return [Incumplimiento(pieza.original, f".claude/{pieza.original}", "falta el original")]
    if not copia.is_file():
        return [Incumplimiento(pieza.original, destino, "falta en el plugin")]
    esperado = texto(original)
    for antes, despues in pieza.sustituciones:
        if esperado.count(antes) != 1:
            archivo = f".claude/{pieza.original}"
            return [Incumplimiento(pieza.original, archivo, "sustitución no aplica")]
        esperado = esperado.replace(antes, despues)
    if texto(copia) != esperado:
        return [Incumplimiento(pieza.original, destino, "diverge")]
    return []


def comprobar(raiz: Path) -> list[Incumplimiento]:
    """Todos los incumplimientos del plugin frente a `.claude/` bajo `raiz`."""
    claude, plugin = raiz / ".claude", raiz / "plugins" / NOMBRE
    incumplimientos: list[Incumplimiento] = []
    for pieza in EMPAQUETADAS:
        incumplimientos += comparar(pieza, claude, plugin)
    originales = {pieza.original for pieza in EMPAQUETADAS}
    for relativa in sorted(inventario_de_claude(claude) - originales):
        if not es_excluida(relativa):
            incumplimientos.append(
                Incumplimiento(relativa, f".claude/{relativa}", "sin clasificar")
            )
    permitidos = {pieza.copia for pieza in EMPAQUETADAS} | PROPIOS
    for relativa in sorted(archivos(plugin) - permitidos):
        motivo = "excluida presente" if es_excluida(relativa) else "sobra en el plugin"
        incumplimientos.append(Incumplimiento(relativa, f"plugins/{NOMBRE}/{relativa}", motivo))
    return incumplimientos


def informe(incumplimientos: list[Incumplimiento]) -> str:
    return "el plugin diverge de .claude/:\n" + "\n".join(f"  - {i}" for i in incumplimientos)


class TestDivergencia:
    """Contrato filas 1–7: copias, variantes, faltantes, sobrantes y clasificación."""

    def test_el_plugin_no_diverge_de_claude(self):
        incumplimientos = comprobar(RAIZ)
        assert not incumplimientos, informe(incumplimientos)

    @pytest.mark.parametrize("pieza", EMPAQUETADAS, ids=lambda pieza: pieza.original)
    def test_cada_pieza_coincide_con_su_original(self, pieza):
        incumplimientos = comparar(pieza, RAIZ / ".claude", PLUGIN)
        assert not incumplimientos, informe(incumplimientos)

    def test_lo_excluido_no_esta_en_el_plugin(self):
        presentes = [ruta for ruta in archivos(PLUGIN) if es_excluida(ruta)]
        assert not presentes, f"excluidas presentes en el plugin: {presentes}"

    def test_toda_pieza_de_claude_esta_clasificada(self):
        originales = {pieza.original for pieza in EMPAQUETADAS}
        sin_clasificar = [
            ruta
            for ruta in inventario_de_claude(RAIZ / ".claude")
            if ruta not in originales and not es_excluida(ruta)
        ]
        assert not sin_clasificar, f"sin clasificar (empaquetar o excluir): {sin_clasificar}"


# --- Controles negativos: sobre una copia temporal, nunca sobre el árbol real ---------------


@pytest.fixture
def arbol(tmp_path) -> Path:
    """Copia de `.claude/` y del plugin en un directorio temporal."""
    ignorar = shutil.ignore_patterns("__pycache__")
    shutil.copytree(RAIZ / ".claude", tmp_path / ".claude", ignore=ignorar)
    shutil.copytree(RAIZ / "plugins", tmp_path / "plugins", ignore=ignorar)
    return tmp_path


def a_crlf(datos: bytes) -> bytes:
    """Fin de línea `\\r\\n` sin duplicar el `\\r` de un clon con `autocrlf` que ya lo trae."""
    return datos.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")


def motivos(raiz: Path) -> set[tuple[str, str]]:
    return {(i.motivo, i.pieza) for i in comprobar(raiz)}


class TestControlesNegativos:
    """La comprobación falla donde debe y no por el fin de línea: no pasa por no mirar."""

    def test_el_arbol_copiado_esta_limpio(self, arbol):
        assert comprobar(arbol) == []

    def test_un_byte_distinto_en_una_copia(self, arbol):
        copia = arbol / "plugins" / NOMBRE / "agents" / "code-reviewer.md"
        copia.write_bytes(copia.read_bytes() + b"x")
        assert motivos(arbol) == {("diverge", "agents/code-reviewer.md")}

    def test_un_byte_distinto_en_un_original(self, arbol):
        original = arbol / ".claude" / "hooks" / "_hooklib.py"
        original.write_bytes(original.read_bytes() + b"# x\n")
        assert motivos(arbol) == {("diverge", "hooks/_hooklib.py")}

    def test_falta_una_copia(self, arbol):
        (arbol / "plugins" / NOMBRE / "hooks" / "block_sensitive_data.py").unlink()
        assert motivos(arbol) == {("falta en el plugin", "hooks/block_sensitive_data.py")}

    def test_falta_un_original(self, arbol):
        (arbol / ".claude" / "agents" / "code-reviewer.md").unlink()
        assert motivos(arbol) == {("falta el original", "agents/code-reviewer.md")}

    def test_sobra_un_archivo_en_el_plugin(self, arbol):
        (arbol / "plugins" / NOMBRE / "extra.md").write_text("x", encoding="utf-8")
        assert motivos(arbol) == {("sobra en el plugin", "extra.md")}

    def test_pieza_nueva_sin_clasificar(self, arbol):
        (arbol / ".claude" / "agents" / "nuevo.md").write_text("x", encoding="utf-8")
        assert motivos(arbol) == {("sin clasificar", "agents/nuevo.md")}

    @pytest.mark.parametrize(
        "relativa", ["commands/open-pr.md", "hooks/require_specs.py", "skills/ticket/SKILL.md"]
    )
    def test_una_pieza_excluida_en_el_plugin(self, arbol, relativa):
        destino = arbol / "plugins" / NOMBRE / relativa
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(arbol / ".claude" / relativa, destino)
        assert {motivo for motivo, _ in motivos(arbol)} == {"excluida presente"}

    def test_una_sustitucion_que_deja_de_aplicar(self, arbol):
        original = arbol / ".claude" / "agents" / "compliance-reviewer.md"
        cambiado = texto(original).replace(
            "tools: Read, Grep, Glob, Bash\n", "tools: Read, Grep, Glob, Bash, Write\n"
        )
        original.write_text(cambiado, encoding="utf-8")
        assert motivos(arbol) == {("sustitución no aplica", "agents/compliance-reviewer.md")}

    def test_solo_cambia_el_fin_de_linea_de_un_original(self, arbol):
        for original in (arbol / ".claude" / "agents").glob("*.md"):
            original.write_bytes(a_crlf(original.read_bytes()))
        assert comprobar(arbol) == []

    def test_solo_cambia_el_fin_de_linea_de_una_copia(self, arbol):
        copia = arbol / "plugins" / NOMBRE / "hooks" / "_hooklib.py"
        copia.write_bytes(a_crlf(copia.read_bytes()))
        assert comprobar(arbol) == []


class TestRevisoresEmpaquetados:
    """Fila 10, Principio II: sin hook que lo restrinja, un revisor empaquetado no ejecuta ni escribe."""

    @pytest.mark.parametrize("nombre", ["code-reviewer", "compliance-reviewer"])
    def test_el_subagente_es_de_solo_lectura(self, nombre):
        ruta = PLUGIN / "agents" / f"{nombre}.md"
        campos = top_level(ruta)
        assert not tool_set(campos["tools"]) & (WRITE_TOOLS | {"Bash"}), ruta
        assert "hooks" not in campos, f"un plugin ignora `hooks` en un subagente: {ruta}"

    def test_la_skill_usa_el_subagente_con_espacio_de_nombres(self):
        campos = top_level(PLUGIN / "skills" / "compliance-check" / "SKILL.md")
        assert campos["agent"] == f"{NOMBRE}:compliance-reviewer"
        assert campos["context"] == "fork"
        permitidas = campos["allowed-tools"]
        assert not {herramienta.split("(")[0] for herramienta in tool_set(permitidas)} & WRITE_TOOLS
        assert "pytest" not in permitidas, "el revisor empaquetado no ejecuta pytest"


# --- Aislamiento: nada propio de este repositorio viaja con el plugin (US3) -----------------

# Recursos que existen aquí y no en el repositorio consumidor. Quedan permitidas, porque son
# convenciones del consumidor que el README documenta: la constitución en
# `.specify/memory/constitution.md`, `src/`, `specs/` y la rama `main`.
REFERENCIAS_PROHIBIDAS = (
    "$CLAUDE_PROJECT_DIR/.claude",
    ".claude/hooks/",
    ".claude/commands",
    "/ticket",
    "/open-pr",
    "require_spec",
    "allow_only_pytest",
    "block_secret_access",
    "format_python",
)


def textos_del_plugin(plugin: Path) -> dict[str, str]:
    return {relativa: texto(plugin / relativa) for relativa in sorted(archivos(plugin))}


def referencias_propias(plugin: Path) -> list[str]:
    """Referencias a piezas o rutas de este repositorio dentro del plugin."""
    return [
        f"{relativa}: {prohibida}"
        for relativa, contenido in textos_del_plugin(plugin).items()
        for prohibida in REFERENCIAS_PROHIBIDAS
        if prohibida in contenido
    ]


def formatos_pesos(monto: int) -> list[str]:
    return [f"{monto:,}".replace(",", "."), f"{monto:,}", str(monto)]


def formatos_porcentaje(proporcion) -> list[str]:
    numero = f"{(proporcion * 100).normalize():f}"
    variantes = {numero, numero.replace(".", ",")}
    return [f"{variante}{separador}%" for variante in variantes for separador in ("", " ")]


def parametros_de_la_politica() -> list[str]:
    from crediagil.policy import params

    return [
        *formatos_pesos(params.MONTO_MAXIMO_PREAPROBACION),
        *formatos_porcentaje(params.TASA_MENSUAL),
        *formatos_porcentaje(params.PROPORCION_MAXIMA_CUOTA_INGRESO),
        *formatos_porcentaje(params.DISCREPANCIA_MAXIMA_INGRESO),
    ]


def parametros_en(plugin: Path) -> list[str]:
    """La tasa y los umbrales no se repiten fuera de la constitución y de la política."""
    return [
        f"{relativa}: {valor}"
        for relativa, contenido in textos_del_plugin(plugin).items()
        for valor in parametros_de_la_politica()
        if valor in contenido
    ]


def datos_con_forma_real(plugin: Path) -> list[str]:
    """Archivos que el propio hook empaquetado bloquearía (tarjeta, cédula o cuenta)."""
    hallazgos = []
    for relativa, contenido in textos_del_plugin(plugin).items():
        resultado = subprocess.run(
            [sys.executable, str(plugin / "hooks" / "block_sensitive_data.py")],
            input=json.dumps(evento(contenido)),
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            timeout=30,
        )
        if resultado.returncode != 0:
            hallazgos.append(f"{relativa}: {resultado.stderr.strip()}")
    return hallazgos


class TestAislamiento:
    """Contrato filas 11 y FR-006: sin piezas del repositorio, sin parámetros, sin datos reales."""

    def test_no_hay_piezas_de_este_repositorio(self):
        propias = [ruta for ruta in archivos(PLUGIN) if es_excluida(ruta)]
        assert not propias, f"piezas propias de este repositorio en el plugin: {propias}"

    def test_no_referencia_recursos_que_no_viajan(self):
        assert not referencias_propias(PLUGIN)

    def test_no_repite_la_tasa_ni_los_umbrales(self):
        assert not parametros_en(PLUGIN)

    def test_no_contiene_datos_con_forma_real(self):
        assert not datos_con_forma_real(PLUGIN)


class TestControlesNegativosDeAislamiento:
    def test_una_referencia_a_un_recurso_propio(self, arbol):
        agente = arbol / "plugins" / NOMBRE / "agents" / "code-reviewer.md"
        agente.write_text(
            texto(agente) + "\nVer .claude/hooks/ del repositorio.\n", encoding="utf-8"
        )
        assert referencias_propias(arbol / "plugins" / NOMBRE) == [
            "agents/code-reviewer.md: .claude/hooks/"
        ]

    def test_la_tasa_dentro_del_plugin(self, arbol):
        from crediagil.policy import params

        readme = arbol / "plugins" / NOMBRE / "README.md"
        tasa = formatos_porcentaje(params.TASA_MENSUAL)[0]
        readme.write_text(texto(readme) + f"\nLa tasa es {tasa}.\n", encoding="utf-8")
        assert parametros_en(arbol / "plugins" / NOMBRE) == [f"README.md: {tasa}"]

    def test_una_tarjeta_dentro_del_plugin(self, arbol):
        readme = arbol / "plugins" / NOMBRE / "README.md"
        readme.write_text(texto(readme) + f"\nEjemplo: {tarjeta()}\n", encoding="utf-8")
        hallazgos = datos_con_forma_real(arbol / "plugins" / NOMBRE)
        assert len(hallazgos) == 1
        assert hallazgos[0].startswith("README.md:")

    def test_una_pieza_de_tickets_dentro_del_plugin(self, arbol):
        destino = arbol / "plugins" / NOMBRE / "skills" / "ticket" / "SKILL.md"
        destino.parent.mkdir(parents=True)
        destino.write_text("x", encoding="utf-8")
        assert [i.motivo for i in comprobar(arbol)] == ["excluida presente"]


# --- README del plugin (US4, FR-009) ----------------------------------------------------------

LEE_EN_EL_README = {
    "añadir el catálogo": "/plugin marketplace add",
    "instalar": f"/plugin install {NOMBRE}@crediagil",
    "actualizar": "/plugin marketplace update crediagil",
    "subagente de código": f"{NOMBRE}:code-reviewer",
    "skill de cumplimiento": f"/{NOMBRE}:compliance-check",
    "hook de datos": "block_sensitive_data",
    "requisito uv": "`uv`",
    "constitución del consumidor": ".specify/memory/constitution.md",
    "rama base": "`main`",
    "código en src": "`src/`",
    "sin constitución": "VEREDICTO: BLOQUEANTE",
    "marcador": "dato-ficticio",
    "convivencia con piezas del mismo nombre": "mismo nombre",
    "limitación del revisor": "solo lectura",
    "no ejecuta pytest": "pytest",
}


class TestReadme:
    @pytest.mark.parametrize("tema", LEE_EN_EL_README)
    def test_el_readme_cubre(self, tema):
        contenido = texto(PLUGIN / "README.md")
        assert LEE_EN_EL_README[tema] in contenido, f"el README no cubre: {tema}"

    def test_lista_cada_pieza_con_una_linea(self):
        contenido = texto(PLUGIN / "README.md")
        for pieza in ("code-reviewer", "compliance-reviewer", "compliance-check"):
            lineas = [linea for linea in contenido.splitlines() if pieza in linea]
            assert lineas, f"el README no menciona {pieza}"

    def test_no_nombra_piezas_que_no_incluye(self):
        contenido = texto(PLUGIN / "README.md")
        for nombre in ("require_specs", "open-pr", "format_python", "speckit"):
            assert nombre not in contenido, nombre
