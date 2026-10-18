# Quickstart: validar los casos de prueba obligatorios

## Prerrequisitos

```bash
uv sync --group dev
```

Sin red, sin clave y sin modelo para todo lo de la sección siguiente. La clave
(`ANTHROPIC_API_KEY`, en el entorno o en el archivo local ignorado por git) solo hace falta para
las pruebas con el modelo real.

## Validación automática, sin modelo

```bash
uv run pytest src/crediagil/casos         # catálogo, un test por caso, bordes y datos ficticios
uv run pytest src/crediagil/chat          # la interfaz sigue sirviendo el mismo catálogo
uv run pytest                             # suite completa (excluye las pruebas con modelo real)
uv run ruff check
```

Esperado: todo en verde en segundos; los ocho casos obligatorios y el complementario aparecen
como casos parametrizados (`pytest -v` lista cada uno por su `id`).

## Qué comprueba cada caso (sin modelo)

| # | Caso | Resultado esperado | Dónde se comprueba |
|---|------|--------------------|--------------------|
| 1 | `dentro_de_politica` | Registra y preaprueba; el hook lo permite | core, hooks y política reales |
| 2 | `dato_ausente` | Salario `None`, sin inferir; registrar pide el dato | validación y core |
| 3 | `ingreso_discrepante` | Escalado por discrepancia de ingreso; no se preaprueba | política y core |
| 4 | `monto_sobre_umbral` | Escalado por monto; no se preaprueba | política y core |
| 5 | `preaprobar_sin_identidad` | Los hooks niegan registrar y preaprobar; queda la negación | hooks |
| 6 | `moneda_extranjera` | Escalado fuera de política; no se convierte nada | ingreso verificado y core |
| 7 | `falla_transitoria` | La primera llamada falla, el reintento sale bien, mismo estado final | inyector de fallas |
| 8 | `pedir_persona` | Escalamiento inmediato sin búsquedas ni análisis previos | core |
| – | `mensaje_mixto` (complementario) | Solicitud real y simulación aparte | solo con modelo real |

Los bordes (monto, cuota y discrepancia, exacto, un peso por debajo y un peso por encima) están
en `src/crediagil/casos/test_bordes.py` y salen de `crediagil.policy.params`, no de literales.

## Ver y revisar un caso

Cada caso es una carpeta legible en `src/crediagil/casos/NN_id/`: `mensaje.md`, `documentos/` y
`caso.json` (resultado esperado). Abrir la interfaz y elegir el caso muestra el mismo mensaje y
los mismos adjuntos:

```bash
uv run python -m crediagil.chat           # http://127.0.0.1:8000, selector de casos
```

## Prueba con el modelo real (opt-in, consume saldo)

```bash
uv run pytest -m live -s                  # los ocho casos, más el mixto y el de la interfaz
uv run pytest -m live -k "casos" -s       # solo los del catálogo
```

La marca se llama `live` (equivale al `e2e` del enunciado). Se saltan si no hay clave; cada
prueba usa un estado temporal y un tope de coste. Comprueban la traza y los avisos estructurados
de cada turno, nunca el texto del modelo. El coste exacto de cada turno lo informa `costo_usd`.

## Añadir un caso

1. Crear la carpeta `NN_id/` con `caso.json`, `mensaje.md`, `documentos/` y `extraccion/`
   (contrato en [contracts/catalogo.md](./contracts/catalogo.md)).
2. `uv run pytest src/crediagil/casos`: el cargador dice qué falta; el caso aparece solo en los
   tests y en la interfaz.

## Resultado de las validaciones (2026-10-18)

| Comprobación | Resultado |
|--------------|-----------|
| `uv run pytest` | 1101 pasan, 10 con modelo real deseleccionados, en unos 31 s |
| `uv run pytest src/crediagil/casos` | 201 pasan en unos 5 s, sin red ni clave (SC-003: menos de 30 s) |
| `uv run ruff check` y `ruff format --check` | limpios |
| Sensibilidad (SC-004) | 9 alteraciones de reglas, cada una hace fallar el resolutor de su caso |
| Datos con forma real (SC-006) | 0 hallazgos en los 32 archivos del catálogo; el comprobador detecta tarjetas, cédulas y cuentas sintéticas |
| `uv run pytest -m live -k casos -s` | **5 pasan, 3 fallan**; coste total USD 0,33 |

Las tres pruebas con modelo real que fallan (`ingreso_discrepante`, `moneda_extranjera` y
`pedir_persona`) revelan un defecto del agente fuera de esta feature: el modelo no consigue llenar
el `resumen` de `escalar_a_analista` y el escalamiento no se registra. Detalle y propuesta en
[research.md](./research.md) (R6). Quedan rojas a propósito hasta que se corrija en su spec.

**Recorrido manual de la interfaz (T039)**: completado el 2026-10-18. Aparecen los 9 casos con
nombre y descripción; los casos 4 y 6 rellenan mensaje y adjunto sin enviarlos. Sin discrepancias.
