# SPDX-License-Identifier: GPL-3.0-or-later
"""Banco de tiempos del reparto de las losas a sus vigas (cargas por planta, #78).

Arma un edificio de ``vanos x vanos`` losas de 6 x 5 m por piso, con vigas en todos
los ejes, y mide ``ModeloFisico.repartir_cargas``. Comprueba además el equilibrio
global: lo que reciben las vigas es lo que pesan las losas.

    python scripts/medir_reparto.py                    # 10 x 10 vanos, 20 pisos
    python scripts/medir_reparto.py --vanos 4 --pisos 3
"""

from __future__ import annotations

import argparse
import math
import time
from itertools import pairwise

from nervi.fisico import ModeloFisico


def edificio(vanos: int, pisos: int) -> ModeloFisico:
    mf = ModeloFisico()
    mf.agregar_piso("PB", 0.0)
    h = mf.agregar_material("H-25", "hormigon", fc=25.0)
    s = mf.agregar_seccion("V 25x50", "rectangular", b=250.0, h=500.0)
    xs = [6.0 * i for i in range(vanos + 1)]
    ys = [5.0 * j for j in range(vanos + 1)]
    for k in range(1, pisos + 1):
        p = mf.agregar_piso(f"P{k}", 3.0 * k, permanente=1.5, sobrecarga=2.0)
        for y in ys:
            for x1, x2 in pairwise(xs):
                mf.agregar_viga(p, (x1, y), (x2, y), s, h)
        for x in xs:
            for y1, y2 in pairwise(ys):
                mf.agregar_viga(p, (x, y1), (x, y2), s, h)
        for x1, x2 in pairwise(xs):
            for y1, y2 in pairwise(ys):
                mf.agregar_losa(p, [(x1, y1), (x2, y1), (x2, y2), (x1, y2)], 120.0, h)
    return mf


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--vanos", type=int, default=10)
    ap.add_argument("--pisos", type=int, default=20)
    ap.add_argument("--repeticiones", type=int, default=5)
    a = ap.parse_args()
    mf = edificio(a.vanos, a.pisos)
    n_losas, n_vigas = len(mf.lista("losas")), len(mf.lista("vigas"))
    tiempos = []
    for _ in range(a.repeticiones):
        t0 = time.perf_counter()
        r = mf.repartir_cargas()
        tiempos.append(time.perf_counter() - t0)
    for caso in r.casos:
        assert math.isclose(r.total(caso), r.total_losas(caso), rel_tol=1e-12), caso
    print(
        f"{n_losas} losas, {n_vigas} vigas, {len(r.tramos)} tramos de carga: "
        f"mejor {min(tiempos):.3f} s, mediana {sorted(tiempos)[len(tiempos) // 2]:.3f} s "
        f"({a.repeticiones} repeticiones). Equilibrio exacto en {len(r.casos)} casos."
    )


if __name__ == "__main__":
    main()
