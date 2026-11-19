# SPDX-License-Identifier: GPL-3.0-or-later
"""Análisis modal y por espectro de respuesta de un edificio de tres pisos.

Unidades: kN, m, s y t (kN·s²/m). Hormigón con E = 25 GPa y G = E / 2.4.
Pórtico de 2 x 1 vanos (6 m en X, 5 m en Y) y tres pisos de 3 m, con columnas
de 40 x 40 y vigas de 25 x 50. La masa sale de la carga permanente y del 25 %
de la sobrecarga (``masa_desde_casos``), más el peso propio de las barras como
masa lineal.

El espectro de diseño de este ejemplo es ilustrativo (meseta y rama
descendente 1/T): el de cada proyecto sale de la norma sísmica que corresponda
y lo arma quien diseña.
"""

import numpy as np

import nervi
from nervi.secciones import rectangular

E = 2.5e7
G = E / 2.4
GAMMA_HORMIGON = 24.0  # kN/m³
G_ACEL = 9.80665  # m/s²
viga = rectangular(b=0.25, h=0.50)
columna = rectangular(b=0.40, h=0.40)
xs, ys, h, pisos = (0.0, 6.0, 12.0), (0.0, 5.0), 3.0, 3

m = nervi.Modelo3D()
nudo = {}
for p in range(pisos + 1):
    for i, x in enumerate(xs):
        for j, y in enumerate(ys):
            nudo[p, i, j] = m.agregar_nudo(x, y, h * p)
            if p == 0:
                m.apoyar(nudo[p, i, j])


def barra(a, b, sec):
    k = m.agregar_barra(a, b, E, G, seccion=sec)
    m.masa_lineal(k, GAMMA_HORMIGON * sec["A"] / G_ACEL)  # peso propio como masa
    return k


for p in range(1, pisos + 1):
    for i in range(len(xs)):
        for j in range(len(ys)):
            barra(nudo[p - 1, i, j], nudo[p, i, j], columna)
            if i + 1 < len(xs):
                v = barra(nudo[p, i, j], nudo[p, i + 1, j], viga)
                m.carga_uniforme("D", v, qz=-20.0, ejes="global")
                m.carga_uniforme("L", v, qz=-8.0, ejes="global")
            if j + 1 < len(ys):
                v = barra(nudo[p, i, j], nudo[p, i, j + 1], viga)
                m.carga_uniforme("D", v, qz=-15.0, ejes="global")
                m.carga_uniforme("L", v, qz=-6.0, ejes="global")

m.masa_desde_casos({"D": 1.0, "L": 0.25}, gravedad=G_ACEL)
modal = m.modal(n_modos=9)
print(modal.tabla())
print("Masa total [t]:", np.round(modal.masa_total, 2))

# Espectro ilustrativo: Sa = 0.6 g en la meseta hasta T = 0.5 s, luego 0.3 g / T.
periodos = np.linspace(0.0, 4.0, 81)
sa = np.where(periodos <= 0.5, 0.6, 0.3 / np.maximum(periodos, 1e-9)) * G_ACEL
espectro = np.column_stack([periodos, sa])

for direccion in ("X", "Y"):
    r = modal.espectro(espectro, direccion=direccion, amortiguamiento=0.05, combinacion="CQC")
    techo = nudo[pisos, 0, 0]
    k = "XY".index(direccion)
    print(
        f"Sismo en {direccion}: cortante basal = {r.cortante_basal[k]:.1f} kN, "
        f"desplazamiento del techo = {1000 * r.desplazamientos[techo, k]:.2f} mm"
    )
    d = r.diagrama(0)  # primera columna, valores absolutos combinados
    print(f"  columna 0: |Mz| máx = {d['Mz'].max():.1f} kN·m, |My| máx = {d['My'].max():.1f} kN·m")
