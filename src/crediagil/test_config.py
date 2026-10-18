"""Tests de la configuración y la clave de la API (spec 007, FR-015)."""

from __future__ import annotations

import os

import pytest

from crediagil.config import ConfiguracionError, cargar_entorno, obtener_api_key, redactar

CLAVE = "sk-ficticia-abc123"
ARCHIVO_LOCAL = ".env"


def test_obtener_api_key_devuelve_la_variable(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", CLAVE)
    assert obtener_api_key() == CLAVE


@pytest.mark.parametrize("valor", [None, "", "   "])
def test_falta_la_clave_lanza_error_sin_valores(monkeypatch, valor):
    if valor is None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    else:
        monkeypatch.setenv("ANTHROPIC_API_KEY", valor)
    with pytest.raises(ConfiguracionError) as error:
        obtener_api_key()
    assert "ANTHROPIC_API_KEY" in str(error.value)
    assert CLAVE not in str(error.value)


def test_redactar_sustituye_todas_las_apariciones(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", CLAVE)
    texto = f"error con {CLAVE} y otra vez {CLAVE}"
    assert redactar(texto) == "error con [REDACTADO] y otra vez [REDACTADO]"


def test_redactar_sin_clave_deja_el_texto(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert redactar("texto normal") == "texto normal"
    assert redactar("") == ""


def test_cargar_entorno_lee_el_archivo_local_sin_pisar(monkeypatch, tmp_path):
    (tmp_path / ARCHIVO_LOCAL).write_text("ANTHROPIC_API_KEY=sk-ficticia-archivo\nOTRA=1\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("OTRA", "definida")
    cargar_entorno()
    assert obtener_api_key() == "sk-ficticia-archivo"
    assert os.environ["OTRA"] == "definida"
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


def test_cargar_entorno_no_pisa_la_clave_definida(monkeypatch, tmp_path):
    (tmp_path / ARCHIVO_LOCAL).write_text("ANTHROPIC_API_KEY=sk-ficticia-archivo\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ANTHROPIC_API_KEY", CLAVE)
    cargar_entorno()
    assert obtener_api_key() == CLAVE


def test_cargar_entorno_sin_archivo_no_falla(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    cargar_entorno()
