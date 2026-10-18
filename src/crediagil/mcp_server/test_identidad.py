"""Tests de búsqueda y verificación: contracts/tools.md (FR-005–FR-012, FR-018)."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from crediagil.mcp_server.errores import ErrorCore, TipoError
from crediagil.mcp_server.estado import AlmacenEstado
from crediagil.mcp_server.identidad import (
    MAX_INTENTOS_VERIFICACION,
    buscar_solicitante,
    identidad_vigente,
    verificar_identidad,
)
from crediagil.mcp_server.semilla import SOLICITANTES_SEMILLA

ANA = SOLICITANTES_SEMILLA[0]
HOY = date(2026, 10, 17)
FECHA_INCORRECTA = "2000-01-01"
DOCUMENTO_INEXISTENTE = "TEST-999999"  # dato-ficticio


@pytest.fixture
def almacen(tmp_path):
    return AlmacenEstado(tmp_path / "estado.json")


def error_de(funcion, *args, **kwargs) -> ErrorCore:
    with pytest.raises(ErrorCore) as info:
        funcion(*args, **kwargs)
    return info.value


def intentos(almacen, id_solicitante=ANA["id_solicitante"]):
    return almacen.leer()["solicitantes"][id_solicitante]["intentos_fallidos"]


class TestBuscar:
    def test_por_documento_exacto(self, almacen):
        coincidencias = buscar_solicitante(almacen, documento=ANA["documento"])
        assert coincidencias == [
            {
                "id_solicitante": ANA["id_solicitante"],
                "documento": ANA["documento"],
                "nombre": ANA["nombre"],
                "bloqueado": False,
            }
        ]

    def test_documento_normalizado(self, almacen):
        documento = " " + ANA["documento"].lower().replace("-", " -") + " "
        assert len(buscar_solicitante(almacen, documento=documento)) == 1

    def test_nombre_parcial_varias_coincidencias(self, almacen):
        nombres = {c["nombre"] for c in buscar_solicitante(almacen, nombre="prueba")}
        assert len(nombres) >= 2
        assert all("Prueba" in n for n in nombres)

    def test_nombre_sin_tildes_ni_mayusculas(self, almacen):
        nombres = [c["nombre"] for c in buscar_solicitante(almacen, nombre="PEREZ")]
        assert any("Pérez" in n for n in nombres)

    @pytest.mark.parametrize(
        "parametros", [{"documento": DOCUMENTO_INEXISTENTE}, {"nombre": "zzzz"}]
    )
    def test_sin_resultados_es_lista_vacia(self, almacen, parametros):
        assert buscar_solicitante(almacen, **parametros) == []

    @pytest.mark.parametrize(
        "parametros",
        [
            {},
            {"documento": ANA["documento"], "nombre": "Ana"},
            {"nombre": "ab"},
            {"nombre": " ab "},
        ],
    )
    def test_parametros_invalidos(self, almacen, parametros):
        error = error_de(buscar_solicitante, almacen, **parametros)
        assert error.tipo is TipoError.VALIDACION
        assert error.codigo == "PARAMETROS_INVALIDOS"

    def test_nunca_devuelve_la_fecha_de_nacimiento(self, almacen):
        for coincidencia in buscar_solicitante(almacen, nombre="fic"):
            assert "fecha_nacimiento" not in coincidencia


class TestVerificar:
    def verificar(self, almacen, fecha, id_solicitante=ANA["id_solicitante"]):
        return verificar_identidad(almacen, id_solicitante, fecha, hoy=HOY)

    def fallar(self, almacen, veces):
        for _ in range(veces):
            with pytest.raises(ErrorCore):
                self.verificar(almacen, FECHA_INCORRECTA)

    def test_limite_es_tres(self):
        assert MAX_INTENTOS_VERIFICACION == 3

    def test_fecha_correcta(self, almacen):
        resultado = self.verificar(almacen, ANA["fecha_nacimiento"])
        assert resultado == {"verificado": True, "id_solicitante": ANA["id_solicitante"]}

    def test_fecha_correcta_tras_dos_fallos_reinicia(self, almacen):
        self.fallar(almacen, 2)
        assert intentos(almacen) == 2
        self.verificar(almacen, ANA["fecha_nacimiento"])
        assert intentos(almacen) == 0

    def test_primer_fallo(self, almacen):
        error = error_de(self.verificar, almacen, FECHA_INCORRECTA)
        assert (error.tipo, error.codigo) == (TipoError.NEGOCIO, "IDENTIDAD_NO_COINCIDE")
        assert error.detalles == {"intentos_restantes": 2}
        assert intentos(almacen) == 1

    def test_segundo_fallo_no_bloquea(self, almacen):
        self.fallar(almacen, 1)
        error = error_de(self.verificar, almacen, FECHA_INCORRECTA)
        assert error.tipo is TipoError.NEGOCIO
        assert error.detalles == {"intentos_restantes": 1}
        assert almacen.leer()["solicitantes"][ANA["id_solicitante"]]["bloqueado"] is False

    def test_tercer_fallo_bloquea(self, almacen):
        self.fallar(almacen, 2)
        error = error_de(self.verificar, almacen, FECHA_INCORRECTA)
        assert (error.tipo, error.codigo) == (TipoError.PERMISOS, "SOLICITANTE_BLOQUEADO")
        solicitante = almacen.leer()["solicitantes"][ANA["id_solicitante"]]
        assert solicitante["bloqueado"] is True
        assert solicitante["intentos_fallidos"] == 3

    def test_bloqueado_rechaza_incluso_la_fecha_correcta(self, almacen):
        self.fallar(almacen, 3)
        error = error_de(self.verificar, almacen, ANA["fecha_nacimiento"])
        assert (error.tipo, error.codigo) == (TipoError.PERMISOS, "SOLICITANTE_BLOQUEADO")

    def test_bloqueo_persiste_tras_reinicio(self, tmp_path):
        ruta = tmp_path / "estado.json"
        self.fallar(AlmacenEstado(ruta), 2)
        reiniciado = AlmacenEstado(ruta)
        error = error_de(self.verificar, reiniciado, FECHA_INCORRECTA)
        assert error.tipo is TipoError.PERMISOS
        assert AlmacenEstado(ruta).leer()["solicitantes"][ANA["id_solicitante"]]["bloqueado"]

    def test_bloqueo_de_uno_no_afecta_a_otro(self, almacen):
        self.fallar(almacen, 3)
        otro = SOLICITANTES_SEMILLA[1]
        resultado = self.verificar(almacen, otro["fecha_nacimiento"], otro["id_solicitante"])
        assert resultado["verificado"] is True

    def test_solicitante_inexistente(self, almacen):
        error = error_de(self.verificar, almacen, FECHA_INCORRECTA, "SOL-9999")
        assert (error.tipo, error.codigo) == (TipoError.NEGOCIO, "SOLICITANTE_NO_ENCONTRADO")

    @pytest.mark.parametrize(
        "fecha", ["17/03/1990", "1990-02-30", "1990-01-01T00:00", "", "2026-10-18"]
    )
    def test_fecha_invalida_o_futura_no_cuenta_intento(self, almacen, fecha):
        self.fallar(almacen, 2)
        error = error_de(self.verificar, almacen, fecha)
        assert (error.tipo, error.codigo) == (TipoError.VALIDACION, "FECHA_INVALIDA")
        assert intentos(almacen) == 2

    def test_fecha_de_hoy_es_valida(self, almacen):
        error = error_de(self.verificar, almacen, HOY.isoformat())
        assert error.codigo == "IDENTIDAD_NO_COINCIDE"


class TestConstanciaDeVerificacion:
    """Spec 005 FR-007: la verificación exitosa deja constancia; el bloqueo la borra."""

    AHORA = datetime(2026, 10, 17, 15, 30, tzinfo=UTC)

    def verificar(self, almacen, fecha):
        return verificar_identidad(almacen, ANA["id_solicitante"], fecha, hoy=HOY, ahora=self.AHORA)

    def solicitante(self, almacen):
        return almacen.leer()["solicitantes"][ANA["id_solicitante"]]

    def test_exito_guarda_verificado_en(self, almacen):
        self.verificar(almacen, ANA["fecha_nacimiento"])
        assert self.solicitante(almacen)["verificado_en"] == "2026-10-17T15:30:00+00:00"

    def test_fallo_sin_bloqueo_conserva_la_verificacion_anterior(self, almacen):
        self.verificar(almacen, ANA["fecha_nacimiento"])
        for _ in range(2):
            with pytest.raises(ErrorCore):
                self.verificar(almacen, FECHA_INCORRECTA)
        assert self.solicitante(almacen)["verificado_en"] is not None

    def test_bloqueo_borra_la_verificacion(self, almacen):
        self.verificar(almacen, ANA["fecha_nacimiento"])
        for _ in range(3):
            with pytest.raises(ErrorCore):
                self.verificar(almacen, FECHA_INCORRECTA)
        assert self.solicitante(almacen)["verificado_en"] is None

    @pytest.mark.parametrize(
        ("verificado_en", "bloqueado", "esperado"),
        [
            ("2026-10-17T15:30:00+00:00", False, True),
            (None, False, False),
            ("2026-10-17T15:30:00+00:00", True, False),
        ],
    )
    def test_identidad_vigente(self, verificado_en, bloqueado, esperado):
        solicitante = {"verificado_en": verificado_en, "bloqueado": bloqueado}
        assert identidad_vigente(solicitante) is esperado
