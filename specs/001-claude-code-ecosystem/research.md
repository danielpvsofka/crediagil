# Research: Ecosistema base de Claude Code

Decisiones de la Fase 0. No quedan `NEEDS CLARIFICATION`.

## R1. Lenguaje y lanzador de los hooks

- **Decision**: Python con solo biblioteca estándar, invocado como
  `uv run --no-project python "$CLAUDE_PROJECT_DIR/.claude/hooks/<hook>.py"`.
- **Rationale**: el agente se construirá en Python (Claude Agent SDK). `uv` ya está instalado
  y resuelve el intérprete igual en Windows y POSIX, lo que evita la ambigüedad
  `python`/`python3`. Sin dependencias externas el hook no necesita un entorno sincronizado.
- **Alternatives considered**: scripts bash (no funcionan en PowerShell y la detección Luhn es
  frágil); Node (añade un runtime al stack); `python` a secas (en macOS/Linux suele ser
  `python3`).

## R2. Protocolo de hooks de Claude Code

- **Decision**: leer el JSON del evento desde stdin. Salida 0 permite; salida 2 bloquea y
  stderr se devuelve al modelo como motivo. En PostToolUse, salida 1 informa un error sin
  bloquear.
- Campos usados: `tool_name`, `tool_input.file_path` (`notebook_path` en NotebookEdit),
  `tool_input.content` (Write), `tool_input.new_string` (Edit), `tool_input.edits[].new_string`
  (MultiEdit), `tool_input.new_source` (NotebookEdit), `tool_input.command` (Bash/PowerShell),
  `cwd`. Raíz del proyecto: `CLAUDE_PROJECT_DIR`, con `cwd` como respaldo.
- **Matchers**: escritura `Write|Edit|MultiEdit|NotebookEdit`; terminal `Bash|PowerShell`. Este
  entorno expone una herramienta PowerShell además de Bash, así que proteger solo Bash dejaría
  un hueco.

## R3. Feature activa para `require_specs`

- **Decision**: `.specify/feature.json` → `feature_directory`. Si falta el archivo o la clave, o
  el directorio no existe, se bloquea. Un documento cuenta como presente si existe y tiene algún
  carácter que no sea espacio en blanco.
- **Rationale**: Spec Kit ya mantiene ese archivo (`/speckit-specify`), y la rama actual
  (`develop`) no codifica la feature.
- **Alternatives considered**: inferir desde la rama git (no aplica con `develop`); exigir los
  documentos de cualquier feature (no garantiza que correspondan al cambio).
- **Rutas**: se normalizan a absolutas con `/`, sin distinguir mayúsculas en Windows, y se
  evalúa si caen bajo `<raíz>/src/`.

## R4. Detección de datos con forma real

- **Tarjeta**: secuencias de dígitos con separadores opcionales (espacio o guion) de 13 a 19
  dígitos, primer dígito de 2 a 6 (rangos de IIN de las marcas comunes) y Luhn válido. Exigir
  un IIN plausible evita bloquear timestamps en milisegundos (empiezan por `1`), que pasan Luhn
  en ~10% de los casos.
- **Cédula / NIT**: 6 a 10 dígitos (puntos y guiones admitidos; dígito de verificación del NIT
  opcional), precedidos a ≤ 30 caracteres en la misma línea por una etiqueta: `cédula`,
  `cedula`, `C.C.`, `CC`, `NIT`, `documento`, `doc` (sin distinguir mayúsculas, con límite de
  palabra).
- **Cuenta bancaria**: 9 a 20 dígitos con la misma regla de etiqueta: `cuenta`, `cta`,
  `ahorros`, `corriente`, `account`.
- **Exención**: una línea con `pragma: dato-ficticio` se omite (FR-010a). Es el mismo patrón que
  usan `# noqa` o `pragma: allowlist secret` de detect-secrets, y queda visible en el diff.
- **Mensaje**: tipo de dato, número de línea y valor enmascarado (últimos 4 dígitos).
- **Alternatives considered**: bloquear cualquier número de 6 o más dígitos (demasiados falsos
  positivos con montos COP); allowlist de rangos "ficticios" (en Colombia no existe un rango de
  cédulas garantizado como inválido); excluir por ruta `tests/` (los fixtures son justamente
  donde más riesgo hay).
- **Tests del propio hook**: generan los números válidos por Luhn en tiempo de ejecución (base
  + dígito de control calculado), así que ningún literal bloqueable queda en el código fuente.

## R5. Protección de secretos

- **permissions.deny**: `Read(./.env)`, `Read(./.env.*)`, `Edit(./.env)`, `Edit(./.env.*)`,
  `Read(./secrets/**)`, `Edit(./secrets/**)`. Las reglas `Read` de Claude Code también aplican
  a Grep/Glob, y las `Edit` a todas las herramientas que modifican archivos.
- **Hook de terminal**: bloquea todo comando que referencie un token de ruta `.env` o `.env.*`
  (precedido de inicio, espacio, `/`, `\`, comilla, `=`, `<`, `>`, `|` o `;`) o un segmento
  `secrets/` o `secrets\`. Bloquea cualquier mención de esas rutas, no solo una lista de
  comandos lectores, porque el número de formas de leer un archivo (`cat`, `type`,
  `Get-Content`, `gc`, `less`, `cp`, `python -c`, `source`, `<` …) es ilimitado.
- `.env.example` también queda bloqueado para mantener coherencia con `permissions.deny`, que
  no admite excepciones (actualizado en la spec).
- **Fuera de alcance**: `printenv`, `echo $GITHUB_PAT` y similares (variables de entorno, no
  archivos). Se anota como mejora futura.

## R6. Formato post-edición

- **Decision**: `uv run --quiet ruff format <archivo>`, con `ruff` del grupo `dev` de
  `pyproject.toml`. Si `uv` falla se intenta `ruff` del PATH; si ambos fallan, salida 1 con
  aviso en stderr (no bloquea; FR-015).
- **Rationale**: `ruff` no está instalado globalmente en este equipo; fijarlo en el proyecto
  garantiza la misma versión para todos.
- **Config**: `[tool.ruff]` con `line-length = 100` y `target-version = "py312"`.

## R7. Tests de hooks

- **Decision**: pytest, `test_<hook>.py` junto a cada hook. `conftest.py` expone
  `run_hook(script, payload: dict | str)`, que ejecuta `sys.executable <hook>` con el JSON por
  stdin, con `CLAUDE_PROJECT_DIR` apuntando a un `tmp_path`, y devuelve
  `(returncode, stdout, stderr)`.
- `pyproject.toml` declara `testpaths = [".claude/hooks"]`. Hay que pasar el directorio
  explícitamente porque pytest ignora por defecto los directorios ocultos al recursar.
- Los tests de `format_python` usan un archivo mal formateado en `tmp_path`, verifican que queda
  formateado y que un `.md` no se toca.

## R8. Reglas con alcance por ruta

- **Formato**: Markdown con frontmatter YAML `paths:` (lista de globs).
- `tests.md`: `**/test_*.py`, `**/*_test.py`, `tests/**`, que cubren los tests de hooks y los
  futuros.
- `mcp-server.md`: `src/**/mcp/**`, `src/**/mcp_server/**`. El servidor MCP del agente aún no
  existe; la regla queda lista para cuando llegue.
- `hooks.md`: `.claude/hooks/**` (stdlib only, fallo seguro, test obligatorio).
