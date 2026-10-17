"""Tests de require_specs: contracts/hooks.md §require_specs (casos 1–8)."""

from __future__ import annotations

import json

import pytest

HOOK = "require_specs.py"
FEATURE_DIR = "specs/999-demo"


def make_project(tmp_path, docs: dict[str, str] | None, *, feature_json: bool = True):
    if feature_json:
        (tmp_path / ".specify").mkdir()
        (tmp_path / ".specify" / "feature.json").write_text(
            json.dumps({"feature_directory": FEATURE_DIR}), encoding="utf-8"
        )
    if docs is not None:
        feature = tmp_path / FEATURE_DIR
        feature.mkdir(parents=True)
        for name, content in docs.items():
            (feature / name).write_text(content, encoding="utf-8")
    return tmp_path


COMPLETE = {"spec.md": "# spec", "plan.md": "# plan", "tasks.md": "# tasks"}


def write_event(path: str, tool: str = "Write") -> dict:
    if tool == "NotebookEdit":
        tool_input = {"notebook_path": path, "new_source": "x = 1"}
    elif tool == "Edit":
        tool_input = {"file_path": path, "old_string": "a", "new_string": "b"}
    else:
        tool_input = {"file_path": path, "content": "x = 1\n"}
    return {"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": tool_input}


@pytest.mark.parametrize("tool", ["Write", "Edit", "NotebookEdit"])
def test_caso1_feature_completa_permite(run_hook, tmp_path, tool):
    project = make_project(tmp_path, COMPLETE)
    code, _, _ = run_hook(HOOK, write_event("src/app.py", tool), project)
    assert code == 0


def test_caso2_falta_tasks_bloquea(run_hook, tmp_path):
    project = make_project(tmp_path, {"spec.md": "# spec", "plan.md": "# plan"})
    code, _, stderr = run_hook(HOOK, write_event("src/app.py"), project)
    assert code == 2
    assert "tasks.md" in stderr
    assert FEATURE_DIR in stderr
    assert "plan.md" not in stderr


def test_caso3_plan_vacio_bloquea(run_hook, tmp_path):
    project = make_project(tmp_path, {**COMPLETE, "plan.md": "  \n\t\n"})
    code, _, stderr = run_hook(HOOK, write_event("src/app.py", "Edit"), project)
    assert code == 2
    assert "plan.md" in stderr


def test_caso4_sin_feature_json_bloquea(run_hook, tmp_path):
    project = make_project(tmp_path, None, feature_json=False)
    code, _, stderr = run_hook(HOOK, write_event("src/app.py"), project)
    assert code == 2
    assert "/speckit-specify" in stderr
    assert "feature.json" in stderr


def test_caso4b_directorio_de_feature_inexistente_bloquea(run_hook, tmp_path):
    project = make_project(tmp_path, None)
    code, _, stderr = run_hook(HOOK, write_event("src/app.py"), project)
    assert code == 2
    assert "feature.json" in stderr


def test_caso5_fuera_de_src_no_interviene(run_hook, tmp_path):
    project = make_project(tmp_path, None, feature_json=False)
    code, _, _ = run_hook(HOOK, write_event("docs/x.md"), project)
    assert code == 0


@pytest.mark.parametrize("style", ["absoluta", "backslash"])
def test_caso6_rutas_equivalentes(run_hook, tmp_path, style):
    project = make_project(tmp_path, {"spec.md": "# spec"})
    path = str(tmp_path / "src" / "pkg" / "app.py") if style == "absoluta" else "src\\pkg\\app.py"
    code, _, _ = run_hook(HOOK, write_event(path), project)
    assert code == 2


def test_caso7_prefijo_no_es_directorio_src(run_hook, tmp_path):
    project = make_project(tmp_path, None, feature_json=False)
    code, _, _ = run_hook(HOOK, write_event("srcx/a.py"), project)
    assert code == 0


@pytest.mark.parametrize("payload", ["no es json", "[]", json.dumps({"tool_name": "Write"})])
def test_caso8_entrada_malformada_bloquea(run_hook, tmp_path, payload):
    code, _, stderr = run_hook(HOOK, payload, tmp_path)
    assert code == 2
    assert "[require_specs]" in stderr
