# Research: Plugin reutilizable por otros equipos

Lo marcado como decisión sale de la documentación oficial de plugins de Claude Code (consultada el
2026-10-18) y de leer las piezas de `.claude/`. Los puntos que dependen de instalar el plugin de
verdad se comprueban en el quickstart.

## R1 — Dónde va el catálogo y dónde el plugin

- **Decision**: catálogo en `.claude-plugin/marketplace.json` en la raíz del repositorio; plugin en
  `plugins/crediagil-devkit/` con su propio `.claude-plugin/plugin.json`. La entrada del catálogo
  usa `source: "./plugins/crediagil-devkit"` (ruta relativa a la raíz del catálogo).
- **Rationale**: Claude Code busca el catálogo en la carpeta `.claude-plugin/` de la raíz; el
  issue pide "`marketplace.json` en la raíz" y esto lo cumple en el único sitio donde funciona.
  Campos obligatorios del catálogo: `name`, `owner.name` y `plugins`; del plugin, solo `name`
  (kebab-case, que además es su espacio de nombres). Se declara también `version` y `description`
  (FR-013).
- **Alternatives considered**: `marketplace.json` suelto en la raíz (no lo encuentra el gestor de
  plugins); plugin en la raíz del repositorio (mezclaría `.claude/` con el plugin y haría que todo
  el repositorio se copie a la caché del consumidor).

## R2 — Copias idénticas, no enlaces

- **Decision**: el plugin lleva copias de las piezas; las originales siguen en `.claude/`.
- **Rationale**: un plugin se copia a una caché al instalarse y no puede declarar componentes fuera
  de su carpeta ni seguir enlaces simbólicos que salgan de ella. Además los enlaces simbólicos no son
  fiables en Windows, el sistema del equipo. Las copias exigen un test de divergencia, que es
  precisamente lo que pide el issue.
- **Alternatives considered**: mover las originales al plugin y que `.claude/` las cargue desde allí
  (rompe el flujo actual y FR-012); generar las copias con un script (otro paso manual que
  olvidar; el test falla igual y la corrección es copiar); enlaces o uniones de directorio (no
  portables).

## R3 — Qué no puede ser copia literal: tres variantes declaradas

La documentación fija dos reglas y el alcance del plugin añade una tercera causa:

1. **Un subagente de plugin ignora `hooks`, `mcpServers` y `permissionMode` en su frontmatter.**
   `compliance-reviewer` restringe `Bash` a `pytest` con un hook declarado en su frontmatter
   (`allow_only_pytest`). Empaquetado tal cual, el hook se ignoraría y el revisor tendría `Bash`
   sin restricción: un revisor que debe ser de solo lectura podría ejecutar cualquier comando.
2. **Los componentes de un plugin se espacian con su nombre.** La skill referencia al subagente con
   `agent: compliance-reviewer`; dentro del plugin se llama `crediagil-devkit:compliance-reviewer`.

3. **Las descripciones no pueden remitir a piezas que no viajan.** `code-reviewer` y `compliance-check`
   dicen en su descripción que los invoca `/open-pr`, que es del flujo de este repositorio.

- **Decision**: las tres piezas se empaquetan como **variante declarada**: el test aplica al original
  una lista de sustituciones exactas y exige que el resultado sea el archivo del plugin.
  - `agents/code-reviewer.md`: quitar de la descripción " Lo invoca /open-pr.". Nada más.
  - `agents/compliance-reviewer.md`: quitar `Bash` de `tools`, quitar el bloque `hooks:` y cambiar
    "Lectura y pytest" por "Solo lectura" en la descripción. El
    revisor empaquetado es de solo lectura (Read, Grep, Glob); no ejecuta pytest. Su cuerpo no se
    toca.
  - `skills/compliance-check/SKILL.md`: `agent: compliance-reviewer` → `agent:
    crediagil-devkit:compliance-reviewer`; la descripción deja de nombrar `/open-pr`. Se quita
    `Bash(uv run pytest:*)` de `allowed-tools`
    para que la skill no prometa lo que su subagente ya no puede hacer.
  - Cada sustitución debe aplicar exactamente una vez; si el original cambia y deja de aplicar, el
    test falla y obliga a revisar la variante.
- **Rationale**: mantiene el contrato "los revisores no escriben ni ejecutan comandos libres" como
  verificación determinista (Principio II) en lugar de depender de un hook que no se cargaría. Es
  más simple que reescribir las piezas aparte (la variante comparte todo el texto con el original)
  y más honesto que una copia "idéntica" que no se comporta igual.
- **Alternatives considered**: hook de plugin sobre `Bash` que limite a pytest (se aplicaría a
  todas las sesiones del consumidor, no solo al revisor: bloquearía su trabajo normal); dejar
  `Bash` sin restricción (viola el solo lectura); no empaquetar `compliance-reviewer` (la skill
  quedaría rota, incumple FR-003); mantener dos archivos escritos a mano (diverge sin que nada lo
  detecte).
- **Coste conocido**: el cuerpo del revisor sigue diciendo que puede ejecutar `uv run pytest`; en
  el plugin esa herramienta no está y el revisor lo omite. Se documenta en el README; reescribir
  el cuerpo es trabajo futuro.

## R4 — El hook y su biblioteca

- **Decision**: `hooks/hooks.json` declara un `PreToolUse` con el mismo `matcher`
  (`Write|Edit|MultiEdit|NotebookEdit`) que `.claude/settings.json` y ejecuta
  `uv run --no-project python "${CLAUDE_PLUGIN_ROOT}/hooks/block_sensitive_data.py"`. El plugin
  lleva `block_sensitive_data.py` y `_hooklib.py`, copias idénticas.
