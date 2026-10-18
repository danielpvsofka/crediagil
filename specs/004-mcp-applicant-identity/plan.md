# Implementation Plan: Servidor MCP: identificación del solicitante

**Branch**: `develop` (feature dir `004-mcp-applicant-identity`) | **Date**: 2026-10-17 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/004-mcp-applicant-identity/spec.md` — Issue [#4](https://github.com/danielpvsofka/crediagil/issues/4)

## Summary

Core de originación simulado como servidor MCP por stdio, en `crediagil.mcp_server`. Usa el SDK
oficial `mcp` 2.x (`MCPServer`) y expone dos herramientas:

- **`buscar_solicitante`**: busca por documento exacto normalizado o por nombre parcial, sin
  distinguir mayúsculas ni tildes. Sin resultados devuelve `coincidencias: []`. Nunca devuelve
  la fecha de nacimiento.
- **`verificar_identidad`**: compara la fecha de nacimiento. Los dos primeros fallos dan
  `negocio` con intentos restantes; el tercero da `permisos` y bloquea, y el bloqueo persiste.

Cada respuesta sigue el contrato `{ok, …}` / `{ok: false, error: {tipo, codigo, mensaje,
reintentable, detalles}}`, que produce una sola envoltura. Esa envoltura convierte cualquier
excepción no prevista en `transitorio`.

El estado vive en un archivo JSON local, protegido con `filelock` y escrito de forma atómica con
temporal + `os.replace`. Si no existe, se crea desde una semilla ficticia (`TEST-NNNNNN`). La
inyección de fallas transitorias se configura por variables de entorno y no toca el estado.
Detalle en [research.md](./research.md).

## Technical Context

**Language/Version**: Python ≥ 3.12 (local 3.14.7)

**Primary Dependencies**: `mcp>=2.3,<3` (SDK oficial; `MCPServer`, cliente stdio para tests) y
`filelock` (lock multiplataforma), las dos nuevas; `pydantic` (ya presente, lo usa `mcp`).

**Storage**: archivo JSON local (`CREDIAGIL_MCP_ESTADO`, por defecto `./.data/core_estado.json`,
ignorado por git), con lock `<archivo>.lock`

**Testing**: pytest + `anyio` (plugin incluido con `mcp`). Unitarios junto al código y uno de
extremo a extremo por stdio con el cliente del SDK.

**Target Platform**: proceso local lanzado por el agente (#7) o por Claude Code; Windows y
POSIX

**Project Type**: servidor MCP (stdio) dentro del paquete `crediagil`

**Performance Goals**: cada llamada < 100 ms con el estado semilla (archivo pequeño, lectura
completa)

**Constraints**:
- La forma de respuesta del contrato, sin excepciones.
- Ninguna fecha de nacimiento en las respuestas.
- Solo datos ficticios.
- Ningún secreto.
- Las reglas de negocio no viven en las herramientas (Principio II).

**Scale/Scope**: 2 herramientas, 6 módulos con sus tests, 4 solicitantes semilla

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Evaluación pre-diseño | Post-diseño |
|-----------|-----------------------|-------------|
| I. Reglas de negocio | ✅ Da la verificación de identidad que necesita la regla 1. No toca tasa ni umbrales. | ✅ Hacer cumplir "verificada antes de registrar" queda en hooks del SDK (#6) |
| II. Garantía en código | ✅ El bloqueo tras 3 intentos es determinista y está en código, no en la descripción de la herramienta. Las descripciones solo guían cuándo usarla y cuándo escalar (`.claude/rules/mcp-server.md`). | ✅ |
| III. Datos ficticios | ✅ Semilla ficticia con documentos `TEST-` y `dato-ficticio`. Estado ignorado por git. Sin credenciales. | ✅ (R6) |
| IV. Spec antes que código | ✅ spec → plan → tasks; `require_specs` lo exige para `src/`. | ✅ |
| V. No inventar datos | ✅ La búsqueda solo devuelve datos del core; sin coincidencias, lista vacía. Nunca se infiere. | ✅ |
| VI. Trazabilidad | ✅ Las respuestas identifican al solicitante (`id_solicitante`, documento) del core. Los tickets de escalamiento quedan para #7. | ✅ |
| VII. Tests junto al código | ✅ Tests por módulo. Bordes de 2 y 3 fallos, bloqueo persistente tras reinicio, cada tipo de error. | ✅ Casos en [contracts/tools.md](./contracts/tools.md) |

**Resultado**: PASA. Sin violaciones.

## Project Structure

### Documentation (this feature)

```text
specs/004-mcp-applicant-identity/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/tools.md     # herramientas, parámetros, respuestas y casos
├── checklists/requirements.md
└── tasks.md               # /speckit-tasks
```

### Source Code (repository root)

```text
pyproject.toml                         # + mcp>=2.3,<3, filelock
.gitignore                             # + .data/
src/crediagil/mcp_server/
├── __init__.py
├── errores.py        / test_errores.py      # TipoError, ErrorCore, exito(), fallo()
├── estado.py         / test_estado.py       # AlmacenEstado: lock, transacción, escritura atómica, semilla
├── semilla.py                               # 4 solicitantes ficticios (dato-ficticio)
├── fallas.py         / test_fallas.py       # InyectorFallas desde variables de entorno
├── identidad.py      / test_identidad.py    # buscar_solicitante, verificar_identidad (lógica pura)
├── server.py         / test_server.py       # MCPServer, envoltura de respuesta, main()
└── test_server_stdio.py                     # extremo a extremo: arranque por stdio + list_tools
```

**Structure Decision**: un subpaquete `crediagil.mcp_server` con la lógica separada del
transporte. `identidad.py` recibe un `AlmacenEstado` y lanza `ErrorCore`; `server.py` solo
adapta a MCP. Así los tests de reglas no necesitan el protocolo. Las herramientas de originación
(#5) se añadirán al mismo servidor.

## Complexity Tracking

Sin violaciones de la constitución que justificar.
