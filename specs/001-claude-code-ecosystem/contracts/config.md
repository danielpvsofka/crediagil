# Contract: Configuración versionada

## CLAUDE.md (raíz)

- La primera sección importa la constitución con `@.specify/memory/constitution.md`.
- Convenciones del equipo: flujo Spec Kit, idioma de artefactos (español), Python ≥ 3.12 con
  `uv`, `ruff` como formateador, tests junto al código, marcador `dato-ficticio`, y
  cómo funcionan los hooks y qué hacer si uno bloquea.
- No duplica tasa ni umbrales: remite a la constitución.

## .gitignore (adiciones)

```text
CLAUDE.local.md
.claude/settings.local.json
.env
.env.*
secrets/
```

## .claude/settings.json

```json
{
  "permissions": {
    "deny": [
      "Read(./.env)", "Read(./.env.*)", "Read(./secrets/**)",
      "Edit(./.env)", "Edit(./.env.*)", "Edit(./secrets/**)"
    ]
  },
  "hooks": {
    "PreToolUse": [
      { "matcher": "Write|Edit|MultiEdit|NotebookEdit",
        "hooks": [
          { "type": "command", "command": "uv run --no-project python \"$CLAUDE_PROJECT_DIR/.claude/hooks/require_specs.py\"" },
          { "type": "command", "command": "uv run --no-project python \"$CLAUDE_PROJECT_DIR/.claude/hooks/block_sensitive_data.py\"" }
        ] },
      { "matcher": "Bash|PowerShell",
        "hooks": [
          { "type": "command", "command": "uv run --no-project python \"$CLAUDE_PROJECT_DIR/.claude/hooks/block_secret_access.py\"" }
        ] }
    ],
    "PostToolUse": [
      { "matcher": "Write|Edit|MultiEdit",
        "hooks": [
          { "type": "command", "command": "uv run --no-project python \"$CLAUDE_PROJECT_DIR/.claude/hooks/format_python.py\"" }
        ] }
    ]
  }
}
```

## .claude/rules/*.md

Frontmatter obligatorio:

```markdown
---
paths:
  - "<glob>"
---
```

| Archivo | `paths` |
|---------|---------|
| `tests.md` | `**/test_*.py`, `**/*_test.py`, `tests/**` |
| `mcp-server.md` | `src/**/mcp/**`, `src/**/mcp_server/**` |
| `hooks.md` | `.claude/hooks/**` |

## .mcp.json

- Servidor `github` (HTTP), `Authorization: Bearer ${GITHUB_PAT}`, `X-MCP-Toolsets` con
  `projects`. El archivo actual ya cumple; solo se verifica.

## pyproject.toml

- `requires-python = ">=3.12"`, sin dependencias de runtime.
- `[dependency-groups] dev = ["pytest", "ruff"]`.
- `[tool.ruff] line-length = 100, target-version = "py312"`.
- `[tool.pytest.ini_options] testpaths = [".claude/hooks"]`.
