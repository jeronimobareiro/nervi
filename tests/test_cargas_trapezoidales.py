# SPDX-License-Identifier: GPL-3.0-or-later
"""Cargas trapezoidales y parciales desde Python (issue #2).

Soluciones cerradas: Roark's Formulas for Stress and Strain, 8.ª ed., tabla 8.1.
"""

import math

import numpy as np
import pytest

import nervi

E, A, I = 2.0e8, 0.01, 1.0e-4


def viga(largo: float) -> nervi.Modelo:
    m = nervi.Modelo()
    m.agregar_nudo(0, 0)
    m.agregar_nudo(largo, 0)
    m.agregar_barra(0, 1, E, A, I)
    return m


def test_triangular_biapoyada_con_b_hasta_el_nudo_j():
    # R_A = wL/6, R_B = wL/3, M_máx = wL²/(9√3) en x = L/√3.
    largo, w = 6.0, 12.0
    m = viga(largo)
    m.apoyar(0, rz=False)
    m.apoyar(1, ux=False, rz=False)
    m.carga_trapezoidal("tri", 0, qy1=0.0, qy2=-w)
    r = m.resolver()["tri"]
    assert r.reacciones[0, 1] == pytest.approx(w * largo / 6, rel=1e-9)
    assert r.reacciones[1, 1] == pytest.approx(w * largo / 3, rel=1e-9)
    d = r.diagrama(0)
    assert d["M"].max() == pytest.approx(w * largo**2 / (9 * math.sqrt(3)), rel=1e-9)
    assert d["x"][np.argmax(d["M"])] == pytest.approx(largo / math.sqrt(3), rel=1e-9)


def test_carga_parcial_en_voladizo():
    # Empotrado en x = 0, w en [a, L]: δ_punta = w(3L⁴ - 4a³L + a⁴)/24EI.
    largo, w, a = 4.0, 8.0, 1.5
    m = viga(largo)
    m.apoyar(0)
    m.carga_parcial("p", 0, a, largo, qy=-w)
    r = m.resolver()["p"]
    esperado = -w * (3 * largo**4 - 4 * a**3 * largo + a**4) / (24 * E * I)
    assert r.desplazamientos[1, 1] == pytest.approx(esperado, rel=1e-9)
    # El diagrama tiene estación en el inicio de la carga.
    assert np.any(np.isclose(r.diagrama(0)["x"], a))


def test_trapezoidal_constante_igual_a_uniforme():
    largo = 5.0
    resultados = []
    for usar_trapezoidal in (False, True):
        m = viga(largo)
        m.apoyar(0)
        m.apoyar(1, ux=False, rz=False)
        if usar_trapezoidal:
            m.carga_trapezoidal("q", 0, qy1=-3, qy2=-3, qx1=1, qx2=1)
        else:
            m.carga_uniforme("q", 0, qx=1, qy=-3)
        resultados.append(m.resolver()["q"])
    u, t = resultados
    np.testing.assert_allclose(t.reacciones, u.reacciones, rtol=1e-9, atol=1e-9)
    np.testing.assert_allclose(t.desplazamientos, u.desplazamientos, rtol=1e-9, atol=1e-15)
    np.testing.assert_allclose(t.diagrama(0)["M"], u.diagrama(0)["M"], rtol=1e-9, atol=1e-9)


def test_tramo_fuera_de_la_barra_se_rechaza():
    m = viga(3.0)
    m.apoyar(0)
    m.carga_parcial("p", 0, 1.0, 4.0, qy=-1)
    with pytest.raises(ValueError, match="trapezoidal"):
        m.resolver()


def test_contrato_tiene_diez_columnas():
    m = viga(3.0)
    m.apoyar(0)
    m.carga_puntual("p", 0, 1.0, py=-1)
    m.carga_trapezoidal("p", 0, qy1=-1)
    arr = m.arreglos()
    assert arr["cargas_barra"].shape == (2, 10)
    assert arr["cargas_barra"][1, 7] == pytest.approx(3.0)
    assert nervi._core.VERSION_CONTRATO == 2
