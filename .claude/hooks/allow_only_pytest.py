"""PreToolUse (Bash) del subagente compliance-reviewer: solo permite ejecutar pytest.

El campo `tools` de un subagente no admite `Bash(prefijo:*)`, así que la restricción se aplica
aquí. Se registra en el frontmatter de `.claude/agents/compliance-reviewer.md`, no en
`settings.json`: solo aplica a ese subagente. Se bloquea cualquier encadenamiento,
redirección o sustitución para que "pytest" no sirva de prefijo para otro comando.
"""

from __future__ import annotations

from _hooklib import HookInputError, allow, block, read_event

HOOK = "allow_only_pytest"
ALLOWED_PREFIXES = ("pytest", "uv run pytest")
FORBIDDEN = (";", "&", "|", "`", "$(", ">", "<", "\n")


def is_pytest(command: str) -> bool:
    command = command.strip()
    if any(token in command for token in FORBIDDEN):
        return False
    return any(command == p or command.startswith(p + " ") for p in ALLOWED_PREFIXES)


def main() -> None:
    try:
        event = read_event()
        command = event["tool_input"].get("command")
        if not isinstance(command, str):
            raise HookInputError("falta tool_input.command")
    except HookInputError as exc:
        block(HOOK, f"Evento inválido, se bloquea por seguridad: {exc}")

    if not is_pytest(command):
        block(HOOK, f"compliance-reviewer solo puede ejecutar pytest: {command!r}")
    allow()


if __name__ == "__main__":
    main()
