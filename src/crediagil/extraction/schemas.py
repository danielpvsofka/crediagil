"""Esquemas de extracción de documentos (Principios V y VI).

Cada dato extraído es `{valor, fragmento}` y el fragmento debe aparecer literalmente en el texto
del documento. Lo que el documento no contiene queda `None` (dato faltante), nunca estimado.
El texto se pasa como contexto de validación: sin él, la validación falla.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    ValidationInfo,
    field_validator,
    model_validator,
)
from pydantic_core import PydanticCustomError

# Montos en pesos: enteros estrictos y positivos (sin booleanos, decimales ni texto).
Pesos = Annotated[int, Field(strict=True, gt=0)]


class CampoExtraido[T](BaseModel):
    """Un dato extraído y el fragmento literal del documento del que sale."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    valor: T
    fragmento: str = Field(min_length=1)

    @field_validator("fragmento")
    @classmethod
    def fragmento_con_contenido(cls, fragmento: str) -> str:
        if not fragmento.strip():
            raise ValueError("el fragmento no puede estar vacío ni ser solo espacios")
        return fragmento


class DocumentoBase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def fragmentos_literales(self, info: ValidationInfo):
        campos = list(self.campos_extraidos())
        if not campos:
            return self
        texto = (info.context or {}).get("texto")
        if not isinstance(texto, str):
            # Tipos de error propios y estables (spec 005 R2): quien valida los distingue sin
            # interpretar el mensaje.
            raise PydanticCustomError(
                "texto_faltante", "falta el texto del documento para validar los fragmentos"
            )
        for nombre, campo in campos:
            if campo.fragmento not in texto:
                raise PydanticCustomError(
                    "fragmento_no_literal",
                    "El fragmento de '{campo}' no aparece literalmente en el documento: "
                    "{fragmento}",
                    {"campo": nombre, "fragmento": repr(campo.fragmento)},
                )
        return self

    def campos_extraidos(self):
        """Pares (nombre, CampoExtraido) no nulos, incluidos los de listas (`abonos_nomina[0]`)."""
        for nombre in type(self).model_fields:
            valor = getattr(self, nombre)
            if isinstance(valor, CampoExtraido):
                yield nombre, valor
            elif isinstance(valor, list):
                for indice, elemento in enumerate(valor):
                    if isinstance(elemento, CampoExtraido):
                        yield f"{nombre}[{indice}]", elemento


class CertificadoLaboral(DocumentoBase):
    tipo: Literal["certificado_laboral"]
    empleador: CampoExtraido[str] | None = None
    nombre_empleado: CampoExtraido[str] | None = None
    salario_mensual: CampoExtraido[Pesos] | None = None
    moneda: CampoExtraido[str] | None = None
    fecha_expedicion: CampoExtraido[date] | None = None


class ExtractoBancario(DocumentoBase):
    tipo: Literal["extracto_bancario"]
    titular: CampoExtraido[str] | None = None
    periodo: CampoExtraido[str] | None = None
    moneda: CampoExtraido[str] | None = None
    abonos_nomina: list[CampoExtraido[Pesos]] = Field(default_factory=list)


class DocumentoNoSoportado(DocumentoBase):
    """Tipo de documento que la política no cubre (regla 5): siempre escala."""

    tipo: Literal["no_soportado"]
    # Al menos un carácter que no sea espacio.
    tipo_detectado: str = Field(min_length=1, pattern=r"\S")


Documento = Annotated[
    CertificadoLaboral | ExtractoBancario | DocumentoNoSoportado,
    Field(discriminator="tipo"),
]

_ADAPTADOR = TypeAdapter(Documento)


def validar_documento(
    datos: dict, texto: str
) -> CertificadoLaboral | ExtractoBancario | DocumentoNoSoportado:
    """Valida una extracción contra el texto completo del documento del que se obtuvo."""
    return _ADAPTADOR.validate_python(datos, context={"texto": texto})
