"""Tests del verificador de trazas de las pruebas con modelo real (spec 009, US3, R6).

Se construyen resultados de turno a mano (con los tipos reales de #7) y se comprueba que el
verificador acepta lo correcto y nombra cada incumplimiento. Nunca se mira el texto del modelo.
"""

from __future__ import annotations

import pytest

from crediagil.agent.canal import PedidoInformacion
from crediagil.agent.negaciones import Negacion
from crediagil.agent.parada import Parada
from crediagil.agent.traza import Aviso, EventoTraza, ResultadoTurno
from crediagil.casos import Herramientas, catalogo
from crediagil.casos.verificacion import TOPE_USD, verificar


def herramienta(nombre, entrada=None, salida=None, de_subagente=False) -> EventoTraza:
    tipo = "delegacion" if nombre == "Agent" else "herramienta"
    return EventoTraza(
        tipo=tipo,
        nombre=nombre,
        entrada=entrada or {},
        salida={"ok": True} if salida is None else salida,
        de_subagente=de_subagente,
    )


def fallo(nombre, reintentable=True, entrada=None) -> EventoTraza:
    salida = {"ok": False, "error": {"codigo": "X", "reintentable": reintentable}}
    return herramienta(nombre, entrada, salida)


def turno(*eventos, avisos=(), negaciones=()) -> ResultadoTurno:
    return ResultadoTurno(
        respuesta="Texto libre del modelo que nunca se inspecciona.",
        avisos=[Aviso(tipo=a) for a in avisos],
        traza=list(eventos),
        parada=Parada.FIN_DE_TURNO,
        negaciones=list(negaciones),
    )


def caso_con(**herramientas):
    base = catalogo().por_id("dentro_de_politica")
    esperado = base.esperado.model_copy(update={"herramientas": Herramientas(**herramientas)})
    return base.model_copy(update={"esperado": esperado})


def negacion(codigo="IDENTIDAD_NO_VERIFICADA", herramienta_="registrar_solicitud") -> Negacion:
    return Negacion(herramienta_, codigo, "mensaje", "accion")


def test_el_tope_de_coste_es_el_de_las_pruebas_anteriores():
    assert TOPE_USD == 0.75


def test_sin_claves_no_hay_incumplimientos():
    assert verificar(caso_con(), turno()) == []


def test_el_texto_libre_nunca_cuenta():
    resultado = turno()
    resultado.respuesta = "llamé a registrar_solicitud y preaprobé el crédito"
    assert verificar(caso_con(debe_llamar=("registrar_solicitud",)), resultado) != []


class TestPrimera:
    def test_cumple(self):
        caso = caso_con(primera="escalar_a_analista")
        assert verificar(caso, turno(herramienta("escalar_a_analista"))) == []

    def test_otra_primera(self):
        caso = caso_con(primera="escalar_a_analista")
        incumplimientos = verificar(
            caso, turno(herramienta("buscar_solicitante"), herramienta("escalar_a_analista"))
        )
        assert [i for i in incumplimientos if i.startswith("primera")]

    def test_sin_llamadas(self):
        assert verificar(caso_con(primera="escalar_a_analista"), turno())

    def test_ignora_las_llamadas_del_subagente(self):
        caso = caso_con(primera="Agent")
        resultado = turno(
            herramienta("Agent"), herramienta("validar_extraccion", de_subagente=True)
        )
        assert verificar(caso, resultado) == []


class TestEntradaPrimera:
    def test_ruta_con_puntos(self):
        caso = caso_con(entrada_primera={"resumen.causa": "solicitud_humano"})
        bueno = turno(herramienta("escalar_a_analista", {"resumen": {"causa": "solicitud_humano"}}))
        malo = turno(herramienta("escalar_a_analista", {"resumen": {"causa": "otra"}}))
        assert verificar(caso, bueno) == []
        assert [i for i in verificar(caso, malo) if i.startswith("entrada_primera")]

    def test_ruta_que_no_existe(self):
        caso = caso_con(entrada_primera={"resumen.causa": "x"})
        assert verificar(caso, turno(herramienta("escalar_a_analista", {})))


class TestDebeYNoDebeLlamar:
    def test_debe_llamar_cumple_y_falla(self):
        caso = caso_con(debe_llamar=("registrar_solicitud", "Agent"))
        assert (
            verificar(caso, turno(herramienta("Agent"), herramienta("registrar_solicitud"))) == []
        )
        faltantes = verificar(caso, turno(herramienta("Agent")))
        assert [i for i in faltantes if i.startswith("debe_llamar")]

    def test_no_debe_llamar_cumple_y_falla(self):
        caso = caso_con(no_debe_llamar=("preaprobar_credito",))
        assert verificar(caso, turno(herramienta("registrar_solicitud"))) == []
        sobrante = verificar(caso, turno(herramienta("preaprobar_credito")))
        assert [i for i in sobrante if i.startswith("no_debe_llamar")]

    def test_una_llamada_del_subagente_no_cuenta(self):
        caso = caso_con(no_debe_llamar=("validar_extraccion",))
        resultado = turno(herramienta("validar_extraccion", de_subagente=True))
        assert verificar(caso, resultado) == []


