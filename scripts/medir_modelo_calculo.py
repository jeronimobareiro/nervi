# SPDX-License-Identifier: GPL-3.0-or-later
"""Banco de tiempos de la generación del modelo de cálculo desde el edificio (#74).

Arma un edificio de ``vanos x vanos`` vanos de 6 x 5 m por piso, con columnas en
todos los cruces de ejes, vigas en todos los ejes y losas, y mide
``nervi.idealizacion.generar`` separando el reparto de las losas, la
idealización en Rust y el armado del ``Modelo3D``. Comprueba además el
equilibrio: las reacciones verticales suman el peso de las losas y de las barras.

    python scripts/medir_modelo_calculo.py                    # 10 x 10 vanos, 20 pisos
    python scripts/medir_modelo_calculo.py --vanos 4 --pisos 3 --resolver
"""

from __future__ import annotations

import argparse
import math
import time
from itertools import pairwise

from nervi import idealizacion
from nervi.fisico import ModeloFisico


def edificio(vanos: int, pisos: int) -> ModeloFisico:
    mf = ModeloFisico()
    anterior = mf.agregar_piso("PB", 0.0)
    h = mf.agregar_material("H-25", "hormigon", fc=25.0)
    c = mf.agregar_seccion("C 40x40", "rectangular", b=400.0, h=400.0)
    s = mf.agregar_seccion("V 25x50", "rectangular", b=250.0, h=500.0)
    xs = [6.0 * i for i in range(vanos + 1)]
    ys = [5.0 * j for j in range(vanos + 1)]
    for k in range(1, pisos + 1):
        p = mf.agregar_piso(f"P{k}", 3.0 * k, permanente=1.5, sobrecarga=2.0)
        for x in xs:
            for y in ys:
                mf.agregar_columna((x, y), anterior, p, c, h)
        for y in ys:
            for x1, x2 in pairwise(xs):
                mf.agregar_viga(p, (x1, y), (x2, y), s, h)
        for x in xs:
            for y1, y2 in pairwise(ys):
                mf.agregar_viga(p, (x, y1), (x, y2), s, h)
        for x1, x2 in pairwise(xs):
            for y1, y2 in pairwise(ys):
                mf.agregar_losa(p, [(x1, y1), (x2, y1), (x2, y2), (x1, y2)], 120.0, h)
        anterior = p
    return mf


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--vanos", type=int, default=10)
    ap.add_argument("--pisos", type=int, default=20)
    ap.add_argument("--repeticiones", type=int, default=5)
    ap.add_argument("--resolver", action="store_true", help="también resolver y comprobar")
    a = ap.parse_args()
    mf = edificio(a.vanos, a.pisos)
    tiempos, reparto = [], []
    for _ in range(a.repeticiones):
        t0 = time.perf_counter()
        mf.repartir_cargas()
        t1 = time.perf_counter()
        mc = idealizacion.generar(mf)
        tiempos.append(time.perf_counter() - t1)
        reparto.append(t1 - t0)
    n = len(mf.lista("columnas")), len(mf.lista("vigas")), len(mf.lista("losas"))
    print(
        f"{n[0]} columnas, {n[1]} vigas, {n[2]} losas -> {len(mc.nudos)} nudos, "
        f"{mc.n_barras} barras, {len(mc.maestros)} diafragmas"
    )
    print(
        f"generar (con su reparto): mejor {min(tiempos):.3f} s, mediana "
        f"{sorted(tiempos)[len(tiempos) // 2]:.3f} s; de eso, el reparto solo: "
        f"{min(reparto):.3f} s ({a.repeticiones} repeticiones)"
    )
    if a.resolver:
        r = mc.modelo.resolver()
        rep = mf.repartir_cargas()
        peso = 25.0 * (
            n[0] * 0.16 * 3.0 + sum(mf.largo_viga(v["id"]) for v in mf.lista("vigas")) * 0.125
        )
        d = rep.total_losas("peso_propio") + rep.total_losas("permanente") + peso
        assert math.isclose(r["D"].reacciones[:, 2].sum(), d, rel_tol=1e-10)
        print("Equilibrio vertical exacto en D.")
        # Lo que la interfaz arma después de calcular (#74): esfuerzos por elemento
        # y la escena 3D con el diagrama de momentos.
        c = r.combinar("1.2D+1.6L", idealizacion.COMBINACIONES["1.2D+1.6L"])
        t0 = time.perf_counter()
        for lista in ("vigas", "columnas", "muros"):
            mc.resumen(c, lista)
        t1 = time.perf_counter()
        try:
            from nervi.gui import escena3d
        except ImportError:
            escena3d = None
        if escena3d is not None:
            escena3d.armar_edificio(mc, mf, r, c, "M", "ambos")
        t2 = time.perf_counter()
        print(f"resumen por elemento: {t1 - t0:.3f} s; escena 3D: {t2 - t1:.3f} s")


if __name__ == "__main__":
    main()
