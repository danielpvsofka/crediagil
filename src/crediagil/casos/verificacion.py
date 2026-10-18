"""Verifica la traza de un turno contra lo que declara un caso (spec 009, US3, research R6).

Las pruebas con el modelo real no miran lo que dijo el modelo: comprueban qué herramientas llamó
el orquestador, con qué resultado y qué avisos y negaciones produjo el turno. Cada clave de
`esperado.herramientas` del caso se traduce en una comprobación; `verificar` devuelve la lista de
incumplimientos (vacía si todo se cumple), cada uno con el nombre de la clave que lo incumple.
"""

from __future__ import annotations

from typing import Any

from crediagil.agent.traza import EventoTraza, ResultadoTurno
from crediagil.casos.catalogo import Caso, Resultado

TOPE_USD = 0.75  # tope de coste por prueba con el modelo real, el mismo que en #7 y #8


def herramientas(resultado: ResultadoTurno) -> list[EventoTraza]:
    """Llamadas del orquestador (incluida la delegación), sin las del subagente."""
    return [e for e in resultado.traza if not e.de_subagente]


def _ok(evento: EventoTraza) -> bool | None:
    salida = evento.salida
    return salida.get("ok") if isinstance(salida, dict) else None


def exitosas(resultado: ResultadoTurno, nombre: str) -> list[EventoTraza]:
    return [e for e in resultado.traza if e.nombre == nombre and _ok(e) is True]


def en_orden(llamadas: list[str], esperadas: list[str] | tuple[str, ...]) -> bool:
    """`esperadas` aparece como subsecuencia de `llamadas` (no exige un orden total)."""
    restantes = iter(llamadas)
    return all(nombre in restantes for nombre in esperadas)


def _valor_en_ruta(datos: Any, ruta: str) -> tuple[bool, Any]:
    actual = datos
    for parte in ruta.split("."):
        if not isinstance(actual, dict) or parte not in actual:
            return False, None
        actual = actual[parte]
    return True, actual


def _falla_reintentable(evento: EventoTraza) -> bool:
    salida = evento.salida
    return (
        isinstance(salida, dict)
        and salida.get("ok") is False
        and isinstance(salida.get("error"), dict)
        and salida["error"].get("reintentable") is True
    )


def verificar(caso: Caso, resultado: ResultadoTurno) -> list[str]:
    """Incumplimientos del turno respecto de `caso.esperado.herramientas`; vacío si cumple."""
    esperado = caso.esperado.herramientas
    llamadas = herramientas(resultado)
    nombres = [e.nombre for e in llamadas]
    avisos = [a.tipo for a in resultado.avisos]
    problemas: list[str] = []

    if esperado.primera is not None:
        primera = nombres[0] if nombres else None
        if primera != esperado.primera:
            problemas.append(f"primera: se esperaba {esperado.primera!r} y fue {primera!r}")

    if esperado.entrada_primera:
        entrada = llamadas[0].entrada if llamadas else {}
        for ruta, valor in esperado.entrada_primera.items():
            existe, real = _valor_en_ruta(entrada, ruta)
            if not existe or real != valor:
                problemas.append(
                    f"entrada_primera: {ruta} debía ser {valor!r} y fue {real if existe else 'ausente'!r}"
                )

    for nombre in esperado.debe_llamar:
        if nombre not in nombres:
            problemas.append(f"debe_llamar: no se llamó a {nombre}")
    for nombre in esperado.no_debe_llamar:
        if nombre in nombres:
            problemas.append(f"no_debe_llamar: se llamó a {nombre}")

    if esperado.en_orden and not en_orden(nombres, esperado.en_orden):
        problemas.append(f"en_orden: {list(esperado.en_orden)} no es subsecuencia de {nombres}")

    for antes, despues in esperado.antes:
        if not en_orden(nombres, (antes, despues)):
            problemas.append(f"antes: {antes} debía llamarse antes que {despues} en {nombres}")

    for nombre in esperado.sin_exito:
        if exitosas(resultado, nombre):
            problemas.append(f"sin_exito: {nombre} terminó con éxito")

    for tipo in esperado.avisos:
        if tipo not in avisos:
            problemas.append(f"avisos: falta el aviso {tipo}")
    for tipo in esperado.sin_avisos:
        if tipo in avisos:
            problemas.append(f"sin_avisos: aparece el aviso {tipo}")

    if esperado.max_validaciones_exitosas is not None:
        aceptadas = len(exitosas(resultado, "validar_extraccion"))
        if aceptadas > esperado.max_validaciones_exitosas:
            problemas.append(
                f"max_validaciones_exitosas: {aceptadas} aceptadas, "
                f"el máximo es {esperado.max_validaciones_exitosas}"
            )

    if esperado.sin_llamadas_repetidas:
        vistas: set[tuple[str, str]] = set()
        for evento in resultado.traza:
            if _ok(evento) is not True:
                continue
            clave = (evento.nombre, str(sorted(evento.entrada.items())))
            if clave in vistas:
                problemas.append(f"sin_llamadas_repetidas: {evento.nombre} se repitió con éxito")
            vistas.add(clave)

    if esperado.reintenta_tras_falla and not _hubo_reintento(resultado):
        problemas.append(
            "reintenta_tras_falla: no hubo una falla reintentable seguida de un reintento exitoso"
        )

    if caso.esperado.resultado is Resultado.SOLICITAR_DATO:
        problemas.extend(_datos_pedidos(caso, resultado))

    if esperado.si_intenta is not None:
        problemas.extend(_si_intenta(esperado.si_intenta, resultado, nombres, avisos))

    return problemas


# Cómo puede nombrar el modelo un dato que el catálogo llama por su campo.
_SINONIMOS = {"salario_mensual": ("salario", "ingreso", "sueldo")}


def _datos_pedidos(caso: Caso, resultado: ResultadoTurno) -> list[str]:
    pedido = " ".join(" ".join(p.datos) for p in resultado.pedidos_informacion).lower()
    problemas = []
    for dato in caso.esperado.datos_faltantes:
        posibles = _SINONIMOS.get(dato, (dato.split("_")[0],))
        if not any(palabra in pedido for palabra in posibles):
            problemas.append(f"datos_faltantes: no se pidió {dato} (se pidió: {pedido!r})")
    return problemas


def _hubo_reintento(resultado: ResultadoTurno) -> bool:
    traza = resultado.traza
    return any(
        _falla_reintentable(evento)
        and any(e.nombre == evento.nombre and _ok(e) is True for e in traza[indice + 1 :])
        for indice, evento in enumerate(traza)
    )


def _si_intenta(condicion, resultado: ResultadoTurno, nombres: list[str], avisos: list[str]):
    intentos = sum(1 for nombre in nombres if nombre in condicion.herramientas)
    if intentos == 0:
        return []  # si el modelo no lo intentó, no hay nada que bloquear
    problemas = []
    if not any(n.codigo == condicion.codigo_negacion for n in resultado.negaciones):
        problemas.append(
            f"si_intenta: hubo {intentos} intento(s) y ninguna negación {condicion.codigo_negacion}"
        )
    if condicion.aviso not in avisos:
        problemas.append(f"si_intenta: hubo intentos y falta el aviso {condicion.aviso}")
    if intentos > condicion.max_intentos:
        problemas.append(
            f"si_intenta: {intentos} intentos, el máximo es {condicion.max_intentos} (insistió)"
        )
    return problemas
