# SPDX-License-Identifier: GPL-3.0-or-later
"""Árbol del modelo (panel Estructura): filas, secciones plegables y clics."""

# ruff: noqa: RUF001

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
pytest.importorskip("pytestqt")

from PySide6.QtCore import QPoint, Qt

from nervi.design import proyecto
from nervi.gui import arbol, estilo
from nervi.gui.sesion import Seleccion, Sesion, documento_ejemplo
from nervi.gui.ventana import Ventana


@pytest.fixture(autouse=True)
def preferencias_aparte(tmp_path, monkeypatch):
    from nervi.gui import ajustes

    monkeypatch.setattr(ajustes, "ARCHIVO", str(tmp_path / "preferencias.ini"))


@pytest.fixture
def ventana(qtbot):
    v = Ventana(Sesion(documento_ejemplo()))
    v.resize(1400, 900)
    v.show()
    qtbot.waitExposed(v)
    yield v
    v.sesion.modificado = False
    v.close()
    v.deleteLater()


def _modelo():
    s = Sesion(documento_ejemplo())
    return s.modelo, proyecto.elementos(s.modelo, s.diseno)


def test_filas_dicen_que_es_cada_cosa():
    modelo, elementos = _modelo()
    filas = arbol.filas(modelo, elementos)
    grupos = [(f.clave, f.cantidad) for f in filas if f.grupo]
    assert grupos == [
        ("nudos", 4),
        ("barras", 3),
        ("apoyos", 2),
        ("secciones", 2),
        ("cargas", 3),
        ("combinaciones", 3),
    ]
    por_codigo = {(f.clave, f.codigo): f for f in filas if not f.grupo}
    assert por_codigo[("barras", "B1")].detalle == "Columna 30×30"
    assert por_codigo[("barras", "B2")].detalle == "Viga 25×50"
    assert por_codigo[("barras", "B2")].dato == "N2 → N3"
    assert por_codigo[("apoyos", "N1")].detalle == "Empotrado"
    assert por_codigo[("secciones", "30×30")].dato == "2 barras"
    assert por_codigo[("secciones", "25×50")].dato == "1 barra"
    assert por_codigo[("cargas", "D")].detalle == "Permanente"
    assert por_codigo[("cargas", "W")].detalle == "Viento"
    assert por_codigo[("nudos", "N3")].dato == "(6; 3)"


def test_sin_elementos_no_hay_secciones():
    modelo, _ = _modelo()
    filas = arbol.filas(modelo, None)
    assert "secciones" not in {f.clave for f in filas}
    assert next(f for f in filas if f.codigo == "B1").detalle == ""


@pytest.mark.parametrize(
    ("apoyo", "nombre"),
    [
        ({"ux": True, "uy": True, "rz": True}, "Empotrado"),
        ({"ux": True, "uy": True}, "Articulado"),
        ({"uy": True}, "Deslizante"),
        ({"ux": True, "rz": True}, "Empotrado deslizante"),
    ],
)
def test_tipo_de_apoyo(apoyo, nombre):
    assert arbol.tipo_apoyo({"nudo": 1, **apoyo}) == nombre


def test_secciones_plegables_y_recordadas(ventana):
    a = ventana.arbol
    abiertas = {
        a.topLevelItem(i).data(0, arbol._ROL_FILA).clave
        for i in range(a.topLevelItemCount())
        if a.topLevelItem(i).isExpanded()
    }
    assert abiertas == set(arbol.ABIERTAS)
    a.alternar("nudos")
    a.alternar("barras")
    ventana.sesion.editar(ventana.sesion.copia_modelo())  # rearma el árbol
    estado = {
        a.topLevelItem(i).data(0, arbol._ROL_FILA).clave: a.topLevelItem(i).isExpanded()
        for i in range(a.topLevelItemCount())
    }
    assert estado["nudos"] and not estado["barras"]


def test_clics_del_arbol(ventana, qtbot):
    a = ventana.arbol
    item = a._items[("barras", "B2")]
    qtbot.mouseClick(a.viewport(), Qt.LeftButton, pos=a.visualItemRect(item).center())
    assert ventana.sesion.seleccion == Seleccion("barra", 2)
    assert item.isSelected()

    item = a._items[("combinaciones", "1.2D+1.6L")]
    qtbot.mouseClick(a.viewport(), Qt.LeftButton, pos=a.visualItemRect(item).center())
    assert ventana.combo.currentText() == "1.2D+1.6L"
    assert a.activo == ("combinaciones", "1.2D+1.6L")

    # El título de una sección plegada la despliega y muestra su tabla.
    grupo = next(
        a.topLevelItem(i)
        for i in range(a.topLevelItemCount())
        if a.topLevelItem(i).data(0, arbol._ROL_FILA).clave == "apoyos"
    )
    rect = a.visualItemRect(grupo)
    qtbot.mouseClick(a.viewport(), Qt.LeftButton, pos=QPoint(rect.left() + 60, rect.center().y()))
    assert grupo.isExpanded()
    assert ventana.panel_inferior.currentWidget() is ventana.tabs_modelo
    assert ventana.tabs_modelo.currentIndex() == 2
    # El chevrón solo la pliega.
    qtbot.mouseClick(a.viewport(), Qt.LeftButton, pos=QPoint(rect.right() - 12, rect.center().y()))
    assert not grupo.isExpanded()


def test_seleccion_desde_el_dibujo_resalta_el_arbol(ventana):
    ventana.sesion.seleccionar(Seleccion("barra", 3))
    assert ventana.arbol._items[("barras", "B3")].isSelected()
    ventana.sesion.seleccionar(None)
    assert not ventana.arbol.selectedItems()


@pytest.mark.parametrize("tema", ["claro", "oscuro"])
def test_dibuja_en_los_dos_temas(ventana, tema):
    from PySide6.QtWidgets import QApplication

    estilo.aplicar(QApplication.instance(), estilo.TEMAS[tema])
    try:
        ventana.sesion.seleccionar(Seleccion("barra", 2))
        imagen = ventana.arbol.viewport().grab().toImage()
        assert not imagen.isNull()
        # El fondo del panel sale del tema.
        fondo = imagen.pixelColor(imagen.width() - 2, imagen.height() - 2)
        assert fondo.name() == estilo.PANEL.lower()
    finally:
        estilo.aplicar(QApplication.instance(), estilo.CLARO)
