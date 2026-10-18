# Contrato: escáner `scripts/scan_repo.py`

Herramienta de línea de comandos que usan el CI y las personas. Solo biblioteca estándar. El detector
de datos con forma real es el del hook `block_sensitive_data`; el escáner no copia sus reglas.

## Uso

```text
uv run --no-project python scripts/scan_repo.py [--github] [--raiz RUTA]
```

| Opción | Efecto |
|---|---|
| `--github` | además del informe, emite una anotación `::error file=…,line=…::` por hallazgo, para que salga en la línea del cambio |
| `--raiz RUTA` | repositorio a escanear (por defecto, la raíz del repositorio que contiene el script); lo usan los tests para apuntar a un repositorio temporal |

## Qué archivos escanea

Los que devuelve `git ls-files --cached --others --exclude-standard` desde la raíz: los versionados y
los nuevos que el archivo de exclusiones no ignora. En CI son los mismos; en local atrapa un archivo
nuevo antes de `git add`.

Se omiten: `uv.lock` (regla de exclusión), los archivos binarios (con un byte nulo) y los que no
se pueden leer. El resto se lee como UTF-8 con sustitución de bytes inválidos.

## Qué busca

| Tipo | Origen | Qué detecta | Marcador `dato-ficticio` |
|---|---|---|---|
| `tarjeta`, `documento`, `cuenta` | detector del hook (`find_in_line`) | tarjeta válida por Luhn; cédula, NIT o cuenta junto a su etiqueta | exime la línea |
| `archivo_de_entorno` | nombre de la ruta | `.env`, `.env.*`, carpeta `secrets`, extensiones `.pem`, `.key`, `.p12`, `.pfx` | no aplica |
| `credencial` | forma de la cadena | claves de la API de Anthropic, tokens de GitHub, claves de acceso de AWS y cabeceras de clave privada (ver data-model.md) | **no** exime |

## Salida

Una línea por hallazgo, ordenada por archivo y línea:

```text
ruta/del/archivo.py:42: tarjeta
.env:0: archivo_de_entorno
```

Y un resumen final con el número de archivos escaneados y de hallazgos. **Nunca** se imprime el
valor detectado, ni completo ni parcial (FR-006, SC-007).

## Códigos de salida

| Código | Significado |
|---|---|
| 0 | sin hallazgos |
| 1 | al menos un hallazgo |
| 2 | no pudo ejecutarse: no es un repositorio git, no está `git`, o el detector no carga |

## Garantías que prueban los tests (`scripts/test_scan_repo.py`)

Sobre un repositorio git temporal, con archivos construidos en ejecución:

| # | Caso | Resultado esperado |
|---|---|---|
| 1 | repositorio limpio | salida 0, sin hallazgos |
| 2 | tarjeta válida por Luhn, cédula con etiqueta, cuenta con etiqueta | salida 1 con el tipo, archivo y línea correctos |
| 3 | las mismas líneas con `dato-ficticio` | salida 0 |
| 4 | archivo `.env` y archivo en `secrets/` | salida 1, tipo `archivo_de_entorno` |
| 5 | nombres parecidos que no son de entorno (`environment.md`, `env.py`, `docs/secretos.md`) | salida 0 |
| 6 | cadena con forma de clave de la API con 20 caracteres tras el prefijo, y con 19 | 20 falla, 19 pasa (borde) |
| 7 | token de GitHub con 36 caracteres tras el prefijo, y con 35 | 36 falla, 35 pasa (borde) |
| 8 | credencial en una línea con `dato-ficticio` | sigue siendo hallazgo |
| 9 | `uv.lock` con una línea que el detector marcaría | se ignora; el mismo contenido en otro archivo falla |
| 10 | archivo binario | se omite sin error |
| 11 | el informe de los casos 2, 4, 6 y 7 | no contiene el valor detectado ni una subcadena de 6 caracteres seguidos de él |
| 12 | un directorio que no es repositorio git | salida 2 |
| 13 | `--github` | emite una anotación `::error file=…,line=…::` por hallazgo, también sin el valor |
| 14 | archivo nuevo sin `git add` | se escanea; si está ignorado por el archivo de exclusiones, no |
| 15 | el escáner sobre el propio repositorio | salida 0 (el árbol actual está limpio) |

Pruebas puras (sin subproceso) sobre las funciones de credenciales, archivos de entorno y enmascarado
cubren los bordes de longitud y de nombre con más casos que el extremo a extremo.
