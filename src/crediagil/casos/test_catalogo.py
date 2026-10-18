"""Tests del cargador del catálogo de casos (spec 009, data-model.md y contracts/catalogo.md).

Los catálogos de prueba se escriben en un directorio temporal: cada test rompe una sola cosa y
comprueba que el cargador la rechaza con la carpeta y el campo.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from crediagil.casos import ErrorCatalogo, cargar_catalogo
from crediagil.chat.adjuntos import LIMITE_BYTES_ADJUNTO

TEXTO_CERTIFICADO = (
    "Empresa Ficticia S.A.S. certifica que Ana Prueba Ficticia devenga un salario mensual "
    "de $6.000.000 COP."
)
EXTRACCION_CERTIFICADO = {
    "tipo": "certificado_laboral",
    "empleador": {"valor": "Empresa Ficticia S.A.S.", "fragmento": "Empresa Ficticia S.A.S."},
    "salario_mensual": {"valor": 6000000, "fragmento": "salario mensual de $6.000.000"},
    "moneda": {"valor": "COP", "fragmento": "$6.000.000 COP"},
}
MENSAJE_SOLICITUD = "Quiero 3.000.000 a 24 meses. Mi ingreso mensual es de 6.000.000."


def _escribir_json(ruta: Path, datos) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")


def _caso_con_documento(id_caso: str, numero: int | None) -> dict:
    return {
        "id": id_caso,
        "numero": numero,
        "nombre": f"Caso {id_caso}",
        "descripcion": f"Ejercita el comportamiento de {id_caso}.",
        "solicitud": {
            "id_solicitante": "SOL-0001",
            "monto": 3000000,
            "plazo_meses": 24,
            "ingreso_declarado": 6000000,
            "identidad": "verificada",
        },
        "esperado": {"resultado": "preaprobar"},
    }


def _escribir_caso_con_documento(raiz: Path, carpeta: str, id_caso: str, numero) -> None:
    base = raiz / carpeta
    _escribir_json(base / "caso.json", _caso_con_documento(id_caso, numero))
    (base / "mensaje.md").write_text(MENSAJE_SOLICITUD, encoding="utf-8")
    (base / "documentos").mkdir(parents=True, exist_ok=True)
    (base / "documentos" / "certificado_laboral.txt").write_text(
        TEXTO_CERTIFICADO, encoding="utf-8"
    )
    _escribir_json(base / "extraccion" / "certificado_laboral.json", EXTRACCION_CERTIFICADO)


def _escribir_caso_humano(raiz: Path, carpeta: str, id_caso: str, numero) -> None:
    base = raiz / carpeta
    _escribir_json(
        base / "caso.json",
        {
            "id": id_caso,
            "numero": numero,
            "nombre": f"Caso {id_caso}",
            "descripcion": "Pide hablar con una persona.",
            "sin_documentos": True,
            "solicitud": None,
            "esperado": {"resultado": "escalar", "causa": "solicitud_humano"},
        },
    )
    (base / "mensaje.md").write_text("Quiero hablar con una persona.", encoding="utf-8")


@pytest.fixture
def raiz(tmp_path) -> Path:
    """Un catálogo mínimo y válido: dos obligatorios y un complementario."""
    _escribir_caso_con_documento(tmp_path, "01_primero", "primero", 1)
    _escribir_caso_humano(tmp_path, "02_segundo", "segundo", 2)
    _escribir_caso_con_documento(tmp_path, "03_extra", "extra", None)
    return tmp_path


def editar_caso(raiz: Path, carpeta: str, cambiar) -> None:
    ruta = raiz / carpeta / "caso.json"
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    cambiar(datos)
    _escribir_json(ruta, datos)


def rechaza(raiz: Path, carpeta: str | None = None, campo: str | None = None) -> ErrorCatalogo:
    with pytest.raises(ErrorCatalogo) as info:
        cargar_catalogo(raiz)
    error = info.value
    if carpeta is not None:
        assert error.carpeta == carpeta
    if campo is not None:
        # El campo es la ruta completa ("esperado.causa"); basta con que `campo` sea su prefijo.
        assert error.campo == campo or error.campo.startswith(f"{campo}."), error.campo
    assert error.mensaje.strip()
    return error


# ---------------------------------------------------------------- catálogo válido


class TestCatalogoValido:
    def test_carga_y_ordena_por_numero_con_los_complementarios_al_final(self, raiz):
        catalogo = cargar_catalogo(raiz)
        assert [c.id for c in catalogo.casos] == ["primero", "segundo", "extra"]
        assert [c.numero for c in catalogo.casos] == [1, 2, None]

    def test_obligatorios_y_por_id(self, raiz):
        catalogo = cargar_catalogo(raiz)
        assert [c.id for c in catalogo.obligatorios] == ["primero", "segundo"]
        assert catalogo.por_id("extra").obligatorio is False
        assert catalogo.por_id("primero").obligatorio is True
        assert catalogo.por_id("no_existe") is None

    def test_lee_mensaje_documentos_y_extraccion(self, raiz):
        caso = cargar_catalogo(raiz).por_id("primero")
        assert caso.mensaje == MENSAJE_SOLICITUD
        (documento,) = caso.documentos
        assert documento.nombre == "certificado_laboral.txt"
        assert documento.texto == TEXTO_CERTIFICADO
        assert documento.extraccion == EXTRACCION_CERTIFICADO
        assert caso.solicitud.monto == 3000000
        assert caso.esperado.resultado == "preaprobar"

    def test_el_caso_sin_documentos_lo_declara(self, raiz):
        caso = cargar_catalogo(raiz).por_id("segundo")
        assert caso.sin_documentos is True
        assert caso.documentos == ()
        assert caso.solicitud is None
        assert caso.esperado.causa == "solicitud_humano"

    def test_los_modelos_son_de_solo_lectura(self, raiz):
        caso = cargar_catalogo(raiz).por_id("primero")
        with pytest.raises(Exception):  # noqa: B017 — pydantic: ValidationError de modelo congelado
            caso.nombre = "otro"
        with pytest.raises(Exception):  # noqa: B017
            caso.esperado.resultado = "escalar"

    def test_valores_por_defecto(self, raiz):
        caso = cargar_catalogo(raiz).por_id("primero")
        assert caso.falla_simulada == 0
        assert caso.sin_documentos is False
        assert caso.esperado.herramientas.debe_llamar == ()


# ---------------------------------------------------------------- 1. estructura de la carpeta


class TestEstructura:
    @pytest.mark.parametrize("archivo", ["caso.json", "mensaje.md"])
    def test_falta_un_archivo_obligatorio(self, raiz, archivo):
        (raiz / "01_primero" / archivo).unlink()
        rechaza(raiz, "01_primero", archivo)

    def test_sobra_un_archivo(self, raiz):
        (raiz / "01_primero" / "notas.txt").write_text("resto", encoding="utf-8")
        rechaza(raiz, "01_primero", "notas.txt")

    def test_sobra_una_subcarpeta(self, raiz):
        (raiz / "01_primero" / "otra").mkdir()
        rechaza(raiz, "01_primero", "otra")

    def test_sobra_una_carpeta_que_no_es_de_caso(self, raiz):
        (raiz / "varios").mkdir()
        rechaza(raiz, "varios")

    def test_json_ilegible(self, raiz):
        (raiz / "01_primero" / "caso.json").write_text("{no json", encoding="utf-8")
        rechaza(raiz, "01_primero", "caso.json")

    def test_mensaje_vacio(self, raiz):
        (raiz / "01_primero" / "mensaje.md").write_text("  \n", encoding="utf-8")
        rechaza(raiz, "01_primero", "mensaje")

    def test_campo_desconocido_en_el_caso(self, raiz):
        editar_caso(raiz, "01_primero", lambda d: d.update(extra="x"))
        rechaza(raiz, "01_primero")

    def test_una_carpeta_sin_prefijo_numerico_se_rechaza(self, raiz):
        (raiz / "01_primero").rename(raiz / "primero")
        rechaza(raiz, "primero")

    def test_una_ruta_inexistente(self, tmp_path):
        with pytest.raises(ErrorCatalogo):
            cargar_catalogo(tmp_path / "no_existe")

    def test_un_catalogo_vacio_se_rechaza(self, tmp_path):
        with pytest.raises(ErrorCatalogo):
            cargar_catalogo(tmp_path)


# ---------------------------------------------------------------- 2. identificador


class TestIdentificador:
    def test_id_repetido(self, raiz):
        editar_caso(raiz, "03_extra", lambda d: d.update(id="primero"))
        (raiz / "03_extra").rename(raiz / "03_primero")
        rechaza(raiz, campo="id")

    @pytest.mark.parametrize("id_malo", ["Primero", "1primero", "con-guion", "con espacio", ""])
    def test_formato_invalido(self, raiz, id_malo):
        editar_caso(raiz, "01_primero", lambda d: d.update(id=id_malo))
        rechaza(raiz, "01_primero", "id")

    def test_distinto_del_nombre_de_la_carpeta(self, raiz):
        editar_caso(raiz, "01_primero", lambda d: d.update(id="otro_id"))
        rechaza(raiz, "01_primero", "id")


# ---------------------------------------------------------------- 3 y 4. número y obligatorio


class TestNumero:
    def test_numero_repetido(self, raiz):
        editar_caso(raiz, "02_segundo", lambda d: d.update(numero=1))
        rechaza(raiz, campo="numero")

    @pytest.mark.parametrize("numero", [0, 9, -1])
    def test_fuera_de_rango(self, raiz, numero):
        editar_caso(raiz, "02_segundo", lambda d: d.update(numero=numero))
        rechaza(raiz, "02_segundo", "numero")

    def test_hueco_entre_los_obligatorios(self, raiz):
        editar_caso(raiz, "02_segundo", lambda d: d.update(numero=3))
        rechaza(raiz, campo="numero")

    @pytest.mark.parametrize("numero", ["1", 1.5, True])
    def test_tipo_invalido(self, raiz, numero):
        editar_caso(raiz, "01_primero", lambda d: d.update(numero=numero))
        rechaza(raiz, "01_primero", "numero")

    def test_obligatorio_incoherente_con_el_numero(self, raiz):
        editar_caso(raiz, "03_extra", lambda d: d.update(obligatorio=True))
        rechaza(raiz, "03_extra", "obligatorio")
        editar_caso(raiz, "03_extra", lambda d: d.update(obligatorio=False))
        editar_caso(raiz, "01_primero", lambda d: d.update(obligatorio=False))
        rechaza(raiz, "01_primero", "obligatorio")

    def test_obligatorio_coherente_se_acepta(self, raiz):
        editar_caso(raiz, "01_primero", lambda d: d.update(obligatorio=True))
        editar_caso(raiz, "03_extra", lambda d: d.update(obligatorio=False))
        assert len(cargar_catalogo(raiz).casos) == 3


# ---------------------------------------------------------------- 5. resultado esperado


class TestEsperado:
    def test_resultado_fuera_del_vocabulario(self, raiz):
        editar_caso(raiz, "01_primero", lambda d: d["esperado"].update(resultado="aprobar"))
        rechaza(raiz, "01_primero", "esperado")

    def test_escalar_sin_causa(self, raiz):
        editar_caso(raiz, "01_primero", lambda d: d["esperado"].update(resultado="escalar"))
        rechaza(raiz, "01_primero", "esperado")

    @pytest.mark.parametrize("causa", ["regla_1", "otra", ""])
    def test_causa_fuera_del_vocabulario(self, raiz, causa):
        editar_caso(
            raiz,
            "01_primero",
            lambda d: d["esperado"].update(resultado="escalar", causa=causa),
        )
        rechaza(raiz, "01_primero", "esperado")

    @pytest.mark.parametrize("causa", ["regla_2", "regla_3", "moneda", "solicitud_humano"])
    def test_las_cuatro_causas_se_aceptan(self, raiz, causa):
        editar_caso(
            raiz,
            "03_extra",
            lambda d: d["esperado"].update(resultado="escalar", causa=causa),
        )
        assert cargar_catalogo(raiz).por_id("extra").esperado.causa == causa

    def test_causa_sobrante(self, raiz):
        editar_caso(raiz, "01_primero", lambda d: d["esperado"].update(causa="regla_2"))
        rechaza(raiz, "01_primero", "esperado")

    def test_solicitar_dato_sin_datos_faltantes(self, raiz):
        editar_caso(raiz, "03_extra", lambda d: d["esperado"].update(resultado="solicitar_dato"))
        rechaza(raiz, "03_extra", "esperado")

    def test_datos_faltantes_sobrantes(self, raiz):
        editar_caso(raiz, "01_primero", lambda d: d["esperado"].update(datos_faltantes=["x"]))
        rechaza(raiz, "01_primero", "esperado")

    def test_solicitar_dato_completo_se_acepta(self, raiz):
        def cambiar(datos):
            datos["esperado"].update(
                resultado="solicitar_dato", datos_faltantes=["salario_mensual"]
            )
            datos["solicitud"]["ingreso_declarado"] = None

        editar_caso(raiz, "03_extra", cambiar)
        (raiz / "03_extra" / "mensaje.md").write_text("Quiero 3.000.000 a 24 meses.", "utf-8")
        assert cargar_catalogo(raiz).por_id("extra").esperado.datos_faltantes == (
            "salario_mensual",
        )

    def test_las_herramientas_se_leen(self, raiz):
        editar_caso(
            raiz,
            "01_primero",
            lambda d: d["esperado"].update(
                herramientas={
                    "primera": "buscar_solicitante",
                    "debe_llamar": ["a", "b"],
                    "avisos": ["credito_preaprobado"],
                    "max_validaciones_exitosas": 1,
                    "si_intenta": {
                        "herramientas": ["registrar_solicitud"],
                        "codigo_negacion": "IDENTIDAD_NO_VERIFICADA",
                        "aviso": "bloqueo_regla",
                        "max_intentos": 3,
                    },
                }
            ),
        )
        herramientas = cargar_catalogo(raiz).por_id("primero").esperado.herramientas
        assert herramientas.primera == "buscar_solicitante"
        assert herramientas.debe_llamar == ("a", "b")
        assert herramientas.si_intenta.max_intentos == 3

    def test_clave_desconocida_en_herramientas(self, raiz):
        editar_caso(
            raiz, "01_primero", lambda d: d["esperado"].update(herramientas={"inventada": 1})
        )
        rechaza(raiz, "01_primero", "esperado")

    def test_solicitud_nula_solo_en_el_caso_de_la_persona(self, raiz):
        editar_caso(raiz, "01_primero", lambda d: d.update(solicitud=None))
        rechaza(raiz, "01_primero", "solicitud")


# ---------------------------------------------------------------- 6. documentos


class TestDocumentos:
    def _documentos(self, raiz) -> Path:
        return raiz / "01_primero" / "documentos"

    @pytest.mark.parametrize("nombre", ["certificado.pdf", "certificado.TXT", "certificado"])
    def test_extension_no_admitida(self, raiz, nombre):
        (self._documentos(raiz) / "certificado_laboral.txt").rename(self._documentos(raiz) / nombre)
        (raiz / "01_primero" / "extraccion" / "certificado_laboral.json").rename(
            raiz / "01_primero" / "extraccion" / f"{Path(nombre).stem}.json"
        )
        rechaza(raiz, "01_primero", nombre)

    def test_extension_md_se_acepta(self, raiz):
        (self._documentos(raiz) / "certificado_laboral.txt").rename(
            self._documentos(raiz) / "certificado_laboral.md"
        )
        assert cargar_catalogo(raiz).por_id("primero").documentos[0].nombre.endswith(".md")

    def test_documento_vacio(self, raiz):
        (self._documentos(raiz) / "certificado_laboral.txt").write_text(" \n", encoding="utf-8")
        rechaza(raiz, "01_primero", "certificado_laboral.txt")

    def test_documento_que_no_es_utf8(self, raiz):
        (self._documentos(raiz) / "certificado_laboral.txt").write_bytes(b"\xff\xfe\x00\xd8")
        rechaza(raiz, "01_primero", "certificado_laboral.txt")

    def test_documento_que_supera_el_limite_de_adjuntos(self, raiz):
        texto = TEXTO_CERTIFICADO + " " + "a" * LIMITE_BYTES_ADJUNTO
        (self._documentos(raiz) / "certificado_laboral.txt").write_text(texto, encoding="utf-8")
        rechaza(raiz, "01_primero", "certificado_laboral.txt")

    def test_el_limite_exacto_se_acepta(self, raiz):
        relleno = LIMITE_BYTES_ADJUNTO - len(TEXTO_CERTIFICADO.encode("utf-8")) - 1
        texto = TEXTO_CERTIFICADO + " " + "a" * relleno
        assert len(texto.encode("utf-8")) == LIMITE_BYTES_ADJUNTO
        (self._documentos(raiz) / "certificado_laboral.txt").write_text(texto, encoding="utf-8")
        cargar_catalogo(raiz)

    def test_caso_sin_documentos_que_no_lo_declara(self, raiz):
        editar_caso(raiz, "02_segundo", lambda d: d.update(sin_documentos=False))
        rechaza(raiz, "02_segundo", "documentos")

    def test_caso_que_declara_sin_documentos_y_los_tiene(self, raiz):
        editar_caso(raiz, "01_primero", lambda d: d.update(sin_documentos=True))
        rechaza(raiz, "01_primero", "documentos")

    def test_documento_sin_extraccion(self, raiz):
        (raiz / "01_primero" / "extraccion" / "certificado_laboral.json").unlink()
        rechaza(raiz, "01_primero", "certificado_laboral.txt")

    def test_extraccion_sin_documento(self, raiz):
        _escribir_json(raiz / "01_primero" / "extraccion" / "huerfano.json", EXTRACCION_CERTIFICADO)
        rechaza(raiz, "01_primero", "huerfano.json")


# ---------------------------------------------------------------- 7. extracción


class TestExtraccion:
    def _escribir(self, raiz, datos) -> None:
        _escribir_json(raiz / "01_primero" / "extraccion" / "certificado_laboral.json", datos)

    def test_extraccion_que_no_pasa_el_esquema(self, raiz):
        self._escribir(raiz, {**EXTRACCION_CERTIFICADO, "tipo": "inventado"})
        rechaza(raiz, "01_primero", "certificado_laboral.json")

    def test_campo_con_un_tipo_invalido(self, raiz):
        malo = {**EXTRACCION_CERTIFICADO, "salario_mensual": {"valor": "mucho", "fragmento": "x"}}
        self._escribir(raiz, malo)
        rechaza(raiz, "01_primero", "certificado_laboral.json")

    def test_fragmento_que_no_esta_literal_en_el_documento(self, raiz):
        malo = {
            **EXTRACCION_CERTIFICADO,
            "salario_mensual": {"valor": 6000000, "fragmento": "salario de 6 millones"},
        }
        self._escribir(raiz, malo)
        error = rechaza(raiz, "01_primero", "certificado_laboral.json")
        assert "literal" in error.mensaje.lower()

    def test_json_de_extraccion_ilegible(self, raiz):
        ruta = raiz / "01_primero" / "extraccion" / "certificado_laboral.json"
        ruta.write_text("[1, 2", encoding="utf-8")
        rechaza(raiz, "01_primero", "certificado_laboral.json")

    def test_un_campo_ausente_queda_fuera(self, raiz):
        sin_salario = {
            "tipo": "certificado_laboral",
            "empleador": EXTRACCION_CERTIFICADO["empleador"],
        }
        self._escribir(raiz, sin_salario)
        cargar_catalogo(raiz)


# ---------------------------------------------------------------- 8, 9 y 10. solicitud


class TestSolicitud:
    def test_solicitante_que_no_esta_en_la_semilla(self, raiz):
        editar_caso(raiz, "01_primero", lambda d: d["solicitud"].update(id_solicitante="SOL-9999"))
        rechaza(raiz, "01_primero", "solicitud.id_solicitante")

    @pytest.mark.parametrize("valor", [-1, 21, True, 1.5, "1"])
    def test_falla_simulada_invalida(self, raiz, valor):
        editar_caso(raiz, "01_primero", lambda d: d.update(falla_simulada=valor))
        rechaza(raiz, "01_primero", "falla_simulada")

    @pytest.mark.parametrize("valor", [0, 1, 20])
    def test_falla_simulada_en_el_rango(self, raiz, valor):
        editar_caso(raiz, "01_primero", lambda d: d.update(falla_simulada=valor))
        assert cargar_catalogo(raiz).por_id("primero").falla_simulada == valor

    @pytest.mark.parametrize(
        "campo,valor", [("monto", 4000000), ("plazo_meses", 36), ("ingreso_declarado", 7000000)]
    )
    def test_un_numero_que_no_aparece_en_el_mensaje(self, raiz, campo, valor):
        editar_caso(raiz, "01_primero", lambda d: d["solicitud"].update({campo: valor}))
        rechaza(raiz, "01_primero", f"solicitud.{campo}")

    def test_el_monto_se_busca_con_puntos_de_miles(self, raiz):
        (raiz / "01_primero" / "mensaje.md").write_text(
            "Quiero 3000000 a 24 meses. Mi ingreso es de 6.000.000.", encoding="utf-8"
        )
        rechaza(raiz, "01_primero", "solicitud.monto")

    def test_ingreso_nulo_solo_si_se_solicita_el_dato(self, raiz):
        editar_caso(raiz, "01_primero", lambda d: d["solicitud"].update(ingreso_declarado=None))
        rechaza(raiz, "01_primero", "solicitud.ingreso_declarado")

    @pytest.mark.parametrize("campo,valor", [("monto", 0), ("plazo_meses", -1)])
    def test_numeros_no_positivos(self, raiz, campo, valor):
        editar_caso(raiz, "01_primero", lambda d: d["solicitud"].update({campo: valor}))
        rechaza(raiz, "01_primero", f"solicitud.{campo}")

    def test_identidad_fuera_del_vocabulario(self, raiz):
        editar_caso(raiz, "01_primero", lambda d: d["solicitud"].update(identidad="quizas"))
        rechaza(raiz, "01_primero", "solicitud")


# ---------------------------------------------------------------- el error es legible


class TestErrorCatalogo:
    def test_el_texto_nombra_la_carpeta_y_el_campo(self, raiz):
        editar_caso(raiz, "01_primero", lambda d: d.update(id="otro_id"))
        error = rechaza(raiz)
        assert "01_primero" in str(error)
        assert "id" in str(error)
        assert (error.carpeta, error.campo) == ("01_primero", "id")


# ---------------------------------------------------------------- el catálogo del paquete

IDS_OBLIGATORIOS = [
    "dentro_de_politica",
    "dato_ausente",
    "ingreso_discrepante",
    "monto_sobre_umbral",
    "preaprobar_sin_identidad",
    "moneda_extranjera",
    "falla_transitoria",
    "pedir_persona",
]


def _formatos_pesos(monto: int) -> list[str]:
    return [f"{monto:,}".replace(",", "."), f"{monto:,}", str(monto)]


def _formatos_porcentaje(proporcion) -> list[str]:
    numero = f"{(proporcion * 100).normalize():f}"
    variantes = {numero, numero.replace(".", ",")}
    return [f"{v}{sep}%" for v in variantes for sep in ("", " ")]


class TestCatalogoDelPaquete:
    def test_carga_sin_error(self):
        from crediagil.casos import catalogo

        assert catalogo().casos

    def test_estan_los_ocho_obligatorios_en_el_orden_del_enunciado(self):
        from crediagil.casos import catalogo

        obligatorios = catalogo().obligatorios
        assert [c.id for c in obligatorios] == IDS_OBLIGATORIOS
        assert [c.numero for c in obligatorios] == list(range(1, 9))

    def test_el_mensaje_mixto_es_complementario(self):
        from crediagil.casos import catalogo

        caso = catalogo().por_id("mensaje_mixto")
        assert caso is not None
        assert caso.numero is None and caso.obligatorio is False
        assert catalogo().casos[-1].id == "mensaje_mixto"

    def test_cada_caso_tiene_nombre_descripcion_y_mensaje(self):
        from crediagil.casos import catalogo

        for caso in catalogo().casos:
            assert caso.nombre.strip() and caso.descripcion.strip() and caso.mensaje.strip()

    def test_solo_dos_casos_declaran_no_llevar_documentos(self):
        from crediagil.casos import catalogo

        sin = {c.id for c in catalogo().casos if c.sin_documentos}
        assert sin == {"pedir_persona", "preaprobar_sin_identidad"}
        for caso in catalogo().casos:
            assert bool(caso.documentos) is (not caso.sin_documentos), caso.id

    def test_solo_la_falla_transitoria_pide_falla_simulada(self):
        from crediagil.casos import catalogo

        for caso in catalogo().casos:
            esperada = 1 if caso.id == "falla_transitoria" else 0
            assert caso.falla_simulada == esperada, caso.id

    def test_el_resultado_esperado_de_cada_obligatorio(self):
        from crediagil.casos import Causa, Resultado, catalogo

        esperado = {
            "dentro_de_politica": (Resultado.PREAPROBAR, None),
            "dato_ausente": (Resultado.SOLICITAR_DATO, None),
            "ingreso_discrepante": (Resultado.ESCALAR, Causa.REGLA_3),
            "monto_sobre_umbral": (Resultado.ESCALAR, Causa.REGLA_2),
            "preaprobar_sin_identidad": (Resultado.BLOQUEAR, None),
            "moneda_extranjera": (Resultado.ESCALAR, Causa.MONEDA),
            "falla_transitoria": (Resultado.REINTENTAR, None),
            "pedir_persona": (Resultado.ESCALAR, Causa.SOLICITUD_HUMANO),
        }
        for caso in catalogo().obligatorios:
            assert (caso.esperado.resultado, caso.esperado.causa) == esperado[caso.id], caso.id

    def test_ningun_texto_repite_la_tasa_ni_los_umbrales(self):
        from crediagil.casos.catalogo import RAIZ
        from crediagil.policy import params

        prohibidos = [
            *_formatos_pesos(params.MONTO_MAXIMO_PREAPROBACION),
            *_formatos_porcentaje(params.TASA_MENSUAL),
            *_formatos_porcentaje(params.PROPORCION_MAXIMA_CUOTA_INGRESO),
            *_formatos_porcentaje(params.DISCREPANCIA_MAXIMA_INGRESO),
        ]
        archivos = [
            ruta
            for carpeta in RAIZ.iterdir()
            if carpeta.is_dir() and carpeta.name[:2].isdigit()
            for ruta in carpeta.rglob("*")
            if ruta.is_file()
        ]
        assert archivos
        for ruta in archivos:
            texto = ruta.read_text(encoding="utf-8")
            for valor in prohibidos:
                assert valor not in texto, f"{ruta.name} contiene {valor!r}"
