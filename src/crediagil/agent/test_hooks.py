"""Tests de los hooks de las reglas 1 y 2: contracts/hooks.md (FR-001–FR-013).

Los hooks se invocan como lo hace el SDK: con el diccionario de entrada de `PreToolUse` y
comprobando la salida del SDK, sin modelo, sin red y sin clave de API.
"""

from __future__ import annotations

from datetime import date

import pytest
from claude_agent_sdk import ClaudeAgentOptions, HookMatcher
from filelock import FileLock

from crediagil.agent import hooks as modulo_hooks
from crediagil.agent.hooks import (
    ACCIONES,
    PERMITIR,
    Decision,
    crear_hook_preaprobacion,
    crear_hook_registro,
    crear_hooks,
    formatear_motivo,
    salida_deny,
)
from crediagil.agent.negaciones import RegistroNegaciones
from crediagil.mcp_server.documentos_prueba import doc_certificado, doc_extracto
from crediagil.mcp_server.errores import ErrorCore
from crediagil.mcp_server.estado import AlmacenEstado
from crediagil.mcp_server.identidad import verificar_identidad
from crediagil.mcp_server.originacion import registrar_solicitud
from crediagil.mcp_server.semilla import SOLICITANTES_SEMILLA

SERVIDOR = "crediagil-core"
AHORA = "2026-10-17T15:30:00+00:00"
ANA = SOLICITANTES_SEMILLA[0]
HOY = date(2026, 10, 17)
# Cuota de 5.000.000 a 12 meses = 467.010; el 30% exacto corresponde a un ingreso de 1.556.700.
INGRESO_30_EXACTO = 1_556_700

CODIGOS = {
    "IDENTIDAD_NO_VERIFICADA",
    "SOLICITUD_NO_ENCONTRADA",
    "SOLICITUD_ESCALADA",
    "HALLAZGOS_DOCUMENTALES",
    "NO_PREAPROBABLE",
    "ESTADO_ILEGIBLE",
    "ENTRADA_INVALIDA",
    "ERROR_INTERNO",
    # Delegación al subagente (spec 007).
    "SUBAGENTE_NO_PERMITIDO",
    "DOCUMENTO_DESCONOCIDO",
    "DELEGACION_INCOMPLETA",
}


# ---------------------------------------------------------------- piezas comunes


class TestPiezasComunes:
    def test_hay_una_accion_para_cada_codigo(self):
        assert set(ACCIONES) == CODIGOS
        assert all(accion.strip() for accion in ACCIONES.values())

    def test_permitir_es_vacio(self):
        assert PERMITIR == {}
        assert Decision.permitir_llamada().permitir is True

    def test_negar_conserva_los_datos(self):
        decision = Decision.negar(
            "SOLICITUD_NO_ENCONTRADA", "No existe esa solicitud.", {"id_solicitud": "SLC-9999"}
        )
        assert decision.permitir is False
        assert decision.codigo == "SOLICITUD_NO_ENCONTRADA"
        assert decision.accion == ACCIONES["SOLICITUD_NO_ENCONTRADA"]
        assert decision.detalles == {"id_solicitud": "SLC-9999"}

    def test_negar_con_codigo_desconocido(self):
        with pytest.raises(ValueError, match="código"):
            Decision.negar("OTRO_CODIGO", "mensaje")

    def test_formato_del_motivo(self):
        decision = Decision.negar("ENTRADA_INVALIDA", "Falta el identificador.")
        assert formatear_motivo(decision) == (
            f"[ENTRADA_INVALIDA] Falta el identificador. Acción: {ACCIONES['ENTRADA_INVALIDA']}"
        )

    def test_salida_deny_tiene_el_formato_del_sdk(self):
        decision = Decision.negar("ENTRADA_INVALIDA", "Falta el identificador.")
        assert salida_deny(decision) == {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": formatear_motivo(decision),
            }
        }


# ---------------------------------------------------------------- helpers del SDK


