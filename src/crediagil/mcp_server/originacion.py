"""Herramientas de originación del core simulado (spec 005, FR-003–FR-015).

Lógica pura sobre `AlmacenEstado`: lanza `ErrorCore` y no sabe nada del protocolo MCP. Las reglas
se evalúan con `crediagil.policy` y `crediagil.extraction` (única fuente de parámetros); el core
las revalida antes de comprometer (defensa en profundidad, además de los hooks del SDK de #6).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

from pydantic import ValidationError

from crediagil.extraction import (
    CertificadoLaboral,
    DocumentoNoSoportado,
    Hallazgo,
    ResultadoIngreso,
    TipoHallazgo,
    derivar_ingreso,
    resultado_de_hallazgos,
    validar_documento,
)
from crediagil.mcp_server.errores import ErrorCore, TipoError
from crediagil.mcp_server.estado import AlmacenEstado, siguiente_id
from crediagil.mcp_server.identidad import identidad_vigente
from crediagil.policy import (
    Decision,
    Resultado,
    calcular_cuota,
    combinar,
    evaluar_discrepancia,
    evaluar_preaprobacion,
)
from crediagil.policy.params import PROPORCION_MAXIMA_CUOTA_INGRESO, TASA_MENSUAL

REGISTRADA, PREAPROBADA, ESCALADA = "REGISTRADA", "PREAPROBADA", "ESCALADA"


# ---------------------------------------------------------------- validar_extraccion


def extraer(datos: dict, texto: str):
    """Valida una extracción; devuelve (documento, campos faltantes) o un error reintentable."""
    try:
        documento = validar_documento(datos, texto)
    except ValidationError as exc:
        raise _error_de_extraccion(exc) from None
    faltantes = [
        nombre
        for nombre, valor in documento
        if valor is None and nombre in _campos_opcionales(type(documento))
    ]
    return documento, faltantes


def _campos_opcionales(modelo) -> set[str]:
    return {n for n, campo in modelo.model_fields.items() if not campo.is_required()}


def _error_de_extraccion(exc: ValidationError) -> ErrorCore:
    errores = exc.errors(include_url=False)
    no_literales = [e["ctx"]["campo"] for e in errores if e["type"] == "fragmento_no_literal"]
    if no_literales:
        return ErrorCore(
            TipoError.VALIDACION,
            "FRAGMENTO_NO_LITERAL",
            "Algún fragmento no aparece literalmente en el documento; corrige la extracción.",
            {"campos": no_literales},
            reintentable=True,
        )
    return ErrorCore(
        TipoError.VALIDACION,
        "EXTRACCION_INVALIDA",
        "La extracción no cumple el esquema; corrígela y vuelve a validar.",
        {"errores": [{"campo": _ruta(e["loc"]), "motivo": e["msg"]} for e in errores]},
        reintentable=True,
    )


def _ruta(loc: tuple) -> str:
    # El primer elemento es el discriminador del tipo de documento; un `loc` sin campo bajo él
    # (tipo ausente o desconocido) señala al propio campo `tipo`.
    partes = [str(p) for p in loc[1:]]
    return ".".join(partes) if partes else "tipo"


# ---------------------------------------------------------------- registrar_solicitud


def registrar_solicitud(
    almacen: AlmacenEstado,
    id_solicitante: str,
    monto: int,
    plazo_meses: int,
    ingreso_declarado: int,
    documentos: list[dict],
    ahora: datetime | None = None,
) -> dict:
    """Registra la solicitud con procedencia de cada dato y devuelve su evaluación."""
    # Identidad primero: nada se revela ni se valida sin identidad vigente.
    _exigir_identidad(almacen.leer(), id_solicitante)
    cuota = _validar_credito(monto, plazo_meses)
    if type(ingreso_declarado) is not int or ingreso_declarado < 0:
        raise _parametros(
            "El ingreso declarado debe ser un entero no negativo.", "ingreso_declarado"
        )
    extraidos = _extraer_documentos(documentos)

    resultado_ingreso = derivar_ingreso([doc for _, doc in extraidos])
    tipos = {h.tipo for h in resultado_ingreso.hallazgos}
    if resultado_ingreso.ingreso is None and TipoHallazgo.FUERA_DE_POLITICA not in tipos:
        faltantes = list(
            dict.fromkeys(
                h.campo
                for h in resultado_ingreso.hallazgos
                if h.tipo is TipoHallazgo.DATO_FALTANTE and h.campo
            )
        )
        raise ErrorCore(
            TipoError.NEGOCIO,
            "INGRESO_NO_VERIFICABLE",
            "El ingreso no se puede verificar con los documentos aportados; pide el certificado "
            "laboral con el salario o escala a un analista.",
            {"datos_faltantes": faltantes},
        )

    ingreso = resultado_ingreso.ingreso
    evaluacion = _evaluacion(
        _evaluar(
            monto,
            plazo_meses,
            ingreso_declarado,
            ingreso and ingreso.valor,
            resultado_ingreso.hallazgos,
        ),
        cuota,
    )
    solicitud = {
        "id_solicitante": id_solicitante,
        "monto": monto,
        "plazo_meses": plazo_meses,
        "ingreso_declarado": ingreso_declarado,
        "ingreso_verificado": _ingreso_con_procedencia(ingreso, extraidos),
        "datos": [dato for id_doc, doc in extraidos for dato in _procedencia(doc, id_doc)],
        "hallazgos": [
            {"tipo": str(h.tipo), "mensaje": h.mensaje, "campo": h.campo, "regla": h.regla}
            for h in resultado_ingreso.hallazgos
        ],
        "evaluacion": evaluacion,
        "estado": REGISTRADA,
        "registrada_en": _marca(ahora),
        "preaprobada_en": None,
        "escalada_en": None,
    }
    with almacen.transaccion() as datos:
        # Se revisa otra vez: el solicitante pudo quedar bloqueado mientras se evaluaba.
        _exigir_identidad(datos, id_solicitante)
        id_solicitud = siguiente_id(datos["solicitudes"], "SLC")
        datos["solicitudes"][id_solicitud] = {"id_solicitud": id_solicitud, **solicitud}
    return {"id_solicitud": id_solicitud, "evaluacion": evaluacion}


def _exigir_identidad(datos: dict, id_solicitante: str) -> None:
    solicitante = datos["solicitantes"].get(id_solicitante)
    if solicitante is None or not identidad_vigente(solicitante):
        raise ErrorCore(
            TipoError.PERMISOS,
            "IDENTIDAD_NO_VERIFICADA",
            "El solicitante no tiene la identidad verificada; verifícala antes de continuar o "
            "escala a un analista si está bloqueado.",
            {"id_solicitante": id_solicitante},
        )


def _validar_credito(monto, plazo_meses) -> int:
    try:
        return calcular_cuota(monto, plazo_meses)
    except ValueError as exc:
        campo = "plazo_meses" if "plazo" in str(exc) else "monto"
        raise _parametros(str(exc), campo) from None


def _extraer_documentos(documentos) -> list[tuple[str, object]]:
    if not isinstance(documentos, list) or not documentos:
        raise _parametros("Envía al menos un documento.", "documentos")
    extraidos, vistos = [], set()
    for documento in documentos:
        if not isinstance(documento, dict):
            raise _parametros("Cada documento debe ser un objeto.", "documentos")
        id_documento = documento.get("id_documento")
        if not isinstance(id_documento, str) or not id_documento.strip() or id_documento in vistos:
            raise _parametros("Cada documento necesita un id_documento único.", "id_documento")
        vistos.add(id_documento)
        validado, _ = extraer(documento.get("datos"), documento.get("texto"))
        extraidos.append((id_documento, validado))
    return extraidos


def _procedencia(documento, id_documento: str) -> list[dict]:
    if isinstance(documento, DocumentoNoSoportado):
        return []
    return [
        {
            "documento_tipo": documento.tipo,
            "campo": nombre,
            "valor": campo.model_dump(mode="json")["valor"],
            "id_documento": id_documento,
            "fragmento": campo.fragmento,
        }
        for nombre, campo in documento.campos_extraidos()
    ]


def _ingreso_con_procedencia(ingreso, extraidos) -> dict | None:
    if ingreso is None:
        return None
    id_documento = next(
        (
            id_doc
            for id_doc, doc in extraidos
            if isinstance(doc, CertificadoLaboral) and doc.salario_mensual == ingreso.origen
        ),
        None,
    )
    if id_documento is None:  # derivar_ingreso siempre toma el salario de un certificado
        raise ErrorCore(
            TipoError.TRANSITORIO,
            "ERROR_INTERNO",
            "No se pudo determinar el documento de origen del ingreso; reintenta.",
        )
    return {
        "valor": ingreso.valor,
        "id_documento": id_documento,
        "fragmento": ingreso.origen.fragmento,
    }


def _evaluar(monto, plazo_meses, declarado, ingreso, hallazgos) -> Resultado:
    partes = [evaluar_preaprobacion(monto, plazo_meses, ingreso)]
    if ingreso is not None:
        partes.append(evaluar_discrepancia(declarado, ingreso))
    partes.append(resultado_de_hallazgos(ResultadoIngreso(ingreso=None, hallazgos=hallazgos)))
    return combinar(*partes)


def _evaluacion(resultado: Resultado, cuota: int) -> dict:
    return {
        "preaprobable_automaticamente": resultado.decision is Decision.PREAPROBABLE,
        "decision": str(resultado.decision),
        "cuota": cuota,
        "causas_escalamiento": [
            {"regla": m.regla, "mensaje": m.mensaje, "valores": m.valores}
            for m in resultado.motivos
        ],
    }


# ---------------------------------------------------------------- calcular_capacidad_pago


def simular(monto: int, plazo_meses: int, ingreso_mensual: int | None = None) -> dict:
    """SOLO SIMULA: no lee ni escribe estado."""
    cuota = _validar_credito(monto, plazo_meses)
    resultado = {"cuota": cuota, "tasa_mensual": str(TASA_MENSUAL)}
    if ingreso_mensual is not None:
        if type(ingreso_mensual) is not int or ingreso_mensual <= 0:
            raise _parametros("El ingreso mensual debe ser un entero positivo.", "ingreso_mensual")
        proporcion = (Decimal(cuota) / ingreso_mensual).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )
        resultado["proporcion_cuota_ingreso"] = str(proporcion)
        resultado["dentro_de_proporcion_maxima"] = (
            cuota <= PROPORCION_MAXIMA_CUOTA_INGRESO * ingreso_mensual
        )
    return resultado


# ---------------------------------------------------------------- preaprobar_credito


def preaprobar_credito(
    almacen: AlmacenEstado, id_solicitud: str, ahora: datetime | None = None
) -> dict:
    """COMPROMETE A CREDIÁGIL: revalida identidad y reglas con los datos guardados."""
    with almacen.transaccion() as datos:
        solicitud = datos["solicitudes"].get(id_solicitud)
        if solicitud is None:
            raise _solicitud_error(
                "SOLICITUD_NO_ENCONTRADA", "No existe esa solicitud.", id_solicitud
            )
        if solicitud["estado"] == ESCALADA:
            raise _solicitud_error(
                "SOLICITUD_ESCALADA",
                "La solicitud ya fue escalada a un analista; no se puede preaprobar.",
                id_solicitud,
            )
        if solicitud["estado"] == PREAPROBADA:
            return solicitud["preaprobacion"]
        _exigir_identidad(datos, solicitud["id_solicitante"])

        # Nunca se usa la evaluación guardada para decidir: se recalcula con la política vigente.
        ingreso = solicitud["ingreso_verificado"]
        hallazgos = [
            Hallazgo(TipoHallazgo(h["tipo"]), h["mensaje"], h["campo"], h["regla"])
            for h in solicitud["hallazgos"]
        ]
        resultado = _evaluar(
            solicitud["monto"],
            solicitud["plazo_meses"],
            solicitud["ingreso_declarado"],
            ingreso and ingreso["valor"],
            hallazgos,
        )
        if resultado.decision is not Decision.PREAPROBABLE:
            raise ErrorCore(
                TipoError.NEGOCIO,
                "NO_PREAPROBABLE",
                "La solicitud no cumple las condiciones de preaprobación; escala a un analista.",
                {"causas": _evaluacion(resultado, resultado.cuota)["causas_escalamiento"]},
            )
        preaprobacion = {
            "id_solicitud": id_solicitud,
            "monto": solicitud["monto"],
            "plazo_meses": solicitud["plazo_meses"],
            "cuota": resultado.cuota,
            "tasa_mensual": str(TASA_MENSUAL),
        }
        solicitud.update(
            estado=PREAPROBADA, preaprobada_en=_marca(ahora), preaprobacion=preaprobacion
        )
    return preaprobacion


# ---------------------------------------------------------------- auxiliares


def _solicitud_error(codigo: str, mensaje: str, id_solicitud: str) -> ErrorCore:
    return ErrorCore(TipoError.NEGOCIO, codigo, mensaje, {"id_solicitud": id_solicitud})


def _parametros(mensaje: str, campo: str) -> ErrorCore:
    return ErrorCore(TipoError.VALIDACION, "PARAMETROS_INVALIDOS", mensaje, {"campo": campo})


def _marca(ahora: datetime | None) -> str:
    return (ahora or datetime.now(UTC)).isoformat()
