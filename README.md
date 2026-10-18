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
| #1–#8 | Ecosistema de Claude Code, flujo de tickets, política y extracción, MCP, hooks del SDK, agente, interfaz de chat | Integrados |
| #9 | Casos de prueba obligatorios | En curso |
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
uv run pytest -m live -k casos -s         # los 8 casos obligatorios
uv run pytest -m live -k chat -s          # solo la de la interfaz
```

La marca se llama `live` y equivale al `e2e` del enunciado.

## Casos de prueba obligatorios (`src/crediagil/casos/`)

Cada caso es una carpeta legible con su mensaje, sus documentos ficticios, la extracción que el
extractor debe devolver y el resultado esperado (`caso.json`). Es la única fuente: la leen los
tests deterministas, las pruebas con el modelo real y el selector de la interfaz de chat.

| # | Carpeta | Resultado esperado |
|---|---|---|
| 1 | `01_dentro_de_politica` | ✅ Crédito preaprobado |
| 2 | `02_dato_ausente` | 📄 Se solicita el dato (queda nulo, no se infiere) |
| 3 | `03_ingreso_discrepante` | 🧑‍💼 Escalado por discrepancia de ingreso |
| 4 | `04_monto_sobre_umbral` | 🧑‍💼 Escalado por monto (solicitud de $8.000.000) |
| 5 | `05_preaprobar_sin_identidad` | ⛔ Bloqueado por el hook de la regla 1 |
| 6 | `06_moneda_extranjera` | 🧑‍💼 Escalado: la política no lo cubre |
| 7 | `07_falla_transitoria` | ⚠️ Reintento y continúa (`CREDIAGIL_MCP_FALLAS_N`) |
| 8 | `08_pedir_persona` | 🧑‍💼 Escalado inmediato, sin buscar ni verificar antes |
| – | `09_mensaje_mixto` | 💬 Complementario: una respuesta; la simulación no registra ni preaprueba |

```bash
uv run pytest src/crediagil/casos         # sin modelo, red ni clave: un test por caso y los bordes
```

Los bordes de monto, cuota y discrepancia de ingreso se prueban exactamente en el umbral, un peso
por debajo y un peso por encima, con valores derivados de la política (no copiados).

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
