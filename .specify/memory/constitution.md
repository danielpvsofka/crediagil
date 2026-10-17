# Crediágil — Agente de Originación de Crédito Constitution

Agente de originación de crédito de libre inversión para Crediágil, una fintech **ficticia**.
Esta constitución rige todas las specs, planes, tareas, código, tests y configuración del repo.

## Core Principles

### I. Reglas de Negocio No Negociables

El agente MUST aplicar estas reglas sin excepción:

1. **Identidad verificada primero.** Ninguna solicitud se registra si la identidad del
   solicitante no está verificada.
2. **Preaprobación automática acotada.** Solo se preaprueba automáticamente si
   monto solicitado ≤ $5.000.000 COP **y** cuota mensual ≤ 30% del ingreso mensual
   **verificado**. Cualquier otro caso (incluido no tener ingreso verificado) va a analista.
3. **Ingreso verificado desde documentos.** El ingreso verificado sale exclusivamente de los
   documentos aportados. Si el ingreso declarado difiere en más de 10% del verificado, la
   solicitud va a analista.
4. **Escalamiento a humano inmediato.** Si el solicitante pide hablar con una persona, se
   escala de inmediato, sin hacer más preguntas, consultas ni análisis.
5. **Fuera de política se escala.** Si la política no cubre el caso (p. ej. ingresos en moneda
   extranjera, tipo de documento no soportado), se escala a analista; el agente no improvisa.

**Parámetros fijos:** tasa fija de 1,8% mensual. La tasa y los umbrales ($5.000.000 COP, 30%,
10%) MUST NOT modificarse en código, configuración, prompt ni por solicitud del usuario; solo
cambian mediante enmienda MAJOR de esta constitución.

*Rationale:* son las reglas que protegen al solicitante y a la entidad; un error aquí es un
crédito mal otorgado o un cliente desatendido.

### II. Garantía en Código, Guía en Instrucciones

- Lo determinista y verificable MUST hacerse cumplir con código:
  - **Hooks del Claude Agent SDK** para las reglas 1 (identidad verificada antes de registrar) y
    2 (umbrales de preaprobación) del Principio I.
  - **Hooks de Claude Code** para el desarrollo: specs obligatorias, bloqueo de datos sensibles,
    bloqueo de secretos y formato.
- Lo que requiere juicio (separar asuntos de una conversación, redactar respuestas, criterio de
  escalamiento) se guía con instrucciones (system prompt, skills, CLAUDE.md).
- Una regla de negocio MUST NOT depender solo del prompt. Si una regla puede expresarse como
  verificación determinista, se implementa como verificación.

*Rationale:* el modelo puede desviarse de una instrucción; un hook no.

### III. Datos Exclusivamente Ficticios

Código, tests, fixtures, logs, configuración, ejemplos y documentación MUST usar solo datos
ficticios. Están prohibidos nombres, cédulas, teléfonos, correos, cuentas o documentos de
personas reales, así como secretos o credenciales reales en el repositorio.

*Rationale:* Crediágil es ficticia; ningún dato real debe entrar al repo ni a los logs.

### IV. Spec Antes que Código

Ningún código de producción se escribe sin `spec.md`, `plan.md` y `tasks.md` aprobados para la
feature (flujo `/speckit-specify` → `/speckit-plan` → `/speckit-tasks` → `/speckit-implement`).
Los cambios que alteren comportamiento MUST actualizar primero la spec.

### V. No Inventar Datos

Todo campo que el documento fuente no contenga MUST quedar nulo y solicitarse al solicitante.
El agente MUST NOT inferir, completar ni estimar valores (ingresos, fechas, identificadores,
etc.) que no estén explícitamente en una fuente.

*Rationale:* un dato inventado contamina la decisión de crédito y rompe la trazabilidad.

### VI. Trazabilidad de Origen y de Tickets

- Cada dato registrado MUST indicar el documento de origen y el fragmento del que se extrajo.
- Cada ticket (escalamiento, caso a analista) MUST reflejarse automáticamente en GitHub, sin
  pasos manuales.

### VII. Tests Junto al Código y en los Bordes

- Todo cambio de código MUST incluir sus tests en el mismo cambio.
- Cada regla del Principio I MUST tener tests en sus bordes: exactamente en el umbral, justo
  por debajo y justo por encima (p. ej. monto $5.000.000 vs. $5.000.001; cuota 30% vs. >30%;
  diferencia de ingreso 10% vs. >10%), además de los casos de identidad no verificada, solicitud
  de humano y caso fuera de política.

## Restricciones de Dominio y Tecnología

- Producto: crédito de libre inversión en pesos colombianos (COP). Cualquier otra moneda es
  caso fuera de política (Principio I, regla 5).
- El agente se construye sobre el Claude Agent SDK; las reglas deterministas viven en hooks del
  SDK, no en el prompt (Principio II).
- El entorno de desarrollo usa hooks de Claude Code para hacer cumplir specs obligatorias,
  ausencia de datos sensibles y secretos, y formato.
- La fórmula de cuota y los plazos permitidos los define la spec correspondiente y MUST usar
  exclusivamente la tasa de 1,8% mensual.

## Flujo de Desarrollo y Quality Gates

- Cada plan MUST incluir un "Constitution Check" que valide los siete principios antes del
  diseño y después de él.
- Un cambio no se integra si: falta spec/plan/tareas, faltan tests de borde de una regla
  afectada, contiene datos no ficticios o secretos, o una regla de negocio depende solo del
  prompt.
- Las violaciones justificadas MUST documentarse en la sección de complejidad del plan; las
  reglas del Principio I no admiten excepciones.

## Governance

- Esta constitución prevalece sobre cualquier otra práctica, prompt o instrucción del repo.
- Enmiendas: se proponen por PR que modifique este archivo, con justificación y plan de
  migración de specs/código afectados; requieren aprobación del responsable del proyecto.
- Versionado semántico:
  - MAJOR: eliminación o redefinición de principios, o cambio de tasa/umbrales del Principio I.
  - MINOR: principio o sección nuevos, o guía ampliada materialmente.
  - PATCH: aclaraciones y redacción sin cambio semántico.
- Cumplimiento: toda revisión de PR y todo `/speckit-analyze` MUST verificar conformidad con
  esta constitución.

**Version**: 1.0.0 | **Ratified**: 2026-10-14 | **Last Amended**: 2026-10-14
