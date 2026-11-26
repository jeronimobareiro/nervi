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


@pytest.fixture(autouse=True)
def preferencias_aparte(tmp_path, monkeypatch):
    # Las pruebas no leen ni tocan las preferencias de quien las corre.
    from nervi.gui import ajustes

    monkeypatch.setattr(ajustes, "ARCHIVO", str(tmp_path / "preferencias.ini"))


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


def test_deshacer_y_rehacer_desde_la_ventana(ventana, qtbot):
    assert not ventana.a_deshacer.isEnabled() and not ventana.a_rehacer.isEnabled()
    tabla = ventana.tabs_modelo.widget(0).modelo  # nudos
    assert tabla.setData(tabla.index(1, 2), "3.5")
    assert ventana.a_deshacer.isEnabled()
    assert ventana.a_deshacer.text() == "Deshacer: Editar el modelo"
    ventana.vista.setFocus()
    qtbot.keyClick(ventana.vista, Qt.Key_Z, Qt.ControlModifier)
    assert ventana.sesion.modelo["nudos"][1]["y"] == 3.0
    assert tabla.data(tabla.index(1, 2)) in ("3", "3.0", "3,0", "3,000", "3.000")
    assert ventana.a_rehacer.isEnabled() and not ventana.a_deshacer.isEnabled()
    ventana.a_rehacer.trigger()
    assert ventana.sesion.modelo["nudos"][1]["y"] == 3.5


def test_exportar_resultados(ventana, tmp_path):
    from nervi import resultados

    ruta = tmp_path / "r.json"
    assert ventana.exportar_resultados(ruta)
    datos = resultados.leer(ruta)
    assert datos["huella_modelo"] == resultados.huella(ventana.sesion.modelo)


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
        "Exportar memoria de cálculo (PDF)",
    ]
    assert [e.texto for e in filtrar(entradas, "memoria pdf")] == [
        "Exportar memoria de cálculo (PDF)"
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


def _en_hilo(qtbot, funcion):
    """Corre ``funcion`` en otro hilo mientras la ventana sigue atendiendo eventos."""
    import threading

    salida = {}

    def correr():
        try:
            salida["valor"] = funcion()
        except Exception as e:  # se revisa en la prueba
            salida["error"] = e

    hilo = threading.Thread(target=correr)
    hilo.start()
    qtbot.waitUntil(lambda: not hilo.is_alive(), timeout=60000)
    return salida


def test_conectar_con_mi_ia(ventana, qtbot, tmp_path, monkeypatch):
    from nervi.ia import canal
    from nervi.ia.herramientas import ErrorConsulta

    monkeypatch.setenv("NERVI_CANAL", str(tmp_path / "canal.json"))
    consultas = []
    ventana.canal.consulta.connect(lambda n, ok: consultas.append((n, ok)))
    assert ventana.conectar_ia() and ventana.a_conectar_ia.isChecked()
    assert (tmp_path / "canal.json").exists()
    ventana.sesion.seleccionar(Seleccion("nudo", 3))
    r = _en_hilo(qtbot, lambda: canal.consultar("leer_seleccion"))
    assert r["valor"]["seleccion"] == {"tipo": "nudo", "id": "N3"}
    modelo = _en_hilo(qtbot, lambda: canal.consultar("leer_modelo"))["valor"]
    modelo["nudos"][1]["y"] += 0.5
    r = _en_hilo(
        qtbot,
        lambda: canal.consultar("proponer_modelo", {"modelo": modelo, "descripcion": "Sube N2"}),
    )
    assert ventana.sesion.propuestas[0].id == r["valor"]["propuesta"]
    assert ventana.sesion.modelo["nudos"][1]["y"] != modelo["nudos"][1]["y"]
    r = _en_hilo(qtbot, lambda: canal.consultar("leer_nudo", {"nudo": "N99"}))
    assert isinstance(r["error"], ErrorConsulta) and "N99" in str(r["error"])
    assert consultas == [
        ("leer_seleccion", True),
        ("leer_modelo", True),
        ("proponer_modelo", True),
        ("leer_nudo", False),
    ]
    assert not ventana.conectar_ia() and not (tmp_path / "canal.json").exists()
    r = _en_hilo(qtbot, lambda: canal.consultar("leer_modelo"))
    assert isinstance(r["error"], canal.SinVentana)


def test_app_de_ia_con_la_ventana_abierta(ventana, qtbot, tmp_path, monkeypatch):
    """Lo que hace la app de IA: lanzar ``nervi-mcp`` sin argumentos y hablarle por
    stdio; el puente le pasa cada consulta a esta ventana."""
    import json
    import subprocess
    import sys

    pytest.importorskip("mcp")
    from nervi.ia.herramientas import NOMBRES, NOMBRES_VENTANA

    monkeypatch.setenv("NERVI_CANAL", str(tmp_path / "canal.json"))
    ventana.conectar_ia(True)
    proceso = subprocess.Popen(
        [sys.executable, "-m", "nervi.ia.servidor"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=os.environ,
    )

    def rpc(id_, metodo, params=None):
        mensaje = {"jsonrpc": "2.0", "id": id_, "method": metodo, "params": params or {}}
        proceso.stdin.write(json.dumps(mensaje) + "\n")
        proceso.stdin.flush()
        while True:
            linea = proceso.stdout.readline()
            if not linea:
                raise RuntimeError(proceso.stderr.read())
            respuesta = json.loads(linea)
            if respuesta.get("id") == id_:
                return respuesta

    def sesion_mcp():
        rpc(
            1,
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "prueba", "version": "0"},
            },
        )
        proceso.stdin.write(
            json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n"
        )
        proceso.stdin.flush()
        lista = rpc(2, "tools/list")["result"]["tools"]
        nudo = rpc(
            3, "tools/call", {"name": "leer_nudo", "arguments": {"nudo": "N2", "resultado": "D"}}
        )
        return lista, nudo

    try:
        r = _en_hilo(qtbot, sesion_mcp)
    finally:
        proceso.stdin.close()
        proceso.wait(timeout=10)
        proceso.stdout.close()
        proceso.stderr.close()
    assert "error" not in r, r.get("error")
    lista, nudo = r["valor"]
    assert [t["name"] for t in lista] == [*NOMBRES, *NOMBRES_VENTANA]
    datos = json.loads(nudo["result"]["content"][0]["text"])
    assert datos == ventana.canal.herramientas.leer_nudo("N2", "D")


