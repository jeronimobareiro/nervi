# SPDX-License-Identifier: GPL-3.0-or-later
"""Modelo de cálculo generado desde el modelo físico (issue #74).

Criterio de salida del issue: el edificio de referencia del #73 (el de
``examples/edificio_fisico.py``) da los mismos esfuerzos que el mismo modelo
armado a mano con ``Modelo3D``, como en ``examples/edificio_diafragma_3d.py``:
columnas, vigas con brazos de media columna, un diafragma por piso, empotramientos
y las cargas de las losas por áreas tributarias a 45° calculadas a mano.
"""

import math
from itertools import pairwise

import numpy as np
import pytest

import nervi
from nervi.fisico import ModeloFisico
from nervi.idealizacion import (
    PESO_ACERO,
    generar,
    modulo_elasticidad,
    peso_especifico,
)
from nervi.reparto import PESO_HORMIGON
from nervi.secciones import rectangular

XS, YS, H, N = (0.0, 6.0, 12.0), (0.0, 5.0), 3.0, 3
E_MPA = 25_000.0
CARGAS = {"permanente": 1.5, "sobrecarga": 2.0}
ESPESOR = 120.0  # mm


def edificio(longitud="m", muro=False):
    """El edificio de referencia del #73, en la unidad pedida."""
    f = {"m": 1.0, "cm": 100.0, "mm": 1000.0}[longitud]
    mf = ModeloFisico(longitud)
    pisos = [mf.agregar_piso("PB", 0.0)]
    pisos += [mf.agregar_piso(f"P{k}", k * H * f, **CARGAS) for k in range(1, N + 1)]
    h25 = mf.agregar_material("H-25", "hormigon", fc=25.0, E=E_MPA)
    col = mf.agregar_seccion("C 40x40", "rectangular", b=400.0, h=400.0)
    vig = mf.agregar_seccion("V 25x50", "rectangular", b=250.0, h=500.0)
    for abajo, arriba in pairwise(pisos):
        for x in XS:
            for y in YS:
                mf.agregar_columna((x * f, y * f), abajo, arriba, col, h25)
        tramos = [((x1, y), (x2, y)) for y in YS for x1, x2 in pairwise(XS)]
        tramos += [((x, YS[0]), (x, YS[1])) for x in XS]
        for a, b in tramos:
            mf.agregar_viga(arriba, (a[0] * f, a[1] * f), (b[0] * f, b[1] * f), vig, h25)
        for x1, x2 in pairwise(XS):
            contorno = [(x1, YS[0]), (x2, YS[0]), (x2, YS[1]), (x1, YS[1])]
            mf.agregar_losa(arriba, [(x * f, y * f) for x, y in contorno], ESPESOR, h25)
    if muro:
        mf.agregar_muro((0.0, 0.0), (0.0, 5.0 * f), pisos[0], pisos[-1], 200.0, h25)
    return mf


# --- Modelo armado a mano --------------------------------------------------------------


def _tributaria(largo, corto):
    """Ancho tributario a 45° sobre un lado de una losa de ``largo`` x ``corto`` con los
    cuatro bordes apoyados: puntos (s, ancho) de la poligonal, para el lado de largo
    ``largo`` (trapecio) o de largo ``corto`` (triángulo)."""
    m = corto / 2
    if largo > corto:
        return [(0.0, 0.0), (m, m), (largo - m, m), (largo, 0.0)]
    return [(0.0, 0.0), (largo / 2, largo / 2), (largo, 0.0)]


def _integrales(poli, lo, hi, ref):
    """∫q y ∫q·(s - ref) de la poligonal ``poli`` entre ``lo`` y ``hi`` (exacto)."""
    f = m = 0.0
    for (s0, q0), (s1, q1) in pairwise(poli):
        a, b = max(s0, lo), min(s1, hi)
        if b <= a:
            continue
        qa = q0 + (q1 - q0) * (a - s0) / (s1 - s0)
        qb = q0 + (q1 - q0) * (b - s0) / (s1 - s0)
        l = b - a
        f += 0.5 * (qa + qb) * l
        m += l * l * (qa / 6 + qb / 3) + (a - ref) * 0.5 * (qa + qb) * l
    return f, m