- **Rationale**: `${CLAUDE_PLUGIN_ROOT}` apunta al plugin instalado; `_hooklib` se resuelve porque
  vive en la misma carpeta que el script. El hook lee el contenido del evento, no del
  repositorio, así que no depende de nada de Crediágil. `hooks.json` no es copia de `settings.json`
  (la ruta cambia), por eso el test lo valida aparte: el comando apunta a un script que existe en
  el plugin y el matcher coincide con el de `settings.json`.
- **Alternatives considered**: copiar también `block_secret_access` (no se pidió y tiene supuestos
  del repositorio: va a trabajo futuro); empaquetar los tests del hook (no deben viajar con el
  plugin; se ejecutan contra la copia desde el test del repositorio, ver R6).

## R5 — Constitución ausente en el consumidor (FR-010)

- **Decision**: añadir al original `.claude/agents/compliance-reviewer.md`, en el paso 1 del
  procedimiento, una línea: si `.specify/memory/constitution.md` no existe, responder
  `VEREDICTO: BLOQUEANTE` con un hallazgo que diga que falta la constitución y dónde se espera. El
  cambio se propaga a la variante porque el cuerpo es común.
- **Rationale**: es la única edición de un original y no cambia lo que hace en este repositorio
  (la constitución existe). Un veredicto bloqueante con motivo es coherente con `/open-pr`, que ya
  trata una respuesta sin veredicto válido como bloqueante.
- **Alternatives considered**: bandera de configuración (más piezas por una línea); no tratar el
  caso (el revisor "revisaría" sin criterio: el riesgo que FR-010 quiere evitar).

## R6 — El test de divergencia

- **Decision**: `.claude/hooks/test_plugin_devkit.py`, con tres tablas explícitas al principio:
  `EMPAQUETADAS` (original → copia), `VARIANTES` (copia → sustituciones sobre el original) y
  `EXCLUIDAS` (lo de `.claude/` que no se empaqueta y por qué). Comprobaciones:
  1. cada copia coincide con su original tras normalizar fin de línea; cada variante coincide con
     el original tras aplicar sus sustituciones;
  2. cada archivo de `.claude/agents`, `.claude/skills`, `.claude/commands` y `.claude/hooks` (sin
     tests, `conftest` ni `__pycache__`) está en una de las tres tablas;
  3. el plugin no contiene archivos fuera de las tablas (nada sobrante) ni los excluidos;
  4. `plugin.json` y `marketplace.json` son JSON válido, coherentes (nombre, versión, ruta) y la
     ruta del catálogo existe;
  5. `hooks.json` apunta a un script del plugin y su matcher coincide con el de `settings.json`;
  6. el plugin no contiene la tasa ni los umbrales de `crediagil.policy.params` ni datos con forma
     real (se pasa el propio detector sobre los archivos del plugin);
  7. el hook empaquetado, ejecutado como subproceso, bloquea una tarjeta y una cédula construidas en
     ejecución, y permite la misma línea con `dato-ficticio` (SC-004).
  El mensaje de fallo nombra pieza y archivo (FR-008). Controles negativos sobre una copia temporal
  del árbol: un byte distinto, un archivo faltante, uno sobrante y una pieza nueva sin clasificar
  deben fallar; solo cambiar el fin de línea no.
- **Rationale**: tablas explícitas hacen que añadir una pieza obligue a decidir; ejecutar el hook
  empaquetado prueba el comportamiento, no solo la igualdad de bytes. Vive en `.claude/hooks/`
  porque `pytest` ya recoge esa carpeta y allí están los tests de las demás piezas.
- **Alternatives considered**: comparar solo hashes (sin mensaje útil); un script aparte de
  sincronización (otro comando que recordar); ubicar el test dentro del plugin (viajaría al
  consumidor y dependería de `.claude/`, que allí no existe).

## R7 — Versión y actualización (FR-013)

- **Decision**: `version` semántica en `plugin.json` y en la entrada del catálogo, con un test que
  comprueba que existen y coinciden. Se sube a mano cuando cambia el contenido; el README explica
  cómo el consumidor actualiza.
- **Rationale**: lo mínimo que el consumidor necesita para ver una actualización. Forzar por test
  que la versión cambie con cada edición exigiría guardar una huella del contenido por versión;
  queda como trabajo futuro, junto con automatizar el versionado (ya fuera de alcance).
- **Alternatives considered**: huella de contenido en el manifiesto con test (más piezas de las que
  pide el ticket); sin versión (el consumidor no distingue versiones).

## R8 — Convivencia con piezas del mismo nombre

- **Decision**: no se hace nada especial. Los componentes del plugin se invocan con su espacio de
  nombres (`crediagil-devkit:code-reviewer`, `/crediagil-devkit:compliance-check`), así que no
  chocan con piezas propias del consumidor. El README lo explica con un ejemplo.
- **Rationale**: es el comportamiento nativo del gestor de plugins; no hay nada que implementar.

## Fuera de alcance (trabajo futuro, no bloqueante)

- Reescribir el cuerpo del revisor empaquetado para no mencionar pytest.
- Empaquetar `block_secret_access` y un `settings` base para consumidores.
- Forzar por test que la versión cambie cuando cambia el contenido y automatizar el versionado.
- Publicar el plugin en un catálogo público.
