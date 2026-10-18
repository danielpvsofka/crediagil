"""Ningún texto del catálogo tiene un dato con forma real (spec 009, US4, research R8; Principio III).

Pasa por todos los textos del catálogo el mismo detector del hook `block_sensitive_data` de Claude
Code (importado por ruta, sin copiar su lógica): así el repositorio cumple también por una vía que
no depende de que Claude escriba el archivo. Cualquier hallazgo sin el marcador `dato-ficticio` en
la misma línea hace fallar el test.
"""

from __future__ import annotations

import importlib.util
import io
import re
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from crediagil.casos import catalogo
from crediagil.casos.catalogo import RAIZ
from crediagil.mcp_server.semilla import SOLICITANTES_SEMILLA

HOOKS = Path(__file__).resolve().parents[3] / ".claude" / "hooks"


def _cargar_detector():
    """Importa el hook por ruta; su única dependencia (`_hooklib`) vive en la misma carpeta."""
    sys.path.insert(0, str(HOOKS))
    # `_hooklib` reconfigura stdin/stdout/stderr al importarse; pytest los sustituye por objetos
    # que no lo admiten, así que durante la importación se usan flujos de texto normales.
    flujos = {
        nombre: io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
        for nombre in ("stdin", "stdout", "stderr")
    }
    try:
        especificacion = importlib.util.spec_from_file_location(
            "block_sensitive_data", HOOKS / "block_sensitive_data.py"
        )
        modulo = importlib.util.module_from_spec(especificacion)
        with patch.multiple(sys, **flujos):
            especificacion.loader.exec_module(modulo)
    finally:
        sys.path.remove(str(HOOKS))
    return modulo


DETECTOR = _cargar_detector()


def hallazgos_sin_marcar(texto: str) -> list[tuple[str, str]]:
    """Datos con forma real en líneas que no llevan el marcador de dato ficticio."""
    encontrados = []
    for linea in texto.splitlines():
        if DETECTOR.MARCADOR in linea:
            continue
        encontrados.extend(DETECTOR.find_in_line(linea))
    return encontrados


def archivos_del_catalogo() -> list[Path]:
    return sorted(
        ruta
        for carpeta in RAIZ.iterdir()
        if carpeta.is_dir() and carpeta.name[:2].isdigit()
        for ruta in carpeta.rglob("*")
        if ruta.is_file()
    )


def numero_con_luhn(prefijo: str = "4", largo: int = 16) -> str:
    """Número ficticio de `largo` dígitos válido por Luhn, construido en tiempo de ejecución."""
    cuerpo = (prefijo + "0" * largo)[: largo - 1]
    total = 0
    for indice, caracter in enumerate(reversed(cuerpo)):
        digito = int(caracter)
        if indice % 2 == 0:
            digito *= 2
            if digito > 9:
                digito -= 9
        total += digito
    return cuerpo + str((10 - total % 10) % 10)


# ---------------------------------------------------------------- el catálogo real


@pytest.mark.parametrize("ruta", archivos_del_catalogo(), ids=lambda r: f"{r.parent.name}/{r.name}")
def test_ningun_archivo_del_catalogo_tiene_datos_con_forma_real(ruta):
    assert hallazgos_sin_marcar(ruta.read_text(encoding="utf-8")) == []


def test_el_catalogo_tiene_archivos_que_revisar():
    assert len(archivos_del_catalogo()) >= 3 * len(catalogo().casos) - 2


def test_todo_identificador_largo_con_forma_de_documento_lleva_el_prefijo_de_prueba():
    for caso in catalogo().casos:
        textos = [caso.mensaje, *(d.texto for d in caso.documentos)]
        for texto in textos:
            assert not re.findall(r"(?<!TEST-)\b\d{6,}\b", texto), (caso.id, texto)


def test_los_identificadores_de_prueba_de_los_mensajes_existen_en_la_semilla():
    documentos = {s["documento"] for s in SOLICITANTES_SEMILLA}
    usados = set()
    for caso in catalogo().casos:
        usados.update(re.findall(r"TEST-\d+", caso.mensaje))
    assert usados, "los mensajes deberían identificar a su solicitante"
    assert usados <= documentos


# ---------------------------------------------------------------- el comprobador no pasa por no mirar


class TestControlNegativo:
    def test_detecta_un_numero_con_forma_de_tarjeta(self):
        tarjeta = numero_con_luhn()
        hallazgos = hallazgos_sin_marcar(f"Pagué con {tarjeta} ayer.")
        assert [tipo for tipo, _ in hallazgos] == ["tarjeta"]

    def test_detecta_una_cedula_con_su_etiqueta(self):
        texto = "cédula: " + "1" * 10
        assert [tipo for tipo, _ in hallazgos_sin_marcar(texto)] == ["documento"]

    def test_detecta_una_cuenta_con_su_etiqueta(self):
        texto = "cuenta de ahorros " + "2" * 12
        assert [tipo for tipo, _ in hallazgos_sin_marcar(texto)] == ["cuenta"]

    def test_el_marcador_en_la_misma_linea_lo_permite(self):
        texto = "cédula: " + "1" * 10 + "  " + DETECTOR.MARCADOR
        assert hallazgos_sin_marcar(texto) == []

    def test_el_marcador_en_otra_linea_no_lo_permite(self):
        texto = DETECTOR.MARCADOR + "\ncédula: " + "1" * 10
        assert [tipo for tipo, _ in hallazgos_sin_marcar(texto)] == ["documento"]

    def test_un_monto_o_un_id_de_prueba_no_son_datos_con_forma_real(self):
        assert hallazgos_sin_marcar("Quiero 3.000.000 de pesos. Identificación TEST-100001.") == []

    def test_un_archivo_con_un_dato_real_haria_fallar_el_test_del_catalogo(self, tmp_path):
        archivo = tmp_path / "mensaje.md"
        archivo.write_text(f"Mi tarjeta es {numero_con_luhn()}", encoding="utf-8")
        assert hallazgos_sin_marcar(archivo.read_text(encoding="utf-8")) != []
