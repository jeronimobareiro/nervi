# SPDX-License-Identifier: GPL-3.0-or-later
"""Pórtico espacial de un piso: cuatro columnas empotradas y cuatro vigas.

Unidades: kN y m. Hormigón con E = 25 GPa y G = E / 2.4 (Poisson 0.2).
Ejes: Z vertical hacia arriba. En las vigas, el eje y local apunta hacia arriba
(la flexión por cargas gravitatorias usa Iz); en las columnas, y = -X.
"""

import numpy as np

import nervi
from nervi.secciones import rectangular

E = 2.5e7
G = E / 2.4
viga = rectangular(b=0.25, h=0.50)
columna = rectangular(b=0.40, h=0.40)
lx, ly, h = 6.0, 4.0, 3.0

m = nervi.Modelo3D()
base = [m.agregar_nudo(x, y, 0.0) for x, y in [(0, 0), (lx, 0), (lx, ly), (0, ly)]]
techo = [m.agregar_nudo(x, y, h) for x, y in [(0, 0), (lx, 0), (lx, ly), (0, ly)]]
for b, t in zip(base, techo, strict=True):
    m.apoyar(b)  # empotramiento
    m.agregar_barra(b, t, E, G, seccion=columna)
vigas = [m.agregar_barra(techo[k], techo[(k + 1) % 4], E, G, seccion=viga) for k in range(4)]

for v in vigas:
    m.carga_uniforme("D", v, qz=-18.0, ejes="global")  # kN/m hacia abajo
m.carga_nodal("W", techo[0], fx=10.0, fy=5.0)  # viento en una esquina

res = m.resolver()
for caso in ("D", "W"):
    r = res[caso]
    print(f"Caso {caso}")
    d_max = np.abs(r.desplazamientos[4:, :3]).max() * 1e3
    print(f"  desplazamiento máximo de los nudos del techo: {d_max:.3f} mm")
    print("  suma de reacciones [kN]:", r.reacciones[:, :3].sum(axis=0).round(6))
    d = r.diagrama(vigas[0])
    print(f"  viga 0: Mz en el centro = {np.interp(lx / 2, d['x'], d['Mz']):.2f} kN·m")
    t = max(np.abs(r.diagrama(k)["T"]).max() for k in range(8))
    print(f"  torsor máximo = {t:.3f} kN·m")
