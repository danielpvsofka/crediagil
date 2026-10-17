# Feature Specification: Automatización del flujo de tickets en GitHub

**Feature Branch**: `develop` (sin hook de rama; directorio de spec: `specs/002-github-ticket-flow`)

**Created**: 2026-10-15

**Status**: Draft

**Issue**: [#2](https://github.com/danielpvsofka/crediagil/issues/2) · **Depende de**: #1

**Input**: User description: "Automatización del flujo de tickets en GitHub — El estado de los tickets debe reflejar el avance real sin intervención manual, y cada PR debe pasar por una revisión independiente de la sesión que generó el código. Alcance: skill `/ticket` que toma el siguiente ítem del Project y arranca el ciclo Spec Kit; comando `/open-pr` compartido por control de versiones; subagentes `code-reviewer` y `compliance-reviewer` con herramientas restringidas a su rol; skill `compliance-check` con `context: fork`, `allowed-tools` y `argument-hint`; workflow integrado del Project para pasar a Done. Issue: #2"

> **Nota de alcance**: igual que en #1, el entregable es el entorno de desarrollo. Los nombres
> de comandos, subagentes, skills y estados del Project son contrato exigido por el issue; el
> cómo queda para `/speckit-plan`.

## User Scenarios & Testing *(mandatory)*

Actores: **desarrollador** (trabaja tickets con Claude Code) y **revisor humano** (aprueba y
hace merge del PR).

### User Story 1 - Tomar un ticket y arrancar su spec (Priority: P1)

El desarrollador ejecuta `/ticket` (o `/ticket <n>`). El sistema elige el issue, lo mueve a
**In progress** en el Project, genera su spec con Spec Kit a partir del título y cuerpo del
issue, y comenta en el issue dónde quedó la spec y qué se especificó.

**Why this priority**: es la entrada del ciclo; sin ella el estado del Project depende de
pasos manuales (Principio VI).

**Independent Test**: con un issue de prueba en **Todo**, ejecutar `/ticket siguiente`: el
ítem queda en **In progress**, existe `specs/NNN-*/spec.md` con "Issue: #n" y el issue tiene
un comentario con la ruta y el resumen.

**Acceptance Scenarios**:

1. **Given** varios ítems en **Todo**, **When** se ejecuta `/ticket` o `/ticket siguiente`, **Then** se toma el primero en el orden del Project, pasa a **In progress** y se genera su spec con el título y cuerpo completos más `Issue: #<n>`.
2. **Given** el issue #n está en el Project, **When** se ejecuta `/ticket <n>`, **Then** se toma ese issue aunque no sea el primero.
3. **Given** la spec se generó, **When** termina `/ticket`, **Then** el issue tiene un comentario con la ruta de la spec y un resumen de lo especificado.
4. **Given** no hay ítems en **Todo**, **When** se ejecuta `/ticket`, **Then** informa que no hay trabajo pendiente y no cambia nada.

---

### User Story 2 - Abrir el PR solo si pasa la revisión independiente (Priority: P1)

Al terminar, el desarrollador ejecuta `/open-pr <n>`. El sistema corre los tests, pide una
revisión de código a un subagente que no participó en escribir el código y, si se tocó lógica
de negocio, una revisión de cumplimiento de la constitución. Si hay bloqueantes, no abre el
PR y los reporta. Si no, abre el PR con `Closes #<n>`, mueve el ítem a **In review** y comenta
en el issue lo especificado, lo decidido y lo pendiente.

**Why this priority**: garantiza la revisión independiente que pide el issue y mantiene el
estado al día.

**Independent Test**: en una rama con un cambio que rompe un test, `/open-pr <n>` no abre PR
y reporta el fallo; corregido el test y sin hallazgos bloqueantes, abre el PR con
`Closes #<n>` y el ítem pasa a **In review**.

**Acceptance Scenarios**:

1. **Given** algún test falla, **When** se ejecuta `/open-pr <n>`, **Then** no se abre el PR ni se invocan las revisiones, y se muestra el fallo.
2. **Given** tests en verde, **When** `code-reviewer` reporta un hallazgo bloqueante, **Then** no se abre el PR y se listan los hallazgos.
3. **Given** el cambio toca lógica de negocio, **When** se ejecuta `/open-pr <n>`, **Then** también se ejecuta `compliance-check`, y un hallazgo bloqueante impide abrir el PR.
4. **Given** el cambio no toca lógica de negocio, **When** se ejecuta `/open-pr <n>`, **Then** `compliance-check` no se ejecuta.
5. **Given** sin bloqueantes, **When** termina `/open-pr <n>`, **Then** existe un PR cuya descripción incluye `Closes #<n>`, el ítem está en **In review** y el issue tiene un comentario con lo especificado, lo decidido y lo pendiente.

---

### User Story 3 - Done automático al hacer merge (Priority: P2)

Cuando un humano hace merge del PR, el ítem pasa a **Done** sin que nadie lo mueva.

**Why this priority**: cierra el ciclo; lo resuelve una configuración del Project, sin código.

**Independent Test**: hacer merge de un PR con `Closes #<n>`: el issue se cierra y el ítem
aparece en **Done**.

**Acceptance Scenarios**:

1. **Given** un PR con `Closes #<n>`, **When** se hace merge, **Then** el issue se cierra y su ítem pasa a **Done**.

---

### User Story 4 - Revisores con permisos mínimos (Priority: P2)

Los subagentes revisores solo pueden hacer lo que su rol requiere: `code-reviewer` solo lee
(Read, Grep, Glob); `compliance-reviewer` lee y puede ejecutar pytest, nada más.

**Why this priority**: una revisión independiente no debe poder modificar lo que revisa.

**Independent Test**: inspeccionar la definición de cada subagente y pedirle que edite un
archivo o ejecute otro comando: no puede.

**Acceptance Scenarios**:

1. **Given** `code-reviewer`, **When** intenta editar, escribir o ejecutar comandos, **Then** no tiene esas herramientas.
2. **Given** `compliance-reviewer`, **When** intenta ejecutar un comando distinto de pytest o editar archivos, **Then** se le niega.

### Edge Cases

- `/ticket <n>` con un issue cerrado, inexistente o fuera del Project: informa el motivo y no cambia nada.
- `/ticket <n>` con un issue que ya está en **In progress**: no lo mueve de nuevo y avisa (si ya existe su spec, la indica en vez de crear otra).
- Falla la generación de la spec después de mover el ítem: el ítem queda en **In progress** y se informa el error; no se comenta el issue.
- `/open-pr <n>` sin cambios respecto a la rama base, o en la rama principal: no abre PR y lo explica.
- Ya existe un PR abierto para la rama: no se crea otro; se informa su enlace.
- Sin `GITHUB_PAT` o sin permisos sobre el Project: los comandos fallan antes de cambiar estados y explican qué falta.
- Las revisiones no devuelven un resultado interpretable: se trata como bloqueante.

## Requirements *(mandatory)*

### Functional Requirements

**`/ticket`**

- **FR-001**: `/ticket` MUST aceptar un número de issue o `siguiente` (por defecto `siguiente`).
- **FR-002**: Con `siguiente`, MUST tomar el primer ítem en estado **Todo** según el orden del Project.
- **FR-003**: MUST mover el ítem a **In progress** antes de generar la spec.
- **FR-004**: MUST ejecutar el flujo `/speckit-specify` con el título y el cuerpo completos del issue, terminando con `Issue: #<n>`.
- **FR-005**: Al terminar, MUST comentar en el issue la ruta de la spec y un resumen de lo especificado (historias y requisitos principales).

**`/open-pr`**

- **FR-006**: `/open-pr <n>` MUST estar versionado en el repositorio para que lo use todo el equipo.
- **FR-007**: MUST ejecutar la suite de tests y detenerse sin abrir PR si alguno falla.
- **FR-008**: MUST invocar el subagente `code-reviewer` sobre el diff de la rama frente a la base.
- **FR-009**: Si el diff toca lógica de negocio, MUST invocar `compliance-check`. Lógica de negocio: código bajo `src/` relacionado con reglas del Principio I de la constitución (ver Assumptions).
- **FR-010**: Si alguna revisión reporta un hallazgo bloqueante, MUST NOT abrir el PR y MUST listar los hallazgos.
- **FR-011**: Sin bloqueantes, MUST abrir un PR cuya descripción incluya `Closes #<n>` y mover el ítem a **In review**.
- **FR-012**: MUST comentar en el issue lo especificado, lo decidido y lo pendiente (a partir de spec, plan y tareas sin completar de la feature).

**Revisores**

- **FR-013**: El subagente `code-reviewer` MUST tener únicamente las herramientas Read, Grep y Glob.
- **FR-014**: El subagente `compliance-reviewer` MUST tener únicamente herramientas de lectura y la ejecución de pytest.
- **FR-015**: La skill `compliance-check` MUST ejecutarse en un contexto separado (`context: fork`) usando `compliance-reviewer`, declarar `allowed-tools` y `argument-hint`, y verificar el diff contra los siete principios de la constitución.
- **FR-016**: Cada revisión MUST devolver un veredicto explícito (bloqueante / no bloqueante) con sus hallazgos.

**Project**

- **FR-017**: El workflow integrado del Project MUST mover a **Done** los ítems cuyo issue se cierra por merge de un PR.

### Key Entities

- **Ítem del Project**: issue enlazado al Project con un estado (**Todo**, **In progress**, **In review**, **Done**).
- **Feature de Spec Kit**: directorio `specs/NNN-*` generado por `/ticket`, enlazado al issue con `Issue: #<n>`.
- **Revisión**: resultado de un revisor: veredicto y lista de hallazgos (archivo, motivo, severidad).
- **Comentario de seguimiento**: comentario en el issue que publica `/ticket` (spec) o `/open-pr` (especificado / decidido / pendiente).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 0 cambios manuales de estado en el Project para un ticket que recorre Todo → Done.
- **SC-002**: El 100% de los PR abiertos con `/open-pr` tienen tests en verde y revisión de código sin bloqueantes en el momento de abrirse.
- **SC-003**: El 100% de los PR que tocan lógica de negocio tienen revisión de cumplimiento sin bloqueantes.
- **SC-004**: Cada issue trabajado tiene al menos dos comentarios de seguimiento (spec y PR) generados automáticamente.
- **SC-005**: Ningún revisor puede modificar archivos (verificado en su definición).

## Assumptions

- El Project de GitHub ya existe, está enlazado al repositorio y tiene el campo de estado con **Todo**, **In progress**, **In review** y **Done**. Activar el workflow integrado "Item closed → Done" es un paso de configuración manual, documentado.
- El acceso a GitHub se hace con el servidor MCP de #1 (toolset `projects`) y `GITHUB_PAT` de cada desarrollador.
- "Lógica de negocio" = cambios bajo `src/` (el agente). Cambios solo en specs, docs, `.claude/` o tests de hooks no la activan. Es una aproximación simple para el primer alcance.
- `/ticket` no crea ramas: se trabaja en la rama actual, igual que en #1.
- `/open-pr` no hace commit ni push sin confirmación del usuario (convención del equipo); si hay cambios sin publicar, los muestra y pide confirmación.
- Los hooks de #1 siguen activos durante todo el flujo.
- Fuera de alcance: CI en GitHub Actions, revisiones automáticas en el propio PR y asignación de revisores humanos.
