---
paths:
  - ".claude/hooks/**"
---

# Reglas para hooks de Claude Code

- Solo biblioteca estándar de Python; reutiliza `_hooklib.py` (`read_event`, `block`,
  `allow`, …).
- Un hook de bloqueo falla de forma segura: entrada malformada → salida 2 con motivo en stderr
  prefijado `[<hook>]`. Los hooks PostToolUse nunca salen con 2.
- Cada hook tiene `test_<hook>.py` en este mismo directorio, que lo ejecuta como subproceso
  con el evento JSON por stdin.
- Todo hook nuevo se registra en `.claude/settings.json` con
  `uv run --no-project python "$CLAUDE_PROJECT_DIR/.claude/hooks/<hook>.py"` y se documenta en
  la tabla de hooks de `CLAUDE.md`.