class TestEnOrden:
    CASO = caso_con(en_orden=("buscar_solicitante", "verificar_identidad", "registrar_solicitud"))

    def test_subsecuencia_con_otras_herramientas_en_medio(self):
        resultado = turno(
            herramienta("buscar_solicitante"),
            herramienta("Agent"),
            herramienta("verificar_identidad"),
            herramienta("calcular_capacidad_pago"),
            herramienta("registrar_solicitud"),
        )
        assert verificar(self.CASO, resultado) == []

    def test_orden_incorrecto(self):
        resultado = turno(
            herramienta("verificar_identidad"),
            herramienta("buscar_solicitante"),
            herramienta("registrar_solicitud"),
        )
        assert [i for i in verificar(self.CASO, resultado) if i.startswith("en_orden")]

    def test_falta_una(self):
        resultado = turno(herramienta("buscar_solicitante"), herramienta("registrar_solicitud"))
        assert [i for i in verificar(self.CASO, resultado) if i.startswith("en_orden")]


class TestAntes:
    CASO = caso_con(antes=(("Agent", "registrar_solicitud"),))

    def test_en_el_orden_pedido(self):
        resultado = turno(herramienta("Agent"), herramienta("registrar_solicitud"))
        assert verificar(self.CASO, resultado) == []

    def test_al_reves(self):
        resultado = turno(herramienta("registrar_solicitud"), herramienta("Agent"))
        assert [i for i in verificar(self.CASO, resultado) if i.startswith("antes")]

    def test_falta_una(self):
        assert [
            i for i in verificar(self.CASO, turno(herramienta("Agent"))) if i.startswith("antes")
        ]


class TestDatosPedidos:
    def _caso(self):
        base = catalogo().por_id("dato_ausente")
        esperado = base.esperado.model_copy(update={"herramientas": Herramientas()})
        return base.model_copy(update={"esperado": esperado})

    def _con_pedido(self, *datos) -> ResultadoTurno:
        resultado = turno()
        resultado.pedidos_informacion = [PedidoInformacion(datos=tuple(datos), motivo="falta")]
        return resultado

    @pytest.mark.parametrize("dato", ["salario mensual", "ingreso mensual", "Salario", "sueldo"])
    def test_el_pedido_nombra_el_dato(self, dato):
        assert verificar(self._caso(), self._con_pedido(dato)) == []

    def test_no_se_pidio_nada(self):
        assert [i for i in verificar(self._caso(), turno()) if i.startswith("datos_faltantes")]

    def test_se_pidio_otra_cosa(self):
        assert [
            i
            for i in verificar(self._caso(), self._con_pedido("fecha de expedición"))
            if i.startswith("datos_faltantes")
        ]

    def test_solo_aplica_cuando_el_resultado_es_solicitar_dato(self):
        assert verificar(caso_con(), turno()) == []


class TestSinExito:
    def test_una_llamada_exitosa_incumple(self):
        caso = caso_con(sin_exito=("preaprobar_credito",))
        assert [
            i
            for i in verificar(caso, turno(herramienta("preaprobar_credito")))
            if i.startswith("sin_exito")
        ]

    def test_un_intento_negado_no_incumple(self):
        caso = caso_con(sin_exito=("preaprobar_credito",))
        negado = herramienta("preaprobar_credito", salida={"ok": False, "error": {}})
        assert verificar(caso, turno(negado)) == []

    def test_sin_llamadas_cumple(self):
        assert verificar(caso_con(sin_exito=("preaprobar_credito",)), turno()) == []


class TestAvisos:
    def test_avisos_requeridos(self):
        caso = caso_con(avisos=("credito_preaprobado",))
        assert verificar(caso, turno(avisos=["credito_preaprobado"])) == []
        assert [i for i in verificar(caso, turno()) if i.startswith("avisos")]

    def test_avisos_prohibidos(self):
        caso = caso_con(sin_avisos=("credito_preaprobado",))
        assert verificar(caso, turno(avisos=["escalamiento"])) == []
        assert [
            i
            for i in verificar(caso, turno(avisos=["credito_preaprobado"]))
            if i.startswith("sin_avisos")
        ]


class TestValidaciones:
    def _validar(self, ok=True):
        salida = {"ok": ok} if ok else {"ok": False, "error": {}}
        return herramienta("validar_extraccion", salida=salida, de_subagente=True)

    def test_dentro_del_tope(self):
        caso = caso_con(max_validaciones_exitosas=1)
        assert verificar(caso, turno(self._validar(), self._validar(ok=False))) == []

    def test_por_encima_del_tope(self):
        caso = caso_con(max_validaciones_exitosas=1)
        resultado = turno(self._validar(), self._validar())
        assert [i for i in verificar(caso, resultado) if i.startswith("max_validaciones")]


