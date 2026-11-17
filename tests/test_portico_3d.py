# SPDX-License-Identifier: GPL-3.0-or-later
"""Pórtico espacial desde Python (issues #11 y #12): API, contrato de datos y
comparación con soluciones cerradas y con el motor plano."""

import math

import numpy as np
import pytest

import nervi
from nervi import _core, secciones

E, G = 2.0e8, 7.7e7
SEC = {"A": 0.012, "Iy": 4.0e-5, "Iz": 1.5e-4, "J": 6.0e-6}


def cerca(calc, esperado, escala=None, tol=1e-9):
    escala = abs(esperado) if escala is None else escala
    assert abs(calc - esperado) <= tol * max(escala, 1e-300), (calc, esperado)


def test_voladizo_con_carga_en_dos_planos_y_torsion():
    # Voladizo sobre X; con los ejes por defecto y = +Z, z = -Y.
    L, py, pz, t = 3.0, -10.0, 4.0, 2.5
    m = nervi.Modelo3D()
    a, b = m.agregar_nudo(0, 0, 0), m.agregar_nudo(L, 0, 0)
    m.agregar_barra(a, b, E, G, seccion=SEC)
    m.apoyar(a)
    # Carga local (py, pz, T) en globales: y local = +Z, z local = -Y.
    m.carga_nodal("P", b, fy=-pz, fz=py, mx=t)
    r = m.resolver()
    d = r["P"].desplazamientos[b]
    cerca(d[2], py * L**3 / (3 * E * SEC["Iz"]))
    cerca(-d[1], pz * L**3 / (3 * E * SEC["Iy"]))
    cerca(d[3], t * L / (G * SEC["J"]))
    np.testing.assert_allclose(r.ejes[0], [[1, 0, 0], [0, 0, 1], [0, -1, 0]], atol=1e-15)
    dg = r["P"].diagrama(0)
    np.testing.assert_allclose(dg["Mz"], py * (L - dg["x"]), rtol=1e-9, atol=1e-9)
    np.testing.assert_allclose(dg["My"], -pz * (L - dg["x"]), rtol=1e-9, atol=1e-9)
    np.testing.assert_allclose(dg["T"], t, rtol=1e-9)
    reac = r["P"].reacciones[a]
    np.testing.assert_allclose(reac[:3], [0, pz, -py], atol=1e-9)


def test_portico_en_xz_coincide_con_el_motor_plano():
    # Pórtico biempotrado de una nave con viga articulada; columnas verticales
    # (regla por defecto) y viga de izquierda a derecha: los ejes locales
    # coinciden con los del plano llevado a XZ.
    p2, p3 = nervi.Modelo(), nervi.Modelo3D()
    for x, y in [(0, 0), (0, 4), (6, 4), (6, 0)]:
        p2.agregar_nudo(x, y)
        n = p3.agregar_nudo(x, 0, y)
        p3.apoyar(n, ux=False, uz=False, ry=False)  # fuera del plano: uy, rx, rz
    for i, j, art in [(0, 1, False), (1, 2, True), (3, 2, False)]:
        p2.agregar_barra(i, j, E=E, A=SEC["A"], I=SEC["Iz"], articulada_j=art)
        p3.agregar_barra(i, j, E, G, seccion=SEC, articulada_j=art)
    for n in (0, 3):
        p2.apoyar(n)
        p3.apoyar(n)
    p2.carga_nodal("H", 1, fx=12.0, mz=3.0)
    p3.carga_nodal("H", 1, fx=12.0, my=-3.0)
    p2.carga_uniforme("H", 1, qy=-15.0, ejes="global")
    p3.carga_uniforme("H", 1, qz=-15.0, ejes="global")
    p2.carga_puntual("H", 0, 1.5, px=1.0, py=-7.0)
    p3.carga_puntual("H", 0, 1.5, px=1.0, py=-7.0)
    p2.carga_trapezoidal("H", 2, qy1=-2.0, qy2=5.0, a=0.5, b=3.5)
    p3.carga_trapezoidal("H", 2, q1=(0, -2.0, 0), q2=(0, 5.0, 0), a=0.5, b=3.5)
    r2, r3 = p2.resolver()["H"], p3.resolver()["H"]
    escala = np.abs(r2.desplazamientos).max()
    np.testing.assert_allclose(
        r3.desplazamientos[:, 0], r2.desplazamientos[:, 0], atol=1e-9 * escala
    )
    np.testing.assert_allclose(
        r3.desplazamientos[:, 2], r2.desplazamientos[:, 1], atol=1e-9 * escala
    )
    np.testing.assert_allclose(
        r3.desplazamientos[:, 4], -r2.desplazamientos[:, 2], atol=1e-9 * escala
    )
    fu = np.abs(r2.reacciones).max()
    np.testing.assert_allclose(r3.reacciones[:, [0, 2]], r2.reacciones[:, :2], atol=1e-9 * fu)
    for b in range(3):
        d2, d3 = r2.diagrama(b), r3.diagrama(b)
        np.testing.assert_allclose(d3["x"], d2["x"], atol=1e-12)
        for k2, k3 in (("N", "N"), ("V", "Vy"), ("M", "Mz"), ("v", "v")):
            np.testing.assert_allclose(d3[k3], d2[k2], atol=1e-9 * max(fu, 1.0))


