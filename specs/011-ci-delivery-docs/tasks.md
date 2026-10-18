# Tasks: CI y documentación de entrega

**Input**: Design documents from `specs/011-ci-delivery-docs/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/ci.md](./contracts/ci.md),
[contracts/escaneo.md](./contracts/escaneo.md), [quickstart.md](./quickstart.md)

**Tests**: obligatorios (FR-008, FR-013, Principio VII). El código nuevo es el escáner
(`scripts/scan_repo.py`); el resto son configuración (el workflow) y documentación, vigiladas por
tests. Ninguno usa modelo, red ni clave.

**Sin cambios de reglas** (FR-015): no se toca `src/`, la política, el core, los hooks ni los
prompts. Tampoco `.claude/hooks/_hooklib.py` ni ninguna pieza empaquetada en el plugin de #10:
cambiarla obligaría a sincronizar su copia y subir la versión (research.md R3).

**Datos ficticios**: los tests construyen en ejecución la tarjeta (función local que genera un
número válido por Luhn con un prefijo ficticio), la cédula (`"cédula: " + "1" * 10`), la cuenta
(`"cuenta de ahorros " + "2" * 11`) y las credenciales (prefijo + caracteres repetidos); ningún
literal con esa forma queda en el código. Los valores de la política se obtienen de
`crediagil.policy.params`, nunca como literales.

**Hooks que pueden saltar al escribir**: `block_sensitive_data` revisa cada escritura (usar los
patrones anteriores o el marcador `dato-ficticio` en la misma línea solo si es deliberadamente
ficticio) y `block_secret_access` bloquea cualquier comando de Bash que mencione los archivos de
entorno o la carpeta de secretos (no mencionarlos en comandos; usar las herramientas de Read, Edit y
Glob o un script en el directorio temporal).

**Nombres de módulos de apoyo**: en `scripts/` no hay `__init__.py`. El módulo de apoyo de los tests
se llama `prueba_comun.py`, **no** `conftest.py`: `from conftest import …` resolvería el `conftest` de
`.claude/hooks/` que pytest ya cargó.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: paralelizable (archivo distinto, sin dependencias pendientes)
- **[Story]**: historia de spec.md (US1–US4)
- Rutas relativas a la raíz del repositorio.

---

## Phase 1: Setup

- [X] T001 Línea base y rama: ejecutar `git branch --show-current`; si es `feature/010-reusable-plugin` (donde se escribieron la spec y el plan), **parar y pedir al usuario** crear una rama propia de #11 (plan.md "Notas"): no se crea ni se hace commit sin su confirmación. Con la rama decidida, `uv run pytest -q` y `uv run ruff check` en verde, y confirmar que existen `.gitignore` con las exclusiones de los archivos de entorno y de la carpeta de secretos, y que no existe `.github/`.
- [X] T002 Añadir `scripts` a `testpaths` en `pyproject.toml` (`[".claude/hooks", "src", "scripts"]`); no cambiar nada más. Crear `scripts/prueba_comun.py` (docstring de una línea) con las utilidades de los tests: `RAIZ` (raíz del repositorio desde `Path(__file__)`), `tarjeta_ficticia()` (número de 16 dígitos válido por Luhn con prefijo ficticio, construido en ejecución, nunca literal) y `parametros_de_la_politica()` (formatos de `crediagil.policy.params.MONTO_MAXIMO_PREAPROBACION` en pesos con punto, coma y sin separador, y de `TASA_MENSUAL`, `PROPORCION_MAXIMA_CUOTA_INGRESO` y `DISCREPANCIA_MAXIMA_INGRESO` en porcentaje con y sin espacio, con punto y con coma decimal). Confirmar con `uv run pytest -q` que no rompe nada.

---

## Phase 2: Foundational (bloquea US1–US4): el escáner base

**Purpose**: el escáner de datos con forma real, con listado de archivos, informe, códigos de salida
y las dos opciones. US1 lo ejecuta en el CI y US2 le añade archivos de entorno y credenciales.

- [X] T003 Tests, que deben fallar, en `scripts/test_scan_repo.py` (contracts/escaneo.md casos 1, 2, 3, 9, 10, 11 (para datos), 12, 13 y 14): fixture `repo_git(tmp_path)` que ejecuta `git init`, configura usuario y correo ficticios y devuelve un ayudante `anadir(nombre, contenido)` que escribe el archivo en el repositorio temporal (sin `git add`), y una función `ejecutar(raiz, *opciones)` que lanza `scripts/scan_repo.py --raiz <raiz>` con `sys.executable` por subproceso y devuelve código de salida, stdout y stderr. Casos, con los datos construidos en ejecución: repositorio limpio → salida 0 y `0 hallazgos`; tarjeta válida por Luhn, cédula con etiqueta y cuenta con etiqueta, cada una en su archivo → salida 1 con `archivo:línea: tipo` correcto (`tarjeta`, `documento`, `cuenta`) y la línea exacta; las mismas líneas con `dato-ficticio` → salida 0; `uv.lock` con una línea que el detector marcaría → se ignora, y el mismo contenido en otro archivo → falla; archivo binario (con un byte nulo) → se omite sin error; el informe y `--github` no contienen el valor detectado ni una subcadena de 6 caracteres seguidos de él; `--github` emite una línea `::error file=…,line=…::` por hallazgo; directorio que no es repositorio git → salida 2; archivo nuevo sin `git add` → se escanea, y si el `.gitignore` del repositorio temporal lo ignora → no.
- [X] T004 Implementar `scripts/scan_repo.py` (solo biblioteca estándar, ~150 líneas con US2): `Hallazgo` (dataclass inmutable con `archivo`, `linea`, `tipo`); `EXCLUIDOS = {"uv.lock": "archivo generado: las rutas de descarga con hashes coinciden con la etiqueta de cédula"}`; `listar_archivos(raiz)` con `git ls-files -z --cached --others --exclude-standard` (lanza un error propio si no hay git o no es un repositorio); lectura como UTF-8 con sustitución de bytes inválidos y omisión de binarios (byte nulo) y de archivos ilegibles; `cargar_detector()` **diferido** que importa `block_sensitive_data` desde `.claude/hooks/` **del repositorio que contiene el script** (no de `--raiz`, que en los tests es un repositorio temporal sin hooks) y devuelve `find_in_line` y `MARCADOR`; salta cualquier línea con el marcador para los tipos `tarjeta`, `documento` y `cuenta`; descarta el valor que devuelve el detector antes de crear el `Hallazgo`; informe ordenado por archivo y línea con el resumen de archivos escaneados y hallazgos; opción `--github` con la anotación `::error file=…,line=…::` (sin el valor); opción `--raiz`; códigos de salida 0, 1 y 2 de contracts/escaneo.md. Hacer pasar T003.

**Checkpoint**: el escáner detecta tarjeta, cédula y cuenta, informa archivo y línea sin el valor y funciona sobre un repositorio temporal.

---

## Phase 3: User Story 1 - Cada cambio se verifica automáticamente (Priority: P1) 🎯 MVP

**Goal**: un workflow de GitHub que ejecuta formato, pruebas y escaneo en cada cambio hacia `main`.

**Independent Test**: `uv run pytest scripts/test_ci.py` y, con el usuario, la ejecución real en GitHub
(T023).

### Tests para US1

- [X] T005 [P] [US1] Tests, que deben fallar, en `scripts/test_ci.py` (contracts/ci.md "Comprobaciones", filas 1–7): leer `.github/workflows/ci.yml` como texto (el proyecto no usa una biblioteca de YAML) y comprobar los disparadores `pull_request` y `push` para `main` y `workflow_dispatch`; los tres trabajos `formato`, `pruebas` y `escaneo` y ninguno con `needs`; `permissions` de solo lectura (`contents: read`) y `timeout-minutes` ≤ 10 en cada trabajo; toda línea `uses:` con un SHA de 40 hexadecimales y un comentario de versión en el mismo renglón; los comandos exactos `uv sync --group dev --locked`, `uv run ruff format --check`, `uv run ruff check`, `uv run pytest` y `uv run --no-project python scripts/scan_repo.py --github`; que no aparecen `secrets.`, `ANTHROPIC`, `GITHUB_PAT` ni `-m live`; y que el texto no repite la tasa ni los umbrales (`parametros_de_la_politica()`). Controles negativos sobre el texto alterado en memoria: quitar un trabajo, cambiar un SHA por un tag, añadir `secrets.X` y subir un `timeout-minutes` a 11 deben fallar cada uno su comprobación (escribir cada comprobación como función que recibe el texto, para poder probarla con textos alterados).

### Implementación para US1

- [X] T006 [US1] Crear `.github/workflows/ci.yml` con el contrato de contracts/ci.md: nombre `CI`; disparadores `pull_request` (ramas `main`), `push` (ramas `main`) y `workflow_dispatch`; `permissions: contents: read`; `concurrency` con grupo por workflow y rama y `cancel-in-progress: true`; tres trabajos independientes en `ubuntu-latest` con `timeout-minutes: 10`. Cada uno usa `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1` con `persist-credentials: false` y `astral-sh/setup-uv@1c37ad07a6a961277cf70c0d37d6f313000f5884 # v10.3.0` con `python-version: "3.12"` y `enable-cache: true`. `formato`: `uv sync --group dev --locked`, `uv run ruff format --check`, `uv run ruff check`. `pruebas`: `uv sync --group dev --locked`, `uv run pytest`. `escaneo`: `uv run --no-project python scripts/scan_repo.py --github`. Ningún secreto, ninguna variable de entorno de la clave del modelo.
- [X] T007 [US1] Hacer pasar T005. Validar la sintaxis del YAML una vez con `uv run --with pyyaml python -c "import yaml, pathlib; yaml.safe_load(pathlib.Path('.github/workflows/ci.yml').read_text(encoding='utf-8'))"` (no se añade PyYAML al proyecto) y comprobar que los SHA siguen correspondiendo a esos tags: `gh api repos/actions/checkout/git/ref/tags/v7.0.1` y `gh api repos/astral-sh/setup-uv/git/ref/tags/v10.3.0`.
- [X] T008 [US1] Ensayo local de los tres trabajos con los mismos comandos que el workflow, en este orden y sin tocar nada: `uv sync --group dev --locked`, `uv run ruff format --check`, `uv run ruff check`, `uv run pytest` y `uv run --no-project python scripts/scan_repo.py`. Anotar la duración de cada uno (alimenta SC-002). Si el escaneo informa algún hallazgo en archivos que no son `uv.lock`, **parar**: es un falso positivo o un dato real; no se debilita el detector ni se añade una exclusión sin documentarlo en research.md R3 y avisar al usuario.

