# SPDX-License-Identifier: GPL-3.0-or-later
"""Combinaciones de carga y envolventes (issue #21, experimental).

Fuentes: ACI 318-19 §5.3.1 y §24.2; viga continua de dos tramos por el método de
las fuerzas (Hibbeler, Structural Analysis, 10.ª ed., cap. 10) y estática.
"""

import doctest

import numpy as np
import pytest

import nervi
from nervi import design

pytestmark = pytest.mark.filterwarnings("ignore::nervi.design.ModuloExperimentalWarning")

E, A, I = 2.0e8, 0.01, 1.0e-4


def _factores(combs):
    return {frozenset(c.factores.items()) for c in combs}


def test_combinaciones_coinciden_con_la_lista_hecha_a_mano():
    # D, L, Lr y un viento W en ambos sentidos, ACI 318-19 §5.3.1.
    combs = design.generar({"D": "D", "L": "L", "Lr": "Lr", "W": "W"})
    a_mano = [
        {"D": 1.4},  # a
        {"D": 1.2, "L": 1.6},  # b sin cubierta
        {"D": 1.2, "L": 1.6, "Lr": 0.5},  # b
        {"D": 1.2, "Lr": 1.6, "L": 1.0},  # c con L
        {"D": 1.2, "Lr": 1.6, "W": 0.5},  # c con W
        {"D": 1.2, "Lr": 1.6, "W": -0.5},
        {"D": 1.2, "W": 1.0, "L": 1.0},  # d sin cubierta
        {"D": 1.2, "W": 1.0, "L": 1.0, "Lr": 0.5},  # d
        {"D": 1.2, "W": -1.0, "L": 1.0},
        {"D": 1.2, "W": -1.0, "L": 1.0, "Lr": 0.5},
        {"D": 0.9, "W": 1.0},  # f
        {"D": 0.9, "W": -1.0},
    ]
    assert len(combs) == len(a_mano)
    assert _factores(combs) == {frozenset(f.items()) for f in a_mano}
    assert all(c.estado == "resistencia" for c in combs)
    assert combs[0].referencia == "ACI 318-19 5.3.1a"


def test_sismo_nieve_y_servicio():
    combs = design.generar(
        {"D": "D", "L": "L", "S": "S", "E": "E"},
        estados=("resistencia", "servicio"),
        invertir_laterales=False,
        reducir_sobrecarga=True,
    )
    f = _factores(combs)
    assert frozenset({"D": 1.2, "E": 1.0, "L": 0.5, "S": 0.2}.items()) in f  # e, §5.3.3
    assert frozenset({"D": 0.9, "E": 1.0}.items()) in f  # g
    servicio = [c for c in combs if c.estado == "servicio"]
    assert _factores(servicio) == {
        frozenset({"D": 1.0}.items()),
        frozenset({"D": 1.0, "L": 1.0}.items()),
        frozenset({"D": 1.0, "L": 1.0, "S": 1.0}.items()),
    }


def test_sobrecarga_alternada_genera_todos_los_juegos():
    combs = design.generar({"D": "D", "L1": "L", "L2": "L"}, alternar_sobrecarga=True)
    assert _factores(combs) == {
        frozenset({"D": 1.4}.items()),
        frozenset({"D": 1.2, "L1": 1.6, "L2": 1.6}.items()),
        frozenset({"D": 1.2, "L1": 1.6}.items()),
        frozenset({"D": 1.2, "L2": 1.6}.items()),
        frozenset({"D": 1.2}.items()),
    }


def test_errores_de_tipos():
    with pytest.raises(ValueError, match="tipos válidos"):
        design.generar({"D": "D", "X": "Q"})
    with pytest.raises(ValueError, match="permanente"):
        design.generar({"L": "L"})
    with pytest.raises(ValueError, match="norma"):
        design.generar({"D": "D"}, norma="inventada")


def test_aviso_experimental():
    with pytest.warns(design.ModuloExperimentalWarning):
        design.generar({"D": "D"})


def _continua(largo: float, d: float, l: float) -> nervi.Modelo:
    m = nervi.Modelo()
    for k in range(3):
        m.agregar_nudo(k * largo, 0.0)
    m.agregar_barra(0, 1, E, A, I)
    m.agregar_barra(1, 2, E, A, I)
    m.apoyar(0, rz=False)
    m.apoyar(1, ux=False, rz=False)
    m.apoyar(2, ux=False, rz=False)
    m.carga_uniforme("D", 0, qy=-d)
    m.carga_uniforme("D", 1, qy=-d)
    m.carga_uniforme("L1", 0, qy=-l)
    m.carga_uniforme("L2", 1, qy=-l)
    return m


