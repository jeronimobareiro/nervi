# SPDX-License-Identifier: GPL-3.0-or-later
"""Brazos rígidos (issue #13) y diafragma rígido de piso (issue #14) desde Python.

Soluciones cerradas: voladizo con brazo rígido en el empotramiento,
``δ = P Lf³ / (3 EI)`` con ``Lf`` la parte flexible, momento ``P Lf`` en la cara
y ``P L`` en el nudo; piso con columnas en voladizo (``k = 3 EI/h³``) unidas por
un diafragma: traslación ``F / Σk`` y modos ``ω² = Σk / M`` y ``Kθ / J``
(Chopra, *Dynamics of Structures*, 4.ª ed., cap. 9).
"""

import math

import numpy as np
import pytest

import nervi
from nervi import _core

E, G = 2.5e7, 1.0e7


def test_brazo_como_longitud_o_vector_y_voladizo_cerrado():
    L, a, P, Iz = 4.0, 0.5, 10.0, 3.0e-3
    resultados = []
    for brazo in (a, (a, 0.0, 0.0)):
        m = nervi.Modelo3D()
        n0, n1 = m.agregar_nudo(0, 0, 0), m.agregar_nudo(L, 0, 0)
        m.agregar_barra(n0, n1, E, G, A=0.12, Iy=2e-3, Iz=Iz, J=1e-3, brazo_i=brazo)
        m.apoyar(n0)
        m.carga_nodal("P", n1, fz=-P)
        resultados.append(m.resolver()["P"])
    Lf = L - a
    for r in resultados:
        assert r.desplazamientos[1, 2] == pytest.approx(-P * Lf**3 / (3 * E * Iz), rel=1e-12)
        assert r.reacciones[0, 4] == pytest.approx(-P * L, rel=1e-12)
        assert abs(r.fuerzas_extremo[0, 5]) == pytest.approx(P * Lf, rel=1e-12)
        assert r.diagrama(0)["x"][-1] == pytest.approx(Lf)
    np.testing.assert_allclose(resultados[0].desplazamientos, resultados[1].desplazamientos)


def test_brazo_en_el_extremo_j_y_trapezoidal_hasta_la_cara():
    # Viga biempotrada de 6 m con brazos de 0.3 m (media columna) y carga
    # trapezoidal sin b: llega hasta la cara, así que la carga total es q·Lf.
    m = nervi.Modelo3D()
    a, b = m.agregar_nudo(0, 0, 0), m.agregar_nudo(6, 0, 0)
    m.agregar_barra(a, b, E, G, A=0.12, Iy=2e-3, Iz=3e-3, J=1e-3, brazo_i=0.3, brazo_j=0.3)
    m.apoyar(a)
    m.apoyar(b)
    m.carga_trapezoidal("q", 0, q1=(0, 0, -5), q2=(0, 0, -5), ejes="global")
    r = m.resolver()["q"]
    assert r.reacciones[:, 2].sum() == pytest.approx(5 * 5.4, rel=1e-12)
    # Momento de empotramiento en la cara q Lf²/12, en el nudo más el brazo.
    assert abs(r.fuerzas_extremo[0, 5]) == pytest.approx(5 * 5.4**2 / 12, rel=1e-10)
    assert abs(r.reacciones[0, 4]) == pytest.approx(5 * 5.4**2 / 12 + 5 * 5.4 / 2 * 0.3, rel=1e-10)
    arr = m.arreglos()
    np.testing.assert_allclose(arr["brazos"][0], [0.3, 0, 0, -0.3, 0, 0])


def piso(masa: float = 0.0):
    """Planta de 6 m por 4 m con cuatro columnas en voladizo de 3.5 m unidas solo
    por el diafragma."""
    h, I0 = 3.5, 1.0e-3
    m = nervi.Modelo3D()
    topes = []
    for x, y in ((0, 0), (6, 0), (0, 4), (6, 4)):
        a, b = m.agregar_nudo(x, y, 0), m.agregar_nudo(x, y, h)
        m.apoyar(a)
        m.agregar_barra(a, b, E, G, A=0.16, Iy=2 * I0, Iz=I0, J=1.5e-3)
        topes.append(b)
        if masa:
            m.masa_nodal(b, mx=masa, my=masa, mz=0.0)
    maestro = m.diafragma(topes)
    k = 3 * E * I0 / h**3  # en X la columna flexiona con Iz
    return m, topes, maestro, k, h


def test_diafragma_crea_el_maestro_y_reparte_la_carga():
    m, topes, maestro, k, h = piso()
    assert maestro == 8
    np.testing.assert_allclose(m.arreglos()["coords"][maestro], [3, 2, h])
    assert m.diafragmas == [(maestro, topes)]
    m.carga_nodal("F", maestro, fx=100.0)
    res = m.resolver()
    r = res["F"]
    # Carga en el centro de rigidez: el piso se traslada sin girar.
    assert r.desplazamientos[maestro, 0] == pytest.approx(100.0 / (4 * k), rel=1e-10)
    assert abs(r.desplazamientos[maestro, 5]) < 1e-14
    np.testing.assert_allclose(r.desplazamientos[topes, 0], 100.0 / (4 * k), rtol=1e-10)
    np.testing.assert_allclose(r.reacciones[::2][:4, 0], -25.0, rtol=1e-10)
    assert res.gdl_sin_rigidez == []
    d = res.derivas("F")
    assert d["maestro"].tolist() == [maestro]
    assert d["deriva_x"][0] == pytest.approx(r.desplazamientos[maestro, 0] / h, rel=1e-14)


