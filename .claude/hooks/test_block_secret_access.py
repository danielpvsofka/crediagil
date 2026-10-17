"""Tests de block_secret_access: contracts/hooks.md §block_secret_access (casos 1–9)."""

from __future__ import annotations

import pytest

HOOK = "block_secret_access.py"
TOOLS = ["Bash", "PowerShell"]


def command_event(tool: str, command: str) -> dict:
    return {"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": {"command": command}}


BLOCKED = [
    "cat .env",  # caso 1
    "cat ./.env.local",  # caso 2
    "less .env.production",
    "Get-Content .env",  # caso 3
    "gc .env",
    "type .env",
    "grep KEY < .env",  # caso 4
    "cp .env /tmp/x",
    "cat secrets/token.txt",  # caso 5
    "type secrets\\token.txt",
    "cat .env.example",  # caso 6
    "python -c \"print(open('.env').read())\"",
    "git status && cat .env | head",
    "Get-Content C:\\repo\\.env",
]

ALLOWED = [
    "git status",  # caso 7
    "ls -la",
    "uv run pytest",
    "cat src/environment.py",  # caso 8
    "echo .envelope",
    "cat docs/secrets.md",
]


@pytest.mark.parametrize("tool", TOOLS)
@pytest.mark.parametrize("command", BLOCKED)
def test_casos1a6_acceso_a_secretos_bloquea(run_hook, tmp_path, tool, command):
    code, _, stderr = run_hook(HOOK, command_event(tool, command), tmp_path)
    assert code == 2, command
    assert "[block_secret_access]" in stderr


@pytest.mark.parametrize("tool", TOOLS)
@pytest.mark.parametrize("command", ALLOWED)
def test_casos7y8_comandos_normales_permiten(run_hook, tmp_path, tool, command):
    code, _, stderr = run_hook(HOOK, command_event(tool, command), tmp_path)
    assert code == 0, stderr


@pytest.mark.parametrize(
    "payload",
    ["no es json", '{"tool_name": "Bash", "tool_input": {}}'],
)
def test_caso9_entrada_malformada_bloquea(run_hook, tmp_path, payload):
    code, _, stderr = run_hook(HOOK, payload, tmp_path)
    assert code == 2
    assert "[block_secret_access]" in stderr
