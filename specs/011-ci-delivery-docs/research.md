# Research: CI y documentación de entrega

Lo marcado como decisión sale de leer el repositorio y de ejecutar pruebas de concepto (escanear
los archivos actuales con el detector del hook, medir `DECISIONES.md`, importar el hook dentro de
pytest, consultar las versiones de las acciones). Lo que depende de GitHub se confirma en la primera
ejecución real (quickstart §6).

## R1 — Forma del workflow

- **Decision**: `.github/workflows/ci.yml` con tres trabajos independientes en `ubuntu-latest`:
  `formato` (`ruff format --check` y `ruff check`), `pruebas` (`uv run pytest`) y `escaneo`
  (`scripts/scan_repo.py`). Disparadores: `pull_request` hacia `main`, `push` a `main` y
  `workflow_dispatch`. `permissions: contents: read`, `concurrency` que cancela la ejecución
  anterior del mismo cambio y `timeout-minutes: 10` por trabajo. Python 3.12 con `astral-sh/setup-uv`
  y `uv sync --group dev --locked` donde hay dependencias que instalar.
- **Rationale**: tres trabajos dan tres estados en el propio cambio (FR-001) y un fallo de formato
  no esconde uno de pruebas; corren en paralelo, así que el total es el del más lento (~1 minuto),
  muy por debajo de los 10 de SC-002. `--locked` falla si `uv.lock` no coincide con `pyproject.toml`,
  que es una divergencia que conviene detectar. Los permisos de solo lectura y la ausencia de secretos
  hacen que un cambio ajeno corra igual (FR-007).
- **Alternatives considered**: un único trabajo con pasos en serie (el primer fallo oculta los
  siguientes y la reejecución cuesta más); matriz con Windows (triplica el tiempo y las pruebas ya
  corren en Windows en local; queda como mejora si el CI revela diferencias); `--frozen` (no detecta
  un `uv.lock` desactualizado); instalar con `pip` (el proyecto se gestiona con `uv`).

## R2 — Acciones fijadas por commit

- **Decision**: fijar cada acción por su SHA de commit con el tag en un comentario:
  `actions/checkout` v7.0.1 (`3d3c42e5aac5ba805825da76410c181273ba90b1`) y `astral-sh/setup-uv`
  v10.3.0 (`1c37ad07a6a961277cf70c0d37d6f313000f5884`). `checkout` con `persist-credentials: false`.
  `setup-uv` con `python-version` y `enable-cache`.
- **Rationale**: un tag es mutable; el SHA no. En un CI que ve todo el código, fijar es la defensa
  barata contra una acción comprometida. Las entradas `python-version` y `enable-cache` existen en
  esa versión de `setup-uv` (comprobado en su `action.yml`).
- **Alternatives considered**: tags de versión mayor (cómodos pero mutables); acciones propias de
  `uv` sin `setup-uv` (reimplementa la instalación y la caché).

## R3 — Reutilizar el detector del hook, con una excepción

- **Decision**: el escáner carga `block_sensitive_data` desde `.claude/hooks/` y llama a
  `find_in_line` y a `MARCADOR`; no copia ninguna expresión regular. Prueba de concepto sobre los
  278 archivos de texto del árbol: **un** hallazgo, en `uv.lock` línea 835, que es un falso positivo
  (la «cc» de la ruta de un hash de descarga seguida de siete dígitos coincide con la etiqueta de
  cédula). `uv.lock` es un archivo generado sin datos humanos, así que se excluye **por nombre**; el
  resto no lleva exclusiones. *Confirmado por el usuario el 2026-10-18, junto con el límite de 1.000
  palabras de R8.*
- **Rationale**: FR-004 pide las mismas reglas que el hook local y una sola fuente evita que el
  CI y el hook discrepen (SC-006). El resultado de la prueba de concepto demuestra que el detector es
  utilizable sobre todo el repositorio sin una lista larga de excepciones. Excluir un archivo
  generado por nombre es más honesto que debilitar el detector o marcar un hash con `dato-ficticio`
  (el marcador es solo para datos de prueba inventados).
