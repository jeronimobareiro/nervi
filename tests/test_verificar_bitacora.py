"""Pruebas del control de bitácora (scripts/verificar_bitacora.py)."""

import importlib.util
from pathlib import Path

_ruta = Path(__file__).resolve().parents[1] / "scripts" / "verificar_bitacora.py"
_spec = importlib.util.spec_from_file_location("verificar_bitacora", _ruta)
vb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vb)

ENTRADA = "docs/bitacora/2026-11-10-01-cargas-trapezoidales.md"
COMPLETA = "\n".join(vb.SECCIONES)


def leer(_ruta: str) -> str:
    return COMPLETA


def test_aporte_completo_pasa():
    lista = [("M", "crates/nervi-core/src/analisis.rs"), ("A", ENTRADA), ("M", vb.ESTADO)]
    assert vb.verificar(lista, leer) == []


def test_codigo_sin_bitacora_falla():
    errores = vb.verificar([("M", "python/nervi/modelo.py")], leer)
    assert any("no agrega una entrada" in e for e in errores)
    assert any("ESTADO.md" in e for e in errores)


def test_solo_documentacion_de_seguimiento_no_exige_entrada():
    assert vb.verificar([("M", vb.ESTADO), ("M", "docs/bitacora/README.md")], leer) == []


def test_editar_entrada_existente_falla():
    lista = [("M", "docs/bitacora/2026-11-09-02-motor-portico-2d.md")]
    assert any("no se editan" in e for e in vb.verificar(lista, leer))


def test_nombre_invalido_falla():
    lista = [("M", "README.md"), ("A", "docs/bitacora/mi aporte.md"), ("M", vb.ESTADO)]
    errores = vb.verificar(lista, leer)
    assert any("el nombre debe ser" in e for e in errores)


def test_entrada_sin_secciones_falla():
    lista = [("M", "README.md"), ("A", ENTRADA), ("M", vb.ESTADO)]
    errores = vb.verificar(lista, lambda _r: "# título")
    assert any("faltan las secciones" in e for e in errores)
