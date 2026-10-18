# Implementation Plan: CI y documentación de entrega

**Branch**: `feature/010-reusable-plugin` hoy (feature dir `011-ci-delivery-docs`; la implementación irá en su propia rama, ver Notas) | **Date**: 2026-10-18 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/011-ci-delivery-docs/spec.md` — Issue [#11](https://github.com/danielpvsofka/crediagil/issues/11)

## Summary

Una verificación automática que no depende de Claude Code (formato, pruebas y escaneo de datos y
credenciales sobre todo el repositorio) y la documentación de entrega ajustada a sus límites. No
cambia ninguna regla de negocio, política, prompt ni código de `src/`.

- **Workflow de CI** (`.github/workflows/ci.yml`): tres trabajos independientes (`formato`,
  `pruebas`, `escaneo`) en cada cambio hacia `main` y en cada publicación en ella; permisos de solo
  lectura, sin secretos, acciones fijadas por commit.
- **Escáner** (`scripts/scan_repo.py`): recorre los archivos del repositorio, reutiliza el detector
  del hook `block_sensitive_data` (sin copiar sus reglas) y añade dos comprobaciones propias:
  archivos de entorno o de secretos y cadenas con forma de credencial. Nunca imprime el valor;
  falla con código 1 si hay hallazgos. Corre igual en local y en CI.
- **Comprobaciones de la entrega** (`scripts/test_entrega.py`): `DECISIONES.md` dentro del límite de
  longitud y con sus necesidades completas, README con sus enlaces y comandos obligatorios.
- **Documentación**: recortar `DECISIONES.md` de unas 1.160 a como mucho 1.000 palabras sin perder
  ninguna necesidad; ajustar el README (URL real del clon, insignia del CI, comando del escaneo).

Detalle y alternativas descartadas en [research.md](./research.md).

## Technical Context

**Language/Version**: Python ≥ 3.12 (escáner y tests, solo biblioteca estándar en el escáner);
YAML del workflow de GitHub Actions

**Primary Dependencies**: ninguna nueva en el proyecto. El CI usa `actions/checkout` y
`astral-sh/setup-uv`, fijadas por commit

**Storage**: N/A (archivos versionados; el escáner no guarda estado)

**Testing**: pytest junto al código (`scripts/test_*.py`; `scripts` se añade a `testpaths`). El
detector del hook no se importa dentro de pytest (su biblioteca reconfigura `stdin` al cargarse y
falla con la captura de pytest), así que lo ejecutable de extremo a extremo se prueba por
subproceso sobre un repositorio git temporal y lo puro (credenciales, archivos de entorno,
enmascarado) se importa sin tocar el hook

**Target Platform**: GitHub Actions en `ubuntu-latest`; el equipo desarrolla en Windows y el
escáner también corre allí

**Project Type**: herramienta de desarrollo (script) y configuración de CI

**Performance Goals**: verificación completa en menos de 10 minutos (SC-002; en la práctica unos
2–3: las pruebas tardan ~35 s); escaneo de ~280 archivos en menos de 5 s

**Constraints**:
- El escáner reutiliza el detector del hook; no duplica sus expresiones (FR-004).
- Ningún informe reproduce un dato o una credencial (FR-006, SC-007).
- El CI no recibe secretos ni la clave del modelo y no ejecuta las pruebas `live` (FR-003, FR-007).
- Sin cambios de reglas, política, prompts ni comportamiento del agente (FR-015).
- No se toca `.claude/hooks/_hooklib.py` ni ninguna pieza empaquetada en el plugin (#10): cambiarla
  obligaría a sincronizar la copia y subir la versión.
- Los tests no escriben literales con forma de tarjeta, cédula, cuenta o credencial: se construyen
  en ejecución.

**Scale/Scope**: 1 workflow, 1 script de ~150 líneas, 3 módulos de test, ajustes de README,
`DECISIONES.md`, `CLAUDE.md` y `pyproject.toml` (`testpaths`)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Antes del diseño | Después del diseño |
|---|---|---|
| I. Reglas de negocio | ✅ No se tocan; el CI y la documentación no definen reglas | ✅ Un test busca la tasa y los umbrales de `crediagil.policy.params` en `DECISIONES.md`, el README y el workflow y falla si aparecen; el CI solo ejecuta las pruebas que ya cubren las reglas |
| II. Garantía en código | ✅ El escaneo es una verificación determinista, no una instrucción de prompt | ✅ Complementa el hook local con una barrera fuera de Claude Code; el límite de `DECISIONES.md` y los enlaces del README también son tests, no una convención |
| III. Datos ficticios | ✅ Es el objeto de la US2 | ✅ Los controles negativos construyen tarjeta, cédula, cuenta, archivo de entorno y credencial en ejecución; el escáner enmascara; el árbol actual pasa limpio salvo `uv.lock`, excluido por nombre (R3) |
| IV. Spec antes que código | ✅ spec.md aprobada | ✅ plan y tasks antes de escribir en `scripts/` o `.github/` (no están bajo `src/`, pero se sigue el flujo) |
| V. No inventar datos | ✅ No aplica | ✅ Sin cambio; el escáner no infiere nada, solo informa de lo que ve |
| VI. Trazabilidad | ✅ El ticket se refleja con `/ticket` y `/open-pr` | ✅ El informe de hallazgos da archivo y línea; el PR y el comentario del issue enlazan la spec |
| VII. Tests en bordes | ✅ Tests junto al código | ✅ Bordes exactos del escáner: credencial con 19 y 20 caracteres, archivo de entorno vs. nombre parecido, línea con y sin marcador; `DECISIONES.md` en 1.000 y 1.001 palabras (función de conteo probada con textos construidos) |

Sin violaciones; la sección de complejidad no se usa.

## Project Structure

### Documentation (this feature)

```text
specs/011-ci-delivery-docs/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── ci.md            # workflow: disparadores, trabajos, permisos, acciones fijadas
│   └── escaneo.md       # CLI del escáner: categorías, exclusiones, salida y códigos de salida
├── checklists/
│   └── requirements.md
└── tasks.md             # lo genera /speckit-tasks
```

### Source Code (repository root)

```text
.github/workflows/
└── ci.yml                       # formato · pruebas · escaneo

