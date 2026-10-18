# Research: Servidor MCP: herramientas de originación

Decisiones de la Fase 0. No quedan `NEEDS CLARIFICATION`: FR-005 se aclaró en la spec con la
opción A. Este trabajo extiende el servidor de #4 y reutiliza la política y la extracción de #3.

## R1. Regla de reintento (FR-001a)

- **Decision**: `ErrorCore` acepta un `reintentable` explícito.
  - Por defecto es `True` solo para `transitorio`.
  - Se permite `reintentable=True` con `tipo=validacion` solo para los códigos `EXTRACCION_INVALIDA` y `FRAGMENTO_NO_LITERAL`. Cualquier otro intento lanza `ValueError` al construir el error, de modo que la regla se cumple en código.
  - `negocio` y `permisos` nunca son reintentables.
- **Cambios a #4**: hay que actualizar `test_errores.py` y `contracts/tools.md` de #4 (fila de la tabla de tipos).

## R2. Distinguir los errores de extracción

- **Decision**: en `crediagil/extraction/schemas.py` (#3), el validador de fragmentos lanza `PydanticCustomError("fragmento_no_literal", mensaje, {"campo": nombre})` en lugar de `ValueError`. Así el tipo de error es estable y no hay que interpretar el texto del mensaje.
  - "Falta el texto del documento" usa `PydanticCustomError("texto_faltante", ...)`.
  - `crediagil.mcp_server.originacion.extraer(datos, texto)` convierte el `ValidationError`:
    - si algún error es `fragmento_no_literal`, el resultado es `FRAGMENTO_NO_LITERAL` con `detalles.campos`;
    - si no, `EXTRACCION_INVALIDA` con `detalles.errores = [{campo: "a.b", motivo: msg}]`.
  - Ambos son `validacion` y reintentables.
- **Rationale**: los tests de #3 ya buscan el nombre del campo en el mensaje, y el mensaje no cambia.

## R3. Constancia de verificación (FR-007)

- **Decision**: cuando `verificar_identidad` (#4) tiene éxito, guarda `verificado_en` en ISO-8601 UTC dentro del solicitante. Al bloquear, se borra (`None`).
- "Identidad vigente" significa `verificado_en` no nulo y `bloqueado == False`. No caduca por tiempo (supuesto de la spec).
- La comprueba una sola función, `identidad_vigente(solicitante)`, que usan el registro y la preaprobación.

## R4. Esquema del estado v2

- **Decision**: el archivo pasa a `version: 2`:

  ```text
  {"version": 2, "solicitantes": {...}, "solicitudes": {"SLC-0001": {...}}, "escalamientos": {"ESC-0001": {...}}}
  ```

  - Al cargar un archivo v1, `AlmacenEstado` añade las colecciones vacías y `verificado_en: null`. Es una migración en memoria que se persiste en la siguiente escritura. Así no se pierde el estado de quien ya tenía `.data/`.
  - Los identificadores son secuenciales (`SLC-NNNN`, `ESC-NNNN`), calculados dentro de la transacción como `max + 1`.

## R5. Registro y evaluación

- **Decision**: `registrar_solicitud(almacen, id_solicitante, monto, plazo_meses, ingreso_declarado, documentos)`. Cada documento es `{id_documento, datos, texto}`, con el tipo dentro de `datos`.
  1. Valida las entradas: monto y plazo con `crediagil.policy`, e ingreso declarado como entero ≥ 0. Un error aquí es `validacion` no reintentable.
  2. Valida todas las extracciones (R2). Un error es reintentable y no se guarda nada.
  3. Llama a `derivar_ingreso`. Si no hay ingreso verificado y no hay hallazgo `FUERA_DE_POLITICA`, responde `negocio` `INGRESO_NO_VERIFICABLE` (no reintentable) con `detalles.datos_faltantes = [campo…]`, sin guardar nada.
  4. Evalúa con `combinar(evaluar_preaprobacion, evaluar_discrepancia si hay ingreso, resultado_de_hallazgos)`.
  5. Dentro de una sola transacción comprueba la identidad vigente. Si no lo está, responde `permisos` `IDENTIDAD_NO_VERIFICADA`. Si lo está, guarda la solicitud.

  Entre los pasos 1–4 y la escritura no se toca el estado: se calcula todo y se escribe una vez.
- **Datos con procedencia**: se guarda una lista plana `{documento_tipo, campo, valor, id_documento, fragmento}` por cada `CampoExtraido` no nulo, incluidos los de listas (`abonos_nomina[0]`). El valor se serializa en JSON con `model_dump(mode="json")`.
- **Evaluación** devuelta y guardada:

  ```text
  {preaprobable_automaticamente, decision, cuota, causas_escalamiento: [{regla, mensaje, valores}]}
  ```

  Las causas son los `Motivo` del `Resultado` combinado.
- **Orden de comprobaciones**: la identidad se revisa **primero** (antes de validar extracciones), para no revelar nada a quien no tiene identidad vigente. La revisión se repite dentro de la transacción de escritura, para cubrir el caso de que el solicitante se haya bloqueado entre medias.

## R6. Preaprobación con revalidación (FR-014)

- **Decision**: `preaprobar_credito(almacen, id_solicitud)` hace todo en una transacción:
  1. Si la solicitud no existe: `negocio` `SOLICITUD_NO_ENCONTRADA`.
  2. Si está `ESCALADA`: `negocio` `SOLICITUD_ESCALADA`.
  3. Si ya está `PREAPROBADA`: responde `ok` con el mismo resultado guardado (idempotente).
  4. Si la identidad del solicitante no está vigente: `permisos` `IDENTIDAD_NO_VERIFICADA`.
  5. Recalcula con los datos guardados: `combinar(evaluar_preaprobacion(monto, plazo, ingreso_verificado), evaluar_discrepancia(...), resultado de los hallazgos guardados)`. Si la decisión no es `PREAPROBABLE`: `negocio` `NO_PREAPROBABLE` con las causas.
  6. Si todo se cumple: `estado = PREAPROBADA`, con `preaprobada_en`, y responde `{id_solicitud, monto, plazo_meses, cuota, tasa_mensual}`. La tasa sale de `crediagil.policy.params` y se serializa como texto.
- **Rationale**: no confía en la evaluación guardada; recalcula con la política vigente (defensa en profundidad).

## R7. Simulación (FR-012)

- **Decision**: `calcular_capacidad_pago(monto, plazo_meses, ingreso_mensual=None)` devuelve `{cuota, tasa_mensual, proporcion_cuota_ingreso?, dentro_de_proporcion_maxima?}`.
  - La proporción se redondea a 4 decimales y se devuelve como texto.
  - No lee ni escribe estado; solo valida las entradas.
  - Las fallas inyectadas se aplican igual, porque son de la envoltura.

## R8. Escalamiento (FR-016–FR-018)

- **Decision**: un modelo Pydantic `ResumenEscalamiento` con `extra="forbid"` y estos campos:
  - `solicitante` (str no vacío);
  - `monto` (int > 0 o null) y `plazo` (int o null);
  - `datos` (lista de `{campo, valor, documento, fragmento}`, todos obligatorios y no vacíos salvo `valor`, que no puede ser null);
  - `discrepancias` (lista de str);
  - `causa` (Literal de los 8 valores);
  - `detalle` y `accion_recomendada` (str no vacíos).

  Todos son **obligatorios como clave**: `Field(...)` sin valor por defecto, admitiendo `None` donde aplica.
  - Si falta cualquier clave o alguna es inválida: `validacion` `RESUMEN_INCOMPLETO` con `detalles.campos_faltantes`.
  - `escalar_a_analista(almacen, resumen, id_solicitud=None)`:
    - si hay solicitud, debe existir y no estar `PREAPROBADA`; si está preaprobada responde `negocio` `SOLICITUD_PREAPROBADA`;
    - guarda el escalamiento y pasa la solicitud a `ESCALADA`.
  - No requiere identidad: la regla 4 exige escalar de inmediato, incluso sin identidad verificada.

## R9. Descripciones (FR-012, FR-013)

- **Decision**: las descripciones son constantes en `server.py` y un test exige los textos literales.
  - `calcular_capacidad_pago` empieza con "SOLO SIMULA: …no registra, no preaprueba y no compromete a Crediágil; no requiere identidad."
  - `preaprobar_credito` empieza con "COMPROMETE A CREDIÁGIL: …úsala solo si registrar_solicitud devolvió preaprobable_automaticamente: true; para simular cuotas usa calcular_capacidad_pago."
  - `registrar_solicitud` y `escalar_a_analista` explican cuándo escalar (`.claude/rules/mcp-server.md`).

## R10. Organización y tests

- **Decision**:
  - Lógica nueva en `crediagil/mcp_server/originacion.py` (extraer, registrar, simular, preaprobar) y `escalamiento.py`; `server.py` registra las 5 herramientas con la envoltura `_responder` de #4.
  - Tests junto al código, con documentos ficticios construidos en tiempo de ejecución y marcador `dato-ficticio` donde haga falta.
  - Bordes de las reglas 2 y 3 vistos desde registro y preaprobación: monto en el tope y +1, cuota 30% exacto y +1, discrepancia 10% exacto y +1.
  - La prueba de extremo a extremo de #4 se amplía: lista 7 herramientas.
