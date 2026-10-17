"""Tests de originación: contracts/tools.md de spec 005 (FR-003–FR-015, FR-019).

Documentos 100% ficticios construidos en tiempo de ejecución. Los bordes de las reglas 2 y 3 se
prueban desde el registro y la preaprobación (Principio VII).
"""

from __future__ import annotations

from datetime import date

import pytest

from crediagil.extraction.schemas import CertificadoLaboral, DocumentoNoSoportado
from crediagil.mcp_server.conftest import doc_certificado, doc_extracto
from crediagil.mcp_server.errores import ErrorCore, TipoError
from crediagil.mcp_server.estado import AlmacenEstado
from crediagil.mcp_server.identidad import verificar_identidad
from crediagil.mcp_server.originacion import (
    extraer,
    preaprobar_credito,
    registrar_solicitud,
    simular,
)
from crediagil.mcp_server.semilla import SOLICITANTES_SEMILLA

ANA = SOLICITANTES_SEMILLA[0]
HOY = date(2026, 10, 17)
# Cuota de 5.000.000 a 12 meses = 467.010; el 30% exacto corresponde a 1.556.700.
INGRESO_30_EXACTO = 1_556_700


def error_de(funcion, *args, **kwargs) -> ErrorCore:
    with pytest.raises(ErrorCore) as info:
        funcion(*args, **kwargs)
    return info.value


@pytest.fixture
def almacen(tmp_path):
    return AlmacenEstado(tmp_path / "estado.json")


@pytest.fixture
def verificado(almacen):
    verificar_identidad(almacen, ANA["id_solicitante"], ANA["fecha_nacimiento"], hoy=HOY)
    return almacen


def registrar(almacen, monto=4_000_000, plazo=24, declarado=2_000_000, documentos=None):
    documentos = documentos if documentos is not None else [doc_certificado()]
    return registrar_solicitud(almacen, ANA["id_solicitante"], monto, plazo, declarado, documentos)


def causas(resultado):
    return [c["regla"] for c in resultado["evaluacion"]["causas_escalamiento"]]


# ---------------------------------------------------------------- US1: extracción


class TestExtraer:
    def test_certificado_valido_con_datos_faltantes(self):
        doc = doc_certificado()
        documento, faltantes = extraer(doc["datos"], doc["texto"])
        assert isinstance(documento, CertificadoLaboral)
        assert documento.salario_mensual.valor == 2_000_000
        assert set(faltantes) == {"nombre_empleado", "fecha_expedicion"}

    def test_no_soportado(self):
        documento, _ = extraer({"tipo": "no_soportado", "tipo_detectado": "pasaporte"}, "")
        assert isinstance(documento, DocumentoNoSoportado)

    def test_fragmento_no_literal(self):
        doc = doc_certificado()
        doc["datos"]["salario_mensual"]["fragmento"] = "salario inventado"
        error = error_de(extraer, doc["datos"], doc["texto"])
        assert (error.tipo, error.codigo) == (TipoError.VALIDACION, "FRAGMENTO_NO_LITERAL")
        assert error.reintentable is True
        assert "salario_mensual" in error.detalles["campos"]

    @pytest.mark.parametrize(
        "cambio",
        [
            {"salario_mensual": {"valor": 2_000_000}},
            {"salario_mensual": {"valor": 0, "fragmento": "salario mensual"}},
            {"confianza": 0.9},
            {"tipo": "pasaporte"},
        ],
    )
    def test_extraccion_invalida(self, cambio):
        doc = doc_certificado()
        datos = {**doc["datos"], **cambio}
        error = error_de(extraer, datos, doc["texto"])
        assert (error.tipo, error.codigo) == (TipoError.VALIDACION, "EXTRACCION_INVALIDA")
        assert error.reintentable is True
        assert error.detalles["errores"]
        assert all({"campo", "motivo"} <= set(e) for e in error.detalles["errores"])
        assert all(e["campo"] for e in error.detalles["errores"])

    @pytest.mark.parametrize("datos", [{"tipo": "pasaporte"}, {"sin_tipo": 1}])
    def test_tipo_desconocido_nombra_el_campo_tipo(self, datos):
        error = error_de(extraer, datos, "texto")
        assert [e["campo"] for e in error.detalles["errores"]] == ["tipo"]


# ---------------------------------------------------------------- US2: registro


