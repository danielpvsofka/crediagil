# Quickstart: validar política y extracción

## Prerrequisitos

```bash
uv sync --group dev        # instala pydantic (dependencia) y pytest/ruff
```

## Validación automática

```bash
uv run pytest src          # política, extracción e ingreso verificado
uv run pytest              # suite completa (incluye hooks de #1 y #2)
uv run ruff check
```

Esperado: todo en verde. Los casos de borde están en
[contracts/policy.md](./contracts/policy.md) y [contracts/extraction.md](./contracts/extraction.md).

## Comprobaciones rápidas

| # | Comprobación | Esperado |
|---|--------------|----------|
| 1 | `uv run python -c "from crediagil.policy.cuota import calcular_cuota; print(calcular_cuota(4_000_000, 24))"` | `206723` |
| 2 | Cambiar `TASA_MENSUAL` en `params.py` y ejecutar `uv run pytest src -k params` | Falla: no coincide con la constitución. Revertir. |
| 3 | `grep -rn "0.018\|5_000_000\|0.30\|0.10" src --include=*.py \| grep -v test_ \| grep -v params.py` | Sin resultados (FR-001: única fuente) |
| 4 | Validar un certificado ficticio con un fragmento que no está en el texto | `ValidationError` que nombra el campo |
| 5 | `derivar_ingreso` con extractos y sin certificado | `ingreso=None` y hallazgo `DATO_FALTANTE` |
