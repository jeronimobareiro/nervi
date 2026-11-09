# SPDX-License-Identifier: GPL-3.0-or-later
import importlib.util
from pathlib import Path

_RUTA = Path(__file__).resolve().parents[1] / "scripts" / "verificar_dco.py"
_spec = importlib.util.spec_from_file_location("verificar_dco", _RUTA)
dco = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dco)


def test_firma_valida():
    assert dco.firmado("Arreglar signo\n\nSigned-off-by: Ana Pérez <ana@ejemplo.org>\n")


def test_sin_firma():
    assert not dco.firmado("Arreglar signo\n\nCo-Authored-By: Alguien <a@b.c>\n")


def test_firma_sin_correo():
    assert not dco.firmado("Arreglar signo\n\nSigned-off-by: Ana Pérez\n")
