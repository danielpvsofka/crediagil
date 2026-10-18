"""Cargador validado del catálogo de casos de prueba (spec 009, data-model.md).

Cada caso es una carpeta con `caso.json`, `mensaje.md`, `documentos/` y `extraccion/`. El cargador
rechaza al primer defecto con la carpeta y el campo, de modo que un caso incompleto o incoherente
no llega a ningún test ni a la interfaz. Los valores de la política no se leen ni se repiten aquí.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import StrEnum
from functools import cache
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from crediagil.chat.adjuntos import EXTENSIONES, LIMITE_BYTES_ADJUNTO
from crediagil.chat.sesion import FALLA_MAXIMA
from crediagil.extraction.schemas import validar_documento
from crediagil.mcp_server.semilla import SOLICITANTES_SEMILLA

RAIZ = Path(__file__).parent
NUMERO_MAXIMO = 8
_CARPETA = re.compile(r"^(\d{2})_(.+)$")
_PATRON_ID = r"^[a-z][a-z0-9_]*$"
_ARCHIVOS = ("caso.json", "mensaje.md")
_SUBCARPETAS = ("documentos", "extraccion")


class ErrorCatalogo(Exception):
    """Un caso no cumple el contrato; nombra la carpeta y el campo que lo incumple."""

    def __init__(self, carpeta: str, campo: str, mensaje: str) -> None:
        super().__init__(f"{carpeta}: {campo}: {mensaje}")
        self.carpeta = carpeta
        self.campo = campo
        self.mensaje = mensaje


class Resultado(StrEnum):
    PREAPROBAR = "preaprobar"
    SOLICITAR_DATO = "solicitar_dato"
    ESCALAR = "escalar"
    BLOQUEAR = "bloquear"
    REINTENTAR = "reintentar"


class Causa(StrEnum):
    REGLA_2 = "regla_2"
    REGLA_3 = "regla_3"
    MONEDA = "moneda"
    SOLICITUD_HUMANO = "solicitud_humano"


class _Modelo(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SiIntenta(_Modelo):
    herramientas: tuple[str, ...]
    codigo_negacion: str
    aviso: str
    max_intentos: Annotated[int, Field(strict=True, gt=0)]


class Herramientas(_Modelo):
    """Lo que la prueba con el modelo real comprueba sobre la traza (todo opcional)."""

    primera: str | None = None
    entrada_primera: dict[str, Any] | None = None
    debe_llamar: tuple[str, ...] = ()
    no_debe_llamar: tuple[str, ...] = ()
    en_orden: tuple[str, ...] = ()
    antes: tuple[tuple[str, str], ...] = ()
    sin_exito: tuple[str, ...] = ()
    avisos: tuple[str, ...] = ()
    sin_avisos: tuple[str, ...] = ()
    max_validaciones_exitosas: Annotated[int, Field(strict=True, ge=0)] | None = None
    sin_llamadas_repetidas: bool = False
    reintenta_tras_falla: bool = False
    si_intenta: SiIntenta | None = None


class Esperado(_Modelo):
    resultado: Resultado
    causa: Causa | None = None
    datos_faltantes: tuple[str, ...] = ()
    herramientas: Herramientas = Herramientas()

    @model_validator(mode="after")
    def _coherente(self) -> Esperado:
        if self.resultado is Resultado.ESCALAR and self.causa is None:
            raise ValueError("escalar exige una causa: regla_2, regla_3, moneda o solicitud_humano")
        if self.resultado is not Resultado.ESCALAR and self.causa is not None:
            raise ValueError("la causa solo se admite cuando el resultado es escalar")
        if self.resultado is Resultado.SOLICITAR_DATO and not self.datos_faltantes:
            raise ValueError("solicitar_dato exige datos_faltantes")
        if self.resultado is not Resultado.SOLICITAR_DATO and self.datos_faltantes:
            raise ValueError("datos_faltantes solo se admite cuando el resultado es solicitar_dato")
        return self


class Solicitud(_Modelo):
    id_solicitante: str
    monto: Annotated[int, Field(strict=True, gt=0)]
    plazo_meses: Annotated[int, Field(strict=True, gt=0)]
    ingreso_declarado: Annotated[int, Field(strict=True, ge=0)] | None
    identidad: Literal["verificada", "sin_verificar"]


class Documento(_Modelo):
    nombre: str
    texto: str
    extraccion: dict[str, Any]


class _CasoJson(_Modelo):
    id: Annotated[str, Field(pattern=_PATRON_ID)]
    numero: Annotated[int, Field(strict=True, ge=1, le=NUMERO_MAXIMO)] | None
    obligatorio: Annotated[bool, Field(strict=True)] | None = None
    nombre: Annotated[str, Field(min_length=1)]
    descripcion: Annotated[str, Field(min_length=1)]
    sin_documentos: Annotated[bool, Field(strict=True)] = False
    falla_simulada: Annotated[int, Field(strict=True, ge=0, le=FALLA_MAXIMA)] = 0
    solicitud: Solicitud | None
    esperado: Esperado


class Caso(_Modelo):
    id: str
    numero: int | None
    obligatorio: bool
    nombre: str
    descripcion: str
    mensaje: str
    sin_documentos: bool
    documentos: tuple[Documento, ...]
    falla_simulada: int
    solicitud: Solicitud | None
    esperado: Esperado
    carpeta: str


@dataclass(frozen=True)
class Catalogo:
    casos: tuple[Caso, ...]

    @property
    def obligatorios(self) -> tuple[Caso, ...]:
        return tuple(c for c in self.casos if c.obligatorio)

    def por_id(self, id_caso: str) -> Caso | None:
        return next((c for c in self.casos if c.id == id_caso), None)


def cargar_catalogo(ruta: Path | str | None = None) -> Catalogo:
    """Lee y valida todas las carpetas de caso; lanza `ErrorCatalogo` ante el primer defecto."""
    raiz = Path(ruta) if ruta is not None else RAIZ
    if not raiz.is_dir():
        raise ErrorCatalogo(str(raiz), "catalogo", "La ruta del catálogo no es una carpeta.")
    carpetas = sorted(
        entrada for entrada in raiz.iterdir() if entrada.is_dir() and entrada.name != "__pycache__"
    )
    if not carpetas:
        raise ErrorCatalogo(str(raiz), "catalogo", "El catálogo no tiene ningún caso.")
    casos = [_cargar_caso(carpeta) for carpeta in carpetas]
    _validar_conjunto(casos)
    orden = sorted(casos, key=lambda c: (c.numero is None, c.numero or 0, c.carpeta))
    return Catalogo(tuple(orden))


@cache
def catalogo() -> Catalogo:
    """El catálogo del paquete, cargado una vez por proceso."""
    return cargar_catalogo()


# ---------------------------------------------------------------- un caso


def _cargar_caso(carpeta: Path) -> Caso:
    nombre = carpeta.name
    coincidencia = _CARPETA.match(nombre)
    if coincidencia is None:
        raise ErrorCatalogo(nombre, "carpeta", "El nombre debe ser NN_id (dos dígitos y el id).")
    _revisar_estructura(carpeta)

    datos = _leer_json(carpeta, carpeta / "caso.json")
    if not isinstance(datos, dict):
        raise ErrorCatalogo(nombre, "caso.json", "Debe ser un objeto JSON.")
    try:
        crudo = _CasoJson.model_validate(datos)
    except ValidationError as exc:
        error = exc.errors(include_url=False)[0]
        campo = ".".join(str(parte) for parte in error["loc"]) or "caso.json"
        raise ErrorCatalogo(nombre, campo, error["msg"]) from None
    if crudo.id != coincidencia.group(2):
        raise ErrorCatalogo(
            nombre, "id", f"El id '{crudo.id}' debe coincidir con la carpeta ('{nombre}')."
        )
    obligatorio = crudo.numero is not None
    if crudo.obligatorio is not None and crudo.obligatorio != obligatorio:
        raise ErrorCatalogo(
            nombre, "obligatorio", "Es obligatorio si y solo si tiene numero (1 a 8)."
        )

    mensaje = _leer_texto(carpeta / "mensaje.md", nombre).strip()
    if not mensaje:
        raise ErrorCatalogo(nombre, "mensaje", "El mensaje no puede estar vacío.")

    documentos = _cargar_documentos(carpeta)
    if bool(documentos) == crudo.sin_documentos:
        raise ErrorCatalogo(
            nombre,
            "documentos",
            "Un caso sin documentos debe declarar sin_documentos; uno con documentos no.",
        )
    _validar_solicitud(nombre, crudo, mensaje)
    return Caso(
        id=crudo.id,
        numero=crudo.numero,
        obligatorio=obligatorio,
        nombre=crudo.nombre,
        descripcion=crudo.descripcion,
        mensaje=mensaje,
        sin_documentos=crudo.sin_documentos,
        documentos=documentos,
        falla_simulada=crudo.falla_simulada,
        solicitud=crudo.solicitud,
        esperado=crudo.esperado,
        carpeta=nombre,
    )


def _revisar_estructura(carpeta: Path) -> None:
    nombre = carpeta.name
    presentes = {entrada.name: entrada for entrada in carpeta.iterdir()}
    for archivo in _ARCHIVOS:
        if archivo not in presentes or not presentes[archivo].is_file():
            raise ErrorCatalogo(nombre, archivo, "Falta el archivo obligatorio.")
    for entrada, ruta in presentes.items():
        if entrada in _ARCHIVOS:
            continue
        if ruta.is_dir() and entrada in _SUBCARPETAS:
            continue
        raise ErrorCatalogo(nombre, entrada, "No está previsto en el contrato de una carpeta.")


def _leer_texto(ruta: Path, carpeta: str) -> str:
    try:
        return ruta.read_bytes().decode("utf-8")
    except UnicodeDecodeError:
        raise ErrorCatalogo(carpeta, ruta.name, "No es texto UTF-8.") from None


def _leer_json(carpeta: Path, ruta: Path) -> Any:
    try:
        return json.loads(_leer_texto(ruta, carpeta.name))
    except json.JSONDecodeError as exc:
        raise ErrorCatalogo(carpeta.name, ruta.name, f"JSON ilegible: {exc.msg}.") from None


# ---------------------------------------------------------------- documentos y extracción


def _cargar_documentos(carpeta: Path) -> tuple[Documento, ...]:
    nombre = carpeta.name
    textos = _textos_de_documentos(carpeta / "documentos", nombre)
    extracciones = _archivos_de(carpeta / "extraccion", nombre)
    por_base = {Path(archivo).stem: archivo for archivo in textos}
    if len(por_base) != len(textos):
        raise ErrorCatalogo(nombre, "documentos", "Dos documentos comparten el mismo nombre base.")
    for archivo in extracciones:
        if Path(archivo).suffix != ".json" or Path(archivo).stem not in por_base:
            raise ErrorCatalogo(nombre, archivo, "No corresponde a ningún documento.")
    documentos = []
    for archivo, texto in sorted(textos.items()):
        base = Path(archivo).stem
        ruta = carpeta / "extraccion" / f"{base}.json"
        if f"{base}.json" not in extracciones:
            raise ErrorCatalogo(nombre, archivo, "Falta su extracción esperada en extraccion/.")
        extraccion = _leer_json(carpeta, ruta)
        if not isinstance(extraccion, dict):
            raise ErrorCatalogo(nombre, ruta.name, "Debe ser un objeto JSON.")
        _validar_extraccion(nombre, ruta.name, extraccion, texto)
        documentos.append(Documento(nombre=archivo, texto=texto, extraccion=extraccion))
    return tuple(documentos)


def _archivos_de(ruta: Path, carpeta: str) -> list[str]:
    if not ruta.exists():
        return []
    nombres = []
    for entrada in sorted(ruta.iterdir()):
        if not entrada.is_file():
            raise ErrorCatalogo(carpeta, entrada.name, "Solo se admiten archivos aquí.")
        nombres.append(entrada.name)
    return nombres


def _textos_de_documentos(ruta: Path, carpeta: str) -> dict[str, str]:
    textos = {}
    for archivo in _archivos_de(ruta, carpeta):
        if not archivo.endswith(EXTENSIONES):
            raise ErrorCatalogo(
                carpeta, archivo, f"Extensión no admitida; usa {' o '.join(EXTENSIONES)}."
            )
        contenido = (ruta / archivo).read_bytes()
        if len(contenido) > LIMITE_BYTES_ADJUNTO:
            raise ErrorCatalogo(
                carpeta, archivo, f"Supera el límite de adjuntos ({LIMITE_BYTES_ADJUNTO} bytes)."
            )
        texto = _leer_texto(ruta / archivo, carpeta)
        if not texto.strip():
            raise ErrorCatalogo(carpeta, archivo, "El documento está vacío.")
        textos[archivo] = texto
    return textos


def _validar_extraccion(carpeta: str, archivo: str, extraccion: dict, texto: str) -> None:
    try:
        validar_documento(extraccion, texto)
    except ValidationError as exc:
        error = exc.errors(include_url=False)[0]
        raise ErrorCatalogo(carpeta, archivo, error["msg"]) from None


# ---------------------------------------------------------------- solicitud y conjunto


def _pesos(valor: int) -> str:
    return f"{valor:,}".replace(",", ".")


def _validar_solicitud(carpeta: str, caso: _CasoJson, mensaje: str) -> None:
    solicitud = caso.solicitud
    humano = caso.esperado.causa is Causa.SOLICITUD_HUMANO
    if solicitud is None:
        if not humano:
            raise ErrorCatalogo(
                carpeta,
                "solicitud",
                "Solo el caso de la persona (solicitud_humano) puede omitirla.",
            )
        return
    if solicitud.id_solicitante not in {s["id_solicitante"] for s in SOLICITANTES_SEMILLA}:
        raise ErrorCatalogo(
            carpeta, "solicitud.id_solicitante", "No existe en la semilla ficticia del core."
        )
    pide_dato = caso.esperado.resultado is Resultado.SOLICITAR_DATO
    if (solicitud.ingreso_declarado is None) != pide_dato:
        raise ErrorCatalogo(
            carpeta,
            "solicitud.ingreso_declarado",
            "Solo es nulo cuando el resultado es solicitar_dato (el mensaje no declara ingreso).",
        )
    if _pesos(solicitud.monto) not in mensaje:
        raise ErrorCatalogo(
            carpeta, "solicitud.monto", "El monto (con puntos de miles) no aparece en el mensaje."
        )
    if not re.search(rf"(?<![\d.]){solicitud.plazo_meses}(?![\d.])", mensaje):
        raise ErrorCatalogo(carpeta, "solicitud.plazo_meses", "El plazo no aparece en el mensaje.")
    if (
        solicitud.ingreso_declarado is not None
        and _pesos(solicitud.ingreso_declarado) not in mensaje
    ):
        raise ErrorCatalogo(
            carpeta,
            "solicitud.ingreso_declarado",
            "El ingreso declarado (con puntos de miles) no aparece en el mensaje.",
        )


def _validar_conjunto(casos: list[Caso]) -> None:
    vistos: dict[str, str] = {}
    for caso in casos:
        if caso.id in vistos:
            raise ErrorCatalogo(
                caso.carpeta, "id", f"El id '{caso.id}' ya lo usa la carpeta {vistos[caso.id]}."
            )
        vistos[caso.id] = caso.carpeta
    numeros: dict[int, str] = {}
    for caso in casos:
        if caso.numero is None:
            continue
        if caso.numero in numeros:
            raise ErrorCatalogo(
                caso.carpeta,
                "numero",
                f"El numero {caso.numero} ya lo usa la carpeta {numeros[caso.numero]}.",
            )
        numeros[caso.numero] = caso.carpeta
    esperados = list(range(1, len(numeros) + 1))
    if sorted(numeros) != esperados:
        huecos = sorted(set(esperados) ^ set(numeros))
        carpeta = numeros[max(numeros)] if numeros else ""
        raise ErrorCatalogo(
            carpeta,
            "numero",
            f"Los obligatorios deben numerarse de 1 sin huecos (revisa {huecos}).",
        )
