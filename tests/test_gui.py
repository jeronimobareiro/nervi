# SPDX-License-Identifier: GPL-3.0-or-later
"""Pruebas de humo de la interfaz de escritorio (pytest-qt, sin pantalla)."""

import os

import numpy as np
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
    assert [e.texto for e in filtrar(entradas, "calcul")] == [
        "Calcular",
        "Exportar memoria de cálculo (PDF)…",
    ]
    assert [e.texto for e in filtrar(entradas, "memoria pdf")] == [
        "Exportar memoria de cálculo (PDF)…"
    ]
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


def test_exportar_memoria_de_calculo(ventana, tmp_path):
    pytest.importorskip("reportlab")
    ruta = tmp_path / "memoria.pdf"
    assert ventana.exportar_memoria(ruta)
    assert ruta.read_bytes().startswith(b"%PDF")
    # Los rótulos usan los id de modelo.json que ve el usuario.
    doc = ventana.sesion.memoria()
    nudos = next(
        b for b in doc.capitulos[1].bloques if getattr(b, "titulo", "") == "Nudos y apoyos"
    )
    ids = [n["id"] for n in ventana.sesion.modelo["nudos"]]
    assert [f[0] for f in nudos.filas] == [f"N{i}" for i in ids]


# --- Etapa Diseño ------------------------------------------------------------------------


def test_etapa_diseno_habilitada_y_disena(ventana):
    boton = ventana.botones_etapa[4]
    assert boton.isEnabled() and not ventana.botones_etapa[5].isEnabled()
    assert ventana.disenar()
    s, panel = ventana.sesion, ventana.panel_diseno
    assert ventana.panel_inferior.currentWidget() is panel
    assert s.diseno_al_dia and boton.text() == "✓ Diseño"
    # Desde que se diseña, los datos de diseño quedan en el proyecto.
    assert s.doc.diseno is not None and s.modificado
    t = panel.tabla
    assert [t.item(f, 0).text() for f in range(t.rowCount())] == ["B1", "B2", "B3"]
    viga = s.resultado_diseno(2)
    assert t.item(1, 4).text() == viga.armadura["Inferior"]
    assert t.item(1, 6).text() == viga.armadura["Estribos"]
    assert t.item(1, 7).text() == f"✓ {viga.relacion:.2f}"
    col = s.resultado_diseno(1)
    assert t.item(0, 4).text() == f"Longitudinal: {col.armadura['Longitudinal']}"
    assert t.item(0, 7).text() == f"✓ {col.relacion:.2f}"
    assert "experimental" in panel.aviso.text().lower()
    # La vista 2D colorea cada barra según su estado.
    assert set(ventana.vista.colores_barra) == {1, 2, 3}


def test_diseno_muestra_verificaciones_de_la_barra_elegida(ventana):
    ventana.disenar()
    s, panel = ventana.sesion, ventana.panel_diseno
    s.seleccionar(Seleccion("barra", 2))
    v = panel.verif
    viga = s.resultado_diseno(2)
    assert v.rowCount() == len(viga.verificaciones)
    assert v.item(0, 0).text() == "Flexión M+"
    assert v.item(0, 3).text().startswith("§")
    assert panel.tabla.currentRow() == 1
    # El panel de propiedades suma la armadura de la barra.
    assert ventana.lbl_dis.isVisibleTo(ventana)
    # Elegir otra fila de la tabla selecciona esa barra.
    panel.tabla.selectRow(2)
    assert s.seleccion == Seleccion("barra", 3)


def test_diseno_editar_seccion_tipo_y_materiales(ventana, qtbot):
    ventana.disenar()
    s, panel = ventana.sesion, ventana.panel_diseno
    panel.tabla.item(1, 3).setText("300")  # h de la viga
    qtbot.waitUntil(lambda: s.doc.diseno["elementos"] == [{"barra": 2, "h": 300.0}])
    assert not s.diseno_al_dia
    panel.disenar()
    assert s.resultado_diseno(2).estado == "no cumple"
    assert panel.tabla.item(1, 7).text().startswith("✕")
    # Tipo "No diseñar" para la columna B1.
    combo = panel.tabla.cellWidget(0, 1)
    combo.setCurrentIndex(combo.findData("No diseñar"))
    assert {"barra": 1, "tipo": "ninguno"} in s.doc.diseno["elementos"]
    panel.fc.setValue(30.0)
    assert s.doc.diseno["hormigon"]["fc"] == 30.0
    # Un dato no válido no se acepta y la tabla vuelve al valor anterior.
    panel.tabla.item(1, 2).setText("-5")
    qtbot.wait(10)
    assert {"barra": 2, "h": 300.0} in s.doc.diseno["elementos"]
    assert panel.tabla.item(1, 2).text() == "250"
    # La tabla se rearma sin dejar selectores de tipo sueltos en otras columnas.
    assert all(panel.tabla.cellWidget(f, 0) is None for f in range(3))


def test_diseno_editar_modelo_lo_desactualiza(ventana):
    ventana.disenar()
    tabla = ventana.tabs_modelo.widget(0).modelo
    assert tabla.setData(tabla.index(1, 2), "3.5")
    assert not ventana.sesion.diseno_al_dia
    assert "desactualizado" in ventana.panel_diseno.lbl_estado.text()


def test_diseno_sin_combinaciones_avisa(ventana):
    m = ventana.sesion.copia_modelo()
    m["combinaciones"] = []
    ventana.sesion.editar(m)
    assert not ventana.disenar()
    assert "combinaciones" in ventana.panel_diseno.lbl_mensaje.text()


