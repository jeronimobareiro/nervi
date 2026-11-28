# SPDX-License-Identifier: GPL-3.0-or-later
"""Visor 3D de resultados (issue #30).

La geometría (``escena3d``) se prueba sin VTK. El dibujo con PyVista se prueba
renderizando a imagen sin pantalla; si en el equipo no hay PyVista u OpenGL
esas pruebas se omiten, salvo con ``NERVI_EXIGIR_3D=1`` (así corre el CI).
"""

import os
import subprocess
import sys

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)

from nervi import formato
from nervi.gui import escena3d
from nervi.gui.sesion import Seleccion, Sesion, documento_ejemplo


@pytest.fixture(scope="module")
def sesion():
    s = Sesion(documento_ejemplo())
    s.calcular()
    s.elegir_combinacion("1.2D+1.0L+1.0W")
    return s


# --- Geometría, sin VTK --------------------------------------------------------------
def test_portico_plano_en_el_plano_xz(sesion):
    e = escena3d.geometria(sesion.modelo)
    assert e.es_plano
    np.testing.assert_allclose(e.nudos[3], [6.0, 0.0, 3.0])
    assert e.tamano == pytest.approx(6.0)
    assert {a.tipo for a in e.apoyos} == {"empotrado"}


def test_ejes_locales_como_en_el_motor():
    # Barra horizontal: y local hacia arriba (+Z del visor), como +y del modelo.
    ejes = escena3d.ejes_locales(np.zeros(3), np.array([2.0, 0.0, 0.0]))
    np.testing.assert_allclose(ejes, [[1, 0, 0], [0, 0, 1], [0, -1, 0]], atol=1e-15)
    # Columna hacia arriba: y local hacia -X (giro antihorario de +Z).
    columna = escena3d.ejes_locales(np.zeros(3), np.array([0.0, 0.0, 3.0]))
    np.testing.assert_allclose(columna[1], [-1, 0, 0], atol=1e-15)
    espacial = escena3d.ejes_locales(np.zeros(3), np.array([1.0, 2.0, 3.0]), False)
    for e in (ejes, columna, espacial):
        np.testing.assert_allclose(e @ e.T, np.eye(3), atol=1e-12)
        assert np.linalg.det(e) == pytest.approx(1.0)


def test_nudos_con_z_quedan_en_el_espacio():
    """El visor ya acepta nudos con ``z`` (modelos espaciales de la Fase 2a)."""
    modelo = {
        "nudos": [{"id": 1, "x": 0, "y": 0, "z": 0}, {"id": 2, "x": 0, "y": 4, "z": 3}],
        "barras": [{"id": 7, "i": 1, "j": 2}],
        "apoyos": [{"nudo": 1, "ux": True, "uy": True}],
    }
    e = escena3d.geometria(modelo)
    assert not e.es_plano
    np.testing.assert_allclose(e.nudos[2], [0.0, 4.0, 3.0])
    assert e.barras[0].largo == pytest.approx(5.0)
    assert e.apoyos[0].tipo == "articulado"


def test_cargas_con_factores_de_la_combinacion(sesion):
    e = escena3d.geometria(sesion.modelo)
    flechas = escena3d.cargas(e, sesion.modelo, "1.2D+1.0L+1.0W")
    viga = [f for f in flechas if f.distribuida]
    assert len(viga) == 10
    for f in viga:
        # qy local -20 (D) y -10 (L) sobre la viga: hacia abajo (-Z), 1.2·20 + 1.0·10
        np.testing.assert_allclose(f.direccion, [0, 0, -1], atol=1e-12)
        assert f.punta[2] == pytest.approx(3.0)
        assert f.valor == pytest.approx(34.0)
    (viento,) = [f for f in flechas if not f.distribuida]
    np.testing.assert_allclose(viento.direccion, [1, 0, 0])
    assert viento.valor == pytest.approx(15.0)
    np.testing.assert_allclose(viento.punta, [0.0, 0.0, 3.0])
    assert escena3d.cargas(e, sesion.modelo, "1.4D")[0].valor == pytest.approx(28.0)
    assert escena3d.cargas(e, sesion.modelo, "no existe") == []


