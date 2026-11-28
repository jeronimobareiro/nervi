# SPDX-License-Identifier: GPL-3.0-or-later
"""Paneles acoplables y distribuciones guardadas (``nervi.gui.paneles``)."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
pytest.importorskip("pytestqt")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QBoxLayout

from nervi.gui import paneles
from nervi.gui.sesion import Sesion, documento_ejemplo
from nervi.gui.ventana import Ventana


@pytest.fixture(autouse=True)
def preferencias_aparte(tmp_path, monkeypatch):
    from nervi.gui import ajustes

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


def test_paneles_de_fabrica(qtbot):
    v = _ventana(qtbot)
    d = v.paneles
    assert v.dockWidgetArea(d["estructura"]) == Qt.LeftDockWidgetArea
    assert v.dockWidgetArea(d["propiedades"]) == Qt.RightDockWidgetArea
    assert v.dockWidgetArea(d["inferior"]) == Qt.BottomDockWidgetArea
    assert not d["asistente"].isVisible()
    assert d["estructura"].isVisible() and d["inferior"].isVisible()
    # El ancho de las tablas no obliga a una ventana enorme (antes, unos 2000 px). El
    # mínimo depende de las fuentes de cada sistema: lo fija la barra superior.
    assert v.minimumSizeHint().width() < 1600
    v.elegir_modo("edificio")
    assert d["estructura"].windowTitle() == "Edificio"
    assert d["estructura"].titleBarWidget().etiqueta.text() == "Edificio"
    _cerrar(v)


def test_desacoplar_cerrar_y_volver_a_abrir(qtbot):
    v = _ventana(qtbot)
    dock = v.paneles["propiedades"]
    titulo = dock.titleBarWidget()
    titulo.b_flotar.click()
    assert dock.isFloating() and titulo.b_flotar.toolTip() == "Acoplar"
    titulo.b_flotar.click()
    assert not dock.isFloating()
    titulo.b_cerrar.click()
    assert not dock.isVisible()
    v._llenar_paneles()
    accion = next(a for a in v.menu_paneles.actions() if a.text() == "Propiedades")
    assert not accion.isChecked()
    accion.trigger()
    assert dock.isVisible()
    _cerrar(v)


def test_asistente_es_un_panel(qtbot):
    v = _ventana(qtbot)
    v.abrir_menu_riel("ia")
    assert v.paneles["asistente"].isVisible() and v.botones_riel["ia"].isChecked()
    v.paneles["asistente"].titleBarWidget().b_cerrar.click()
    assert not v.botones_riel["ia"].isChecked()
    _cerrar(v)


def test_la_distribucion_se_recuerda_al_volver_a_abrir(qtbot):
    v = _ventana(qtbot)
    v.paneles["estructura"].close()
    v.addDockWidget(Qt.LeftDockWidgetArea, v.paneles["propiedades"])
    _cerrar(v)
    w = _ventana(qtbot)
    assert not w.paneles["estructura"].isVisible()
    assert w.dockWidgetArea(w.paneles["propiedades"]) == Qt.LeftDockWidgetArea
    w.restablecer_distribucion()
    assert w.paneles["estructura"].isVisible()
    assert w.dockWidgetArea(w.paneles["propiedades"]) == Qt.RightDockWidgetArea
    _cerrar(w)


def test_distribuciones_con_nombre(qtbot):
    v = _ventana(qtbot)
    v.paneles["inferior"].close()
    assert v.guardar_distribucion("Solo la vista") == "Solo la vista"
    assert paneles.distribuciones() == ["Solo la vista"]
    v.restablecer_distribucion()
    assert v.paneles["inferior"].isVisible()
    assert v.aplicar_distribucion("Solo la vista")
    assert not v.paneles["inferior"].isVisible()
    assert v.guardar_distribucion("  ") is None
    v._llenar_distribuciones()
    assert [a.text() for a in v.menu_distribuciones.actions() if a.text()][:1] == ["Solo la vista"]
    paneles.borrar_distribucion("Solo la vista")
    assert paneles.distribuciones() == []
    assert not v.aplicar_distribucion("Solo la vista")
    _cerrar(v)


def test_barra_de_dibujo_a_un_costado(qtbot):
    v = _ventana(qtbot)
    barra = v.barra_dibujo
    assert barra.isMovable()
    v.addToolBar(Qt.LeftToolBarArea, barra)
    capas = v.dibujo_calculo.property("capas")
    assert all(c.direction() == QBoxLayout.TopToBottom for c in capas)
    v.addToolBar(Qt.TopToolBarArea, barra)
    assert all(c.direction() == QBoxLayout.LeftToRight for c in capas)
    # Cada modo muestra sus herramientas.
    v.elegir_modo("edificio")
    assert v.dibujo_edificio.isVisible() and not v.dibujo_calculo.isVisible()
    _cerrar(v)