def test_envolvente_de_viga_continua_con_sobrecarga_alternada():
    # Dos tramos iguales con w1 en el tramo 1 y w2 en el 2 (método de las fuerzas):
    # M_B = -(w1 + w2) L²/16; en el tramo 1, R_A = w1 L/2 + M_B/L y M_máx = R_A²/2w1.
    largo, d, l = 6.0, 10.0, 8.0
    m = _continua(largo, d, l)
    combs = design.generar({"D": "D", "L1": "L", "L2": "L"}, alternar_sobrecarga=True)
    res = m.resolver(combinaciones=design.como_diccionario(combs))
    env = design.envolvente(res, 0)

    # Momento negativo máximo sobre el apoyo central: los dos tramos cargados.
    w = 1.2 * d + 1.6 * l
    assert env["M_min"][-1] == pytest.approx(-w * largo**2 / 8, rel=1e-9)
    assert env["M_min_comb"][-1] == "5.3.1b: 1.2·D + 1.6·L1 + 1.6·L2"

    # Momento positivo máximo del tramo 1: sobrecarga solo en el tramo 1.
    w1, w2 = 1.2 * d + 1.6 * l, 1.2 * d
    mb = -(w1 + w2) * largo**2 / 16
    ra = w1 * largo / 2 + mb / largo
    m_max = ra**2 / (2 * w1)
    k = env["M_max"].argmax()
    assert env["M_max"][k] == pytest.approx(m_max, rel=1e-9)
    assert env["x"][k] == pytest.approx(ra / w1, rel=1e-9)
    assert env["M_max_comb"][k] == "5.3.1b: 1.2·D + 1.6·L1"

    # La sobrecarga alternada da un M+ mayor que la sobrecarga en los dos tramos.
    ambos = res["5.3.1b: 1.2·D + 1.6·L1 + 1.6·L2"].diagrama(0)["M"].max()
    assert m_max > ambos

    # Reacciones: la del apoyo central es máxima con los dos tramos cargados (5wL/4).
    er = design.envolvente_reacciones(res)
    assert er["max"][1, 1] == pytest.approx(5 * w * largo / 4, rel=1e-9)


def test_combinacion_resuelta_es_exacta_y_comparte_estaciones():
    largo = 6.0
    m = _continua(largo, 10.0, 8.0)
    m.carga_puntual("P", 0, 2.0, py=-30.0)  # salto en x = 2 solo en el caso P
    combs = {"A": {"D": 1.2, "L1": 1.6}, "B": {"D": 1.0, "P": 1.0, "L2": 0.5}}
    res = m.resolver(combinaciones=combs)
    assert res.combinaciones == ["A", "B"]
    assert res.factores("B") == {"D": 1.0, "L2": 0.5, "P": 1.0}
    da, db = res["A"].diagrama(0), res["B"].diagrama(0)
    np.testing.assert_array_equal(da["x"], db["x"])
    # Reacciones y desplazamientos por superposición.
    r = res["B"].reacciones
    esperado = res["D"].reacciones + res["P"].reacciones + 0.5 * res["L2"].reacciones
    np.testing.assert_allclose(r, esperado, rtol=1e-12, atol=1e-9)
    # En las estaciones de los casos, el diagrama de la combinación es su suma.
    dd, dp, dl = (res[c].diagrama(0) for c in ("D", "P", "L2"))
    for x in dp["x"][dp["x"] != 2.0]:
        k = np.flatnonzero(np.isclose(db["x"], x))[0]
        suma = sum(
            f * d["M"][np.flatnonzero(np.isclose(d["x"], x))[0]]
            for d, f in ((dd, 1.0), (dp, 1.0), (dl, 0.5))
            if np.isclose(d["x"], x).any()
        )
        if np.isclose(dd["x"], x).any() and np.isclose(dl["x"], x).any():
            assert db["M"][k] == pytest.approx(suma, rel=1e-9, abs=1e-9)
    # El salto bajo la carga puntual aparece en la combinación.
    k = np.flatnonzero(np.isclose(db["x"], 2.0))
    assert k.size == 2
    assert db["V"][k[0]] - db["V"][k[1]] == pytest.approx(30.0, rel=1e-9)


def test_errores_de_combinaciones():
    m = _continua(6.0, 10.0, 8.0)
    with pytest.raises(ValueError, match="nombre de un caso"):
        m.resolver(combinaciones={"D": {"D": 1.0}})
    with pytest.raises(ValueError, match="inexistente"):
        m.resolver(combinaciones={"X": {"Q": 1.0}})
    res = m.resolver()
    with pytest.raises(ValueError, match="no hay combinaciones"):
        design.envolvente(res, 0)


def test_doctest_del_modulo():
    import nervi.design as mod

    assert doctest.testmod(mod).failed == 0
