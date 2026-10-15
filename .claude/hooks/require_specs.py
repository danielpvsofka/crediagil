"""PreToolUse: bloquea cambios en src/ si la feature activa no tiene spec, plan y tareas.

Feature activa: `.specify/feature.json` → `feature_directory` (Principio IV).
"""

from __future__ import annotations

import json

from _hooklib import HookInputError, allow, block, is_under, project_root, read_event, target_path

HOOK = "require_specs"
REQUIRED_DOCS = ("spec.md", "plan.md", "tasks.md")
NO_FEATURE = (
    "No hay feature activa: ejecuta /speckit-specify o define feature_directory en "
    ".specify/feature.json antes de modificar src/."
)


def main() -> None:
    try:
        event = read_event()
    except HookInputError as exc:
        block(HOOK, f"Evento inválido, se bloquea por seguridad: {exc}")

    root = project_root(event)
    path = target_path(event)
    if path is None or not is_under(path, root, "src"):
        allow()

    try:
        data = json.loads((root / ".specify" / "feature.json").read_text(encoding="utf-8"))
        feature_dir = data["feature_directory"]
    except (OSError, ValueError, TypeError, KeyError):
        block(HOOK, NO_FEATURE)
    if not isinstance(feature_dir, str) or not (root / feature_dir).is_dir():
        block(HOOK, NO_FEATURE)

    missing = []
    for name in REQUIRED_DOCS:
        doc = root / feature_dir / name
        try:
            if not doc.read_text(encoding="utf-8").strip():
                missing.append(f"{name} (vacío)")
        except OSError:
            missing.append(name)
    if missing:
        block(
            HOOK,
            f"La feature activa '{feature_dir}' no tiene: {', '.join(missing)}. "
            "Completa /speckit-specify → /speckit-plan → /speckit-tasks antes de modificar src/.",
        )
    allow()


if __name__ == "__main__":
    main()