def entrada(herramienta: str, servidor: str = SERVIDOR, **tool_input) -> dict:
    """Entrada de `PreToolUse` tal como la entrega el SDK."""
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": f"mcp__{servidor}__{herramienta}",
        "tool_input": tool_input,
        "tool_use_id": "t1",
        "session_id": "s1",
        "transcript_path": "",
        "cwd": ".",
    }


async def invocar(hook, datos_entrada: dict) -> dict:
    return await hook(datos_entrada, "t1", {"signal": None})


def veredicto(salida: dict) -> tuple[str | None, str]:
    """(decisión de permiso, motivo) de una salida del SDK; (None, "") si no hay opinión."""
    especifica = salida.get("hookSpecificOutput", {})
    return especifica.get("permissionDecision"), especifica.get("permissionDecisionReason", "")


@pytest.fixture
def almacen(tmp_path):
    almacen = AlmacenEstado(tmp_path / "estado.json")
    almacen.leer()  # el core crea el estado al arrancar; los hooks nunca lo crean
    return almacen


def verificar(almacen, solicitante=ANA):
    verificar_identidad(
        almacen, solicitante["id_solicitante"], solicitante["fecha_nacimiento"], hoy=HOY
    )


def bloquear(almacen, solicitante=ANA):
    for _ in range(3):
        with pytest.raises(ErrorCore):
            verificar_identidad(almacen, solicitante["id_solicitante"], "2000-01-01", hoy=HOY)


# ---------------------------------------------------------------- US1: hook de registro


@pytest.mark.anyio
class TestHookRegistro:
    @pytest.fixture
    def hook(self, almacen):
        return crear_hook_registro(almacen)

    async def llamar(self, hook, **tool_input):
        return await invocar(hook, entrada("registrar_solicitud", **tool_input))

    async def test_identidad_vigente_permite(self, almacen, hook):
        verificar(almacen)
        assert await self.llamar(hook, id_solicitante=ANA["id_solicitante"]) == {}

    async def test_sin_verificar_niega(self, hook):
        salida = await self.llamar(hook, id_solicitante=ANA["id_solicitante"])
        decision, motivo = veredicto(salida)
        assert decision == "deny"
        assert motivo.startswith("[IDENTIDAD_NO_VERIFICADA]")
        assert salida["hookSpecificOutput"]["hookEventName"] == "PreToolUse"

    async def test_bloqueado_despues_de_verificar_niega(self, almacen, hook):
        verificar(almacen)
        bloquear(almacen)
        decision, motivo = veredicto(await self.llamar(hook, id_solicitante=ANA["id_solicitante"]))
        assert decision == "deny"
        assert motivo.startswith("[IDENTIDAD_NO_VERIFICADA]")

    async def test_solicitante_inexistente_niega(self, hook):
        decision, motivo = veredicto(await self.llamar(hook, id_solicitante="SOL-9999"))
        assert decision == "deny"
        assert motivo.startswith("[IDENTIDAD_NO_VERIFICADA]")

    async def test_no_evalua_umbrales(self, almacen, hook):
        verificar(almacen)
        salida = await self.llamar(
            hook, id_solicitante=ANA["id_solicitante"], monto=5_000_001, plazo_meses=12
        )
        assert salida == {}

    async def test_ignora_lo_que_afirma_el_modelo(self, hook):
        salida = await self.llamar(
            hook, id_solicitante=ANA["id_solicitante"], identidad_verificada=True
        )
        assert veredicto(salida)[0] == "deny"

    @pytest.mark.parametrize("valor", [None, 123, "", "   "])
    async def test_identificador_invalido(self, hook, valor):
        decision, motivo = veredicto(await self.llamar(hook, id_solicitante=valor))
        assert decision == "deny"
        assert motivo.startswith("[ENTRADA_INVALIDA]")

    async def test_sin_identificador(self, hook):
        decision, motivo = veredicto(await self.llamar(hook, monto=4_000_000))
        assert decision == "deny"
        assert motivo.startswith("[ENTRADA_INVALIDA]")


# ---------------------------------------------------------------- US2: hook de preaprobación