def a_mano():
    """El mismo edificio con ``Modelo3D``, nudo por nudo y carga por carga."""
    E = E_MPA * 1e3
    G = E / 2.4
    columna, viga = rectangular(0.40, 0.40), rectangular(0.25, 0.50)
    brazo = 0.20
    m = nervi.Modelo3D()
    m.caso("D")
    m.caso("L")
    nudo = {}
    for p in range(N + 1):
        for x in XS:
            for y in YS:
                nudo[p, x, y] = m.agregar_nudo(x, y, H * p)
                if p == 0:
                    m.apoyar(nudo[p, x, y])
    q = {
        "D": ESPESOR * 1e-3 * PESO_HORMIGON + CARGAS["permanente"],
        "L": CARGAS["sobrecarga"],
    }
    for p in range(1, N + 1):
        for x in XS:
            for y in YS:
                # Sección con h sobre Y (y local) y b sobre X, como en la planta.
                m.agregar_barra(
                    nudo[p - 1, x, y], nudo[p, x, y], E, G, seccion=columna, referencia=(0, 1, 0)
                )
        vigas = [((x1, y), (x2, y)) for y in YS for x1, x2 in pairwise(XS)]
        vigas += [((x, YS[0]), (x, YS[1])) for x in XS]
        for a, b in vigas:
            i, j = nudo[(p, *a)], nudo[(p, *b)]
            k = m.agregar_barra(i, j, E, G, seccion=viga, brazo_i=brazo, brazo_j=brazo)
            largo = math.dist(a, b)
            en_x = a[1] == b[1]
            # Losas a cada lado: las de X tienen una; la del eje central en Y, dos.
            n_losas = 1 if en_x or a[0] in (XS[0], XS[-1]) else 2
            poli = _tributaria(largo, 5.0 if en_x else 6.0)
            d = np.array(b) - np.array(a)
            d = d / np.linalg.norm(d)
            for caso, qs in q.items():
                w = [(s, n_losas * qs * t) for s, t in poli]
                # Parte flexible: tramos trapezoidales entre los vértices.
                for (s0, q0), (s1, q1) in pairwise(w):
                    lo, hi = max(s0, brazo), min(s1, largo - brazo)
                    if hi <= lo:
                        continue
                    qa = q0 + (q1 - q0) * (lo - s0) / (s1 - s0)
                    qb = q0 + (q1 - q0) * (hi - s0) / (s1 - s0)
                    m.carga_trapezoidal(
                        caso, k, (0, 0, -qa), (0, 0, -qb), lo - brazo, hi - brazo, ejes="global"
                    )
                # Brazos: fuerza y momento de la carga sobre la zona rígida, al nudo.
                zonas = ((i, 0, brazo, 0.0), (j, largo - brazo, largo, largo))
                for nudo_k, lo, hi, s_nudo in zonas:
                    f, mom = _integrales(w, lo, hi, s_nudo)
                    # M = ∫ r x (0, 0, -q) con r = d·(s - s_nudo)
                    r = d * mom
                    m.carga_nodal(caso, nudo_k, fz=-f, mx=-r[1], my=r[0])
    for p in range(1, N + 1):
        m.diafragma([nudo[p, x, y] for x in XS for y in YS])
    return m, nudo


def _por_coordenadas(nudos):
    return {tuple(np.round(p, 9)): k for k, p in enumerate(nudos)}


