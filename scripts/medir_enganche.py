# SPDX-License-Identifier: GPL-3.0-or-later
"""Banco de tiempos del enganche de puntos en planta (dibujo con el mouse, #31 y #73).

Arma una planta de ``vanos x vanos`` paños de 6 x 5 m con vigas en todos los ejes,
columnas en los cruces y bordes de losa, y mide el armado del índice y las consultas
con el cursor en lugares al azar. Compara cada consulta con el recorrido completo
(sin índice): tienen que dar exactamente lo mismo.

    python scripts/medir_enganche.py                 # 70 x 70 vanos (unos 20 000 elementos)
    python scripts/medir_enganche.py --vanos 10 --consultas 2000
"""

from __future__ import annotations

import argparse
import random
import time
from itertools import pairwise

from nervi.enganche import IndiceEnganche


def planta(vanos: int):
    xs = [6.0 * i for i in range(vanos + 1)]
    ys = [5.0 * j for j in range(vanos + 1)]
    puntos = [(x, y) for x in xs for y in ys]
    segmentos = []
    for y in ys:
        segmentos += [((a, y), (b, y)) for a, b in pairwise(xs)]
    for x in xs:
        segmentos += [((x, a), (x, b)) for a, b in pairwise(ys)]
    # Bordes de las losas (repiten las vigas, como en un modelo real).
    segmentos += segmentos[: len(segmentos) // 2]
    return puntos, segmentos, xs[-1], ys[-1]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--vanos", type=int, default=70)
    ap.add_argument("--consultas", type=int, default=20000)
    ap.add_argument(
        "--comparar", type=int, default=300, help="consultas contra el recorrido completo"
    )
    a = ap.parse_args()

    puntos, segmentos, ancho, alto = planta(a.vanos)
    t0 = time.perf_counter()
    idx = IndiceEnganche(puntos, segmentos)
    t_indice = time.perf_counter() - t0
    rnd = random.Random(1)
    cursores = [
        (rnd.uniform(-2, ancho + 2), rnd.uniform(-2, alto + 2), rnd.random() < 0.5)
        for _ in range(a.consultas)
    ]
    t0 = time.perf_counter()
    for x, y, con_anterior in cursores:
        idx.enganchar(
            x,
            y,
            0.3,
            anterior=(x - 3.1, y + 0.7) if con_anterior else None,
            paso_grilla=0.5,
            recientes=(0, 5),
        )
    t_consultas = time.perf_counter() - t0
    for x, y, con_anterior in cursores[: a.comparar]:
        kw = dict(anterior=(x - 3.1, y + 0.7) if con_anterior else None, paso_grilla=0.5)
        e1 = idx.enganchar(x, y, 0.3, **kw)
        e2 = idx.enganchar(x, y, 0.3, recorrer_todo=True, **kw)
        assert e1 == e2, (x, y, e1, e2)
    n = len(puntos) + len(segmentos)
    print(f"Planta de {a.vanos} x {a.vanos} vanos: {len(puntos)} puntos, ", end="")
    print(f"{len(segmentos)} segmentos ({n} elementos)")
    print(f"Índice armado en {t_indice * 1e3:.1f} ms")
    por_consulta = t_consultas / a.consultas * 1e6
    print(f"{a.consultas} consultas en {t_consultas * 1e3:.1f} ms: {por_consulta:.1f} µs cada una")
    print(f"{a.comparar} consultas iguales al recorrido completo")


if __name__ == "__main__":
    main()
