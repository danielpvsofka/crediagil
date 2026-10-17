"""Extracción de documentos: esquemas validados e ingreso verificado."""

from crediagil.extraction.income import (
    Hallazgo,
    IngresoVerificado,
    ResultadoIngreso,
    TipoHallazgo,
    derivar_ingreso,
    resultado_de_hallazgos,
)
from crediagil.extraction.schemas import (
    CampoExtraido,
    CertificadoLaboral,
    Documento,
    DocumentoNoSoportado,
    ExtractoBancario,
    validar_documento,
)

__all__ = [
    "CampoExtraido",
    "CertificadoLaboral",
    "Documento",
    "DocumentoNoSoportado",
    "ExtractoBancario",
    "Hallazgo",
    "IngresoVerificado",
    "ResultadoIngreso",
    "TipoHallazgo",
    "derivar_ingreso",
    "resultado_de_hallazgos",
    "validar_documento",
]