**Checkpoint**: el workflow existe, cumple su contrato y sus tres comandos pasan en local.

---

## Phase 4: User Story 2 - Ningún archivo de entorno ni credencial en el repositorio (Priority: P1)

**Goal**: el escáner también falla si hay un archivo de entorno o de secretos versionado o una cadena
con forma de credencial, y el repositorio actual está limpio.

**Independent Test**: `uv run pytest scripts/test_scan_repo.py scripts/test_repositorio.py` y
`uv run --no-project python scripts/scan_repo.py` sobre el repositorio real.

### Tests para US2 (deben fallar hasta T010)

- [X] T009 [US2] Ampliar `scripts/test_scan_repo.py` (contracts/escaneo.md casos 4–8 y 11, data-model.md "Credenciales reconocidas" y "Archivos de entorno"):
  - **Puras**, sin subproceso, con `import scan_repo` (el detector no se carga): `es_archivo_de_entorno(ruta)` es verdadero para nombre `.env` o que empieza por `.env.` (`.env`, `config/.env.local`), para una ruta con una carpeta `secrets` (`secrets/clave.txt`) y para extensión `.pem`, `.key`, `.p12` o `.pfx`; falso para `environment.md`, `env.py`, `docs/secretos.md` y `monkey.py`. `buscar_credenciales(linea)` con prefijo + caracteres repetidos construidos en ejecución: `sk-ant-` con 20 caracteres tras el prefijo **sí** y con 19 **no**; `ghp_` con exactamente 36 **sí** y con 35 **no** (y con 37 **no** como token completo exacto, para fijar el borde: `exactamente 36 tras el prefijo`); `github_pat_` con 22 **sí** y con 21 **no**; `AKIA` con 16 **sí** y con 15 **no**; cabecera de clave privada PEM construida en ejecución **sí**; un texto sin credencial **no**.
  - **Extremo a extremo** sobre `repo_git`: un archivo `.env` y otro `secrets/clave.txt` → salida 1, tipo `archivo_de_entorno`, línea `0`; los nombres parecidos del caso 5 → salida 0; una credencial en una línea con `dato-ficticio` **sigue siendo hallazgo** (`credencial`); ninguno de los informes (incluido `--github`) contiene el valor ni una subcadena de 6 caracteres seguidos de él.
