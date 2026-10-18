# Crediágil · Agente de originación de crédito

Agente construido con el **Claude Agent SDK** que extrae datos de documentos de soporte,
calcula la capacidad de pago, preaprueba los casos simples y escala al analista cuando
corresponde. Las herramientas del core viven en un **servidor MCP** propio que simula la
originación con datos 100% ficticios. Crediágil es una fintech ficticia.

- 📋 GitHub Project: `https://github.com/users/danielpvsofka/projects/1`
- 🎬 Video de funcionamiento: `https://youtu.be/4MPLYHot6ng`
- 🧭 Decisiones del ecosistema: [DECISIONES.md](DECISIONES.md)
- 📜 Reglas de negocio y parámetros: [constitución](.specify/memory/constitution.md) (única
  fuente de la tasa y los umbrales)

## Estado

| Issue | Alcance | Estado |
|---|---|---|
| #1–#7 | Ecosistema de Claude Code, flujo de tickets, política y extracción, MCP, hooks del SDK, agente | Integrados |
| #8 | Interfaz de chat | PR abierto |
| #9 | Casos de prueba obligatorios | Pendiente |
| #10 | Plugin reutilizable | Pendiente |
| #11 | CI y documentación de entrega | Pendiente |

## Correr en menos de 5 minutos

Requisitos: Python 3.12+, [uv](https://docs.astral.sh/uv/) y una `ANTHROPIC_API_KEY`.

```bash
git clone <repo> && cd <repo>
uv sync --group dev                       # instala dependencias
uv run pytest                             # suite determinista, sin red ni API key
export ANTHROPIC_API_KEY=...              # o defínela en un archivo .env local (ignorado por git)
uv run python -m crediagil.chat           # http://127.0.0.1:8000
```

`CREDIAGIL_CHAT_PUERTO` cambia el puerto. La interfaz solo escucha en `127.0.0.1`, no tiene
autenticación y no comprueba `Origin`: no la expongas en una red.

En la interfaz, elige un caso en **Demostración**: rellena el mensaje y el adjunto sin enviarlos.
También puedes escribir mensajes y adjuntar documentos `.txt` o `.md` (hasta 5, de 100 KiB). Cada
turno trae un desplegable con las herramientas llamadas, la razón de parada y el coste. Los avisos
(crédito preaprobado, información solicitada, escalado, bloqueo por regla) salen del resultado
estructurado del turno, nunca del texto del modelo.

Tests con el modelo real (opt-in, consumen saldo, se saltan sin clave):

```bash
uv run pytest -m live -s                  # todas
uv run pytest -m live -k chat -s          # solo la de la interfaz
```

## Casos de prueba de la interfaz (`src/crediagil/chat/casos.py`)

| Caso | Resultado esperado |
|---|---|
| Solicitud dentro de política | ✅ Crédito preaprobado |
| Pedir hablar con una persona | 🧑‍💼 Escalado inmediato, sin buscar ni verificar antes |
| Dato ausente en el documento | 📄 Se solicita el dato (queda nulo, no se infiere) |
| Solicitud y pregunta en el mismo mensaje | 💬 Una sola respuesta; la simulación no registra ni preaprueba |
| Preaprobar sin identidad verificada | ⛔ Bloqueado por el hook de la regla 1 |
| Falla transitoria del core | ⚠️ Reintento y continúa (falla simulada con `CREDIAGIL_MCP_FALLAS_N`) |

El conjunto completo de casos obligatorios, con sus tests, es el alcance del issue #9.

## Arquitectura

```
Chat (Starlette) ─► Agente orquestador (Agent SDK) ──Agent──► Subagente extractor-documentos
                        │  hooks PreToolUse (reglas 1 y 2)            │
                        ▼                                             ▼
                 Servidor MCP crediagil (stdio) ◄───────── validar_extraccion
                        │
                 Estado JSON (.data/) ◄── lo leen los hooks
```

- El ciclo del agente lo decide la razón de parada del modelo (`clasificar_parada`), no el texto.
- Las reglas 1 y 2 de la constitución se hacen cumplir con hooks del SDK, no con el prompt.
- Los incidentes se escalan por código, con `escalar_a_analista`.

| Carpeta | Contenido |
|---|---|
| `src/crediagil/policy/` | Política: parámetros (`params.py`), cuota y decisión |
| `src/crediagil/extraction/` | Esquemas de extracción (`{valor, fragmento}`) e ingreso verificado |
| `src/crediagil/mcp_server/` | Core simulado: estado, errores estructurados, herramientas MCP |
| `src/crediagil/agent/` | Orquestador, subagente extractor, prompts, hooks, canal y trazas |
| `src/crediagil/chat/` | Interfaz web de chat (API, sesión, adjuntos, casos y estáticos) |
| `src/crediagil/config.py` | Carga del entorno y redacción de la clave |
| `.claude/` | Ecosistema de Claude Code del equipo (hooks, agentes, skills, reglas) |
| `specs/`, `.specify/` | Artefactos de Spec Kit |

El plugin reutilizable para otros equipos (issue #10) aún no existe.

## Ecosistema de Claude Code

Para desarrollar con Claude Code, exporta `GITHUB_PAT` (token classic de GitHub con scopes
`repo` y `project`) en tu shell. Lo toma `.mcp.json`, que no contiene credenciales. Flujo por
issue: `/ticket <n>` → `/speckit-plan` → `/speckit-tasks` → `/speckit-implement` →
`/open-pr <n>`. Convenciones y hooks activos en [CLAUDE.md](CLAUDE.md); decisiones en
[DECISIONES.md](DECISIONES.md).

Todos los datos de este repositorio son ficticios.
