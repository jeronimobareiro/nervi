# SPDX-License-Identifier: GPL-3.0-or-later
"""Dibujo con el mouse del modelo de cálculo en la vista 2D (#31)."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
pytest.importorskip("pytestqt")

from PySide6.QtCore import Qt

from nervi import formato
from nervi.gui.sesion import Seleccion, Sesion
from nervi.gui.ventana import Ventana


@pytest.fixture(autouse=True)
def preferencias_aparte(tmp_path, monkeypatch):
    from nervi.gui import ajustes

    monkeypatch.setattr(ajustes, "ARCHIVO", str(tmp_path / "preferencias.ini"))


@pytest.fixture
def ventana(qtbot):
    """Proyecto vacío en el modo Cálculo."""
    v = Ventana(Sesion(formato.Documento.nuevo()))
    v.resize(1500, 900)
    v.show()
    qtbot.waitExposed(v)
    yield v
    v.sesion.modificado = False
    v.close()
    v.deleteLater()


def _clic(v, qtbot, x, y, boton=Qt.LeftButton):
    q = v.vista.transformacion().a_pantalla(x, y).toPoint()
    qtbot.mouseMove(v.vista, q)
    qtbot.mouseClick(v.vista, boton, pos=q)


def _portico(v, qtbot):
    v.elegir_herramienta("barra", calculo=True)
    for x, y in ((0, 0), (0, 3), (6, 3), (6, 0)):
        _clic(v, qtbot, x, y)
    _clic(v, qtbot, 6, 0, Qt.RightButton)


def test_vista_vacia_y_barra_de_herramientas(ventana):
    v = ventana
    assert v.vista.transformacion() is not None
    assert not v.vista.grab().isNull()
    v.botones_herramienta_calculo["barra"].click()
    assert v.modo == "calculo" and v.vista.dibujo.herramienta == "barra"
    assert v.pila_prop.currentWidget() is v.panel_calculo
    assert v.panel_calculo.lbl_tipo.text() == "NUEVA BARRA"
    assert v.panel_calculo.campos["E"].text() == "2.5e+07"
    v.botones_enganche_calculo["orto"].click()
    assert v.vista.dibujo.opciones.enganches["orto"]
    assert not v.planta.dibujo.opciones.enganches["orto"]  # cada lienzo el suyo
    v.vista.dibujo.elegir("seleccionar")
    assert v.pila_prop.currentWidget() is v.pila_prop.widget(0)


def test_dibujar_portico_apoyos_y_cargas_y_calcular(ventana, qtbot):
    v = ventana
    _portico(v, qtbot)
    m = v.sesion.modelo
    assert [(n["x"], n["y"]) for n in m["nudos"]] == [(0, 0), (0, 3), (6, 3), (6, 0)]
    assert [(b["i"], b["j"]) for b in m["barras"]] == [(1, 2), (2, 3), (3, 4)]
    v.elegir_herramienta("apoyo", calculo=True)
    _clic(v, qtbot, 0, 0)
    _clic(v, qtbot, 6, 0)
    assert [(a["nudo"], a["rz"]) for a in v.sesion.modelo["apoyos"]] == [(1, True), (4, True)]
    v.elegir_herramienta("repartida", calculo=True)
    _clic(v, qtbot, 3, 3)
    v.elegir_herramienta("puntual", calculo=True)
    v.vista.dibujo.carga.update(fx=15.0, fy=0.0)
    _clic(v, qtbot, 0, 3)
    m = v.sesion.modelo
    assert [c["nombre"] for c in m["casos"]] == ["D"]
    assert m["cargas_barra"] == [
        {"caso": 1, "barra": 2, "tipo": "uniforme", "ejes": "global", "qx": 0.0, "qy": -10.0}
    ]
    assert m["cargas_nodales"] == [{"caso": 1, "nudo": 2, "fx": 15.0, "fy": 0.0, "mz": 0.0}]
    assert not v.vista.grab().isNull()  # con las flechas de las cargas
    v.sesion.calcular()
    r = v.sesion.resultado()
    assert sum(r.reacciones[[0, 3], 1]) == pytest.approx(60.0)
    assert sum(r.reacciones[[0, 3], 0]) == pytest.approx(-15.0)


def test_nudo_parte_barra_y_ctrl_z(ventana, qtbot):
    v = ventana
    v.elegir_herramienta("barra", calculo=True)
    _clic(v, qtbot, 0, 0)
    _clic(v, qtbot, 6, 0)
    _clic(v, qtbot, 6, 0, Qt.RightButton)
    v.elegir_herramienta("nudo", calculo=True)
    _clic(v, qtbot, 3, 0)  # se engancha al medio
    m = v.sesion.modelo
    assert len(m["barras"]) == 2 and m["nudos"][-1] == {"id": 3, "x": 3.0, "y": 0.0}
    v.sesion.deshacer()
    assert len(v.sesion.modelo["barras"]) == 1


def test_apoyo_se_saca_con_otro_clic_y_largo_escrito(ventana, qtbot):
    v = ventana
    v.elegir_herramienta("barra", calculo=True)
    v.botones_enganche_calculo["orto"].click()
    _clic(v, qtbot, 0, 0)
    qtbot.mouseMove(v.vista, v.vista.transformacion().a_pantalla(2, 0.2).toPoint())
    qtbot.keyClicks(v.vista, "4")
    entrada = v.vista.dibujo.entrada
    assert entrada.isVisible()
    entrada.largo.setText("4.5")
    qtbot.keyClick(entrada.largo, Qt.Key_Return)
    assert v.sesion.modelo["nudos"][-1]["x"] == 4.5
    v.elegir_herramienta("apoyo", calculo=True)
    _clic(v, qtbot, 0, 0)
    _clic(v, qtbot, 0, 0)
    assert v.sesion.modelo["apoyos"] == []


def test_elegir_y_borrar(ventana, qtbot):
    v = ventana
    _portico(v, qtbot)
    v.vista.dibujo.elegir("seleccionar")
    v.sesion.seleccionar(Seleccion("nudo", 2))
    v.vista.setFocus()
    qtbot.keyClick(v.vista, Qt.Key_Delete)
    m = v.sesion.modelo
    assert [n["id"] for n in m["nudos"]] == [1, 3, 4]
    assert [(b["i"], b["j"]) for b in m["barras"]] == [(3, 4)]
    assert v.sesion.seleccion is None


def test_mensaje_si_no_hay_barra(ventana, qtbot):
    v = ventana
    mensajes = []
    v.vista.dibujo.mensaje.connect(mensajes.append)
    v.elegir_herramienta("repartida", calculo=True)
    _clic(v, qtbot, 2, 2)
    assert mensajes == ["Clic en una barra"]
    assert v.sesion.modelo["cargas_barra"] == []
