# Quickstart: validar el servidor MCP de identificación

## Prerrequisitos

```bash
uv sync --group dev        # instala mcp y filelock (dependencias nuevas)
```

## Validación automática

```bash
uv run pytest src/crediagil/mcp_server   # unitarios + extremo a extremo por stdio
uv run pytest                            # suite completa
uv run ruff check
```

Casos en [contracts/tools.md](./contracts/tools.md).

## Comprobaciones manuales

| # | Comprobación | Esperado |
|---|--------------|----------|
| 1 | `uv run python -m crediagil.mcp_server.server` (Ctrl+C para salir) | Queda esperando por stdio, sin errores; crea `.data/core_estado.json` |
| 2 | `git status` tras el paso 1 | `.data/` no aparece (ignorado) |
| 3 | Registrar el servidor en un cliente MCP (p. ej. `claude mcp add crediagil-core -- uv run python -m crediagil.mcp_server.server`) y listar herramientas | `buscar_solicitante` y `verificar_identidad` |
| 4 | Con `CREDIAGIL_MCP_FALLAS_N=1`, llamar a `buscar_solicitante` dos veces | 1.ª `transitorio` reintentable; 2.ª normal |
| 5 | Borrar `.data/core_estado.json` y arrancar de nuevo | Estado semilla restaurado (desbloquea todo) |
