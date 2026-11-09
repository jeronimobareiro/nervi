"""Pruebas de la API Python contra soluciones analíticas (unidades kN, m)."""

import doctest

import numpy as np
import pytest

import nervi

E, A, I = 2.0e8, 0.01, 1.0e-4


def viga(l: float) -> tuple[nervi.Modelo, int, int, int]:
    m = nervi.Modelo()
    a = m.agregar_nudo(0.0, 0.0)
    b = m.agregar_nudo(l, 0.0)
    barra = m.agregar_barra(a, b, E, A, I)
    return m, a, b, barra


def test_viga_biapoyada_uniforme():
    l, q = 6.0, 10.0
    m, a, b, barra = viga(l)
    m.apoyar(a, ux=True, uy=True, rz=False)
    m.apoyar(b, ux=False, uy=True, rz=False)
    m.carga_uniforme("q", barra, qy=-q)
    r = m.resolver(n_estaciones=21)["q"]
    assert r.reacciones[a, 1] == pytest.approx(q * l / 2, rel=1e-10)
    d = r.diagrama(barra)
    assert d["M"].max() == pytest.approx(q * l**2 / 8, rel=1e-10)
    assert d["v"].min() == pytest.approx(-5 * q * l**4 / (384 * E * I), rel=1e-10)


def test_combinacion_lineal():
    l = 5.0
    m, a, b, barra = viga(l)
    m.apoyar(a)
    m.carga_uniforme("D", barra, qy=-4.0)
    m.carga_uniforme("L", barra, qy=-3.0)
    res = m.resolver()
    combo = res.combinar("1.2D+1.6L", {"D": 1.2, "L": 1.6})
    q = 1.2 * 4.0 + 1.6 * 3.0
    assert combo.reacciones[a, 2] == pytest.approx(q * l**2 / 2, rel=1e-10)
    assert combo.desplazamientos[b, 1] == pytest.approx(-q * l**4 / (8 * E * I), rel=1e-10)
    assert combo.diagrama(barra)["M"][0] == pytest.approx(-q * l**2 / 2, rel=1e-10)


def test_combinacion_con_estaciones_distintas():
    l = 4.0
    m, a, _, barra = viga(l)
    m.apoyar(a)
    m.carga_puntual("P1", barra, a=1.0, py=-10.0)
    m.carga_uniforme("q", barra, qy=-2.0)
    res = m.resolver()
    combo = res.combinar("P1+q", {"P1": 1.0, "q": 1.0})
    # Momento de empotramiento exacto en x = 0 (es una estación de ambos casos).
    esperado = -(10.0 * 1.0 + 2.0 * l**2 / 2)
    assert combo.diagrama(barra)["M"][0] == pytest.approx(esperado, rel=1e-10)


def test_cercha_reporta_giros_sin_rigidez():
    m = nervi.Modelo()
    n0, n1, n2 = m.agregar_nudo(0, 0), m.agregar_nudo(4, 0), m.agregar_nudo(2, 2)
    for i, j in [(n0, n2), (n2, n1), (n0, n1)]:
        m.agregar_barra(i, j, E, A, I, articulada_i=True, articulada_j=True)
    m.apoyar(n0, rz=False)
    m.apoyar(n1, ux=False, rz=False)
    m.carga_nodal("P", n2, fy=-100.0)
    res = m.resolver()
    assert sorted(res.gdl_sin_rigidez) == [(0, "rz"), (1, "rz"), (2, "rz")]
    assert res["P"].diagrama(2)["N"][0] == pytest.approx(50.0, rel=1e-10)


def test_asentamiento():
    l, delta = 5.0, 0.01
    m, a, b, _ = viga(l)
    m.apoyar(a)
    m.apoyar(b)
    m.desplazamiento_impuesto("S", b, uy=-delta)
    r = m.resolver()["S"]
    assert abs(r.reacciones[a, 2]) == pytest.approx(6 * E * I * delta / l**2, rel=1e-10)


def test_mecanismo_lanza_error_claro():
    m, a, b, _ = viga(4.0)
    m.apoyar(a, ux=False, rz=False)
    m.apoyar(b, ux=False, rz=False)
    m.carga_nodal("H", b, fx=1.0)
    with pytest.raises(nervi.MecanismoError, match="mecanismo"):
        m.resolver()


def test_datos_invalidos():
    m, a, b, _ = viga(3.0)
    m.apoyar(a)
    m.carga_nodal("P", b, fy=-1)
    m._barras[0] = (0, 1, -1.0, A, I, (False,) * 6)
    with pytest.raises(ValueError, match="E = -1"):
        m.resolver()


def test_contrato_valida_formas():
    m, a, b, _ = viga(3.0)
    m.apoyar(a)
    m.carga_nodal("P", b, fy=-1)
    arr = m.arreglos()
    arr["props"] = arr["props"][:, :2].copy()
    with pytest.raises(ValueError, match="props"):
        nervi._core.resolver_portico_2d(nervi._core.VERSION_CONTRATO, **arr)
    with pytest.raises(ValueError, match="versión"):
        nervi._core.resolver_portico_2d(99, **m.arreglos())


def test_arreglos_resultado_tienen_formas_del_contrato():
    m, a, b, barra = viga(3.0)
    m.apoyar(a)
    m.carga_nodal("P", b, fy=-1)
    m.carga_nodal("H", b, fx=1)
    res = m.resolver()
    assert res.casos == ["P", "H"]
    r = res["H"]
    assert r.desplazamientos.shape == (2, 3)
    assert r.fuerzas_extremo.shape == (1, 6)
    assert np.all(np.diff(r.diagrama(barra)["x"]) >= 0)


def test_ejemplo_de_la_documentacion():
    assert doctest.testmod(nervi).failed == 0