# --- Barra lateral de menús y ajustes ------------------------------------------------
def test_barra_lateral_abre_cada_menu(ventana, qtbot):
    assert set(ventana.botones_riel) == {
        "archivo",
        "editar",
        "modelo",
        "calcular",
        "ver",
        "herramientas",
        "ia",
        "ayuda",
        "preferencias",
    }
    for clave, menu in ventana.menus_riel.items():
        # Solo acciones que existen: ninguna gris ni sin texto.
        acciones = [a for a in menu.actions() if not a.isSeparator()]
        # Deshacer y Rehacer quedan inactivos mientras no hay nada que deshacer.
        activas = acciones if clave != "editar" else []
        assert acciones and all(a.text() for a in acciones), clave
        assert all(a.isEnabled() for a in activas), clave
        ventana.abrir_menu_riel(clave)
        qtbot.waitUntil(menu.isVisible)
        assert ventana.botones_riel[clave].isChecked()
        boton = ventana.botones_riel[clave]
        assert menu.pos().x() >= boton.mapToGlobal(boton.rect().topRight()).x()
        menu.hide()
        assert not ventana.botones_riel[clave].isChecked()
    editar = ventana.menus_riel["editar"].actions()
    assert [a.text() for a in editar] == ["Deshacer", "Rehacer"]
    m = ventana.sesion.copia_modelo()
    m["nudos"][1]["y"] += 0.5
    ventana.sesion.editar(m, descripcion="Mover N2")
    assert editar[0].isEnabled() and "Mover N2" in editar[0].text()
    textos = [a.text() for a in ventana.menus_riel["archivo"].actions()]
    assert "Configuración del proyecto" in textos and "Abrir reciente" in textos


def test_preferencias_cambian_tema_y_letra(ventana):
    from nervi.gui import ajustes, estilo

    dialogo = ventana.abrir_preferencias()
    assert [dialogo.lista.item(k).text() for k in range(dialogo.lista.count())] == [
        "General",
        "Apariencia",
    ]
    dialogo.controles["interfaz/tema"].setCurrentIndex(1)
    dialogo.controles["interfaz/tamano"].setCurrentIndex(1)
    assert dialogo.aplicar()
    assert ajustes.leer("interfaz/tema") == "oscuro"
    assert estilo.actual.fondo == estilo.OSCURO.fondo and estilo.actual.tamano == 11.0
    assert ventana.a_temas["oscuro"].isChecked()
    # Restablecer el apartado vuelve a los valores por defecto.
    dialogo.elegir_apartado("Apariencia")
    dialogo._restablecer[dialogo.paginas.currentIndex()]()
    assert dialogo.aplicar()
    assert estilo.actual == estilo.CLARO
    dialogo.close()


def test_buscador_de_ajustes(ventana):
    dialogo = ventana.configurar_proyecto()
    dialogo.buscador.setText("diámetros")
    visibles = [
        dialogo.lista.item(k).text()
        for k in range(dialogo.lista.count())
        if not dialogo.lista.item(k).isHidden()
    ]
    assert visibles == ["Diseño"]
    assert dialogo.lista.currentItem().text() == "Diseño"
    dialogo.close()


