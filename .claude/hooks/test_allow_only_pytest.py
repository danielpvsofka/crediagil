"""Tests de allow_only_pytest: contracts/reviewers.md §Hook allow_only_pytest.py."""

from __future__ import annotations

import pytest

HOOK = "allow_only_pytest.py"


def bash_event(command: str | None) -> dict:
    tool_input = {} if command is None else {"command": command}
    return {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": tool_input}


ALLOWED = [
    "uv run pytest",
    "uv run pytest .claude/hooks -q",
    "pytest -k umbral",
    "pytest",
    "  uv run pytest",
]

BLOCKED = [
    "git status",
    "rm -rf src",
    "uv run pytest; rm -rf src",
    "uv run pytest && git push",
    "uv run pytest || git push",
    "uv run pytest | tee out.txt",
    "uv run pytest > out.txt",
    "uv run pytest < in.txt",
    "uv run pytest $(cat x)",
    "uv run pytest `cat x`",
    "uv run pytestx",
    "uv run python -m pytest",
    "",
    "   ",
]


@pytest.mark.parametrize("command", ALLOWED)
def test_permite_pytest(run_hook, tmp_path, command):
    code, _, stderr = run_hook(HOOK, bash_event(command), tmp_path)
    assert code == 0, stderr


@pytest.mark.parametrize("command", BLOCKED)
def test_bloquea_otros_comandos(run_hook, tmp_path, command):
    code, _, stderr = run_hook(HOOK, bash_event(command), tmp_path)
    assert code == 2
    assert stderr.startswith("[allow_only_pytest]")


def test_bloquea_sin_command(run_hook, tmp_path):
    code, _, stderr = run_hook(HOOK, bash_event(None), tmp_path)
    assert code == 2
    assert stderr.startswith("[allow_only_pytest]")


def test_bloquea_stdin_no_json(run_hook, tmp_path):
    code, _, stderr = run_hook(HOOK, "esto no es json", tmp_path)
    assert code == 2
    assert stderr.startswith("[allow_only_pytest]")