- **Alternatives considered**: copiar las expresiones al escáner (diverge en cuanto se toque el
  hook); extraer el detector a un módulo común (obliga a tocar `block_sensitive_data.py`, que está
  empaquetado en el plugin: habría que sincronizar la copia y subir la versión); marcar la línea del
  lock (no se puede editar a mano un archivo que `uv` regenera).

## R4 — El hook no se puede importar dentro de pytest

- **Decision**: el escáner importa el hook de forma diferida (solo cuando va a escanear). Los tests
  de lo puro (credenciales, archivos de entorno, enmascarado, exclusiones, conteo) importan
  `scan_repo` sin cargar el hook; los de extremo a extremo ejecutan el script por subproceso sobre un
  repositorio git temporal con archivos construidos en ejecución.
- **Rationale**: se comprobó que `import block_sensitive_data` dentro de pytest falla con
  `AttributeError` en `_hooklib.py` línea 17: reconfigura `sys.stdin`, que pytest sustituye durante
  la captura. Correr el script como proceso real evita el problema y además prueba lo que ve el CI.
- **Alternatives considered**: hacer tolerante `_hooklib` (toca una pieza empaquetada, ver R3);
  desactivar la captura en esos tests (frágil y oculta fallos); simular el módulo (no prueba el
  detector real).

## R5 — Qué cuenta como archivo de entorno y como credencial

- **Decision**: el escáner mira el conjunto `git ls-files --cached --others --exclude-standard`
  (los versionados más los nuevos aún no ignorados): en CI son lo mismo; en local atrapa un archivo
  nuevo antes de hacer `git add`. Dos comprobaciones propias, además del detector:
  - **Archivos de entorno o de secretos** por nombre de ruta: `.env`, `.env.*`, cualquier ruta que
    pase por una carpeta `secrets`, y extensiones `.pem`, `.key`, `.p12`, `.pfx`.
  - **Credenciales** por forma: clave de la API de Anthropic (`sk-ant-` + 20 o más caracteres),
    tokens de GitHub (`ghp_`, `gho_`, `ghu_`, `ghs_`, `ghr_` + 36 caracteres y `github_pat_` + 22 o
    más), clave de acceso de AWS (`AKIA` + 16) y cabecera de clave privada PEM. El marcador
    `dato-ficticio` **no** exime una credencial.
- **Rationale**: son las credenciales que este proyecto o su entorno pueden manejar (la clave del
  modelo, el `GITHUB_PAT` del flujo de tickets) más las dos más comunes por accidente. Patrones
  específicos con longitud mínima dan pocos falsos positivos; un patrón genérico de «clave = "…"»
  habría marcado fixtures y código legítimo. El marcador no aplica porque ninguna credencial es un
  dato de prueba inventado.
- **Alternatives considered**: patrón genérico `token|secret|password = "…"` (muchos falsos
  positivos; queda como mejora futura si se quiere más cobertura); herramienta externa de escaneo de
  secretos (otra dependencia y otra acción que fijar para cubrir cuatro patrones); solo escanear
  lo versionado (un archivo nuevo sin `git add` pasaría inadvertido en local).

## R6 — Ubicación del escáner y de los tests

- **Decision**: `scripts/scan_repo.py` con tests en `scripts/test_*.py`, y `scripts` añadido a
  `testpaths` de `pyproject.toml`.
