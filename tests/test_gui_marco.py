# SPDX-License-Identifier: GPL-3.0-or-later
"""Barra de título propia de la ventana (``nervi.gui.marco``)."""

import ctypes
import os
from ctypes import wintypes

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
pytest.importorskip("pytestqt")

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QLabel, QPushButton

from nervi.gui import ajustes, marco
from nervi.gui.sesion import Sesion, documento_ejemplo
from nervi.gui.ventana import Ventana


@pytest.fixture(autouse=True)
def preferencias_aparte(tmp_path, monkeypatch):
    monkeypatch.setattr(ajustes, "ARCHIVO", str(tmp_path / "preferencias.ini"))


def _ventana(qtbot) -> Ventana:
    v = Ventana(Sesion(documento_ejemplo()))
    qtbot.addWidget(v)
    v.resize(1400, 900)
    v.show()
    qtbot.waitExposed(v)
    return v


def _cerrar(v: Ventana) -> None:
    v.sesion.modificado = False
    v.close()


def test_barra_propia_por_defecto(qtbot):
    v = _ventana(qtbot)
    assert marco.usar_propia()
    assert v.windowFlags() & Qt.FramelessWindowHint
    b = v.botones_ventana
    assert [x.toolTip() for x in (b.b_minimizar, b.b_maximizar, b.b_cerrar)] == [
        "Minimizar",
        "Maximizar",
        "Cerrar",
    ]
    assert v.findChild(QLabel, "titulo").parentWidget().height() == marco.ALTO_BARRA
    _cerrar(v)


def test_barra_del_sistema(qtbot):
    ajustes.guardar(marco.CLAVE, "sistema")
    v = _ventana(qtbot)
    assert not v.windowFlags() & Qt.FramelessWindowHint
    assert v.botones_ventana is None and v.marco is None
    _cerrar(v)


def test_maximizar_y_restaurar(qtbot):
    v = _ventana(qtbot)
    b = v.botones_ventana
    b.b_maximizar.click()
    qtbot.waitUntil(v.isMaximized)
    assert b.b_maximizar.toolTip() == "Restaurar"
    assert v.marco.borde(QPoint(0, 0)) == Qt.Edge(0)  # maximizada no se redimensiona
    b.b_maximizar.click()
    qtbot.waitUntil(lambda: not v.isMaximized())
    assert b.b_maximizar.toolTip() == "Maximizar"
    _cerrar(v)


def test_cerrar(qtbot):
    v = _ventana(qtbot)
    v.sesion.modificado = False
    v.botones_ventana.b_cerrar.click()
    assert not v.isVisible()


def test_bordes(qtbot):
    v = _ventana(qtbot)
    m, w, h = v.marco, v.width(), v.height()
    assert m.borde(QPoint(1, 1)) == Qt.LeftEdge | Qt.TopEdge
    assert m.borde(QPoint(w - 1, h // 2)) == Qt.RightEdge
    assert m.borde(QPoint(w // 2, h - 1)) == Qt.BottomEdge
    assert m.borde(QPoint(w // 2, h // 2)) == Qt.Edge(0)
    _cerrar(v)


def test_que_parte_arrastra(qtbot):
    v = _ventana(qtbot)
    titulo = v.findChild(QLabel, "titulo")
    calcular = next(b for b in v.findChildren(QPushButton) if b.text().startswith("Calcular"))
    barra = titulo.parentWidget()
    # El nombre del archivo y el espacio vacío arrastran; Calcular y las etapas no.
    assert v.marco.es_barra(titulo.mapToGlobal(titulo.rect().center()))
    vacio = v.botones_etapa[0].geometry().left() - 20
    assert v.marco.es_barra(barra.mapToGlobal(QPoint(vacio, barra.height() // 2)))
    assert not v.marco.es_barra(calcular.mapToGlobal(calcular.rect().center()))
    assert not v.marco.es_barra(v.botones_etapa[1].mapToGlobal(QPoint(5, 5)))
    _cerrar(v)


def test_zonas_de_windows(qtbot):
    """La respuesta a ``WM_NCHITTEST``, sin Windows: se simula la conversión a cliente."""
    v = _ventana(qtbot)
    escala = v.devicePixelRatioF()

    class User32:
        @staticmethod
        def ScreenToClient(_hwnd, punto):  # la ventana empieza en (0, 0) de la pantalla
            return 1

    w = marco._Windows.__new__(marco._Windows)
    w.ct, w.wt, w.marco, w.user32 = ctypes, wintypes, v.marco, User32()
    w._preparar = lambda: 0

    def zona(widget, punto: QPoint) -> int:
        p = widget.mapTo(v, punto)
        x, y = round(p.x() * escala), round(p.y() * escala)
        return w._zona((y << 16) | x)

    barra = v.findChild(QLabel, "titulo").parentWidget()
    maximizar = v.botones_ventana.b_maximizar
    assert zona(v, QPoint(1, 1)) == marco.HTTOPLEFT
    assert zona(v, QPoint(v.width() // 2, v.height() - 1)) == marco.HTBOTTOM
    assert zona(maximizar, maximizar.rect().center()) == marco.HTMAXBUTTON
    assert zona(barra, QPoint(v.botones_etapa[0].x() - 20, 20)) == marco.HTCAPTION
    assert zona(v.botones_etapa[1], QPoint(5, 5)) == marco.HTCLIENT
    _cerrar(v)