def test_mismo_resultado_que_a_mano():
    mc = generar(edificio(), peso_propio=False)
    mano, nudo = a_mano()
    assert mc.n_barras == len(mano._barras)
    assert len(mc.modelo.diafragmas) == N
    r_gen, r_mano = mc.modelo.resolver(), mano.resolver()
    idx = _por_coordenadas(mc.nudos)
    pares = [(idx[(x, y, H * p)], k) for (p, x, y), k in nudo.items()]
    for caso in ("D", "L"):
        ug, um = r_gen[caso].desplazamientos, r_mano[caso].desplazamientos
        escala = np.abs(um).max()
        for g, k in pares:
            np.testing.assert_allclose(ug[g], um[k], rtol=0, atol=1e-9 * escala)
        rg, rm = r_gen[caso].reacciones, r_mano[caso].reacciones
        for g, k in pares:
            np.testing.assert_allclose(rg[g], rm[k], rtol=0, atol=1e-9 * np.abs(rm).max())

    # Barra por barra: mismas fuerzas de extremo (se emparejan por sus nudos).
    def clave_mano(b):
        return tuple(tuple(np.round(mano._nudos[n], 9)) for n in b["nudos"])

    extremos = {clave_mano(b): k for k, b in enumerate(mano._barras)}
    for k, o in enumerate(mc.origenes):
        i, j = mc.modelo._barras[k]["nudos"]
        clave = (tuple(np.round(mc.nudos[i], 9)), tuple(np.round(mc.nudos[j], 9)))
        km = extremos[clave]
        assert mc.modelo._barras[k]["brazos"] == mano._barras[km]["brazos"], o
        for caso in ("D", "L"):
            fg, fm = r_gen[caso].fuerzas_extremo[k], r_mano[caso].fuerzas_extremo[km]
            np.testing.assert_allclose(fg, fm, rtol=0, atol=1e-9 * max(1.0, np.abs(fm).max()))


def test_equilibrio_con_peso_propio_y_muro():
    mf = edificio(muro=True)
    mc = generar(mf)
    r = mc.modelo.resolver()
    rep = mf.repartir_cargas()
    peso = 0.0
    for lista in ("columnas", "vigas"):
        for el in mf.lista(lista):
            largo = mf.altura_columna(el["id"]) if lista == "columnas" else mf.largo_viga(el["id"])
            s = mf.elemento("secciones", el["seccion"])
            peso += PESO_HORMIGON * s["b"] * s["h"] * 1e-6 * largo
    muro = mf.lista("muros")[0]
    peso += PESO_HORMIGON * 0.2 * 5.0 * 9.0
    esperado_d = rep.total_losas("peso_propio") + rep.total_losas("permanente") + peso
    assert math.isclose(r["D"].reacciones[:, 2].sum(), esperado_d, rel_tol=1e-12)
    assert math.isclose(r["L"].reacciones[:, 2].sum(), rep.total_losas("sobrecarga"), rel_tol=1e-12)
    # Las vigas sobre el muro no son barras: su carga pasa al muro.
    sobre = [a for a in mc.avisos if a.motivo == "viga_sobre_muro"]
    assert len(sobre) == N and all(a.otro == muro["id"] for a in sobre)
    assert all(mc.barras_de("vigas", a.viga) == [] for a in sobre)
    assert "sobre el muro" in sobre[0].texto(mf)
    # El muro: una barra por piso, con su nudo en el diafragma.
    assert len(mc.barras_de("muros", muro["id"])) == N


def test_misma_respuesta_en_cm():
    """El modelo en cm da las mismas fuerzas y los momentos por 100."""
    r_m = generar(edificio("m")).modelo.resolver()
    mc_cm = generar(edificio("cm"))
    r_cm = mc_cm.modelo.resolver()
    np.testing.assert_allclose(
        r_cm["D"].reacciones[:, :3], r_m["D"].reacciones[:, :3], rtol=1e-9, atol=1e-9
    )
    np.testing.assert_allclose(
        r_cm["D"].reacciones[:, 3:], 100 * r_m["D"].reacciones[:, 3:], rtol=1e-9, atol=1e-7
    )