def test_derivas_de_dos_pisos_y_espectro():
    h = 3.0
    m = nervi.Modelo3D()
    abajo = [m.agregar_nudo(x, y, 0) for x, y in ((0, 0), (5, 0), (0, 5), (5, 5))]
    for n in abajo:
        m.apoyar(n)
    maestros = []
    for piso_ in (1, 2):
        arriba = [m.agregar_nudo(x, y, piso_ * h) for x, y in ((0, 0), (5, 0), (0, 5), (5, 5))]
        for a, b in zip(abajo, arriba, strict=True):
            m.agregar_barra(a, b, E, G, A=0.16, Iy=2e-3, Iz=2e-3, J=3e-3)
        for k in range(4):
            m.masa_nodal(arriba[k], mx=5.0, my=5.0, mz=0.0)
        maestros.append(m.diafragma(arriba))
        abajo = arriba
    m.carga_nodal("V", maestros[0], fx=30.0)
    m.carga_nodal("V", maestros[1], fx=60.0)
    r = m.resolver()
    d = r.derivas("V")
    u = r["V"].desplazamientos[maestros, 0]
    np.testing.assert_allclose(d["z"], [h, 2 * h])
    np.testing.assert_allclose(d["deriva_x"], [u[0] / h, (u[1] - u[0]) / h], rtol=1e-14)
    np.testing.assert_allclose(d["ux"], u)

    modal = m.modal(n_modos=6)
    assert len(modal.diafragmas) == 2
    for dia in modal.diafragmas:
        assert dia["masa"][0] == pytest.approx(20.0)
        np.testing.assert_allclose(dia["centro_masa"], [2.5, 2.5], atol=1e-12)
        assert dia["inercia"] == pytest.approx(20.0 * 2 * 2.5**2, rel=1e-12)
    assert modal.masa_total[0] == pytest.approx(40.0)
    assert modal.masa_participante_acumulada[-1, 0] == pytest.approx(1.0)
    esp = modal.espectro([(0.0, 4.0), (2.0, 4.0)], direccion="X", combinacion="SRSS")
    de = esp.derivas()
    # La deriva combinada es la combinación de las derivas de cada modo, no la
    # diferencia de los desplazamientos combinados.
    escala = esp.factores * esp.aceleraciones / modal.omegas**2
    um = modal.modos[:, maestros, 0] * escala[:, None]
    dm = np.diff(np.concatenate([np.zeros((um.shape[0], 1)), um], axis=1), axis=1) / h
    np.testing.assert_allclose(de["deriva_x"], np.sqrt((dm**2).sum(axis=0)), rtol=1e-12)
    np.testing.assert_allclose(de["ux"], esp.desplazamientos[maestros, 0], rtol=1e-10)
    assert 0 < esp.cortante_basal[0] <= 40.0 * 4.0


def test_modos_del_piso():
    M = 15.0
    m, _, _, k, h = piso(masa=M)
    modal = m.modal(n_modos=3)
    ky = 2 * k
    j = 4 * M * (3**2 + 2**2)
    kt = 4 * (k * 2**2 + ky * 3**2) + 4 * G * 1.5e-3 / h
    esperadas = sorted([4 * k / (4 * M), 4 * ky / (4 * M), kt / j])
    np.testing.assert_allclose(modal.omegas**2, esperadas, rtol=1e-9)
    assert modal.n_gdl_masa == 3


def test_errores():
    m, topes, maestro, k, _ = piso()
    with pytest.raises(ValueError, match="uno solo"):
        m.diafragma([topes[0], topes[1]])
        m.arreglos()
    m, topes, maestro, k, _ = piso()
    m.apoyar(topes[0], uz=False, rx=False, ry=False, rz=False)
    m.carga_nodal("F", maestro, fx=1.0)
    with pytest.raises(ValueError, match="maestro"):
        m.resolver()
    with pytest.raises(ValueError, match="negativo"):
        nervi.Modelo3D().agregar_barra(0, 1, E, G, 1, 1, 1, 1, brazo_i=-0.2)
    sin = nervi.Modelo3D()
    a, b = sin.agregar_nudo(0, 0, 0), sin.agregar_nudo(0, 0, 3)
    sin.agregar_barra(a, b, E, G, 0.16, 1e-3, 1e-3, 1e-3)
    sin.apoyar(a)
    sin.carga_nodal("F", b, fx=1.0)
    with pytest.raises(ValueError, match="diafragmas"):
        sin.resolver().derivas("F")
    assert _core.VERSION_CONTRATO_3D == 2
    assert _core.VERSION_CONTRATO_DINAMICA == 2
    assert math.isfinite(k)
