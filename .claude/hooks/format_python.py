"""PostToolUse: formatea con ruff cada archivo .py creado o editado.

Nunca bloquea (nunca sale con 2): si ruff no está disponible o falla, avisa con salida 1.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from _hooklib import HookInputError, project_root, read_event, target_path

HOOK = "format_python"


def warn(message: str) -> None:
    print(f"[{HOOK}] {message}", file=sys.stderr)
    sys.exit(1)


def run_ruff(root: Path, file: str) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            ["uv", "run", "--quiet", "--project", str(root), "ruff", "format", file],
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except FileNotFoundError:
        # Sin uv: se intenta ruff del PATH. Si tampoco existe, FileNotFoundError sube.
        return subprocess.run(
            ["ruff", "format", file], check=False, capture_output=True, text=True, timeout=60
        )


def main() -> None:
    try:
        event = read_event()
    except HookInputError as exc:
        warn(f"Evento inválido, no se formatea: {exc}")

    path = target_path(event)
    if path is None or not path.endswith(".py") or not Path(path).is_file():
        sys.exit(0)

    try:
        result = run_ruff(project_root(event), path)
    except FileNotFoundError:
        warn("No se encontró uv ni ruff; ejecuta 'uv sync --group dev'. El archivo no se formateó.")
    except subprocess.TimeoutExpired:
        warn("ruff tardó demasiado; el archivo no se formateó.")
    if result.returncode != 0:
        warn(f"ruff no pudo formatear {path}:\n{(result.stderr or result.stdout).strip()}")
    sys.exit(0)


if __name__ == "__main__":
    main()
