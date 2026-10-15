"""PreToolUse: bloquea contenido con forma de tarjeta, documento de identidad o cuenta real.

Principio III (datos exclusivamente ficticios). Una línea con `pragma: dato-ficticio` queda
exenta (FR-010a).
"""

from __future__ import annotations

import re

from _hooklib import HookInputError, allow, block, new_content, read_event

HOOK = "block_sensitive_data"
PRAGMA = "pragma: dato-ficticio"

# 13–19 dígitos con espacios o guiones opcionales entre ellos, como token propio: dígitos
# incrustados en hashes hex o identificadores alfanuméricos no cuentan.
CARD_RE = re.compile(r"(?<![\w])\d(?:[ -]?\d){12,18}(?![\w])")
# Etiqueta, hasta 30 caracteres sin dígitos en la misma línea, y el número.
DOCUMENT_RE = re.compile(
    r"(?i)(?<![\w.])(c[ée]dula|c\.\s?c\.?|cc|nit|documento|doc)\b[^\d\n]{0,30}?(\d[\d.\-]*\d)"
)
ACCOUNT_RE = re.compile(
    r"(?i)(?<![\w.])(cuenta|cta|ahorros|corriente|account)\b[^\d\n]{0,30}?(\d[\d.\-]*\d)"
)


def luhn_valid(digits: str) -> bool:
    total = 0
    for index, char in enumerate(reversed(digits)):
        digit = int(char)
        if index % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def looks_like_card(raw: str) -> bool:
    groups = re.split(r"[ -]", raw)
    # Con separadores, solo grupos de 3–6 dígitos (formato de tarjeta), no números sueltos.
    if len(groups) > 1 and any(not 3 <= len(group) <= 6 for group in groups):
        return False
    digits = "".join(groups)
    # Primer dígito 2–6 (rangos IIN comunes): evita timestamps en ms, que empiezan por 1.
    return 13 <= len(digits) <= 19 and digits[0] in "23456" and luhn_valid(digits)


def mask(digits: str) -> str:
    return "••••" + digits[-4:]


def find_in_line(line: str) -> list[tuple[str, str]]:
    findings: list[tuple[str, str]] = []
    for match in CARD_RE.finditer(line):
        if looks_like_card(match.group()):
            findings.append(("tarjeta", re.sub(r"\D", "", match.group())))
    for kind, pattern, low, high in (
        ("documento", DOCUMENT_RE, 6, 10),
        ("cuenta", ACCOUNT_RE, 9, 20),
    ):
        for match in pattern.finditer(line):
            digits = re.sub(r"\D", "", match.group(2))
            if low <= len(digits) <= high:
                findings.append((kind, digits))
    return findings


def main() -> None:
    try:
        event = read_event()
    except HookInputError as exc:
        block(HOOK, f"Evento inválido, se bloquea por seguridad: {exc}")

    messages = []
    for text in new_content(event):
        for number, line in enumerate(text.splitlines(), start=1):
            if PRAGMA in line:
                continue
            # Una cuenta puede llevar varias etiquetas ("cuenta de ahorros"): un hallazgo por número.
            for kind, digits in dict.fromkeys(find_in_line(line)):
                messages.append(f"{kind} en línea {number}: {mask(digits)}")
    if messages:
        block(
            HOOK,
            "El contenido tiene datos con forma real (Principio III):\n  - "
            + "\n  - ".join(messages)
            + "\nUsa datos ficticios generados o marca la línea con '# pragma: dato-ficticio'.",
        )
    allow()


if __name__ == "__main__":
    main()
