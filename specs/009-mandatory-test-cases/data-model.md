# Data Model: Casos de prueba obligatorios

Todo se valida al cargar (pydantic); un caso inválido impide cargar el catálogo y el error nombra
la carpeta y el campo.

## Caso

| Campo | Tipo | Regla |
|---|---|---|
| `id` | texto | `[a-z][a-z0-9_]*`; único en el catálogo; coincide con el nombre de la carpeta sin el prefijo `NN_` |
| `numero` | entero o `null` | 1 a 8 para los obligatorios, único y sin huecos; `null` solo en complementarios |
| `obligatorio` | booleano | `true` ⇔ `numero` no es `null` |
| `nombre` | texto | no vacío |
| `descripcion` | texto | no vacía; dice qué comportamiento ejercita |
| `mensaje` | texto | contenido de `mensaje.md`; no vacío |
| `documentos` | lista de `Documento` | puede ser vacía solo si el caso lo declara (`sin_documentos: true`), como el caso 8 |
| `falla_simulada` | entero | 0 a 20 (mismo rango que la interfaz); 0 = sin falla |
| `solicitud` | `Solicitud` o `null` | `null` solo en casos que no llegan a registrar (caso 8) |
| `esperado` | `Esperado` | ver abajo |

## Documento

| Campo | Tipo | Regla |
|---|---|---|
| `nombre` | texto | nombre del archivo en `documentos/`; extensión `.txt` o `.md` (minúsculas) |
| `texto` | texto | UTF-8, no vacío; tamaño dentro del límite de adjuntos de la interfaz |
| `extraccion` | objeto o `null` | contenido de `extraccion/<mismo nombre sin extensión>.json`; si existe, pasa `validar_documento` y **cada `fragmento` aparece literal en `texto`** |

Un documento sin `extraccion` solo es válido si el caso declara que el extractor no debe
producir nada de él (no hay ninguno en los ocho obligatorios).

## Solicitud

| Campo | Tipo | Regla |
|---|---|---|
| `id_solicitante` | texto | existe en la semilla ficticia (`SOL-000N`) |
| `monto` | entero | `> 0`; aparece en `mensaje` en formato de pesos con puntos |
| `plazo_meses` | entero | `> 0`; aparece en `mensaje` |
| `ingreso_declarado` | entero o `null` | `≥ 0` y aparece en `mensaje` (con puntos de miles); `null` solo si `esperado.resultado = solicitar_dato` (el mensaje no declara ingreso) |
| `identidad` | `verificada` \| `sin_verificar` | `sin_verificar` solo en el caso 5; los demás verifican con los datos de la semilla |

## Esperado

| Campo | Tipo | Regla |
|---|---|---|
| `resultado` | enum | `preaprobar`, `solicitar_dato`, `escalar`, `bloquear`, `reintentar` |
| `causa` | enum o `null` | obligatoria si `resultado = escalar`: `regla_2`, `regla_3`, `moneda`, `solicitud_humano`; prohibida en los demás |
| `datos_faltantes` | lista de texto | obligatoria si `resultado = solicitar_dato` (p. ej. `salario_mensual`) |
| `herramientas` | `Herramientas` | lo que la prueba con modelo real verifica sobre la traza |

### Herramientas (todas opcionales)

| Campo | Significado |
|---|---|
| `primera` | nombre de la primera herramienta que llama el orquestador (sin las del subagente) |
| `debe_llamar` | herramientas que deben aparecer |
| `no_debe_llamar` | herramientas que no deben aparecer |
| `en_orden` | subsecuencia que debe respetarse (no un orden total) |
| `avisos` / `sin_avisos` | tipos de aviso que deben / no deben estar en el resultado del turno |
| `entrada_primera` | pares ruta→valor que debe cumplir la entrada de la primera llamada (p. ej. `resumen.causa = solicitud_humano`) |
| `sin_exito` | herramientas que no deben haber terminado con `ok = true` (aunque se hayan intentado) |
| `si_intenta` | si el modelo intentó alguna de `herramientas`, debe haber una negación con `codigo_negacion`, un aviso del tipo `aviso` y no más de `max_intentos` intentos; si no intentó, se cumple |
| `reintenta_tras_falla` | si es `true`, hubo una llamada fallida con `reintentable = true` y después la misma herramienta salió bien |
| `max_validaciones_exitosas` | tope de `validar_extraccion` aceptadas (el dato ausente no se reintenta) |
| `sin_llamadas_repetidas` | si es `true`, ninguna llamada exitosa se repite con la misma entrada |

## Relaciones y reglas del catálogo

- Los 8 obligatorios (`numero` 1 a 8) están todos; los complementarios no ocupan número.
- Ningún texto del catálogo repite la tasa ni los umbrales (la comprobación de #8 se amplía a todos
  los textos de las carpetas).
- Ningún texto tiene datos con forma real sin el marcador de dato ficticio en la misma línea.

## Transiciones

Ninguna: el catálogo es de solo lectura en ejecución. Los tests crean estados temporales y los
descartan.
