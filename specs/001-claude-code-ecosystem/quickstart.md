# Quickstart: validar el ecosistema base

## Prerrequisitos

- `uv` instalado (`uv --version`).
- `GITHUB_PAT` definido en el entorno local (solo para el MCP de GitHub).

## 1. Tests automáticos de hooks

```bash
uv sync --group dev
uv run pytest
```

**Esperado**: todos los casos de [contracts/hooks.md](./contracts/hooks.md) pasan.

## 2. Convenciones al clonar (US1)

```bash
git clone https://github.com/danielpvsofka/crediagil.git /tmp/crediagil-check
cd /tmp/crediagil-check && claude
```

- Ejecutar `/memory`: aparecen `CLAUDE.md` y la constitución importada.
- Preguntar "¿cuál es la tasa fija?": la respuesta coincide con la de la constitución.
- `touch CLAUDE.local.md .claude/settings.local.json && git status`: no aparecen.

## 3. Validación manual en sesión

| Acción pedida a Claude | Esperado |
|------------------------|----------|
| Crear `src/demo.py` con `feature.json` apuntando a una feature sin `tasks.md` | Bloqueado; menciona `tasks.md` |
| Escribir un fixture con `cédula: ` + 10 dígitos | Bloqueado (`documento`) |
| Lo mismo con `# pragma: dato-ficticio` | Permitido |
| Leer `.env` con la herramienta de lectura | Denegado por permisos |
| `cat .env` por terminal (Bash y PowerShell) | Bloqueado por hook |
| Escribir un `.py` mal formateado | Queda formateado |

## 4. Sin secretos en el repo

```bash
git grep -nE "ghp_|github_pat_|Bearer [A-Za-z0-9]" -- . ':!specs'
```

**Esperado**: solo `.mcp.json` con `Bearer ${GITHUB_PAT}`.
