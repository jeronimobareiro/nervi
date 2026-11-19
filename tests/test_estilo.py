# SPDX-License-Identifier: GPL-3.0-or-later
"""Pruebas del sistema de diseño de la interfaz (``nervi.gui.estilo``)."""

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
pytest.importorskip("pytestqt")

from PySide6.QtWidgets import QComboBox, QDoubleSpinBox, QStyledItemDelegate

from nervi.gui import estilo


def test_la_hoja_estila_las_partes_de_los_controles_compuestos():
    # Sin estas reglas Qt dibuja flechas y botones con relieve biselado (aspecto Windows 98).
    hoja = estilo.qss(estilo.CLARO)
    for regla in (
        "QComboBox::drop-down",
        "QComboBox::down-arrow",
        "QComboBox QAbstractItemView::item",
        "QAbstractSpinBox::up-button",
        "QAbstractSpinBox::down-arrow",
        "QCheckBox::indicator:checked",
        "QRadioButton::indicator:checked",
        "QSlider::handle:horizontal",
    ):
        assert regla in hoja, regla
    assert "{" in hoja and "{{" not in hoja


def test_iconos_del_tema(tmp_path: Path):
    rutas = estilo.iconos(estilo.CLARO, tmp_path)
    assert set(rutas) >= {"abajo", "arriba", "check", "punto"}
    for ruta in rutas.values():
        texto = Path(ruta).read_text(encoding="utf-8")
        assert texto.startswith("<svg") and "\\" not in ruta
    assert estilo.CLARO.texto_2 in Path(rutas["abajo"]).read_text(encoding="utf-8")
    assert estilo.CLARO.sobre_acento in Path(rutas["check"]).read_text(encoding="utf-8")


def test_aplicar_instala_hoja_y_ajusta_controles(qtbot, qapp):
    estilo.aplicar(qapp)
    estilo.aplicar(qapp)  # dos veces no cambia nada
    assert qapp.styleSheet() == estilo.qss(estilo.CLARO)
    combo = QComboBox()
    combo.addItems(["Sismo X", "Sismo Y"])
    numero = QDoubleSpinBox()
    qtbot.addWidget(combo)
    qtbot.addWidget(numero)
    combo.show()
    numero.show()
    qtbot.waitExposed(combo)
    assert isinstance(combo.itemDelegate(), QStyledItemDelegate)
    assert numero.lineEdit().textMargins().left() == estilo.MARGEN_TEXTO_NUMERICO
