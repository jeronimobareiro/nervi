# SPDX-License-Identifier: GPL-3.0-or-later
"""Modelo físico en la interfaz (issue #73): modo Edificio, planta por piso, árbol,
tablas, propiedades y gestor de plantas (pytest-qt, sin pantalla)."""

import importlib.util
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
pytest.importorskip("pytestqt")

from PySide6.QtCore import QPointF, Qt

from nervi.gui.edificio import GestorPlantas, filas_arbol
from nervi.gui.sesion import Sesion, documento_ejemplo
from nervi.gui.ventana import Ventana

RAIZ = Path(__file__).resolve().parents[1]


def _edificio():
    spec = importlib.util.spec_from_file_location(
        "edificio_fisico", RAIZ / "examples" / "edificio_fisico.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.armar()


@pytest.fixture(autouse=True)
def preferencias_aparte(tmp_path, monkeypatch):
    from nervi.gui import ajustes

    monkeypatch.setattr(ajustes, "ARCHIVO", str(tmp_path / "preferencias.ini"))


@pytest.fixture
def ventana(qtbot):
    s = Sesion(documento_ejemplo())
    s.editar_fisico(_edificio().a_json(), "Edificio de ejemplo")
    v = Ventana(s)
    v.show()
    qtbot.waitExposed(v)
    v.elegir_modo("edificio")
    yield v
    v.sesion.modificado = False
    v.close()
    v.deleteLater()


def _piso(v, nombre):
    return next(p["id"] for p in v.edificio.modelo().lista("pisos") if p["nombre"] == nombre)


def test_modo_edificio_y_calculo(ventana):
    v = ventana
    assert v.vistas.currentWidget() is v.planta
    assert v.pila_arbol.currentWidget() is v.arbol_edificio
    assert v.pila_prop.currentWidget() is v.prop_edificio
    assert v.panel_inferior.currentWidget() is v.tablas_edificio
    assert not v.ctx_calculo.isVisible() and v.ctx_edificio.isVisible()
    assert "4 pisos" in v.lbl_tamano.text()
    v.elegir_modo("calculo")
    assert v.vistas.currentWidget() is v.vista
    assert v.pila_arbol.currentWidget() is v.arbol
    assert v.panel_inferior.currentWidget() is v.tabs_modelo
    assert v.ctx_calculo.isVisible() and not v.ctx_edificio.isVisible()
    assert "nudos" in v.lbl_tamano.text()


def test_edificio_no_muestra_resultados_ni_diseno_del_calculo(ventana):
    """En Edificio no se ven las barras del pórtico de cálculo en Resultados ni Diseño."""
    v = ventana
    tabs = v.panel_inferior
    for panel in (v.tabs_res, v.panel_diseno, v.panel_dinamica):
        assert not tabs.isTabVisible(tabs.indexOf(panel))
    # Ir a la etapa Diseño pasa al modelo de cálculo, donde están esas barras.
    v.ir_a_etapa(4)
    assert v.modo == "calculo"
    assert tabs.currentWidget() is v.panel_diseno
    assert tabs.isTabVisible(tabs.indexOf(v.panel_diseno))
    # Volver a Edificio con Diseño a la vista muestra las tablas del edificio.
    v.elegir_modo("edificio")
    assert tabs.currentWidget() is v.tablas_edificio
    v.mostrar_dinamica()
    assert v.modo == "calculo" and tabs.currentWidget() is v.panel_dinamica


def test_empieza_en_la_planta_mas_baja_con_elementos(ventana):
    assert ventana.edificio.piso == _piso(ventana, "Piso 1")
    assert ventana.combo_planta.count() == 4
    assert ventana.combo_planta.currentData() == ventana.edificio.piso


def test_flechas_y_atajos_cambian_de_planta(ventana, qtbot):
    v = ventana
    v.b_subir.click()
    assert v.edificio.piso == _piso(v, "Piso 2")
    v.subir_planta(5)  # no pasa del techo
    assert v.edificio.piso == _piso(v, "Piso 3")
    assert not v.b_subir.isEnabled() and v.b_bajar.isEnabled()
    v.planta.setFocus()
    qtbot.keyClick(v.planta, Qt.Key_PageDown)
    assert v.edificio.piso == _piso(v, "Piso 2")
    v.combo_planta.activated.emit(v.combo_planta.findData(_piso(v, "Planta baja")))
    assert v.edificio.piso == _piso(v, "Planta baja")
    assert not v.b_bajar.isEnabled()
    # En Cálculo, Re Pág y Av Pág son de las tablas.
    v.elegir_modo("calculo")
    assert not v.a_subir.isEnabled()


def test_planta_dibuja_y_elige_con_clic(ventana, qtbot):
    v = ventana
    imagen = v.planta.grab()
    assert not imagen.isNull()
    t = v.planta.transformacion()
    # Medio de la viga de (0, 0) a (6, 0) del piso 1.
    p = t.a_pantalla(3.0, 0.0)
    qtbot.mouseClick(v.planta, Qt.LeftButton, pos=p.toPoint())
    lista, id = v.edificio.eleccion
    assert lista == "vigas"
    assert v.edificio.modelo().elemento("vigas", id)["nombre"] == "V101"
    assert v.prop_edificio.lbl_nombre.text() == "V101"
    # Una columna en (6, 5) y una losa en el centro de un paño.
    assert v.planta.elemento_en(t.a_pantalla(6.0, 5.0))[0] == "columnas"
    assert v.planta.elemento_en(t.a_pantalla(3.0, 2.5))[0] == "losas"
    assert v.planta.elemento_en(QPointF(2, 2)) is None
    qtbot.mouseClick(v.planta, Qt.LeftButton, pos=QPointF(2, 2).toPoint())
    assert v.edificio.eleccion is None
    assert v.prop_edificio.lbl_tipo.text() == "PLANTA"


def test_arbol_del_edificio(ventana):
    v = ventana
    mf = v.edificio.modelo()
    filas = filas_arbol(mf, v.edificio.piso)
    grupos = {f.clave: f.cantidad for f in filas if f.grupo}
    assert grupos["pisos"] == 4 and grupos["columnas"] == 6 and grupos["vigas"] == 7
    viga = mf.en_piso(v.edificio.piso)["vigas"][0]["id"]
    v._item_explorador("edificio", ("vigas", viga))
    assert v.edificio.eleccion == ("vigas", viga)
    v._item_explorador("edificio", ("pisos", _piso(v, "Piso 3")))
    assert v.edificio.piso == _piso(v, "Piso 3") and v.edificio.eleccion is None
    v._item_explorador("tabla_edificio", "losas")
    assert v.tablas_edificio.currentWidget() is v.tablas_edificio.editores["losas"]


def test_tabla_edita_agrega_elimina_y_deshace(ventana):
    v = ventana
    editor = v.tablas_edificio.editores["vigas"]
    tabla = editor.modelo
    assert tabla.rowCount() == 7
    col_x2 = [c.titulo for c in tabla.columnas].index("x₂")
    assert tabla.setData(tabla.index(0, col_x2), "6,5")
    id = tabla.id_de_fila(0)
    assert v.edificio.modelo().elemento("vigas", id)["p2"][0] == 6.5
    # Un valor inválido no cambia nada y avisa.
    col_secc = [c.titulo for c in tabla.columnas].index("Sección")
    assert not tabla.setData(tabla.index(0, col_secc), "no existe")
    editor.agregar()
    assert tabla.rowCount() == 8
    editor.tabla.selectRow(7)
    editor.eliminar()
    assert tabla.rowCount() == 7
    for _ in range(3):
        assert v.deshacer()
    assert v.edificio.modelo().elemento("vigas", id)["p2"][0] == 6.0


def test_agregar_piso_desde_cero(qtbot):
    v = Ventana(Sesion(documento_ejemplo()))
    qtbot.addWidget(v)
    v.elegir_modo("edificio")
    assert v.edificio.piso is None
    assert v.prop_edificio.lbl_nombre.text() == "Sin pisos"
    v.tablas_edificio.editores["pisos"].agregar()
    assert v.edificio.piso is not None
    v.tablas_edificio.editores["columnas"].agregar()  # sin piso de abajo: avisa
    assert not v.edificio.modelo().lista("columnas")
    v.tablas_edificio.editores["pisos"].agregar()
    v.edificio.subir(1)
    v.tablas_edificio.editores["columnas"].agregar()
    mf = v.edificio.modelo()
    assert len(mf.lista("columnas")) == 1 and mf.lista("materiales")
    v.sesion.modificado = False


def test_propiedades_editables(ventana):
    v = ventana
    mf = v.edificio.modelo()
    losa = mf.en_piso(v.edificio.piso)["losas"][0]["id"]
    v.edificio.elegir("losas", losa)
    p = v.prop_edificio
    campos = {
        p.form.itemAt(k, p.form.ItemRole.LabelRole).widget().text(): p.form.itemAt(
            k, p.form.ItemRole.FieldRole
        ).widget()
        for k in range(p.form.rowCount())
    }
    campos["Espesor [mm]"].setText("150")
    campos["Espesor [mm]"].editingFinished.emit()
    assert v.edificio.modelo().elemento("losas", losa)["espesor"] == 150.0
    campos = {
        p.form.itemAt(k, p.form.ItemRole.LabelRole).widget().text(): p.form.itemAt(
            k, p.form.ItemRole.FieldRole
        ).widget()
        for k in range(p.form.rowCount())
    }
    campos["Contorno (x, y; …)"].setText("0, 0; 6, 0")
    campos["Contorno (x, y; …)"].editingFinished.emit()
    assert p.lbl_error.isVisibleTo(p)
    assert len(v.edificio.modelo().elemento("losas", losa)["contorno"]) == 4
    assert v.deshacer()
    assert v.edificio.modelo().elemento("losas", losa)["espesor"] == 120.0


def test_gestor_de_plantas(ventana, monkeypatch):
    v = ventana
    g = v.gestionar_plantas()
    assert isinstance(g, GestorPlantas)
    assert g.tabla.rowCount() == 4
    # Agregar arriba del techo: un piso más, 3 m más arriba.
    g.elegida = _piso(v, "Piso 3")
    g.agregar(arriba=True)
    assert g.tabla.rowCount() == 5
    assert g.mf.nivel(g.elegida) == pytest.approx(12.0)
    # Cambiar el entrepiso del piso 1 mueve los de arriba.
    p1 = _piso(v, "Piso 1")
    g.elegida = p1
    g._planta_elegida()
    g.c_mover.setChecked(True)
    g.e_entrepiso.setValue(3.5)
    g._entrepiso()
    assert g.mf.nivel(p1) == pytest.approx(3.5)
    assert g.mf.nivel(_piso(v, "Piso 3")) == pytest.approx(9.5)
    # Copiar el piso 1 al nuevo piso.
    nuevo = max(p["id"] for p in g.mf.lista("pisos"))
    g.c_origen.setCurrentIndex(g.c_origen.findData(p1))
    for id, b in g.c_destinos.items():
        b.setChecked(id == nuevo)
    g.copiar()
    assert g.mf.elementos_en_piso(nuevo) == 6 + 7 + 2
    # Quitar una planta con elementos pide confirmación.
    g.elegida = _piso(v, "Piso 2")
    monkeypatch.setattr(g, "confirmar", lambda n: False)
    g.quitar()
    assert g.tabla.rowCount() == 5
    monkeypatch.setattr(g, "confirmar", lambda n: True)
    g.quitar()
    assert g.tabla.rowCount() == 4
    # Nada cambia en la sesión hasta Aceptar, y un Ctrl+Z lo deshace todo.
    assert len(v.edificio.modelo().lista("pisos")) == 4
    assert v.edificio.modelo().nivel(p1) == 3.0
    g.accept()
    mf = v.edificio.modelo()
    assert [p["nombre"] for p in mf.pisos_ordenados()][-1] == "Piso 4"
    assert mf.nivel(p1) == pytest.approx(3.5)
    assert v.deshacer()
    assert v.edificio.modelo().nivel(p1) == 3.0
    assert len(v.edificio.modelo().lista("pisos")) == 4


def test_gestor_cancelar_no_cambia_nada(ventana):
    v = ventana
    antes = v.sesion.fisico
    g = v.gestionar_plantas()
    g.agregar(arriba=False)
    g.reject()
    assert v.sesion.fisico == antes
