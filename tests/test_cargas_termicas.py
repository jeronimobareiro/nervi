# SPDX-License-Identifier: GPL-3.0-or-later
"""Cargas térmicas desde Python (issue #4).

Fuente: Ghali, Neville y Brown, Structural Analysis, 6.ª ed., §4.6 y §6.4.
"""

import pytest

import nervi

E, A, I = 2.0e8, 0.01, 1.0e-4
ALFA, H = 1.2e-5, 0.4


def viga(largo: float) -> nervi.Modelo:
    m = nervi.Modelo()
    m.agregar_nudo(0, 0)
    m.agregar_nudo(largo, 0)
    m.agregar_barra(0, 1, E, A, I)
    return m


def test_biempotrada_con_dt_uniforme():
    m = viga(5.0)
    m.apoyar(0)
    m.apoyar(1)
    m.carga_termica("T", 0, ALFA, dt=30.0)
    d = m.resolver()["T"].diagrama(0)
    assert d["N"] == pytest.approx(-E * A * ALFA * 30.0, rel=1e-9)
    assert abs(d["M"]).max() < 1e-6


def test_biapoyada_con_gradiente_solo_se_curva():
    largo, dg = 6.0, 15.0
    m = viga(largo)
    m.apoyar(0, rz=False)
    m.apoyar(1, ux=False, rz=False)
    m.carga_termica("T", 0, ALFA, gradiente=dg, h=H)
    r = m.resolver()["T"]
    d = r.diagrama(0)
    assert abs(d["M"]).max() < 1e-6
    assert d["v"].min() == pytest.approx(-ALFA * dg * largo**2 / (8 * H), rel=1e-9)


def test_biempotrada_con_gradiente_y_combinacion():
    largo, dg = 4.0, 20.0
    m = viga(largo)
    m.apoyar(0)
    m.apoyar(1)
    m.carga_termica("T", 0, ALFA, gradiente=dg, h=H)
    m.carga_uniforme("D", 0, qy=-10.0)
    res = m.resolver()
    c = res.combinar("D+T", {"D": 1.0, "T": 1.0})
    mt = -E * I * ALFA * dg / H
    # En los empotramientos: -qL²/12 de la carga más el momento térmico.
    assert c.diagrama(0)["M"][0] == pytest.approx(-10.0 * largo**2 / 12 + mt, rel=1e-9)


def test_gradiente_sin_canto_se_rechaza():
    m = viga(3.0)
    with pytest.raises(ValueError, match="canto"):
        m.carga_termica("T", 0, ALFA, gradiente=10.0)