class TestRegistrarIdentidad:
    def test_sin_verificar(self, almacen):
        almacen.leer()
        antes = almacen.ruta.read_bytes()
        error = error_de(registrar, almacen)
        assert (error.tipo, error.codigo) == (TipoError.PERMISOS, "IDENTIDAD_NO_VERIFICADA")
        assert almacen.ruta.read_bytes() == antes

    def test_bloqueado(self, verificado):
        for _ in range(3):
            with pytest.raises(ErrorCore):
                verificar_identidad(verificado, ANA["id_solicitante"], "2000-01-01", hoy=HOY)
        assert error_de(registrar, verificado).codigo == "IDENTIDAD_NO_VERIFICADA"

    def test_solicitante_inexistente(self, verificado):
        error = error_de(
            registrar_solicitud, verificado, "SOL-9999", 4_000_000, 24, 1, [doc_certificado()]
        )
        assert error.codigo == "IDENTIDAD_NO_VERIFICADA"


class TestRegistrarRegla2:
    def registrar_borde(self, almacen, salario, monto=5_000_000):
        doc = doc_certificado(salario=salario)
        return registrar(almacen, monto=monto, plazo=12, declarado=salario, documentos=[doc])

    def test_cuota_en_30_exacto_preaprueba(self, verificado):
        resultado = self.registrar_borde(verificado, INGRESO_30_EXACTO)
        evaluacion = resultado["evaluacion"]
        assert evaluacion["preaprobable_automaticamente"] is True
        assert evaluacion["decision"] == "preaprobable"
        assert evaluacion["cuota"] == 467_010
        assert evaluacion["causas_escalamiento"] == []

    def test_cuota_un_peso_sobre_30(self, verificado):
        resultado = self.registrar_borde(verificado, INGRESO_30_EXACTO - 1)
        assert resultado["evaluacion"]["preaprobable_automaticamente"] is False
        assert causas(resultado) == ["regla_2"]

    def test_cuota_un_peso_bajo_30(self, verificado):
        resultado = self.registrar_borde(verificado, INGRESO_30_EXACTO + 1)
        assert resultado["evaluacion"]["preaprobable_automaticamente"] is True

    def test_monto_un_peso_bajo_el_tope(self, verificado):
        resultado = self.registrar_borde(verificado, 10_000_000, monto=4_999_999)
        assert resultado["evaluacion"]["preaprobable_automaticamente"] is True

    def test_monto_sobre_el_tope(self, verificado):
        resultado = self.registrar_borde(verificado, 10_000_000, monto=5_000_001)
        assert causas(resultado) == ["regla_2"]


class TestRegistrarRegla3:
    @pytest.mark.parametrize("declarado", [2_200_000, 1_800_000, 2_199_999, 1_800_001])
    def test_diferencia_10_exacto(self, verificado, declarado):
        resultado = registrar(verificado, declarado=declarado)
        assert resultado["evaluacion"]["preaprobable_automaticamente"] is True

    @pytest.mark.parametrize("declarado", [2_200_001, 1_799_999])
    def test_diferencia_sobre_10(self, verificado, declarado):
        resultado = registrar(verificado, declarado=declarado)
        assert causas(resultado) == ["regla_3"]