- [X] T010 [P] [US2] Crear `scripts/test_repositorio.py`: (a) `.gitignore` contiene las exclusiones de los archivos de entorno (`.env` y `.env.*`) y de la carpeta `secrets/` (FR-014); (b) ejecutar `scan_repo.py` por subproceso sobre el propio repositorio (`RAIZ`) devuelve salida 0 (contracts/escaneo.md caso 15; SC-005); (c) ningún archivo versionado (`git ls-files`) pasa `es_archivo_de_entorno`. Debe fallar hasta que T011 integre las comprobaciones si el árbol tuviera algo; si ya está limpio, documentar en la salida del test que pasa por el árbol limpio.

### Implementación para US2

- [X] T011 [US2] En `scripts/scan_repo.py` añadir `es_archivo_de_entorno(ruta)` y `buscar_credenciales(linea)` con las formas de data-model.md ("Credenciales reconocidas": Anthropic `sk-ant-` + letras, dígitos, `_` o `-`, **20 o más**; GitHub clásico `ghp_`/`gho_`/`ghu_`/`ghs_`/`ghr_` + alfanuméricos, **exactamente 36**; GitHub de granularidad fina `github_pat_` + alfanuméricos y `_`, **22 o más**; AWS `AKIA` + mayúsculas y dígitos, **exactamente 16**; cabecera `-----BEGIN … PRIVATE KEY-----`) e integrarlas en el escaneo: un archivo de entorno produce un `Hallazgo` `archivo_de_entorno` con línea `0` y no se lee su contenido; una credencial produce `credencial` **aunque la línea lleve `dato-ficticio`**. Comprobar que el propio código fuente del escáner no coincide con sus patrones (los patrones se escriben como expresiones, no como cadenas con forma de credencial). Hacer pasar T009 y T010.
- [X] T012 [US2] Ejecutar `uv run --no-project python scripts/scan_repo.py` sobre el repositorio real y comprobar salida 0 y `0 hallazgos` (quickstart §1). Si aparece un hallazgo: no lo marques con `dato-ficticio` ni debilites el patrón; si es un archivo generado, documéntalo en research.md R3 y en `EXCLUIDOS`; si es un dato o credencial reales, avisa al usuario y no sigas.

