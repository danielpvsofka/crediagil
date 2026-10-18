# Implementation Plan: Interfaz de chat

**Branch**: `develop` (feature dir `008-chat-interface`) | **Date**: 2026-10-18 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/008-chat-interface/spec.md` — Issue [#8](https://github.com/danielpvsofka/crediagil/issues/8)

## Summary

Una aplicación web local, `crediagil.chat`, para conversar con el agente de #7. Un único proceso
Python sirve una página estática y una API JSON pequeña con Starlette y uvicorn.

- **Hilo y continuidad**: la sesión guarda un único `Agente` abierto entre peticiones (verificado
  que funciona aunque cada petición corra en una tarea distinta) y un turno a la vez.
- **Adjuntos**: el navegador envía los archivos en base64; el servidor valida (`.txt` o `.md`,
  hasta 100 KiB, hasta 5, UTF-8, no vacíos) y decide.
- **Avisos**: se pintan solo los que trae el `ResultadoTurno` (preaprobado, información solicitada,
  escalamiento, bloqueo por regla), cada uno con rótulo e icono además de color. El texto de la
  respuesta no genera avisos.
- **Detalle técnico**: un `<details>` nativo, cerrado por defecto, con herramientas, entradas,
  salidas, razón de parada y coste de cada turno.
- **Operación de la demostración**: catálogo de casos servido por la API, falla transitoria
  simulada (la pasa a una conversación nueva por `ConfigAgente.entorno_core`) y reinicio de datos
  con confirmación (`AlmacenEstado.reiniciar`, nuevo).
- **Seguridad del contenido**: todo texto entra con `textContent`; un test falla si el JavaScript
  usa `innerHTML` o equivalentes. La clave se redacta de toda respuesta.
- **Pruebas**: todo lo verificable sin modelo (adjuntos, casos, serialización, sesión con cliente
  falso, API con `TestClient`, archivos estáticos); una prueba opt-in con el modelo real.

La interfaz no aplica reglas de negocio. Reutiliza sin cambios `Agente`, `ResultadoTurno`, los
hooks de #6 y el core de #4 y #5, salvo `AlmacenEstado.reiniciar()`. Detalle y verificación de la
concurrencia en [research.md](./research.md).

## Technical Context

**Language/Version**: Python ≥ 3.12 (backend); HTML, CSS y JavaScript sin compilación (frontend)

**Primary Dependencies**: `starlette` y `uvicorn` (ya instaladas como transitivas de `mcp`; se
declaran de forma explícita); las existentes (`claude-agent-sdk`, `python-dotenv`, `anyio`, ...)

**Storage**: el estado del core (v2) para los datos del trámite; el hilo vive en la memoria de la
página y la sesión, sin persistencia propia

**Testing**: pytest + anyio. Sin modelo: funciones puras, sesión con cliente SDK falso y API con
`TestClient`. Con modelo real: una prueba `@pytest.mark.live`

**Target Platform**: proceso local en `127.0.0.1`, navegador moderno; sin Node

**Project Type**: aplicación web local (paquete `crediagil.chat` con sus archivos estáticos)

**Performance Goals**: la página responde al instante; el turno tarda lo que tarde el modelo

**Constraints**:
- La interfaz no repite reglas, tasa ni umbrales.
- Los avisos salen solo del resultado estructurado del turno.
- La clave nunca aparece en pantalla, respuestas ni errores.
- Contenido siempre como texto, nunca como marcado.
- Escucha solo en `127.0.0.1`.
- Solo datos ficticios en casos, tests y documentación.

**Scale/Scope**: 6 módulos nuevos (`adjuntos`, `casos`, `serializacion`, `sesion`, `app`,
`__main__`) con sus tests, 3 archivos estáticos, un método nuevo en `AlmacenEstado` y una prueba
con modelo real

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Evaluación pre-diseño | Post-diseño |
|-----------|-----------------------|-------------|
| I. Reglas de negocio | ✅ La interfaz no decide nada: muestra lo que devuelve el agente. Un test asegura que ni la tasa ni los umbrales aparecen en los archivos estáticos ni en los casos. | ✅ R7, R8 |
| II. Garantía en código | ✅ Los adjuntos los valida el servidor; los avisos salen de la estructura; un turno a la vez lo impone un cerrojo; el contenido como texto lo verifica un test. Nada depende de una instrucción al modelo. | ✅ R2, R4, R6, R7 |
| III. Datos ficticios | ✅ Casos con identificadores `TEST-` y documentos construidos al vuelo; la clave se redacta de toda salida. | ✅ R8 |
| IV. Spec antes que código | ✅ spec → plan → tasks antes de escribir en `src/`. | ✅ |
| V. No inventar datos | ✅ La interfaz no completa ni infiere datos: envía lo que el solicitante escribe y adjunta. | ✅ |
| VI. Trazabilidad | ⚠️ El detalle técnico muestra cada herramienta con entrada y salida, y los avisos de escalamiento y bloqueo se ven. Pero el escalamiento sigue sin reflejarse como ticket en GitHub (desviación heredada de #7, FR-020 de aquella spec). | ⚠️ Heredada, documentada abajo |
| VII. Tests junto al código y en los bordes | ✅ Cada regla de adjuntos se prueba en su borde (100 KiB exactos y uno más; 5 adjuntos y 6; falla simulada 0, 20 y 21); cada tipo de aviso, cada código de error y el cerrojo tienen su test. | ✅ [contracts/api.md](./contracts/api.md) |

**Resultado**: PASA con una desviación heredada y justificada (Principio VI, ticket de GitHub).

## Project Structure

### Documentation (this feature)

```text
specs/008-chat-interface/
├── plan.md, research.md, data-model.md, quickstart.md
├── contracts/api.md
├── checklists/requirements.md
└── tasks.md            # /speckit-tasks
```

### Source Code (repository root)

```text
pyproject.toml                               # + starlette, uvicorn
src/crediagil/
├── mcp_server/estado.py                     # + AlmacenEstado.reiniciar() (test en test_estado.py)
└── chat/
    ├── __init__.py, __main__.py             # arranque: python -m crediagil.chat
    ├── adjuntos.py     / test_adjuntos.py   # decodificar_adjuntos, ErrorAdjunto, límites
    ├── casos.py        / test_casos.py      # CasoPrueba, CASOS (datos ficticios)
    ├── serializacion.py/ test_serializacion.py  # ResultadoTurno -> JSON, ROTULOS_AVISO, redactar
    ├── sesion.py       / test_sesion.py     # Sesion: agente entre peticiones, cerrojo, nueva, reiniciar
    ├── app.py          / test_app.py        # crear_app, rutas, errores (TestClient)
    ├── test_estaticos.py                    # sin innerHTML, elementos requeridos, sin umbrales
    ├── test_vivo.py                         # 1 prueba con el modelo real (marker live)
    └── static/index.html, app.js, estilos.css
```

**Structure Decision**: cada responsabilidad en su módulo y casi todo puro: se prueba sin el SDK
ni el modelo. `sesion.py` es lo único con estado y solo orquesta `Agente`; `app.py` solo traduce
HTTP a esa sesión. El JavaScript se mantiene fino (pintar lo que dice la API) porque no hay
pruebas de navegador.

## Complexity Tracking

| Violación | Por qué se acepta | Alternativa más simple descartada |
|-----------|-------------------|-----------------------------------|
| Principio VI: el escalamiento no se refleja aún como ticket en GitHub | Heredada de #7 (decisión del usuario): esta feature solo muestra el escalamiento que el agente ya registró en el core; crear el ticket no es trabajo de la interfaz. | Un hook determinista tras `escalar_a_analista` que cree el issue: trabajo futuro, fuera de #7 y #8. |
