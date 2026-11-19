# SPDX-License-Identifier: GPL-3.0-or-later
"""Banco de tiempos del diseño de hormigón armado (etapa Diseño).

Arma un pórtico plano de ``vanos x pisos`` con cargas D, L y W, lo resuelve con
las combinaciones de resistencia de ACI 318-19 y mide ``nervi.design.proyecto.disenar``.
Es el pórtico de referencia de la regla de rendimiento del proyecto: todo cambio
que toque cálculo informa en el PR el tiempo antes y después.

    python scripts/medir_diseno.py                 # 6 vanos x 10 pisos (130 barras)
    python scripts/medir_diseno.py --vanos 3 --pisos 4
    python scripts/medir_diseno.py --guardar ref.json    # armaduras y relaciones
    python scripts/medir_diseno.py --comparar ref.json   # falla si cambian

``--comparar`` exige la misma armadura en cada elemento y relaciones con una
diferencia relativa menor que ``--tolerancia``.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import warnings

import nervi
from nervi import formato
from nervi.design import combinaciones, proyecto


def portico(vanos: int, pisos: int) -> tuple[formato.Documento, dict]:
    """Pórtico de ``vanos`` de 6 m y ``pisos`` de 3 m; columnas de 40 x 40 cm, vigas de 25 x 50."""
    E = 2.5e7
    col = dict(E=E, A=0.4 * 0.4, I=0.4**4 / 12)
    viga = dict(E=E, A=0.25 * 0.5, I=0.25 * 0.5**3 / 12)
    m = nervi.Modelo()
    n = {}
    for i in range(vanos + 1):
        for j in range(pisos + 1):
            n[i, j] = m.agregar_nudo(6.0 * i, 3.0 * j)
    for i in range(vanos + 1):
        m.apoyar(n[i, 0])
        for j in range(pisos):
            m.agregar_barra(n[i, j], n[i, j + 1], **col)
    for j in range(1, pisos + 1):
        for i in range(vanos):
            v = m.agregar_barra(n[i, j], n[i + 1, j], **viga)
            m.carga_uniforme("D", v, qy=-20.0)
            m.carga_uniforme("L", v, qy=-10.0)
        m.carga_nodal("W", n[0, j], fx=15.0)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        combs = combinaciones.como_diccionario(
            combinaciones.generar({"D": "D", "L": "L", "W": "W"})
        )
    return formato.Documento.desde_modelo(m, combs), combs


def medir(vanos: int, pisos: int) -> tuple[list, dict]:
    doc, combs = portico(vanos, pisos)
    t0 = time.perf_counter()
    m, idx = formato.construir_modelo(doc.modelo)
    res = m.resolver(combinaciones=combs)
    t1 = time.perf_counter()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        salida = proyecto.disenar(doc.modelo, None, res, idx)
    t2 = time.perf_counter()
    columnas = sum(1 for r in salida if r.elemento.tipo == "columna")
    tiempos = {
        "barras": len(salida),
        "vigas": len(salida) - columnas,
        "columnas": columnas,
        "combinaciones": len(combs),
        "analisis_s": t1 - t0,
        "diseno_s": t2 - t1,
    }
    return salida, tiempos


def resumen(salida: list) -> list[dict]:
    return [
        {
            "barra": r.elemento.barra,
            "tipo": r.elemento.tipo,
            "estado": r.estado,
            "armadura": r.armadura,
            "relaciones": [v.relacion for v in r.verificaciones],
        }
        for r in salida
    ]


def comparar(actual: list[dict], referencia: list[dict], tol: float) -> list[str]:
    errores = []
    if len(actual) != len(referencia):
        return [f"{len(actual)} elementos; la referencia tiene {len(referencia)}"]
    for a, r in zip(actual, referencia, strict=True):
        b = a["barra"]
        for clave in ("tipo", "estado", "armadura"):
            if a[clave] != r[clave]:
                errores.append(f"barra {b}: {clave} {a[clave]!r} ≠ {r[clave]!r}")
        if len(a["relaciones"]) != len(r["relaciones"]):
            errores.append(f"barra {b}: cambió la cantidad de verificaciones")
            continue
        for k, (x, y) in enumerate(zip(a["relaciones"], r["relaciones"], strict=True)):
            if abs(x - y) > tol * max(abs(y), 1.0):
                errores.append(f"barra {b}, verificación {k}: {x:.9g} ≠ {y:.9g}")
    return errores


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--vanos", type=int, default=6)
    p.add_argument("--pisos", type=int, default=10)
    p.add_argument("--guardar", help="guarda armaduras y relaciones en este JSON")
    p.add_argument("--comparar", help="compara con un JSON guardado antes")
    p.add_argument("--tolerancia", type=float, default=1e-6)
    a = p.parse_args(argv)
    salida, t = medir(a.vanos, a.pisos)
    print(
        f"{t['barras']} barras ({t['vigas']} vigas, {t['columnas']} columnas), "
        f"{t['combinaciones']} combinaciones: análisis {t['analisis_s']:.3f} s, "
        f"diseño {t['diseno_s']:.2f} s"
    )
    datos = resumen(salida)
    if a.guardar:
        with open(a.guardar, "w", encoding="utf-8") as f:
            json.dump({"tiempos": t, "elementos": datos}, f, ensure_ascii=False, indent=1)
    if a.comparar:
        with open(a.comparar, encoding="utf-8") as f:
            ref = json.load(f)
        errores = comparar(datos, ref["elementos"], a.tolerancia)
        for e in errores:
            print(e)
        print("igual a la referencia" if not errores else f"{len(errores)} diferencias")
        return 1 if errores else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
