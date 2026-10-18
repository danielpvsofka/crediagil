# Contrato: carpeta de un caso y API pública

## Estructura de una carpeta

```text
src/crediagil/casos/NN_id/
├── caso.json                    # obligatorio
├── mensaje.md                   # obligatorio, UTF-8, lo que escribe el solicitante
├── documentos/                  # omitida si el caso declara sin_documentos
│   └── <nombre>.txt | .md       # lo que adjunta; UTF-8; no vacío
└── extraccion/
    └── <nombre>.json            # salida esperada del extractor para ese documento
```

- `NN` son dos dígitos (`01` a `09`); el `id` de `caso.json` debe coincidir con el nombre de la
  carpeta sin el prefijo.
- Archivos o carpetas que no estén en este contrato hacen fallar la carga (evita restos).
- Los textos no pueden contener la tasa ni los umbrales ni datos con forma real.

## `caso.json`

```json
{
  "id": "monto_sobre_umbral",
  "numero": 4,
  "nombre": "Solicitud de $8.000.000",
  "descripcion": "Una solicitante con ingreso holgado pide un monto mayor al de preaprobación automática: el agente registra la solicitud y la escala por monto.",
  "sin_documentos": false,
  "falla_simulada": 0,
  "solicitud": {
    "id_solicitante": "SOL-0001",
    "monto": 8000000,
    "plazo_meses": 36,
    "ingreso_declarado": 20000000,
    "identidad": "verificada"
  },
  "esperado": {
    "resultado": "escalar",
    "causa": "regla_2",
    "herramientas": {
      "debe_llamar": ["registrar_solicitud", "escalar_a_analista"],
      "no_debe_llamar": ["preaprobar_credito"],
      "avisos": ["escalamiento"],
      "sin_avisos": ["credito_preaprobado"]
    }
  }
}
```

Los números del ejemplo son ilustrativos: el ingreso exacto de cada caso se fija en su carpeta,
siempre lejos de cualquier umbral salvo en `test_bordes.py`, que los deriva de la política.

## `extraccion/<nombre>.json`

El mismo formato que acepta `validar_extraccion` (spec 005), con `{valor, fragmento}` en cada
campo y el fragmento literal del documento. Un campo que el documento no trae no aparece o es
`null` (Principio V).

```json
{
  "tipo": "certificado_laboral",
  "empleador": {"valor": "Empresa Ficticia S.A.S.", "fragmento": "Empresa Ficticia S.A.S."},
  "salario_mensual": {"valor": 20000000, "fragmento": "salario mensual de $20.000.000"},
  "moneda": {"valor": "COP", "fragmento": "$20.000.000 COP"}
}
```

## API pública (`crediagil.casos`)

| Símbolo | Descripción |
|---|---|
| `cargar_catalogo(ruta=None) -> Catalogo` | Lee y valida todas las carpetas; lanza `ErrorCatalogo(carpeta, campo, mensaje)` ante el primer defecto. Sin `ruta` usa la del paquete. |
| `Catalogo.casos` | Tupla de `Caso` ordenada por `numero` (complementarios al final). |
| `Catalogo.obligatorios` | Los 8 casos con `numero`. |
| `Catalogo.por_id(id)` | `Caso` o `None`. |
| `Caso`, `Documento`, `Solicitud`, `Esperado`, `Herramientas` | Modelos de solo lectura descritos en [data-model.md](../data-model.md). |
| `catalogo()` | Catálogo del paquete cargado una vez por proceso (`functools.cache`). |

### Validaciones del cargador (cada una con su test)

1. Faltan `caso.json` o `mensaje.md`, o sobra un archivo no previsto.
2. `id` repetido, con formato inválido o distinto del nombre de la carpeta.
3. `numero` repetido, fuera de 1 a 8 o con huecos entre los obligatorios.
4. `obligatorio` incoherente con `numero`.
5. `resultado` fuera del vocabulario, `causa` ausente o sobrante, `datos_faltantes` ausente.
6. Documento con otra extensión, vacío, no UTF-8 o que supera el límite de adjuntos.
7. Extracción que no pasa `validar_documento` o con un fragmento que no está literal en su
   documento.
8. `id_solicitante` que no existe en la semilla.
9. `falla_simulada` fuera de 0 a 20.
10. `monto`, `plazo_meses` o `ingreso_declarado` que no aparecen en el mensaje.

## `GET /api/casos` (interfaz de chat, compatible hacia atrás)

Cada elemento conserva `id`, `nombre`, `descripcion`, `mensaje`, `adjuntos` (`nombre`, `texto`) y
`falla_sugerida`, y añade `numero` (entero o `null`) y `obligatorio` (booleano). El orden es el
del catálogo.
