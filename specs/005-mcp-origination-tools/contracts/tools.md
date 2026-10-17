# Contrato: herramientas de originación

Mismo servidor `crediagil-core` de #4 (contrato de respuesta, fallas inyectadas). Entidades y
códigos en [data-model.md](../data-model.md). Montos en pesos enteros.

## `validar_extraccion`

**Descripción (es)**: "Valida los datos que extrajiste de un documento contra su texto completo:
cada campo debe ser {valor, fragmento} y el fragmento debe aparecer literalmente en el texto.
Si el error es reintentable, corrige la extracción y vuelve a validar; nunca inventes un valor
para cubrir un dato faltante."

| Parámetro | Tipo |
|-----------|------|
| `datos` | `object` (incluye `tipo`) |
| `texto` | `str` |

| Caso | Resultado |
|------|-----------|
| Certificado válido | `ok`, `extraccion` normalizada, `datos_faltantes: [campos nulos]`, `politica_no_cubre: false` |
| `tipo: no_soportado` | `ok`, `politica_no_cubre: true` |
| Fragmento no literal | `validacion` `FRAGMENTO_NO_LITERAL`, `reintentable: true`, `detalles.campos` incluye el campo |
| Valor sin fragmento / campo extra / salario ≤ 0 / tipo desconocido | `validacion` `EXTRACCION_INVALIDA`, `reintentable: true`, `detalles.errores[].campo` |

## `registrar_solicitud`

**Descripción (es)**: "Registra una solicitud de crédito de un solicitante con identidad
verificada (verificar_identidad), con monto, plazo, ingreso declarado y los documentos (cada uno
con id_documento, datos extraídos y texto). Guarda cada dato con su documento y fragmento y
devuelve la evaluación. Si preaprobable_automaticamente es false, escala a un analista con las
causas; no intentes preaprobar."

| Parámetro | Tipo |
|-----------|------|
| `id_solicitante` | `str` |
| `monto` | `int` |
| `plazo_meses` | `int` |
| `ingreso_declarado` | `int` |
| `documentos` | `list[{id_documento, datos, texto}]` |

| Caso | Resultado |
|------|-----------|
| Identidad no verificada / bloqueado | `permisos` `IDENTIDAD_NO_VERIFICADA`; nada guardado |
| Monto 5.000.000, 12 meses, salario 1.556.700, declarado = salario | `ok`, `id_solicitud`, `evaluacion.preaprobable_automaticamente: true`, `causas_escalamiento: []` |
| Igual con salario 1.556.699 | registrada, `preaprobable_automaticamente: false`, causa `regla_2` |
| Monto 5.000.001 | registrada, causa `regla_2` |
| Declarado = salario × 1,10 exacto / +1 | preaprobable / causa `regla_3` |
| Nómina > 10% del salario | registrada, causa `nomina`, decisión `analista` |
| Certificado en USD | registrada, decisión `fuera_de_politica` |
| Sin certificado (o sin salario) | `negocio` `INGRESO_NO_VERIFICABLE`, no reintentable, `detalles.datos_faltantes` incluye `salario_mensual`; nada guardado |
| Extracción inválida | mismo error que `validar_extraccion`; nada guardado |
| Monto 0 / plazo 61 / declarado negativo | `validacion` `PARAMETROS_INVALIDOS`, no reintentable |
| Registro OK | cada dato guardado tiene `id_documento` y `fragmento` |

## `calcular_capacidad_pago`

**Descripción (es)**: "SOLO SIMULA: calcula la cuota mensual de un monto y plazo (y, si das un
ingreso, qué proporción representa). No registra, no preaprueba y no compromete a Crediágil; no
requiere identidad. Úsala para responder simulaciones; para comprometer usa preaprobar_credito."

| Parámetro | Tipo |
|-----------|------|
| `monto` | `int` |
| `plazo_meses` | `int` |
| `ingreso_mensual` | `int \| null` |

| Caso | Resultado |
|------|-----------|
| 4.000.000, 24 | `ok`, `cuota: 206723`, `tasa_mensual: "0.018"` |
| + ingreso 1.556.700 con 5.000.000/12 | `proporcion_cuota_ingreso: "0.3000"`, `dentro_de_proporcion_maxima: true` |
| Cualquier llamada | el archivo de estado no cambia |
| Plazo 61 | `validacion` `PARAMETROS_INVALIDOS` |

## `preaprobar_credito`

**Descripción (es)**: "COMPROMETE A CREDIÁGIL: preaprueba una solicitud registrada. Úsala solo
si registrar_solicitud devolvió preaprobable_automaticamente: true; para simular cuotas usa
calcular_capacidad_pago. El core vuelve a validar identidad y umbrales y rechaza si no se
cumplen; en ese caso escala a un analista."

| Parámetro | Tipo |
|-----------|------|
| `id_solicitud` | `str` |

| Caso | Resultado |
|------|-----------|
| Preaprobable, identidad vigente | `ok`, `id_solicitud`, `monto`, `plazo_meses`, `cuota`, `tasa_mensual`; estado `PREAPROBADA` |
| Segunda llamada | mismo `ok` (idempotente) |
| Solicitante bloqueado tras registrar | `permisos` `IDENTIDAD_NO_VERIFICADA`; estado sin cambio |
| Solicitud con causa regla 2/3/nómina | `negocio` `NO_PREAPROBABLE`, `detalles.causas` |
| Solicitud escalada | `negocio` `SOLICITUD_ESCALADA` |
| Inexistente | `negocio` `SOLICITUD_NO_ENCONTRADA` |

## `escalar_a_analista`

**Descripción (es)**: "Escala un caso a un analista humano con un resumen completo para que no
tenga que repetir preguntas: solicitante, monto, plazo, datos con documento y fragmento,
discrepancias, causa, detalle y acción recomendada. Úsala de inmediato si el solicitante pide
hablar con una persona (causa solicitud_humano; monto, plazo y datos pueden ir vacíos) y siempre
que la evaluación no sea preaprobable."

| Parámetro | Tipo |
|-----------|------|
| `resumen` | `object` (ResumenEscalamiento) |
| `id_solicitud` | `str \| null` |

| Caso | Resultado |
|------|-----------|
| Resumen completo con solicitud | `ok`, `id_escalamiento`; solicitud `ESCALADA` |
| `solicitud_humano` con monto/plazo `null`, `datos: []`, `discrepancias: []` | `ok` |
| Falta cualquiera de las 8 claves | `validacion` `RESUMEN_INCOMPLETO`, `detalles.campos_faltantes` |
| `detalle: ""` o `causa: "otra_cosa"` | `RESUMEN_INCOMPLETO` |
| Dato sin `fragmento` o `documento` | `RESUMEN_INCOMPLETO` |
| Solicitud ya preaprobada | `negocio` `SOLICITUD_PREAPROBADA` |
| Solicitud inexistente | `negocio` `SOLICITUD_NO_ENCONTRADA` |

## Cambios a #4

| Herramienta | Cambio |
|-------------|--------|
| `verificar_identidad` | éxito guarda `verificado_en`; bloqueo lo borra |
| Contrato de errores | regla de reintento FR-001a |
| `list_tools` | 7 herramientas |
