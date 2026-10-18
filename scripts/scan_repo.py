"""Escáner de datos con forma real, archivos de entorno y credenciales (spec 011).

Recorre los archivos del repositorio y falla (código 1) si encuentra algo. Los datos con forma
real (tarjeta, cédula, cuenta) los detecta el mismo código que el hook `block_sensitive_data`:
aquí no se copia ninguna de sus reglas. El informe nunca reproduce el valor encontrado.

Uso: uv run --no-project python scripts/scan_repo.py [--github] [--raiz RUTA]
Códigos de salida: 0 sin hallazgos, 1 con hallazgos, 2 si no pudo ejecutarse.
"""

from __future__ import annotations

import argparse
import importlib
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

# Repositorio que contiene este script: de él se carga el detector, aunque `--raiz` apunte a otro.
RAIZ_DEL_SCRIPT = Path(__file__).resolve().parents[1]

# Archivos que no se escanean, con el motivo. Se comparan por nombre de archivo.
EXCLUIDOS = {
    "uv.lock": "archivo generado: las rutas de descarga con hashes coinciden con la etiqueta de cédula",
}

# Extensiones de archivos de claves o certificados privados.
EXTENSIONES_DE_SECRETOS = (".pem", ".key", ".p12", ".pfx")

# Formas de credencial reconocidas (data-model.md). Se escriben como expresiones, no como cadenas con
# forma de credencial, para que este archivo pase su propio escaneo. El marcador `dato-ficticio`
# NO exime una credencial: ninguna lo es.
CREDENCIALES = {
    "anthropic": re.compile(r"(?<![A-Za-z0-9_-])sk-ant-[A-Za-z0-9_-]{20,}"),
    "github": re.compile(r"(?<![A-Za-z0-9_])gh[pousr]_[A-Za-z0-9]{36}(?![A-Za-z0-9])"),
    "github_fino": re.compile(r"(?<![A-Za-z0-9_])github_pat_[A-Za-z0-9_]{22,}"),
    "aws": re.compile(r"(?<![A-Za-z0-9])AKIA[0-9A-Z]{16}(?![0-9A-Z])"),
    "clave_privada": re.compile(r"-----BEGIN (?:[A-Z]+ )*PRIVATE KEY-----"),
}


class ErrorDeEscaneo(Exception):
    """El escáner no pudo ejecutarse (código de salida 2)."""


@dataclass(frozen=True)
class Hallazgo:
    """Una cosa encontrada. Nunca contiene el valor."""

    archivo: str
    linea: int
    tipo: str

    def __str__(self) -> str:
        return f"{self.archivo}:{self.linea}: {self.tipo}"


