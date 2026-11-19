# SPDX-License-Identifier: GPL-3.0-or-later
"""Comparación cruzada: flexocompresión de columnas en Rust contra la versión NumPy.

El núcleo de ``nervi.design.aci318.columna`` pasó a ``nervi_core::diseno::columna``
(entrada de bitácora 2026-11-19-04). Mientras dure la transición, estas pruebas
comparan la versión Rust con la NumPy anterior (``_referencia_columna_numpy.py``)
en secciones, armaduras y solicitaciones al azar.
"""

import math
import warnings

import _referencia_columna_numpy as ref  # junto a esta prueba (rootdir de pytest)
import numpy as np
import pytest

import nervi
from nervi.design import aci318
from nervi.design.aci318 import columna as col

MAT = aci318.Materiales(fc=28.0, fy=420.0)
TOL = 1e-6


def _secciones(rng, n):
    salida = []
    for _ in range(n):
        if rng.random() < 0.7:
            hy, hz = rng.uniform(250.0, 800.0, 2)
            n_y, n_z = rng.integers(2, 5, 2)
            s = aci318.SeccionColumna.rectangular(
                hy, hz, int(n_y), int(n_z), float(rng.choice([12, 16, 20, 25]))
            )
        else:
            s = aci318.SeccionColumna.circular(
                rng.uniform(300.0, 800.0), int(rng.integers(6, 12)), 16.0
            )
        salida.append(s)
    return salida


def _cerca(a, b, tol=TOL):
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    # Relativa al mayor valor del arreglo: un cero y un residuo de redondeo son iguales.
    finitos = np.abs(b[np.isfinite(b)])
    escala = max(float(finitos.max(initial=0.0)), 1.0)
    iguales = (a == b) | (np.abs(a - b) <= tol * escala)
    return bool(np.all(iguales))


def test_resultantes_iguales_a_numpy():
    rng = np.random.default_rng(1)
    for s in _secciones(rng, 20):
        geo = col._geo(s)
        theta = rng.uniform(0.0, 2.0 * math.pi, 50)
        c = np.exp(rng.uniform(math.log(1.0), math.log(5000.0), 50))
        for zunchada in (False, True):
            a = col._seccion_en(geo, MAT, theta, c, zunchada)
            b = ref._seccion_en(geo, MAT, theta, c, zunchada)
            for x, y in zip(a, b, strict=True):
                assert _cerca(x, y, 1e-9)


def test_capacidad_y_razones_iguales_a_numpy():
    rng = np.random.default_rng(2)
    for s in _secciones(rng, 12):
        geo = col._geo(s)
        ax = col.resistencia_axial(s, MAT)
        pu = rng.uniform(-0.9 * ax.phiPnt, 1.1 * ax.phiPn_max, 20)
        escala = 0.15 * ax.Po * min(s.altura("z"), s.altura("y")) / 1e3
        mz = rng.normal(0.0, escala, 20)
        my = rng.normal(0.0, escala, 20)
        my[:3] = 0.0  # flexión uniaxial
        mz[3:5] = my[3:5] = 0.0  # sin momento
        a = col._razones(geo, MAT, pu, mz, my, False, ax.phiPn_max, ax.phiPnt)
        b = ref._razones(geo, MAT, pu, mz, my, False, ax.phiPn_max, ax.phiPnt)
        for x, y in zip(a, b, strict=True):
            assert _cerca(x, y)


def test_diagrama_de_interaccion_igual_a_numpy():
    s = aci318.SeccionColumna.rectangular(500.0, 300.0, 3, 2, 20.0)
    geo = col._geo(s)
    ax = col.resistencia_axial(s, MAT, zunchada=True)
    # Como diagrama_interaccion: sin los extremos, donde φPn = p_obj solo en el borde.
    niveles = np.linspace(-ax.phiPnt, 0.75 * ax.Po, 32)[1:-1] * 1e3
    for angulo in (0.0, 0.6, math.pi / 2, 2.5):
        a = col._capacidad_en_direccion(geo, MAT, niveles, angulo, True)
        b = ref._capacidad_en_direccion(geo, MAT, niveles, angulo, True)
        for x, y in zip(a, b, strict=True):
            assert _cerca(x, y)


