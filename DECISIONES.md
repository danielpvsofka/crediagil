# Decisiones del ecosistema y del agente

Criterio general: **lo determinista se garantiza con código y lo que requiere juicio se guía
con instrucciones**. Una regla de negocio nunca depende solo de un prompt.

## Necesidades del ecosistema de Claude Code

| # | Necesidad | Mecanismo | Por qué / alternativa descartada |
|---|---|---|---|
| 1 | Convenciones del equipo sin configurar nada | `CLAUDE.md` raíz y `.claude/settings.json` versionados | Se cargan al clonar; `~/.claude` es personal y no viaja con el repo. |
| 2 | Lo personal no afecta al equipo | `~/.claude/CLAUDE.md`, `CLAUDE.local.md` y `settings.local.json` en `.gitignore` | Separa ámbitos por ubicación, no por disciplina. |
| 3 | Tests en muchas carpetas, mismas convenciones | `.claude/rules/tests.md` con `paths` | Los tests están dispersos: una regla por patrón aplica en todas partes; un `CLAUDE.md` por carpeta duplicaría el texto. |
| 4 | Sin código sin spec | Hook `PreToolUse` `require_specs.py` | Es verificable: existen o no `spec.md`, `plan.md` y `tasks.md` de la feature activa; como instrucción sería una sugerencia. Solo aplica a `src/`, para no bloquear la escritura de las specs. |
| 5 | Nada con forma de dato real | Hook `PreToolUse` `block_sensitive_data.py` y, en el CI, `scripts/scan_repo.py` con el mismo detector | El hook cubre lo que escribe Claude; el CI, cualquier otra vía, y además archivos de entorno y credenciales. Tarjetas con Luhn y cédulas o cuentas por etiqueta, para no bloquear montos. Un fixture ficticio lleva `dato-ficticio` en la misma línea. |
| 6 | No leer ni modificar secretos | `permissions.deny` y hook `block_secret_access.py` sobre Bash y PowerShell | `deny` cubre Read, Edit y Write, pero leer el archivo con `cat` lo esquivaría; el hook cierra ese hueco. |
| 7 | Formato tras cada edición | Hook `PostToolUse` `format_python.py` (ruff) y, en el CI, `ruff format --check` | Es consecuencia de la edición, no condición: por eso es Post y nunca bloquea. El CI cubre lo escrito sin Claude Code. |
| 8 | Revisión independiente antes del PR | Subagente `code-reviewer` (Read, Grep, Glob) invocado por `/open-pr` | Contexto aislado, sin el sesgo de quien escribió el código y sin poder editar. |
| 9 | Cumplimiento de reglas de negocio | Subagente `compliance-reviewer` y skill `compliance-check` (`context: fork`) | La auditoría es larga y ruidosa: el fork no contamina la sesión. El revisor solo ejecuta `pytest` (hook `allow_only_pytest`) y marca como crítico que la regla 1 o 2 dependa del prompt. |
| 10 | Tickets sincronizados sin intervención | Skill `/ticket` (→ In progress), `/open-pr` (→ In review) y workflow del Project (→ Done) | Done lo hace GitHub al fusionar con `Closes #N`: no depende de una sesión abierta. |
| 11 | Otro equipo instala las piezas | Plugin `crediagil-devkit` y catálogo `.claude-plugin/marketplace.json` | Empaqueta lo genérico (revisores, `compliance-check`, hook de datos); lo propio de este repo queda fuera. **Copias, no enlaces**: un plugin no puede salir de su carpeta y los enlaces fallan en Windows; un test falla si divergen. Un plugin ignora `hooks` en un subagente: el revisor empaquetado es de solo lectura y el test declara esa variante. |

**Memoria y MCP:** el `CLAUDE.md` raíz importa la constitución para no duplicarla y
`.claude/rules/` carga el contexto de cada zona solo al trabajar en ella. `.mcp.json` usa
`${GITHUB_PAT}` (el token nunca toca el repo) y el header `X-MCP-Toolsets` para habilitar `projects`.

**CI:** `.github/workflows/ci.yml` en tres trabajos independientes (formato, pruebas, escaneo)
para que un fallo no oculte otro; sin secretos ni pruebas con el modelo, con permisos de solo
lectura y acciones fijadas por commit. El escáner excluye `uv.lock`: es generado y sus hashes
parecen cédulas.

## Agente

- **Reglas 1 y 2 en hooks del SDK:** `PreToolUse` sobre `registrar_solicitud` y
  `preaprobar_credito`. Recalculan desde el estado del core con `crediagil.policy`, no desde lo
  que afirma el modelo, y fallan cerrado. El core también valida (defensa en profundidad).
- **Ciclo agéntico:** `clasificar_parada` decide por `stop_reason`: `end_turn` termina,
  `max_tokens` continúa hasta un máximo, y `refusal`, el tope de turnos, un error de la API o una
  razón desconocida son incidentes que se escalan por código. Sin contador de iteraciones ni
  búsqueda de palabras.
- **Estado compartido en JSON con lock:** el servidor MCP y los hooks son procesos distintos y
  deben ver la misma verdad; descarté la memoria y una base de datos (fuera de alcance).
- **Extracción:** el subagente `extractor-documentos` recibe el documento completo y solo usa
  `validar_extraccion`. Cada campo es `{valor, fragmento}`: sin fragmento literal se rechaza. Un
  dato ausente no se reintenta ni se infiere: se pide con `solicitar_informacion`.
- **Errores y descripciones:** `transitorio | validacion | negocio | permisos` más `reintentable`.
  `calcular_capacidad_pago` empieza con "SOLO SIMULA" y `preaprobar_credito` con "COMPROMETE A
  CREDIÁGIL".
- **Interfaz:** web local, un solo `Agente` por sesión y un turno a la vez. Los avisos salen del
  `ResultadoTurno`, nunca del texto del modelo, y todo texto entra con `textContent`. Solo escucha
  en `127.0.0.1`, sin autenticación ni comprobación de `Origin` (brecha documentada).
- **Claves y aislamiento:** `ANTHROPIC_API_KEY` viene del entorno o de un archivo local ignorado
  por git y `redactar()` la quita de logs y errores; `setting_sources=[]` impide que el agente
  herede la configuración de Claude Code (el valor por defecto `None` no aísla).
- **Casos de prueba:** catálogo único en `src/crediagil/casos/`, una carpeta por caso con mensaje,
  documentos y extracción esperada con fragmentos literales. Sin modelo no se puede ejecutar al
  extractor, así que esa extracción permite probar las reglas con el core, los hooks y la política
  reales. El mismo catálogo dirige las pruebas con el modelo real (sobre la traza, nunca el texto) y
  el selector de la interfaz.