def test_carga_trapezoidal_parcial_y_global():
    doc = documento_ejemplo()
    m = doc.modelo
    m["cargas_barra"] = [
        {"caso": 1, "barra": 2, "tipo": "trapezoidal", "ejes": "global",
         "a": 1.0, "b": 4.0, "qx1": 0.0, "qy1": -5.0, "qx2": 0.0, "qy2": -20.0},
        {"caso": 1, "barra": 2, "tipo": "termica", "ejes": "local", "alfa": 1e-5, "dt": 10.0},
    ]  # fmt: skip
    e = escena3d.geometria(m)
    flechas = escena3d.cargas(e, m, "D")
    assert flechas[0].punta[0] == pytest.approx(1.0)
    assert flechas[-1].punta[0] == pytest.approx(4.0)
    assert flechas[0].valor == pytest.approx(5.0)
    assert flechas[-1].valor == pytest.approx(20.0)


def test_diagrama_de_momento_a_escala(sesion):
    res = sesion.resultado()
    e = escena3d.armar(sesion.modelo, res, sesion.indices, "M", sesion.combinacion)
    d = res.diagrama(sesion.indices.barras[2])
    maximo = max(float(np.abs(res.diagrama(k)["M"]).max()) for k in sesion.indices.barras.values())
    assert e.escala_diagrama == pytest.approx(escena3d.ALTURA_DIAGRAMA * 6.0 / maximo)
    # En la viga, M positivo se dibuja del lado -y local (abajo): el borde baja M·escala.
    (positivo,) = [r for r in e.rellenos if r.barra == 2 and r.signo == 1]
    caida = positivo.eje[:, 2] - positivo.borde[:, 2]
    assert caida.max() == pytest.approx(d["M"].max() * e.escala_diagrama)
    valores = [round(t.valor, 6) for t in e.etiquetas]
    assert round(float(d["M"].max()), 6) in valores


def test_deformada_pasa_por_los_desplazamientos_de_los_nudos(sesion):
    res = sesion.resultado()
    e = escena3d.armar(sesion.modelo, res, sesion.indices, "D", sesion.combinacion)
    assert e.amplificacion > 0
    nudos = {n["id"]: n for n in sesion.modelo["nudos"]}
    for b, curva in zip(e.barras, e.deformada, strict=True):
        for extremo, punto in ((b.j, curva[-1]), (b.i, curva[0])):
            ux, uy, _ = res.desplazamientos[sesion.indices.nudos[extremo]]
            n = nudos[extremo]
            esperado = [n["x"] + ux * e.amplificacion, 0.0, n["y"] + uy * e.amplificacion]
            np.testing.assert_allclose(punto, esperado, atol=1e-9)


def test_sin_resultados_solo_geometria_y_cargas(sesion):
    e = escena3d.armar(sesion.modelo, None, None, "M", "D")
    assert e.cargas and not e.rellenos and not e.deformada
    assert all(b.indice is None for b in e.barras)


# --- Dibujo con PyVista, sin pantalla ---------------------------------------------------
def _hay_opengl() -> str | None:
    try:
        import pyvista  # noqa: F401
    except ImportError:
        return "falta PyVista (pip install nervi[visor3d])"
    prueba = (
        "import pyvista as pv; p = pv.Plotter(off_screen=True, window_size=[64, 64]);"
        "p.add_mesh(pv.Sphere()); p.screenshot(); p.close()"
    )
    r = subprocess.run([sys.executable, "-c", prueba], capture_output=True, timeout=120)
    return None if r.returncode == 0 else "VTK no puede renderizar sin pantalla (falta OpenGL)"


@pytest.fixture(scope="module")
def pv():
    motivo = _hay_opengl()
    if motivo is not None:
        if os.environ.get("NERVI_EXIGIR_3D"):
            pytest.fail(motivo)
        pytest.skip(motivo)
    import pyvista

    return pyvista


def _hex(color: str) -> np.ndarray:
    return np.array([int(color[k : k + 2], 16) for k in (1, 3, 5)])