def _elegir_numpy(seccion, mat, puntos):
    """``elegir_armadura_columna`` con el núcleo NumPy, tal como estaba."""
    candidatas = col._candidatas(seccion, col.DIAMETROS_COLUMNA, False)
    secciones = [seccion.con_barras(cant, d) for _, _, cant, d in candidatas]
    n_max = max(s.barras.shape[0] for s in secciones)
    pb = np.zeros((len(secciones), n_max, 2))
    ab = np.zeros((len(secciones), n_max))
    for k, s in enumerate(secciones):
        pb[k, : s.barras.shape[0]] = s.barras[:, :2]
        ab[k, : s.barras.shape[0]] = s.areas
    ax = [col.resistencia_axial(s, mat) for s in secciones]
    pmax = np.array([a.phiPn_max for a in ax])
    pnt = np.array([a.phiPnt for a in ax])
    todos = np.array([p[2:] for p in puntos], dtype=np.float64)
    grupo = {int(np.argmax(np.hypot(todos[:, 1], todos[:, 2]))), int(np.argmax(todos[:, 0]))}
    vivas = np.arange(len(secciones))
    while vivas.size:
        g = np.array(sorted(grupo))
        sel = todos[g]
        geo = (seccion.contorno, pb[vivas][:, None], ab[vivas][:, None])
        _, _, _, r = ref._razones(
            geo, mat, sel[:, 0], sel[:, 1], sel[:, 2], False,
            pmax[vivas][:, None], pnt[vivas][:, None],
        )  # fmt: skip
        vivas = vivas[np.all(r <= 1.0, axis=1)]
        if not vivas.size:
            break
        mejor = secciones[int(vivas[0])]
        a = col.resistencia_axial(mejor, mat)
        _, _, _, rr = ref._razones(
            col._geo(mejor), mat, todos[:, 0], todos[:, 1], todos[:, 2], False,
            a.phiPn_max, a.phiPnt,
        )  # fmt: skip
        if np.all(rr <= 1.0):
            return mejor
        grupo.add(int(np.argmax(rr)))
        vivas = vivas[1:]
    return None


@pytest.mark.parametrize("semilla", [3, 4, 5])
def test_eleccion_de_armadura_igual_a_numpy(semilla):
    rng = np.random.default_rng(semilla)
    s = aci318.SeccionColumna.rectangular(
        float(rng.uniform(300.0, 600.0)), float(rng.uniform(300.0, 600.0))
    )
    ax = col.resistencia_axial(s, MAT)
    puntos = [
        ("c", None, float(p), float(m1), float(m2))
        for p, m1, m2 in zip(
            rng.uniform(0.0, 0.5 * ax.phiPn_max, 8),
            rng.normal(0.0, 0.02 * ax.Po * s.altura("z") / 1e3, 8),
            rng.normal(0.0, 0.01 * ax.Po * s.altura("y") / 1e3, 8),
            strict=True,
        )
    ]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            rust = col.elegir_armadura_columna(s, MAT, puntos)
        except ValueError:
            rust = None
    numpy = _elegir_numpy(s, MAT, puntos)
    assert (rust is None) == (numpy is None)
    if rust is not None:
        assert rust.descripcion == numpy.descripcion


def test_version_del_contrato():
    assert nervi._core.VERSION_CONTRATO_DISENO == 1
    s = aci318.SeccionColumna.rectangular(400.0, 400.0)
    v, pb, ab = col._geo(s)
    with pytest.raises(ValueError, match="contrato"):
        nervi._core.columna_razones(
            99, v, np.ascontiguousarray(pb), ab, 28.0, 420.0, False,
            np.zeros((1, 3)), 1.0, 1.0,
        )  # fmt: skip