def solicitud(
    almacen, salario=2_000_000, monto=4_000_000, plazo=24, declarado=None, documentos=None
):
    """Verifica la identidad de Ana y registra una solicitud; devuelve su id_solicitud."""
    verificar(almacen)
    documentos = documentos or [doc_certificado(salario=salario)]
    declarado = salario if declarado is None else declarado
    return registrar_solicitud(almacen, ANA["id_solicitante"], monto, plazo, declarado, documentos)[
        "id_solicitud"
    ]


def cambiar_estado(almacen, id_solicitud, **campos):
    with almacen.transaccion() as datos:
        datos["solicitudes"][id_solicitud].update(campos)


@pytest.mark.anyio
class TestHookPreaprobacion:
    @pytest.fixture
    def hook(self, almacen):
        return crear_hook_preaprobacion(almacen)

    async def llamar(self, hook, **tool_input):
        return await invocar(hook, entrada("preaprobar_credito", **tool_input))

    async def negada(self, hook, codigo, **tool_input):
        decision, motivo = veredicto(await self.llamar(hook, **tool_input))
        assert decision == "deny"
        assert motivo.startswith(f"[{codigo}]"), motivo
        return motivo

    # -- bordes de la regla 2 (5.000.000 a 12 meses)

    async def test_cuota_en_30_exacto_y_monto_en_el_tope(self, almacen, hook):
        id_solicitud = solicitud(almacen, INGRESO_30_EXACTO, 5_000_000, 12)
        assert await self.llamar(hook, id_solicitud=id_solicitud) == {}

    async def test_cuota_un_peso_sobre_30(self, almacen, hook):
        id_solicitud = solicitud(almacen, INGRESO_30_EXACTO - 1, 5_000_000, 12)
        motivo = await self.negada(hook, "NO_PREAPROBABLE", id_solicitud=id_solicitud)
        assert "regla_2" in motivo

    async def test_cuota_un_peso_bajo_30(self, almacen, hook):
        id_solicitud = solicitud(almacen, INGRESO_30_EXACTO + 1, 5_000_000, 12)
        assert await self.llamar(hook, id_solicitud=id_solicitud) == {}

    async def test_monto_un_peso_sobre_el_tope(self, almacen, hook):
        id_solicitud = solicitud(almacen, 10_000_000, 5_000_001, 12)
        await self.negada(hook, "NO_PREAPROBABLE", id_solicitud=id_solicitud)

    # -- bordes de la regla 3 (verificado 2.000.000)

    @pytest.mark.parametrize("declarado", [2_200_000, 1_800_000, 2_199_999, 1_800_001])
    async def test_discrepancia_hasta_10_exacto(self, almacen, hook, declarado):
        id_solicitud = solicitud(almacen, declarado=declarado)
        assert await self.llamar(hook, id_solicitud=id_solicitud) == {}

    @pytest.mark.parametrize("declarado", [2_200_001, 1_799_999])
    async def test_discrepancia_sobre_10(self, almacen, hook, declarado):
        id_solicitud = solicitud(almacen, declarado=declarado)
        motivo = await self.negada(hook, "NO_PREAPROBABLE", id_solicitud=id_solicitud)
        assert "regla_3" in motivo

    # -- hallazgos documentales

    @pytest.mark.parametrize(
        ("documentos", "tipo"),
        [
            ([doc_certificado(), doc_extracto(2_200_001)], "inconsistencia_documental"),
            ([doc_certificado(moneda="USD")], "fuera_de_politica"),
        ],
    )
    async def test_hallazgos_documentales(self, almacen, hook, documentos, tipo):
        id_solicitud = solicitud(almacen, documentos=documentos)
        motivo = await self.negada(hook, "HALLAZGOS_DOCUMENTALES", id_solicitud=id_solicitud)
        assert tipo in motivo

    # -- no confía en lo guardado ni en lo que diga el modelo

    async def test_no_usa_la_evaluacion_guardada(self, almacen, hook):
        id_solicitud = solicitud(almacen, INGRESO_30_EXACTO - 1, 5_000_000, 12)
        cambiar_estado(
            almacen,
            id_solicitud,
            evaluacion={
                "preaprobable_automaticamente": True,
                "decision": "preaprobable",
                "cuota": 467_010,
                "causas_escalamiento": [],
            },
        )
        await self.negada(hook, "NO_PREAPROBABLE", id_solicitud=id_solicitud)

    # -- identidad, existencia y estado

    async def test_solicitante_bloqueado_despues_de_registrar(self, almacen, hook):
        id_solicitud = solicitud(almacen)
        bloquear(almacen)
        await self.negada(hook, "IDENTIDAD_NO_VERIFICADA", id_solicitud=id_solicitud)

    async def test_solicitud_inexistente(self, hook):
        await self.negada(hook, "SOLICITUD_NO_ENCONTRADA", id_solicitud="SLC-9999")

    async def test_solicitud_escalada(self, almacen, hook):
        id_solicitud = solicitud(almacen)
        cambiar_estado(almacen, id_solicitud, estado="ESCALADA")
        await self.negada(hook, "SOLICITUD_ESCALADA", id_solicitud=id_solicitud)

    async def test_ya_preaprobada_con_todo_vigente(self, almacen, hook):
        id_solicitud = solicitud(almacen)
        cambiar_estado(almacen, id_solicitud, estado="PREAPROBADA")
        assert await self.llamar(hook, id_solicitud=id_solicitud) == {}

    async def test_ya_preaprobada_y_solicitante_bloqueado_despues(self, almacen, hook):
        id_solicitud = solicitud(almacen)
        cambiar_estado(almacen, id_solicitud, estado="PREAPROBADA")
        bloquear(almacen)
        await self.negada(hook, "IDENTIDAD_NO_VERIFICADA", id_solicitud=id_solicitud)

    # -- entrada

    async def test_campo_adicional(self, almacen, hook):
        id_solicitud = solicitud(almacen)
        await self.negada(hook, "ENTRADA_INVALIDA", id_solicitud=id_solicitud, forzar=True)

    @pytest.mark.parametrize("valor", [None, 123, "", "   "])
    async def test_identificador_invalido(self, hook, valor):
        await self.negada(hook, "ENTRADA_INVALIDA", id_solicitud=valor)

    async def test_sin_identificador(self, hook):
        await self.negada(hook, "ENTRADA_INVALIDA")


