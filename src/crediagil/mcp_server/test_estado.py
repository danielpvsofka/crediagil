"""Tests del almacén de estado: research.md R3 (FR-013, FR-014)."""

from __future__ import annotations

import json
import multiprocessing
import time
from pathlib import Path

import pytest
from filelock import FileLock

from crediagil.mcp_server.errores import ErrorCore, TipoError
from crediagil.mcp_server.estado import AlmacenEstado, ruta_por_defecto, siguiente_id
from crediagil.mcp_server.semilla import SOLICITANTES_SEMILLA


def test_crea_el_archivo_con_la_semilla(tmp_path):
    ruta = tmp_path / "sub" / "estado.json"
    datos = AlmacenEstado(ruta).leer()
    assert ruta.exists()
    assert datos["version"] == 2
    assert len(datos["solicitantes"]) == len(SOLICITANTES_SEMILLA) == 4
    for solicitante in datos["solicitantes"].values():
        assert solicitante["intentos_fallidos"] == 0
        assert solicitante["bloqueado"] is False


def test_documentos_semilla_normalizados(tmp_path):
    datos = AlmacenEstado(tmp_path / "e.json").leer()
    for solicitante in datos["solicitantes"].values():
        documento = solicitante["documento"]
        assert documento == documento.upper().replace(" ", "")
        assert documento.startswith("TEST-")


def test_transaccion_persiste(tmp_path):
    ruta = tmp_path / "e.json"
    with AlmacenEstado(ruta).transaccion() as datos:
        datos["solicitantes"]["SOL-0001"]["intentos_fallidos"] = 2
    assert AlmacenEstado(ruta).leer()["solicitantes"]["SOL-0001"]["intentos_fallidos"] == 2


def test_excepcion_en_transaccion_no_escribe(tmp_path):
    ruta = tmp_path / "e.json"
    almacen = AlmacenEstado(ruta)
    almacen.leer()
    antes = ruta.read_bytes()
    with pytest.raises(RuntimeError), almacen.transaccion() as datos:
        datos["solicitantes"]["SOL-0001"]["bloqueado"] = True
        raise RuntimeError("falla a mitad")
    assert ruta.read_bytes() == antes
    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.parametrize("contenido", ["{no json", "[]", '{"version": 1}'])
def test_archivo_ilegible_no_se_sobrescribe(tmp_path, contenido):
    ruta = tmp_path / "e.json"
    ruta.write_text(contenido, encoding="utf-8")
    with pytest.raises(ErrorCore) as info:
        AlmacenEstado(ruta).leer()
    assert info.value.tipo is TipoError.TRANSITORIO
    assert info.value.codigo == "ESTADO_ILEGIBLE"
    assert ruta.read_text(encoding="utf-8") == contenido


def _incrementar(ruta: str, veces: int) -> None:
    almacen = AlmacenEstado(Path(ruta))
    for _ in range(veces):
        with almacen.transaccion() as datos:
            datos["contador"] = datos.get("contador", 0) + 1


def test_escrituras_concurrentes_no_se_pierden(tmp_path):
    ruta = tmp_path / "e.json"
    AlmacenEstado(ruta).leer()
    contexto = multiprocessing.get_context("spawn")
    procesos = [contexto.Process(target=_incrementar, args=(str(ruta), 50)) for _ in range(2)]
    for proceso in procesos:
        proceso.start()
    for proceso in procesos:
        proceso.join(timeout=60)
        assert proceso.exitcode == 0
    assert json.loads(ruta.read_text(encoding="utf-8"))["contador"] == 100


def test_ruta_por_defecto(monkeypatch, tmp_path):
    monkeypatch.delenv("CREDIAGIL_MCP_ESTADO", raising=False)
    monkeypatch.chdir(tmp_path)
    assert ruta_por_defecto() == tmp_path / ".data" / "core_estado.json"
    monkeypatch.setenv("CREDIAGIL_MCP_ESTADO", str(tmp_path / "otro.json"))
    assert ruta_por_defecto() == tmp_path / "otro.json"


