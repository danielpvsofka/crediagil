# Feature Specification: CI y documentación de entrega

**Feature Branch**: `feature/010-reusable-plugin` (sin hook de rama; directorio de spec: `specs/011-ci-delivery-docs`)

**Created**: 2026-10-18

**Status**: Draft

**Issue**: [#11](https://github.com/danielpvsofka/crediagil/issues/11) · **Depende de**: #9, #10

**Input**: User description: "CI y documentación de entrega — El proyecto debe poder ejecutarse en menos de 5 minutos y justificar sus decisiones. Los datos sensibles deben vigilarse también fuera de Claude Code. Criterios: workflow de CI que ejecuta formato, tests y un escaneo de datos con forma real sobre todo el repositorio; README con instrucciones para correr el agente y los tests en menos de 5 minutos, enlace al Project y enlace al video de funcionamiento; `DECISIONES.md` de máximo dos páginas con el mecanismo elegido para cada necesidad del ecosistema y por qué; ningún archivo `.env` ni credencial en el repositorio. Depende de #9, #10. Issue: #11"

> **Nota de alcance**: esta feature no cambia ninguna regla de negocio ni el comportamiento del
> agente de originación. Cierra el proyecto por fuera: una verificación automática que no depende
> de Claude Code y la documentación con la que otra persona lo ejecuta y entiende sus decisiones. La
> tasa y los umbrales viven solo en la constitución y en la política; ni el CI ni la documentación
> los repiten.

## User Scenarios & Testing *(mandatory)*

Actores: **revisor** (decide si un cambio entra y quiere que una máquina lo compruebe), **equipo
de desarrollo** (abre cambios, a veces sin Claude Code, y necesita saber pronto qué rompió) y
**persona nueva** (clona el repositorio y quiere ver el agente y los tests funcionando sin pedir
ayuda).

### User Story 1 - Cada cambio se verifica automáticamente (Priority: P1)

Cuando alguien propone un cambio hacia la rama principal, una verificación automática comprueba el
formato del código, ejecuta las pruebas y busca datos con forma real en todo el repositorio. El
resultado se ve en el propio cambio y un fallo impide darlo por bueno, sin importar si se editó
con Claude Code o a mano.

**Why this priority**: los hooks locales solo protegen lo que se escribe con Claude Code; esta
verificación es la red de seguridad para todo lo demás y es el núcleo del ticket.

**Independent Test**: abrir tres cambios de prueba (formato incorrecto, una prueba rota, un dato
con forma real) y comprobar que cada uno falla con un motivo claro, y que un cuarto cambio limpio
pasa.

**Acceptance Scenarios**:

1. **Given** un cambio con código sin el formato del proyecto, **When** corre la verificación, **Then** falla indicando que el formato no cumple.
2. **Given** un cambio que rompe una prueba, **When** corre la verificación, **Then** falla y muestra qué prueba falló.
3. **Given** un cambio que añade en cualquier archivo un número con forma de tarjeta o una cédula, NIT o cuenta junto a su etiqueta, **When** corre la verificación, **Then** falla indicando el archivo y la línea, sin mostrar el dato completo.
4. **Given** un dato de prueba deliberadamente ficticio marcado con `dato-ficticio` en la misma línea, **When** corre la verificación, **Then** no se considera hallazgo, igual que en el hook local.
5. **Given** un cambio limpio, **When** corre la verificación, **Then** pasa sin necesitar claves ni consumir saldo del modelo.
6. **Given** que las pruebas con el modelo real son opcionales, **When** corre la verificación, **Then** no se ejecutan.

---

### User Story 2 - Ningún archivo de entorno ni credencial en el repositorio (Priority: P1)

El repositorio no contiene archivos de entorno con valores ni credenciales, y una comprobación
automática lo vigila en cada cambio: si alguien versiona un archivo de ese tipo o pega una clave,
la verificación falla antes de que entre.

**Why this priority**: un secreto publicado es un incidente aunque se borre después; es un criterio
explícito del ticket y de la constitución (Principio III).

**Independent Test**: añadir a un cambio de prueba un archivo de entorno versionado y, aparte, una
cadena con forma de clave de la API; comprobar que ambos hacen fallar la verificación y que el
árbol actual del repositorio pasa limpio.

**Acceptance Scenarios**:

1. **Given** el repositorio actual, **When** se ejecuta la comprobación, **Then** no hay archivos de entorno versionados ni cadenas con forma de credencial.
2. **Given** un cambio que versiona un archivo de entorno, **When** corre la verificación, **Then** falla nombrando el archivo.
3. **Given** un cambio que incluye una cadena con forma de clave de la API, **When** corre la verificación, **Then** falla indicando archivo y línea, sin repetir la clave en el informe.
4. **Given** el archivo de exclusiones del control de versiones, **When** se revisa, **Then** excluye los archivos de entorno y la carpeta de secretos.

---

### User Story 3 - Una persona nueva lo ejecuta en menos de 5 minutos (Priority: P2)

El README permite a alguien que no conoce el proyecto instalar, ejecutar las pruebas y abrir la
interfaz del agente en menos de 5 minutos, e incluye el enlace al tablero del proyecto y al video
de funcionamiento.

**Why this priority**: es lo primero que ve un evaluador; sin él el trabajo no se puede comprobar,
pero depende de que el resto exista y funcione.

**Independent Test**: una persona ajena sigue solo el README en una máquina con las herramientas
indicadas y mide el tiempo hasta ver las pruebas en verde y la interfaz abierta.

**Acceptance Scenarios**:

1. **Given** el README, **When** una persona nueva sigue los pasos en orden, **Then** en menos de 5 minutos tiene las pruebas deterministas en verde y la interfaz del agente abierta.
2. **Given** el README, **When** se buscan los enlaces, **Then** están el del tablero del proyecto y el del video de funcionamiento, y no están vacíos.
3. **Given** los comandos del README, **When** se ejecutan tal cual, **Then** funcionan sin pasos ocultos; lo que requiere clave del modelo lo dice y no bloquea las pruebas deterministas.
4. **Given** el README, **When** se leen los requisitos, **Then** declara qué herramientas hacen falta y cómo se aporta la clave sin escribirla en un archivo versionado.

---

### User Story 4 - Las decisiones se justifican en dos páginas (Priority: P2)

`DECISIONES.md` cabe en dos páginas y recoge, para cada necesidad del ecosistema de desarrollo,
qué mecanismo se eligió y por qué, para que un revisor entienda las decisiones sin leer el código.

**Why this priority**: justifica el diseño, pero solo tiene sentido con el trabajo terminado.

**Independent Test**: contar la longitud del documento contra el límite y comprobar que cada
necesidad del ecosistema aparece con su mecanismo y su motivo.

**Acceptance Scenarios**:

1. **Given** `DECISIONES.md`, **When** se mide su longitud, **Then** no supera el equivalente a dos páginas.
2. **Given** la lista de necesidades del ecosistema, **When** se revisa el documento, **Then** cada una tiene su mecanismo y el motivo de la elección, y alguna alternativa descartada donde aporte.
3. **Given** el documento, **When** se lee, **Then** no repite la tasa ni los umbrales de negocio y remite a la constitución.
4. **Given** que el CI y el plugin pasan a ser mecanismos reales, **When** se lee, **Then** reflejan su estado actual y no hablan de ellos como pendientes.

---

### Edge Cases

- ¿Qué pasa con un cambio que viene de una copia del repositorio sin acceso a secretos? La verificación no necesita ninguno, así que corre igual.
- ¿Qué pasa con datos de prueba con forma real que son deliberadamente ficticios? Se aceptan solo con el marcador `dato-ficticio` en la misma línea; sin él, fallan.
- ¿Qué pasa si el escaneo encuentra un falso positivo en un archivo generado o binario? Los binarios y las carpetas de dependencias o caché no se escanean; para el resto el marcador es la única salida.
- ¿Qué pasa si la verificación tarda demasiado? Debe terminar en minutos; una ejecución que supere el límite se considera fallo.
- ¿Qué pasa si el informe del escaneo imprime el dato encontrado? No debe: nunca reproduce el número ni la clave completos.
- ¿Qué pasa si el README y los comandos reales se desfasan? Una comprobación automática detecta que falta un enlace o un comando obligatorio.
- ¿Qué pasa si hay un archivo de entorno local sin versionar en la máquina de quien desarrolla? No cuenta: solo se vigilan los archivos versionados.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El repositorio MUST incluir una verificación automática que corre en cada cambio propuesto hacia la rama principal y en cada publicación en ella, y cuyo resultado es visible en el propio cambio.
- **FR-002**: La verificación MUST comprobar el formato del código y fallar si no cumple; también el análisis estático que el proyecto ya usa.
- **FR-003**: La verificación MUST ejecutar las pruebas deterministas del proyecto, sin red, sin clave y sin consumir saldo, y MUST NOT ejecutar las pruebas con el modelo real.
- **FR-004**: La verificación MUST escanear todos los archivos de texto versionados del repositorio buscando datos con forma real (tarjeta válida por Luhn, cédula, NIT o cuenta junto a su etiqueta) con las mismas reglas que el hook local, sin duplicar su lógica, y respetando el marcador `dato-ficticio` en la misma línea.
- **FR-005**: La verificación MUST fallar si hay un archivo de entorno o de secretos versionado, o una cadena con forma de credencial en cualquier archivo versionado.
- **FR-006**: Todo hallazgo MUST informar archivo y línea y MUST NOT reproducir el dato ni la credencial completos.
- **FR-007**: La verificación MUST NOT requerir secretos ni la clave del modelo, de modo que corra igual en cambios de personas sin acceso a ellos.
- **FR-008**: Los controles del escaneo MUST tener tests junto al código, con controles negativos que demuestren que detecta una tarjeta, una cédula, una cuenta, un archivo de entorno y una credencial construidos en ejecución, y que no falla con el marcador ni con texto limpio (Principio VII).
- **FR-009**: El escaneo MUST poder ejecutarse también en local, con el mismo resultado que en la verificación automática.
- **FR-010**: El README MUST explicar cómo instalar, ejecutar las pruebas y abrir la interfaz del agente en menos de 5 minutos, con los requisitos y cómo aportar la clave sin versionarla.
- **FR-011**: El README MUST incluir el enlace al tablero del proyecto y el enlace al video de funcionamiento.
- **FR-012**: `DECISIONES.md` MUST tener como máximo dos páginas y MUST recoger, para cada necesidad del ecosistema de desarrollo, el mecanismo elegido y por qué.
- **FR-013**: Una comprobación automática MUST fallar si `DECISIONES.md` supera el límite de longitud, o si el README pierde alguno de los dos enlaces o un comando obligatorio.
- **FR-014**: El repositorio MUST NOT contener archivos de entorno con valores ni credenciales, y el archivo de exclusiones MUST excluir los archivos de entorno y la carpeta de secretos.
- **FR-015**: Esta feature MUST NOT cambiar reglas de negocio, política, prompts ni el comportamiento del agente, y MUST NOT repetir la tasa ni los umbrales en el CI ni en la documentación.

### Key Entities

- **Verificación automática (CI)**: conjunto de comprobaciones que corre por cada cambio: formato, pruebas y escaneo.
- **Escaneo de datos y credenciales**: recorrido de los archivos versionados que produce hallazgos.
- **Hallazgo**: archivo, línea y tipo de dato detectado, sin el valor completo.
- **README de entrega**: guía de ejecución con requisitos, comandos y enlaces.
- **Documento de decisiones**: `DECISIONES.md`, con la necesidad, el mecanismo y el motivo de cada decisión.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El 100 % de los cambios de prueba con formato incorrecto, prueba rota, dato con forma real o credencial son rechazados por la verificación, y el cambio limpio pasa.
- **SC-002**: La verificación completa termina en menos de 10 minutos.
- **SC-003**: Una persona nueva instala, ejecuta las pruebas deterministas y abre la interfaz del agente en menos de 5 minutos siguiendo solo el README.
- **SC-004**: `DECISIONES.md` no supera dos páginas y cubre el 100 % de las necesidades del ecosistema listadas.
- **SC-005**: El 0 % de los archivos versionados son archivos de entorno o contienen credenciales, comprobado en cada ejecución.
- **SC-006**: El escaneo local y el automático dan el mismo resultado sobre el mismo conjunto de muestras.
- **SC-007**: Cero informes de hallazgos reproducen el dato o la credencial completos.

## Assumptions

- El repositorio está en GitHub, así que la verificación automática es un flujo de trabajo de GitHub; no se evalúan otras plataformas.
- Dos páginas equivalen a unas 1.000 palabras (alrededor de 500 por página). `DECISIONES.md` medía unas 1.180 y quedó en 915, sin perder ninguna necesidad. *Confirmado por el usuario el 2026-10-18.*
- El escaneo reutiliza las reglas del hook `block_sensitive_data` en lugar de reescribirlas; el CI no añade reglas nuevas de datos con forma real, salvo las de credenciales de la FR-005.
- El análisis estático ya usado por el proyecto forma parte de "formato" porque no añade herramientas nuevas.
- Los enlaces al tablero y al video ya existen en el README; se comprueba que estén presentes y no vacíos, no que el video se reproduzca.
- Los archivos de entorno locales sin versionar de cada persona no cuentan; solo se vigila lo versionado. Una plantilla de ejemplo de variables queda fuera de alcance.
- Se verifica el árbol actual en cada ejecución; una revisión única del historial de cambios en busca de credenciales se hace al cerrar la feature, no en cada ejecución.
- Fuera de alcance: proteger la rama principal desde la configuración de GitHub (ajuste manual), publicar versiones, ejecutar las pruebas con el modelo real en CI y automatizar la actualización del plugin.
- Esta feature se integra después de #9 y #10, que añaden pruebas y piezas que la verificación ejecuta y escanea.