def test_capturar_portico_con_diagrama(pv, sesion, tmp_path):
    from PIL import Image

    from nervi.gui import estilo, vista3d

    ruta = vista3d.capturar(
        sesion.modelo,
        tmp_path / "momento.png",
        sesion.resultado(),
        sesion.indices,
        "M",
        sesion.combinacion,
        tamano=(600, 400),
    )
    img = np.asarray(Image.open(ruta).convert("RGB")).astype(int)
    assert img.shape == (400, 600, 3)

    def pixeles(color: str) -> int:
        return int((np.abs(img - _hex(color)).sum(axis=2) < 40).sum())

    assert pixeles(estilo.PANEL) > 0.5 * 600 * 400  # fondo
    assert pixeles(estilo.POSITIVO) > 20  # borde del diagrama positivo
    assert pixeles(estilo.NEGATIVO) > 20
    assert pixeles(vista3d.COLOR_CARGA) > 20  # flechas de carga


def test_clic_sobre_una_barra_la_elige(pv, sesion):
    from nervi.gui import vista3d

    e = escena3d.armar(sesion.modelo, sesion.resultado(), sesion.indices, "M")
    p = pv.Plotter(off_screen=True, window_size=[600, 400])
    try:
        actores = vista3d.dibujar(p, e, Seleccion("barra", 2))
        vista3d.encuadrar(p, e, "frente")
        p.render()
        assert vista3d.barra_en(p, actores, *vista3d.a_pantalla(p, (3.0, 0.0, 3.0))) == 2
        assert vista3d.barra_en(p, actores, *vista3d.a_pantalla(p, (0.0, 0.0, 1.5))) == 1
        assert vista3d.barra_en(p, actores, *vista3d.a_pantalla(p, (3.0, 0.0, 1.0))) is None
    finally:
        p.close()


# --- Ventana --------------------------------------------------------------------------
def test_ventana_sin_visor_3d_avisa(qtbot, monkeypatch):
    from nervi.gui import vista3d
    from nervi.gui.ventana import Ventana

    monkeypatch.setenv("NERVI_SIN_3D", "1")
    v = Ventana(Sesion(documento_ejemplo()))
    qtbot.addWidget(v)
    v.mostrar_vista("3D")
    assert isinstance(v.vista3d, vista3d.SinVisor3D)
    assert v.vistas.currentWidget() is v.vista3d
    v.mostrar_vista("2D")
    assert v.vistas.currentWidget() is v.vista
    v.sesion.modificado = False


def test_ventana_con_visor_3d(pv, qtbot):
    from nervi.gui.ventana import Ventana
    from nervi.gui.vista3d import Vista3D

    v = Ventana(Sesion(documento_ejemplo()))
    qtbot.addWidget(v)
    v.calcular()
    v.mostrar_vista("3D")
    w = v.vista3d
    assert isinstance(w, Vista3D)
    assert w.escena.escala_diagrama > 0
    v.elegir_diagrama("D")
    assert v.vista.diagrama == w.diagrama == "D"
    assert w.escena.amplificacion > 0
    w.b_cargas.setChecked(False)
    assert not w.escena.cargas
    # Editar el modelo actualiza la escena: los resultados quedan desactualizados.
    m = v.sesion.copia_modelo()
    m["nudos"][1]["y"] = 3.5
    v.sesion.editar(m)
    assert w.escena.nudos[2][2] == pytest.approx(3.5)
    assert not w.escena.deformada
    v.sesion.modificado = False
    v.close()


def test_documento_de_ejemplo_valido():
    formato.validar(documento_ejemplo().modelo)


def test_comprobacion_del_ejecutable(pv, tmp_path):
    """``nervi-gui --comprobar-visor3d img.png``: la prueba que corre el workflow de
    publicación sobre el ejecutable empaquetado."""
    from nervi.gui.app import main

    ruta = tmp_path / "visor.png"
    assert main(["nervi-gui", "--comprobar-visor3d", str(ruta)]) == 0
    assert ruta.stat().st_size > 0


