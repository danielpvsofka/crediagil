"""PreToolUse (Bash/PowerShell): bloquea comandos que mencionen archivos de secretos.

Complementa `permissions.deny`, que solo cubre las herramientas de archivo. Se bloquea toda
mención de `.env*` o `secrets/`, no una lista de comandos: las formas de leer un archivo desde
una terminal son ilimitadas.
"""

from __future__ import annotations

import re

from _hooklib import HookInputError, allow, block, read_event

HOOK = "block_secret_access"
BOUNDARY = r"""(?:^|[\s/\\'"=<>|;&(])"""
SECRET_RE = re.compile(
    BOUNDARY + r"""\.env(?:\.[\w.-]+)?(?=$|[\s'"|;&)<>])""" + "|" + BOUNDARY + r"secrets[/\\]"
)


def main() -> None:
    try:
        event = read_event()
        command = event["tool_input"].get("command")
        if not isinstance(command, str):
            raise HookInputError("falta tool_input.command")
    except HookInputError as exc:
        block(HOOK, f"Evento inválido, se bloquea por seguridad: {exc}")

    if SECRET_RE.search(command):
        block(
            HOOK,
            "Acceso a archivos de secretos bloqueado (.env*, secrets/). "
            "Pide al usuario el valor que necesites.",
        )
    allow()


if __name__ == "__main__":
    main()
