# Feature Specification: Ecosistema base de Claude Code

**Feature Branch**: `develop` (no se creó rama de feature; directorio de spec: `specs/001-claude-code-ecosystem`)

**Created**: 2026-10-14

**Status**: Draft

**Issue**: [#1](https://github.com/danielpvsofka/crediagil/issues/1)

**Input**: User description: "Ecosistema base de Claude Code — Todo desarrollador que clone el repositorio debe recibir las convenciones del equipo sin configurar nada, y las reglas deterministas (datos ficticios, secretos, formato, specs obligatorias) deben hacerse cumplir con hooks, no con instrucciones. Alcance: `CLAUDE.md` raíz con `@import` de la constitución; separación de lo personal (`CLAUDE.local.md`, `.claude/settings.local.json` en `.gitignore`); reglas en `.claude/rules/` con `paths`; `.claude/settings.json` con `permissions.deny` y registro de hooks; hooks de specs obligatorias, datos con forma real, protección de secretos por Bash y formato post-edición; `.mcp.json` con el servidor de GitHub (toolset `projects`) sin credenciales. Fuera de alcance: automatización del flujo de tickets (issue #2). Issue: #1"

> **Nota de alcance**: el "producto" de esta feature es el propio entorno de desarrollo del
> repositorio. Por eso los requisitos nombran artefactos concretos (`CLAUDE.md`,
> `.claude/settings.json`, hooks `PreToolUse`/`PostToolUse`, `.mcp.json`): son el entregable
> exigido por el issue y por el Principio II de la constitución, no decisiones de diseño
> internas. El cómo (lenguaje de los hooks, estructura del código) queda para `/speckit-plan`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Convenciones del equipo al clonar (Priority: P1)

Un desarrollador clona el repositorio y abre una sesión de Claude Code. Sin configurar nada,
la sesión ya conoce las convenciones del equipo y la constitución del proyecto. Sus
preferencias personales (instrucciones locales, permisos locales) viven en archivos que nunca
se versionan.

**Why this priority**: es la base de todo lo demás: sin convenciones compartidas cargadas
automáticamente, cada desarrollador trabaja con reglas distintas y la constitución no se aplica.

**Independent Test**: clonar el repositorio en un directorio limpio, abrir Claude Code y
preguntar por las reglas de negocio no negociables y la tasa fija; la respuesta debe reflejar
la constitución. Crear `CLAUDE.local.md` y `.claude/settings.local.json` y verificar que git
los ignora.

**Acceptance Scenarios**:

1. **Given** un clon limpio del repositorio, **When** un desarrollador inicia Claude Code en la
   raíz, **Then** el contexto cargado incluye las convenciones del equipo y el contenido de la
   constitución (`.specify/memory/constitution.md`) sin pasos manuales.
2. **Given** un desarrollador crea `CLAUDE.local.md` o `.claude/settings.local.json`, **When**
   ejecuta `git status`, **Then** esos archivos no aparecen como pendientes de versionar.
3. **Given** un desarrollador trabaja sobre archivos de tests o del servidor MCP, **When**
   Claude Code lee o edita esos archivos, **Then** se cargan las reglas específicas de esa
   ruta y no se cargan para rutas no relacionadas.

---

### User Story 2 - Spec antes que código, garantizado (Priority: P1)

Un desarrollador (o Claude) intenta modificar código de producción en `src/` para la feature
activa. Si esa feature todavía no tiene spec, plan y tareas, la edición se bloquea con un
mensaje que explica qué falta.

**Why this priority**: hace cumplir con código el Principio IV de la constitución; sin esto,
el flujo spec-first depende de la disciplina individual.

**Independent Test**: con una feature activa que solo tiene `spec.md`, intentar editar un
archivo en `src/`: la edición se bloquea indicando que faltan `plan.md` y `tasks.md`. Al
completar los tres archivos, la misma edición se permite.

**Acceptance Scenarios**:

1. **Given** la feature activa tiene `spec.md`, `plan.md` y `tasks.md`, **When** se edita o
   crea un archivo bajo `src/`, **Then** la operación se permite.
2. **Given** a la feature activa le falta al menos uno de los tres documentos, **When** se
   intenta editar o crear un archivo bajo `src/`, **Then** la operación se bloquea y el mensaje
   lista los documentos faltantes y la feature evaluada.
3. **Given** no hay feature activa determinable, **When** se intenta editar `src/`, **Then** la
   operación se bloquea con un mensaje que indica cómo declarar la feature activa.
4. **Given** cualquier estado de specs, **When** se edita un archivo fuera de `src/` (p. ej.
   documentación o specs), **Then** este control no interviene.

---

### User Story 3 - Ningún dato con forma real entra al repositorio (Priority: P1)

Al escribir o editar cualquier archivo, si el contenido incluye algo con forma de número de
tarjeta real (válido por Luhn), documento de identidad o cuenta bancaria, la operación se
bloquea antes de llegar al disco.

**Why this priority**: hace cumplir el Principio III (datos exclusivamente ficticios); un dato
real filtrado en el repo o en fixtures es un incidente de privacidad.

**Independent Test**: intentar escribir un archivo con un número de 16 dígitos válido por
Luhn: se bloquea. El mismo número con el dígito de control alterado (inválido por Luhn) se
permite.

**Acceptance Scenarios**:

1. **Given** un contenido con una secuencia de 13–19 dígitos (con o sin espacios/guiones) que
   pasa la verificación de Luhn, **When** se intenta escribir o editar un archivo, **Then** la
   operación se bloquea indicando el tipo de dato detectado (sin repetir el valor completo).
2. **Given** un contenido con un número de documento de identidad o de cuenta bancaria
   identificado como tal por su contexto (etiqueta como "cédula", "CC", "NIT", "cuenta",
   "ahorros", "corriente"), **When** se intenta escribir o editar un archivo, **Then** la
   operación se bloquea.
3. **Given** un contenido con números que no tienen esas formas (montos, fechas, cuotas,
   identificadores internos ficticios marcados como tales), **When** se escribe el archivo,
   **Then** la operación se permite.

---

### User Story 4 - Secretos inaccesibles (Priority: P2)

Ni las herramientas de lectura/edición ni la terminal pueden leer o modificar archivos de
secretos (`.env*`, `secrets/`). El servidor MCP de GitHub se configura sin token en el
repositorio, tomando la credencial de una variable de entorno.

**Why this priority**: evita que credenciales reales terminen en el contexto del modelo, en
logs o en commits; el repositorio ya contiene un `.env` local.

**Independent Test**: pedir a Claude que lea `.env` con la herramienta de lectura y con
`cat .env` por terminal; ambas se bloquean. Buscar en el repo cualquier token: no hay.

**Acceptance Scenarios**:

1. **Given** existe `.env`, `.env.local` o un archivo bajo `secrets/`, **When** se intenta
   leerlo o editarlo con las herramientas de archivo, **Then** la configuración de permisos lo
   deniega.
2. **Given** los mismos archivos, **When** se intenta acceder a ellos desde la terminal
   (`cat`, `type`, `Get-Content`, `less`, `head`, `tail`, `grep`, copia o redirección),
   **Then** el control sobre comandos de terminal lo bloquea.
3. **Given** `.mcp.json` versionado, **When** se inspecciona, **Then** la credencial se
   referencia como `${GITHUB_PAT}` y el toolset `projects` está habilitado; no hay token literal
   en ningún archivo versionado.

---

### User Story 5 - Formato automático tras editar Python (Priority: P3)

Cada vez que se crea o edita un archivo `.py`, se formatea automáticamente con el formateador
del equipo, sin que el desarrollador lo pida.

**Why this priority**: elimina diffs de estilo y discusiones de formato; no protege reglas de
negocio, por eso va después.

**Independent Test**: escribir un `.py` mal formateado; tras la escritura el archivo queda
formateado. Editar un `.md`: no se toca.

**Acceptance Scenarios**:

1. **Given** se crea o edita un archivo `.py`, **When** la operación termina, **Then** el
   archivo queda formateado con ruff.
2. **Given** se edita un archivo que no es `.py`, **When** la operación termina, **Then** el
   formateador no se ejecuta.
3. **Given** el formateador no está instalado o falla, **When** termina la edición, **Then** se
   informa el problema sin revertir la edición ni bloquear la sesión.

---

### User Story 6 - Hooks verificables (Priority: P2)

Cada hook tiene tests ubicados junto a él que lo ejecutan como subproceso, enviándole por
stdin el JSON del evento tal como lo haría Claude Code, y verifican el código de salida y el
mensaje.

**Why this priority**: un control que no está probado no es una garantía (Principios II y VII).

**Independent Test**: ejecutar la suite de tests de hooks; cada hook tiene casos de permitir y
bloquear, y todos pasan.

**Acceptance Scenarios**:

1. **Given** la suite de tests de hooks, **When** se ejecuta, **Then** cada hook se invoca como
   subproceso con un JSON de evento por stdin y se verifica su código de salida (0 permite, 2
   bloquea) y su mensaje.
2. **Given** el hook de datos con forma real, **When** se ejecutan sus tests, **Then** cubren
   los bordes: número válido por Luhn vs. el mismo con dígito de control alterado; longitudes
   12, 13, 19 y 20 dígitos.

---

### Edge Cases

- **Tests del propio hook de datos sensibles**: sus fixtures necesitan números válidos por
  Luhn, pero escribirlos literalmente sería bloqueado. Los tests MUST poder existir sin
  desactivar el hook (p. ej. generando el número en tiempo de ejecución).
- **Formato con separadores**: números de tarjeta escritos con espacios o guiones
  (`XXXX XXXX XXXX XXXX`, `XXXX-XXXX-...`) MUST detectarse igual que sin separadores.
- **Falsos positivos**: montos en COP (p. ej. `5000000`), timestamps, UUIDs y hashes no deben
  bloquearse por sí solos.
- **Rutas equivalentes**: `src/` referenciado por ruta absoluta, relativa o con separadores de
  Windows (`src\\...`) MUST evaluarse igual en el control de specs.
- **Evasión por terminal**: variantes como `cat ./.env`, `cat .env.local`, `cat secrets/x`,
  `Get-Content .env`, `type .env`, o `.env` dentro de una tubería MUST bloquearse, tanto en
  Bash como en PowerShell.
- **JSON de evento malformado o incompleto**: los hooks de bloqueo MUST fallar de forma
  segura (bloquear con mensaje explicativo) en lugar de permitir silenciosamente.
- **Feature activa con documentos vacíos**: un `plan.md` vacío no cuenta como presente.

## Requirements *(mandatory)*

### Functional Requirements

**Convenciones compartidas**

- **FR-001**: El repositorio MUST incluir un `CLAUDE.md` raíz versionado con las convenciones
  del equipo que importe `.specify/memory/constitution.md` mediante `@import`.
- **FR-002**: `.gitignore` MUST excluir `CLAUDE.local.md` y `.claude/settings.local.json`.
- **FR-003**: El repositorio MUST incluir al menos dos reglas en `.claude/rules/` con alcance
  por ruta (`paths` con patrones glob): una para archivos de tests y otra para el servidor MCP.
- **FR-004**: `.claude/settings.json` versionado MUST registrar todos los hooks de esta feature
  y declarar `permissions.deny`.

**Spec antes que código**

- **FR-005**: Un hook `PreToolUse` sobre operaciones de escritura/edición MUST bloquear (código
  de salida 2) cualquier cambio a archivos bajo `src/` si la feature activa no tiene
  `spec.md`, `plan.md` y `tasks.md` no vacíos.
- **FR-006**: La feature activa MUST determinarse a partir de `.specify/feature.json`
  (`feature_directory`); si no existe o no es válida, el cambio a `src/` se bloquea.
- **FR-007**: El mensaje de bloqueo MUST indicar la feature evaluada y los documentos faltantes.

**Datos con forma real**

- **FR-008**: Un hook `PreToolUse` sobre operaciones de escritura/edición MUST bloquear
  contenido que contenga una secuencia de 13–19 dígitos (admitiendo espacios o guiones como
  separadores) válida por el algoritmo de Luhn, que empiece por 2–6 (rangos IIN de las marcas
  comunes; excluye timestamps en milisegundos) y que sea un token propio (no incrustado en un
  hash hex ni en un identificador alfanumérico).
- **FR-009**: El mismo hook MUST bloquear números de documento de identidad (6–10 dígitos) y de
  cuenta bancaria (9–20 dígitos) cuando aparezcan junto a una etiqueta que los identifique
  (p. ej. "cédula", "CC", "C.C.", "NIT", "documento", "cuenta", "ahorros", "corriente").
- **FR-010**: El mensaje de bloqueo MUST indicar el tipo de dato y la ubicación aproximada sin
  reproducir el valor completo.
- **FR-010a**: Una línea que contenga el marcador explícito `dato-ficticio` MUST quedar
  exenta de las verificaciones de FR-008 y FR-009, para permitir fixtures ficticios
  deliberados (Principio III). El uso del marcador queda visible en revisión de código.

**Secretos**

- **FR-011**: `permissions.deny` MUST denegar lectura y edición de `.env`, `.env.*` y de todo
  archivo bajo `secrets/`.
- **FR-012**: Un hook `PreToolUse` sobre comandos de terminal MUST bloquear comandos que lean,
  copien, muestren o redirijan archivos `.env*` (incluido `.env.example`, por coherencia con
  `permissions.deny`, que no admite excepciones) o bajo `secrets/`.
- **FR-013**: `.mcp.json` MUST configurar el servidor de GitHub con el toolset `projects`
  habilitado y la credencial como `${GITHUB_PAT}`; ningún archivo versionado MUST contener un
  token literal.

**Formato**

- **FR-014**: Un hook `PostToolUse` MUST formatear con ruff cada archivo `.py` creado o editado,
  y no actuar sobre otros tipos de archivo.
- **FR-015**: Si el formateo falla, el hook MUST informar el error sin bloquear ni revertir la
  edición.

**Calidad**

- **FR-016**: Cada hook MUST tener tests ubicados junto a él que lo ejecuten como subproceso con
  el JSON del evento por stdin y verifiquen código de salida y mensaje.
- **FR-017**: Los hooks de bloqueo MUST fallar de forma segura ante entrada malformada.
- **FR-018**: Todos los datos de ejemplo y fixtures de esta feature MUST ser ficticios
  (Principio III).

### Key Entities

- **Convención de equipo**: instrucción compartida y versionada que se carga en cada sesión.
- **Regla con alcance por ruta**: instrucción que se carga solo cuando se trabaja con archivos
  que coinciden con sus patrones.
- **Feature activa**: directorio de spec declarado en `.specify/feature.json`, con sus
  documentos `spec.md`, `plan.md` y `tasks.md`.
- **Hook**: control determinista que recibe un evento (JSON por stdin) y decide permitir
  (salida 0) o bloquear (salida 2), o actúa después de la operación (formato).
- **Archivo protegido**: archivo de secretos (`.env*`, `secrets/`) inaccesible para el modelo.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Un desarrollador nuevo tiene las convenciones del equipo y la constitución
  cargadas en su primera sesión con 0 pasos de configuración manual tras clonar.
- **SC-002**: El 100% de los intentos de modificar `src/` sin spec, plan y tareas completos en
  la feature activa se bloquean.
- **SC-003**: El 100% de los casos de prueba con números válidos por Luhn y con documentos o
  cuentas etiquetados se bloquean, y el 0% de los casos de números legítimos de referencia
  (montos, fechas, identificadores ficticios) se bloquea.
- **SC-004**: El 100% de las variantes de acceso a secretos del catálogo de casos de prueba
  (herramientas de archivo y terminal) se bloquean.
- **SC-005**: 0 tokens o credenciales literales en archivos versionados.
- **SC-006**: El 100% de los archivos `.py` editados en sesión quedan con formato conforme sin
  intervención manual.
- **SC-007**: Cada hook tiene al menos un caso de "permitir" y uno de "bloquear" (o "formatear"
  / "no formatear") cubiertos por tests que pasan.

## Assumptions

- La feature activa se toma de `.specify/feature.json`, que Spec Kit ya mantiene; no se
  infiere desde el nombre de la rama.
- "Documento de identidad" y "cuenta bancaria" se detectan por contexto (etiqueta cercana)
  para evitar falsos positivos con montos y otros números; los rangos de longitud siguen los
  formatos colombianos habituales (cédula de 6–10 dígitos; cuentas de 9–20 dígitos).
- `.env.example`, si se crea, lo mantiene un humano: queda bloqueado para el modelo igual que
  el resto de `.env*`, porque `permissions.deny` no admite excepciones por patrón.
- Los fixtures ficticios con forma de cédula o cuenta se marcan con `dato-ficticio`
  (FR-010a); el hook no puede distinguir por sí solo un número ficticio de uno real.
- Los desarrolladores tienen ruff disponible en su entorno (se documentará en `CLAUDE.md`); su
  ausencia no bloquea la edición (FR-015).
- Cada desarrollador define `GITHUB_PAT` en su entorno local; el repositorio no lo provee.
- Los hooks deben funcionar en Windows (entorno actual del equipo) y en sistemas POSIX.
- La automatización del flujo de tickets hacia GitHub queda fuera de alcance (issue #2).
