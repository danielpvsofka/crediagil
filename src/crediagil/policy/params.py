"""Parámetros de la política de crédito.

Única definición en código: el resto del paquete, el servidor MCP y los hooks los importan de
aquí. Deben coincidir con la constitución (Principio I); `test_params.py` lo verifica. Solo
cambian mediante enmienda MAJOR de la constitución.
"""

from __future__ import annotations

from decimal import Decimal

TASA_MENSUAL = Decimal("0.018")
MONTO_MAXIMO_PREAPROBACION = 5_000_000
PROPORCION_MAXIMA_CUOTA_INGRESO = Decimal("0.30")
DISCREPANCIA_MAXIMA_INGRESO = Decimal("0.10")

# Plazos permitidos en meses (spec 003, FR-004).
PLAZO_MINIMO_MESES = 6
PLAZO_MAXIMO_MESES = 60

MONEDA = "COP"
