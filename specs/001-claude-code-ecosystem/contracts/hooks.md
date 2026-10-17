# Contract: Hooks

Todos los hooks leen un `HookEvent` (ver [data-model.md](../data-model.md)) desde stdin y
responden con un `HookDecision`. Los casos listados son el mínimo que debe cubrir el test de
cada hook (FR-016). Los números "Luhn válidos" se generan en tiempo de ejecución.

## require_specs.py

- **Evento / matcher**: PreToolUse · `Write|Edit|MultiEdit|NotebookEdit`
- **Entrada relevante**: ruta de destino; `.specify/feature.json`
- **Salida**: 0 si la ruta está fuera de `src/` o la feature activa está completa; 2 en otro
  caso. stderr con la feature evaluada y los documentos faltantes.

| # | Caso | Esperado |
|---|------|----------|
| 1 | `src/app.py`, feature con los 3 documentos | 0 |
| 2 | `src/app.py`, falta `tasks.md` | 2, menciona `tasks.md` |
| 3 | `src/app.py`, `plan.md` vacío | 2, menciona `plan.md` |
| 4 | `src/app.py`, sin `feature.json` | 2, explica cómo declarar la feature |
| 5 | `docs/x.md` sin feature | 0 |
| 6 | Ruta absoluta y con `\` bajo `src` | igual que la relativa |
| 7 | `srcx/a.py` (prefijo, no directorio) | 0 |
| 8 | stdin no JSON | 2 |

## block_sensitive_data.py

- **Evento / matcher**: PreToolUse · `Write|Edit|MultiEdit|NotebookEdit`
- **Entrada relevante**: contenido nuevo (`content` / `new_string` / `edits[].new_string` /
  `new_source`)
- **Salida**: 0 si no hay hallazgos; 2 con lista de `kind` + línea + valor enmascarado.

| # | Caso | Esperado |
|---|------|----------|
| 1 | 16 dígitos Luhn válido, empieza por 4 | 2 (`tarjeta`) |
| 2 | El mismo con el dígito de control alterado | 0 |
| 3 | Luhn válido con espacios y con guiones | 2 |
| 3b | Tarjeta junto a otro número separado por espacio o guion (CVV, vencimiento) | 2 |
| 4 | Longitudes 12 y 20 (Luhn válido) | 0 |
| 5 | Longitudes 13 y 19 (Luhn válido) | 2 |
| 6 | Timestamp ms de 13 dígitos que empieza por 1 | 0 |
| 7 | `cédula: ` + 10 dígitos | 2 (`documento`) |
| 8 | `cuenta de ahorros ` + 11 dígitos | 2 (`cuenta`) |
| 9 | Caso 7 con `# pragma: dato-ficticio` en la línea | 0 |
| 10 | Monto `5000000` y `monto: 5.000.000 COP` | 0 |
| 11 | MultiEdit con el hallazgo en el segundo edit | 2 |
| 12 | stderr no contiene el número completo | ✔ |
| 13 | stdin no JSON | 2 |

## block_secret_access.py

- **Evento / matcher**: PreToolUse · `Bash|PowerShell`
- **Entrada relevante**: `tool_input.command`
- **Salida**: 0 si el comando no referencia `.env*` ni `secrets/`; 2 en otro caso.

| # | Comando | Esperado |
|---|---------|----------|
| 1 | `cat .env` | 2 |
| 2 | `cat ./.env.local` / `less .env.production` | 2 |
| 3 | `Get-Content .env` / `gc .env` / `type .env` | 2 |
| 4 | `grep KEY < .env` / `cp .env /tmp/x` | 2 |
| 5 | `cat secrets/token.txt` / `type secrets\token.txt` | 2 |
| 6 | `cat .env.example` | 2 |
| 7 | `git status` / `ls -la` / `uv run pytest` | 0 |
| 8 | `cat src/environment.py` / `echo .envelope` | 0 |
| 9 | stdin no JSON | 2 |

## format_python.py

- **Evento / matcher**: PostToolUse · `Write|Edit|MultiEdit`
- **Salida**: 0 tras formatear o si el archivo no es `.py`; 1 con aviso si ruff no está
  disponible o falla. Nunca 2.

| # | Caso | Esperado |
|---|------|----------|
| 1 | `.py` mal formateado | 0, archivo formateado |
| 2 | `.md` | 0, archivo intacto |
| 3 | ruff no disponible (PATH vacío) | 1, archivo intacto |
| 4 | stdin no JSON | 1 |
