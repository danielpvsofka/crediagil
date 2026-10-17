"""Reglas 2 (preaprobación) y 3 (discrepancia de ingreso) de la constitución.

Las comparaciones se hacen sin dividir (`cuota ≤ proporción · ingreso`) para que los bordes
exactos sean exactos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from crediagil.policy.cuota import calcular_cuota
from crediagil.policy.params import (
    DISCREPANCIA_MAXIMA_INGRESO,
    MONTO_MAXIMO_PREAPROBACION,
    PROPORCION_MAXIMA_CUOTA_INGRESO,
)


class Decision(StrEnum):
    PREAPROBABLE = "preaprobable"
    ANALISTA = "analista"
    FUERA_DE_POLITICA = "fuera_de_politica"


# Al combinar, gana la decisión más restrictiva.
PRECEDENCIA = [Decision.PREAPROBABLE, Decision.ANALISTA, Decision.FUERA_DE_POLITICA]


@dataclass(frozen=True)
class Motivo:
    regla: str
    mensaje: str
    valores: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Resultado:
    decision: Decision
    cuota: int | None = None
    motivos: list[Motivo] = field(default_factory=list)


def es_entero(valor) -> bool:
    # bool es subclase de int: se rechaza explícitamente.
    return type(valor) is int


def evaluar_preaprobacion(
    monto: int, plazo_meses: int, ingreso_verificado: int | None
) -> Resultado:
    """Regla 2: preaprobable solo si monto ≤ tope y cuota ≤ proporción máxima del ingreso."""
    if ingreso_verificado is not None and not es_entero(ingreso_verificado):
        raise ValueError(
            f"El ingreso verificado debe ser un entero de pesos: {ingreso_verificado!r}"
        )
    cuota = calcular_cuota(monto, plazo_meses)
    motivos = []
    if monto > MONTO_MAXIMO_PREAPROBACION:
        motivos.append(
            Motivo(
                regla="regla_2",
                mensaje="El monto supera el máximo de preaprobación automática.",
                valores={"monto": monto, "maximo": MONTO_MAXIMO_PREAPROBACION},
            )
        )
    if ingreso_verificado is None or ingreso_verificado <= 0:
        motivos.append(
            Motivo(
                regla="regla_2",
                mensaje="No hay ingreso verificado.",
                valores={"ingreso_verificado": ingreso_verificado},
            )
        )
    elif cuota > PROPORCION_MAXIMA_CUOTA_INGRESO * ingreso_verificado:
        motivos.append(
            Motivo(
                regla="regla_2",
                mensaje="La cuota supera la proporción máxima del ingreso verificado.",
                valores={
                    "cuota": cuota,
                    "ingreso_verificado": ingreso_verificado,
                    "proporcion_maxima": str(PROPORCION_MAXIMA_CUOTA_INGRESO),
                },
            )
        )
    decision = Decision.ANALISTA if motivos else Decision.PREAPROBABLE
    return Resultado(decision=decision, cuota=cuota, motivos=motivos)


def evaluar_discrepancia(declarado: int, verificado: int) -> Resultado:
    """Regla 3: escala si el declarado difiere del verificado más de la discrepancia máxima.

    Sin ingreso verificado la regla 2 ya envía la solicitud a analista: evalúala antes.
    """
    if not es_entero(verificado) or verificado <= 0:
        raise ValueError(f"El ingreso verificado debe ser un entero positivo: {verificado!r}")
    if not es_entero(declarado) or declarado < 0:
        raise ValueError(f"El ingreso declarado debe ser un entero no negativo: {declarado!r}")
    if abs(declarado - verificado) > DISCREPANCIA_MAXIMA_INGRESO * verificado:
        motivo = Motivo(
            regla="regla_3",
            mensaje="El ingreso declarado difiere del verificado más de lo permitido.",
            valores={
                "declarado": declarado,
                "verificado": verificado,
                "discrepancia_maxima": str(DISCREPANCIA_MAXIMA_INGRESO),
            },
        )
        return Resultado(decision=Decision.ANALISTA, motivos=[motivo])
    return Resultado(decision=Decision.PREAPROBABLE)


def combinar(*resultados: Resultado) -> Resultado:
    """Decisión más restrictiva, todos los motivos y la primera cuota disponible."""
    if not resultados:
        raise ValueError("No hay resultados que combinar")
    decision = max((r.decision for r in resultados), key=PRECEDENCIA.index)
    cuota = next((r.cuota for r in resultados if r.cuota is not None), None)
    motivos = [m for r in resultados for m in r.motivos]
    return Resultado(decision=decision, cuota=cuota, motivos=motivos)
