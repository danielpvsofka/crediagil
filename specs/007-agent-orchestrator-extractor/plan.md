# Implementation Plan: Agente orquestador y subagente extractor

**Branch**: `develop` (feature dir `007-agent-orchestrator-extractor`) | **Date**: 2026-10-18 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/007-agent-orchestrator-extractor/spec.md` — Issue [#7](https://github.com/danielpvsofka/crediagil/issues/7)

## Summary

El agente de originación sobre el Claude Agent SDK, en `crediagil.agent`. Una conversación es un
`ClaudeSDKClient`; el SDK lanza el CLI de Claude Code, que ejecuta el bucle de herramientas. El
código de esta feature decide con la razón de parada, no con el texto.

- **Orquestador (`Agente`)**: recibe el mensaje y los adjuntos de cada turno, y devuelve un
  `ResultadoTurno` estructurado: respuesta, avisos, traza técnica, razón de parada y negaciones.
  - Las razones de parada se clasifican con la función pura `clasificar_parada`: fin de turno,
    truncado (continúa de forma acotada), rechazo, tope y desconocida (incidente: escala).
  - Los avisos se derivan de los resultados de las herramientas, nunca del texto del modelo.
- **Subagente `extractor-documentos`**: solo puede usar `validar_extraccion`. Un hook
  `PreToolUse` sobre `Agent` garantiza en código que cada delegación lleve `documento_id`,
  nombre y texto completo.
- **`solicitar_informacion`**: herramienta de canal en proceso que registra el pedido al
  solicitante sin tocar el core.
- **Aislamiento**: `setting_sources=[]` (el valor por defecto `None` no aísla), lista de
  herramientas cerrada, `permission_mode="dontAsk"`, solo los servidores MCP del código y un
  directorio de trabajo vacío.
- **Clave de la API**: se carga del entorno o del archivo local con `python-dotenv`, nunca se
  pisan variables definidas y se redacta de toda salida.
- **Pruebas**: lo determinista se prueba sin modelo con un cliente falso que emite mensajes del
  SDK guionizados; 5 pruebas con el modelo real quedan fuera de la suite por defecto
  (`-m live`).

Los hooks de #6 y el servidor de #4 y #5 se reutilizan sin cambios. Detalle y API verificada del
SDK en [research.md](./research.md).

## Technical Context

**Language/Version**: Python ≥ 3.12

**Primary Dependencies**: `claude-agent-sdk>=0.2.168,<0.3` (ya instalada; empaqueta el CLI);
`python-dotenv` (nueva); las existentes (`mcp`, `filelock`, `pydantic`, `anyio`)

**Storage**: el estado del core (v2), compartido entre el agente (hooks) y el servidor MCP hijo

**Testing**: pytest + anyio. Sin modelo: funciones puras y un cliente SDK falso con mensajes
reales del SDK. Con modelo real: `@pytest.mark.live`, excluido por `addopts = -m "not live"`

**Target Platform**: proceso local; el CLI de Claude Code va empaquetado con el SDK

**Project Type**: biblioteca (paquete `crediagil.agent`); la interfaz es #8

**Performance Goals**: N/A en pruebas sin modelo; los turnos reales dependen del modelo

**Constraints**:
- Ningún fin de ciclo por conteo fijo ni por texto; los topes son solo de seguridad.
- La clave nunca sale en logs, respuestas ni traza.
- Sin herramientas fuera de la lista permitida.
- Solo datos ficticios.
- Pruebas con modelo real opt-in y con tope de coste.

**Scale/Scope**: 7 módulos nuevos más `config.py`, 2 prompts, sus tests y 5 pruebas con modelo
real

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Evaluación pre-diseño | Post-diseño |
|-----------|-----------------------|-------------|
| I. Reglas de negocio | ✅ El agente no aplica reglas: delega en el core (#5), la política (#3) y los hooks (#6). Un test garantiza que ni la tasa ni los umbrales aparecen en los prompts. | ✅ R10 |
| II. Garantía en código | ✅ El fin del ciclo lo decide `clasificar_parada`; la delegación explícita, un hook; el aislamiento, las opciones; los prompts solo guían. | ✅ R2, R3, R6 |
| III. Datos ficticios | ✅ Pruebas con datos ficticios; la clave no entra al repositorio y se redacta de toda salida. | ✅ R7 |
| IV. Spec antes que código | ✅ spec → plan → tasks antes de escribir en `src/`. | ✅ |
| V. No inventar datos | ✅ El subagente devuelve los datos faltantes y el agente los pide con `solicitar_informacion`; nunca se reintentan ni se completan. | ✅ R3, R4 |
| VI. Trazabilidad | ⚠️ Avisos, traza y negaciones salen de resultados reales y cada dato conserva su procedencia. Pero el escalamiento no se refleja aún como ticket en GitHub (decisión del usuario sobre FR-020). | ⚠️ Desviación documentada abajo |
| VII. Tests junto al código y en los bordes | ✅ Cada razón de parada, cada fila de la delegación y cada opción de aislamiento tiene su test; los casos de humo reales cubren solicitud de humano, dato ausente y fuera de política. | ✅ [contracts/agente.md](./contracts/agente.md) |

**Resultado**: PASA con una desviación justificada (Principio VI, ticket de GitHub).

## Project Structure

### Documentation (this feature)

```text
specs/007-agent-orchestrator-extractor/
├── plan.md, research.md, data-model.md, quickstart.md
├── contracts/agente.md
├── checklists/requirements.md
└── tasks.md            # /speckit-tasks
```

### Source Code (repository root)

```text
pyproject.toml                               # + python-dotenv; marker live; addopts -m "not live"
src/crediagil/
├── config.py            / test_config.py     # cargar_entorno, obtener_api_key, redactar
└── agent/
    ├── prompts/orquestador.md, extractor.md  # en español, sin tasa ni umbrales
    ├── prompts.py       / test_prompts.py    # carga y comprobaciones de los prompts
    ├── parada.py        / test_parada.py     # Parada, clasificar_parada
    ├── canal.py         / test_canal.py      # PedidoInformacion, solicitar_informacion
    ├── delegacion.py    / test_delegacion.py # DocumentoAdjunto, hook sobre Agent
    ├── traza.py         / test_traza.py      # EventoTraza, Aviso, ResultadoTurno, derivación
    ├── opciones.py      / test_opciones.py   # ConfigAgente, construir_opciones (aislamiento)
    ├── orquestador.py   / test_orquestador.py# Agente con cliente falso guionizado
    └── test_vivo.py                          # 5 pruebas con el modelo real (marker live)
```

**Structure Decision**: cada responsabilidad en su módulo y casi todas funciones puras: se prueban
sin el SDK ni el modelo. `orquestador.py` solo compone: abre el cliente, envía el turno,
traduce los mensajes con `traza.py`, clasifica la parada y escala por código en los incidentes.

## Complexity Tracking

| Violación | Por qué se acepta | Alternativa más simple descartada |
|-----------|-------------------|-----------------------------------|
| Principio VI: el escalamiento no se refleja aún como ticket en GitHub | Decisión del usuario (FR-020, opción A): el issue #7 no lo incluye y las pruebas con el modelo real crearían issues reales en el repositorio. El escalamiento ya queda guardado en el core con su resumen completo. | Un hook determinista tras `escalar_a_analista` que cree el issue: queda anotado como siguiente paso en una feature posterior. |
