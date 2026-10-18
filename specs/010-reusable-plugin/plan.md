# Implementation Plan: Plugin reutilizable por otros equipos

**Branch**: `develop` (feature dir `010-reusable-plugin`) | **Date**: 2026-10-18 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/010-reusable-plugin/spec.md` — Issue [#10](https://github.com/danielpvsofka/crediagil/issues/10)

## Summary

Empaquetar como plugin de Claude Code las piezas genéricas de `.claude/`, distribuido desde este
mismo repositorio, y blindarlo con un test que impide que diverja. No cambia ninguna regla de
negocio, política, prompt del agente de originación ni código de `src/`.

- **Plugin** `plugins/crediagil-devkit/`: subagentes `code-reviewer` y `compliance-reviewer`,
  skill `compliance-check`, hook `block_sensitive_data` (con su biblioteca `_hooklib`) y README.
- **Catálogo** `.claude-plugin/marketplace.json` en la raíz: anuncia el plugin con ruta relativa
  `./plugins/crediagil-devkit`. (El issue dice "en la raíz": el archivo debe estar en la carpeta
  `.claude-plugin/` de la raíz, que es donde Claude Code lo busca; ver R1.)
- **Copias, no enlaces**: un plugin no puede salir de su carpeta ni seguir enlaces fuera de ella, y
  los enlaces simbólicos no son fiables en Windows. Las originales siguen en `.claude/`.
- **Variantes declaradas**: dos archivos no pueden ser copia literal, porque un plugin ignora
  `hooks` en el frontmatter de un subagente y espacia los nombres (`crediagil-devkit:…`). Se
  declaran como sustituciones exactas sobre el original que el test aplica y comprueba (R3).
- **Test de divergencia** (`.claude/hooks/test_plugin_devkit.py`): copias idénticas (ignorando fin
  de línea) o variantes aplicadas, ninguna pieza sin clasificar, exclusiones respetadas, manifiestos
  coherentes y el hook empaquetado ejecutado de verdad con los mismos casos que el original.

Detalle y alternativas descartadas en [research.md](./research.md).

## Technical Context

**Language/Version**: Python ≥ 3.12 (tests y hook, como el resto del repo); manifiestos en JSON y
piezas en Markdown

**Primary Dependencies**: ninguna nueva. El hook usa solo la biblioteca estándar; el consumidor
necesita `uv` para ejecutarlo igual que aquí (se documenta en el README)

**Storage**: archivos versionados (`plugins/crediagil-devkit/**`, `.claude-plugin/marketplace.json`)

**Testing**: pytest, junto a los tests de hooks existentes (`testpaths` ya incluye `.claude/hooks`,
no hace falta tocar `pyproject.toml`). Sin red ni clave

**Target Platform**: Claude Code en Windows y Linux/macOS (por eso copias y no enlaces)

**Project Type**: paquete de configuración reutilizable (plugin) con su test de integridad

**Performance Goals**: la comprobación del plugin corre en menos de 10 s (SC-005); en la práctica
unos segundos, con 3–4 ejecuciones del hook como subproceso

**Constraints**:
- El plugin no incluye `require_specs`, `/open-pr`, `ticket`, `format_python`, `block_secret_access`
  ni las skills `speckit-*` (FR-006); cada pieza de `.claude/` queda clasificada o el test falla.
- Sin datos reales, secretos, tasa ni umbrales dentro del plugin (FR-011).
- Las piezas de este repositorio siguen intactas y funcionando desde `.claude/` (FR-012); la única
  edición de una original es la línea de la constitución ausente (FR-010).
- Un plugin no puede declarar componentes fuera de su carpeta: todo lo que necesita viaja dentro.

**Scale/Scope**: 4 piezas empaquetadas (2 subagentes, 1 skill, 1 hook) + 1 biblioteca, 2 manifiestos,
1 README, 1 módulo de test

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Antes del diseño | Después del diseño |
|---|---|---|
| I. Reglas de negocio | ✅ No se tocan; el plugin no contiene tasa, umbrales ni reglas | ✅ El test de FR-011 busca los parámetros de `crediagil.policy.params` dentro del plugin y falla si aparecen; el revisor de cumplimiento sigue leyendo la constitución del consumidor, no una copia |
| II. Garantía en código | ✅ El bloqueo de datos sigue siendo un hook, no un prompt | ✅ El subagente de cumplimiento empaquetado pierde `Bash` (el campo `hooks` de un subagente de plugin se ignora): la garantía "solo lectura" pasa a ser la lista de herramientas, también código. Se prueba que ningún revisor empaquetado puede escribir ni ejecutar |
| III. Datos ficticios | ✅ Nada real; ejemplos del README ficticios | ✅ Los tests del hook empaquetado construyen en ejecución la tarjeta y la cédula de prueba (sin literales); el README no lleva números con forma real |
| IV. Spec antes que código | ✅ spec.md aprobada | ✅ plan y tasks antes de escribir en `src/` o en el plugin (el plugin no está bajo `src/`, pero se sigue el flujo) |
| V. No inventar datos | ✅ No aplica | ✅ Sin cambio; `compliance-reviewer` ante constitución ausente declara el hallazgo en vez de inventar criterio |
| VI. Trazabilidad | ✅ No aplica | ✅ El informe de divergencia nombra pieza y archivo; el comentario del issue y el PR enlazan la spec |
| VII. Tests en bordes | ✅ Es el objeto de la feature | ✅ Test de divergencia con controles negativos (un byte distinto, archivo faltante, archivo sobrante, pieza sin clasificar, sustitución que ya no aplica) y diferencia de solo fin de línea que NO debe fallar |

Sin violaciones; la sección de complejidad no se usa.

## Project Structure

### Documentation (this feature)

```text
specs/010-reusable-plugin/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── plugin.md        # estructura del plugin, manifiestos, clasificación y variantes
├── checklists/
│   └── requirements.md
└── tasks.md             # lo genera /speckit-tasks
```

### Source Code (repository root)

```text
.claude-plugin/
└── marketplace.json                     # catálogo: lista crediagil-devkit

plugins/crediagil-devkit/
├── .claude-plugin/
│   └── plugin.json                      # nombre, versión, descripción
├── agents/
│   ├── code-reviewer.md                 # variante: sin la mención a /open-pr (R3)
│   └── compliance-reviewer.md           # variante: sin Bash ni hooks (R3)
├── skills/
│   └── compliance-check/
│       └── SKILL.md                     # variante: agent con espacio de nombres (R3)
├── hooks/
│   ├── hooks.json                       # PreToolUse → block_sensitive_data.py
│   ├── block_sensitive_data.py          # copia idéntica de .claude/hooks/
│   └── _hooklib.py                      # copia idéntica de .claude/hooks/
└── README.md                            # instalación, piezas, requisitos, convivencia, actualización

.claude/
├── agents/compliance-reviewer.md        # única edición de un original: aviso si falta la constitución (R5)
└── hooks/
    └── test_plugin_devkit.py            # test de divergencia y de integridad del plugin
```

**Structure Decision**: el plugin vive en una subcarpeta (`plugins/crediagil-devkit/`) y el
catálogo en la raíz, de modo que el repositorio es a la vez fuente de plugins y proyecto. La
subcarpeta evita que el plugin se confunda con `.claude/` y permite añadir más plugins después. El
test vive junto a los de los demás hooks (`.claude/hooks/`), que ya recoge `pytest`.

## Complexity Tracking

Sin violaciones que justificar. Las tres variantes declaradas (R3) no violan la constitución: son la
alternativa más simple que conserva el contrato "solo lectura" del revisor y una skill funcional
dentro de un plugin.