- **Rationale**: no es un hook, y en `.claude/hooks/` el test de integridad del plugin (#10) lo
  vería como una pieza de `.claude/` sin clasificar; tampoco es código del agente, así que no va en
  `src/`. Los tests junto al script cumplen el Principio VII. `ruff` ya cubre `scripts/` porque
  formatea todo el repositorio.
- **Alternatives considered**: `.claude/hooks/scan_repo.py` (acopla con el plugin); `src/crediagil/`
  (mezcla herramientas de desarrollo con el paquete que se instala); `tests/` en la raíz (el
  proyecto no usa esa convención).

## R7 — Salida del escáner

- **Decision**: una línea por hallazgo, `archivo:línea: tipo`, con tipos `tarjeta`, `documento`,
  `cuenta`, `archivo_de_entorno` y `credencial`, nunca con el valor; al final un resumen con el número
  de archivos escaneados y de hallazgos. Código de salida 0 sin hallazgos, 1 con hallazgos, 2 si no
  puede ejecutarse (no es un repositorio git, el detector no carga). En CI además emite una anotación
  de GitHub (`::error file=…,line=…::`) para que el hallazgo salga en la línea del cambio.
- **Rationale**: FR-006 y SC-007 prohíben reproducir el dato; el detector ya devuelve el valor, así
  que el escáner lo descarta antes de imprimir. Tres códigos distintos separan «hay un problema en el
  código» de «el escáner no pudo correr».
- **Alternatives considered**: imprimir el valor parcialmente enmascarado (sigue filtrando parte del
  dato); salida JSON (nadie la consume todavía).

## R8 — Qué se mide en `DECISIONES.md` y en el README

- **Decision**: límite de **1.000 palabras** (`re.findall(r"\w+", texto)`, que cuenta acentos pero
  no los símbolos de las tablas) como equivalente de dos páginas. El texto actual tiene unas
  1.160: hay que recortar unas 160. `DECISIONES.md` debe seguir teniendo las 11 necesidades del
  ecosistema (filas numeradas de la tabla), cada una con mecanismo y motivo no vacíos, y no repetir la
  tasa ni los umbrales. El README debe conservar el enlace al Project, el del video y los comandos
  `uv sync --group dev`, `uv run pytest` y `uv run python -m crediagil.chat`.
- **Rationale**: dos páginas no se pueden medir, mil palabras sí; el test evita que el documento
  vuelva a crecer sin que nadie lo note. Contar `\w+` no penaliza las barras de las tablas. Un test
  del README evita que un enlace o un comando obligatorio desaparezca en una edición.
- **Alternatives considered**: contar líneas (una tabla con celdas largas engaña); contar caracteres
  (menos legible); no comprobar nada (el límite se rompe en silencio).

## R9 — Los 5 minutos del README

- **Decision**: el README ya trae los pasos; se ajusta la URL real del repositorio en el `git clone`,
  se añade la insignia del CI y el comando del escaneo, y se **mide** el tiempo desde un clon limpio
  (clonar, `uv sync --group dev`, `uv run pytest`, abrir la interfaz) para anotarlo en el quickstart.
- **Rationale**: SC-003 es una afirmación; un tiempo medido es evidencia. Las pruebas tardan unos
  35 s, así que lo que domina es la descarga de dependencias, que depende de la red y de la caché de
  `uv`.
- **Alternatives considered**: automatizar la medición en el CI (no representa a una persona con una
  máquina nueva).

## R10 — Historial y protección de rama

- **Decision**: la revisión del historial en busca de credenciales se hace una vez, al cerrar la
  feature, con un script temporal que aplica las mismas comprobaciones de credenciales a las líneas
  añadidas de todo el historial y a los nombres de archivo; no se versiona ni corre en CI. Exigir que
  `formato`, `pruebas` y `escaneo` pasen antes de fusionar es un ajuste de GitHub (protección de la
  rama `main`), fuera de alcance, y se documenta en el quickstart.
- **Rationale**: el árbol actual se vigila en cada ejecución; el historial no cambia salvo
  reescritura. Una revisión única cubre el riesgo sin añadir una comprobación lenta y permanente.
- **Alternatives considered**: modo `--historial` permanente en el escáner (más código y tests para
  una comprobación que se hace una vez).

## Fuera de alcance (trabajo futuro, no bloqueante)

- Matriz de sistemas operativos en el CI (Windows y macOS).
- Patrón genérico de credenciales y escaneo de secretos con herramienta externa.
- Protección de la rama `main` exigiendo los tres trabajos.
- Pruebas con el modelo real en un trabajo manual con clave de entorno protegido.
