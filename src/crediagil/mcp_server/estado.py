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

from filelock import FileLock, Timeout

from crediagil.mcp_server.errores import ErrorCore, TipoError
from crediagil.mcp_server.semilla import SOLICITANTES_SEMILLA

VERSION = 2


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
                "verificado_en": None,
            }
            for s in SOLICITANTES_SEMILLA
        },
        "solicitudes": {},
        "escalamientos": {},
    }


def siguiente_id(coleccion: dict, prefijo: str) -> str:
    """Identificador secuencial `{prefijo}-NNNN`; usar dentro de una transacción."""
    numeros = [int(clave.rsplit("-", 1)[1]) for clave in coleccion if clave.startswith(prefijo)]
    return f"{prefijo}-{max(numeros, default=0) + 1:04d}"


def _migrar(datos: dict) -> dict:
    """v1 → v2 (spec 005 R4): añade colecciones y `verificado_en` sin tocar lo existente."""
    datos.setdefault("solicitudes", {})
    datos.setdefault("escalamientos", {})
    for solicitante in datos["solicitantes"].values():
        solicitante.setdefault("verificado_en", None)
    datos["version"] = VERSION
    return datos


class AlmacenEstado:
    def __init__(self, ruta: Path) -> None:
        self.ruta = Path(ruta)
        self._lock = FileLock(str(self.ruta) + ".lock")

    def leer(self) -> dict:
        with self._lock:
            return self._cargar()

    def leer_existente(self, timeout: float = 5.0) -> dict:
        """Lectura de solo lectura: no crea el archivo ni lo migra en disco (spec 006, R4).

        Falla con `ESTADO_ILEGIBLE` si no existe, está corrupto o el lock no se obtiene a tiempo.
        Es lo que usan los hooks, que deben decidir sobre el estado real sin modificarlo.
        """
        if not self.ruta.exists():
            raise _ilegible()
        try:
            with self._lock.acquire(timeout=timeout):
                return self._cargar(crear=False)
        except (Timeout, OSError) as exc:
            raise _ilegible() from exc

    @contextmanager
    def transaccion(self) -> Iterator[dict]:
        """Bloquea, entrega el estado y lo escribe solo si el bloque termina sin excepción."""
        with self._lock:
            datos = self._cargar()
            yield datos
            self._escribir(datos)

    def reiniciar(self) -> None:
        """Devuelve el estado a la semilla, bajo el bloqueo del archivo (spec 008, R5).

        Sirve aunque el archivo no exista o esté corrupto. Se escribe la semilla en lugar de borrar
        el archivo: el servidor del core puede estar leyéndolo y el bloqueo evita la carrera.
        """
        with self._lock:
            self.ruta.parent.mkdir(parents=True, exist_ok=True)
            self._escribir(estado_semilla())

    def _cargar(self, crear: bool = True) -> dict:
        if not self.ruta.exists():
            if not crear:
                raise _ilegible()
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
        return _migrar(datos)

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
