# Data Model: Ecosistema base de Claude Code

No hay persistencia. Las "entidades" son los mensajes que intercambian Claude Code y los hooks,
y los archivos de configuración que los gobiernan.

## HookEvent (entrada, JSON por stdin)

| Campo | Tipo | Notas |
|-------|------|-------|
| `hook_event_name` | `"PreToolUse"` \| `"PostToolUse"` | |
| `tool_name` | string | `Write`, `Edit`, `MultiEdit`, `NotebookEdit`, `Bash`, `PowerShell` |
| `tool_input` | object | Forma según la herramienta (ver abajo) |
| `cwd` | string | Respaldo si falta `CLAUDE_PROJECT_DIR` |

`tool_input` por herramienta:

- `Write`: `file_path`, `content`
- `Edit`: `file_path`, `old_string`, `new_string`
- `MultiEdit`: `file_path`, `edits[]` con `new_string`
- `NotebookEdit`: `notebook_path`, `new_source`
- `Bash` / `PowerShell`: `command`

**Validación**: si el JSON no se puede parsear o faltan campos requeridos, un hook de bloqueo
termina con salida 2 (FR-017).

## HookDecision (salida)

| Resultado | Código | stderr |
|-----------|--------|--------|
| Permitir | 0 | vacío |
| Bloquear (PreToolUse) | 2 | motivo accionable, prefijado `[<hook>]` |
| Aviso no bloqueante (PostToolUse) | 1 | descripción del fallo |

## ActiveFeature

- Fuente: `.specify/feature.json` → `feature_directory` (ruta relativa a la raíz).
- Documentos requeridos: `spec.md`, `plan.md`, `tasks.md`.
- Estado: **completa**, si los tres existen y no están vacíos; **incompleta**, si falta alguno o
  está vacío; **indeterminada**, si no hay `feature.json`, falta la clave o el directorio no
  existe.
- Regla: un cambio a `src/` solo se permite con la feature en estado **completa**.

## SensitiveFinding

| Campo | Descripción |
|-------|-------------|
| `kind` | `tarjeta` \| `documento` \| `cuenta` |
| `line` | Número de línea dentro del contenido evaluado |
| `masked` | Valor enmascarado, p. ej. `••••1234` (nunca el valor completo) |

## Mapeo regla → mecanismo (Principio II)

| Regla | Mecanismo | Requisito |
|-------|-----------|-----------|
| Convenciones al clonar | `CLAUDE.md` + `@import` | FR-001 |
| Personal fuera del repo | `.gitignore` | FR-002 |
| Guía por ruta | `.claude/rules/*.md` | FR-003 |
| Spec antes que código | hook `require_specs` | FR-005–007 |
| Datos ficticios | hook `block_sensitive_data` | FR-008–010a |
| Secretos (herramientas de archivo) | `permissions.deny` | FR-011 |
| Secretos (terminal) | hook `block_secret_access` | FR-012 |
| Credenciales MCP | `.mcp.json` con `${GITHUB_PAT}` | FR-013 |
| Formato | hook `format_python` | FR-014–015 |
