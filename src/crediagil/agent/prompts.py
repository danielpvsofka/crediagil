"""Prompts del orquestador y del extractor (spec 007, FR-017).

Solo guían el juicio: las reglas de negocio no se escriben aquí (Principio II). Un test garantiza
que la tasa y los umbrales no aparezcan. La sección de esquemas del extractor se genera desde los
modelos de `crediagil.extraction`, para que nunca se desincronice de lo que valida el core.
"""

from __future__ import annotations

from importlib.resources import files

from crediagil.extraction.schemas import CertificadoLaboral, DocumentoNoSoportado, ExtractoBancario

# Aclaraciones de formato por campo (el nombre de los campos sale del modelo).
_FORMATO = {
    "salario_mensual": "entero en pesos, sin puntos ni símbolos",
    "fecha_expedicion": "AAAA-MM-DD",
    "abonos_nomina": "lista de {valor, fragmento}, uno por abono",
    "moneda": "la moneda que menciona el documento junto al monto",
}


def _cargar(nombre: str) -> str:
    return files("crediagil.agent").joinpath("prompts", nombre).read_text(encoding="utf-8")


def _esquemas() -> str:
    lineas = []
    for modelo in (CertificadoLaboral, ExtractoBancario, DocumentoNoSoportado):
        campos = [c for c in modelo.model_fields if c != "tipo"]
        tipo = modelo.model_fields["tipo"].annotation.__args__[0]
        detalle = ", ".join(f"`{c}` ({_FORMATO[c]})" if c in _FORMATO else f"`{c}`" for c in campos)
        lineas.append(f'- `tipo: "{tipo}"`: {detalle}')
    return "\n".join(lineas)


_INTRO_ESQUEMAS = (
    "\n## Esquemas\n\n"
    "`datos` lleva `tipo` y los campos de ese tipo, y nada más (las claves desconocidas se "
    'rechazan). Cada campo es `{"valor": ..., "fragmento": "<texto literal del documento>"}`. '
    "Incluye todos los campos que el documento contenga; los que no, omítelos.\n\n"
)

PROMPT_ORQUESTADOR = _cargar("orquestador.md")
PROMPT_EXTRACTOR = _cargar("extractor.md") + _INTRO_ESQUEMAS + _esquemas() + "\n"
