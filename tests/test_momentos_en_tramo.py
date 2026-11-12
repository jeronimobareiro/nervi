# SPDX-License-Identifier: GPL-3.0-or-later
"""Momentos concentrados en el tramo de una barra desde Python (issue #3).

Fuente: viga biempotrada con momento concentrado, Ghali, Neville y Brown,
Structural Analysis, 6.ª ed., apéndice D (``M0/4`` en cada extremo y
``3·M0/(2L)`` de cortante con el momento en el centro).
"""

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


def test_biempotrada_con_momento_en_el_centro():
    largo, m0 = 6.0, 30.0
    m = viga(largo)
    m.apoyar(0)
    m.apoyar(1)
    m.carga_momento("M", 0, a=largo / 2, mz=m0)
    r = m.resolver()["M"]
    assert r.reacciones[0] == pytest.approx([0.0, 1.5 * m0 / largo, m0 / 4], abs=1e-9)
    assert r.reacciones[1] == pytest.approx([0.0, -1.5 * m0 / largo, m0 / 4], abs=1e-9)


def test_salto_del_diagrama_en_a():
    largo, a, m0 = 5.0, 2.0, 12.0
    m = viga(largo)
    m.apoyar(0, rz=False)
    m.apoyar(1, ux=False, rz=False)
    m.carga_momento("M", 0, a=a, mz=m0)
    d = m.resolver()["M"].diagrama(0)
    en_a = d["M"][np.isclose(d["x"], a)]
    assert len(en_a) == 2
    assert en_a[1] - en_a[0] == pytest.approx(-m0, rel=1e-9)
    assert en_a[0] == pytest.approx(m0 * a / largo, rel=1e-9)


def test_igual_a_un_momento_nodal_en_un_nudo_intermedio():
    largo, a, m0 = 7.0, 2.6, -25.0
    m1 = viga(largo)
    m1.apoyar(0)
    m1.apoyar(1, rz=False)
    m1.carga_momento("M", 0, a=a, mz=m0)

    m2 = nervi.Modelo()
    for x in (0.0, a, largo):
        m2.agregar_nudo(x, 0)
    m2.agregar_barra(0, 1, E, A, I)
    m2.agregar_barra(1, 2, E, A, I)
    m2.apoyar(0)
    m2.apoyar(2, rz=False)
    m2.carga_nodal("M", 1, mz=m0)

    r1, r2 = m1.resolver()["M"], m2.resolver()["M"]
    np.testing.assert_allclose(r1.reacciones[[0, 1]], r2.reacciones[[0, 2]], atol=1e-9)


def test_posicion_fuera_de_la_barra_se_rechaza():
    m = viga(3.0)
    m.apoyar(0)
    m.carga_momento("M", 0, a=3.5, mz=1.0)
    with pytest.raises(ValueError, match="fuera de la luz"):
        m.resolver()
