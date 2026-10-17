"""Utilidades compartidas por los hooks de Claude Code (solo biblioteca estándar).

Protocolo: el evento llega como JSON por stdin. Salida 0 permite, salida 2 bloquea y el
contenido de stderr se devuelve al modelo como motivo.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import NoReturn

# Claude Code intercambia UTF-8; en Windows la consola por defecto usa otra codificación.
for _stream in (sys.stdin, sys.stdout, sys.stderr):
    _stream.reconfigure(encoding="utf-8")


class HookInputError(Exception):
    """El evento recibido por stdin no es válido."""


def read_event() -> dict:
    raw = sys.stdin.read()
    try:
        event = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HookInputError(f"stdin no es JSON válido: {exc}") from exc
    if not isinstance(event, dict):
        raise HookInputError("el evento no es un objeto JSON")
    if not isinstance(event.get("tool_name"), str):
        raise HookInputError("falta tool_name")
    if not isinstance(event.get("tool_input"), dict):
        raise HookInputError("falta tool_input")
    return event


def project_root(event: dict) -> Path:
    root = os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or os.getcwd()
    return Path(root).resolve()


def target_path(event: dict) -> str | None:
    tool_input = event["tool_input"]
    path = tool_input.get("file_path") or tool_input.get("notebook_path")
    return path if isinstance(path, str) and path else None


def new_content(event: dict) -> list[str]:
    """Textos que la herramienta va a escribir, según su tipo."""
    tool_input = event["tool_input"]
    texts: list[str] = []
    for key in ("content", "new_string", "new_source"):
        value = tool_input.get(key)
        if isinstance(value, str):
            texts.append(value)
    for edit in tool_input.get("edits") or []:
        if isinstance(edit, dict) and isinstance(edit.get("new_string"), str):
            texts.append(edit["new_string"])
    return texts


def _normalized(path: Path) -> tuple[str, ...]:
    return tuple(os.path.normcase(part) for part in path.parts)


def is_under(path: str, root: Path, subdir: str) -> bool:
    """True si `path` cae dentro de `root/subdir` (comparando segmentos completos)."""
    candidate = Path(path.replace("\\", "/"))
    if not candidate.is_absolute():
        candidate = root / candidate
    base = _normalized((root / subdir).resolve())
    target = _normalized(candidate.resolve())
    return target[: len(base)] == base and len(target) > len(base)


def block(hook_name: str, message: str) -> NoReturn:
    print(f"[{hook_name}] {message}", file=sys.stderr)
    sys.exit(2)


def allow() -> NoReturn:
    sys.exit(0)
