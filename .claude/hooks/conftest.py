"""Arnés de tests de hooks: ejecuta cada hook como subproceso con el evento por stdin."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).parent


def luhn_valid_number(prefix: str, length: int) -> str:
    """Construye en tiempo de ejecución un número ficticio de `length` dígitos válido por Luhn.

    Se genera aquí para que ningún literal con forma de tarjeta quede en el código fuente.
    """
    body = (prefix + "0" * length)[: length - 1]
    total = 0
    for index, char in enumerate(reversed(body)):
        digit = int(char)
        if index % 2 == 0:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return body + str((10 - total % 10) % 10)


@pytest.fixture
def run_hook():
    def _run(
        script_name: str,
        payload: dict | str,
        project_dir: Path,
        extra_env: dict | None = None,
    ) -> tuple[int, str, str]:
        stdin = payload if isinstance(payload, str) else json.dumps(payload)
        env = {**os.environ, "CLAUDE_PROJECT_DIR": str(project_dir), **(extra_env or {})}
        result = subprocess.run(
            [sys.executable, str(HOOKS_DIR / script_name)],
            input=stdin,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
            timeout=30,
        )
        return result.returncode, result.stdout, result.stderr

    return _run