**Checkpoint**: el escáner completo pasa sobre el repositorio y falla con los controles negativos.

---

## Phase 5: User Story 3 - Una persona nueva lo ejecuta en menos de 5 minutos (Priority: P2)

**Goal**: el README permite instalar, probar y abrir la interfaz en menos de 5 minutos, con los dos
enlaces y los comandos de la verificación.

**Independent Test**: `uv run pytest scripts/test_entrega.py -k Readme` y la medición de T015.

- [X] T013 [US3] Tests, que deben fallar, en `scripts/test_entrega.py`, clase `TestReadme` (FR-010, FR-011, FR-013): el README contiene el enlace al Project (`https://github.com/users/danielpvsofka/projects/1`) y un enlace de video no vacío (`https://youtu.be/` seguido de al menos un carácter); los comandos `uv sync --group dev`, `uv run pytest` y `uv run python -m crediagil.chat`; el requisito `ANTHROPIC_API_KEY` y la mención de que no se versiona; la URL real del clon (`https://github.com/danielpvsofka/crediagil.git`) y **no** el marcador `<repo>`; la insignia del workflow (`actions/workflows/ci.yml`); los comandos de la verificación (`uv run ruff format --check` y `uv run --no-project python scripts/scan_repo.py`); y que no repite la tasa ni los umbrales (`parametros_de_la_politica()`). Controles negativos sobre el texto alterado en memoria: quitar el enlace del video, vaciarlo (`https://youtu.be/`) y quitar un comando obligatorio deben fallar.
- [X] T014 [P] [US3] Ajustar `README.md`: sustituir `git clone <repo> && cd <repo>` por la URL real del clon; añadir bajo el título la insignia del CI (enlace a `.github/workflows/ci.yml`); en "Correr en menos de 5 minutos" añadir, tras las pruebas, una línea con los comandos de la verificación local (`uv run ruff format --check`, `uv run ruff check` y `uv run --no-project python scripts/scan_repo.py`) y una subsección breve "Verificación automática" que diga qué ejecuta el CI (formato, pruebas deterministas y escaneo de datos y credenciales), que no usa secretos ni consume saldo y que exigir los tres trabajos antes de fusionar es un ajuste de GitHub; actualizar la fila de #11 de la tabla "Estado". Mantener los dos enlaces. Hacer pasar T013.
- [X] T015 [US3] Medir los 5 minutos (SC-003) desde un clon limpio en un directorio temporal fuera del repositorio: `git clone` de la rama de trabajo, `uv sync --group dev`, `uv run pytest`, y arrancar `uv run python -m crediagil.chat` en segundo plano para comprobar que responde en `http://127.0.0.1:8000/api/casos` y detenerlo. Anotar el tiempo de cada paso y el total en `quickstart.md` ("Resultado de las validaciones"); si supera 5 minutos, anotar qué domina (descarga de dependencias, pruebas) en lugar de ocultarlo. No imprimir ni escribir ninguna clave.

