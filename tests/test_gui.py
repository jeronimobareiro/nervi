# SPDX-License-Identifier: GPL-3.0-or-later
"""Pruebas de humo de la interfaz de escritorio (pytest-qt, sin pantalla)."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
pytest.importorskip("pytestqt")

from PySide6.QtCore import Qt

from nervi import formato
from nervi.gui.paleta import filtrar
from nervi.gui.sesion import Seleccion, Sesion, documento_ejemplo
from nervi.gui.ventana import Ventana


@pytest.fixture
def ventana(qtbot):
    v = Ventana(Sesion(documento_ejemplo()))
    v.show()
    qtbot.waitExposed(v)
    yield v
    v.sesion.modificado = False  # que el cierre no pregunte por cambios sin guardar
    v.close()
    v.deleteLater()


def test_calcular_y_mostrar_resultados(ventana):
    assert ventana.calcular()
    s = ventana.sesion
    assert s.al_dia
    ventana.combo.setCurrentText("1.2D+1.6L")
    r = s.resultado()
    viga = s.indices.barras[2]
    assert r.diagrama(viga)["M"].max() == pytest.approx(119.08, abs=0.01)
    assert ventana.tabs_res.widget(0).model().rowCount() == 2
    assert "al día" in ventana.lbl_estado.text()


def test_editar_tabla_desactualiza_resultados(ventana):
    ventana.calcular()
    tabla = ventana.tabs_modelo.widget(0).modelo  # nudos
    assert tabla.setData(tabla.index(1, 2), "3.5")
    assert ventana.sesion.modelo["nudos"][1]["y"] == 3.5
    assert not ventana.sesion.al_dia
    assert ventana.sesion.modificado
    assert "desactualizados" in ventana.lbl_estado.text()


def test_dato_invalido_no_se_acepta(ventana):
    tabla = ventana.tabs_modelo.widget(1).modelo  # barras
    assert not tabla.setData(tabla.index(0, 3), "abc")
    assert ventana.sesion.modelo["barras"][0]["E"] == 2.5e7


def test_agregar_y_eliminar_filas(ventana):
    editor = ventana.tabs_modelo.widget(0)
    editor.agregar()
    assert ventana.sesion.modelo["nudos"][-1]["id"] == 5
    assert any(a.nivel == "error" and "N5" in a.texto for a in ventana.sesion.avisos)
    editor.tabla.selectRow(4)
    editor.eliminar()
    assert len(ventana.sesion.modelo["nudos"]) == 4


def test_mecanismo_avisa_sin_romper(ventana):
    modelo = ventana.sesion.copia_modelo()
    modelo["apoyos"] = []
    ventana.sesion.editar(modelo)
    assert not ventana.calcular()
    assert ventana.panel_inferior.currentWidget() is ventana.revision
    # Sin apoyos todos los nudos se mueven; el motor señala uno y la vista lo marca.
    ines = ventana.sesion.inestabilidad
    assert ines is not None and ines.nudo in {n["id"] for n in modelo["nudos"]}
    assert ventana.sesion.seleccion == Seleccion("nudo", ines.nudo)
    ventana.vista.grab()
    # Al editar el modelo la marca desaparece.
    ventana.sesion.editar(ventana.sesion.copia_modelo())
    assert ventana.sesion.inestabilidad is None


def test_mecanismo_marca_el_nudo_con_su_id(ventana):
    # Viga articulada en el centro: los id no coinciden con los índices del motor.
    modelo = ventana.sesion.copia_modelo()
    modelo["nudos"] = [
        {"id": 10, "x": 0.0, "y": 0.0},
        {"id": 20, "x": 3.0, "y": 0.0},
        {"id": 30, "x": 6.0, "y": 0.0},
    ]
    barra = dict(modelo["barras"][0])
    modelo["barras"] = [
        {**barra, "id": 1, "i": 10, "j": 20, "liberaciones": [False] * 5 + [True]},
        {**barra, "id": 2, "i": 20, "j": 30, "liberaciones": [False, False, True] + [False] * 3},
    ]
    modelo["apoyos"] = [{"nudo": 10, "ux": True, "uy": True}, {"nudo": 30, "uy": True}]
    modelo["cargas_nodales"] = [{"caso": 1, "nudo": 20, "fy": -10.0}]
    modelo["cargas_barra"] = []
    modelo["desplazamientos_impuestos"] = []
    ventana.sesion.editar(modelo)
    assert not ventana.calcular()
    ines = ventana.sesion.inestabilidad
    assert (ines.nudo, ines.gdl) == (20, "uy")
    assert ines.nudos == {10, 20, 30}
    assert "N20 se puede mover en uy" in ventana.sesion.avisos[0].texto


def test_guardar_y_abrir(ventana, tmp_path):
    ruta = tmp_path / "portico"
    assert ventana._guardar_en(ruta)
    assert (tmp_path / "portico.nrv").exists()
    assert ventana.windowTitle().startswith("portico.nrv")
    doc = formato.abrir(tmp_path / "portico.nrv")
    assert doc.modelo == ventana.sesion.modelo
    ventana.sesion.nuevo()
    assert ventana.abrir(tmp_path / "portico.nrv")
    assert len(ventana.sesion.modelo["barras"]) == 3


def test_diagramas_y_seleccion(ventana, qtbot):
    ventana.calcular()
    for clave in ("V", "N", "D", "M"):
        ventana.botones_diagrama[clave].click()
        assert ventana.vista.diagrama == clave
        ventana.vista.grab()  # dibuja sin errores
    ventana.sesion.seleccionar(Seleccion("barra", 2))
    assert ventana.lbl_sel.text() == "B2"
    ventana.sesion.seleccionar(Seleccion("nudo", 1))
    assert ventana.lbl_sel.text() == "N1"


def test_clic_en_la_vista_selecciona_la_barra(ventana, qtbot):
    _bid, _k, pi, pj = ventana.vista._barras()[1]
    medio = ((pi + pj) / 2).toPoint()
    qtbot.mouseClick(ventana.vista, Qt.LeftButton, pos=medio)
    assert ventana.sesion.seleccion == Seleccion("barra", 2)


def test_paleta_de_comandos(ventana):
    entradas = ventana.entradas_paleta()
    assert [e.texto for e in filtrar(entradas, "calcul")] == ["Calcular"]
    assert any(e.texto.startswith("B2") for e in filtrar(entradas, "b2"))
    assert filtrar(entradas, "geometria")  # sin tilde también encuentra
    paleta = ventana.abrir_paleta()
    paleta.campo.setText("calcular")
    paleta._ejecutar_actual()
    assert ventana.sesion.al_dia


def test_consola(ventana):
    ventana.calcular()
    ventana.combo.setCurrentText("1.2D+1.6L")
    salida = ventana.consola.ejecutar("round(float(r.reacciones[0, 1]), 2)")
    assert salida.strip() == "120.0"
    assert "NameError" in ventana.consola.ejecutar("no_existe")


def test_carga_trapezoidal_en_la_tabla(ventana):
    editor = ventana.tabs_modelo.widget(5)  # cargas en barras
    tabla = editor.modelo
    assert tabla.lista == "cargas_barra"
    cols = [c.clave for c in tabla.columnas]
    fila = 0
    assert ventana.sesion.modelo["cargas_barra"][fila]["tipo"] == "uniforme"
    assert not tabla.flags(tabla.index(fila, cols.index("b"))) & Qt.ItemIsEditable
    assert tabla.setData(tabla.index(fila, cols.index("tipo")), "trapezoidal")
    carga = ventana.sesion.modelo["cargas_barra"][fila]
    assert carga["qy1"] == carga["qy2"] == -20.0  # la uniforme pasa a parcial en toda la luz
    assert "b" not in carga and "qy" not in carga
    assert tabla.flags(tabla.index(fila, cols.index("b"))) & Qt.ItemIsEditable
    assert tabla.setData(tabla.index(fila, cols.index("b")), "4")
    assert tabla.setData(tabla.index(fila, cols.index("qy2")), "-5")
    assert not tabla.setData(tabla.index(fila, cols.index("b")), "abc")
    assert ventana.sesion.modelo["cargas_barra"][fila]["b"] == 4.0
    assert ventana.calcular()
    assert tabla.setData(tabla.index(fila, cols.index("b")), "")
    assert "b" not in ventana.sesion.modelo["cargas_barra"][fila]
    assert tabla.setData(tabla.index(fila, cols.index("tipo")), "puntual")
    carga = ventana.sesion.modelo["cargas_barra"][fila]
    assert set(carga) == {"caso", "barra", "tipo", "ejes", "a", "px", "py"}


def test_carga_termica_en_la_tabla(ventana):
    tabla = ventana.tabs_modelo.widget(5).modelo
    cols = [c.clave for c in tabla.columnas]
    assert tabla.setData(tabla.index(0, cols.index("tipo")), "termica")
    assert not tabla.flags(tabla.index(0, cols.index("qx2"))) & Qt.ItemIsEditable
    assert tabla.setData(tabla.index(0, cols.index("a")), "1.2e-5")
    assert tabla.setData(tabla.index(0, cols.index("qx")), "30")
    carga = ventana.sesion.modelo["cargas_barra"][0]
    assert carga["tipo"] == "termica"
    assert carga["alfa"] == 1.2e-5 and carga["dt"] == 30.0
    # La qy de la uniforme pasó a la columna del gradiente: sin canto no calcula.
    assert carga["gradiente"] == -20.0
    assert not ventana.calcular()
    assert tabla.setData(tabla.index(0, cols.index("b")), "0.5")
    assert ventana.sesion.modelo["cargas_barra"][0]["h"] == 0.5
    assert ventana.calcular()


def test_carga_momento_en_la_tabla_y_el_inspector(ventana):
    tabla = ventana.tabs_modelo.widget(5).modelo
    cols = [c.clave for c in tabla.columnas]
    assert tabla.setData(tabla.index(0, cols.index("tipo")), "momento")
    assert not tabla.flags(tabla.index(0, cols.index("qy"))) & Qt.ItemIsEditable
    assert tabla.setData(tabla.index(0, cols.index("a")), "2")
    assert tabla.setData(tabla.index(0, cols.index("qx")), "-15")
    carga = ventana.sesion.modelo["cargas_barra"][0]
    assert set(carga) == {"caso", "barra", "tipo", "ejes", "a", "mz"}
    assert carga["a"] == 2.0 and carga["mz"] == -15.0
    assert ventana.calcular()
    ventana.sesion.seleccionar(Seleccion("barra", carga["barra"]))
    assert ventana.lbl_sel.text() == f"B{carga['barra']}"


def test_inspector_con_carga_termica(ventana):
    tabla = ventana.tabs_modelo.widget(5).modelo
    cols = [c.clave for c in tabla.columnas]
    assert tabla.setData(tabla.index(0, cols.index("tipo")), "termica")
    assert tabla.setData(tabla.index(0, cols.index("a")), "1.2e-5")
    assert tabla.setData(tabla.index(0, cols.index("qy")), "0")
    carga = ventana.sesion.modelo["cargas_barra"][0]
    # Antes el inspector buscaba "a" en la carga térmica y fallaba.
    ventana.sesion.seleccionar(Seleccion("barra", carga["barra"]))
    assert ventana.lbl_sel.text() == f"B{carga['barra']}"