class TestRegistrarIngreso:
    def test_inconsistencia_de_nomina(self, verificado):
        resultado = registrar(verificado, documentos=[doc_certificado(), doc_extracto(2_200_001)])
        assert resultado["evaluacion"]["decision"] == "analista"
        assert "nomina" in causas(resultado)

    def test_moneda_extranjera_se_registra_fuera_de_politica(self, verificado):
        resultado = registrar(verificado, documentos=[doc_certificado(moneda="USD")])
        assert resultado["evaluacion"]["decision"] == "fuera_de_politica"
        assert resultado["evaluacion"]["preaprobable_automaticamente"] is False

    @pytest.mark.parametrize(
        "documentos",
        [[doc_extracto(2_000_000)], [doc_certificado(salario=None)]],
    )
    def test_ingreso_no_verificable(self, verificado, documentos):
        error = error_de(registrar, verificado, documentos=documentos)
        assert (error.tipo, error.codigo) == (TipoError.NEGOCIO, "INGRESO_NO_VERIFICABLE")
        assert error.reintentable is False
        assert "salario_mensual" in error.detalles["datos_faltantes"]
        assert verificado.leer()["solicitudes"] == {}

    def test_extraccion_invalida_no_registra(self, verificado):
        doc = doc_certificado()
        doc["datos"]["salario_mensual"]["fragmento"] = "salario inventado"
        assert error_de(registrar, verificado, documentos=[doc]).codigo == "FRAGMENTO_NO_LITERAL"
        assert verificado.leer()["solicitudes"] == {}

    @pytest.mark.parametrize(
        "cambio",
        [
            {"monto": 0},
            {"plazo": 61},
            {"declarado": -1},
            {"declarado": 2_000_000.0},
            {"documentos": []},
        ],
    )
    def test_parametros_invalidos(self, verificado, cambio):
        error = error_de(registrar, verificado, **cambio)
        assert (error.tipo, error.codigo) == (TipoError.VALIDACION, "PARAMETROS_INVALIDOS")
        assert error.reintentable is False

    def test_id_documento_repetido(self, verificado):
        documentos = [doc_certificado(), doc_extracto(2_000_000, id_documento="cert-1")]
        assert error_de(registrar, verificado, documentos=documentos).codigo == (
            "PARAMETROS_INVALIDOS"
        )


class TestRegistrarProcedencia:
    def test_cada_dato_con_documento_y_fragmento(self, verificado):
        documentos = [doc_certificado(), doc_extracto(2_000_000, 2_000_000)]
        resultado = registrar(verificado, documentos=documentos)
        solicitud = verificado.leer()["solicitudes"][resultado["id_solicitud"]]
        assert solicitud["estado"] == "REGISTRADA"
        textos = {d["id_documento"]: d["texto"] for d in documentos}
        for dato in solicitud["datos"]:
            assert dato["fragmento"] in textos[dato["id_documento"]]
        campos = {d["campo"] for d in solicitud["datos"]}
        assert {"salario_mensual", "abonos_nomina[0]", "abonos_nomina[1]"} <= campos
        assert solicitud["ingreso_verificado"] == {
            "valor": 2_000_000,
            "id_documento": "cert-1",
            "fragmento": "salario mensual de $2.000.000",
        }

    def test_identificadores_secuenciales(self, verificado):
        assert registrar(verificado)["id_solicitud"] == "SLC-0001"
        assert registrar(verificado)["id_solicitud"] == "SLC-0002"


# ---------------------------------------------------------------- US3: simular y preaprobar


class TestSimular:
    def test_cuota(self):
        assert simular(4_000_000, 24) == {"cuota": 206_723, "tasa_mensual": "0.018"}

    def test_proporcion_en_el_borde(self):
        resultado = simular(5_000_000, 12, INGRESO_30_EXACTO)
        assert resultado["proporcion_cuota_ingreso"] == "0.3000"
        assert resultado["dentro_de_proporcion_maxima"] is True
        assert simular(5_000_000, 12, INGRESO_30_EXACTO - 1)["dentro_de_proporcion_maxima"] is False
        assert simular(5_000_000, 12, INGRESO_30_EXACTO + 1)["dentro_de_proporcion_maxima"] is True

    @pytest.mark.parametrize(
        "argumentos", [(4_000_000, 61), (0, 24), (4_000_000, 24, 0), (4_000_000, 24, 1.5)]
    )
    def test_parametros_invalidos(self, argumentos):
        assert error_de(simular, *argumentos).codigo == "PARAMETROS_INVALIDOS"


