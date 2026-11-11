# SPDX-License-Identifier: GPL-3.0-or-later
"""El error de mecanismo indica el nudo y el GDL que hacen inestable el modelo (issue #9)."""

import pytest

import nervi

E, A, I = 2.0e8, 0.01, 1.0e-4


def test_viga_con_articulacion_de_mas_indica_el_nudo():
    # A (articulado) ─ C (rótula) ─ B (carrito): el centro puede bajar libremente.
    m = nervi.Modelo()
    a = m.agregar_nudo(0.0, 0.0)
    c = m.agregar_nudo(3.0, 0.0)
    b = m.agregar_nudo(6.0, 0.0)
    m.agregar_barra(a, c, E, A, I, articulada_j=True)
    m.agregar_barra(c, b, E, A, I, articulada_i=True)
    m.apoyar(a, rz=False)
    m.apoyar(b, ux=False, rz=False)
    m.carga_nodal("P", c, fy=-10.0)
    with pytest.raises(nervi.MecanismoError, match=f"el nudo {c} se puede mover en uy") as info:
        m.resolver()
    err = info.value
    assert (err.nudo, err.gdl) == (c, "uy")
    assert len(err.modos) == 1
    modo = {(n, g): v for n, g, v in err.modos[0]}
    assert modo[(c, "uy")] == pytest.approx(1.0)
    assert modo[(a, "rz")] == pytest.approx(1.0 / 3.0)
    assert modo[(b, "rz")] == pytest.approx(-1.0 / 3.0)


def test_portico_sin_arriostrar():
    m = nervi.Modelo()
    n0 = m.agregar_nudo(0.0, 0.0)
    n1 = m.agregar_nudo(0.0, 4.0)
    n2 = m.agregar_nudo(6.0, 4.0)
    n3 = m.agregar_nudo(6.0, 0.0)
    m.agregar_barra(n0, n1, E, A, I)
    m.agregar_barra(n1, n2, E, A, I, articulada_i=True, articulada_j=True)
    m.agregar_barra(n3, n2, E, A, I)
    m.apoyar(n0, rz=False)
    m.apoyar(n3, rz=False)
    m.carga_nodal("H", n1, fx=5.0)
    with pytest.raises(nervi.MecanismoError, match="mecanismo") as info:
        m.resolver()
    assert info.value.gdl == "ux"
    assert info.value.nudo in (n1, n2)


def test_carga_sin_rigidez_tambien_indica_el_nudo():
    # Nudo de cercha con carga de momento: el giro no tiene rigidez.
    m = nervi.Modelo()
    a = m.agregar_nudo(0.0, 0.0)
    b = m.agregar_nudo(3.0, 0.0)
    m.agregar_barra(a, b, E, A, I, articulada_i=True, articulada_j=True)
    m.apoyar(a, rz=False)
    m.apoyar(b, rz=False)
    m.carga_nodal("M", b, mz=1.0)
    with pytest.raises(nervi.MecanismoError) as info:
        m.resolver()
    assert (info.value.nudo, info.value.gdl, info.value.modos) == (b, "rz", [])
