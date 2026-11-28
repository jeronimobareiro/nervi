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


def test_el_proyecto_dice_si_es_edificio_o_portico(ventana, qtbot):
    """Sin selector Edificio | Cálculo: un proyecto con modelo físico se abre como
    edificio, y uno sin modelo físico como pórtico plano (#74)."""
    v = ventana
    assert v.modo == "edificio"
    assert not hasattr(v, "botones_modo")
    assert v.vistas.currentWidget() is v.planta
    assert v.pila_arbol.currentWidget() is v.arbol_edificio
    assert v.pila_prop.currentWidget() is v.prop_edificio
    assert v.panel_inferior.currentWidget() is v.tablas_edificio
    assert not v.ctx_calculo.isVisible() and v.ctx_edificio.isVisible()
    assert v.botones_vista["planta"].isVisible() and not v.botones_vista["frente"].isVisible()
    assert "4 pisos" in v.lbl_tamano.text() and "barras" in v.lbl_tamano.text()
    p = Ventana(Sesion(documento_ejemplo()))
    qtbot.addWidget(p)
    assert p.modo == "calculo"
    assert p.vistas.currentWidget() is p.vista
    assert p.pila_arbol.currentWidget() is p.arbol
    assert p.panel_inferior.currentWidget() is p.tabs_modelo
    assert not p.botones_vista["planta"].isVisibleTo(p)
    assert "nudos" in p.lbl_tamano.text()


def test_nuevo_edificio_y_nuevo_portico(ventana):
    v = ventana
    v.sesion.modificado = False
    v.nuevo(edificio=False)
    assert v.modo == "calculo" and not v.sesion.es_edificio
    v.nuevo()
    assert v.modo == "edificio" and v.sesion.es_edificio
    assert len(v.edificio.modelo()) == 0
    assert v.a_nuevo.text() == "Nuevo edificio"


def test_las_etapas_mandan_sobre_el_panel_inferior(ventana):
    """El panel inferior no tiene pestañas de primer nivel: muestra lo de la etapa."""
    v = ventana
    tabs = v.panel_inferior
    assert tabs.tabBar().isHidden()
    v.ir_a_etapa(1)
    assert tabs.currentWidget() is v.tablas_edificio
    assert v.tablas_edificio.currentWidget() is v.tablas_edificio.editores["losas"]
    v.ir_a_etapa(2)
    a = v.tabs_analisis
    assert tabs.currentWidget() is a and a.currentWidget() is v.revision
    assert a.isTabVisible(a.indexOf(v.panel_modelo_calculo))
    assert not a.isTabVisible(a.indexOf(v.panel_dinamica))
    assert v.panel_modelo_calculo.modelo.rowCount() == v.sesion.modelo_calculo().n_barras
    v.ir_a_etapa(3)
    assert tabs.currentWidget() is v.res_edificio
    v.ir_a_etapa(4)
    assert tabs.currentWidget() is v.diseno_edificio
    # La dinámica es del pórtico plano: en el edificio avisa y no cambia de etapa.
    v.mostrar_dinamica()
    assert tabs.currentWidget() is v.diseno_edificio
    # La consola es un panel propio.
    v.mostrar_consola()
    assert v.paneles["consola"].isVisible()


def test_calcular_el_edificio_devuelve_resultados_a_cada_elemento(ventana):
    v = ventana
    assert v.calcular()
    s = v.sesion
    assert s.edificio_al_dia and v.etapas.checkedId() == 3
    assert v.panel_inferior.currentWidget() is v.res_edificio
    assert "al día" in v.lbl_estado.text()
    assert [v.combo.itemText(k) for k in range(v.combo.count())] == ["1.4D", "1.2D+1.6L", "D", "L"]
    v.combo.setCurrentText("1.2D+1.6L")
    t = v.res_edificio.por_elemento
    mf = v.edificio.modelo()
    assert t.rowCount() == len(mf.lista("vigas"))
    # La fila de V101 tiene los momentos leídos sobre la viga del edificio.
    fila = next(k for k in range(t.rowCount()) if t.textos[k][0] == "V101")
    mc = s.modelo_calculo()
    d = mc.diagrama(s.resultado_edificio(), "vigas", mf.lista("vigas")[0]["id"])
    assert t.valores[fila, 0] == pytest.approx(d["Mz"][0])
    assert t.valores[fila, 1] == pytest.approx(d["Mz"].max())
    # Elegir una fila elige el elemento del edificio.
    v.res_edificio.tabla_elementos.clicked.emit(t.index(fila, 0))
    assert v.edificio.eleccion == ("vigas", mf.lista("vigas")[0]["id"])
    v.res_edificio.elegir_lista("columnas")
    assert t.rowCount() == len(mf.lista("columnas"))
    assert v.res_edificio.reacciones.rowCount() == len(mc.apoyos)
    assert v.res_edificio.derivas.rowCount() == 3
    # Cambiar el edificio deja los resultados desactualizados.
    datos = mf.a_json()
    datos["vigas"][0]["p2"] = [6.0, 0.0]
    s.editar_fisico(datos)
    assert not s.edificio_al_dia and s.resultado_edificio() is None
    assert "desactualizados" in v.lbl_estado.text()
    assert v.res_edificio.por_elemento.rowCount() == 0
    assert "calculá" in v.res_edificio.nota.text()


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
    # En un pórtico plano, Re Pág y Av Pág son de las tablas.
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