class TestPreaprobar:
    def solicitud_preaprobable(self, almacen):
        return registrar(almacen)["id_solicitud"]

    def test_preaprueba_y_es_idempotente(self, verificado):
        id_solicitud = self.solicitud_preaprobable(verificado)
        resultado = preaprobar_credito(verificado, id_solicitud)
        assert resultado == {
            "id_solicitud": id_solicitud,
            "monto": 4_000_000,
            "plazo_meses": 24,
            "cuota": 206_723,
            "tasa_mensual": "0.018",
        }
        assert verificado.leer()["solicitudes"][id_solicitud]["estado"] == "PREAPROBADA"
        assert preaprobar_credito(verificado, id_solicitud) == resultado

    def test_identidad_bloqueada_despues_de_registrar(self, verificado):
        id_solicitud = self.solicitud_preaprobable(verificado)
        for _ in range(3):
            with pytest.raises(ErrorCore):
                verificar_identidad(verificado, ANA["id_solicitante"], "2000-01-01", hoy=HOY)
        error = error_de(preaprobar_credito, verificado, id_solicitud)
        assert (error.tipo, error.codigo) == (TipoError.PERMISOS, "IDENTIDAD_NO_VERIFICADA")
        assert verificado.leer()["solicitudes"][id_solicitud]["estado"] == "REGISTRADA"

    @pytest.mark.parametrize(
        ("salario", "declarado", "regla"),
        [
            (INGRESO_30_EXACTO - 1, INGRESO_30_EXACTO - 1, "regla_2"),
            (2_000_000, 2_200_001, "regla_3"),
        ],
    )
    def test_no_preaprobable(self, verificado, salario, declarado, regla):
        monto, plazo = (5_000_000, 12) if regla == "regla_2" else (4_000_000, 24)
        id_solicitud = registrar(
            verificado, monto, plazo, declarado, [doc_certificado(salario=salario)]
        )["id_solicitud"]
        error = error_de(preaprobar_credito, verificado, id_solicitud)
        assert (error.tipo, error.codigo) == (TipoError.NEGOCIO, "NO_PREAPROBABLE")
        assert regla in [c["regla"] for c in error.detalles["causas"]]

    @pytest.mark.parametrize(
        ("monto", "plazo", "salario", "declarado"),
        [
            (5_000_000, 12, INGRESO_30_EXACTO, INGRESO_30_EXACTO),  # monto en tope y cuota 30%
            (4_000_000, 24, 2_000_000, 2_200_000),  # discrepancia 10% exacto
            (4_000_000, 24, 2_000_000, 1_800_000),
        ],
    )
    def test_preaprueba_en_el_umbral_exacto(self, verificado, monto, plazo, salario, declarado):
        documentos = [doc_certificado(salario=salario)]
        id_solicitud = registrar(verificado, monto, plazo, declarado, documentos)["id_solicitud"]
        assert preaprobar_credito(verificado, id_solicitud)["monto"] == monto

    def test_monto_sobre_el_tope_no_preaprueba(self, verificado):
        documentos = [doc_certificado(salario=10_000_000)]
        id_solicitud = registrar(verificado, 5_000_001, 12, 10_000_000, documentos)["id_solicitud"]
        error = error_de(preaprobar_credito, verificado, id_solicitud)
        assert error.codigo == "NO_PREAPROBABLE"
        assert [c["regla"] for c in error.detalles["causas"]] == ["regla_2"]

    def test_inconsistencia_de_nomina_no_preaprueba(self, verificado):
        documentos = [doc_certificado(), doc_extracto(2_200_001)]
        id_solicitud = registrar(verificado, documentos=documentos)["id_solicitud"]
        error = error_de(preaprobar_credito, verificado, id_solicitud)
        assert error.codigo == "NO_PREAPROBABLE"
        assert "nomina" in [c["regla"] for c in error.detalles["causas"]]

    def test_no_confia_en_la_evaluacion_guardada(self, verificado):
        id_solicitud = registrar(
            verificado,
            5_000_000,
            12,
            INGRESO_30_EXACTO - 1,
            [doc_certificado(salario=INGRESO_30_EXACTO - 1)],
        )["id_solicitud"]
        with verificado.transaccion() as datos:
            evaluacion = datos["solicitudes"][id_solicitud]["evaluacion"]
            evaluacion.update(
                preaprobable_automaticamente=True, decision="preaprobable", causas_escalamiento=[]
            )
        assert error_de(preaprobar_credito, verificado, id_solicitud).codigo == "NO_PREAPROBABLE"

    def test_solicitud_escalada(self, verificado):
        id_solicitud = self.solicitud_preaprobable(verificado)
        with verificado.transaccion() as datos:
            datos["solicitudes"][id_solicitud]["estado"] = "ESCALADA"
        assert error_de(preaprobar_credito, verificado, id_solicitud).codigo == (
            "SOLICITUD_ESCALADA"
        )

    def test_inexistente(self, verificado):
        error = error_de(preaprobar_credito, verificado, "SLC-9999")
        assert (error.tipo, error.codigo) == (TipoError.NEGOCIO, "SOLICITUD_NO_ENCONTRADA")