# --- Visor único: navegación propia, brújula y paso entre Frente y 3D -----------------
def test_la_camara_de_nervi_llega_a_vtk(pv, sesion):
    from nervi.gui import camara3d, vista3d

    e = escena3d.armar(sesion.modelo, sesion.resultado(), sesion.indices, "M")
    p = pv.Plotter(off_screen=True, window_size=[800, 500])
    try:
        vista3d.dibujar(p, e, paso_grilla=1.0, ejes=False)
        c = camara3d.Camara3D(-30.0, 25.0, (3.0, 0.0, 1.5), 50.0)
        vista3d.poner_camara(p, c, 500)
        p.render()
        for punto in ((0.0, 0.0, 0.0), (6.0, 0.0, 3.0)):
            x, y = vista3d.a_pantalla(p, punto)
            esperado = c.a_pantalla(punto, 800, 500)
            assert (x, 500 - y) == pytest.approx(esperado, abs=1.0)
    finally:
        p.close()


def test_encuadre_incluye_diagramas_y_cargas(sesion):
    from nervi.gui import vista3d

    e = escena3d.armar(sesion.modelo, sesion.resultado(), sesion.indices, "M", "1.4D")
    puntos = vista3d.puntos_visibles(e)
    assert len(puntos) > len(e.nudos)
    assert puntos[:, 2].max() > max(n[2] for n in e.nudos.values())  # colas de las flechas


@pytest.fixture
def ventana_3d(pv, qtbot, monkeypatch):
    from nervi.gui import ajustes
    from nervi.gui.ventana import Ventana
    from nervi.gui.vista3d import Vista3D

    monkeypatch.setattr(ajustes, "ARCHIVO", os.devnull)
    monkeypatch.setattr(Vista3D, "DURACION_MS", 0)
    v = Ventana(Sesion(documento_ejemplo()))
    qtbot.addWidget(v)
    v.resize(1400, 900)
    v.show()
    v.calcular()
    yield v
    v.sesion.modificado = False
    v.close()


def test_frente_y_3d_son_un_mismo_visor(ventana_3d):
    from nervi.gui.vista3d import Vista3D

    v = ventana_3d
    assert v.vista_visible() == "frente" and v.vista.brujula.isVisible()
    assert not v.grupo_proyeccion.isVisible()
    v.mostrar_vista("3d")
    w = v.vista3d
    assert isinstance(w, Vista3D) and v.vistas.currentWidget() is w
    assert v.vista_visible() == "3d" and v.grupo_proyeccion.isVisible()
    assert w.camara.acimut == pytest.approx(-32.0)  # isométrica
    v.mostrar_vista("frente")
    assert v.vistas.currentWidget() is v.vista
    # La cámara 3D terminó exactamente donde mira la vista de frente.
    vf = v.vista.vista_actual()
    assert w.camara.es_frente()
    assert w.camara.escala == pytest.approx(vf.escala)
    assert w.camara.centro == pytest.approx((vf.cx, 0.0, vf.cy))
    # Los nombres de antes siguen andando.
    v.mostrar_vista("3D")
    assert v.vista_visible() == "3d"
    v.mostrar_vista("2D")
    assert v.vista_visible() == "frente"


def test_arrastre_derecho_en_frente_pasa_a_3d_y_gira(ventana_3d, qtbot):
    from PySide6.QtCore import QPointF

    v = ventana_3d
    t = v.vista.transformacion()
    inicio = t.a_pantalla(3.0, 3.0)
    v.vista.giro_pedido.emit(inicio, 3.0, 3.0)
    w = v.vista3d
    assert v.vistas.currentWidget() is w
    assert w.camara.es_frente()
    antes = w.camara.a_pantalla((3.0, 0.0, 3.0), *w._tamano())
    v.vista.giro_arrastre.emit(30.0, 10.0)
    assert w.camara.acimut == pytest.approx(-12.0)
    assert w.camara.elevacion == pytest.approx(4.0)
    # El punto donde empezó el arrastre (sobre la viga) es el centro de giro.
    assert w.camara.a_pantalla((3.0, 0.0, 3.0), *w._tamano()) == pytest.approx(antes)
    assert w._pivote is not None
    v.vista.giro_terminado.emit()
    assert w._pivote is None and w._arrastre is None
    assert isinstance(inicio, QPointF)


