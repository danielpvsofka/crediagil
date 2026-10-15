"""Tests de block_sensitive_data: contracts/hooks.md §block_sensitive_data (casos 1–13).

Ningún número con forma real aparece como literal: todo se construye en tiempo de ejecución.
"""

from __future__ import annotations

import hashlib
import json

import pytest
from conftest import luhn_valid_number

HOOK = "block_sensitive_data.py"


def write_event(content: str) -> dict:
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": "Write",
        "tool_input": {"file_path": "tests/fixture.py", "content": content},
    }


def altered_check_digit(number: str) -> str:
    return number[:-1] + str((int(number[-1]) + 1) % 10)


def grouped(number: str, sep: str) -> str:
    return sep.join(number[i : i + 4] for i in range(0, len(number), 4))


def test_caso1_tarjeta_luhn_valida_bloquea(run_hook, tmp_path):
    card = luhn_valid_number("4", 16)
    code, _, stderr = run_hook(HOOK, write_event(f"numero = '{card}'\n"), tmp_path)
    assert code == 2
    assert "tarjeta" in stderr


def test_caso2_digito_de_control_alterado_permite(run_hook, tmp_path):
    card = altered_check_digit(luhn_valid_number("4", 16))
    code, _, _ = run_hook(HOOK, write_event(f"numero = '{card}'\n"), tmp_path)
    assert code == 0


@pytest.mark.parametrize("sep", [" ", "-"])
def test_caso3_tarjeta_con_separadores_bloquea(run_hook, tmp_path, sep):
    card = grouped(luhn_valid_number("5", 16), sep)
    code, _, stderr = run_hook(HOOK, write_event(f"pan: {card}\n"), tmp_path)
    assert code == 2
    assert "tarjeta" in stderr


@pytest.mark.parametrize("length", [12, 20])
def test_caso4_longitudes_fuera_de_rango_permiten(run_hook, tmp_path, length):
    number = luhn_valid_number("4", length)
    code, _, _ = run_hook(HOOK, write_event(f"valor = {number}\n"), tmp_path)
    assert code == 0


@pytest.mark.parametrize("length", [13, 19])
def test_caso5_longitudes_limite_bloquean(run_hook, tmp_path, length):
    number = luhn_valid_number("4", length)
    code, _, _ = run_hook(HOOK, write_event(f"valor = {number}\n"), tmp_path)
    assert code == 2


def test_caso6_timestamp_ms_no_bloquea(run_hook, tmp_path):
    timestamp = luhn_valid_number("17", 13)
    code, _, _ = run_hook(HOOK, write_event(f"created_at = {timestamp}\n"), tmp_path)
    assert code == 0


def test_caso7_cedula_etiquetada_bloquea(run_hook, tmp_path):
    content = "cliente = {'cédula: " + "1" * 10 + "'}\n"
    code, _, stderr = run_hook(HOOK, write_event(content), tmp_path)
    assert code == 2
    assert "documento" in stderr


def test_caso7b_nit_con_puntos_y_dv_bloquea(run_hook, tmp_path):
    nit = ".".join(["9" * 3, "1" * 3, "4" * 3]) + "-7"
    code, _, stderr = run_hook(HOOK, write_event(f"NIT {nit}\n"), tmp_path)
    assert code == 2
    assert "documento" in stderr


def test_caso8_cuenta_etiquetada_bloquea(run_hook, tmp_path):
    content = "cuenta de ahorros " + "2" * 11 + "\n"
    code, _, stderr = run_hook(HOOK, write_event(content), tmp_path)
    assert code == 2
    assert "cuenta" in stderr


def test_caso9_pragma_dato_ficticio_permite(run_hook, tmp_path):
    content = "cedula = 'cédula: " + "1" * 10 + "'  # pragma: dato-ficticio\n"
    code, _, _ = run_hook(HOOK, write_event(content), tmp_path)
    assert code == 0


@pytest.mark.parametrize(
    "content",
    [
        "monto = " + "5" + "0" * 6 + "\n",
        "monto: 5.000.000 COP\n",
        "montos = [" + "5" + "0" * 6 + ", " + "3" + "0" * 6 + "]\n",
        "solicitud_id = '123e4567-e89b-12d3-a456-426614174000'\n",
        f"sha = '{hashlib.sha256(b'crediagil').hexdigest()}'\n",
        # Hash hex con una racha de dígitos válida por Luhn (falso positivo real del manifest).
        "sha = '7e" + luhn_valid_number("6", 15) + "fdca'\n",
    ],
)
def test_caso10_numeros_legitimos_permiten(run_hook, tmp_path, content):
    code, _, stderr = run_hook(HOOK, write_event(content), tmp_path)
    assert code == 0, stderr


def test_caso11_multiedit_hallazgo_en_segundo_edit_bloquea(run_hook, tmp_path):
    card = luhn_valid_number("4", 16)
    event = {
        "hook_event_name": "PreToolUse",
        "tool_name": "MultiEdit",
        "tool_input": {
            "file_path": "tests/fixture.py",
            "edits": [
                {"old_string": "a", "new_string": "x = 1"},
                {"old_string": "b", "new_string": f"y = '{card}'"},
            ],
        },
    }
    code, _, _ = run_hook(HOOK, event, tmp_path)
    assert code == 2


@pytest.mark.parametrize("tool", ["Edit", "NotebookEdit"])
def test_caso11b_otras_herramientas_bloquean(run_hook, tmp_path, tool):
    card = luhn_valid_number("4", 16)
    key = "new_string" if tool == "Edit" else "new_source"
    event = {"tool_name": tool, "tool_input": {"file_path": "a.py", key: card}}
    code, _, _ = run_hook(HOOK, event, tmp_path)
    assert code == 2


def test_caso12_stderr_no_contiene_el_numero_completo(run_hook, tmp_path):
    card = luhn_valid_number("4", 16)
    content = f"x = 1\nnumero = '{card}'\n"
    code, _, stderr = run_hook(HOOK, write_event(content), tmp_path)
    assert code == 2
    assert card not in stderr
    assert card[-4:] in stderr
    assert "línea 2" in stderr


@pytest.mark.parametrize("payload", ["no es json", json.dumps({"tool_input": {}})])
def test_caso13_entrada_malformada_bloquea(run_hook, tmp_path, payload):
    code, _, stderr = run_hook(HOOK, payload, tmp_path)
    assert code == 2
    assert "[block_sensitive_data]" in stderr
