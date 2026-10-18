"""Configuración y clave de la API (spec 007, FR-015).

La clave `ANTHROPIC_API_KEY` se lee del entorno o del archivo local ignorado por git. Nunca se
imprime ni se guarda: toda salida que pueda contenerla pasa por `redactar`.
"""

from __future__ import annotations

import os

from dotenv import find_dotenv, load_dotenv

VARIABLE_CLAVE = "ANTHROPIC_API_KEY"
MARCA_REDACTADO = "[REDACTADO]"


class ConfiguracionError(Exception):
    """Falta una configuración obligatoria."""


def cargar_entorno() -> None:
    """Carga el archivo local del directorio actual sin pisar variables ya definidas."""
    load_dotenv(find_dotenv(usecwd=True), override=False)


def obtener_api_key() -> str:
    clave = os.environ.get(VARIABLE_CLAVE, "").strip()
    if not clave:
        raise ConfiguracionError(
            f"Falta {VARIABLE_CLAVE}: defínela en el entorno o en el archivo local ignorado por git."
        )
    return clave


def redactar(texto: str) -> str:
    """Sustituye el valor de la clave por `[REDACTADO]`; sin clave definida no cambia nada."""
    clave = os.environ.get(VARIABLE_CLAVE, "").strip()
    if not clave or not texto:
        return texto
    return texto.replace(clave, MARCA_REDACTADO)
