# SPDX-License-Identifier: GPL-3.0-or-later
"""Pruebas del plan de la hoja de ruta (.github/hoja-de-ruta.json)."""

import importlib.util
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
_ruta = RAIZ / "scripts" / "organizar_hoja_de_ruta.py"
_spec = importlib.util.spec_from_file_location("organizar_hoja_de_ruta", _ruta)
ohr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ohr)


def test_plan_consistente():
    assert ohr.validar_plan(ohr.cargar_plan()) == []


def test_documento_nombra_cada_hito():
    texto = (RAIZ / "docs" / "hoja-de-ruta.md").read_text("utf-8")
    for hito in ohr.cargar_plan()["hitos"]:
        assert hito["titulo"] in texto


def test_etiquetas_de_contributing_existen():
    nombres = {e["nombre"] for e in ohr.cargar_plan()["etiquetas"]}
    texto = (RAIZ / "CONTRIBUTING.md").read_text("utf-8")
    for etiqueta in ("buen-primer-aporte", "proyecto-academico", "tesis-posible"):
        assert etiqueta in nombres
        assert etiqueta in texto


def test_detecta_hito_con_etiqueta_inexistente():
    plan = {
        "etiquetas": [{"nombre": "fase-1", "color": "000000", "descripcion": ""}],
        "hitos": [{"titulo": "X", "etiqueta": "fase-9", "descripcion": ""}],
    }
    assert ohr.validar_plan(plan) == ["el hito X usa una etiqueta inexistente: fase-9"]
