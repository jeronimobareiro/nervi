# SPDX-License-Identifier: GPL-3.0-or-later
"""Zoom, paneo y grilla de la planta del edificio y de la vista 2D."""

import math

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pytestqt")

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication
from test_gui_edificio import _edificio

from nervi.gui.navegacion import Camara, Vista, escala_papel, paso_grilla
from nervi.gui.sesion import Sesion, documento_ejemplo
from nervi.gui.ventana import Ventana


def test_paso_grilla_serie_1_2_5():
    # 40 px por metro: el paso fino que deja 14 px es 0.5 m y el grueso 1 m.
    assert paso_grilla(40.0) == pytest.approx((0.5, 1.0))
    assert paso_grilla(14.0) == pytest.approx((1.0, 5.0))
    assert paso_grilla(5.0) == pytest.approx((5.0, 10.0))
    assert paso_grilla(1.0) == pytest.approx((20.0, 100.0))
    for escala in (0.01, 0.3, 7.0, 123.0, 9000.0):
        fino, grueso = paso_grilla(escala)
        assert fino * escala >= 14 * (1 - 1e-9)
        assert fino * escala < 14 * 2.5 + 1e-9
        assert grueso / fino == pytest.approx(round(grueso / fino))


def test_escala_papel():
    # A 96 ppp un metro son 3779.5 px; con 37.8 px por metro la escala es 1:100.
    assert escala_papel(Vista(37.795, 0, 0), "m", 96) == 100
    assert escala_papel(Vista(0.37795, 0, 0), "cm", 96) == 100
    assert escala_papel(Vista(1, 0, 0), "pies", 96) is None


def test_camara_acerca_hacia_el_cursor():
    c = Camara()
    ajuste = Vista(10.0, 5.0, 2.0)
    centro, cursor = QPointF(400, 300), QPointF(520, 210)

    def bajo_cursor(v):
        return (
            v.cx + (cursor.x() - centro.x()) / v.escala,
            v.cy - (cursor.y() - centro.y()) / v.escala,
        )

    antes = bajo_cursor(c.resolver(ajuste))
    c.acercar(1.2**3, cursor, centro, ajuste)
    assert c.activa
    assert c.vista.escala == pytest.approx(10.0 * 1.2**3)
    assert bajo_cursor(c.vista) == pytest.approx(antes)
    c.desplazar(30, -20, ajuste)
    assert c.vista.cx == pytest.approx(
        antes[0] - (cursor.x() - centro.x()) / c.vista.escala - 30 / c.vista.escala
    )
    c.encuadrar()
    assert not c.activa and c.resolver(ajuste) is ajuste


@pytest.fixture
def ventana(qtbot):
    s = Sesion(documento_ejemplo())
    s.editar_fisico(_edificio().a_json(), "Edificio de ejemplo")
    v = Ventana(s)
    v.resize(1400, 900)
    v.show()
    qtbot.waitExposed(v)
    v.elegir_modo("edificio")
    yield v
    v.sesion.modificado = False
    v.close()
    v.deleteLater()


def _rueda(lienzo, pos: QPointF, pasos: int) -> None:
    evento = QWheelEvent(
        pos,
        lienzo.mapToGlobal(pos),
        QPoint(0, 0),
        QPoint(0, 120 * pasos),
        Qt.NoButton,
        Qt.NoModifier,
        Qt.NoScrollPhase,
        False,
    )
    QApplication.sendEvent(lienzo, evento)


@pytest.mark.parametrize("cual", ["planta", "vista"])
def test_rueda_paneo_y_encuadre(ventana, qtbot, cual):
    if cual == "vista":
        ventana.elegir_modo("calculo")
    lienzo = getattr(ventana, cual)
    qtbot.wait(10)
    inicial = lienzo.vista_actual()
    assert inicial is not None and not lienzo.camara.activa
    cursor = QPointF(lienzo.width() * 0.3, lienzo.height() * 0.4)
    centro = lienzo.centro_lienzo()

    def modelo(v, q):
        return (v.cx + (q.x() - centro.x()) / v.escala, v.cy - (q.y() - centro.y()) / v.escala)

    antes = modelo(inicial, cursor)
    _rueda(lienzo, cursor, 2)
    v = lienzo.vista_actual()
    assert v.escala == pytest.approx(inicial.escala * 1.44)
    assert modelo(v, cursor) == pytest.approx(antes)

    # Paneo con el botón del medio: el modelo sigue al mouse.
    qtbot.mousePress(lienzo, Qt.MiddleButton, pos=QPoint(200, 200))
    qtbot.mouseMove(lienzo, QPoint(260, 170))
    qtbot.mouseRelease(lienzo, Qt.MiddleButton, pos=QPoint(260, 170))
    w = lienzo.vista_actual()
    assert w.cx == pytest.approx(v.cx - 60 / v.escala)
    assert w.cy == pytest.approx(v.cy - 30 / v.escala)
    lienzo.update()
    assert not lienzo.grab().isNull()

    # F encuadra de nuevo.
    lienzo.setFocus()
    qtbot.keyClick(lienzo, Qt.Key_F)
    assert not lienzo.camara.activa
    assert lienzo.vista_actual().escala == pytest.approx(inicial.escala)

    # Botones de la esquina.
    lienzo.botones_navegacion.botones["acercar"].click()
    assert lienzo.vista_actual().escala == pytest.approx(inicial.escala * 1.2)
    lienzo.botones_navegacion.botones["encuadrar"].click()
    assert not lienzo.camara.activa


def test_el_clic_izquierdo_sigue_eligiendo_con_zoom(ventana, qtbot):
    planta = ventana.planta
    _rueda(planta, QPointF(planta.width() / 2, planta.height() / 2), 1)
    t = planta.transformacion()
    mf = ventana.edificio.modelo()
    viga = mf.en_piso(ventana.edificio.piso)["vigas"][0]
    (x1, y1), (x2, y2) = viga["p1"], viga["p2"]
    q = t.a_pantalla((x1 + x2) / 2, (y1 + y2) / 2)
    qtbot.mouseClick(planta, Qt.LeftButton, pos=q.toPoint())
    assert ventana.edificio.eleccion == ("vigas", viga["id"])
    # El botón del medio no elige.
    qtbot.mouseClick(planta, Qt.MiddleButton, pos=QPoint(5, 5))
    assert ventana.edificio.eleccion == ("vigas", viga["id"])


def test_abrir_otro_proyecto_encuadra(ventana):
    ventana.planta.zoom(3.0)
    ventana.vista.zoom(3.0)
    ventana.sesion.modificado = False  # sin el diálogo de cambios sin guardar
    ventana.abrir_ejemplo()
    assert not ventana.planta.camara.activa and not ventana.vista.camara.activa
    assert math.isfinite(ventana.vista.vista_actual().escala)