# ---------------------------------------------------------------- US3: fallar cerrado


FABRICAS = [
    ("registrar_solicitud", crear_hook_registro, {"id_solicitante": ANA["id_solicitante"]}),
    ("preaprobar_credito", crear_hook_preaprobacion, {"id_solicitud": "SLC-0001"}),
]


@pytest.mark.anyio
@pytest.mark.parametrize(("herramienta", "fabrica", "tool_input"), FABRICAS)
class TestFallarCerrado:
    async def negada(self, hook, herramienta, tool_input, codigo):
        salida = await invocar(hook, entrada(herramienta, **tool_input))
        decision, motivo = veredicto(salida)
        assert decision == "deny"
        assert motivo.startswith(f"[{codigo}]"), motivo
        return motivo

    async def test_estado_ausente_niega_y_no_lo_crea(
        self, tmp_path, herramienta, fabrica, tool_input
    ):
        ruta = tmp_path / "estado.json"
        hook = fabrica(AlmacenEstado(ruta))
        await self.negada(hook, herramienta, tool_input, "ESTADO_ILEGIBLE")
        assert not ruta.exists()

    async def test_estado_corrupto_niega_y_no_lo_toca(
        self, tmp_path, herramienta, fabrica, tool_input
    ):
        ruta = tmp_path / "estado.json"
        ruta.write_text("{no json", encoding="utf-8")
        hook = fabrica(AlmacenEstado(ruta))
        await self.negada(hook, herramienta, tool_input, "ESTADO_ILEGIBLE")
        assert ruta.read_text(encoding="utf-8") == "{no json"

    async def test_lock_ocupado_niega_a_tiempo(self, almacen, herramienta, fabrica, tool_input):
        hook = fabrica(almacen, timeout_lectura=0.2)
        with FileLock(str(almacen.ruta) + ".lock"):
            await self.negada(hook, herramienta, tool_input, "ESTADO_ILEGIBLE")

    @pytest.mark.parametrize("malformado", [None, ["id"], "id"])
    async def test_tool_input_que_no_es_un_diccionario(
        self, almacen, herramienta, fabrica, tool_input, malformado
    ):
        datos_entrada = entrada(herramienta) | {"tool_input": malformado}
        decision, motivo = veredicto(await invocar(fabrica(almacen), datos_entrada))
        assert decision == "deny"
        assert motivo.startswith("[ENTRADA_INVALIDA]")

    async def test_error_inesperado_niega_sin_exponerlo(
        self, almacen, herramienta, fabrica, tool_input, monkeypatch
    ):
        def explota(*_):
            raise RuntimeError("secreto interno")

        monkeypatch.setattr(modulo_hooks, "decidir_registro", explota)
        monkeypatch.setattr(modulo_hooks, "decidir_preaprobacion", explota)
        hook = fabrica(almacen)
        motivo = await self.negada(hook, herramienta, tool_input, "ERROR_INTERNO")
        assert "secreto" not in motivo

    async def test_herramienta_ajena_no_se_toca(self, tmp_path, herramienta, fabrica, tool_input):
        ruta = tmp_path / "estado.json"  # ausente: si el hook lo leyera, negaría
        hook = fabrica(AlmacenEstado(ruta))
        for ajena in (
            entrada("buscar_solicitante", nombre="prueba"),
            {**entrada(herramienta), "tool_name": "Bash"},
            entrada(herramienta, servidor="otro", **tool_input),
        ):
            assert await invocar(hook, ajena) == {}
        assert not ruta.exists()

    async def test_el_estado_no_cambia_ni_al_permitir_ni_al_negar(
        self, almacen, herramienta, fabrica, tool_input
    ):
        verificar(almacen)
        id_solicitud = registrar_solicitud(
            almacen, ANA["id_solicitante"], 4_000_000, 24, 2_000_000, [doc_certificado()]
        )["id_solicitud"]
        hook = fabrica(almacen)
        permitida = {
            "registrar_solicitud": ANA["id_solicitante"],
            "preaprobar_credito": id_solicitud,
        }
        negada = {"registrar_solicitud": "SOL-9999", "preaprobar_credito": "SLC-9999"}
        campo = "id_solicitante" if herramienta == "registrar_solicitud" else "id_solicitud"
        antes = almacen.ruta.read_bytes()
        assert await invocar(hook, entrada(herramienta, **{campo: permitida[herramienta]})) == {}
        assert almacen.ruta.read_bytes() == antes
        await invocar(hook, entrada(herramienta, **{campo: negada[herramienta]}))
        assert almacen.ruta.read_bytes() == antes