def test_resultados_vuelven_a_la_viga():
    mf = ModeloFisico()
    pb, p1 = mf.agregar_piso("PB", 0.0), mf.agregar_piso("P1", 3.0)
    h = mf.agregar_material("H", "hormigon", fc=25.0)
    c = mf.agregar_seccion("C", "rectangular", b=300.0, h=300.0)
    v = mf.agregar_seccion("V", "rectangular", b=200.0, h=400.0)
    for x in (0.0, 4.0, 8.0):
        mf.agregar_columna((x, 0.0), pb, p1, c, h)
    viga = mf.agregar_viga(p1, (0.0, 0.0), (8.0, 0.0), v, h)
    mc = generar(mf)
    # La viga pasa por la columna del medio: se parte en dos barras con brazos.
    barras = mc.barras_de("vigas", viga)
    assert len(barras) == 2
    o = [mc.origenes[k] for k in barras]
    assert (o[0].s0, o[0].s1, o[1].s0, o[1].s1) == (0.0, 4.0, 4.0, 8.0)
    assert all(x.brazo_i == pytest.approx(0.15) and x.brazo_j == pytest.approx(0.15) for x in o)
    r = mc.modelo.resolver()
    d = mc.diagrama(r["D"], "vigas", viga)
    assert d["s"][0] == pytest.approx(0.15) and d["s"][-1] == pytest.approx(7.85)
    assert np.all(np.diff(d["s"]) >= 0)
    # Simetría: los momentos en las caras de la columna del medio son iguales.
    mz = d["Mz"]
    assert mz[0] == pytest.approx(mz[-1], rel=1e-9)


def test_columna_girada_cruces_y_viga_sobre_viga():
    mf = ModeloFisico()
    pb, p1, p2 = (mf.agregar_piso(n, z) for n, z in (("PB", 0.0), ("P1", 3.0), ("P2", 6.0)))
    h = mf.agregar_material("H", "hormigon", fc=30.0)
    c = mf.agregar_seccion("C", "rectangular", b=600.0, h=200.0)
    v = mf.agregar_seccion("V", "rectangular", b=200.0, h=500.0)
    # Columna de dos pisos girada 90°: el ancho de 600 queda sobre Y.
    col = mf.agregar_columna((0.0, 0.0), pb, p2, c, h, angulo=90.0)
    for x, y in ((6.0, 0.0), (0.0, 6.0), (6.0, 6.0)):
        mf.agregar_columna((x, y), pb, p1, c, h)
    vx = mf.agregar_viga(p1, (0.0, 0.0), (6.0, 0.0), v, h)
    vy = mf.agregar_viga(p1, (0.0, 0.0), (0.0, 6.0), v, h)
    # Dos vigas que se cruzan en (3, 3) y una que apoya en el medio de otra.
    a = mf.agregar_viga(p1, (0.0, 6.0), (6.0, 0.0), v, h)
    b = mf.agregar_viga(p1, (0.0, 0.0), (6.0, 6.0), v, h)
    apoyada = mf.agregar_viga(p1, (3.0, 0.0), (3.0, 3.0), v, h)
    mc = generar(mf)
    # La columna pasa por P1: dos barras.
    assert len(mc.barras_de("columnas", col)) == 2
    # Brazos en la columna girada: 0.10 hacia X (su lado de 200) y 0.30 hacia Y.
    assert mc.origenes[mc.barras_de("vigas", vx)[0]].brazo_i == pytest.approx(0.10)
    assert mc.origenes[mc.barras_de("vigas", vy)[0]].brazo_i == pytest.approx(0.30)
    # Las diagonales se parten en el cruce y vx en el apoyo de la viga apoyada.
    assert len(mc.barras_de("vigas", a)) == 2
    assert len(mc.barras_de("vigas", b)) == 2
    assert len(mc.barras_de("vigas", vx)) == 2
    assert len(mc.barras_de("vigas", apoyada)) == 1
    r = mc.modelo.resolver()
    assert r["D"].reacciones[:, 2].sum() > 0


def test_materiales_por_omision():
    assert modulo_elasticidad({"tipo": "hormigon", "fc": 25.0}) == pytest.approx(23_500.0)
    assert modulo_elasticidad({"tipo": "acero", "fy": 250.0}) == 200_000.0
    assert modulo_elasticidad({"tipo": "hormigon", "fc": 25.0, "E": 30_000.0}) == 30_000.0
    assert peso_especifico({"tipo": "acero"}) == PESO_ACERO
    assert peso_especifico({"tipo": "hormigon", "peso": 24.0}) == 24.0


def test_ejemplo_de_referencia():
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "examples"))
    from edificio_fisico import armar

    mf = armar()
    mc = generar(mf)
    assert len(mc.maestros) == N
    r = mc.modelo.resolver()
    assert np.isfinite(r["D"].desplazamientos).all()
