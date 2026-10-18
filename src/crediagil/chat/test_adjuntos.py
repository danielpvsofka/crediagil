"""Tests de la validación de adjuntos (spec 008, data-model.md "Adjunto", research R6)."""

from __future__ import annotations

import base64

import pytest

from crediagil.agent.documentos import DocumentoAdjunto
from crediagil.chat.adjuntos import (
    EXTENSIONES,
    LIMITE_ADJUNTOS,
    LIMITE_BYTES_ADJUNTO,
    ErrorAdjunto,
    decodificar_adjuntos,
)


def _b64(contenido: str | bytes) -> str:
    crudo = contenido.encode("utf-8") if isinstance(contenido, str) else contenido
    return base64.b64encode(crudo).decode("ascii")


def _entrada(nombre="certificado.txt", contenido: str | bytes = "texto"):
    return {"nombre": nombre, "contenido_b64": _b64(contenido)}


def _codigo(entradas) -> str:
    with pytest.raises(ErrorAdjunto) as error:
        decodificar_adjuntos(entradas)
    return error.value.codigo


def test_las_constantes_son_las_del_diseno():
    assert LIMITE_BYTES_ADJUNTO == 102_400
    assert LIMITE_ADJUNTOS == 5
    assert EXTENSIONES == (".txt", ".md")


def test_sin_adjuntos_devuelve_vacio():
    assert decodificar_adjuntos([]) == []
    assert decodificar_adjuntos(None) == []


def test_adjuntos_validos_conservan_nombre_y_texto():
    documentos = decodificar_adjuntos(
        [_entrada("a.txt", "Salario: $6.000.000 COP\nñandú"), _entrada("NOTAS.MD", "# título")]
    )
    assert documentos == [
        DocumentoAdjunto("a.txt", "Salario: $6.000.000 COP\nñandú"),
        DocumentoAdjunto("NOTAS.MD", "# título"),
    ]


def test_el_bom_inicial_no_queda_en_el_texto():
    (documento,) = decodificar_adjuntos([_entrada("a.txt", b"\xef\xbb\xbfhola")])
    assert documento.texto == "hola"


def test_borde_del_tamano_maximo():
    exacto = _entrada("a.txt", "a" * LIMITE_BYTES_ADJUNTO)
    assert len(decodificar_adjuntos([exacto])[0].texto) == LIMITE_BYTES_ADJUNTO
    assert _codigo([_entrada("a.txt", "a" * (LIMITE_BYTES_ADJUNTO + 1))]) == (
        "ADJUNTO_DEMASIADO_GRANDE"
    )


def test_el_tamano_se_mide_en_bytes_no_en_caracteres():
    # "ñ" ocupa 2 bytes: la mitad más uno de caracteres ya supera el límite.
    assert _codigo([_entrada("a.txt", "ñ" * (LIMITE_BYTES_ADJUNTO // 2 + 1))]) == (
        "ADJUNTO_DEMASIADO_GRANDE"
    )


def test_borde_de_la_cantidad_de_adjuntos():
    cinco = [_entrada(f"a{i}.txt") for i in range(LIMITE_ADJUNTOS)]
    assert len(decodificar_adjuntos(cinco)) == LIMITE_ADJUNTOS
    seis = [_entrada(f"a{i}.txt") for i in range(LIMITE_ADJUNTOS + 1)]
    assert _codigo(seis) == "ADJUNTOS_DEMASIADOS"


@pytest.mark.parametrize(
    "nombre", ["a.pdf", "a.txt.exe", "sin_extension", "a.mdx", "a.", ".txt.bak"]
)
def test_extension_no_admitida(nombre):
    assert _codigo([_entrada(nombre)]) == "EXTENSION_NO_ADMITIDA"


@pytest.mark.parametrize("contenido", ["", "   ", "\n\n", " \t\r\n "])
def test_adjunto_vacio(contenido):
    assert _codigo([_entrada("a.txt", contenido)]) == "ADJUNTO_VACIO"


@pytest.mark.parametrize(
    "contenido_b64",
    ["esto no es base64!", "abc", _b64(b"\xff\xfe\x00 roto"), _b64(b"\x80\x81\x82")],
)
def test_adjunto_ilegible(contenido_b64):
    assert _codigo([{"nombre": "a.txt", "contenido_b64": contenido_b64}]) == "ADJUNTO_ILEGIBLE"


@pytest.mark.parametrize(
    "entrada",
    [
        "texto",
        None,
        3,
        {},
        {"nombre": "a.txt"},
        {"contenido_b64": "YQ=="},
        {"nombre": 3, "contenido_b64": "YQ=="},
        {"nombre": "a.txt", "contenido_b64": 3},
        {"nombre": "", "contenido_b64": "YQ=="},
        {"nombre": "   ", "contenido_b64": "YQ=="},
        {"nombre": "carpeta/", "contenido_b64": "YQ=="},
    ],
)
def test_forma_invalida(entrada):
    assert _codigo([entrada]) == "ADJUNTO_INVALIDO"


def test_adjuntos_que_no_son_una_lista():
    assert _codigo("a.txt") == "ADJUNTO_INVALIDO"
    assert _codigo({"nombre": "a.txt"}) == "ADJUNTO_INVALIDO"


@pytest.mark.parametrize(
    ("nombre", "base"),
    [("../../x.txt", "x.txt"), ("C:\\carpeta\\y.md", "y.md"), ("a/b/z.TXT", "z.TXT")],
)
def test_se_quitan_las_rutas_del_nombre(nombre, base):
    (documento,) = decodificar_adjuntos([_entrada(nombre)])
    assert documento.nombre == base


def test_los_nombres_repetidos_se_conservan():
    documentos = decodificar_adjuntos([_entrada("a.txt", "uno"), _entrada("a.txt", "dos")])
    assert [d.texto for d in documentos] == ["uno", "dos"]


def test_los_mensajes_son_claros_y_no_traen_el_contenido():
    secreto = "contenido-privado-del-documento"
    with pytest.raises(ErrorAdjunto) as error:
        decodificar_adjuntos([_entrada("datos.pdf", secreto)])
    assert "datos.pdf" in error.value.mensaje
    assert ".txt" in error.value.mensaje and ".md" in error.value.mensaje
    assert secreto not in error.value.mensaje
    for entradas in (
        [_entrada("a.txt", "")],
        [_entrada("a.txt", "a" * (LIMITE_BYTES_ADJUNTO + 1))],
    ):
        with pytest.raises(ErrorAdjunto) as otro:
            decodificar_adjuntos(entradas)
        assert "a.txt" in otro.value.mensaje
