# crediagil-devkit

Piezas reutilizables de desarrollo de Crediágil (una fintech ficticia) para Claude Code: dos
revisores independientes, una revisión de cumplimiento y un bloqueo de datos con forma real.
Se instala en cualquier repositorio sin copiar archivos a mano.

## Qué incluye

| Pieza | Nombre | Qué hace |
|---|---|---|
| Subagente | `crediagil-devkit:code-reviewer` | Revisa un diff de forma independiente: corrección, tests junto al código y datos ficticios. Solo lectura. |
| Subagente | `crediagil-devkit:compliance-reviewer` | Compara un diff con la constitución del proyecto. Lo usa la skill; no se invoca a mano. Solo lectura. |
| Skill | `/crediagil-devkit:compliance-check` | Revisa en un contexto aislado los cambios de `src/` frente a `main` y responde `VEREDICTO:` con sus hallazgos. |
| Hook | `block_sensitive_data` | Antes de escribir o editar, bloquea contenido con una tarjeta válida por Luhn o con una cédula, un NIT o una cuenta junto a su etiqueta. |

El hook deja pasar una línea que lleve el marcador `dato-ficticio`, para los datos de prueba
deliberadamente inventados. El marcador solo se pone en datos que no puedan ser reales.

## Requisitos del repositorio donde se instala

- Claude Code con soporte de plugins y `uv` instalado: el hook se ejecuta con
  `uv run --no-project python`.
- Para `compliance-check`:
  - una constitución del proyecto en `.specify/memory/constitution.md`;
  - la rama base `main`;
  - el código de negocio bajo `src/`.
- Sin la constitución, el revisor no revisa: responde `VEREDICTO: BLOQUEANTE` con un hallazgo
  que dice que falta el archivo y dónde se espera. Es un aviso, no un fallo del plugin.
- `code-reviewer` y el hook no necesitan nada más.

## Instalación

Dentro de Claude Code, en el repositorio donde quieres usar el plugin:

1. Añade este repositorio como fuente de plugins. Desde GitHub:

   ```text
   /plugin marketplace add danielpvsofka/crediagil
   ```

   O desde una copia local, con la ruta de la carpeta que contiene `.claude-plugin/`:

   ```text
   /plugin marketplace add <ruta a la copia local>
   ```

2. Instala el plugin:

   ```text
   /plugin install crediagil-devkit@crediagil
   ```

3. Comprueba que está activo con `/plugin`: debe aparecer `crediagil-devkit` con sus piezas.

Los mismos pasos desde la terminal: `claude plugin marketplace add <fuente>` y
`claude plugin install crediagil-devkit@crediagil`.

## Uso

Las piezas del plugin siempre llevan el prefijo `crediagil-devkit:`.

- Revisión de código: pídele a Claude que use el subagente `crediagil-devkit:code-reviewer` sobre
  un diff.
- Revisión de cumplimiento: `/crediagil-devkit:compliance-check` o, con una nota para el revisor,
  `/crediagil-devkit:compliance-check issue 42`.
- Datos con forma real: no hay nada que invocar; el hook actúa solo en cada escritura. Si bloquea
  una línea que es un dato de prueba inventado, añade `dato-ficticio` en esa misma línea.

### Si ya tienes piezas con el mismo nombre

No chocan: la pieza del plugin se llama `crediagil-devkit:code-reviewer` y la tuya
`code-reviewer`. Ambas conviven y eliges cuál usar por su nombre.

## Limitaciones

- El revisor de cumplimiento empaquetado es de solo lectura: no ejecuta pytest. Un plugin ignora
  las restricciones de comandos que un subagente declara en su configuración, así que se quitó la
  ejecución de comandos en lugar de dejarla sin restricción. El texto del revisor aún menciona
  pytest; lo omite.
- No incluye bloqueo de archivos de secretos, ni el flujo de tickets ni las specs obligatorias de
  Crediágil: son específicos de ese repositorio.
- La versión no se sube sola: quien cambia una pieza actualiza `version` en `plugin.json` y en el
  catálogo.

## Actualizar

Cuando haya una versión nueva:

```text
/plugin marketplace update crediagil
```

y, si no se actualiza sola, `claude plugin update crediagil-devkit`.

## Para quien mantiene el plugin

Las piezas se mantienen en `.claude/` del repositorio de Crediágil y el plugin lleva copias. Un
test de ese repositorio falla si una copia se aparta de su original, si falta o sobra un archivo,
o si aparece una pieza de `.claude/` sin clasificar. Solo se admiten las diferencias declaradas en
ese test (por ejemplo, el nombre con prefijo del subagente de cumplimiento).
