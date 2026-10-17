"""Tests de configuración de revisores: contracts/reviewers.md §Test de configuración (SC-005)."""

from __future__ import annotations

from pathlib import Path

CLAUDE_DIR = Path(__file__).resolve().parent.parent
CODE_REVIEWER = CLAUDE_DIR / "agents" / "code-reviewer.md"
COMPLIANCE_REVIEWER = CLAUDE_DIR / "agents" / "compliance-reviewer.md"
COMPLIANCE_CHECK = CLAUDE_DIR / "skills" / "compliance-check" / "SKILL.md"
WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}


def frontmatter_lines(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "---", f"{path} no empieza con frontmatter"
    end = lines.index("---", 1)
    return lines[1:end]


def top_level(path: Path) -> dict[str, str]:
    """Claves de primer nivel del frontmatter (lector mínimo, sin PyYAML)."""
    fields = {}
    for line in frontmatter_lines(path):
        if line and not line[0].isspace() and ":" in line:
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip().strip('"')
    return fields


def tool_set(value: str) -> set[str]:
    return {tool.strip() for tool in value.split(",") if tool.strip()}


def test_code_reviewer_solo_lectura():
    assert tool_set(top_level(CODE_REVIEWER)["tools"]) == {"Read", "Grep", "Glob"}


def test_compliance_reviewer_lectura_y_bash():
    assert tool_set(top_level(COMPLIANCE_REVIEWER)["tools"]) == {"Read", "Grep", "Glob", "Bash"}


def test_compliance_reviewer_restringe_bash_con_hook():
    body = "\n".join(frontmatter_lines(COMPLIANCE_REVIEWER))
    assert "hooks:" in body
    assert "PreToolUse:" in body
    assert 'matcher: "Bash"' in body
    assert "allow_only_pytest.py" in body


def test_ningun_revisor_puede_escribir():
    for path in (CODE_REVIEWER, COMPLIANCE_REVIEWER):
        assert not tool_set(top_level(path)["tools"]) & WRITE_TOOLS, path


def test_compliance_check_en_contexto_aislado():
    fields = top_level(COMPLIANCE_CHECK)
    assert fields["context"] == "fork"
    assert fields["agent"] == "compliance-reviewer"
    assert fields.get("argument-hint")
    allowed = fields["allowed-tools"]
    assert allowed
    assert not {tool.split("(")[0] for tool in tool_set(allowed)} & WRITE_TOOLS