def test_configuracion_del_proyecto(ventana, tmp_path):
    s = ventana.sesion
    dialogo = ventana.configurar_proyecto()
    # El modelo tiene datos: las unidades no se cambian sin convertir los valores.
    assert not dialogo.fuerza.isEnabled()
    dialogo.datos["nombre"].setText("  Galpón Norte ")
    dialogo.datos["autor"].setText("Ing. Pérez")
    dialogo.recubrimiento.setValue(30)
    for d, cb in dialogo.diametros.items():
        cb.setChecked(d in (16, 20))
    assert dialogo.aplicar()
    assert s.doc.proyecto == {"datos": {"nombre": "Galpón Norte", "autor": "Ing. Pérez"}}
    c = s.diseno["criterios"]
    assert c["recubrimiento"] == 30 and c["diametros_columna"] == [16, 20]
    assert s.modificado
    # La etapa Diseño muestra lo mismo.
    assert ventana.panel_diseno.recubrimiento.value() == 30
    s.guardar(tmp_path / "p.nrv")
    doc = formato.abrir(tmp_path / "p.nrv")
    assert doc.proyecto["datos"]["nombre"] == "Galpón Norte"
    assert doc.diseno["criterios"]["diametros_columna"] == [16, 20]
    dialogo.close()


def test_configuracion_sin_diametros_no_se_aplica(ventana):
    dialogo = ventana.configurar_proyecto()
    for cb in dialogo.diametros.values():
        cb.setChecked(False)
    assert not dialogo.aplicar()
    assert "al menos un diámetro" in dialogo.lbl_error.text()
    assert dialogo.lista.currentItem().text() == "Diseño"
    assert ventana.sesion.doc.diseno is None
    dialogo.close()


def test_sin_cambios_no_agrega_modulos(ventana):
    dialogo = ventana.configurar_proyecto()
    assert dialogo.aplicar()
    assert ventana.sesion.doc.diseno is None and ventana.sesion.doc.proyecto is None
    assert not ventana.sesion.modificado
    dialogo.close()


def test_unidades_de_un_modelo_vacio(ventana):
    ventana.sesion.nuevo()
    dialogo = ventana.configurar_proyecto()
    assert dialogo.fuerza.isEnabled()
    dialogo.fuerza.setCurrentIndex(dialogo.fuerza.findData("tf"))
    dialogo.longitud.setCurrentIndex(dialogo.longitud.findData("cm"))
    assert dialogo.aplicar()
    assert ventana.sesion.modelo["unidades"] == {"fuerza": "tf", "longitud": "cm"}
    assert ventana.lbl_unidades.text() == "tf · cm"
    dialogo.close()


def test_recientes_y_abrir_el_ultimo(ventana, tmp_path):
    from nervi.gui import ajustes
    from nervi.gui.app import crear_ventana

    ruta = tmp_path / "porticos" / "a.nrv"
    ruta.parent.mkdir()
    assert ventana._guardar_en(ruta)
    assert ajustes.recientes() == [str(ruta.resolve())]
    ventana._llenar_recientes()
    assert [a.text() for a in ventana.menu_recientes.actions()] == ["a.nrv"]
    ajustes.guardar("general/inicio", "ultimo")
    otra = crear_ventana([])
    assert otra.sesion.ruta == ruta.resolve() or otra.sesion.ruta == ruta
    otra.close()
    ajustes.guardar("general/inicio", "vacio")
    vacia = crear_ventana([])
    assert vacia.sesion.modelo["nudos"] == []
    vacia.close()


