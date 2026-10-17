"""Tests de los esquemas de extracción: contracts/extraction.md §schemas (Principios V y VI).

Todos los documentos son ficticios.
"""

from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError

from crediagil.extraction.schemas import (
    CertificadoLaboral,
    Documento,
    DocumentoNoSoportado,
    ExtractoBancario,
    validar_documento,
)

TEXTO_CERTIFICADO = (
    "Empresa Ficticia S.A.S. certifica que Ana Prueba labora con nosotros desde 2020 "
    "y devenga un salario de $2.500.000 COP mensuales. "
    "Se expide en Bogotá el 30 de septiembre de 2026."
)

TEXTO_EXTRACTO = (
    "Banco Imaginario - Extracto de septiembre 2026. Titular: Ana Prueba. Moneda: COP.\n"
    "05/09 ABONO NOMINA EMPRESA FICTICIA 2.500.000\n"
    "20/09 ABONO NOMINA EMPRESA FICTICIA 2.500.000\n"
)


def campo(valor, fragmento):
    return {"valor": valor, "fragmento": fragmento}


def certificado(**cambios):
    datos = {
        "tipo": "certificado_laboral",
        "empleador": campo("Empresa Ficticia S.A.S.", "Empresa Ficticia S.A.S."),
        "nombre_empleado": campo("Ana Prueba", "Ana Prueba"),
        "salario_mensual": campo(2_500_000, "un salario de $2.500.000 COP mensuales"),
        "moneda": campo("COP", "$2.500.000 COP"),
        "fecha_expedicion": campo("2026-09-30", "30 de septiembre de 2026"),
    }
    datos.update(cambios)
    return datos


def extracto(**cambios):
    datos = {
        "tipo": "extracto_bancario",
        "titular": campo("Ana Prueba", "Titular: Ana Prueba"),
        "periodo": campo("2026-09", "Extracto de septiembre 2026"),
        "moneda": campo("COP", "Moneda: COP"),
        "abonos_nomina": [
            campo(2_500_000, "05/09 ABONO NOMINA EMPRESA FICTICIA 2.500.000"),
            campo(2_500_000, "20/09 ABONO NOMINA EMPRESA FICTICIA 2.500.000"),
        ],
    }
    datos.update(cambios)
    return datos


class TestCamposValidos:
    def test_certificado_completo_y_literal(self):
        doc = validar_documento(certificado(), TEXTO_CERTIFICADO)
        assert isinstance(doc, CertificadoLaboral)
        assert doc.salario_mensual.valor == 2_500_000
        assert doc.salario_mensual.fragmento in TEXTO_CERTIFICADO
        assert doc.fecha_expedicion.valor.year == 2026

    def test_extracto_con_abonos(self):
        doc = validar_documento(extracto(), TEXTO_EXTRACTO)
        assert isinstance(doc, ExtractoBancario)
        assert [a.valor for a in doc.abonos_nomina] == [2_500_000, 2_500_000]

    def test_extracto_sin_abonos(self):
        doc = validar_documento(extracto(abonos_nomina=[]), TEXTO_EXTRACTO)
        assert doc.abonos_nomina == []

    def test_campo_ausente_queda_nulo(self):
        doc = validar_documento(certificado(salario_mensual=None), TEXTO_CERTIFICADO)
        assert doc.salario_mensual is None

    def test_campo_omitido_queda_nulo(self):
        datos = certificado()
        del datos["fecha_expedicion"]
        assert validar_documento(datos, TEXTO_CERTIFICADO).fecha_expedicion is None

    def test_documento_no_soportado(self):
        doc = validar_documento(
            {"tipo": "no_soportado", "tipo_detectado": "pasaporte"}, "texto cualquiera"
        )
        assert isinstance(doc, DocumentoNoSoportado)
        assert doc.tipo_detectado == "pasaporte"


class TestCamposRechazados:
    def test_valor_sin_fragmento(self):
        with pytest.raises(ValidationError, match="fragmento"):
            validar_documento(certificado(salario_mensual={"valor": 2_500_000}), TEXTO_CERTIFICADO)

    def test_fragmento_vacio(self):
        with pytest.raises(ValidationError):
            validar_documento(certificado(salario_mensual=campo(2_500_000, "")), TEXTO_CERTIFICADO)

    def test_fragmento_solo_espacios(self):
        with pytest.raises(ValidationError, match="fragmento"):
            validar_documento(certificado(salario_mensual=campo(2_500_000, " ")), TEXTO_CERTIFICADO)

    @pytest.mark.parametrize("valor", [0, -2_500_000, True, "2500000", 2_500_000.0])
    def test_salario_no_entero_positivo(self, valor):
        with pytest.raises(ValidationError, match="salario_mensual"):
            validar_documento(
                certificado(salario_mensual=campo(valor, "$2.500.000")), TEXTO_CERTIFICADO
            )

    @pytest.mark.parametrize("valor", [0, -1])
    def test_abono_no_positivo(self, valor):
        abonos = [campo(valor, "ABONO NOMINA EMPRESA FICTICIA 2.500.000")]
        with pytest.raises(ValidationError, match="abonos_nomina"):
            validar_documento(extracto(abonos_nomina=abonos), TEXTO_EXTRACTO)

    def test_fragmento_sin_valor(self):
        with pytest.raises(ValidationError, match="valor"):
            validar_documento(
                certificado(salario_mensual={"fragmento": "$2.500.000"}), TEXTO_CERTIFICADO
            )

    @pytest.mark.parametrize(
        "fragmento",
        [
            "un salario de  $2.500.000 COP mensuales",  # espacio de más
            "Un salario de $2.500.000 COP mensuales",  # mayúscula distinta
            "un salario de $3.000.000 COP mensuales",  # inventado
        ],
    )
    def test_fragmento_no_literal_nombra_el_campo(self, fragmento):
        with pytest.raises(ValidationError, match="salario_mensual"):
            validar_documento(
                certificado(salario_mensual=campo(2_500_000, fragmento)), TEXTO_CERTIFICADO
            )

    def test_fragmento_no_literal_en_lista(self):
        abonos = [campo(9_000_000, "ABONO NOMINA 9.000.000")]
        with pytest.raises(ValidationError, match="abonos_nomina"):
            validar_documento(extracto(abonos_nomina=abonos), TEXTO_EXTRACTO)

    def test_campo_extra(self):
        salario = {**campo(2_500_000, "$2.500.000"), "confianza": 0.9}
        with pytest.raises(ValidationError):
            validar_documento(certificado(salario_mensual=salario), TEXTO_CERTIFICADO)

    @pytest.mark.parametrize("tipo_detectado", ["", "   "])
    def test_no_soportado_sin_tipo_detectado(self, tipo_detectado):
        with pytest.raises(ValidationError, match="tipo_detectado"):
            validar_documento({"tipo": "no_soportado", "tipo_detectado": tipo_detectado}, "")

    def test_tipo_desconocido(self):
        with pytest.raises(ValidationError):
            validar_documento({"tipo": "pasaporte"}, "texto")

    def test_sin_texto_del_documento(self):
        with pytest.raises(ValidationError, match="falta el texto del documento"):
            CertificadoLaboral.model_validate(certificado())


def test_json_schema_para_el_extractor():
    esquema = TypeAdapter(Documento).json_schema()
    tipos = {opcion["$ref"].rsplit("/", 1)[-1] for opcion in esquema["oneOf"]}
    assert tipos == {"CertificadoLaboral", "ExtractoBancario", "DocumentoNoSoportado"}
