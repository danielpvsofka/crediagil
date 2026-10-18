"""Tests del escáner `scripts/scan_repo.py` (spec 011, contracts/escaneo.md).

Todo dato con forma real se construye en ejecución: ningún literal con forma de tarjeta, cédula,
cuenta o credencial queda en este archivo. El escáner se ejecuta por subproceso sobre un
repositorio git temporal porque el detector del hook no se puede importar dentro de pytest
(su biblioteca reconfigura `stdin` al cargarse).
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest
from prueba_comun import RAIZ, tarjeta_ficticia

SCRIPT = RAIZ / "scripts" / "scan_repo.py"
MARCADOR = "dato-ficticio"

CEDULA = "cédula: " + "1" * 10
CUENTA = "cuenta de ahorros " + "2" * 11


def linea_de_tarjeta() -> str:
    return f"numero = {tarjeta_ficticia()}"


# Línea con forma real → (tipo esperado, valor que nunca debe aparecer en un informe)
DATOS = {
    "tarjeta": (linea_de_tarjeta, "tarjeta"),
    "documento": (lambda: CEDULA, "documento"),
    "cuenta": (lambda: CUENTA, "cuenta"),
}


def solo_digitos(texto: str) -> str:
    return "".join(caracter for caracter in texto if caracter.isdigit())


@dataclass
class Resultado:
    codigo: int
    salida: str
    error: str

    @property
    def informe(self) -> str:
        return self.salida + self.error


class Repo:
    """Repositorio git temporal sobre el que se ejecuta el escáner."""

    def __init__(self, raiz: Path):
        self.raiz = raiz

    def anadir(self, nombre: str, contenido: str | bytes) -> Path:
        ruta = self.raiz / nombre
        ruta.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(contenido, bytes):
            ruta.write_bytes(contenido)
        else:
            ruta.write_text(contenido, encoding="utf-8")
        return ruta

    def git(self, *argumentos: str) -> None:
        subprocess.run(["git", *argumentos], cwd=self.raiz, check=True, capture_output=True)

    def ejecutar(self, *opciones: str, raiz: Path | None = None) -> Resultado:
        entorno = {
            **os.environ,
            "PYTHONUTF8": "1",
            # Un directorio sin .git no debe resolverse hacia un repositorio que lo contenga.
            "GIT_CEILING_DIRECTORIES": str(self.raiz.parent),
        }
        proceso = subprocess.run(
            [sys.executable, str(SCRIPT), "--raiz", str(raiz or self.raiz), *opciones],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            env=entorno,
            timeout=60,
        )
        return Resultado(proceso.returncode, proceso.stdout, proceso.stderr)


@pytest.fixture
def repo_git(tmp_path) -> Repo:
    repo = Repo(tmp_path)
    repo.git("init", "-q")
    repo.git("config", "user.name", "Persona Ficticia")
    repo.git("config", "user.email", "persona@ejemplo.invalid")
    return repo


def hallazgos(resultado: Resultado) -> list[str]:
    """Líneas `archivo:línea: tipo` del informe (sin el resumen ni las anotaciones)."""
    return [
        linea
        for linea in resultado.salida.splitlines()
        if linea and not linea.startswith("::") and ": " in linea and linea.count(":") >= 2
    ]


class TestEscanerBase:
    def test_repositorio_limpio(self, repo_git):
        repo_git.anadir("README.md", "Texto sin datos.\n")
        resultado = repo_git.ejecutar()
        assert resultado.codigo == 0, resultado.informe
        assert "0 hallazgos" in resultado.salida
        assert hallazgos(resultado) == []

    @pytest.mark.parametrize("tipo", DATOS)
    def test_detecta_el_dato_con_su_archivo_y_su_linea(self, repo_git, tipo):
        construir, esperado = DATOS[tipo]
        repo_git.anadir("datos.txt", f"primera línea limpia\n{construir()}\ntercera línea\n")
        resultado = repo_git.ejecutar()
        assert resultado.codigo == 1, resultado.informe
        assert hallazgos(resultado) == [f"datos.txt:2: {esperado}"]

    @pytest.mark.parametrize("tipo", DATOS)
    def test_el_marcador_exime_la_linea(self, repo_git, tipo):
        construir, _ = DATOS[tipo]
        repo_git.anadir("datos.txt", f"{construir()}  # {MARCADOR}\n")
        resultado = repo_git.ejecutar()
        assert resultado.codigo == 0, resultado.informe

    def test_el_marcador_solo_exime_su_propia_linea(self, repo_git):
        repo_git.anadir("datos.txt", f"{CEDULA}  # {MARCADOR}\n{CEDULA}\n")
        resultado = repo_git.ejecutar()
        assert resultado.codigo == 1
        assert hallazgos(resultado) == ["datos.txt:2: documento"]

    def test_varios_archivos_salen_ordenados(self, repo_git):
        repo_git.anadir("b.txt", f"{CEDULA}\n")
        repo_git.anadir("a.txt", f"x\n{CUENTA}\n")
        resultado = repo_git.ejecutar()
        assert hallazgos(resultado) == ["a.txt:2: cuenta", "b.txt:1: documento"]
        assert "2 hallazgos" in resultado.salida

    def test_uv_lock_se_ignora(self, repo_git):
        repo_git.anadir("uv.lock", f"{CEDULA}\n")
        resultado = repo_git.ejecutar()
        assert resultado.codigo == 0, resultado.informe

    def test_el_mismo_contenido_en_otro_archivo_falla(self, repo_git):
        repo_git.anadir("otro.lock", f"{CEDULA}\n")
        repo_git.anadir("sub/uv.lock", f"{CEDULA}\n")
        resultado = repo_git.ejecutar()
        assert resultado.codigo == 1
        assert hallazgos(resultado) == ["otro.lock:1: documento"]

    def test_un_archivo_binario_se_omite(self, repo_git):
        repo_git.anadir("datos.bin", b"\x00\x01" + CEDULA.encode("utf-8"))
        resultado = repo_git.ejecutar()
        assert resultado.codigo == 0, resultado.informe

    def test_un_archivo_no_utf8_no_rompe_el_escaneo(self, repo_git):
        repo_git.anadir("latin.txt", "acción sin datos\n".encode("latin-1"))
        resultado = repo_git.ejecutar()
        assert resultado.codigo == 0, resultado.informe

    def test_un_archivo_nuevo_sin_git_add_se_escanea(self, repo_git):
        repo_git.anadir("nuevo.txt", f"{CEDULA}\n")
        assert repo_git.ejecutar().codigo == 1

    def test_un_archivo_versionado_se_escanea(self, repo_git):
        repo_git.anadir("versionado.txt", f"{CEDULA}\n")
        repo_git.git("add", "versionado.txt")
        resultado = repo_git.ejecutar()
        assert hallazgos(resultado) == ["versionado.txt:1: documento"]

    def test_un_archivo_ignorado_por_gitignore_no_se_escanea(self, repo_git):
        repo_git.anadir(".gitignore", "ignorado.txt\n")
        repo_git.anadir("ignorado.txt", f"{CEDULA}\n")
        resultado = repo_git.ejecutar()
        assert resultado.codigo == 0, resultado.informe


class TestElInformeNoRevelaElValor:
    @pytest.mark.parametrize("tipo", DATOS)
    @pytest.mark.parametrize("opciones", [(), ("--github",)])
    def test_ni_el_valor_ni_una_parte_de_seis_caracteres(self, repo_git, tipo, opciones):
        construir, _ = DATOS[tipo]
        valor = solo_digitos(construir())
        repo_git.anadir("datos.txt", f"{construir()}\n")
        resultado = repo_git.ejecutar(*opciones)
        assert resultado.codigo == 1
        for inicio in range(len(valor) - 5):
            assert valor[inicio : inicio + 6] not in resultado.informe, tipo

    def test_la_anotacion_de_github_lleva_archivo_y_linea(self, repo_git):
        repo_git.anadir("sub/datos.txt", f"x\ny\n{CEDULA}\n")
        resultado = repo_git.ejecutar("--github")
        anotaciones = [linea for linea in resultado.salida.splitlines() if linea.startswith("::")]
        assert len(anotaciones) == 1
        assert anotaciones[0].startswith("::error file=sub/datos.txt,line=3::")

    def test_sin_la_opcion_github_no_hay_anotaciones(self, repo_git):
        repo_git.anadir("datos.txt", f"{CEDULA}\n")
        resultado = repo_git.ejecutar()
        assert resultado.codigo == 1
        assert "::error" not in resultado.salida


class TestCodigosDeSalida:
    def test_un_directorio_que_no_es_un_repositorio_git(self, tmp_path):
        sin_git = tmp_path / "sin_git"
        sin_git.mkdir()
        resultado = Repo(sin_git).ejecutar()
        assert resultado.codigo == 2
        assert "repositorio git" in resultado.error

    def test_una_raiz_inexistente(self, tmp_path):
        resultado = Repo(tmp_path).ejecutar(raiz=tmp_path / "no_existe")
        assert resultado.codigo == 2
        assert "no existe" in resultado.error

    def test_una_opcion_desconocida_no_se_confunde_con_hallazgos(self, repo_git):
        resultado = repo_git.ejecutar("--no-existe")
        assert resultado.codigo not in (0, 1)
        assert "--no-existe" in resultado.error


# --- Archivos de entorno y credenciales (US2) -----------------------------------------------------

CICLO = "Xq7Zp2Lm9Vk4Rt8Wn3Yc5Hd6Fg1Bs0J"


def relleno(longitud: int) -> str:
    """Caracteres alfanuméricos variados, para que ninguna subcadena se repita en el informe."""
    return (CICLO * (longitud // len(CICLO) + 1))[:longitud]


def clave_anthropic(longitud: int) -> str:
    return "sk-ant-" + relleno(longitud)


def token_github(longitud: int) -> str:
    return "ghp_" + relleno(longitud)


def token_github_fino(longitud: int) -> str:
    return "github_pat_" + relleno(longitud)


def clave_aws(longitud: int) -> str:
    return "AKIA" + relleno(longitud).upper()


def cabecera_pem(algoritmo: str = "") -> str:
    return "-----BEGIN " + algoritmo + "PRIVATE KEY" + "-----"


class TestArchivosDeEntorno:
    @pytest.mark.parametrize(
        "ruta",
        [
            ".env",
            "config/.env",
            ".env.local",
            "servicios/api/.env.production",
            "secrets/clave.txt",
            "a/secrets/b/c.txt",
            "certs/servidor.pem",
            "certs/Servidor.PEM",
            "claves/firma.key",
            "claves/almacen.p12",
            "claves/almacen.pfx",
        ],
    )
    def test_es_un_archivo_de_entorno_o_de_secretos(self, ruta):
        import scan_repo

        assert scan_repo.es_archivo_de_entorno(ruta), ruta

    @pytest.mark.parametrize(
        "ruta",
        [
            "environment.md",
            "env.py",
            "docs/secretos.md",
            "secrets.md",
            "monkey.py",
            "certs/servidor.pem.md",
            "config/entorno.env.md",
            "README.md",
        ],
    )
    def test_un_nombre_parecido_no_lo_es(self, ruta):
        import scan_repo

        assert not scan_repo.es_archivo_de_entorno(ruta), ruta

    @pytest.mark.parametrize("ruta", [".env", "config/.env.local", "secrets/clave.txt", "x/y.pem"])
    def test_falla_con_tipo_y_linea_cero(self, repo_git, ruta):
        repo_git.anadir(ruta, "contenido\n")
        resultado = repo_git.ejecutar()
        assert resultado.codigo == 1, resultado.informe
        assert hallazgos(resultado) == [f"{ruta}:0: archivo_de_entorno"]

    def test_no_se_lee_el_contenido_de_un_archivo_de_entorno(self, repo_git):
        repo_git.anadir(".env", f"{CEDULA}\n")
        resultado = repo_git.ejecutar()
        assert hallazgos(resultado) == [".env:0: archivo_de_entorno"]

    def test_los_nombres_parecidos_no_fallan(self, repo_git):
        for nombre in ("environment.md", "env.py", "docs/secretos.md", "monkey.py"):
            repo_git.anadir(nombre, "texto sin datos\n")
        resultado = repo_git.ejecutar()
        assert resultado.codigo == 0, resultado.informe

    def test_un_archivo_de_entorno_ignorado_por_gitignore_no_falla(self, repo_git):
        repo_git.anadir(".gitignore", ".env\n")
        repo_git.anadir(".env", "contenido\n")
        resultado = repo_git.ejecutar()
        assert resultado.codigo == 0, resultado.informe


class TestCredenciales:
    """Bordes exactos de longitud de data-model.md «Credenciales reconocidas»."""

    @pytest.mark.parametrize(
        ("construir", "longitud", "esperado"),
        [
            (clave_anthropic, 19, False),
            (clave_anthropic, 20, True),
            (clave_anthropic, 21, True),
            (clave_anthropic, 80, True),
            (token_github, 35, False),
            (token_github, 36, True),
            (token_github, 37, False),
            (token_github_fino, 21, False),
            (token_github_fino, 22, True),
            (token_github_fino, 82, True),
            (clave_aws, 15, False),
            (clave_aws, 16, True),
            (clave_aws, 17, False),
        ],
        ids=lambda valor: getattr(valor, "__name__", str(valor)),
    )
    def test_el_borde_de_longitud(self, construir, longitud, esperado):
        import scan_repo

        linea = f"valor = '{construir(longitud)}'"
        assert bool(scan_repo.buscar_credenciales(linea)) is esperado, linea

    @pytest.mark.parametrize("prefijo", ["gho_", "ghu_", "ghs_", "ghr_"])
    def test_los_otros_prefijos_de_token_de_github(self, prefijo):
        import scan_repo

        assert scan_repo.buscar_credenciales(prefijo + relleno(36))
        assert not scan_repo.buscar_credenciales(prefijo + relleno(35))

    @pytest.mark.parametrize("algoritmo", ["", "RSA ", "EC ", "OPENSSH ", "ENCRYPTED "])
    def test_cabecera_de_clave_privada(self, algoritmo):
        import scan_repo

        assert scan_repo.buscar_credenciales(cabecera_pem(algoritmo))

    @pytest.mark.parametrize(
        "linea",
        [
            "texto sin credenciales",
            "sk-ant- sin cuerpo",
            "export CLAVE=${ANTHROPIC_API_KEY}",
            "Authorization: Bearer ${GITHUB_PAT}",
            "-----BEGIN CERTIFICATE-----",
            "AKIA en minúsculas: akia" + relleno(16).lower(),
        ],
    )
    def test_texto_sin_forma_de_credencial(self, linea):
        import scan_repo

        assert not scan_repo.buscar_credenciales(linea), linea

    def test_las_credenciales_no_se_devuelven_por_valor(self):
        import scan_repo

        valor = clave_anthropic(30)
        assert all(valor not in nombre for nombre in scan_repo.buscar_credenciales(valor))

    @pytest.mark.parametrize(
        "construir",
        [
            lambda: clave_anthropic(30),
            lambda: token_github(36),
            lambda: token_github_fino(30),
            lambda: clave_aws(16),
            lambda: cabecera_pem("RSA "),
        ],
    )
    def test_falla_con_archivo_y_linea(self, repo_git, construir):
        repo_git.anadir("config.txt", f"primera\nclave = {construir()}\n")
        resultado = repo_git.ejecutar()
        assert resultado.codigo == 1, resultado.informe
        assert hallazgos(resultado) == ["config.txt:2: credencial"]

    def test_el_marcador_no_exime_una_credencial(self, repo_git):
        repo_git.anadir("config.txt", f"clave = {clave_anthropic(30)}  # {MARCADOR}\n")
        resultado = repo_git.ejecutar()
        assert resultado.codigo == 1
        assert hallazgos(resultado) == ["config.txt:1: credencial"]

    def test_una_credencial_y_un_dato_en_la_misma_linea(self, repo_git):
        repo_git.anadir("mezcla.txt", f"{CEDULA} {clave_anthropic(30)}  # {MARCADOR}\n")
        resultado = repo_git.ejecutar()
        assert hallazgos(resultado) == ["mezcla.txt:1: credencial"]

    @pytest.mark.parametrize("opciones", [(), ("--github",)])
    @pytest.mark.parametrize(
        "valor",
        [clave_anthropic(30), token_github(36), token_github_fino(30), clave_aws(16)],
        ids=["anthropic", "github", "github_fino", "aws"],
    )
    def test_el_informe_no_revela_la_credencial(self, repo_git, valor, opciones):
        repo_git.anadir("config.txt", f"clave = {valor}\n")
        resultado = repo_git.ejecutar(*opciones)
        assert resultado.codigo == 1
        for inicio in range(len(valor) - 5):
            assert valor[inicio : inicio + 6] not in resultado.informe

    def test_el_codigo_del_escaner_no_coincide_con_sus_propios_patrones(self):
        """El escáner debe poder escanearse a sí mismo sin hallazgos."""
        import scan_repo

        for linea in (RAIZ / "scripts" / "scan_repo.py").read_text(encoding="utf-8").splitlines():
            assert not scan_repo.buscar_credenciales(linea), linea
