# Decisiones del ecosistema y del agente

Criterio general: **lo determinista se garantiza con código y lo que requiere juicio se guía
con instrucciones**. Una regla de negocio nunca depende solo de un prompt.

## Necesidades del ecosistema de Claude Code

| # | Necesidad | Mecanismo | Por qué / alternativa descartada |
|---|---|---|---|
| 1 | Convenciones del equipo sin configurar nada | `CLAUDE.md` raíz y `.claude/settings.json` versionados | Se cargan al clonar. Descarté `~/.claude`, que es personal y no viaja con el repo. |
| 2 | Lo personal no afecta al equipo | `~/.claude/CLAUDE.md`, `CLAUDE.local.md` y `settings.local.json` en `.gitignore` | Separa ámbitos por ubicación, no por disciplina. |
| 3 | Tests en muchas carpetas, mismas convenciones | `.claude/rules/tests.md` con `paths: src/**/test_*.py` | Los tests están dispersos: una regla por patrón aplica en todas partes. Un `CLAUDE.md` por carpeta duplicaría el texto. |
| 4 | Sin código sin spec | Hook `PreToolUse` `require_specs.py` (exit 2) | Es verificable: existen o no `spec.md`, `plan.md` y `tasks.md` de la feature activa (`.specify/feature.json`). Como instrucción sería una sugerencia. Solo aplica a `src/`, para no bloquear la propia escritura de specs. |
| 5 | Nada con forma de dato real | Hook `PreToolUse` `block_sensitive_data.py` (el job de CI con el mismo script es el issue #11, pendiente) | El hook cubre lo que escribe Claude; el CI cubrirá cualquier otra vía. Tarjetas con Luhn y cédulas o cuentas por etiqueta, para no bloquear montos. Un fixture deliberadamente ficticio lleva `dato-ficticio` en la misma línea. |
| 6 | No leer ni modificar secretos | `permissions.deny` y hook `block_secret_access.py` sobre Bash y PowerShell | `deny` cubre Read/Edit/Write, pero `cat .env` lo esquivaría; el hook cierra ese hueco. |
| 7 | Formato tras cada edición | Hook `PostToolUse` `format_python.py` (ruff) | Es consecuencia de la edición, no condición: por eso es Post y nunca bloquea. |
| 8 | Revisión independiente antes del PR | Subagente `code-reviewer` (Read, Grep, Glob) invocado por `/open-pr` | Corre en contexto aislado, sin el sesgo de la sesión que generó el código, y sin poder editar. |
| 9 | Cumplimiento de reglas de negocio | Subagente `compliance-reviewer` y skill `compliance-check` (`context: fork`) | La auditoría es larga y ruidosa: el fork no contamina la sesión principal. El revisor solo ejecuta `pytest` (hook `allow_only_pytest` en su frontmatter). Marca como crítico si la regla 1 o 2 depende del prompt. |
| 10 | Tickets sincronizados sin intervención | Skill `/ticket` (→ In progress), comando `/open-pr` (→ In review) y workflow del Project (→ Done) | Done lo hace GitHub al cerrarse el issue con el merge (`Closes #N`): no depende de que haya una sesión abierta. |
| 11 | Otro equipo instala las piezas | Plugin `crediagil-devkit` y `marketplace.json` (issue #10, **pendiente**) | Empaquetará lo genérico (reviewer, compliance y el hook de datos). Lo específico de este repo (`require_specs`, `/ticket`) quedará fuera. Un test evitará que las copias diverjan. |

**Memoria:** el `CLAUDE.md` raíz hace `@import` de la constitución para no duplicarla.
Las reglas por ruta (`.claude/rules/`: `tests.md`, `hooks.md`, `mcp-server.md`) cargan el
contexto de cada zona solo al trabajar en ella, sin duplicar texto en `CLAUDE.md`.

**MCP:** `.mcp.json` versionado con `${GITHUB_PAT}` (expansión de variable de entorno; el
token nunca toca el repo) y el header `X-MCP-Toolsets` para habilitar el toolset `projects`,
que no viene por defecto.

## Agente

- **Reglas 1 y 2 en hooks del SDK** (`agent/hooks.py`): `PreToolUse` sobre
  `registrar_solicitud` y `preaprobar_credito`. Recalculan desde el estado del core con
  `crediagil.policy`, no desde lo que afirma el modelo, y fallan cerrado. El core también
  valida (defensa en profundidad), pero la garantía del agente es el hook.
- **Ciclo agéntico:** el SDK itera mientras el modelo pide herramientas. Al llegar el
  `ResultMessage`, `clasificar_parada` decide por `stop_reason`: `end_turn` y `stop_sequence`
  terminan; `max_tokens` (y `model_context_window_exceeded`) es `TRUNCADA` y se continúa hasta
  un máximo de continuaciones; `refusal`, el tope de turnos, un error de la API y cualquier
  razón desconocida (incluida `pause_turn`) son incidentes que se escalan por código. No hay
  contador de iteraciones como criterio ni búsqueda de palabras.
- **Estado compartido en JSON con lock:** el servidor MCP (stdio) y los hooks están en
  procesos distintos y deben ver la misma verdad. Descarté el estado en memoria por eso, y
  una base de datos por estar fuera de alcance.
- **Extracción:** el subagente `extractor-documentos` recibe el documento completo en el
  prompt (no ve la conversación) y solo puede usar `validar_extraccion`. Cada campo es
  `{valor, fragmento}`: un valor sin fragmento literal se rechaza. El reintento solo ocurre
  si el error es `validacion` reintentable. Un dato ausente (`INGRESO_NO_VERIFICABLE`) no es
  reintentable: se pide al solicitante con `solicitar_informacion`.
- **Errores:** `transitorio | validacion | negocio | permisos` más `reintentable`. Una
  búsqueda vacía no es error.
- **Descripciones:** `calcular_capacidad_pago` empieza con "SOLO SIMULA" y
  `preaprobar_credito` con "COMPROMETE A CREDIÁGIL", cada una diciendo cuándo usar la otra.
- **Ingreso verificado:** el certificado es la fuente del salario y los extractos lo
  corroboran. Si el salario falta, no se infiere desde los extractos: se pide.
- **Interfaz:** aplicación web local (Starlette y JavaScript sin build). Un solo `Agente`
  abierto por sesión, un turno a la vez (otro simultáneo recibe 409). Cada acción con efecto
  (preaprobar, pedir, escalar, bloqueo) aparece como aviso propio, tomado del `ResultadoTurno`
  y nunca del texto del modelo; el detalle técnico queda en un desplegable cerrado. Todo texto
  entra con `textContent`. Solo escucha en `127.0.0.1`, sin autenticación ni comprobación de
  `Origin` (brecha documentada, no exponer en red).
- **Claves:** `ANTHROPIC_API_KEY` viene del entorno o de un archivo local ignorado por git;
  `redactar()` la quita de logs, trazas, errores y respuestas de la API.
- **Aislamiento del agente:** `setting_sources=[]` (el valor por defecto `None` no aísla), de
  modo que el agente no hereda la configuración de Claude Code del repositorio.
- **Casos de prueba:** un catálogo único en `src/crediagil/casos/`, una carpeta por caso con el
  mensaje, los documentos y la **extracción esperada** junto a cada documento (con fragmentos
  literales, que el cargador comprueba). Sin modelo no se puede ejecutar al extractor, así que la
  extracción esperada permite probar las reglas con el core, los hooks y la política reales sin
  reimplementarlas. El mismo catálogo dirige las pruebas con el modelo real (`esperado.herramientas`
  se comprueba sobre la traza, nunca sobre el texto) y el selector de la interfaz. Los bordes
  salen de `crediagil.policy.params`. Una prueba rompe cada regla y comprueba que su caso falla.
  Se mantiene la marca `live` en lugar de `e2e`: dos nombres para lo mismo confundirían.