def test_panel_del_asistente(ventana, qtbot, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QLabel, QPushButton

    monkeypatch.setenv("NERVI_CANAL", str(tmp_path / "canal.json"))
    panel = ventana.asistente
    assert not panel.isVisible() and not ventana.insignia_ia.isVisible()
    ventana.abrir_menu_riel("ia")
    assert panel.isVisible() and ventana.botones_riel["ia"].isChecked()
    assert panel.b_conectar.isVisible() and panel.lbl_conexion.text() == "Sin conectar"
    panel.b_conectar.click()
    assert ventana.canal.activo and ventana.a_conectar_ia.isChecked()
    assert panel.lbl_conexion.text().endswith("Conectado") and panel.b_desconectar.isVisible()

    # Llega una propuesta: insignia en el ícono y tarjeta con su resumen.
    s = ventana.sesion
    m = s.copia_modelo()
    m["nudos"][1]["y"] += 0.5
    s.proponer(m, "ia: Claude Desktop", "Sube N2")
    assert ventana.insignia_ia.isVisible() and ventana.insignia_ia.text() == "1"
    assert panel.lbl_propuestas.text() == "PROPUESTAS PENDIENTES · 1"
    qtbot.wait(20)  # las tarjetas nuevas se muestran al volver al bucle de eventos
    textos = [w.text() for w in panel.findChildren(QLabel) if w.isVisibleTo(panel)]
    assert "Sube N2" in textos and "•  Cambia N2 (y)" in textos
    assert any(t.startswith("de Claude Desktop") for t in textos)

    dialogo = panel.vista_previa(s.propuestas[0].id)
    assert dialogo.isVisible() and dialogo._sesion.modelo["nudos"][1]["y"] == m["nudos"][1]["y"]
    assert s.modelo["nudos"][1]["y"] != m["nudos"][1]["y"]  # la vista previa no aplica
    dialogo.close()

    qtbot.wait(20)
    aplicar = next(
        b for b in panel.findChildren(QPushButton) if b.text() == "Aplicar" and b.isVisibleTo(panel)
    )
    aplicar.click()
    assert s.modelo["nudos"][1]["y"] == m["nudos"][1]["y"] and not s.propuestas
    assert not ventana.insignia_ia.isVisible()
    assert s.doc.historial["cambios"][-1]["origen"] == "ia: Claude Desktop"
    ventana.deshacer()
    assert s.modelo["nudos"][1]["y"] != m["nudos"][1]["y"]

    # Descartar no cambia nada.
    s.proponer(m, "ia: Claude Desktop", "Sube N2 otra vez")
    antes = s.copia_modelo()
    qtbot.wait(20)
    descartar = next(
        b
        for b in panel.findChildren(QPushButton)
        if b.text() == "Descartar" and b.isVisibleTo(panel)
    )
    descartar.click()
    assert not s.propuestas and s.modelo == antes

    # Las consultas del agente quedan a la vista.
    ventana.canal.consulta.emit("leer_barra", True)
    ventana.canal.consulta.emit("leer_verificaciones", False)
    assert [c[1:] for c in panel.consultas] == [
        ("leer_barra", True),
        ("leer_verificaciones", False),
    ]
    panel.b_desconectar.click()
    assert not ventana.canal.activo and not ventana.a_conectar_ia.isChecked()
    ventana.abrir_menu_riel("ia")
    assert not panel.isVisible() and not ventana.botones_riel["ia"].isChecked()


def test_propuesta_sobre_un_modelo_que_cambio(ventana, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    avisos = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a: avisos.append(a[2]))
    s = ventana.sesion
    m = s.copia_modelo()
    m["nudos"][1]["y"] += 0.5
    p = s.proponer(m, "ia: prueba", "Sube N2")
    otro = s.copia_modelo()
    otro["nudos"][2]["y"] += 1.0
    s.editar(otro)
    assert not ventana.asistente.aplicar(p.id)
    assert "cambió" in avisos[0] and "rehaga" in avisos[0]
    assert s.modelo == otro


def test_importar_dxf_con_vista_previa(ventana, tmp_path, qtbot):
    from nervi.importar import dxf

    ruta = tmp_path / "nave.dxf"
    # El pórtico del ejemplo de dxf.py, en cm: queda al lado del que ya está.
    ruta.write_text(dxf._EJEMPLO.replace("$INSUNITS\n70\n4", "$INSUNITS\n70\n5"), "utf-8")
    antes = ventana.sesion.copia_modelo()
    d = ventana.importar_dxf(ruta)
    assert d is not None and d.unidad.currentData() == "cm"
    assert not d.al_origen.isEnabled()  # el modelo ya tiene nudos
    assert d.lbl_resumen.text() == "Se agregan 3 nudos y 3 barras"
    assert len(d.vista.colores_barra) == 3  # lo nuevo, resaltado
    assert "textos" in d.lbl_avisos.text()
    assert ventana.sesion.modelo == antes  # mirar no cambia nada
    d.casillas["VIGAS"].setChecked(False)
    assert d.lbl_resumen.text() == "Se agregan 3 nudos y 2 barras"
    d.casillas["COLUMNAS"].setChecked(False)
    assert not d.b_importar.isEnabled()
    assert "no tienen líneas" in d.lbl_resumen.text()
    d.casillas["COLUMNAS"].setChecked(True)
    d.b_importar.click()
    assert len(ventana.sesion.modelo["barras"]) == len(antes["barras"]) + 2
    cambio = ventana.sesion.doc.historial["cambios"][-1]
    assert cambio["origen"] == "importador: DXF"
    assert cambio["descripcion"].startswith("Importar nave.dxf")
    assert ventana.deshacer()
    assert ventana.sesion.modelo == antes


def test_importar_un_archivo_que_no_es_dxf(ventana, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    avisos = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a: avisos.append(a[2]))
    ruta = tmp_path / "plano.dxf"
    ruta.write_bytes(b"AutoCAD Binary DXF\r\n\x1a\x00")
    assert ventana.importar_dxf(ruta) is None
    assert "binario" in avisos[0]
