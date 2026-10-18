# Crediágil — convenciones del equipo

Agente de originación de crédito de libre inversión para Crediágil, una fintech **ficticia**.
La constitución del proyecto prevalece sobre todo lo demás:

@.specify/memory/constitution.md

Tasa, umbrales y reglas de negocio viven **solo** en la constitución; no los repitas ni los
cambies aquí, en código ni en prompts.

## Flujo de trabajo

- Spec antes que código: `/speckit-specify` → `/speckit-plan` → `/speckit-tasks` →
  `/speckit-implement`. Un cambio de comportamiento actualiza primero la spec.
- La feature activa es la de `.specify/feature.json` (`feature_directory`).
- Artefactos (specs, planes, tareas, documentación) en español.
- Nunca hacer commit ni push sin confirmación explícita.

## Stack y comandos

- Python ≥ 3.12 gestionado con `uv`: `uv sync --group dev` instala pydantic, pytest y ruff.
- Código del agente en `src/crediagil/` (paquete instalable). La política se importa de
  `crediagil.policy`; los parámetros viven solo en `crediagil/policy/params.py`, verificados
  contra la constitución por `test_params.py`. Nunca los redefinas en otro módulo.
- Datos extraídos: `crediagil.extraction` (`{valor, fragmento}` con fragmento literal; lo
  ausente queda `None`).
- Core de originación simulado: `uv run python -m crediagil.mcp_server.server` (MCP por stdio).
  Estado en `.data/core_estado.json` (ignorado; bórralo para volver a la semilla) o en
  `CREDIAGIL_MCP_ESTADO`. Fallas transitorias para pruebas: `CREDIAGIL_MCP_FALLAS_N`,
  `CREDIAGIL_MCP_FALLAS_PROB` y `CREDIAGIL_MCP_FALLAS_SEMILLA`.
  Herramientas: `buscar_solicitante`, `verificar_identidad`, `validar_extraccion`,
  `registrar_solicitud`, `calcular_capacidad_pago` (solo simula), `preaprobar_credito` (la única
  que compromete; revalida identidad y reglas en el core) y `escalar_a_analista`.
- Hooks de las reglas 1 y 2: `crediagil.agent.hooks.crear_hooks(almacen, registro)` devuelve la
  configuración `PreToolUse` para `ClaudeAgentOptions(hooks=...)` (`claude-agent-sdk` es
  dependencia). Niegan `registrar_solicitud` sin identidad vigente y `preaprobar_credito` si no
  se cumplen identidad, documentos y política recalculada. Son de solo lectura y fail-closed;
  cada negación queda en `RegistroNegaciones` para la interfaz. El nombre del servidor debe
  coincidir con la clave de `mcp_servers`.
- Agente: `crediagil.agent.Agente` (`async with Agente(ConfigAgente()) as agente`, `await
  agente.turno(mensaje, adjuntos)` devuelve un `ResultadoTurno`). Sobre el Claude Agent SDK: el
  ciclo lo decide la razón de parada (`clasificar_parada`), nunca el texto; los incidentes se
  escalan por código. Subagente `extractor-documentos` (solo `validar_extraccion`, en primer
  plano) con un hook sobre `Agent` que exige `documento_id`, nombre y texto completo. Para aislar
  al agente de la configuración de Claude Code se usa `setting_sources=[]`: el valor por defecto
  `None` NO aísla. Los prompts (`agent/prompts/`) no llevan la tasa ni los umbrales.
- Clave de la API: `ANTHROPIC_API_KEY` en el entorno o en el archivo local ignorado por git
  (`crediagil.config.cargar_entorno()` no pisa variables ya definidas). Nunca escribas su valor en
  un archivo; `redactar()` la quita de logs, trazas y errores.
- Pruebas con el modelo real: `uv run pytest -m live -s` (opt-in, consumen saldo; `uv run pytest`
  las excluye; `-k chat` ejecuta solo la de la interfaz; `-k casos` los casos obligatorios). Se
  saltan si no hay clave. La marca se llama `live` y equivale al `e2e` del enunciado.
- Casos de prueba obligatorios: `crediagil.casos` (`src/crediagil/casos/`), una carpeta `NN_id/`
  por caso con `caso.json` (resultado esperado), `mensaje.md`, `documentos/` y `extraccion/` (lo
  que el extractor debe devolver, con fragmentos literales). `cargar_catalogo()` valida el
  contrato y es la única fuente: tests deterministas (`test_casos.py`, `test_bordes.py`), pruebas
  con modelo real (`test_vivo.py`, dirigidas por `esperado.herramientas` y comprobadas sobre la
  traza con `verificacion.py`) y el selector de la interfaz. Los bordes salen de
  `crediagil.policy.params`, nunca de literales; los mensajes dicen "identificación" y no
  "documento" junto al id `TEST-…` para que el detector de datos no pida el marcador en el texto
  que ve el usuario.