scripts/
├── scan_repo.py                 # escáner de datos con forma real, archivos de entorno y credenciales
├── test_scan_repo.py            # puro (credenciales, entorno, enmascarado) + subproceso sobre repo git temporal
├── test_ci.py                   # el workflow cumple el contrato (disparadores, trabajos, sin secretos, SHA fijas)
└── test_entrega.py              # DECISIONES.md (longitud, necesidades) y README (enlaces, comandos)

pyproject.toml                   # testpaths += "scripts"
README.md                        # URL del clon, insignia del CI, comando del escaneo
DECISIONES.md                    # recortado a ≤ 1.000 palabras; CI y plugin ya no figuran como pendientes
CLAUDE.md                        # comando del escaneo y del CI
```

**Structure Decision**: el escáner vive en `scripts/` y no en `.claude/hooks/` porque no es un hook
y, allí, el test de integridad del plugin (#10) lo trataría como una pieza sin clasificar; tampoco
en `src/`, que es el paquete del agente. Los tests quedan junto al código, como exige el
Principio VII.

## Notas

- **Rama de implementación**: la spec se creó con `feature/010-reusable-plugin` activa (el flujo
  `/ticket` no crea ramas). `/speckit-implement` debe correr en una rama propia de #11, creada
  cuando #20 (#9) y #21 (#10) estén fusionados o, como mínimo, desde `feature/010-reusable-plugin`
  si se quiere avanzar antes; no se mezcla con el PR #21.
- **Dependencia**: el CI ejecuta la suite de #9 y #10; hasta que estén en `main`, su primera
  ejecución completa será la del PR de #11 o la de los PR #20 y #21 una vez exista el workflow.

## Complexity Tracking

Sin violaciones que justificar.
