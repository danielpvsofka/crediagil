# Quickstart: validar el plugin `crediagil-devkit`

Guía para comprobar de punta a punta que la feature funciona. Estructura y reglas en
[contracts/plugin.md](./contracts/plugin.md); tablas en [data-model.md](./data-model.md).

## Prerrequisitos

- `uv sync --group dev` en este repositorio.
- Claude Code instalado y, para el recorrido de instalación, un directorio vacío fuera de este
  repositorio (el "repositorio consumidor").

## 1. Integridad del plugin (sin red, sin clave)

```bash
uv run pytest .claude/hooks/test_plugin_devkit.py
```

Esperado: todo en verde en pocos segundos (SC-005).

## 2. La divergencia se detecta (SC-002)

1. Cambiar una línea de `.claude/agents/code-reviewer.md`.
2. Repetir el comando del paso 1: debe fallar nombrando `code-reviewer` y el archivo.
3. Revertir el cambio: vuelve a pasar.
4. Cambiar solo el fin de línea de un original: no debe fallar.

## 3. Lo específico queda fuera (SC-003)

```bash
git ls-files plugins/crediagil-devkit
```

Esperado: ni `require_specs`, ni `open-pr`, ni `ticket`, ni `format_python`, ni `speckit-*`.

## 4. Instalación en un repositorio ajeno (SC-001)

En el repositorio consumidor, dentro de Claude Code, seguir solo el README del plugin:

```text
/plugin marketplace add <ruta local o owner/repo de este repositorio>
/plugin install crediagil-devkit@crediagil
```

Esperado:
- el plugin aparece en `/plugin` con su descripción;
- están `crediagil-devkit:code-reviewer` y `/crediagil-devkit:compliance-check`;
- pedir a Claude que escriba un archivo con una tarjeta válida o una cédula con su etiqueta (números
  inventados en el momento) lo bloquea con el mismo mensaje que en este repositorio; la misma
  línea con `dato-ficticio` pasa.

## 5. Constitución ausente (FR-010)

En el repositorio consumidor sin `.specify/memory/constitution.md`, con un cambio en `src/`:
ejecutar `/crediagil-devkit:compliance-check`. Esperado: `VEREDICTO: BLOQUEANTE` indicando que
falta la constitución y dónde se espera.

## 6. Este repositorio sigue igual (FR-012)

```bash
uv run pytest
uv run ruff check
```

Esperado: la suite completa en verde; `code-reviewer` y `compliance-check` funcionan como antes
desde `.claude/`.

## Resultado de las validaciones

Medido el 2026-10-18:

- **§1 Integridad del plugin**: `uv run pytest .claude/hooks/test_plugin_devkit.py` → 76 pasan en
  unos 4 s (SC-005 exige menos de 10 s).
- **§2 La divergencia se detecta**: añadida una línea a `.claude/agents/code-reviewer.md`, la suite
  falló con `diverge: agents/code-reviewer.md (plugins/crediagil-devkit/agents/code-reviewer.md)`;
  revertida, volvió a pasar. El cambio de solo fin de línea no falla (control negativo en el test).
- **§3 Lo específico queda fuera**: el plugin contiene solo `code-reviewer`, `compliance-reviewer`,
  `compliance-check`, `block_sensitive_data`, `_hooklib`, `hooks.json`, los dos manifiestos y el
  README; ni `require_specs`, ni `open-pr`, ni `ticket`, ni `format_python`, ni `speckit-*`.
- **§6 Este repositorio sigue igual**: `uv run pytest` → 1178 pasan, 10 `live` excluidos, en unos
  32 s (antes 1101: el aumento son los 77 tests de esta feature); `uv run ruff check` y
  `uv run ruff format --check` limpios.
- **Validación de formato con la propia CLI** (`claude plugin validate … --strict`, Claude Code
  2.1.292): catálogo, plugin, `agents/` y `skills/` pasan sin avisos. No estaba prevista en la
  spec; es la comprobación más cercana a una instalación real sin tocar la configuración del
  usuario.

**Pendiente**: §4 (instalación en un repositorio ajeno) y §5 (constitución ausente), que requieren
una sesión de Claude Code en otro directorio; es la tarea T023.
