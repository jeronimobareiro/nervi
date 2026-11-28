# SPDX-License-Identifier: GPL-3.0-or-later
"""Dibujo con el mouse en la planta del edificio (#73 segunda parte, #31)."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
pytest.importorskip("pytestqt")

from PySide6.QtCore import QPoint, QPointF, Qt

from nervi.fisico import ModeloFisico
from nervi.gui.sesion import Sesion, documento_ejemplo
from nervi.gui.ventana import Ventana


@pytest.fixture(autouse=True)
def preferencias_aparte(tmp_path, monkeypatch):
    from nervi.gui import ajustes

    monkeypatch.setattr(ajustes, "ARCHIVO", str(tmp_path / "preferencias.ini"))


@pytest.fixture
def ventana(qtbot):
    """Edificio vacío con planta baja y un piso: se dibuja en el Piso 1."""
    mf = ModeloFisico()
    mf.agregar_piso("Planta baja", 0.0)
    p1 = mf.agregar_piso("Piso 1", 3.0)
    s = Sesion(documento_ejemplo())
    s.editar_fisico(mf.a_json(), "Pisos")
    v = Ventana(s)
    v.resize(1400, 900)
    v.show()
    qtbot.waitExposed(v)
    v.elegir_modo("edificio")
    v.edificio.ir_a_piso(p1)
    yield v
    v.sesion.modificado = False
    v.close()
    v.deleteLater()


def _clic(v, qtbot, x, y, boton=Qt.LeftButton):
    t = v.planta.transformacion()
    q = t.a_pantalla(x, y).toPoint()
    qtbot.mouseMove(v.planta, q)
    qtbot.mouseClick(v.planta, boton, pos=q)


def _ejes(v, qtbot):
    v.elegir_herramienta("ejes")
    for x in (0.0, 6.0, 12.0):
        _clic(v, qtbot, x, -1.0)
        _clic(v, qtbot, x, 6.0)
    for y in (0.0, 5.0):
        _clic(v, qtbot, -1.0, y)
        _clic(v, qtbot, 13.0, y)


def test_planta_vacia_se_puede_dibujar(ventana):
    v = ventana
    assert v.planta.transformacion() is not None
    assert not v.planta.grab().isNull()


def test_barra_y_panel_de_la_herramienta(ventana):
    v = ventana
    v.botones_herramienta["vigas"].click()
    assert v.planta.dibujo.herramienta == "vigas"
    assert v.pila_prop.currentWidget() is v.panel_herramienta
    assert v.panel_herramienta.lbl_tipo.text() == "NUEVA VIGA"
    v.botones_enganche["orto"].click()
    assert v.planta.dibujo.opciones.enganches["orto"]
    v.planta.setFocus()
    v.planta.dibujo.elegir("seleccionar")
    assert v.pila_prop.currentWidget() is v.prop_edificio


def test_dibujar_ejes_columnas_vigas_losa_y_muro(ventana, qtbot):
    v = ventana
    _ejes(v, qtbot)
    mf = v.edificio.modelo()
    nombres = sorted(e["nombre"] for e in mf.lista("ejes"))
    assert nombres == ["1", "2", "A", "B", "C"]
    a = next(e for e in mf.lista("ejes") if e["nombre"] == "A")
    assert a["p1"] == [0.0, -1.0] and a["p2"] == [0.0, 6.0]

    # Columnas: una ventana sobre todos los cruces de los ejes.
    v.elegir_herramienta("columnas")
    t = v.planta.transformacion()
    q0, q1 = t.a_pantalla(-0.5, -0.5).toPoint(), t.a_pantalla(12.5, 5.5).toPoint()
    qtbot.mousePress(v.planta, Qt.LeftButton, pos=q0)
    qtbot.mouseMove(v.planta, q1)
    qtbot.mouseRelease(v.planta, Qt.LeftButton, pos=q1)
    mf = v.edificio.modelo()
    piso = v.edificio.piso
    cols = sorted(tuple(c["punto"]) for c in mf.en_piso(piso)["columnas"])
    assert cols == [(x, y) for x in (0.0, 6.0, 12.0) for y in (0.0, 5.0)]
    assert {c["desde"] for c in mf.lista("columnas")} == {mf.pisos_ordenados()[0]["id"]}
    assert [s["nombre"] for s in mf.lista("secciones")] == ["C 30x30"]

    # Vigas encadenadas: de A1 a C1 se parte en B1, y sube a C2. Esc termina.
    v.elegir_herramienta("vigas")
    _clic(v, qtbot, 0.0, 0.0)
    _clic(v, qtbot, 12.0, 0.0)
    _clic(v, qtbot, 12.0, 5.0)
    _clic(v, qtbot, 0.0, 5.0)
    _clic(v, qtbot, 0.0, 0.0)
    qtbot.keyClick(v.planta, Qt.Key_Escape)
    assert v.planta.dibujo.puntos == []
    mf = v.edificio.modelo()
    vigas = sorted((tuple(e["p1"]), tuple(e["p2"])) for e in mf.lista("vigas"))
    assert ((0.0, 0.0), (6.0, 0.0)) in vigas and ((6.0, 0.0), (12.0, 0.0)) in vigas
    assert ((12.0, 5.0), (6.0, 5.0)) in vigas and ((6.0, 5.0), (0.0, 5.0)) in vigas
    assert len(vigas) == 6
    # Viga del eje B, para cerrar dos paños.
    _clic(v, qtbot, 6.0, 0.0)
    _clic(v, qtbot, 6.0, 5.0)
    qtbot.keyClick(v.planta, Qt.Key_Escape)
    assert len(v.edificio.modelo().lista("vigas")) == 7

    # Losa: un clic dentro del paño de la derecha.
    v.elegir_herramienta("losas")
    _clic(v, qtbot, 9.2, 2.3)
    mf = v.edificio.modelo()
    (losa,) = mf.lista("losas")
    assert losa["contorno"] == [[6.0, 0.0], [12.0, 0.0], [12.0, 5.0], [6.0, 5.0]]
    assert mf.area_losa(losa["id"]) == pytest.approx(30.0)

    # Muro en el eje A.
    v.elegir_herramienta("muros")
    _clic(v, qtbot, 0.0, 0.0)
    _clic(v, qtbot, 0.0, 5.0)
    qtbot.keyClick(v.planta, Qt.Key_Escape)
    (muro,) = v.edificio.modelo().lista("muros")
    assert muro["p1"] == [0.0, 0.0] and muro["p2"] == [0.0, 5.0]

    # Cada cosa es un Ctrl+Z: el muro se deshace solo.
    v.deshacer()
    assert v.edificio.modelo().lista("muros") == []
    assert len(v.edificio.modelo().lista("losas")) == 1


def test_largo_escrito_y_orto(ventana, qtbot):
    v = ventana
    v.elegir_herramienta("vigas")
    v.botones_enganche["orto"].setChecked(True)
    _clic(v, qtbot, 0.0, 0.0)
    # El cursor casi horizontal: con orto la dirección es 0°.
    t = v.planta.transformacion()
    qtbot.mouseMove(v.planta, t.a_pantalla(3.0, 0.4).toPoint())
    qtbot.keyClicks(v.planta, "2")
    entrada = v.planta.dibujo.entrada
    assert entrada.isVisible()
    qtbot.keyClicks(entrada.largo, ".5")
    qtbot.keyClick(entrada.largo, Qt.Key_Return)
    (viga,) = v.edificio.modelo().lista("vigas")
    assert viga["p1"] == [0.0, 0.0] and viga["p2"] == [2.5, 0.0]
    # Con ángulo escrito.
    qtbot.keyClicks(v.planta, "4")
    qtbot.keyClick(entrada.largo, Qt.Key_Tab)
    qtbot.keyClicks(entrada.angulo, "90")
    qtbot.keyClick(entrada.angulo, Qt.Key_Return)
    vigas = v.edificio.modelo().lista("vigas")
    assert vigas[-1]["p1"] == [2.5, 0.0] and vigas[-1]["p2"] == [2.5, 4.0]


def test_losa_a_mano_y_avisos(ventana, qtbot):
    v = ventana
    # Sin vigas no hay paño: los clics dibujan el contorno y Enter lo cierra.
    v.elegir_herramienta("losas")
    for x, y in ((0.0, 0.0), (4.0, 0.0), (4.0, 3.0), (0.0, 3.0)):
        _clic(v, qtbot, x, y)
    qtbot.keyClick(v.planta, Qt.Key_Return)
    (losa,) = v.edificio.modelo().lista("losas")
    assert losa["contorno"] == [[0.0, 0.0], [4.0, 0.0], [4.0, 3.0], [0.0, 3.0]]
    # En la planta baja no hay piso abajo para las columnas.
    v.edificio.subir(-1)
    v.elegir_herramienta("columnas")
    mensajes = []
    v.edificio.mensaje.connect(mensajes.append)
    _clic(v, qtbot, 1.0, 1.0)
    assert v.edificio.modelo().lista("columnas") == []
    assert "piso de abajo" in mensajes[-1]


def test_seleccionar_y_borrar(ventana, qtbot):
    v = ventana
    v.elegir_herramienta("vigas")
    _clic(v, qtbot, 0.0, 0.0)
    _clic(v, qtbot, 5.0, 0.0)
    qtbot.keyClick(v.planta, Qt.Key_Escape)
    qtbot.keyClick(v.planta, Qt.Key_Escape)  # segundo Esc: vuelve a Seleccionar
    assert v.planta.dibujo.herramienta == "seleccionar"
    _clic(v, qtbot, 2.5, 0.0)
    assert v.edificio.eleccion[0] == "vigas"
    qtbot.keyClick(v.planta, Qt.Key_Delete)
    assert v.edificio.modelo().lista("vigas") == []


def test_marca_de_enganche(ventana, qtbot):
    v = ventana
    _ejes(v, qtbot)
    v.elegir_herramienta("vigas")
    t = v.planta.transformacion()
    qtbot.mouseMove(v.planta, (t.a_pantalla(6.0, 0.0) + QPointF(3, -2)).toPoint())
    e = v.planta.dibujo.enganche
    assert e.tipo == "cruce" and e.punto == (6.0, 0.0)
    assert not v.planta.grab().isNull()
    qtbot.mouseMove(v.planta, QPoint(2, 2))