**Checkpoint**: el README lleva todo lo exigido y su tiempo está medido.

---

## Phase 6: User Story 4 - Las decisiones se justifican en dos páginas (Priority: P2)

**Goal**: `DECISIONES.md` cabe en 1.000 palabras con las 11 necesidades, cada una con su mecanismo y su motivo.

**Independent Test**: `uv run pytest scripts/test_entrega.py -k Decisiones`.

- [X] T016 [US4] Tests, que deben fallar, en `scripts/test_entrega.py`, clase `TestDecisiones` (FR-012, FR-013; data-model.md "Límites de la documentación de entrega"): `contar_palabras(texto)` = `len(re.findall(r"\w+", texto))` probada con textos construidos de **exactamente 1.000** palabras (pasa) y de **1.001** (falla) para fijar el borde; `DECISIONES.md` ≤ 1.000 palabras; las filas numeradas de la tabla de necesidades son exactamente las 11 (`1` a `11`), cada una con al menos 4 celdas con contenido (número, necesidad, mecanismo, motivo); no repite la tasa ni los umbrales (`parametros_de_la_politica()`); y no presenta como pendientes el CI ni el plugin (no aparece `pendiente` junto a `#10` ni a `#11`). Control negativo sobre el texto alterado: duplicar el documento supera el límite y quitar una fila deja de cubrir las 11.
- [X] T017 [P] [US4] Recortar `DECISIONES.md` de unas 1.160 palabras a **como máximo 1.000** sin perder ninguna de las 11 necesidades ni cambiar el sentido de las decisiones: acortar las celdas de la tabla (mecanismo y motivo en una frase cada uno, quitando repeticiones entre las filas 4–9), condensar la sección "Agente" (una línea por decisión; mantener ingreso verificado, interfaz, claves, aislamiento y casos de prueba) y dejar el criterio general al inicio. Actualizar la fila 5 (el CI ya existe: `scripts/scan_repo.py` en un workflow, con el mismo detector que el hook) y la fila 11 (el plugin ya está entregado; el CI no figura como pendiente). Medir con la función de T016 y hacer pasar T016. No tocar el criterio general ni la nota de memoria y de MCP salvo para recortarlos.

**Checkpoint**: las decisiones caben en el límite y reflejan el estado actual.

---

## Phase 7: Polish y validación

