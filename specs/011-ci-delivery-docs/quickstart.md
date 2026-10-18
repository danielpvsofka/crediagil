# Quickstart: validar la verificación automática y la documentación de entrega

Guía para comprobar de punta a punta que la feature funciona. Reglas en
[contracts/escaneo.md](./contracts/escaneo.md) y [contracts/ci.md](./contracts/ci.md); tablas en
[data-model.md](./data-model.md).

## Prerrequisitos

- `uv sync --group dev` en este repositorio.
- Para el recorrido del CI (§6), el repositorio en GitHub con permiso para publicar una rama y abrir
  un PR de prueba.

## 1. El escáner sobre el repositorio (sin red, sin clave)

```bash
uv run --no-project python scripts/scan_repo.py
```

Esperado: salida 0 y el resumen `0 hallazgos`; `uv.lock` no aparece como hallazgo.

## 2. Los tests de la feature

```bash
uv run pytest scripts
```

Esperado: todo en verde en pocos segundos (escáner, workflow, entrega).

## 3. El escáner falla donde debe (SC-001, SC-005, SC-007)

En un directorio temporal con un repositorio git vacío (el propio test lo hace):

1. añadir un archivo con una tarjeta válida generada en ejecución → falla con `tarjeta`;
2. añadir un archivo llamado como un archivo de entorno → falla con `archivo_de_entorno`;
3. añadir una línea con la forma de una clave de la API de Anthropic, construida en ejecución →
   falla con `credencial`;
4. comprobar que ningún informe contiene el valor.

## 4. Límites de la entrega (SC-004)

```bash
uv run pytest scripts/test_entrega.py
```

Esperado: `DECISIONES.md` ≤ 1.000 palabras con las 11 necesidades; el README con los dos enlaces y
los tres comandos. Subir artificialmente el documento por encima del límite debe hacerlo fallar.

## 5. Una persona nueva en menos de 5 minutos (SC-003)

En un directorio vacío, sin la caché del entorno virtual:

```bash
git clone https://github.com/danielpvsofka/crediagil.git && cd crediagil
uv sync --group dev
uv run pytest
uv run python -m crediagil.chat      # abrir http://127.0.0.1:8000
```

Medir el tiempo total hasta tener la interfaz abierta y anotarlo abajo.

## 6. El CI en GitHub (SC-001, SC-002)

1. Publicar una rama con un cambio limpio y abrir un PR hacia `main`: los tres trabajos (`formato`,
   `pruebas`, `escaneo`) deben pasar en menos de 10 minutos.
2. En una rama de prueba, añadir por separado: un archivo sin formato, una prueba rota y una línea con
   una tarjeta generada en ejecución. Cada cambio debe fallar en **su** trabajo con un motivo claro; el
   del escaneo debe mostrar la anotación en la línea, sin el número.
3. Cerrar los PR de prueba sin fusionar.
4. Opcional (fuera de alcance de la feature): en la configuración de GitHub, exigir que los tres
   trabajos pasen antes de fusionar en `main`.

## 7. Historial sin credenciales (revisión única)

Con un script temporal que no se versiona, aplicar las comprobaciones de credenciales a las líneas
añadidas de todo el historial y los nombres de archivo de entorno a todos los archivos que alguna vez
existieron. Esperado: ningún hallazgo. Anotar el resultado abajo.

## Resultado de las validaciones

Medido el 2026-10-18 (Windows, `uv` con la caché caliente):

- **§1 Escáner sobre el repositorio**: salida 0, `290 archivos escaneados, 0 hallazgos`, en 0,5 s;
  `uv.lock` no aparece como hallazgo.
- **§2 Tests de la feature**: `uv run pytest scripts` → 145 pasan en unos 15 s (escáner, workflow,
  repositorio y entrega). La suite completa: `uv run pytest` → 1323 pasan, 10 `live` excluidos, en
  unos 50 s (antes 1178: el aumento son los 145 de esta feature).
- **§3 El escáner falla donde debe**: los controles negativos construyen en ejecución una tarjeta, una
  cédula, una cuenta, archivos de entorno y de secretos y las cinco formas de credencial; ningún
  informe contiene el valor ni una subcadena de 6 caracteres de él (SC-001, SC-005, SC-007).
- **§4 Límites de la entrega**: `DECISIONES.md` mide 915 palabras (límite 1.000; antes 1.160) con las
  11 necesidades; el README conserva los dos enlaces y los seis comandos (SC-004).
- **Ensayo local de los tres trabajos del CI** (mismos comandos que el workflow): `uv sync --group dev
  --locked` 0,2 s, `ruff format --check` 0,3 s, `ruff check` 0,3 s, `uv run pytest` ~41 s y el escaneo
  0,5 s: todos con salida 0. El tiempo del CI real (que instala desde cero) se anota en §6.
- **§5 Persona nueva (SC-003)**: clon limpio desde GitHub en un directorio vacío, con los archivos
  nuevos de esta feature superpuestos y sin `ANTHROPIC_API_KEY`: `git clone` 1,4 s · `uv sync --group
  dev` 2,8 s · `uv run pytest` 66 s (1310 pasan) · interfaz respondiendo en `/api/casos` 3,1 s →
  **92 s en total**. Con la caché de `uv` caliente; con descarga completa de dependencias dominaría
  `uv sync` y dependería de la red. **Hallazgo**: la primera medición falló 2 tests del plugin (#10),
  porque en un clon con `autocrlf` los archivos ya traen `\r\n` y el control de fin de línea los
  duplicaba a `\r\r\n`; corregido en `.claude/hooks/test_plugin_devkit.py` (`a_crlf`) y repetida la
  medición en verde. Pasaba en el árbol de trabajo porque sus archivos tenían `\n`.
- **§7 Historial**: 27 commits y 276 archivos distintos revisados, 32.246 líneas añadidas: ningún
  archivo de entorno o de secretos versionado alguna vez y ninguna credencial (script temporal, no
  versionado).

**Pendiente**: §6, la ejecución real del CI en GitHub (T023), que requiere publicar una rama y abrir
un PR de prueba con confirmación del usuario.
