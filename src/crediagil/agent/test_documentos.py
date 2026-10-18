"""Tests de los adjuntos (spec 007, FR-004)."""

from __future__ import annotations

from crediagil.agent.documentos import DocumentoAdjunto, asignar_ids, renderizar_mensaje


def test_ids_consecutivos():
    docs = [DocumentoAdjunto("a.txt", "uno"), DocumentoAdjunto("b.txt", "dos")]
    con_id, omitidos = asignar_ids(docs)
    assert [d.documento_id for d in con_id] == ["DOC-1", "DOC-2"]
    assert omitidos == []


def test_los_ids_siguen_contando_en_turnos_posteriores():
    con_id, _ = asignar_ids([DocumentoAdjunto("c.txt", "tres")], ya_asignados=2)
    assert con_id[0].documento_id == "DOC-3"


def test_adjunto_vacio_se_omite_y_no_gasta_id():
    docs = [
        DocumentoAdjunto("vacio.txt", ""),
        DocumentoAdjunto("espacios.txt", "  \n "),
        DocumentoAdjunto("ok.txt", "texto"),
    ]
    con_id, omitidos = asignar_ids(docs)
    assert [d.nombre for d in con_id] == ["ok.txt"]
    assert con_id[0].documento_id == "DOC-1"
    assert [d.nombre for d in omitidos] == ["vacio.txt", "espacios.txt"]


def test_renderizar_incluye_cada_documento():
    con_id, _ = asignar_ids([DocumentoAdjunto("certificado.txt", "Salario: 3000000")])
    mensaje = renderizar_mensaje("Quiero un crédito", con_id)
    assert mensaje.startswith("Quiero un crédito")
    assert '<documento id="DOC-1" nombre="certificado.txt">Salario: 3000000</documento>' in mensaje


def test_renderizar_escapa_las_comillas_del_nombre():
    con_id, _ = asignar_ids([DocumentoAdjunto('a"b.txt', "x")])
    assert 'nombre="a&quot;b.txt"' in renderizar_mensaje("hola", con_id)


def test_sin_adjuntos_el_mensaje_queda_igual():
    assert renderizar_mensaje("hola", []) == "hola"
