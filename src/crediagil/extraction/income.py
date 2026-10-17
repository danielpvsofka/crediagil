"""Ingreso verificado a partir de documentos validados (constitución, regla 3; spec FR-012–014).

El ingreso verificado sale solo del salario del certificado laboral. Los extractos únicamente
sirven para contrastarlo; nunca lo sustituyen (Principio V).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from crediagil.extraction.schemas import (
    CampoExtraido,
    CertificadoLaboral,
    DocumentoNoSoportado,
    ExtractoBancario,
)
from crediagil.policy.params import DISCREPANCIA_MAXIMA_INGRESO, MONEDA
from crediagil.policy.reglas import Decision, Motivo, Resultado


class TipoHallazgo(StrEnum):
    DATO_FALTANTE = "dato_faltante"
    INCONSISTENCIA_DOCUMENTAL = "inconsistencia_documental"
    FUERA_DE_POLITICA = "fuera_de_politica"


@dataclass(frozen=True)
class Hallazgo:
    tipo: TipoHallazgo
    mensaje: str
    campo: str | None = None
    # Regla del Motivo equivalente al convertirlo en Resultado.
    regla: str = "ingreso"


@dataclass(frozen=True)
class IngresoVerificado:
    valor: int
    moneda: str
    origen: CampoExtraido[int]


@dataclass(frozen=True)
class ResultadoIngreso:
    ingreso: IngresoVerificado | None
    hallazgos: list[Hallazgo] = field(default_factory=list)


def derivar_ingreso(documentos: list) -> ResultadoIngreso:
    hallazgos = [
        Hallazgo(
            TipoHallazgo.FUERA_DE_POLITICA,
            f"Tipo de documento no soportado: {doc.tipo_detectado}.",
            regla="documento",
        )
        for doc in documentos
        if isinstance(doc, DocumentoNoSoportado)
    ]
    extractos = [doc for doc in documentos if isinstance(doc, ExtractoBancario)]
    for extracto in extractos:
        if extracto.moneda is not None and extracto.moneda.valor != MONEDA:
            hallazgos.append(_fuera_de_moneda(extracto.moneda.valor, "extracto bancario"))

    certificados = [doc for doc in documentos if isinstance(doc, CertificadoLaboral)]
    ingreso = _ingreso_de_certificados(certificados, hallazgos)
    if ingreso is not None:
        inconsistencia = _contrastar_nomina(ingreso.valor, extractos)
        if inconsistencia:
            hallazgos.append(inconsistencia)
    return ResultadoIngreso(ingreso=ingreso, hallazgos=hallazgos)


def _ingreso_de_certificados(
    certificados: list[CertificadoLaboral], hallazgos: list[Hallazgo]
) -> IngresoVerificado | None:
    """Salario certificado, revisando salario y moneda de **todos** los certificados.

    Se acumulan todos los problemas antes de decidir, así el resultado no depende del orden de
    los documentos ni del de las comprobaciones: cualquier certificado en otra moneda deja el
    caso fuera de política, cualquiera sin moneda es dato faltante, salarios distintos son
    ambiguos y sin salario no hay ingreso. Con algún problema no hay ingreso verificado.
    """
    problemas = []
    otras = sorted({c.moneda.valor for c in certificados if c.moneda and c.moneda.valor != MONEDA})
    if otras:
        problemas.append(_fuera_de_moneda(", ".join(otras), "certificado laboral"))
    if any(c.moneda is None for c in certificados):
        problemas.append(
            Hallazgo(
                TipoHallazgo.DATO_FALTANTE,
                "Un certificado laboral no indica la moneda del salario.",
                campo="moneda",
            )
        )
    salarios = {c.salario_mensual.valor for c in certificados if c.salario_mensual is not None}
    if len(salarios) > 1:
        # Salario ambiguo: no se elige uno (Principio V).
        problemas.append(
            Hallazgo(
                TipoHallazgo.DATO_FALTANTE,
                "Hay varios certificados laborales con salarios distintos; el salario es ambiguo.",
                campo="salario_mensual",
            )
        )
    elif not salarios:
        problemas.append(
            Hallazgo(
                TipoHallazgo.DATO_FALTANTE,
                "Falta el salario del certificado laboral; no se infiere de los extractos.",
                campo="salario_mensual",
            )
        )
    if problemas:
        hallazgos.extend(problemas)
        return None
    salario = next(c.salario_mensual for c in certificados if c.salario_mensual is not None)
    return IngresoVerificado(valor=salario.valor, moneda=MONEDA, origen=salario)


def _contrastar_nomina(salario: int, extractos: list[ExtractoBancario]) -> Hallazgo | None:
    """Inconsistencia si el promedio de nómina difiere del salario más de la discrepancia máxima.

    Solo cuentan los extractos que indican la moneda de la política: uno sin moneda no se
    asume en COP. Se compara `|suma − salario·n| > discrepancia · salario·n` para no dividir.
    """
    abonos = [
        abono.valor
        for extracto in extractos
        if extracto.moneda is not None and extracto.moneda.valor == MONEDA
        for abono in extracto.abonos_nomina
    ]
    if not abonos:
        return None
    esperado = salario * len(abonos)
    if abs(sum(abonos) - esperado) > DISCREPANCIA_MAXIMA_INGRESO * esperado:
        return Hallazgo(
            TipoHallazgo.INCONSISTENCIA_DOCUMENTAL,
            "El promedio de nómina de los extractos difiere del salario certificado más de lo "
            "permitido.",
            campo="abonos_nomina",
            regla="nomina",
        )
    return None


def _fuera_de_moneda(moneda: str, documento: str) -> Hallazgo:
    return Hallazgo(
        TipoHallazgo.FUERA_DE_POLITICA,
        f"Ingreso en moneda {moneda} en el {documento}; la política solo cubre {MONEDA}.",
        campo="moneda",
        regla="moneda",
    )


def resultado_de_hallazgos(resultado: ResultadoIngreso) -> Resultado:
    """Hallazgos → decisión: fuera de política prevalece; cualquier otro hallazgo va a analista."""
    motivos = [
        Motivo(regla=h.regla, mensaje=h.mensaje, valores={"tipo": str(h.tipo), "campo": h.campo})
        for h in resultado.hallazgos
    ]
    tipos = {h.tipo for h in resultado.hallazgos}
    if TipoHallazgo.FUERA_DE_POLITICA in tipos:
        decision = Decision.FUERA_DE_POLITICA
    elif tipos:
        decision = Decision.ANALISTA
    else:
        decision = Decision.PREAPROBABLE
    return Resultado(decision=decision, motivos=motivos)
