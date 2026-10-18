"""Comprobaciones sobre el propio repositorio (spec 011, FR-014, SC-005)."""

from __future__ import annotations

import os
import subprocess
import sys

import pytest
from prueba_comun import RAIZ

EXCLUSIONES_OBLIGATORIAS = (".env", ".env.*", "secrets/")


def lineas_del_gitignore() -> set[str]:
    texto = (RAIZ / ".gitignore").read_text(encoding="utf-8")
    return {linea.strip() for linea in texto.splitlines() if linea.strip()}


class TestExclusiones:
    @pytest.mark.parametrize("exclusion", EXCLUSIONES_OBLIGATORIAS)
    def test_gitignore_excluye_los_archivos_de_entorno_y_la_carpeta_de_secretos(self, exclusion):
        assert exclusion in lineas_del_gitignore()


class TestElRepositorioEstaLimpio:
    def test_ningun_archivo_versionado_es_de_entorno_ni_de_secretos(self):
        import scan_repo

        versionados = subprocess.run(
            ["git", "ls-files", "-z"], cwd=RAIZ, capture_output=True, check=True
        ).stdout.decode("utf-8", errors="replace")
        entorno = [
            ruta
            for ruta in versionados.split("\0")
            if ruta and scan_repo.es_archivo_de_entorno(ruta)
        ]
        assert not entorno, f"archivos de entorno o de secretos versionados: {entorno}"

    def test_el_escaner_sobre_el_repositorio_sale_con_cero(self):
        """SC-005: el árbol actual no tiene datos con forma real ni credenciales."""
        proceso = subprocess.run(
            [sys.executable, str(RAIZ / "scripts" / "scan_repo.py")],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            timeout=120,
            env={**os.environ, "PYTHONUTF8": "1"},
        )
        assert proceso.returncode == 0, proceso.stdout + proceso.stderr
        assert "0 hallazgos" in proceso.stdout