- Interfaz de chat: `uv run python -m crediagil.chat` abre una aplicación web local en
  `http://127.0.0.1:8000` (`CREDIAGIL_CHAT_PUERTO` cambia el puerto). Solo escucha en `127.0.0.1`,
  no tiene autenticación y **no comprueba `Origin`**: no la expongas en una red. Una conversación
  y un turno a la vez; el hilo vive en memoria. Solo muestra y opera: los avisos salen del
  `ResultadoTurno` (nunca del texto del modelo) y todo texto entra con `textContent`. Los casos
  de prueba salen del catálogo (`crediagil/chat/casos.py` solo lo adapta). Reiniciar datos usa `AlmacenEstado.reiniciar()`. El
  JavaScript no tiene pruebas de navegador: `test_estaticos.py` lo revisa como texto y el
  recorrido manual está en `specs/008-chat-interface/quickstart.md`.
- Tests: `uv run pytest`. Todo cambio de código incluye sus tests en el mismo cambio, junto al
  código, y cubre los bordes exactos de cada umbral.
- Formato: `ruff format` se aplica solo tras editar cualquier `.py` (hook). Lint:
  `uv run ruff check`.

## Datos ficticios

- Solo datos ficticios en código, tests, fixtures, logs y documentación.
- Un fixture con forma de cédula o cuenta deliberadamente ficticio se marca en **la misma
  línea** con `dato-ficticio`. Si es una edición, el marcador debe estar dentro del
  texto editado. No uses el marcador para nada que pueda ser real.
- Los números con forma de tarjeta para tests se generan en tiempo de ejecución, nunca como
  literal.

## Secretos

- Los secretos van en `.env` (ignorado por git). Claude no puede leer `.env*` ni `secrets/`:
  si necesitas un valor, pídelo al usuario.
- `GITHUB_PAT` se define en el entorno de cada desarrollador; `.mcp.json` solo lo referencia.

## Hooks activos (`.claude/settings.json`)

| Hook | Cuándo | Bloquea si… | Qué hacer |
|------|--------|-------------|-----------|
| `require_specs` | Antes de escribir/editar | el archivo está bajo `src/` y la feature activa no tiene `spec.md`, `plan.md` y `tasks.md` no vacíos | Completar el flujo Spec Kit o corregir `.specify/feature.json` |
| `block_sensitive_data` | Antes de escribir/editar | el contenido tiene una tarjeta válida por Luhn, o una cédula/NIT/cuenta junto a su etiqueta | Usar datos ficticios generados, o `dato-ficticio` si es deliberado |
| `block_secret_access` | Antes de Bash/PowerShell | el comando menciona `.env*` o `secrets/` | Pedir el valor al usuario |
| `format_python` | Después de escribir/editar | nunca bloquea; avisa si ruff no está disponible | Ejecutar `uv sync --group dev` |
| `allow_only_pytest` | Antes de Bash, solo en el subagente `compliance-reviewer` (frontmatter, no `settings.json`) | el comando no es `pytest`/`uv run pytest`, o encadena/redirige | Nada: el revisor solo debe leer y ejecutar tests |

Los hooks y sus tests viven en `.claude/hooks/`. Las reglas por ruta, en `.claude/rules/`.

## Flujo de tickets

- Repositorio: `danielpvsofka/crediagil`. Rama base de los PR: `main`.
- Project: "Crediágil", owner `danielpvsofka` (usuario), número **1**, campo `Status`. El
  `GITHUB_PAT` necesita un token classic con scopes `repo` y `project`. La opción `Ready` del
  Project no la usa ningún comando.
- Estados: `Todo` → `In progress` (`/ticket`) → `In review` (`/open-pr`) → `Done` (workflows
  integrados "Item closed" y "Pull request merged" del Project, activados a mano).
  `Closes #n` solo cierra el issue al fusionar en `main`.
- Lógica de negocio = cualquier ruta bajo `src/` en el diff; dispara `compliance-check`.
- Piezas:
  - `/ticket [n|siguiente]` (`.claude/skills/ticket/`): mueve a In progress, genera la spec y
    comenta en el issue.
  - `/open-pr <n>` (`.claude/commands/open-pr.md`): tests, revisiones, PR, In review y
    comentario.
  - `code-reviewer` (`.claude/agents/`): Read, Grep, Glob.
  - `compliance-reviewer` (`.claude/agents/`): lectura y pytest (hook `allow_only_pytest`).
  - `compliance-check` (`.claude/skills/`): `context: fork` con `compliance-reviewer`.

## Personal

Preferencias propias en `CLAUDE.local.md` y `.claude/settings.local.json` (ambos ignorados por
git).