class TestLlamadasRepetidas:
    def test_distintas_o_con_otra_entrada_no_incumplen(self):
        caso = caso_con(sin_llamadas_repetidas=True)
        resultado = turno(
            herramienta("verificar_identidad", {"id": 1}),
            herramienta("verificar_identidad", {"id": 2}),
            herramienta("registrar_solicitud", {"id": 1}),
        )
        assert verificar(caso, resultado) == []

    def test_una_exitosa_repetida_incumple(self):
        caso = caso_con(sin_llamadas_repetidas=True)
        resultado = turno(
            herramienta("registrar_solicitud", {"id": 1}),
            herramienta("registrar_solicitud", {"id": 1}),
        )
        assert [i for i in verificar(caso, resultado) if i.startswith("sin_llamadas_repetidas")]

    def test_repetir_la_que_fallo_es_lo_esperado(self):
        caso = caso_con(sin_llamadas_repetidas=True)
        resultado = turno(
            fallo("verificar_identidad", entrada={"id": 1}),
            herramienta("verificar_identidad", {"id": 1}),
        )
        assert verificar(caso, resultado) == []


class TestReintento:
    CASO = caso_con(reintenta_tras_falla=True)

    def test_falla_transitoria_y_reintento_exitoso(self):
        resultado = turno(fallo("verificar_identidad"), herramienta("verificar_identidad"))
        assert verificar(self.CASO, resultado) == []

    def test_sin_falla_incumple(self):
        resultado = turno(herramienta("verificar_identidad"))
        assert [i for i in verificar(self.CASO, resultado) if i.startswith("reintenta")]

    def test_falla_no_reintentable_incumple(self):
        resultado = turno(
            fallo("verificar_identidad", reintentable=False), herramienta("verificar_identidad")
        )
        assert [i for i in verificar(self.CASO, resultado) if i.startswith("reintenta")]

    def test_falla_sin_reintento_incumple(self):
        resultado = turno(fallo("verificar_identidad"), herramienta("registrar_solicitud"))
        assert [i for i in verificar(self.CASO, resultado) if i.startswith("reintenta")]


class TestSiIntenta:
    CASO = caso_con(
        si_intenta={
            "herramientas": ("registrar_solicitud", "preaprobar_credito"),
            "codigo_negacion": "IDENTIDAD_NO_VERIFICADA",
            "aviso": "bloqueo_regla",
            "max_intentos": 2,
        }
    )

    def test_sin_intentos_se_cumple(self):
        assert verificar(self.CASO, turno(herramienta("buscar_solicitante"))) == []

    def test_intento_con_negacion_y_aviso(self):
        resultado = turno(
            herramienta("registrar_solicitud", salida={"ok": False, "error": {}}),
            avisos=["bloqueo_regla"],
            negaciones=[negacion()],
        )
        assert verificar(self.CASO, resultado) == []

    def test_intento_sin_la_negacion(self):
        resultado = turno(herramienta("registrar_solicitud"), avisos=["bloqueo_regla"])
        assert [i for i in verificar(self.CASO, resultado) if i.startswith("si_intenta")]

    def test_intento_con_otro_codigo(self):
        resultado = turno(
            herramienta("registrar_solicitud"),
            avisos=["bloqueo_regla"],
            negaciones=[negacion("NO_PREAPROBABLE")],
        )
        assert [i for i in verificar(self.CASO, resultado) if i.startswith("si_intenta")]

    def test_intento_sin_el_aviso(self):
        resultado = turno(herramienta("registrar_solicitud"), negaciones=[negacion()])
        assert [i for i in verificar(self.CASO, resultado) if i.startswith("si_intenta")]

    def test_demasiados_intentos(self):
        resultado = turno(
            *[herramienta("registrar_solicitud") for _ in range(3)],
            avisos=["bloqueo_regla"],
            negaciones=[negacion()],
        )
        assert [i for i in verificar(self.CASO, resultado) if i.startswith("si_intenta")]


def test_varios_incumplimientos_se_listan_todos():
    caso = caso_con(primera="escalar_a_analista", debe_llamar=("registrar_solicitud",))
    incumplimientos = verificar(caso, turno(herramienta("buscar_solicitante")))
    assert len(incumplimientos) == 2


def test_los_casos_del_catalogo_son_verificables_contra_un_turno_ideal():
    """Cada caso obligatorio declara claves que el verificador entiende (sin errores de tipo)."""
    for caso in catalogo().obligatorios:
        assert isinstance(verificar(caso, turno()), list)
