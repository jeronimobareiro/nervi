# SPDX-License-Identifier: GPL-3.0-or-later
"""Comparación cruzada: flexión de vigas en Rust contra la versión en Python.

El núcleo de ``nervi.design.aci318.flexion`` pasó a ``nervi_core::diseno::viga``
(entrada de bitácora 2026-11-19-06). Mientras dure la transición, estas pruebas
comparan la versión Rust con la de Python anterior (``_referencia_flexion_python.py``)
en secciones, materiales y momentos al azar.
"""

import math
import warnings

import _referencia_flexion_python as ref  # junto a esta prueba (rootdir de pytest)
import numpy as np
import pytest

from nervi.design import aci318
from nervi.design.aci318 import flexion

TOL = 1e-9


@pytest.fixture(autouse=True)
def _sin_avisos():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        yield


def _igual(a, b, tol=TOL):
    if isinstance(a, float) and math.isinf(a):
        return a == b
    return abs(a - b) <= tol * max(abs(b), 1.0)


def _misma_resistencia(a, b, tol=TOL):
    for campo in ("Mn", "phi", "phiMn", "c", "a", "eps_t", "fs", "fs_comp"):
        assert _igual(getattr(a, campo), getattr(b, campo), tol), campo


def _materiales(rng):
    return aci318.Materiales(fc=float(rng.choice([21, 25, 28, 35, 45, 60])), fy=420.0)


def test_resistencia_igual_a_python():
    rng = np.random.default_rng(10)
    for _ in range(300):
        mat = _materiales(rng)
        b, h = rng.uniform(200, 500), rng.uniform(300, 900)
        d = h - rng.uniform(40, 80)
        As = float(rng.choice([0.0, rng.uniform(100, 0.06 * b * d)]))
        As_comp = float(rng.choice([0.0, rng.uniform(100, 3000)]))
        d_comp = float(rng.uniform(40, 80))
        dt = d + float(rng.uniform(0, 30))
        a = flexion._resistencia(b, d, As, mat, As_comp, d_comp, dt)
        r = ref._resistencia(b, d, As, mat, As_comp, d_comp, dt)
        _misma_resistencia(a, r)


def test_armadura_flexion_igual_a_python():
    rng = np.random.default_rng(11)
    for _ in range(200):
        mat = _materiales(rng)
        b, h = rng.uniform(200, 500), rng.uniform(300, 900)
        d = h - 60.0
        mu = float(rng.uniform(1.0, 2.5e-7 * mat.fc * b * d * d))
        kw = {"d_comp": 60.0, "eps_t_min": float(rng.choice([0.004, 0.005]))}
        try:
            r = ref.armadura_flexion(mu, b, d, mat, **kw)
        except ValueError as e:
            with pytest.raises(ValueError, match=str(e)[:20]):
                flexion.armadura_flexion(mu, b, d, mat, **kw)
            continue
        a = flexion.armadura_flexion(mu, b, d, mat, **kw)
        for campo in ("As_req", "As_min", "As", "As_comp", "eps_t_min"):
            assert _igual(getattr(a, campo), getattr(r, campo)), campo
        assert a.doble == r.doble
        _misma_resistencia(a.resistencia, r.resistencia)


@pytest.mark.parametrize("semilla", range(5))
def test_eleccion_de_barras_igual_a_python(semilla):
    rng = np.random.default_rng(20 + semilla)
    for _ in range(12):
        mat = _materiales(rng)
        sec = aci318.SeccionRectangular(
            b=float(rng.choice([200, 250, 300, 400])), h=float(rng.choice([400, 500, 700]))
        )
        mu = float(rng.uniform(5.0, 4e-7 * mat.fc * sec.b * sec.h**2))
        kw = {"max_capas": int(rng.choice([1, 2])), "max_barras": int(rng.integers(4, 13))}
        try:
            r = ref.elegir_barras(mu, sec, mat, **kw)
        except ValueError:
            with pytest.raises(ValueError, match="no hay una disposición"):
                flexion.elegir_barras(mu, sec, mat, **kw)
            continue
        a = flexion.elegir_barras(mu, sec, mat, **kw)
        assert a.capas == r.capas
        assert a.descripcion == r.descripcion
        for campo in ("As", "d", "dt", "b_nec", "s_libre", "As_req", "exceso"):
            assert _igual(getattr(a, campo), getattr(r, campo)), campo
        _misma_resistencia(a.resistencia, r.resistencia)


def test_diametros_propios_conservan_su_tipo():
    mat = aci318.Materiales(fc=28.0, fy=420.0)
    sec = aci318.SeccionRectangular(b=300, h=600)
    a = flexion.elegir_barras(180.0, sec, mat, diametros=(16, 20, 25))
    r = ref.elegir_barras(180.0, sec, mat, diametros=(16, 20, 25))
    assert a.capas == r.capas and all(isinstance(x, int) for c in a.capas for x in c)
