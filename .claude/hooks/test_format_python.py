"""Tests de format_python: contracts/hooks.md §format_python (casos 1–4)."""

from __future__ import annotations

from conftest import HOOKS_DIR

HOOK = "format_python.py"
# ruff se resuelve desde el proyecto real (grupo dev de pyproject.toml).
REPO_ROOT = HOOKS_DIR.parent.parent
UGLY = "x=1;y = [1,2 ,3]\n"


def post_event(path) -> dict:
    return {
        "hook_event_name": "PostToolUse",
        "tool_name": "Write",
        "tool_input": {"file_path": str(path), "content": ""},
    }


def test_caso1_py_queda_formateado(run_hook, tmp_path):
    target = tmp_path / "feo.py"
    target.write_text(UGLY, encoding="utf-8")
    code, _, stderr = run_hook(HOOK, post_event(target), REPO_ROOT)
    assert code == 0, stderr
    assert target.read_text(encoding="utf-8") == "x = 1\ny = [1, 2, 3]\n"


def test_caso2_otros_archivos_no_se_tocan(run_hook, tmp_path):
    target = tmp_path / "notas.md"
    target.write_text(UGLY, encoding="utf-8")
    code, _, _ = run_hook(HOOK, post_event(target), REPO_ROOT)
    assert code == 0
    assert target.read_text(encoding="utf-8") == UGLY


def test_caso3_sin_ruff_avisa_sin_bloquear(run_hook, tmp_path):
    target = tmp_path / "feo.py"
    target.write_text(UGLY, encoding="utf-8")
    code, _, stderr = run_hook(HOOK, post_event(target), REPO_ROOT, extra_env={"PATH": ""})
    assert code == 1
    assert "[format_python]" in stderr
    assert target.read_text(encoding="utf-8") == UGLY


def test_caso3b_error_de_sintaxis_avisa_sin_bloquear(run_hook, tmp_path):
    target = tmp_path / "roto.py"
    target.write_text("def (:\n", encoding="utf-8")
    code, _, stderr = run_hook(HOOK, post_event(target), REPO_ROOT)
    assert code == 1
    assert "[format_python]" in stderr


def test_caso4_entrada_malformada_no_bloquea(run_hook, tmp_path):
    code, _, _ = run_hook(HOOK, "no es json", REPO_ROOT)
    assert code == 1
