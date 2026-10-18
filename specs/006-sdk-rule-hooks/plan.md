# Implementation Plan: Hooks del Agent SDK para las reglas 1 y 2

**Branch**: `develop` (feature dir `006-sdk-rule-hooks`) | **Date**: 2026-10-17 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/006-sdk-rule-hooks/spec.md` — Issue [#6](https://github.com/danielpvsofka/crediagil/issues/6)

## Summary

Dos hooks `PreToolUse` del Claude Agent SDK que hacen cumplir las reglas 1 y 2 fuera del prompt
y fuera de las herramientas, en el paquete nuevo `crediagil.agent`:

- **Hook de registro**: lee el estado del core y niega `registrar_solicitud` si el solicitante no
  existe, no está verificado o está bloqueado.
- **Hook de preaprobación**: niega `preaprobar_credito` si la solicitud no existe o está
  escalada, si no hay identidad vigente, si tiene hallazgos documentales o si, al recalcular con
  `crediagil.policy`, no cumple las reglas 2 y 3. No usa la evaluación guardada ni nada de lo
  que afirme el modelo.

Comportamiento común:

- **Fail-closed**: estado ilegible, entrada inválida o error inesperado terminan en negación.
- **Solo lectura**: los hooks no modifican el estado.
- **Motivo**: el modelo recibe un motivo con código, mensaje y acción, y cada negación queda en
  un `RegistroNegaciones` que la interfaz puede consultar.

`crear_hooks(...)` devuelve la configuración lista para `ClaudeAgentOptions(hooks=…)`; el agente
que la usa es #7.

Soporte en el core (#4 y #5):

- `AlmacenEstado.leer_existente()`: lectura sin crear el archivo.
- `evaluar_solicitud_guardada()`: evaluación compartida entre la herramienta y el hook.
- Los documentos ficticios de los tests pasan a un módulo propio.

Detalle y API verificada del SDK en [research.md](./research.md).

## Technical Context

**Language/Version**: Python ≥ 3.12

**Primary Dependencies**: `claude-agent-sdk>=0.2.168,<0.3` (nueva; `HookMatcher`,
`ClaudeAgentOptions`); las existentes (`mcp`, `filelock`, `pydantic`)

**Storage**: el archivo de estado del core (v2), solo lectura; el registro de negaciones es en
memoria

**Testing**: pytest + anyio; los tests llaman a los callbacks con la entrada del SDK, sin modelo
ni red ni clave de API

**Target Platform**: se ejecuta dentro del proceso del agente (#7)

**Project Type**: biblioteca (paquete `crediagil.agent`)

**Performance Goals**: decidir en < 100 ms con el estado pequeño; lock de lectura con tiempo
máximo de 5 s y timeout del hook de 10 s

**Constraints**:
- Fail-closed.
- Solo lectura.
- Una única evaluación compartida con la herramienta.
- Parámetros solo de `crediagil.policy`.
- Solo datos ficticios.

**Scale/Scope**: 2 hooks, 1 registro, 1 función de configuración; 3 módulos nuevos con sus tests
y 3 ajustes pequeños al core

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Evaluación pre-diseño | Post-diseño |
|-----------|-----------------------|-------------|
| I. Reglas de negocio | ✅ Aplica las reglas 1 y 2 (y la 3 al recalcular) con los parámetros de `crediagil.policy`; no los redefine. | ✅ Bordes exactos probados desde el hook |
| II. Garantía en código | ✅ Es la implementación literal del principio: hooks del SDK para las reglas 1 y 2, además de la revalidación del core. | ✅ Decide con el estado, nunca con el modelo (R5, R8) |
| III. Datos ficticios | ✅ Tests con documentos ficticios; el motivo nunca incluye la fecha de nacimiento. | ✅ |
| IV. Spec antes que código | ✅ spec → plan → tasks antes de escribir en `src/`. | ✅ |
| V. No inventar datos | ✅ Sin datos para decidir ⇒ negar; no se completa nada. | ✅ |
| VI. Trazabilidad | ✅ Cada negación se registra con herramienta, código, datos y momento. | ✅ [data-model.md](./data-model.md) |
| VII. Tests en los bordes | ✅ Monto en tope ±1, cuota 30% ±1, discrepancia 10% ±1, identidad no verificada, solicitud de humano (fuera de este hook) y fuera de política vía hallazgos. | ✅ Tablas en [contracts/hooks.md](./contracts/hooks.md) |

**Resultado**: PASA. Sin violaciones.

## Project Structure

### Documentation (this feature)

```text
specs/006-sdk-rule-hooks/
├── plan.md, research.md, data-model.md, quickstart.md
├── contracts/hooks.md
├── checklists/requirements.md
└── tasks.md            # /speckit-tasks
```

### Source Code (repository root)

```text
pyproject.toml                               # + claude-agent-sdk>=0.2.168,<0.3
src/crediagil/agent/
├── __init__.py
├── conftest.py                              # anyio_backend
├── negaciones.py     / test_negaciones.py   # Negacion, RegistroNegaciones
└── hooks.py          / test_hooks.py        # decisiones puras, callbacks, crear_hooks
src/crediagil/mcp_server/
├── estado.py         / test_estado.py       # leer_existente (sin crear, con lock y timeout)
├── originacion.py    / test_originacion.py  # evaluar_solicitud_guardada (extraída de preaprobar)
├── documentos_prueba.py                     # helpers ficticios (antes en conftest.py)
├── test_originacion.py, test_server.py      # importan de documentos_prueba
└── conftest.py                              # se elimina
```

**Structure Decision**: la lógica de decisión son funciones puras sobre el diccionario de
estado (`decidir_registro`, `decidir_preaprobacion`); los callbacks solo leen el estado,
llaman a la decisión, anotan la negación y formatean la salida del SDK. Así se prueba cada regla
sin SDK y el SDK solo se importa para construir la configuración.

## Complexity Tracking

Sin violaciones de la constitución que justificar.
