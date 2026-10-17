# Quickstart: validar las herramientas de originación

## Prerrequisitos

```bash
uv sync --group dev        # sin dependencias nuevas
```

## Validación automática

```bash
uv run pytest src/crediagil   # política, extracción y servidor MCP
uv run pytest                 # suite completa
uv run ruff check
```

Casos en [contracts/tools.md](./contracts/tools.md).

## Flujo manual (cliente MCP)

Con el servidor registrado en un cliente MCP (ver quickstart de #4) y datos ficticios:

| # | Paso | Esperado |
|---|------|----------|
| 1 | `calcular_capacidad_pago` (4.000.000, 24) | `cuota: 206723`; `.data/core_estado.json` sin cambios |
| 2 | `registrar_solicitud` sin verificar identidad | `permisos` `IDENTIDAD_NO_VERIFICADA` |
| 3 | `buscar_solicitante` → `verificar_identidad` → `registrar_solicitud` con un certificado ficticio válido | `id_solicitud` y evaluación |
| 4 | `preaprobar_credito` con ese `id_solicitud` | `PREAPROBADA` si la evaluación lo era; si no, `NO_PREAPROBABLE` |
| 5 | `escalar_a_analista` con un resumen al que le falta `accion_recomendada` | `RESUMEN_INCOMPLETO` con el campo |
| 6 | Revisar `.data/core_estado.json` | la solicitud tiene cada dato con `id_documento` y `fragmento` |
