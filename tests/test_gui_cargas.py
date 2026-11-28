# SPDX-License-Identifier: GPL-3.0-or-later
"""Cargas por planta en la interfaz (issue #78): botón Cargas y caso en el modo
Edificio, zonas tributarias en la planta, cargas en pisos y losas y lo que recibe
cada viga (pytest-qt, sin pantalla)."""

import importlib.util
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
pytest.importorskip("pytestqt")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QLineEdit

from nervi.gui.edificio import DiagramaCarga, TablaFisico, diagrama, resultante
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
    piso1 = next(p["id"] for p in v.edificio.modelo().lista("pisos") if p["nombre"] == "Piso 1")
    v.edificio.ir_a_piso(piso1)
    yield v
    v.sesion.modificado = False
    v.close()
    v.deleteLater()


def _viga(v, nombre):
    return next(x["id"] for x in v.edificio.modelo().lista("vigas") if x.get("nombre") == nombre)


def _textos(prop):
    """Textos de las etiquetas que muestra ahora el panel de propiedades."""
    textos = []
    for k in range(prop.form.count()):
        w = prop.form.itemAt(k).widget()
        if w is None:
            continue
        for e in [w, *w.findChildren(QLabel)]:
            if isinstance(e, QLabel):
                textos.append(e.text())
    return textos


def test_boton_cargas_y_caso(ventana):
    v = ventana
    assert not v.edificio.cargas_visibles and not v.combo_caso.isVisible()
    v.b_cargas.click()
    assert v.edificio.cargas_visibles and v.combo_caso.isVisible()
    v.combo_caso.setCurrentIndex(3)
    v.combo_caso.activated.emit(3)
    assert v.edificio.caso == "sobrecarga"
    v.planta.grab()  # dibuja zonas y rótulos sin errores
    v.b_cargas.click()
    assert not v.edificio.cargas_visibles and not v.combo_caso.isVisible()
    with pytest.raises(ValueError):
        v.edificio.mostrar_cargas(True, "viento")


def test_viga_elegida_muestra_lo_que_recibe(ventana):
    v = ventana
    v.edificio.mostrar_cargas(True, "peso_propio")
    v106 = _viga(v, "V106")
    v.edificio.elegir("vigas", v106)
    r = v.edificio.reparto()
    # V106 entre las dos losas de 6 x 5 m: dos triángulos de 6,25 m² con 3 kN/m².
    assert resultante(r, ("vigas", v106), "peso_propio") == pytest.approx(37.5)
    assert resultante(r, ("vigas", v106), "total") == pytest.approx(37.5 + 18.75 + 25.0)
    puntos = diagrama(r, ("vigas", v106), "peso_propio")
    assert max(q for _, q in puntos) == pytest.approx(15.0)
    assert puntos[0][1] == pytest.approx(0.0) and puntos[-1][1] == pytest.approx(0.0)
    textos = _textos(v.prop_edificio)
    assert "CARGAS DE LOSAS" in textos and "37,5" in textos and "15,00" in textos
    assert "12.50 m²" in textos
    assert v.prop_edificio.findChildren(DiagramaCarga)
    v.planta.grab()


def test_cargas_del_piso_se_editan_y_se_deshacen(ventana):
    v = ventana
    piso = v.edificio.piso
    form = v.prop_edificio.form
    campos = {
        w.property("clave"): w
        for w in (form.itemAt(k).widget() for k in range(form.count()))
        if isinstance(w, QLineEdit)
    }
    campos["sobrecarga"].setText("3")
    campos["sobrecarga"].editingFinished.emit()
    assert v.edificio.modelo().elemento("pisos", piso)["sobrecarga"] == 3.0
    assert v.edificio.reparto().cargas_losa[1]["sobrecarga"] == 3.0
    v.sesion.deshacer()
    assert v.edificio.modelo().elemento("pisos", piso)["sobrecarga"] == 2.0


def test_tabla_de_losas_muestra_la_carga_del_piso_en_gris(ventana):
    v = ventana
    t = TablaFisico(v.edificio, "losas")
    col = next(k for k, c in enumerate(t.columnas) if c.clave == "sobrecarga")
    i = t.index(0, col)
    assert t.data(i, Qt.DisplayRole) == "2" and t.data(i, Qt.EditRole) == ""
    assert t.data(i, Qt.ToolTipRole)
    assert t.setData(i, "4,5")
    i = t.index(0, col)
    assert t.data(i, Qt.DisplayRole) == "4.5" and t.data(i, Qt.ToolTipRole) is None
    losa = t.id_de_fila(0)
    assert v.edificio.modelo().cargas_losa(losa)["sobrecarga"] == 4.5
    # Vacía otra vez: vuelve a tomar la del piso.
    assert t.setData(t.index(0, col), "")
    assert "sobrecarga" not in v.edificio.modelo().elemento("losas", losa)


def test_losa_sin_repartir_avisa(ventana):
    v = ventana
    piso = v.edificio.piso
    h = v.edificio.modelo().lista("materiales")[0]["id"]
    v.edificio.aplicar(
        lambda mf: mf.agregar_losa(
            piso, [(20, 0), (24, 0), (24, 2), (22, 2), (22, 4), (20, 4)], 120.0, h, nombre="LX"
        ),
        "Losa en L",
    )
    losa = next(x["id"] for x in v.edificio.modelo().lista("losas") if x.get("nombre") == "LX")
    v.edificio.mostrar_cargas(True)
    v.edificio.elegir("losas", losa)
    assert any("no es convexa" in t for t in _textos(v.prop_edificio))
    assert "Peso propio" in _textos(v.prop_edificio)
    v.planta.grab()