class TestVersion2:
    """Spec 005 R4: solicitudes, escalamientos y verificado_en, con migración desde v1."""

    def test_semilla_v2(self, tmp_path):
        datos = AlmacenEstado(tmp_path / "e.json").leer()
        assert datos["version"] == 2
        assert datos["solicitudes"] == {}
        assert datos["escalamientos"] == {}
        assert all(s["verificado_en"] is None for s in datos["solicitantes"].values())

    def test_migra_un_archivo_v1_sin_perder_datos(self, tmp_path):
        ruta = tmp_path / "e.json"
        v1 = {
            "version": 1,
            "solicitantes": {
                "SOL-0001": {
                    "id_solicitante": "SOL-0001",
                    "documento": SOLICITANTES_SEMILLA[0]["documento"],
                    "nombre": "Ana Prueba Ficticia",
                    "fecha_nacimiento": "1990-03-17",
                    "intentos_fallidos": 2,
                    "bloqueado": False,
                }
            },
        }
        ruta.write_text(json.dumps(v1), encoding="utf-8")
        almacen = AlmacenEstado(ruta)
        with almacen.transaccion() as datos:
            assert datos["solicitudes"] == {}
        guardado = json.loads(ruta.read_text(encoding="utf-8"))
        assert guardado["version"] == 2
        assert guardado["escalamientos"] == {}
        solicitante = guardado["solicitantes"]["SOL-0001"]
        assert solicitante["intentos_fallidos"] == 2
        assert solicitante["verificado_en"] is None

    def test_siguiente_id(self):
        coleccion = {}
        assert siguiente_id(coleccion, "SLC") == "SLC-0001"
        coleccion["SLC-0001"] = {}
        assert siguiente_id(coleccion, "SLC") == "SLC-0002"


class TestLecturaSoloLectura:
    """Spec 006 R4: `leer_existente` no crea ni escribe nada y falla cerrado."""

    def test_lee_un_estado_existente(self, tmp_path):
        almacen = AlmacenEstado(tmp_path / "e.json")
        almacen.leer()
        datos = almacen.leer_existente()
        assert datos["version"] == 2
        assert len(datos["solicitantes"]) == 4

    def test_migra_en_memoria_sin_escribir(self, tmp_path):
        ruta = tmp_path / "e.json"
        v1 = {"version": 1, "solicitantes": {"SOL-0001": {"bloqueado": False}}}
        ruta.write_text(json.dumps(v1), encoding="utf-8")
        datos = AlmacenEstado(ruta).leer_existente()
        assert datos["version"] == 2
        assert datos["solicitudes"] == {}
        assert json.loads(ruta.read_text(encoding="utf-8"))["version"] == 1

    def test_archivo_ausente_no_se_crea(self, tmp_path):
        ruta = tmp_path / "e.json"
        with pytest.raises(ErrorCore) as info:
            AlmacenEstado(ruta).leer_existente()
        assert (info.value.tipo, info.value.codigo) == (TipoError.TRANSITORIO, "ESTADO_ILEGIBLE")
        assert not ruta.exists()

    def test_directorio_inexistente(self, tmp_path):
        almacen = AlmacenEstado(tmp_path / "no_existe" / "e.json")
        with pytest.raises(ErrorCore) as info:
            almacen.leer_existente()
        assert info.value.codigo == "ESTADO_ILEGIBLE"

    def test_json_corrupto_queda_intacto(self, tmp_path):
        ruta = tmp_path / "e.json"
        ruta.write_text("{no json", encoding="utf-8")
        with pytest.raises(ErrorCore) as info:
            AlmacenEstado(ruta).leer_existente()
        assert info.value.codigo == "ESTADO_ILEGIBLE"
        assert ruta.read_text(encoding="utf-8") == "{no json"

    def test_lock_ocupado_falla_a_tiempo(self, tmp_path):
        ruta = tmp_path / "e.json"
        almacen = AlmacenEstado(ruta)
        almacen.leer()
        inicio = time.monotonic()
        with FileLock(str(ruta) + ".lock"), pytest.raises(ErrorCore) as info:
            AlmacenEstado(ruta).leer_existente(timeout=0.2)
        assert info.value.codigo == "ESTADO_ILEGIBLE"
        assert time.monotonic() - inicio < 2
