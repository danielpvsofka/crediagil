# Feature Specification: Hooks del Agent SDK para las reglas 1 y 2

**Feature Branch**: `develop` (sin hook de rama; directorio de spec: `specs/006-sdk-rule-hooks`)

**Created**: 2026-10-17

**Status**: Draft

**Issue**: [#6](https://github.com/danielpvsofka/crediagil/issues/6) · **Depende de**: #5 (y #3, #4) · **Habilita**: #7, #8

**Input**: User description: "Hooks del Agent SDK para las reglas 1 y 2 — Las reglas 1 (identidad verificada) y 2 (umbrales de preaprobación) deben garantizarse con hooks del SDK. Una instrucción en el prompt no es suficiente. Alcance: hooks PreToolUse sobre registrar_solicitud y preaprobar_credito. Criterios: el hook de registro niega la llamada si el solicitante no tiene identidad verificada en el estado del core; el hook de preaprobación niega si la solicitud no existe, si no hay identidad verificada, si hay hallazgos documentales o si no cumple los umbrales; los hooks deciden leyendo el estado del core y recalculando con el módulo de política, nunca con lo que afirma el modelo; fail-closed: si no se puede leer el estado, se niega; el motivo de la negación se devuelve al modelo y queda disponible para la interfaz; tests invocan los hooks como lo haría el SDK, sin modelo: preaprobar sin identidad es bloqueado. Depende de #5. Issue: #6"

> **Nota de alcance**: esta feature entrega los hooks y su configuración lista para pasar al
> agente. El ensamblado del agente que los registra es #7. Los parámetros de la constitución no
> se repiten aquí: los hooks los obtienen de `crediagil.policy`.

## User Scenarios & Testing *(mandatory)*

Actores: **agente de originación** (el modelo, que puede equivocarse o ser inducido a error),
**interfaz de chat** (#8), que muestra los bloqueos, y **equipo de desarrollo**.

### User Story 1 - Bloquear el registro sin identidad verificada (Priority: P1)

Cuando el modelo intenta registrar una solicitud, un hook comprueba en el estado del core que el
solicitante tiene la identidad verificada. Si no, la llamada no llega a la herramienta.

**Why this priority**: es la regla 1 de la constitución: ninguna solicitud se registra sin
identidad verificada. El modelo puede olvidarla; el hook no.

**Independent Test**: invocar el hook con un solicitante sin verificar, bloqueado y verificado.

**Acceptance Scenarios**:

1. **Given** un solicitante sin identidad verificada, **When** el modelo llama a `registrar_solicitud`, **Then** el hook niega la llamada con motivo `IDENTIDAD_NO_VERIFICADA` y la herramienta no se ejecuta.
2. **Given** un solicitante bloqueado tras fallar la verificación, **When** se intenta registrar, **Then** se niega con el mismo motivo.
3. **Given** un solicitante con identidad verificada y vigente, **When** el modelo registra, **Then** el hook permite la llamada.
4. **Given** una solicitud de registro para un identificador que no existe, **When** se intenta, **Then** se niega con `IDENTIDAD_NO_VERIFICADA`.

---

### User Story 2 - Bloquear la preaprobación que no cumple las reglas (Priority: P1)

Cuando el modelo intenta preaprobar, un hook lee la solicitud guardada, vuelve a comprobar la
identidad y recalcula las reglas con la política. Solo si todo se cumple la llamada llega a la
herramienta, aunque el modelo afirme que ya está evaluado.

**Why this priority**: comprometer a Crediágil es lo más costoso; las reglas 1 y 2 no pueden
depender de lo que diga el modelo.

**Independent Test**: preaprobar solicitudes inexistentes, de solicitantes sin identidad, con
hallazgos documentales, fuera de umbral y válidas.

**Acceptance Scenarios**:

1. **Given** una solicitud que no existe, **When** el modelo llama a `preaprobar_credito`, **Then** el hook niega con `SOLICITUD_NO_ENCONTRADA`.
2. **Given** una solicitud cuyo solicitante no tiene identidad verificada (por ejemplo, quedó bloqueado después de registrar), **When** se intenta preaprobar, **Then** se niega con `IDENTIDAD_NO_VERIFICADA`.
3. **Given** una solicitud con hallazgos documentales (dato faltante, inconsistencia, fuera de política), **When** se intenta preaprobar, **Then** se niega con `HALLAZGOS_DOCUMENTALES` y la lista de hallazgos.
4. **Given** una solicitud que supera el monto o la proporción de cuota, o cuya discrepancia de ingreso excede lo permitido, **When** se intenta preaprobar, **Then** se niega con `NO_PREAPROBABLE` y las causas, aunque la evaluación guardada diga lo contrario.
5. **Given** una solicitud escalada a un analista, **When** se intenta preaprobar, **Then** se niega con `SOLICITUD_ESCALADA`.
6. **Given** una solicitud que cumple identidad, documentos y umbrales (también en los bordes exactos), **When** se preaprueba, **Then** el hook permite la llamada.

---

### User Story 3 - Fallar cerrado (Priority: P1)

Si el hook no puede comprobar algo, niega: nunca deja pasar por duda.

**Why this priority**: una garantía que se abre cuando falla algo no es una garantía.

**Independent Test**: provocar estado ausente, ilegible, entrada de herramienta malformada y
error inesperado dentro del hook.

**Acceptance Scenarios**:

1. **Given** que el estado del core no se puede leer (archivo ilegible o corrupto), **When** el modelo llama a cualquiera de las dos herramientas, **Then** el hook niega con `ESTADO_ILEGIBLE`.
2. **Given** una llamada sin el identificador esperado o con un tipo incorrecto, o —en la preaprobación, cuya herramienta solo admite el identificador de la solicitud— con campos adicionales, **When** llega al hook, **Then** se niega con `ENTRADA_INVALIDA`. (En el registro el hook solo valida el identificador del solicitante; el resto de argumentos los valida la herramienta.)
3. **Given** un error inesperado dentro del hook, **When** ocurre, **Then** se niega con `ERROR_INTERNO` y sin exponer detalles internos.
4. **Given** una llamada a cualquier otra herramienta, **When** llega a estos hooks, **Then** no se interfiere con ella (los hooks solo se registran para las dos herramientas).

---

### User Story 4 - Motivo de la negación para el modelo y la interfaz (Priority: P2)

Cada negación devuelve al modelo un motivo claro y queda registrada en un formato que la
interfaz puede mostrar.

**Why this priority**: el modelo necesita saber por qué para escalar o pedir datos en lugar de
insistir; la interfaz necesita mostrar el "bloqueo por regla de negocio" (#8).

**Independent Test**: provocar una negación y leer el motivo devuelto y el registro de
negaciones.

**Acceptance Scenarios**:

1. **Given** una negación, **When** el hook responde, **Then** el motivo que recibe el modelo incluye el código, un mensaje en español y qué hacer (escalar, pedir datos o no reintentar).
2. **Given** una negación, **When** la interfaz consulta el registro, **Then** encuentra una entrada con herramienta, código, mensaje, datos de la solicitud y momento.
3. **Given** una llamada permitida, **When** pasa por el hook, **Then** no se registra ninguna negación.

### Edge Cases

- El modelo afirma en sus argumentos que la identidad está verificada o que la solicitud es preaprobable: el hook lo ignora y decide con el estado.
- Estado modificado entre el registro y la preaprobación (solicitante bloqueado): la preaprobación se niega.
- Solicitud ya preaprobada: el hook aplica las mismas comprobaciones; si siguen cumpliéndose, permite la llamada (la herramienta es idempotente).
- Dos hooks sobre la misma llamada (registro y preaprobación): cada uno solo evalúa su herramienta.
- El nombre de la herramienta llega con el prefijo del servidor MCP; los hooks reconocen ese nombre completo y ninguna variante parecida.
- Los hooks no modifican el estado ni consumen intentos: son de solo lectura.

## Requirements *(mandatory)*

### Functional Requirements

**Hook de registro (regla 1)**

- **FR-001**: Antes de `registrar_solicitud`, el hook MUST leer el estado del core y negar la llamada si el solicitante indicado no existe, no tiene la identidad verificada o está bloqueado (`IDENTIDAD_NO_VERIFICADA`).
- **FR-002**: El hook de registro MUST NOT evaluar umbrales: registrar una solicitud no preaprobable es legítimo (se evalúa y se escala).

**Hook de preaprobación (reglas 1 y 2)**

- **FR-003**: Antes de `preaprobar_credito`, el hook MUST negar si la solicitud no existe (`SOLICITUD_NO_ENCONTRADA`) o está escalada (`SOLICITUD_ESCALADA`).
- **FR-004**: MUST negar si el solicitante de la solicitud no tiene identidad verificada vigente (`IDENTIDAD_NO_VERIFICADA`).
- **FR-005**: MUST negar si la solicitud tiene hallazgos documentales (`HALLAZGOS_DOCUMENTALES`, con la lista).
- **FR-006**: MUST recalcular con `crediagil.policy` y los datos guardados la regla 2 y la regla 3, y negar si el resultado no es preaprobable (`NO_PREAPROBABLE`, con las causas). La evaluación guardada en la solicitud MUST NOT usarse para decidir.
- **FR-007**: Los hooks MUST NOT usar lo que afirma el modelo (argumentos que describan identidad, evaluación o umbrales) como fuente de verdad: del argumento solo se toma el identificador del solicitante o de la solicitud.

**Comportamiento común**

- **FR-008**: Fail-closed: si el estado no se puede leer (`ESTADO_ILEGIBLE`), si la entrada de la herramienta es inválida (`ENTRADA_INVALIDA`) o si ocurre un error inesperado (`ERROR_INTERNO`), el hook MUST negar.
- **FR-009**: Una negación MUST devolver al modelo el motivo con código, mensaje en español y la acción esperada, y MUST anotarse en un registro de negaciones accesible para la interfaz (herramienta, código, mensaje, datos, momento).
- **FR-010**: Los hooks MUST ser de solo lectura: no modifican el estado ni los intentos de verificación.
- **FR-011**: Los hooks MUST aplicarse únicamente a las dos herramientas indicadas, identificadas por su nombre completo con el prefijo del servidor MCP; el resto de herramientas no se ve afectado.
- **FR-012**: La feature MUST entregar una configuración de hooks lista para pasar a las opciones del agente (el ensamblado del agente es #7).
- **FR-013**: Cada negación posible y el caso permitido MUST tener tests que invoquen el hook con el mismo formato de entrada y salida que usa el SDK, sin modelo y sin red, incluidos los bordes exactos de las reglas 2 y 3 (Principio VII).

### Key Entities

- **Decisión del hook**: permitir o negar; en caso de negar, código, mensaje, acción esperada y datos de apoyo.
- **Registro de negaciones**: lista de negaciones con herramienta, código, mensaje, datos de la solicitud y momento, consultable por la interfaz.
- **Estado del core**: solicitantes, solicitudes y escalamientos (spec 004 y 005), leído por los hooks.
- **Configuración de hooks**: asociación de cada herramienta con su hook, en el formato del SDK.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El 100% de los intentos de registrar o preaprobar sin identidad verificada vigente son negados antes de llegar a la herramienta.
- **SC-002**: 0 preaprobaciones permitidas para solicitudes que no cumplen las reglas al recalcular, aunque el modelo afirme lo contrario o la evaluación guardada esté alterada.
- **SC-003**: El 100% de los casos en que el estado no se puede leer terminan en negación.
- **SC-004**: El 100% de las negaciones llevan un motivo con código y mensaje y quedan en el registro.
- **SC-005**: Los hooks no cambian el estado en ninguna ejecución (permitida o negada).

## Assumptions

- La negación se expresa con la decisión de permiso del SDK (`deny` con motivo), que el modelo recibe como resultado de su llamada.
- El registro de negaciones vive en memoria de la sesión del agente y se entrega a la interfaz mediante una función de consulta o devolución de llamada; persistirlo queda como mejora.
- La identidad vigente es la definida en #5: verificada alguna vez y no bloqueada desde entonces (no caduca por tiempo).
- Una solicitud ya preaprobada pasa por las mismas comprobaciones; si el solicitante se bloqueó después, el hook niega aunque la herramienta, por ser idempotente, devolvería el resultado guardado. Es una barrera más estricta a propósito.
- El hook de preaprobación reutiliza la misma evaluación del core que usa la herramienta, para que ambas barreras nunca discrepen.
- Los datos y textos de prueba son 100% ficticios; las líneas con forma de documento o cuenta junto a su etiqueta llevan `pragma: dato-ficticio`.
- Esta feature no necesita la clave de la API: los tests no llaman al modelo. La prueba con el modelo real es de #7.