def test_diseno_se_guarda_y_se_abre(ventana, tmp_path, qtbot):
    ventana.disenar()
    panel = ventana.panel_diseno
    panel.tabla.item(1, 3).setText("550")
    qtbot.waitUntil(lambda: ventana.sesion.doc.diseno["elementos"] != [])
    ruta = tmp_path / "p.nrv"
    assert ventana._guardar_en(ruta)
    otra = Sesion()
    otra.abrir(ruta)
    assert otra.doc.diseno["elementos"] == [{"barra": 2, "h": 550.0}]
    assert otra.resultados_diseno is None


def test_memoria_con_capitulo_de_diseno(ventana, tmp_path):
    pytest.importorskip("reportlab")
    doc = ventana.sesion.memoria()
    assert not any(c.titulo.startswith("Diseño") for c in doc.capitulos)
    assert doc.normas == []
    ventana.disenar()
    doc = ventana.sesion.memoria()
    assert doc.capitulos[-1].titulo == "Diseño de hormigón armado (ACI 318-19)"
    assert any("experimental" in a.lower() for a in doc.avisos)
    assert [n[:10] for n in doc.normas] == ["ACI 318-19"]  # hoja de normativa
    assert ventana.exportar_memoria(tmp_path / "m.pdf")


# --- Dinámica: modos y espectros ---------------------------------------------------------


def test_dinamica_sin_masa_avisa(ventana):
    panel = ventana.panel_dinamica
    assert not ventana.analizar_dinamica()
    assert ventana.panel_inferior.currentWidget() is panel
    assert "masa" in panel.lbl_estado.text()
    assert ventana.sesion.doc.dinamica is None


def test_dinamica_desde_el_panel(ventana, qtbot):
    s, panel = ventana.sesion, ventana.panel_dinamica
    # Factores de masa en la tabla (D = 1, L = 0,25) y un espectro de ejemplo.
    filas = {panel.t_masas.item(k, 0).text(): k for k in range(panel.t_masas.rowCount())}
    panel.t_masas.item(filas["D"], 1).setText("1")
    panel.t_masas.item(filas["L"], 1).setText("0,25")
    assert s.dinamica["masas"]["casos"] == {"D": 1.0, "L": 0.25}
    panel.n_modos.setValue(4)
    panel.agregar_espectro()
    assert [e["nombre"] for e in s.dinamica["espectros"]] == ["Sismo X"]
    assert panel.t_puntos.rowCount() == len(s.dinamica["espectros"][0]["puntos"])
    panel.c_combinacion.setCurrentText("SRSS")
    assert s.dinamica["espectros"][0]["combinacion"] == "SRSS"

    assert ventana.analizar_dinamica()
    din = s.resultados_dinamica
    assert s.dinamica_al_dia and panel.t_modos.rowCount() == din.modal.n_modos == 4
    assert panel.t_basal.rowCount() == 1
    # Primer modo: traslación horizontal con toda la masa en X; se dibuja como deformada.
    assert din.modal.masa_participante[0, 0] == pytest.approx(1.0, abs=1e-4)
    assert s.combinacion == "Modo 1" and ventana.vista.diagrama == "D"
    assert "Modo 1" in s.nombres_resultado() and "Sismo X" in s.nombres_resultado()
    assert np.abs(s.resultado().desplazamientos[:, :2]).max() == pytest.approx(1.0)
    ventana.vista.grab()
    # Elegir el espectro en la tabla muestra su momento (valores absolutos).
    panel.t_basal.selectRow(0)
    assert s.combinacion == "Sismo X" and ventana.vista.diagrama == "M"
    assert s.resultado().cortante_basal[0] > 0
    ventana.vista.grab()
    # Animación del modo en la vista 2D.
    panel.t_modos.selectRow(1)
    assert s.combinacion == "Modo 2"
    panel.b_animar.setChecked(True)
    qtbot.waitUntil(lambda: ventana.vista.fase != 1.0, timeout=2000)
    ventana.vista.grab()
    panel.b_animar.setChecked(False)
    assert ventana.vista.fase == 1.0
    # Editar el modelo desactualiza la dinámica y saca los modos del selector.
    m = s.copia_modelo()
    m["nudos"][1]["x"] = 0.1
    s.editar(m)
    assert not s.dinamica_al_dia and "Modo 1" not in s.nombres_resultado()
    assert "desactualizados" in panel.lbl_estado.text()


def test_dinamica_se_guarda_y_va_a_la_memoria(ventana, tmp_path):
    pytest.importorskip("reportlab")
    s = ventana.sesion
    d = formato.dinamica.nuevo()
    d["masas"]["casos"] = {"D": 1.0}
    d["n_modos"] = 3
    d["espectros"].append(formato.dinamica.espectro_ejemplo())
    s.editar_dinamica(d)
    ruta = tmp_path / "p.nrv"
    assert ventana._guardar_en(ruta)
    otra = Sesion()
    otra.abrir(ruta)
    assert otra.doc.dinamica == d and otra.resultados_dinamica is None
    # La memoria analiza si hace falta y suma el capítulo antes del de diseño.
    doc = s.memoria()
    assert doc.capitulos[-1].titulo == "Análisis dinámico"
    ventana.disenar()
    titulos = [c.titulo for c in s.memoria().capitulos]
    assert titulos.index("Análisis dinámico") < titulos.index(
        "Diseño de hormigón armado (ACI 318-19)"
    )
    assert ventana.exportar_memoria(tmp_path / "m.pdf")


def test_modo_en_la_escena_3d(ventana):
    # El visor 3D dibuja el modo como una deformada (sin abrir VTK).
    from nervi.gui import escena3d

    s = ventana.sesion
    d = formato.dinamica.nuevo()
    d["masas"]["casos"] = {"D": 1.0}
    s.editar_dinamica(d)
    ventana.analizar_dinamica()
    escena = escena3d.armar(s.modelo, s.resultado(), s.indices, "D", s.combinacion)
    assert escena.deformada
