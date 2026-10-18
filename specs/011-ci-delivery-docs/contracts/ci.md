# Contrato: workflow de CI

`.github/workflows/ci.yml`. Lo que debe cumplir y lo que `scripts/test_ci.py` comprueba leyendo el
archivo como texto (el proyecto no depende de una biblioteca de YAML).

## Disparadores

| Evento | Condición |
|---|---|
| `pull_request` | ramas base: `main` |
| `push` | ramas: `main` |
| `workflow_dispatch` | sin entradas |

## Permisos y ejecución

- `permissions: contents: read` a nivel del workflow; ningún trabajo lo amplía.
- `concurrency` con grupo por workflow y rama y `cancel-in-progress: true`.
- Cada trabajo: `runs-on: ubuntu-latest`, `timeout-minutes: 10`.
- **Sin secretos**: el archivo no contiene `secrets.` ni `ANTHROPIC` ni `GITHUB_PAT` (FR-007).
- Las pruebas con el modelo real no se ejecutan: ningún comando pasa `-m live` ni `--live`.

## Acciones (fijadas por commit)

| Acción | Versión | Commit | Uso |
|---|---|---|---|
| `actions/checkout` | v7.0.1 | `3d3c42e5aac5ba805825da76410c181273ba90b1` | `persist-credentials: false` |
| `astral-sh/setup-uv` | v10.3.0 | `1c37ad07a6a961277cf70c0d37d6f313000f5884` | `python-version: "3.12"`, `enable-cache: true` |

Toda línea `uses:` lleva un SHA de 40 caracteres hexadecimales y, en el mismo renglón, un comentario
con la versión.

## Trabajos

| Trabajo | Pasos tras `checkout` y `setup-uv` | Falla si |
|---|---|---|
| `formato` | `uv sync --group dev --locked`; `uv run ruff format --check`; `uv run ruff check` | el formato no cumple, hay avisos de análisis estático o `uv.lock` no coincide con `pyproject.toml` |
| `pruebas` | `uv sync --group dev --locked`; `uv run pytest` | una prueba falla (las `live` quedan excluidas por la configuración del proyecto) |
| `escaneo` | `uv run --no-project python scripts/scan_repo.py --github` | el escáner devuelve 1 (hallazgos) o 2 (no pudo ejecutarse) |

Los tres son independientes (ninguno declara `needs`) y se ejecutan en paralelo.

## Comprobaciones del test del workflow (`scripts/test_ci.py`)

| # | Condición |
|---|---|
| 1 | existen los disparadores `pull_request` y `push` para `main`, y `workflow_dispatch` |
| 2 | hay exactamente los tres trabajos `formato`, `pruebas` y `escaneo` y ninguno usa `needs` |
| 3 | `permissions` de solo lectura y cada trabajo con `timeout-minutes` ≤ 10 |
| 4 | toda `uses:` lleva un SHA de 40 hexadecimales y un comentario de versión |
| 5 | aparecen los comandos exactos de la tabla de trabajos |
| 6 | no aparece `secrets.`, `ANTHROPIC`, `GITHUB_PAT` ni `-m live` |
| 7 | el workflow no repite la tasa ni los umbrales de la política |

Controles negativos con el texto del workflow alterado en memoria: quitar un trabajo, cambiar un SHA
por un tag, añadir una referencia a un secreto y subir un tiempo máximo deben hacer fallar la
comprobación correspondiente.