def test_tripode_de_bielas():
    R, h, P = 2.0, 3.0, 60.0
    L = math.hypot(R, h)
    A = 0.004
    m = nervi.Modelo3D()
    d = m.agregar_nudo(0, 0, h)
    for k in range(3):
        ang = 2 * math.pi * k / 3
        n = m.agregar_nudo(R * math.cos(ang), R * math.sin(ang), 0)
        m.apoyar(n, rx=False, ry=False, rz=False)
        m.agregar_biela(n, d, E, A)
    m.carga_nodal("P", d, fz=-P)
    r = m.resolver()
    cerca(r["P"].desplazamientos[d, 2], -P * L**3 / (3 * h * h * E * A))
    for b in range(3):
        np.testing.assert_allclose(r["P"].diagrama(b)["N"], -P * L / (3 * h), rtol=1e-9)
    assert len(r.gdl_sin_rigidez) == 12
    assert {g for _, g in r.gdl_sin_rigidez} == {"rx", "ry", "rz"}


def test_combinar_casos():
    m = nervi.Modelo3D()
    a, b = m.agregar_nudo(0, 0, 0), m.agregar_nudo(0, 0, 3)
    m.agregar_barra(a, b, E, G, seccion=SEC)
    m.apoyar(a)
    m.carga_nodal("D", b, fx=1.0)
    m.carga_nodal("L", b, fy=2.0)
    r = m.resolver()
    c = r.combinar("1.2D+1.6L", {"D": 1.2, "L": 1.6})
    np.testing.assert_allclose(
        c.desplazamientos, 1.2 * r["D"].desplazamientos + 1.6 * r["L"].desplazamientos
    )
    np.testing.assert_allclose(
        c.diagrama(0)["My"], 1.2 * r["D"].diagrama(0)["My"] + 1.6 * r["L"].diagrama(0)["My"]
    )


def test_mecanismo_de_torsion():
    m = nervi.Modelo3D()
    n = [m.agregar_nudo(2.0 * k, 0, 0) for k in range(3)]
    m.agregar_barra(n[0], n[1], E, G, seccion=SEC)
    m.agregar_barra(n[1], n[2], E, G, seccion=SEC)
    m.apoyar(n[0], rx=False, ry=False, rz=False)
    m.apoyar(n[2], ux=False, rx=False, ry=False, rz=False)
    m.carga_nodal("P", n[1], fz=-10.0)
    with pytest.raises(nervi.MecanismoError) as e:
        m.resolver()
    assert e.value.gdl == "rx"


def test_errores_claros():
    m = nervi.Modelo3D()
    a, b = m.agregar_nudo(0, 0, 0), m.agregar_nudo(0, 0, 3)
    m.agregar_barra(a, b, E, G, seccion=SEC, referencia=(0, 0, 2))
    m.apoyar(a)
    m.carga_nodal("P", b, fx=1.0)
    with pytest.raises(ValueError, match="paralelo"):
        m.resolver()
    with pytest.raises(ValueError, match="falta la propiedad"):
        m.agregar_barra(a, b, E, G, A=1.0)
    m2 = nervi.Modelo3D()
    a, b = m2.agregar_nudo(0, 0, 0), m2.agregar_nudo(1, 0, 0)
    m2.agregar_barra(a, b, E, G, seccion=SEC)
    m2.apoyar(a)
    m2.carga_nodal("P", b, fz=-1.0)
    arr = m2.arreglos()
    with pytest.raises(ValueError, match="versión de contrato 3D"):
        _core.resolver_portico_3d(99, **arr)
    malo = dict(arr, coords=arr["coords"][:, :2].copy())
    with pytest.raises(ValueError, match="'coords' tiene forma"):
        _core.resolver_portico_3d(_core.VERSION_CONTRATO_3D, **malo)
    malo = dict(arr, cargas_barra=np.zeros((1, 10)))
    with pytest.raises(ValueError, match="se esperaban 12"):
        _core.resolver_portico_3d(_core.VERSION_CONTRATO_3D, **malo)
    lib = arr["liberaciones"].copy()
    lib[0, [3, 9]] = 1
    with pytest.raises(ValueError, match="T en ambos extremos"):
        _core.resolver_portico_3d(_core.VERSION_CONTRATO_3D, **dict(arr, liberaciones=lib))


def test_secciones():
    s = secciones.rectangular(0.3, 0.5)
    cerca(s["A"], 0.15)
    cerca(s["Iz"], 0.3 * 0.5**3 / 12)
    cerca(s["Iy"], 0.5 * 0.3**3 / 12)
    # Timoshenko y Goodier, §109, tabla: J = k·a·b³ con k = 0.141 (a/b = 1),
    # 0.229 (a/b = 2) y 0.312 (a/b = 10), tabulados con tres cifras.
    for relacion, k in ((1.0, 0.1406), (2.0, 0.229), (10.0, 0.312)):
        cerca(secciones.torsion_rectangular(relacion, 1.0), k * relacion, tol=2e-3)
    # Límite de la sección muy delgada: J → a b³/3 · (1 - 0.630 b/a).
    cerca(secciones.torsion_rectangular(100.0, 1.0), 100 / 3 * (1 - 0.6302 / 100), tol=1e-4)
    c = secciones.circular(0.2)
    cerca(c["J"], math.pi * 0.2**4 / 32)
    t = secciones.tubo_circular(0.2, 0.1)
    assert t == pytest.approx(c)
    with pytest.raises(ValueError):
        secciones.tubo_circular(0.2, 0.15)
    with pytest.raises(ValueError):
        secciones.rectangular(0.0, 1.0)
