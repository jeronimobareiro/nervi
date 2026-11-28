# SPDX-License-Identifier: GPL-3.0-or-later
"""Enganche de puntos en planta desde Python (``nervi.enganche``, motor en Rust)."""

import random

import pytest
from test_gui_edificio import _edificio

from nervi.enganche import Enganche, IndiceEnganche, geometria_planta


def test_tipos_basicos():
    idx = IndiceEnganche([(6.0, 0.0)], [((0.0, 0.0), (6.0, 0.0)), ((6.0, 0.0), (6.0, 5.0))])
    assert idx.cantidad == (1, 2)
    assert idx.enganchar(6.1, 0.1, 0.3).tipo == "punto"
    assert idx.enganchar(6.1, 0.1, 0.3, puntos=False).tipo == "extremo"
    assert idx.enganchar(3.0, 0.2, 0.3) == Enganche((3.0, 0.0), "medio", 0)
    assert idx.enganchar(1.0, 0.2, 0.3).tipo == "cerca"
    e = idx.enganchar(9.1, 0.1, 0.3, anterior=(6.0, 0.0), paso_grilla=0.5)
    assert e.tipo == "polar" and e.punto == (9.0, 0.0) and e.guia == ((6.0, 0.0), (9.0, 0.0))
    e = idx.enganchar(8.1, 3.4, 0.3, anterior=(6.0, 0.0), orto=True, paso_grilla=0.5)
    assert e.tipo == "polar" and e.punto == (6.0, 3.5)
    assert idx.enganchar(3.3, 3.3, 0.3, paso_grilla=0.5) == Enganche((3.5, 3.5), "grilla")
    assert idx.enganchar(3.3, 3.3, 0.3).tipo == "libre"


def test_entradas_invalidas():
    with pytest.raises(ValueError):
        IndiceEnganche([(float("nan"), 0.0)], [])
    idx = IndiceEnganche([], [])
    with pytest.raises(ValueError):
        idx.enganchar(0, 0, -1.0)
    assert idx.enganchar(1.0, 2.0, 0.5).punto == (1.0, 2.0)


def test_geometria_de_la_planta_del_ejemplo():
    mf = _edificio()
    piso = next(p["id"] for p in mf.lista("pisos") if p["nombre"] == "Piso 1")
    g = geometria_planta(mf, piso)
    en = mf.en_piso(piso)
    columna = en["columnas"][0]
    x, y = columna["punto"]
    e = g.indice.enganchar(x + 0.1, y + 0.05, 0.3)
    assert e.tipo == "punto" and g.origen(e) == ("columnas", columna["id"])
    viga = en["vigas"][0]
    (x1, y1), (x2, y2) = viga["p1"], viga["p2"]
    e = g.indice.enganchar((x1 + x2) / 2 + 0.7, (y1 + y2) / 2 + 0.01, 0.3, medios=False)
    assert e.tipo == "cerca" and g.origen(e)[0] in ("vigas", "losas", "ejes")
    sin_ejes = geometria_planta(mf, piso, ejes=False)
    assert sin_ejes.indice.cantidad[1] == g.indice.cantidad[1] - len(mf.lista("ejes"))
    assert geometria_planta(mf, None).indice.cantidad == (0, len(mf.lista("ejes")))


def test_indice_igual_al_recorrido_completo():
    rnd = random.Random(3)
    segs = []
    for _ in range(400):
        a = (rnd.uniform(0, 80), rnd.uniform(0, 50))
        segs.append((a, (a[0] + rnd.uniform(-8, 8), a[1] + rnd.uniform(-8, 8))))
    pts = [(rnd.uniform(0, 80), rnd.uniform(0, 50)) for _ in range(200)]
    idx = IndiceEnganche(pts, segs)
    for k in range(800):
        x, y = rnd.uniform(-5, 85), rnd.uniform(-5, 55)
        kw = {
            "anterior": (rnd.uniform(0, 80), rnd.uniform(0, 50)) if k % 2 else None,
            "orto": k % 3 == 0,
            "paso_grilla": 0.5 if k % 4 else 0.0,
            "recientes": (k % 400,),
        }
        r = rnd.uniform(0.05, 1.5)
        assert idx.enganchar(x, y, r, **kw) == idx.enganchar(x, y, r, recorrer_todo=True, **kw)