def listar_archivos(raiz: Path) -> list[str]:
    """Versionados y nuevos no ignorados, con `/` como separador y ordenados."""
    if not raiz.is_dir():
        raise ErrorDeEscaneo(f"la raíz {raiz} no existe")
    try:
        proceso = subprocess.run(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            cwd=raiz,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise ErrorDeEscaneo("git no está instalado o no está en el PATH") from exc
    if proceso.returncode != 0:
        raise ErrorDeEscaneo(f"{raiz} no es un repositorio git")
    nombres = proceso.stdout.decode("utf-8", errors="replace").split("\0")
    return sorted({nombre for nombre in nombres if nombre})


def es_archivo_de_entorno(ruta: str) -> bool:
    """Archivo de entorno o de secretos por el nombre de su ruta (separada con `/`)."""
    partes = PurePosixPath(ruta).parts
    if not partes:
        return False
    nombre = partes[-1]
    if nombre == ".env" or nombre.startswith(".env."):
        return True
    if "secrets" in partes[:-1]:
        return True
    return nombre.lower().endswith(EXTENSIONES_DE_SECRETOS)


def buscar_credenciales(linea: str) -> list[str]:
    """Nombres de las credenciales que la línea parece contener; nunca sus valores."""
    return [nombre for nombre, patron in CREDENCIALES.items() if patron.search(linea)]


def leer_texto(ruta: Path) -> str | None:
    """Contenido como UTF-8 con sustitución de bytes inválidos; `None` si es binario o ilegible."""
    try:
        datos = ruta.read_bytes()
    except OSError:
        return None
    if b"\0" in datos:
        return None
    return datos.decode("utf-8", errors="replace")


def cargar_detector():
    """`find_in_line` y `MARCADOR` del hook, cargados solo cuando hacen falta.

    La importación es diferida porque la biblioteca del hook reconfigura `stdin` al cargarse y eso
    falla dentro de pytest; así los tests de lo puro pueden importar este módulo sin cargarlo.
    """
    hooks = str(RAIZ_DEL_SCRIPT / ".claude" / "hooks")
    if hooks not in sys.path:
        sys.path.insert(0, hooks)
    try:
        modulo = importlib.import_module("block_sensitive_data")
    except Exception as exc:  # cualquier fallo de carga impide escanear
        raise ErrorDeEscaneo(f"no se pudo cargar el detector del hook: {exc}") from exc
    return modulo.find_in_line, modulo.MARCADOR


def hallazgos_de_datos(archivo: str, texto: str, detector, marcador: str) -> set[Hallazgo]:
    """Datos con forma real por línea, sin el valor y sin las líneas con el marcador."""
    encontrados: set[Hallazgo] = set()
    for numero, linea in enumerate(texto.splitlines(), start=1):
        if marcador in linea:
            continue
        for tipo, _valor in detector(linea):
            encontrados.add(Hallazgo(archivo, numero, tipo))
    return encontrados


def hallazgos_de_credenciales(archivo: str, texto: str) -> set[Hallazgo]:
    """Credenciales por línea, sin el valor y sin exención por marcador."""
    return {
        Hallazgo(archivo, numero, "credencial")
        for numero, linea in enumerate(texto.splitlines(), start=1)
        if buscar_credenciales(linea)
    }


def escanear(raiz: Path) -> tuple[int, list[Hallazgo]]:
    """Número de archivos de texto leídos y hallazgos ordenados por archivo y línea."""
    nombres = listar_archivos(raiz)
    detector, marcador = cargar_detector()
    escaneados = 0
    hallazgos: set[Hallazgo] = set()
    for nombre in nombres:
        if es_archivo_de_entorno(nombre):
            # El problema es el archivo, no una línea; su contenido no se lee.
            hallazgos.add(Hallazgo(nombre, 0, "archivo_de_entorno"))
            continue
        if Path(nombre).name in EXCLUIDOS:
            continue
        texto = leer_texto(raiz / nombre)
        if texto is None:
            continue
        escaneados += 1
        hallazgos |= hallazgos_de_datos(nombre, texto, detector, marcador)
        hallazgos |= hallazgos_de_credenciales(nombre, texto)
    return escaneados, sorted(hallazgos, key=lambda h: (h.archivo, h.linea, h.tipo))


def anotacion_de_github(hallazgo: Hallazgo) -> str:
    """Anotación de GitHub Actions para que el hallazgo salga en la línea del cambio."""
    linea = max(hallazgo.linea, 1)
    return (
        f"::error file={hallazgo.archivo},line={linea}::"
        f"{hallazgo.tipo} detectado (el valor no se muestra)"
    )


def informe(escaneados: int, hallazgos: list[Hallazgo], github: bool) -> str:
    lineas = [str(hallazgo) for hallazgo in hallazgos]
    if github:
        lineas += [anotacion_de_github(hallazgo) for hallazgo in hallazgos]
    lineas.append(f"{escaneados} archivos escaneados, {len(hallazgos)} hallazgos")
    return "\n".join(lineas)


def main(argv: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    analizador.add_argument(
        "--github", action="store_true", help="emite anotaciones ::error de GitHub Actions"
    )
    analizador.add_argument(
        "--raiz",
        type=Path,
        default=RAIZ_DEL_SCRIPT,
        help="repositorio a escanear (por defecto, el que contiene el script)",
    )
    opciones = analizador.parse_args(argv)
    try:
        escaneados, hallazgos = escanear(opciones.raiz)
    except ErrorDeEscaneo as exc:
        print(f"scan_repo: {exc}", file=sys.stderr)
        return 2
    print(informe(escaneados, hallazgos, opciones.github))
    return 1 if hallazgos else 0


if __name__ == "__main__":
    sys.exit(main())
