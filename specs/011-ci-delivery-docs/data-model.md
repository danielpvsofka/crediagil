# Data Model: CI y documentación de entrega

No hay datos de negocio ni estado persistente: son los resultados del escáner, las reglas que
aplica y los límites que vigilan los tests de la entrega.

## Hallazgo

Una cosa encontrada por el escáner. Nunca contiene el valor.

| Campo | Tipo | Regla |
|---|---|---|
| `archivo` | cadena | ruta relativa a la raíz del repositorio, con `/` |
| `linea` | entero ≥ 1 | número de línea; `0` solo para `archivo_de_entorno` (el problema es el archivo, no una línea) |
| `tipo` | enumeración | `tarjeta`, `documento`, `cuenta`, `archivo_de_entorno` o `credencial` |

**Invariantes**
- El valor detectado (número, clave) no se almacena ni se imprime; solo `archivo`, `linea` y `tipo`.
- `tarjeta`, `documento` y `cuenta` vienen del detector del hook; `archivo_de_entorno` y
  `credencial` son comprobaciones propias del escáner.
- Una línea con el marcador `dato-ficticio` no produce hallazgos de `tarjeta`, `documento` ni `cuenta`;
  **sí** puede producir `credencial` (el marcador no exime una credencial).

## Regla de exclusión

| Campo | Significado |
|---|---|
| `nombre` | nombre de archivo excluido del escaneo |
| `motivo` | por qué (texto breve, para quien lea el código) |

Reglas vigentes:

| Nombre | Motivo |
|---|---|
| `uv.lock` | archivo generado: las rutas de descarga con hashes coinciden con la etiqueta de cédula (falso positivo comprobado) |

Además se omiten los archivos binarios (con un byte nulo) y los que no se pueden leer.

## Resultado del escaneo

| Campo | Tipo | Regla |
|---|---|---|
| `escaneados` | entero ≥ 0 | archivos de texto leídos |
| `hallazgos` | lista de Hallazgo | ordenada por archivo y línea |
| `codigo_de_salida` | 0, 1 o 2 | 0 sin hallazgos; 1 con hallazgos; 2 si no pudo ejecutarse |

## Credenciales reconocidas

| Tipo de credencial | Forma | Longitud (borde) |
|---|---|---|
| Clave de la API de Anthropic | `sk-ant-` + letras, dígitos, `_` o `-` | 20 o más tras el prefijo (19 no cuenta) |
| Token de GitHub clásico | `ghp_`, `gho_`, `ghu_`, `ghs_` o `ghr_` + alfanuméricos | exactamente 36 tras el prefijo |
| Token de GitHub de granularidad fina | `github_pat_` + alfanuméricos y `_` | 22 o más tras el prefijo |
| Clave de acceso de AWS | `AKIA` + mayúsculas y dígitos | exactamente 16 tras el prefijo |
| Clave privada | cabecera `-----BEGIN … PRIVATE KEY-----` | — |

## Archivos de entorno o de secretos (por nombre de ruta)

| Condición | Ejemplo que falla | Ejemplo que no falla |
|---|---|---|
| nombre `.env` o que empieza por `.env.` | `.env`, `config/.env.local` | `environment.md`, `env.py` |
| una carpeta de la ruta se llama `secrets` | `secrets/clave.txt` | `docs/secretos.md` |
| extensión `.pem`, `.key`, `.p12` o `.pfx` | `certs/servidor.pem` | `monkey.py` |

## Límites de la documentación de entrega

| Elemento | Límite | Cómo se mide |
|---|---|---|
| `DECISIONES.md` | ≤ 1.000 palabras | `len(re.findall(r"\w+", texto))` |
| Necesidades del ecosistema | 11, cada una con mecanismo y motivo no vacíos | filas numeradas de la tabla, con al menos 4 celdas con contenido |
| Tasa y umbrales | 0 apariciones en `DECISIONES.md`, README y workflow | formatos de `crediagil.policy.params` (pesos con punto, coma y sin separador; porcentaje con y sin espacio) |
| README | enlace al Project, enlace al video, tres comandos obligatorios | presencia de las URL y de las cadenas de comando |

## Contrato del workflow

Ver [contracts/ci.md](./contracts/ci.md): disparadores, tres trabajos, permisos, acciones fijadas.

## Transiciones

No hay estados. Un archivo nuevo que entra al repositorio se escanea en la siguiente ejecución;
un recorte de `DECISIONES.md` por debajo del límite hace pasar el test de longitud.
