# SPDX-License-Identifier: GPL-3.0-or-later
"""Ediciones geométricas del modelo de cálculo (``nervi.edicion``)."""

import copy

import numpy as np
import pytest

from nervi import edicion, formato


def _vacio(fuerza="kN", longitud="m") -> dict:
    m = formato.modelo.nuevo()
    m["unidades"] = {"fuerza": fuerza, "longitud": longitud}
    return m


def _props(m):
    return edicion.propiedades_por_omision(m["unidades"])


def test_propiedades_por_omision_en_cada_unidad():
    kn_m = edicion.propiedades_por_omision({"fuerza": "kN", "longitud": "m"})
    assert kn_m == pytest.approx({"E": 2.5e7, "A": 0.09, "I": 0.3**4 / 12})
    n_mm = edicion.propiedades_por_omision({"fuerza": "N", "longitud": "mm"})
    # 25 GPa = 25 000 N/mm²; 90 000 mm²; 6,75e8 mm⁴.
    assert n_mm == pytest.approx({"E": 25_000.0, "A": 90_000.0, "I": 6.75e8})


def test_barra_crea_y_reusa_nudos():
    m = _vacio()
    assert edicion.agregar_barra(m, (0, 0), (0, 3), _props(m)) == [1]
    assert edicion.agregar_barra(m, (0, 3), (6, 3), _props(m)) == [2]
    assert [(n["id"], n["x"], n["y"]) for n in m["nudos"]] == [
        (1, 0.0, 0.0),
        (2, 0.0, 3.0),
        (3, 6.0, 3.0),
    ]
    assert [(b["i"], b["j"]) for b in m["barras"]] == [(1, 2), (2, 3)]
    with pytest.raises(ValueError, match="ya está"):
        edicion.agregar_barra(m, (6, 3), (0, 3), _props(m))
    with pytest.raises(ValueError, match="largo"):
        edicion.agregar_barra(m, (1, 1), (1, 1), _props(m))
    formato.modelo.validar(m)


def test_barra_se_parte_en_los_nudos_por_los_que_pasa():
    m = _vacio()
    edicion.agregar_nudo(m, (2, 0))
    edicion.agregar_nudo(m, (4, 0))
    edicion.agregar_nudo(m, (4, 1))  # fuera de la barra
    nuevas = edicion.agregar_barra(m, (0, 0), (6, 0), _props(m))
    assert len(nuevas) == 3
    xy = {n["id"]: (n["x"], n["y"]) for n in m["nudos"]}
    tramos = [(xy[b["i"]][0], xy[b["j"]][0]) for b in m["barras"]]
    assert tramos == [(0.0, 2.0), (2.0, 4.0), (4.0, 6.0)]


def test_nudo_sobre_barra_la_parte_con_sus_liberaciones():
    m = _vacio()
    edicion.agregar_barra(m, (0, 0), (6, 0), _props(m))
    m["barras"][0]["liberaciones"] = [False, False, True, False, False, True]
    n = edicion.agregar_nudo(m, (2, 0))
    b1, b2 = m["barras"]
    assert (b1["i"], b1["j"], b2["i"], b2["j"]) == (1, n, n, 2)
    assert b1["liberaciones"] == [False, False, True, False, False, False]
    assert b2["liberaciones"] == [False, False, False, False, False, True]
    assert edicion.agregar_nudo(m, (2, 0)) == n  # ya está


def test_partir_una_barra_no_cambia_los_resultados():
    """Partir una viga con todas sus cargas da las mismas reacciones y la misma flecha."""
    m = _vacio()
    edicion.agregar_barra(m, (0, 0), (8, 0), _props(m))
    edicion.poner_apoyo(m, 1, "articulado")
    edicion.poner_apoyo(m, 2, "movil_x")
    d = edicion.caso(m, "D")
    edicion.agregar_carga_barra(m, d, 1, {"tipo": "uniforme", "ejes": "global", "qy": -10.0})
    edicion.agregar_carga_barra(
        m, d, 1, {"tipo": "puntual", "ejes": "local", "a": 5.0, "px": 2.0, "py": -30.0}
    )
    edicion.agregar_carga_barra(
        m,
        d,
        1,
        {"tipo": "trapezoidal", "ejes": "global", "a": 1.0, "b": 7.0, "qy1": -4.0, "qy2": -16.0},
    )
    edicion.agregar_carga_barra(m, d, 1, {"tipo": "momento", "ejes": "local", "a": 6.0, "mz": 12.0})
    antes = copy.deepcopy(m)
    edicion.agregar_nudo(m, (3.0, 0.0))
    formato.modelo.validar(m)
    assert len(m["barras"]) == 2
    trap = [c for c in m["cargas_barra"] if c["tipo"] == "trapezoidal"]
    assert [(c["barra"], c["a"], c["b"]) for c in trap] == [(1, 1.0, 3.0), (2, 0.0, 4.0)]
    assert trap[0]["qy2"] == pytest.approx(-8.0) and trap[1]["qy1"] == pytest.approx(-8.0)
    puntual = next(c for c in m["cargas_barra"] if c["tipo"] == "puntual")
    assert (puntual["barra"], puntual["a"]) == (2, 2.0)

    def resolver(modelo):
        mod, _ = formato.construir_modelo(modelo)
        return mod.resolver()["D"]

    r0, r1 = resolver(antes), resolver(m)
    np.testing.assert_allclose(r1.reacciones[:2], r0.reacciones[:2], rtol=1e-12, atol=1e-9)
    np.testing.assert_allclose(
        r1.desplazamientos[:2], r0.desplazamientos[:2], rtol=1e-10, atol=1e-14
    )


def test_apoyos_cargas_y_quitar():
    m = _vacio()
    edicion.agregar_barra(m, (0, 0), (0, 3), _props(m))
    edicion.agregar_barra(m, (0, 3), (5, 3), _props(m))
    edicion.poner_apoyo(m, 1, "empotrado")
    assert edicion.tipo_apoyo(m["apoyos"][0]) == "empotrado"
    edicion.poner_apoyo(m, 1, "articulado")
    assert m["apoyos"] == [{"nudo": 1, "ux": True, "uy": True, "rz": False}]
    w = edicion.caso(m, "W")
    assert edicion.caso(m, "W") == w
    edicion.agregar_carga_nodal(m, w, 2, fx=5.0)
    with pytest.raises(ValueError, match="nula"):
        edicion.agregar_carga_nodal(m, w, 2)
    edicion.agregar_carga_barra(m, w, 2, {"tipo": "uniforme", "ejes": "local", "qy": -3.0})
    formato.modelo.validar(m)
    edicion.quitar_barra(m, 2)
    assert m["cargas_barra"] == [] and len(m["nudos"]) == 3
    edicion.quitar_nudo(m, 2)
    assert [b["id"] for b in m["barras"]] == [] and m["cargas_nodales"] == []
    edicion.quitar_nudo(m, 1)
    assert m["apoyos"] == []
    formato.modelo.validar(m)
