# Implementation Plan: Casos de prueba obligatorios

**Branch**: `develop` (feature dir `009-mandatory-test-cases`) | **Date**: 2026-10-18 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/009-mandatory-test-cases/spec.md` — Issue [#9](https://github.com/danielpvsofka/crediagil/issues/9)

## Summary

Un catálogo único de casos en forma de carpetas, `src/crediagil/casos/`, y tres consumidores que
lo leen sin copias: tests deterministas, pruebas opt-in con el modelo real y el selector de la
interfaz de chat. No cambia ninguna regla ni ningún prompt.

- **Carpeta por caso**: `caso.json` (metadatos, solicitud y resultado esperado), `mensaje.md`,
  `documentos/*.txt|.md` y `extraccion/*.json` (lo que el extractor debe producir de cada
  documento, con fragmentos literales). Los ocho obligatorios más el complementario "mensaje
  mixto" de #8.
- **Cargador validado** (`catalogo.py`): rechaza casos incompletos, ids repetidos, documentos
  ilegibles, extracciones cuyo fragmento no está en el documento y resultados esperados fuera del
  vocabulario cerrado.
- **Tests deterministas** (sin modelo, red ni clave): cada caso se resuelve con las piezas reales
  —extracción validada, core (`registrar_solicitud`, `preaprobar_credito`, `escalar_a_analista`),
  hooks de #6 e inyector de fallas de #5— según su resultado esperado. Los bordes de monto, cuota
  y discrepancia se prueban aparte, con valores derivados de `crediagil.policy.params`.
- **Pruebas con modelo real** (`-m live`): una por caso, dirigidas por el propio catálogo
  (`esperado.herramientas`), que comprueban la traza y los avisos estructurados, nunca el texto.
  Sustituyen a las pruebas por caso de #7 para no pagar dos veces el mismo escenario.
- **Datos ficticios**: un test pasa el detector del hook `block_sensitive_data` por todos los
  textos del catálogo, sin duplicar su lógica.
- **Interfaz**: `crediagil.chat.casos` deja de tener los casos escritos a mano y adapta el
  catálogo; la API `GET /api/casos` conserva su forma.

Detalle y alternativas descartadas en [research.md](./research.md).

## Technical Context

**Language/Version**: Python ≥ 3.12

**Primary Dependencies**: ninguna nueva. Reutiliza `pydantic` (validación del catálogo),
`crediagil.extraction`, `crediagil.mcp_server`, `crediagil.agent` y `crediagil.policy`

**Storage**: archivos de texto y JSON versionados dentro del paquete (datos del paquete, los
incluye `hatchling` con el resto de `src/crediagil`); ningún estado propio. Los tests usan estados
temporales

**Testing**: pytest + anyio. Sin modelo: tests deterministas por caso y de bordes. Con modelo real:
`@pytest.mark.live`, parametrizado por el catálogo, con tope de coste por prueba

**Target Platform**: desarrollo local y, después, CI (#11); sin red ni clave en la suite normal

**Project Type**: biblioteca interna de datos de prueba y sus tests (paquete `crediagil.casos`)

**Performance Goals**: suite determinista de los casos en menos de 30 s (SC-003); en la práctica
unos segundos, porque no hay subprocesos salvo el servidor MCP del caso de falla transitoria

**Constraints**:
- Ningún caso repite la tasa ni los umbrales (el test de #8 lo sigue exigiendo para todo el
  catálogo); los tests los obtienen de `crediagil.policy.params`.
- Solo datos ficticios; identificadores con prefijo `TEST-` y marcador `dato-ficticio`.
- Las pruebas con modelo real comprueban la traza, no las palabras del modelo.
- Sin cambios de reglas, política, prompts ni comportamiento del agente (FR-017).

**Scale/Scope**: 9 carpetas de caso (8 obligatorios + 1 complementario), 1 módulo nuevo de
código (`catalogo.py`), 3 módulos de test (`test_catalogo`, `test_casos`, `test_bordes`) más
`test_datos_ficticios` y `test_vivo`, y un adaptador reducido en `chat/casos.py`

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Antes del diseño | Después del diseño |
|---|---|---|
| I. Reglas de negocio | ✅ No se tocan; los casos ejercen las cinco reglas: 1 (caso 5), 2 (casos 1, 4), 3 (caso 3), 4 (caso 8), 5 (caso 6) | ✅ Cada regla tiene caso y test que falla si se rompe; ninguna regla se reimplementa en los tests, siempre se llama a la política y al core |
| II. Garantía en código | ✅ La regla 1 se prueba contra el hook real; la 4 es de prompt (juicio) y se verifica solo con modelo real | ✅ Documentado: la regla 4 no tiene garantía en código; su prueba es opt-in y la brecha ya figura como trabajo futuro desde #7 |
| III. Datos ficticios | ✅ Documentos inventados; ids con prefijo `TEST-` | ✅ Test que pasa el detector del hook por todo el catálogo; ningún número con forma de tarjeta literal |
| IV. Spec antes que código | ✅ spec.md aprobada | ✅ plan y tasks antes de escribir en `src/` (hook `require_specs`) |
| V. No inventar datos | ✅ El caso 2 exige campo nulo y petición del dato | ✅ El test del caso 2 comprueba que el salario queda `None` y que no se infiere de extractos |
| VI. Trazabilidad | ✅ Cada dato extraído lleva documento y fragmento | ✅ Las extracciones esperadas se validan contra el texto: un fragmento que no sea literal rompe el cargador |
| VII. Tests en bordes | ✅ Es el objeto de la feature | ✅ `test_bordes.py`: monto 5.000.000 vs 5.000.001, cuota 30 % vs más de 30 %, diferencia 10 % vs más de 10 %, más identidad, humano y fuera de política |

Sin violaciones; la sección de complejidad no se usa.

## Project Structure

### Documentation (this feature)

```text
specs/009-mandatory-test-cases/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── catalogo.md      # formato de la carpeta de un caso y su vocabulario cerrado
├── checklists/
│   └── requirements.md
└── tasks.md             # lo genera /speckit-tasks
```

### Source Code (repository root)

```text
src/crediagil/
├── casos/
│   ├── __init__.py                  # re-exporta Caso, cargar_catalogo, obligatorios
│   ├── catalogo.py                  # modelo pydantic, cargador y validaciones
│   ├── 01_dentro_de_politica/
│   │   ├── caso.json
│   │   ├── mensaje.md
│   │   ├── documentos/certificado_laboral.txt
│   │   └── extraccion/certificado_laboral.json
│   ├── 02_dato_ausente/             # certificado sin salario
│   ├── 03_ingreso_discrepante/      # declarado > 10 % del verificado
│   ├── 04_monto_sobre_umbral/       # $8.000.000
│   ├── 05_preaprobar_sin_identidad/
│   ├── 06_moneda_extranjera/
│   ├── 07_falla_transitoria/
│   ├── 08_pedir_persona/            # sin documentos
│   ├── 09_mensaje_mixto/            # complementario (de #8)
│   ├── verificacion.py              # verifica una traza contra esperado.herramientas
│   ├── resolutores.py               # resuelve cada caso con core, hooks y política reales
│   ├── conftest.py                  # almacén temporal, identidad y documentos extraídos
│   ├── test_catalogo.py             # cargador, validaciones y completitud
│   ├── test_casos.py                # un test determinista por caso (usa resolutores)
│   ├── test_bordes.py               # umbrales exactos, por debajo y por encima
│   ├── test_sensibilidad.py         # romper una regla hace fallar su caso
│   ├── test_verificacion.py         # el verificador detecta cada incumplimiento
│   ├── test_datos_ficticios.py      # detector del hook sobre todo el catálogo
│   └── test_vivo.py                 # @live, parametrizado por el catálogo
├── chat/
│   ├── casos.py                     # ahora adapta el catálogo (CASOS, caso_por_id, casos_publicos)
│   └── test_casos.py                # ajustado a los ids nuevos
└── agent/
    └── test_vivo.py                 # se retiran las pruebas por caso que pasan al catálogo
```

La carpeta de cada caso se llama `NN_id`: el prefijo ordena los ocho obligatorios y el id es el
estable (se lee de `caso.json`, que debe coincidir con el nombre sin prefijo).

**Structure Decision**: los casos viven **dentro del paquete** (no en una carpeta de la raíz)
porque la interfaz de chat los sirve en ejecución y el paquete debe llevar sus datos al
instalarse; los tests quedan junto al código, como exige el Principio VII.

## Complexity Tracking

Sin violaciones que justificar.
