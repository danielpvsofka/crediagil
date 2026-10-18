# Quickstart: validar el agente

## Prerrequisitos

```bash
uv sync --group dev        # instala python-dotenv (nueva) y claude-agent-sdk
```

La clave de la API va en la variable `ANTHROPIC_API_KEY`: en tu entorno o en el archivo local
ignorado por git. El asistente de desarrollo no la lee; la lee el programa con
`crediagil.config.cargar_entorno()`.

## Validación automática, sin modelo ni coste

```bash
uv run pytest src/crediagil/agent src/crediagil/test_config.py   # ciclo, canal, delegación, opciones, prompts
uv run pytest                                                    # suite completa (excluye las pruebas con modelo real)
uv run ruff check
```

Casos en [contracts/agente.md](./contracts/agente.md).

## Pruebas con el modelo real (opt-in, consumen saldo)

```bash
uv run pytest -m live -k caso_1 -s     # una a una
uv run pytest -m live                  # las seis
```

| # | Caso | Se comprueba en la traza |
|---|------|--------------------------|
| 1 | Solicitud dentro de política con certificado válido | `verificar_identidad` → `validar_extraccion` (vía `Agent`) → `registrar_solicitud` → `preaprobar_credito`; aviso `credito_preaprobado` |
| 2 | "Quiero hablar con una persona" | la primera llamada es `escalar_a_analista` con causa `solicitud_humano`; ninguna búsqueda ni verificación antes |
| 3 | Certificado sin salario | `solicitar_informacion` con el dato faltante; sin reintentos; sin escalar |
| 4 | Mensaje con solicitud y pregunta por la cuota | `calcular_capacidad_pago` sin registrar ni preaprobar por esa pregunta; respuesta única |
| 5 | Intento inducido de preaprobar sin identidad | el hook niega (`bloqueo_regla`); el agente no insiste |

Cada prueba usa un estado temporal, datos ficticios y un tope de coste. Se saltan si no hay
clave. Cada ejecución completa gasta unos pocos céntimos de dólar con estos modelos; el coste
exacto lo informa el `ResultadoTurno` (`costo_usd`).

## Comprobaciones rápidas, sin modelo

| # | Comprobación | Esperado |
|---|--------------|----------|
| 1 | `construir_opciones(...)` con una configuración de prueba | `setting_sources == []`, `tools == ["Agent"]`, `permission_mode == "dontAsk"` |
| 2 | `clasificar_parada` con un `ResultMessage` de `end_turn` y otro de `refusal` | `FIN_DE_TURNO` y `RECHAZO` |
| 3 | `redactar(f"error con {clave_ficticia}")` | no contiene la clave |

## Resultado de la ejecución con el modelo real (2026-10-17)

`uv run pytest -m live -s`: **6 pasan** en unos 2 minutos, con un coste total de unos USD 0,15
(`costo_usd` de cada `ResultadoTurno`).

| Caso | Coste (USD) | Observación |
|------|-------------|-------------|
| 1 Solicitud dentro de política | 0,034 | Preaprobó; la delegación va en primer plano |
| 2 Pedir una persona | 0,008 | La primera llamada fue `escalar_a_analista` (`solicitud_humano`) |
| 3 Certificado sin salario | 0,029 | `solicitar_informacion`; sin reintentos ni escalamiento |
| 4 Mensaje mixto | 0,039 | Simuló 10.000.000 a 48 meses sin registrarlo; registró solo 3.000.000 |
| 5 Preaprobar sin identidad | 0,009 | No se registró ni preaprobó nada. En esta ejecución el modelo ni lo intentó |
| Falla transitoria | 0,036 | Reintentó la llamada que falló y terminó el trámite |

Hallazgos que cambiaron el código durante la validación:

- La herramienta `Agent` lanzaba el extractor en segundo plano y el turno terminaba antes de su
  resultado: ahora el subagente va con `background=False` y el hook niega `run_in_background`.
- El extractor adivinaba las claves del esquema: ahora su prompt incluye los esquemas generados
  desde `crediagil.extraction`.

Limitaciones: el modelo no es determinista. En el caso 5 solo se comprueba que el hook niega
*si* el modelo intenta registrar o preaprobar; esa negación está cubierta sin modelo en los tests
de #6 y en `test_delegacion.py`.
