# Data Model: Plugin reutilizable por otros equipos

No hay datos de negocio ni estado en ejecución: son archivos versionados y las tablas que el test
de integridad usa para vigilarlos. Todo es de solo lectura para el test.

## Plugin `crediagil-devkit`

| Campo (`plugin.json`) | Tipo | Regla |
|---|---|---|
| `name` | cadena | `crediagil-devkit`, kebab-case; es el espacio de nombres de sus piezas |
| `version` | cadena | semántica `MAYOR.MENOR.PARCHE`; igual a la de la entrada del catálogo |
| `description` | cadena | no vacía; dice qué incluye, sin repetir tasa ni umbrales |

## Catálogo `marketplace.json`

| Campo | Tipo | Regla |
|---|---|---|
| `name` | cadena | identificador kebab-case del catálogo |
| `owner.name` | cadena | no vacía |
| `plugins[]` | lista | una entrada por plugin |
| `plugins[].name` | cadena | igual al `name` de `plugin.json` |
| `plugins[].source` | cadena | `./plugins/crediagil-devkit`; la carpeta existe y contiene `.claude-plugin/plugin.json` |
| `plugins[].version` | cadena | igual a la de `plugin.json` |

## Pieza empaquetada

Una pieza es un archivo del plugin con un original en `.claude/`.

| Campo | Significado |
|---|---|
| `original` | ruta relativa a `.claude/` |
| `copia` | ruta relativa a `plugins/crediagil-devkit/` |
| `tipo` | `identica` o `variante` |
| `sustituciones` | solo en variantes: lista de pares (`antes`, `despues`) sobre el texto del original |

**Reglas de comparación**
- Se normaliza el fin de línea (`\r\n` → `\n`) en ambos lados antes de comparar.
- `identica`: el texto normalizado de la copia es igual al del original.
- `variante`: se aplica cada sustitución al original; **cada `antes` debe aparecer exactamente una
  vez**; el resultado debe ser igual al texto de la copia.
- Una pieza cuyo original o copia no existe es un incumplimiento.

### Piezas empaquetadas

| Original (`.claude/`) | Copia (`plugins/crediagil-devkit/`) | Tipo |
|---|---|---|
| `agents/code-reviewer.md` | `agents/code-reviewer.md` | variante (quita de la descripción la mención a `/open-pr`, que no viaja) |
| `agents/compliance-reviewer.md` | `agents/compliance-reviewer.md` | variante (quita `Bash` y `hooks`; la descripción dice "Solo lectura") |
| `skills/compliance-check/SKILL.md` | `skills/compliance-check/SKILL.md` | variante (`agent` con espacio de nombres; sin `Bash(uv run pytest:*)`; sin la mención a `/open-pr` en la descripción) |
| `hooks/block_sensitive_data.py` | `hooks/block_sensitive_data.py` | identica |
| `hooks/_hooklib.py` | `hooks/_hooklib.py` | identica |

Archivos propios del plugin, sin original: `.claude-plugin/plugin.json`, `hooks/hooks.json`,
`README.md`.

## Lista de exclusiones

Cada pieza de `.claude/` que no se empaqueta lleva su motivo.

| Pieza | Motivo |
|---|---|
| `hooks/require_specs.py` | exige la estructura de Spec Kit de este repositorio |
| `hooks/format_python.py` | formato de Python de este repositorio (ruff) |
| `hooks/block_secret_access.py` | supuestos del repositorio (`.env`, `secrets/`); trabajo futuro |
| `hooks/allow_only_pytest.py` | solo lo usa el frontmatter del revisor, que un plugin ignora (R3) |
| `commands/open-pr.md` | flujo de tickets de este repositorio |
| `skills/ticket/` | flujo de tickets de este repositorio |
| `skills/speckit-*` | instalados por Spec Kit; no son piezas propias |
| `settings.json` | configuración de este repositorio |

Quedan fuera por patrón, sin necesidad de clasificarse: `test_*.py`, `conftest.py`,
`__pycache__/`, `rules/`.

## Informe de divergencia

Resultado del test cuando algo no cuadra. Cada incumplimiento es una línea con:

| Campo | Contenido |
|---|---|
| `pieza` | nombre de la pieza o `sin clasificar` |
| `archivo` | ruta del archivo que difiere, falta, sobra o no está clasificado |
| `motivo` | `diverge`, `falta en el plugin`, `falta el original`, `sobra en el plugin`, `sin clasificar`, `sustitución no aplica`, `excluida presente` |

## Transiciones

No hay estados. Añadir una pieza a `.claude/` hace fallar el test (`sin clasificar`) hasta que se
añada a empaquetadas o a excluidas; subir de versión es una edición manual de los dos manifiestos.
