# Contrato: estructura del plugin, manifiestos y test de integridad

Lo que el consumidor ve y lo que el test garantiza. Los nombres de campo de los manifiestos son
los de la documentación de plugins de Claude Code.

## Disposición de archivos

```text
.claude-plugin/marketplace.json                       # catálogo (raíz del repositorio)
plugins/crediagil-devkit/
├── .claude-plugin/plugin.json
├── agents/code-reviewer.md
├── agents/compliance-reviewer.md
├── skills/compliance-check/SKILL.md
├── hooks/hooks.json
├── hooks/block_sensitive_data.py
├── hooks/_hooklib.py
└── README.md
```

Nada fuera de la carpeta del plugin: un plugin no puede referenciar archivos externos ni enlaces
que salgan de ella.

## `.claude-plugin/marketplace.json`

```json
{
  "name": "crediagil",
  "owner": { "name": "Crediágil" },
  "description": "Piezas reutilizables de desarrollo de Crediágil, una fintech ficticia",
  "plugins": [
    {
      "name": "crediagil-devkit",
      "source": "./plugins/crediagil-devkit",
      "description": "Revisores, revisión de cumplimiento y bloqueo de datos con forma real",
      "version": "0.1.0"
    }
  ]
}
```

## `plugins/crediagil-devkit/.claude-plugin/plugin.json`

```json
{
  "name": "crediagil-devkit",
  "version": "0.1.0",
  "description": "Revisores, revisión de cumplimiento y bloqueo de datos con forma real",
  "author": { "name": "Crediágil" }
}
```

## `plugins/crediagil-devkit/hooks/hooks.json`

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write|Edit|MultiEdit|NotebookEdit",
        "hooks": [
          {
            "type": "command",
            "command": "uv run --no-project python \"${CLAUDE_PLUGIN_ROOT}/hooks/block_sensitive_data.py\""
          }
        ]
      }
    ]
  }
}
```

El `matcher` es el mismo que el de `block_sensitive_data` en `.claude/settings.json`.

## Qué ve el consumidor

| Pieza | Nombre con espacio de nombres | Cómo se usa |
|---|---|---|
| Subagente de código | `crediagil-devkit:code-reviewer` | se le pasa un diff; devuelve `VEREDICTO:` y hallazgos |
| Subagente de cumplimiento | `crediagil-devkit:compliance-reviewer` | lo invoca la skill; solo lectura |
| Skill | `/crediagil-devkit:compliance-check [nota]` | revisa `git diff main...HEAD -- src/` contra la constitución del consumidor |
| Hook | automático | niega escrituras con tarjeta válida por Luhn o cédula/NIT/cuenta con etiqueta, salvo `dato-ficticio` en la misma línea |

## Requisitos del repositorio consumidor (los documenta el README)

- `uv` instalado (ejecuta el hook).
- Para `compliance-check`: una constitución en `.specify/memory/constitution.md`, rama base `main`
  y código bajo `src/`. Sin la constitución, el revisor responde `VEREDICTO: BLOQUEANTE` y dice que
  falta (FR-010).
- Convivencia: las piezas del plugin siempre llevan el prefijo `crediagil-devkit:`; no pisan piezas
  propias del mismo nombre.

## Contrato del test de integridad (`.claude/hooks/test_plugin_devkit.py`)

Falla, con un mensaje que nombra pieza y archivo, cuando:

| # | Condición | Motivo en el informe |
|---|---|---|
| 1 | copia ≠ original (tras normalizar fin de línea) | `diverge` |
| 2 | variante ≠ original con sus sustituciones aplicadas | `diverge` |
| 3 | una sustitución no aparece exactamente una vez en el original | `sustitución no aplica` |
| 4 | falta la copia o el original | `falta en el plugin` / `falta el original` |
| 5 | el plugin tiene un archivo que no está en la tabla | `sobra en el plugin` |
| 6 | una pieza de `.claude/` no está en empaquetadas ni excluidas | `sin clasificar` |
| 7 | una pieza excluida aparece en el plugin | `excluida presente` |
| 8 | manifiestos inválidos, versiones distintas o `source` inexistente | `manifiesto` |
| 9 | `hooks.json` apunta a un script ausente o su `matcher` difiere del de `settings.json` | `hook` |
| 10 | un revisor empaquetado declara una herramienta de escritura, `Bash` o `hooks` | `revisor` |
| 11 | el plugin contiene la tasa o un umbral de la política, o un dato con forma real | `dato` |
| 12 | el hook empaquetado no bloquea tarjeta o cédula construidas en ejecución, o no respeta `dato-ficticio` | `hook` |

No falla cuando solo cambia el fin de línea de un archivo.

Controles negativos (sobre una copia temporal del árbol, nunca sobre el real): cambiar un byte de
una copia, borrar una copia, añadir un archivo al plugin, añadir una pieza a `.claude/` sin
clasificar y cambiar un original de modo que una sustitución deje de aplicar deben fallar con el
motivo esperado.
