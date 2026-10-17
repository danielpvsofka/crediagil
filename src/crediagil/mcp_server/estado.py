"""Estado del core en un archivo JSON local, con lock exclusivo y escritura atómica (FR-013).

Toda lectura o modificación toma el lock; las escrituras van a un temporal en el mismo
directorio y se aplican con `os.replace`, así un fallo a mitad nunca deja el archivo a medias.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from filelock import FileLock

from crediagil.mcp_server.errores import ErrorCore, TipoError
from crediagil.mcp_server.semilla import SOLICITANTES_SEMILLA

VERSION = 1


def ruta_por_defecto() -> Path:
    ruta = os.environ.get("CREDIAGIL_MCP_ESTADO")
    return Path(ruta) if ruta else Path.cwd() / ".data" / "core_estado.json"


def normalizar_documento(documento: str) -> str:
    return "".join(documento.split()).upper()


def estado_semilla() -> dict:
    return {
        "version": VERSION,
        "solicitantes": {
            s["id_solicitante"]: {
                **s,
                "documento": normalizar_documento(s["documento"]),
                "intentos_fallidos": 0,
                "bloqueado": False,
            }
            for s in SOLICITANTES_SEMILLA
        },
    }


class AlmacenEstado:
    def __init__(self, ruta: Path) -> None:
        self.ruta = Path(ruta)
        self._lock = FileLock(str(self.ruta) + ".lock")

    def leer(self) -> dict:
        with self._lock:
            return self._cargar()

    @contextmanager
    def transaccion(self) -> Iterator[dict]:
        """Bloquea, entrega el estado y lo escribe solo si el bloque termina sin excepción."""
        with self._lock:
            datos = self._cargar()
            yield datos
            self._escribir(datos)

    def _cargar(self) -> dict:
        if not self.ruta.exists():
            self.ruta.parent.mkdir(parents=True, exist_ok=True)
            datos = estado_semilla()
            self._escribir(datos)
            return datos
        try:
            datos = json.loads(self.ruta.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise _ilegible() from exc
        if not isinstance(datos, dict) or not isinstance(datos.get("solicitantes"), dict):
            raise _ilegible()
        return datos

    def _escribir(self, datos: dict) -> None:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=self.ruta.parent, suffix=".tmp", delete=False
        ) as temporal:
            json.dump(datos, temporal, ensure_ascii=False, indent=2)
        os.replace(temporal.name, self.ruta)


def _ilegible() -> ErrorCore:
    return ErrorCore(
        TipoError.TRANSITORIO,
        "ESTADO_ILEGIBLE",
        "El estado del core no se pudo leer; inténtalo de nuevo o avisa a soporte.",
    )
