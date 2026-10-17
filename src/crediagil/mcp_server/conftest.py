"""Helpers compartidos por los tests del core: documentos 100% ficticios construidos al vuelo."""

from __future__ import annotations


def pesos(valor: int) -> str:
    return f"${valor:,}".replace(",", ".")


def doc_certificado(salario: int | None = 2_000_000, moneda: str = "COP", id_documento="cert-1"):
    monto_texto = pesos(salario or 0)
    texto = (
        "Empresa Ficticia S.A.S. certifica que Ana Prueba Ficticia devenga un salario mensual "
        f"de {monto_texto} {moneda}."
    )
    datos = {
        "tipo": "certificado_laboral",
        "empleador": {"valor": "Empresa Ficticia S.A.S.", "fragmento": "Empresa Ficticia S.A.S."},
        "moneda": {"valor": moneda, "fragmento": f"{monto_texto} {moneda}"},
    }
    if salario is not None:
        datos["salario_mensual"] = {
            "valor": salario,
            "fragmento": f"salario mensual de {monto_texto}",
        }
    return {"id_documento": id_documento, "datos": datos, "texto": texto}


def doc_extracto(*abonos: int, id_documento="ext-1"):
    lineas = [f"ABONO NOMINA EMPRESA FICTICIA {pesos(a)} #{i}" for i, a in enumerate(abonos)]
    texto = "Banco Imaginario. Moneda: COP.\n" + "\n".join(lineas)
    datos = {
        "tipo": "extracto_bancario",
        "moneda": {"valor": "COP", "fragmento": "Moneda: COP"},
        "abonos_nomina": [{"valor": a, "fragmento": linea} for a, linea in zip(abonos, lineas)],
    }
    return {"id_documento": id_documento, "datos": datos, "texto": texto}