def test_vista2d_arrastre_derecho_emite_giro_y_clic_cancela(qtbot):
    from PySide6.QtCore import QPoint, Qt

    from nervi.gui.vista2d import Vista2D

    s = Sesion(documento_ejemplo())
    w = Vista2D(s)
    qtbot.addWidget(w)
    w.resize(800, 500)
    w.show()
    pedidos, arrastres, fines = [], [], []
    w.giro_pedido.connect(lambda p, x, y: pedidos.append((x, y)))
    w.giro_arrastre.connect(lambda dx, dy: arrastres.append((dx, dy)))
    w.giro_terminado.connect(lambda: fines.append(True))
    q = w.transformacion().a_pantalla(3.0, 3.0).toPoint()
    # Clic derecho sin mover: no gira y termina el trazo de la herramienta.
    w.dibujo.elegir("barra")
    a = w.transformacion().a_pantalla(0.0, 0.0)
    w.dibujo.mover(a)
    w.dibujo.presionar(a)
    w.dibujo.soltar(a)
    assert w.dibujo.puntos
    qtbot.mouseClick(w, Qt.RightButton, pos=q)
    assert not pedidos and not fines
    assert not w.dibujo.puntos
    # Arrastre: pide el giro una vez, con el punto del modelo donde empezó.
    qtbot.mousePress(w, Qt.RightButton, pos=q)
    qtbot.mouseMove(w, q + QPoint(20, 5))
    qtbot.mouseMove(w, q + QPoint(30, 5))
    qtbot.mouseRelease(w, Qt.RightButton, pos=q + QPoint(30, 5))
    assert len(pedidos) == 1 and pedidos[0] == pytest.approx((3.0, 3.0), abs=0.05)
    assert sum(d[0] for d in arrastres) == pytest.approx(30.0)
    assert fines == [True]


def test_brujula_pide_la_vista_del_eje(ventana_3d):
    from PySide6.QtCore import QPointF

    from nervi.gui import brujula

    v = ventana_3d
    b = v.vista.brujula
    centro = QPointF(brujula.LADO / 2, brujula.LADO / 2)
    puntos = {clave: q for _p, clave, q in brujula.extremos(b.camara, centro)}
    # De frente, +Z queda arriba del centro y +X a la derecha.
    assert puntos["+Z"].y() < centro.y() and puntos["+X"].x() > centro.x()
    assert b.extremo_en(puntos["+Z"]) == "+Z"
    assert b.extremo_en(centro + QPointF(0, brujula.LADO)) is None
    b.vista_pedida.emit("+Z")  # en planta: pasa a la vista 3D desde arriba
    w = v.vista3d
    assert v.vista_visible() == "3d"
    assert w.camara.elevacion == pytest.approx(90.0)
    w.brujula.vista_pedida.emit("-Y")  # de frente: vuelve a la vista plana
    assert v.vista_visible() == "frente" and v.vistas.currentWidget() is v.vista


def test_rueda_acerca_hacia_el_cursor_y_f_encuadra(ventana_3d, qtbot):
    from PySide6.QtCore import QPointF

    v = ventana_3d
    v.mostrar_vista("3d")
    w = v.vista3d
    tam = w._tamano()
    cursor = QPointF(tam[0] * 0.7, tam[1] * 0.3)
    p = w.camara.en_plano(cursor.x(), cursor.y(), *tam)
    escala = w.camara.escala
    w.zoom(1.2, cursor)
    assert w.camara.escala == pytest.approx(escala * 1.2)
    assert w.camara.a_pantalla(p, *tam) == pytest.approx((cursor.x(), cursor.y()))
    w.encuadrar()
    assert w.camara.escala == pytest.approx(escala)
    v.elegir_proyeccion("perspectiva")
    assert w.camara.perspectiva and w.perspectiva
    assert not w.plotter.renderer.GetActiveCamera().GetParallelProjection()
