# Quickstart: validar los hooks de las reglas 1 y 2

## Prerrequisitos

```bash
uv sync --group dev        # instala claude-agent-sdk (dependencia nueva)
```

No hace falta la clave de la API: los hooks se prueban sin llamar al modelo.

## Validación automática

```bash
uv run pytest src/crediagil/agent    # hooks y registro de negaciones
uv run pytest                        # suite completa
uv run ruff check
```

Casos en [contracts/hooks.md](./contracts/hooks.md).

## Comprobaciones rápidas

| # | Comprobación | Esperado |
|---|--------------|----------|
| 1 | Con un estado temporal, llamar al hook de preaprobación con una solicitud inexistente (script con `asyncio.run`) | `permissionDecision: "deny"` y motivo que empieza por `[SOLICITUD_NO_ENCONTRADA]` |
| 2 | Verificar identidad, registrar una solicitud preaprobable y llamar al hook | `{}` |
| 3 | Bloquear al solicitante (3 fechas incorrectas) y llamar otra vez | `deny` `IDENTIDAD_NO_VERIFICADA` |
| 4 | Borrar el archivo de estado y llamar al hook | `deny` `ESTADO_ILEGIBLE`, y el archivo no se vuelve a crear |
| 5 | `python -c "from claude_agent_sdk import ClaudeAgentOptions; from crediagil.agent.hooks import crear_hooks; ..."` | las opciones se construyen con 2 matchers `mcp__crediagil-core__…` |

La prueba de extremo a extremo con el modelo real (el hook bloqueando una llamada del agente)
se hace en #7, cuando exista el orquestador y la clave de la API.
