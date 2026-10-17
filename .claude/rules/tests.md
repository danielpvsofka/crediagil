---
paths:
  - "**/test_*.py"
  - "**/*_test.py"
  - "tests/**"
---

# Reglas para tests

- pytest, ejecutado con `uv run pytest`. Los tests viven junto al código que prueban.
- Cada regla de negocio de la constitución (Principio I) se prueba en sus bordes: exactamente
  en el umbral, justo por debajo y justo por encima. Además se cubren identidad no verificada,
  solicitud de humano y caso fuera de política.
- Los tests de hooks ejecutan el hook como subproceso con el evento JSON por stdin (fixture
  `run_hook` de `.claude/hooks/conftest.py`) y verifican código de salida y stderr.
- Solo datos ficticios. Los números con forma de tarjeta se generan en tiempo de ejecución
  (`luhn_valid_number`). Las cédulas o cuentas literales llevan `pragma: dato-ficticio` en la
  misma línea.
- Sin red, sin secretos y sin depender de variables de entorno reales.
