# Feature Specification: Servidor MCP: identificación del solicitante

**Feature Branch**: `develop` (sin hook de rama; directorio de spec: `specs/004-mcp-applicant-identity`)

**Created**: 2026-10-17

**Status**: Draft

**Issue**: [#4](https://github.com/danielpvsofka/crediagil/issues/4) · **Depende de**: #3 · **Habilita**: #5, #6

**Input**: User description: "Servidor MCP: identificación del solicitante — El agente necesita identificar y verificar al solicitante a través del core de originación, simulado con un servidor MCP propio y datos ficticios. Alcance: servidor MCP por stdio con estado local persistido (archivo JSON con lock); contrato de errores estructurados; herramientas `buscar_solicitante` y `verificar_identidad`; datos semilla ficticios. Criterios: toda respuesta es {ok: true, ...} u {ok: false, error: {tipo, codigo, mensaje, reintentable, detalles}}; tipos de error transitorio, validacion, negocio, permisos, cada uno indica si es reintentable; `buscar_solicitante` busca por documento o nombre parcial y puede devolver varias coincidencias; una búsqueda sin resultados devuelve coincidencias: [], no un error; `verificar_identidad` valida con la fecha de nacimiento y bloquea tras 3 intentos fallidos (error de permisos); inyección de fallas transitorias configurable para pruebas; datos semilla 100% ficticios (documentos TEST-xxxxxx); el servidor arranca con `python -m crediagil.mcp_server.server` y lista sus herramientas por protocolo MCP. Depende de #3. Issue: #4"

> **Nota de alcance**: los nombres de herramientas, la forma de las respuestas, los tipos de error
> y el comando de arranque son contrato exigido por el issue (los consumirá el agente en #5–#7).
> El cómo queda para `/speckit-plan`. Los documentos semilla se escriben aquí como el patrón
> `TEST-NNNNNN` (N = dígito); los valores concretos viven en los datos semilla.

## User Scenarios & Testing *(mandatory)*

Actores: **agente de originación**, que llama a las herramientas en nombre de un solicitante;
**equipo de desarrollo**, que prueba el agente contra el core simulado.

### User Story 1 - Buscar al solicitante (Priority: P1)

El agente busca a un solicitante por su número de documento o por parte de su nombre y recibe
las coincidencias, que pueden ser varias o ninguna.

**Why this priority**: sin identificar al solicitante no se puede verificar ni registrar nada
(regla 1).

**Independent Test**: con los datos semilla, buscar por un documento existente, por un nombre
parcial compartido y por algo inexistente.

**Acceptance Scenarios**:

1. **Given** un solicitante semilla, **When** se busca por su documento `TEST-NNNNNN`, **Then** la respuesta es `ok: true` con exactamente esa coincidencia.
2. **Given** dos solicitantes cuyo nombre contiene "Prueba", **When** se busca por "prueba", **Then** la respuesta trae ambas coincidencias (sin distinguir mayúsculas ni tildes).
3. **Given** que nadie coincide, **When** se busca, **Then** la respuesta es `ok: true` con `coincidencias: []`, no un error.
4. **Given** una búsqueda sin documento ni nombre, o con ambos, o con un nombre de menos de 3 caracteres, **When** se llama a la herramienta, **Then** la respuesta es un error de tipo `validacion`, no reintentable.

---

### User Story 2 - Verificar la identidad con bloqueo por intentos (Priority: P1)

El agente verifica la identidad de un solicitante encontrado comparando la fecha de nacimiento
que da el solicitante. Tras 3 intentos fallidos, el solicitante queda bloqueado.

**Why this priority**: es la condición previa de la regla 1 de la constitución (ninguna
solicitud sin identidad verificada).

**Independent Test**: verificar con la fecha correcta, con fechas incorrectas hasta el bloqueo y
después del bloqueo, reiniciando el servidor entre medio.

**Acceptance Scenarios**:

1. **Given** un solicitante no bloqueado, **When** se verifica con su fecha de nacimiento, **Then** la respuesta es `ok: true` con `verificado: true` y el contador de intentos fallidos vuelve a 0.
2. **Given** 0 intentos fallidos, **When** se verifica con una fecha incorrecta, **Then** la respuesta es un error `negocio` (no reintentable) que indica 2 intentos restantes.
3. **Given** 2 intentos fallidos, **When** se falla el tercero, **Then** la respuesta es un error `permisos` y el solicitante queda bloqueado.
4. **Given** un solicitante bloqueado, **When** se verifica, incluso con la fecha correcta, **Then** la respuesta es un error `permisos`.
5. **Given** 2 intentos fallidos y un reinicio del servidor, **When** se falla otra vez, **Then** queda bloqueado (el contador persiste).
6. **Given** un solicitante inexistente, **When** se verifica, **Then** la respuesta es un error `negocio` de solicitante no encontrado.
7. **Given** una fecha con formato inválido o futura, **When** se verifica, **Then** la respuesta es un error `validacion` y **no** cuenta como intento fallido.

---

### User Story 3 - Contrato de errores e inyección de fallas (Priority: P1)

Toda respuesta del servidor sigue una forma única y, en pruebas, se pueden provocar fallas
transitorias para comprobar que el agente reintenta o escala correctamente.

**Why this priority**: el agente decide reintentar o escalar a partir de `tipo` y
`reintentable`; sin un contrato estable no puede hacerlo.

**Independent Test**: activar la inyección de fallas y llamar a cada herramienta; desactivarla y
comprobar respuestas normales.

**Acceptance Scenarios**:

1. **Given** cualquier llamada, **When** el servidor responde, **Then** la respuesta es `{ok: true, …}` o `{ok: false, error: {tipo, codigo, mensaje, reintentable, detalles}}`, nunca otra forma.
2. **Given** la inyección de fallas configurada para fallar las próximas N llamadas, **When** se llama a una herramienta, **Then** la respuesta es un error `transitorio` con `reintentable: true` y el estado no cambia (un intento de verificación fallido por inyección no cuenta).
3. **Given** un error interno inesperado, **When** ocurre, **Then** se devuelve como error estructurado de tipo `transitorio`, sin exponer detalles internos.

---

### User Story 4 - Arranque y descubrimiento de herramientas (Priority: P2)

El servidor arranca con un comando conocido y anuncia sus herramientas por el protocolo MCP,
con descripciones en español que indican cuándo usarlas y cuándo escalar.

**Why this priority**: lo necesita el agente (#7) para conectarse; las herramientas en sí ya
aportan valor probadas directamente.

**Independent Test**: arrancar el servidor y pedir la lista de herramientas por el protocolo.

**Acceptance Scenarios**:

1. **Given** el entorno instalado, **When** se ejecuta `python -m crediagil.mcp_server.server`, **Then** el servidor queda escuchando por la entrada/salida estándar.
2. **Given** el servidor arrancado, **When** un cliente MCP lista las herramientas, **Then** aparecen `buscar_solicitante` y `verificar_identidad` con su descripción y esquema de entrada.
3. **Given** que no existe el archivo de estado, **When** arranca, **Then** lo crea con los datos semilla.

### Edge Cases

- Documento con espacios o en minúsculas (`test-NNNNNN`): se normaliza antes de buscar.
- Nombre parcial con tildes o mayúsculas distintas: coincide igual ("perez" encuentra "Pérez").
- Dos procesos del servidor usando el mismo archivo de estado: ninguna escritura se pierde ni corrompe el archivo.
- Archivo de estado corrupto o ilegible: error `transitorio` estructurado; el servidor no sobrescribe el archivo con datos vacíos.
- La respuesta de búsqueda nunca incluye la fecha de nacimiento (es el dato secreto de la verificación).
- Verificación exitosa tras 1 o 2 fallos: reinicia el contador.
- Fallas inyectadas: no consumen intentos de verificación ni modifican el estado.

## Requirements *(mandatory)*

### Functional Requirements

**Contrato de respuesta**

- **FR-001**: Toda respuesta de herramienta MUST ser `{ok: true, …datos}` o `{ok: false, error: {tipo, codigo, mensaje, reintentable, detalles}}`.
- **FR-002**: `tipo` MUST ser uno de `transitorio`, `validacion`, `negocio`, `permisos`; `reintentable` MUST ser `true` solo para `transitorio`.
- **FR-003**: `codigo` MUST ser un identificador estable en mayúsculas (p. ej. `SOLICITANTE_BLOQUEADO`); `mensaje` MUST estar en español; `detalles` MUST ser un objeto (vacío si no aplica).
- **FR-004**: Un error inesperado MUST devolverse como `transitorio` sin trazas ni detalles internos.

**`buscar_solicitante`**

- **FR-005**: MUST aceptar exactamente uno de: `documento` o `nombre` (parcial, mínimo 3 caracteres). Otro caso MUST ser error `validacion`.
- **FR-006**: La búsqueda por documento MUST ser exacta tras normalizar (sin espacios, mayúsculas). La búsqueda por nombre MUST ser por subcadena, sin distinguir mayúsculas ni tildes.
- **FR-007**: MUST devolver `coincidencias`: lista (posiblemente vacía) con identificador del solicitante, documento, nombre completo y si está bloqueado. MUST NOT incluir la fecha de nacimiento.

**`verificar_identidad`**

- **FR-008**: MUST aceptar el identificador del solicitante y la fecha de nacimiento (formato `AAAA-MM-DD`).
- **FR-009**: Fecha correcta → `ok: true`, `verificado: true`; reinicia los intentos fallidos.
- **FR-010**: Fecha incorrecta → error `negocio` `IDENTIDAD_NO_COINCIDE` con `intentos_restantes` en `detalles`. Al tercer fallo consecutivo → error `permisos` `SOLICITANTE_BLOQUEADO` y el solicitante queda bloqueado.
- **FR-011**: Un solicitante bloqueado MUST recibir siempre `permisos` `SOLICITANTE_BLOQUEADO`, aunque la fecha sea correcta. El desbloqueo queda fuera de alcance.
- **FR-012**: Solicitante inexistente → `negocio` `SOLICITANTE_NO_ENCONTRADO`. Fecha con formato inválido o futura → `validacion`, sin contar intento.

**Estado e inyección de fallas**

- **FR-013**: Solicitantes, intentos fallidos y bloqueos MUST persistir en un archivo local entre reinicios; las escrituras MUST hacerse bajo bloqueo exclusivo y de forma atómica.
- **FR-014**: Si el archivo de estado no existe, MUST crearse con los datos semilla.
- **FR-015**: MUST existir una inyección de fallas transitorias configurable sin cambiar código (p. ej. "fallar las próximas N llamadas" o una probabilidad con semilla fija), desactivada por defecto. Una falla inyectada MUST NOT cambiar el estado.

**Datos y arranque**

- **FR-016**: Los datos semilla MUST ser 100% ficticios, con documentos `TEST-` seguido de 6 dígitos, e incluir al menos dos solicitantes que comparten parte del nombre.
- **FR-017**: El servidor MUST arrancar con `python -m crediagil.mcp_server.server` por stdio y listar sus herramientas por el protocolo MCP, con descripciones en español que digan cuándo usarlas y cuándo escalar.
- **FR-018**: Cada herramienta MUST tener tests de sus casos de éxito y de cada tipo de error, incluidos los bordes del bloqueo (2 fallos: no bloquea; 3: bloquea).

### Key Entities

- **Solicitante**: identificador, documento (`TEST-NNNNNN`), nombre completo, fecha de nacimiento (secreta), intentos fallidos (0–3), bloqueado (sí/no).
- **Respuesta**: éxito (`ok: true` + datos) o error (`ok: false` + `ErrorEstructurado`).
- **ErrorEstructurado**: tipo, código, mensaje, reintentable, detalles.
- **Estado del core**: conjunto de solicitantes persistido en un archivo local.
- **Configuración de fallas**: modo y parámetros de la inyección de fallas transitorias.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El 100% de las respuestas de las herramientas cumplen la forma única del contrato.
- **SC-002**: Ninguna búsqueda sin resultados produce un error.
- **SC-003**: El 100% de los solicitantes con 3 fallos consecutivos quedan bloqueados, también tras reiniciar el servidor; ninguno con 2.
- **SC-004**: 0 respuestas de búsqueda incluyen la fecha de nacimiento.
- **SC-005**: Con la inyección activada, el 100% de las fallas inyectadas son `transitorio` y reintentables, sin cambios de estado.
- **SC-006**: Un cliente MCP descubre las 2 herramientas al arrancar el servidor con el comando documentado.

## Assumptions

- El identificador del solicitante lo devuelve la búsqueda y se usa para verificar (el agente busca primero y luego verifica).
- El tercer fallo consecutivo devuelve directamente el error `permisos`; los dos primeros, `negocio` con intentos restantes.
- El desbloqueo de un solicitante (analista o reinicio del estado) queda fuera de alcance; borrar el archivo de estado restaura los datos semilla.
- El archivo de estado vive fuera del control de versiones (configurable; por defecto en un directorio de datos local ignorado por git).
- La inyección de fallas se configura por variables de entorno del servidor.
- Las reglas de negocio (identidad verificada antes de registrar, umbrales) se hacen cumplir en hooks del Agent SDK (#6), no dentro de estas herramientas (Principio II, `.claude/rules/mcp-server.md`).
- **Datos semilla y hook de datos sensibles**: un documento `TEST-` con su número junto a la etiqueta "documento" activa el hook `block_sensitive_data`. Los datos semilla y los tests llevan `pragma: dato-ficticio` en esas líneas, o se construyen en tiempo de ejecución. Que el hook reconozca el prefijo `TEST-` como ficticio queda como posible mejora de #1, fuera de esta feature.
