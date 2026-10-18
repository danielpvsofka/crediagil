# Feature Specification: Plugin reutilizable por otros equipos

**Feature Branch**: `develop` (sin hook de rama; directorio de spec: `specs/010-reusable-plugin`)

**Created**: 2026-10-18

**Status**: Draft

**Issue**: [#10](https://github.com/danielpvsofka/crediagil/issues/10) · **Depende de**: #2

**Input**: User description: "Plugin reutilizable por otros equipos — Otro equipo de la fintech debe poder instalar nuestras piezas reutilizables en su propio repositorio. Criterios: plugin `crediagil-devkit` con al menos un subagente (`code-reviewer`), una skill (`compliance-check`) y un hook (datos con forma real); `marketplace.json` en la raíz del repositorio que permite instalarlo con `/plugin`; README del plugin con instrucciones de instalación; un test falla si las copias del plugin divergen de las de `.claude/`; lo específico de este repositorio (`require_spec`, `/ticket`) queda fuera del plugin. Depende de #2. Issue: #10"

> **Nota de alcance**: esta feature no cambia ninguna regla de negocio ni el comportamiento del
> agente de originación. Empaqueta piezas de desarrollo que ya existen en `.claude/` (#1 y #2)
> para que otro equipo las use sin copiarlas a mano. La tasa y los umbrales viven solo en la
> constitución y en la política; el plugin no los repite.

## User Scenarios & Testing *(mandatory)*

Actores: **equipo consumidor** (otro equipo de la fintech que quiere las revisiones y la
protección de datos sin heredar el flujo de este repositorio), **mantenedor** (quien cambia las
piezas en `.claude/` y no debe olvidarse de actualizar el plugin) y **revisor** (comprueba que el
plugin no arrastra nada específico de Crediágil).

### User Story 1 - Instalar el plugin desde el repositorio (Priority: P1)

Una persona de otro equipo añade este repositorio como fuente de plugins, instala
`crediagil-devkit` desde el gestor de plugins de Claude Code y, en su propio repositorio, dispone
del subagente `code-reviewer`, la skill `compliance-check` y el hook que bloquea datos con forma
real.

**Why this priority**: es el objetivo del ticket; sin una instalación que funcione no hay nada
reutilizable.

**Independent Test**: en un repositorio vacío, añadir la fuente, instalar el plugin y comprobar
que las tres piezas aparecen y funcionan.

**Acceptance Scenarios**:

1. **Given** un repositorio ajeno sin configuración de Claude Code, **When** la persona añade este repositorio como fuente de plugins y lista lo disponible, **Then** ve `crediagil-devkit` con su descripción.
2. **Given** el plugin instalado, **When** se listan los subagentes y las skills, **Then** aparecen `code-reviewer` y `compliance-check`.
3. **Given** el plugin instalado, **When** se intenta escribir un archivo con una tarjeta válida o una cédula/cuenta junto a su etiqueta, **Then** la escritura se bloquea con el mismo mensaje que en este repositorio.
4. **Given** una línea con el marcador `dato-ficticio`, **When** se escribe con el plugin instalado, **Then** el hook la deja pasar.
5. **Given** que la skill `compliance-check` revisa el cumplimiento con un subagente revisor, **When** se instala el plugin, **Then** ese subagente viene incluido, de modo que la skill no queda rota en el repositorio consumidor.

---

### User Story 2 - Las copias del plugin no divergen de `.claude/` (Priority: P1)

Las piezas siguen viviendo en `.claude/` (es lo que usa este repositorio) y el plugin lleva copias.
Un test automático falla si alguna copia deja de ser idéntica a su original (salvo las variantes
declaradas, que el test comprueba aparte), de modo que quien
corrige un revisor o el hook no deja el plugin desactualizado sin darse cuenta.

**Why this priority**: sin esta garantía el plugin se pudre en silencio y el otro equipo recibe
versiones viejas de las reglas.

**Independent Test**: modificar una línea de un original en `.claude/` y comprobar que el test
falla indicando qué pieza divergió; revertir y comprobar que pasa.

**Acceptance Scenarios**:

1. **Given** originales y copias idénticas, **When** se ejecuta la suite, **Then** el test pasa.
2. **Given** un cambio en un original de `.claude/` sin su copia, **When** se ejecuta la suite, **Then** el test falla y nombra la pieza y el archivo que divergen.
3. **Given** un cambio en la copia del plugin sin su original, **When** se ejecuta la suite, **Then** también falla.
4. **Given** un archivo de una pieza empaquetada que falta en la copia, **When** se ejecuta la suite, **Then** el test falla indicando el faltante.
5. **Given** una variante declarada cuya sustitución ya no aplica porque el original cambió, **When** se ejecuta la suite, **Then** el test falla pidiendo revisar la variante.

---

### User Story 3 - Lo específico de este repositorio queda fuera (Priority: P2)

El plugin contiene solo piezas genéricas. El hook de specs obligatorias, el comando de tickets y
cualquier otra pieza atada al flujo de Crediágil no se empaquetan, y las piezas empaquetadas no
dependen de rutas ni archivos que solo existen aquí.

**Why this priority**: un plugin que exige la estructura de este repositorio no sirve a otro
equipo; es la calidad del plugin, no su existencia.

**Independent Test**: un test inspecciona el contenido del plugin y falla si aparece alguna pieza
de la lista de exclusiones o una referencia a recursos propios de este repositorio.

**Acceptance Scenarios**:

1. **Given** el plugin, **When** se enumera su contenido, **Then** no incluye el hook de specs obligatorias, el comando de apertura de PR ni la skill de tickets.
2. **Given** una pieza empaquetada, **When** se revisan sus referencias, **Then** no apunta a archivos que no viajan con el plugin (por ejemplo la constitución o `specs/` de este repositorio) sin una alternativa documentada.
3. **Given** una pieza nueva en `.claude/` que no está en la lista de empaquetadas ni en la de exclusiones, **When** se ejecuta la suite, **Then** el test falla pidiendo decidir si se empaqueta o se excluye.

---

### User Story 4 - Instrucciones de instalación y uso (Priority: P2)

El plugin trae un README que explica, para alguien que no conoce este repositorio, cómo
instalarlo, qué incluye, qué necesita su repositorio para que cada pieza funcione y cómo
actualizarlo.

**Why this priority**: sin instrucciones el otro equipo depende de preguntar; es barato y cierra
la entrega.

**Independent Test**: una persona ajena al proyecto sigue solo el README y consigue instalar el
plugin y ver sus piezas.

**Acceptance Scenarios**:

1. **Given** el README del plugin, **When** se sigue paso a paso, **Then** se llega a tener el plugin instalado sin consultar otro documento.
2. **Given** el README, **When** se busca qué incluye, **Then** lista las piezas con una línea cada una y sus requisitos en el repositorio consumidor.
3. **Given** el README, **When** se busca cómo actualizar, **Then** explica cómo obtener una versión nueva.

---

### Edge Cases

- ¿Qué pasa si el repositorio consumidor no tiene constitución? La skill de cumplimiento debe indicar qué documento necesita y dónde esperarlo, no fallar con un error opaco.
- ¿Qué pasa si el consumidor no tiene `uv` o Python para el hook? El README lo declara como requisito y el hook no deja la escritura bloqueada sin explicación.
- ¿Qué pasa si el consumidor ya tiene su propio `code-reviewer`? El plugin usa un espacio de nombres propio y el README explica cómo conviven.
- ¿Qué pasa si se cambia solo el formato (saltos de línea) de un original? La comparación no debe dar falsos positivos por diferencias de fin de línea.
- ¿Qué pasa si se añade una pieza al plugin sin su original? El test de divergencia también lo detecta.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El repositorio MUST contener un plugin llamado `crediagil-devkit` con al menos el subagente `code-reviewer`, la skill `compliance-check` y el hook que bloquea datos con forma real.
- **FR-002**: El repositorio MUST incluir en su raíz un catálogo de plugins (`marketplace.json`, dentro de la carpeta `.claude-plugin/` de la raíz, que es donde el gestor de plugins lo busca) que lista `crediagil-devkit` y permite instalarlo con el gestor de plugins de Claude Code.
- **FR-003**: El plugin MUST incluir el subagente revisor del que depende `compliance-check`, para que la skill funcione sin piezas adicionales. Como un plugin no aplica las restricciones de comandos que ese subagente declara en su configuración, la versión empaquetada MUST ser de solo lectura (sin ejecución de comandos), y esa diferencia MUST estar declarada y comprobada (FR-007).
- **FR-004**: El hook empaquetado MUST comportarse igual que el de este repositorio: bloquea tarjeta válida por Luhn y cédula, NIT o cuenta junto a su etiqueta, y respeta el marcador `dato-ficticio` en la misma línea.
- **FR-005**: El hook empaquetado MUST llevar consigo todo lo que necesita para ejecutarse (sus módulos de apoyo), sin depender de archivos de este repositorio.
- **FR-006**: El plugin MUST NOT incluir el hook de specs obligatorias, el comando de apertura de PR, la skill de tickets ni el hook de formato de Python; esta exclusión MUST estar declarada en una lista comprobable.
- **FR-007**: Un test MUST fallar si el contenido de una pieza empaquetada difiere del de su original en `.claude/`, si falta un archivo en cualquiera de los dos lados, o si aparece en `.claude/` una pieza no clasificada como empaquetada ni excluida. Las únicas diferencias admitidas son las **variantes declaradas** (cambios exactos y enumerados que el plugin exige, como el nombre con espacio de nombres de un subagente o quitar la ejecución de comandos); el test las aplica al original y falla si una deja de aplicar.
- **FR-008**: La comparación MUST ignorar diferencias de fin de línea y MUST nombrar la pieza y el archivo que divergen.
- **FR-009**: El plugin MUST incluir un README con instrucciones de instalación, lista de piezas, requisitos del repositorio consumidor, cómo coexistir con piezas del mismo nombre y cómo actualizar.
- **FR-010**: Cuando `compliance-check` no encuentre la constitución en el repositorio consumidor, MUST indicar qué documento necesita y dónde buscarlo, en lugar de revisar sin criterio.
- **FR-011**: El plugin MUST NOT contener datos reales, secretos ni la tasa ni los umbrales del negocio (Principio III y regla de no repetir parámetros); todo ejemplo usa datos ficticios.
- **FR-012**: Las piezas de este repositorio MUST seguir funcionando igual desde `.claude/`: empaquetarlas no cambia cómo las usa Crediágil.
- **FR-013**: El plugin MUST declarar nombre, versión y descripción, y la versión MUST cambiar cuando cambie su contenido.

### Key Entities

- **Plugin `crediagil-devkit`**: conjunto instalable de piezas genéricas de desarrollo, con nombre, versión y descripción.
- **Catálogo de plugins (`marketplace.json`)**: archivo en la raíz que anuncia el plugin y desde dónde se instala.
- **Pieza empaquetada**: subagente, skill o hook con su original en `.claude/` y su copia en el plugin.
- **Lista de exclusiones**: piezas de `.claude/` que se declaran propias de este repositorio y no se empaquetan.
- **Informe de divergencia**: resultado del test que nombra la pieza y el archivo que difieren, faltan o sobran.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Una persona de otro equipo instala el plugin y ve sus tres tipos de pieza en menos de 5 minutos siguiendo solo el README.
- **SC-002**: El 100 % de las piezas empaquetadas tienen un test que falla si su copia diverge de su original; cambiar una línea de cualquier original hace fallar la suite.
- **SC-003**: El 0 % de las piezas específicas de este repositorio (specs obligatorias, tickets, apertura de PR, formato) aparecen en el plugin.
- **SC-004**: Con el plugin instalado en un repositorio vacío, el 100 % de los casos de datos con forma real que se bloquean aquí también se bloquean allí.
- **SC-005**: La suite de comprobación del plugin corre en menos de 10 segundos, sin red ni clave.

## Assumptions

- El plugin se distribuye desde este mismo repositorio (catálogo en la raíz); no se publica en un catálogo externo.
- Las originales siguen en `.claude/` porque este repositorio las usa directamente; el plugin lleva copias comprobadas por test, no enlaces simbólicos (que no funcionan de forma fiable en Windows).
- El otro equipo usa Claude Code y tiene `uv` instalado; el hook se ejecuta con Python como en este repositorio.
- `compliance-check` y su subagente revisor evalúan contra la constitución del repositorio consumidor; si no existe, el README explica cómo aportar una o qué hará la skill en su ausencia.
- Los datos de ejemplo del plugin son ficticios y no se versiona ninguna clave.
- Esta feature empaqueta lo ya hecho en #1 y #2; no añade piezas nuevas ni cambia su lógica.
- Queda fuera de alcance publicar el plugin en un catálogo público y automatizar la actualización de versiones (trabajo futuro).
