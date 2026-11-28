# SPDX-License-Identifier: GPL-3.0-or-later
"""Cámara del visor único (giro tipo plato con Z arriba), sin VTK ni Qt."""

import numpy as np
import pytest

from nervi.gui.camara3d import (
    EXTREMOS,
    VISTAS,
    Camara3D,
    encuadre,
    interpolar,
)

W, H = 800.0, 500.0


def _ortonormal(c: Camara3D) -> None:
    d, u, n = c.ejes()
    m = np.vstack([d, u, n])
    np.testing.assert_allclose(m @ m.T, np.eye(3), atol=1e-12)


def test_de_frente_es_la_vista_2d():
    """De frente: X a la derecha, Z arriba, como la vista 2D (``(x, y)`` -> ``(x, 0, y)``)."""
    c = Camara3D.de_frente(50.0, 3.0, 1.5)
    assert c.es_frente()
    assert c.a_pantalla((3.0, 0.0, 1.5), W, H) == pytest.approx((W / 2, H / 2))
    # Un metro a la derecha y uno arriba en el modelo: 50 px a la derecha y 50 arriba.
    assert c.a_pantalla((4.0, 0.0, 2.5), W, H) == pytest.approx((W / 2 + 50, H / 2 - 50))
    # La profundidad (Y) no cambia el píxel en la vista paralela.
    assert c.a_pantalla((4.0, 7.0, 2.5), W, H) == pytest.approx((W / 2 + 50, H / 2 - 50))


@pytest.mark.parametrize("vista", list(VISTAS) + list(EXTREMOS))
def test_ejes_ortonormales_y_sin_rolido(vista):
    az, el = VISTAS[vista] if vista in VISTAS else EXTREMOS[vista]
    c = Camara3D(az, el, (0, 0, 0), 1.0)
    _ortonormal(c)
    d, u, _ = c.ejes()
    assert d[2] == 0.0  # la horizontal de la pantalla es horizontal en el modelo
    assert u[2] >= -1e-15  # Z nunca queda hacia abajo


def test_extremos_de_la_brujula_miran_desde_su_lado():
    for clave, (az, el) in EXTREMOS.items():
        _, _, n = Camara3D(az, el, (0, 0, 0), 1.0).ejes()
        eje = np.zeros(3)
        eje["XYZ".index(clave[1])] = 1.0 if clave[0] == "+" else -1.0
        np.testing.assert_allclose(n, eje, atol=1e-12)


def test_girar_deja_el_pivote_en_su_lugar():
    c = Camara3D(-30.0, 20.0, (3.0, 0.0, 1.5), 60.0)
    pivote = (5.0, 0.4, 3.0)
    antes = c.a_pantalla(pivote, W, H)
    g = c.girar(37.0, -12.0, pivote)
    assert g.a_pantalla(pivote, W, H) == pytest.approx(antes, abs=1e-9)
    assert g.acimut == pytest.approx(-30.0 - 37.0 * 0.4)
    assert g.elevacion == pytest.approx(20.0 - 12.0 * 0.4)
    assert g.escala == c.escala


def test_girar_hacia_la_derecha_lleva_el_frente_a_la_derecha():
    """El modelo sigue al mouse: lo que está adelante va hacia donde se arrastra."""
    c = Camara3D.de_frente(50.0, 0.0, 0.0)
    adelante = (0.0, -1.0, 0.0)
    x0, _ = c.a_pantalla(adelante, W, H)
    x1, _ = c.girar(20.0, 0.0).a_pantalla(adelante, W, H)
    assert x1 > x0
    # Arrastrar hacia abajo muestra el modelo más desde arriba.
    assert c.girar(0.0, 30.0).elevacion > 0


def test_la_elevacion_se_detiene_en_planta():
    c = Camara3D(0.0, 80.0, (0, 0, 0), 1.0).girar(0.0, 1000.0)
    assert c.elevacion == 90.0
    _ortonormal(c)
    assert Camara3D(0.0, -80.0, (0, 0, 0), 1.0).girar(0.0, -1000.0).elevacion == -90.0


def test_acercar_deja_fijo_el_punto_bajo_el_cursor():
    c = Camara3D(-30.0, 25.0, (1.0, 2.0, 3.0), 40.0)
    x, y = 610.0, 120.0
    p = c.en_plano(x, y, W, H)
    z = c.acercar(1.2**3, x, y, W, H)
    assert z.escala == pytest.approx(40.0 * 1.2**3)
    assert z.a_pantalla(p, W, H) == pytest.approx((x, y))


def test_desplazar_sigue_al_mouse():
    c = Camara3D(-30.0, 25.0, (1.0, 2.0, 3.0), 40.0)
    p = (2.0, 0.5, 1.0)
    x, y = c.a_pantalla(p, W, H)
    assert c.desplazar(15.0, -7.0).a_pantalla(p, W, H) == pytest.approx((x + 15.0, y - 7.0))


def test_encuadre_muestra_todos_los_puntos():
    puntos = np.array([[0, 0, 0], [6, 0, 0], [6, 5, 3], [0, 5, 6.0]])
    for vista in VISTAS:
        c = encuadre(puntos, W, H, vista, margen=0.1)
        px = np.array([c.a_pantalla(p, W, H) for p in puntos])
        assert px[:, 0].min() >= 0.1 * W - 1e-6 and px[:, 0].max() <= 0.9 * W + 1e-6
        assert px[:, 1].min() >= 0.1 * H - 1e-6 and px[:, 1].max() <= 0.9 * H + 1e-6
        # Centrado en el lado que manda.
        medio = (px.min(axis=0) + px.max(axis=0)) / 2
        assert medio == pytest.approx((W / 2, H / 2))


def test_interpolar_va_por_el_camino_corto():
    a = Camara3D(170.0, 0.0, (0, 0, 0), 10.0)
    b = Camara3D(-170.0, 40.0, (2, 0, 0), 40.0)
    assert interpolar(a, b, 0.0) == a
    fin = interpolar(a, b, 1.0)
    assert fin.acimut == pytest.approx(-170.0)
    assert fin.elevacion == pytest.approx(40.0)
    assert fin.escala == pytest.approx(40.0)
    medio = interpolar(a, b, 0.5)
    assert abs(medio.acimut) == pytest.approx(180.0)  # cruzó por 180°, no por 0°
    assert medio.escala == pytest.approx(20.0)  # proporción geométrica


def test_a_vtk_perspectiva_y_paralela():
    c = Camara3D(0.0, 0.0, (1.0, 0.0, 2.0), 50.0)
    p = c.a_vtk(500.0)
    assert p["parallel_projection"] is True
    assert p["parallel_scale"] == pytest.approx(5.0)
    np.testing.assert_allclose(p["up"], [0, 0, 1], atol=1e-12)
    pos = np.array(p["position"])
    assert pos[1] < 0 and pos[0] == pytest.approx(1.0) and pos[2] == pytest.approx(2.0)
    from dataclasses import replace

    assert replace(c, perspectiva=True).a_vtk(500.0)["parallel_projection"] is False