# ------------------------------------------- US4: registro de negaciones y configuración


@pytest.mark.anyio
class TestRegistroDeNegaciones:
    @pytest.fixture
    def registro(self):
        return RegistroNegaciones()

    @pytest.fixture
    def hook(self, almacen, registro):
        return crear_hook_preaprobacion(almacen, registro=registro, ahora=AHORA)

    async def test_una_negacion_deja_una_entrada(self, almacen, registro, hook):
        id_solicitud = solicitud(almacen)
        bloquear(almacen)
        salida = await invocar(hook, entrada("preaprobar_credito", id_solicitud=id_solicitud))
        _, motivo = veredicto(salida)
        assert motivo.startswith("[IDENTIDAD_NO_VERIFICADA]")
        (negacion,) = registro.listar()
        assert negacion.herramienta == "preaprobar_credito"  # sin el prefijo del servidor
        assert negacion.codigo == "IDENTIDAD_NO_VERIFICADA"
        assert negacion.mensaje in motivo
        assert negacion.accion in motivo
        assert negacion.detalles["id_solicitud"] == id_solicitud
        assert negacion.momento == AHORA

    async def test_los_detalles_llevan_las_causas(self, almacen, registro, hook):
        id_solicitud = solicitud(almacen, INGRESO_30_EXACTO - 1, 5_000_000, 12)
        await invocar(hook, entrada("preaprobar_credito", id_solicitud=id_solicitud))
        assert [c["regla"] for c in registro.ultima().detalles["causas"]] == ["regla_2"]

    async def test_una_llamada_permitida_no_deja_nada(self, almacen, registro, hook):
        id_solicitud = solicitud(almacen)
        assert await invocar(hook, entrada("preaprobar_credito", id_solicitud=id_solicitud)) == {}
        assert registro.listar() == []

    async def test_los_dos_hooks_comparten_el_registro(self, almacen, registro, hook):
        hook_registro = crear_hook_registro(almacen, registro=registro, ahora=AHORA)
        await invocar(hook_registro, entrada("registrar_solicitud", id_solicitante="SOL-9999"))
        await invocar(hook, entrada("preaprobar_credito", id_solicitud="SLC-9999"))
        assert [n.herramienta for n in registro.listar()] == [
            "registrar_solicitud",
            "preaprobar_credito",
        ]

    async def test_al_negar_avisa_a_la_interfaz(self, almacen):
        avisos = []
        hook = crear_hook_preaprobacion(
            almacen, registro=RegistroNegaciones(al_negar=avisos.append), ahora=AHORA
        )
        await invocar(hook, entrada("preaprobar_credito", id_solicitud="SLC-9999"))
        assert [a.codigo for a in avisos] == ["SOLICITUD_NO_ENCONTRADA"]

    async def test_un_fallo_de_la_interfaz_no_abre_la_puerta(self, almacen):
        def falla(_):
            raise RuntimeError("falla de la interfaz")

        hook = crear_hook_preaprobacion(almacen, registro=RegistroNegaciones(al_negar=falla))
        salida = await invocar(hook, entrada("preaprobar_credito", id_solicitud="SLC-9999"))
        assert veredicto(salida)[0] == "deny"

    async def test_sin_registro_se_niega_igual(self, almacen):
        hook = crear_hook_preaprobacion(almacen)
        salida = await invocar(hook, entrada("preaprobar_credito", id_solicitud="SLC-9999"))
        assert veredicto(salida)[0] == "deny"

    async def test_nada_expone_la_fecha_de_nacimiento(self, almacen, registro):
        verificar(almacen)
        bloquear(almacen)
        hook = crear_hook_registro(almacen, registro=registro)
        salida = await invocar(
            hook, entrada("registrar_solicitud", id_solicitante=ANA["id_solicitante"])
        )
        publico = str(salida) + str(registro.listar())
        assert ANA["fecha_nacimiento"] not in publico