- [X] T018 [P] Actualizar `CLAUDE.md`: en "Stack y comandos", el CI (`.github/workflows/ci.yml`: tres trabajos, sin secretos, acciones fijadas por commit), el escaneo local (`uv run --no-project python scripts/scan_repo.py`, que reutiliza el detector del hook, ignora `uv.lock` y falla con 1 si hay hallazgos, 2 si no puede ejecutarse), que los tests de `scripts/` entran en `uv run pytest` y que el hook no se puede importar dentro de pytest (se prueba por subproceso). Sin repetir tasa ni umbrales y sin mencionar los archivos de entorno en comandos de ejemplo.
- [X] T019 Ejecutar `uv run ruff check`, `uv run ruff format --check` y `uv run pytest` completos; confirmar que la suite de #9, #10 y las demás sigue en verde (FR-015) y que el test de integridad del plugin (`.claude/hooks/test_plugin_devkit.py`) no se ve afectado (el escáner está en `scripts/`, no en `.claude/`). Buscar la tasa y los umbrales como literales en `scripts/`, `.github/`, `README.md` y `DECISIONES.md`: no debe haber ninguno.
- [X] T020 Revisión única del historial (quickstart §7; research.md R10), con un script temporal en el directorio temporal de la sesión, **no versionado**: aplicar `buscar_credenciales` (importando `scan_repo`) a las líneas añadidas de `git log --all -p` y `es_archivo_de_entorno` a todos los nombres de archivo que alguna vez existieron (`git log --all --name-only --pretty=format:`). No mencionar los archivos de entorno en la línea de comandos. Anotar el resultado en `quickstart.md`; si hay un hallazgo real, avisar al usuario sin reproducir el valor.
- [X] T021 Medir y anotar en `quickstart.md` "Resultado de las validaciones": `uv run pytest` completo (número de tests y duración), `uv run pytest scripts` (número y duración), la duración de cada comando del ensayo de T008 y del escaneo (SC-002, SC-005), el tiempo de T015 (SC-003), el número de palabras de `DECISIONES.md` (SC-004) y el resultado de T020. Marcar en este archivo las tareas completadas.
- [X] T022 Revisar con el usuario las dos decisiones que hoy son suposición (spec.md "Assumptions"): que dos páginas equivalen a 1.000 palabras y que `uv.lock` se excluye por nombre. Anotar su respuesta en spec.md y research.md.
- [ ] T023 Ejecución real en GitHub (quickstart §6), **con confirmación explícita del usuario** antes de cada push y de abrir PR de prueba: publicar una rama con un cambio limpio y abrir un PR hacia `main`: los tres trabajos deben pasar en menos de 10 minutos; luego, en una rama de prueba, un archivo sin formato, una prueba rota y una línea con una tarjeta generada en ejecución deben fallar cada uno **en su** trabajo, y el del escaneo mostrar la anotación en la línea sin el número. Cerrar los PR de prueba sin fusionar. Anotar el enlace de cada ejecución y cualquier diferencia entre Linux y Windows en `quickstart.md`; si el CI revela un fallo propio de Linux, corregirlo en el workflow o el test, no desactivar la comprobación.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (T001–T002)**: sin dependencias; T001 puede detener el flujo hasta que el usuario elija la rama.
- **Foundational (T003–T004)**: depende de T002; **bloquea US1–US4** (el workflow, el README y los tests de la entrega referencian el escáner).
- **US1 (T005–T008)**: depende de T004. T005 es paralelizable con T009–T010; T006 → T007 → T008. T008 usa el escáner completo si US2 ya está; si no, solo el de datos.
- **US2 (T009–T012)**: depende de T004. T009 en el mismo archivo que T003, así que va después de T004; T010 es paralelizable (archivo distinto); T011 depende de T009–T010; T012 al final.
- **US3 (T013–T015)**: depende de T004 y de T008 (los comandos que cita el README deben funcionar); T014 es paralelizable con T017 (archivo distinto).
- **US4 (T016–T017)**: independiente del escáner; T016 comparte `scripts/test_entrega.py` con T013, por lo que van en orden.
- **Polish (T018–T023)**: depende de las historias entregadas; T021 al final de las automáticas; T022 y T023 con el usuario.

### Parallel Opportunities

- T005 (test del workflow) mientras se escribe T009–T010.
- T010 (test del repositorio) en paralelo con T009 una vez hecho T004.
- T014 (README) y T017 (`DECISIONES.md`) en paralelo tras sus tests.
- T018 (`CLAUDE.md`) en paralelo con T019.

### Parallel Example: tras el escáner base

```bash
# Con T004 hecho, a la vez (archivos distintos):
Task: "Tests del workflow en scripts/test_ci.py (T005)"
Task: "Tests del repositorio en scripts/test_repositorio.py (T010)"
```

---

## Implementation Strategy

### MVP primero (US1 + US2)

1. Setup y Foundational (el escáner base).
2. US1: workflow y su test.
3. US2: archivos de entorno y credenciales, y el repositorio limpio.
4. **Parar y validar**: `uv run pytest` y el escaneo sobre el repositorio real; el CI en GitHub con el usuario (T023).
5. Con eso se cumplen el primer y el cuarto criterios del issue; la documentación cierra los otros dos.

### Entrega incremental

1. + US3: README ajustado y medido.
2. + US4: `DECISIONES.md` recortado y vigilado.
3. Documentación, historial, medición final y ejecución real en GitHub.

---

## Notes

- [P] = archivo distinto y sin dependencias pendientes.
- Verificar que los tests fallan antes de implementar (T003, T005, T009, T013, T016).
- No hacer commit ni push sin confirmación explícita del usuario.
- El detector del hook no se importa dentro de pytest (research.md R4): lo ejecutable de extremo a extremo se prueba por subproceso.
- El marcador `dato-ficticio` exime datos con forma real pero **no** credenciales.
- Un hallazgo real en el repositorio no se "arregla" con el marcador ni debilitando un patrón: se informa al usuario.
- El comando de actualizar protección de rama en GitHub queda fuera de alcance (ajuste manual).