@pytest.mark.anyio
class TestConfiguracion:
    def test_dos_matchers_con_los_nombres_completos(self, almacen):
        configuracion = crear_hooks(almacen)
        assert list(configuracion) == ["PreToolUse"]
        matchers = configuracion["PreToolUse"]
        assert all(isinstance(m, HookMatcher) for m in matchers)
        assert [m.matcher for m in matchers] == [
            "mcp__crediagil-core__registrar_solicitud",
            "mcp__crediagil-core__preaprobar_credito",
        ]
        assert all(m.timeout == 10 and len(m.hooks) == 1 for m in matchers)

    def test_el_servidor_cambia_los_nombres(self, almacen):
        matchers = crear_hooks(almacen, servidor="otro")["PreToolUse"]
        assert [m.matcher for m in matchers] == [
            "mcp__otro__registrar_solicitud",
            "mcp__otro__preaprobar_credito",
        ]

    def test_las_opciones_del_agente_la_aceptan(self, almacen):
        opciones = ClaudeAgentOptions(hooks=crear_hooks(almacen))
        assert len(opciones.hooks["PreToolUse"]) == 2

    async def test_el_hook_configurado_niega_una_preaprobacion_sin_identidad(self, almacen):
        registro = RegistroNegaciones()
        _, preaprobacion = crear_hooks(almacen, registro=registro)["PreToolUse"]
        id_solicitud = solicitud(almacen)
        bloquear(almacen)
        salida = await invocar(
            preaprobacion.hooks[0], entrada("preaprobar_credito", id_solicitud=id_solicitud)
        )
        assert veredicto(salida)[0] == "deny"
        assert registro.ultima().codigo == "IDENTIDAD_NO_VERIFICADA"
