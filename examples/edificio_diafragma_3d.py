# SPDX-License-Identifier: GPL-3.0-or-later
"""Edificio de tres pisos con diafragma rígido por piso y brazos rígidos.

Unidades: kN, m, s y t (kN·s²/m). El mismo edificio de
``modal_espectro_3d.py`` (2 x 1 vanos de 6 m y 5 m, pisos de 3 m, columnas de
40 x 40 y vigas de 25 x 50), ahora modelado como un edificio real:

* cada losa es un **diafragma rígido** en su plano, con el nudo maestro en el
  centroide del piso; la masa de cada piso queda concentrada en su maestro;
* las vigas tienen **brazos rígidos** de media columna (0.20 m) en cada
  extremo, así que su luz flexible y sus momentos de diseño son a la cara de
  la columna.

Se imprime la masa y el centro de masa de cada piso, la tabla modal (ya sin
los modos locales verticales de las vigas) y las derivas de piso del sismo en X
y en Y con un espectro ilustrativo; el de cada proyecto sale de su norma.
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
media_columna = 0.20

m = nervi.Modelo3D()
nudo = {}
for p in range(pisos + 1):
    for i, x in enumerate(xs):
        for j, y in enumerate(ys):
            nudo[p, i, j] = m.agregar_nudo(x, y, h * p)
            if p == 0:
                m.apoyar(nudo[p, i, j])


def barra(a, b, sec, brazo=0.0):
    k = m.agregar_barra(a, b, E, G, seccion=sec, brazo_i=brazo, brazo_j=brazo)
    m.masa_lineal(k, GAMMA_HORMIGON * sec["A"] / G_ACEL)  # peso propio como masa
    return k


for p in range(1, pisos + 1):
    for i in range(len(xs)):
        for j in range(len(ys)):
            barra(nudo[p - 1, i, j], nudo[p, i, j], columna)
            if i + 1 < len(xs):
                v = barra(nudo[p, i, j], nudo[p, i + 1, j], viga, media_columna)
                m.carga_uniforme("D", v, qz=-20.0, ejes="global")
                m.carga_uniforme("L", v, qz=-8.0, ejes="global")
            if j + 1 < len(ys):
                v = barra(nudo[p, i, j], nudo[p, i, j + 1], viga, media_columna)
                m.carga_uniforme("D", v, qz=-15.0, ejes="global")
                m.carga_uniforme("L", v, qz=-6.0, ejes="global")

# Un diafragma por piso, con el maestro creado en el centroide.
maestros = [
    m.diafragma([nudo[p, i, j] for i in range(len(xs)) for j in range(len(ys))])
    for p in range(1, pisos + 1)
]

m.masa_desde_casos({"D": 1.0, "L": 0.25}, gravedad=G_ACEL)
modal = m.modal(n_modos=9)
for p, d in enumerate(modal.diafragmas, start=1):
    x, y = d["centro_masa"]
    print(
        f"Piso {p}: masa = {d['masa'][0]:.2f} t, centro de masa = ({x:.2f}, {y:.2f}) m, "
        f"inercia = {d['inercia']:.1f} t·m²"
    )
print(modal.tabla())

periodos = np.linspace(0.0, 4.0, 81)
sa = np.where(periodos <= 0.5, 0.6, 0.3 / np.maximum(periodos, 1e-9)) * G_ACEL
espectro = np.column_stack([periodos, sa])
for direccion in ("X", "Y"):
    r = modal.espectro(espectro, direccion=direccion)
    der = r.derivas()
    k = "XY".index(direccion)
    print(f"Sismo en {direccion}: cortante basal = {r.cortante_basal[k]:.1f} kN")
    for p in range(pisos):
        print(
            f"  piso {p + 1}: u = {1000 * der['u' + 'xy'[k]][p]:.2f} mm, "
            f"deriva = {der['deriva_' + 'xy'[k]][p]:.5f}"
        )

# Momento de una viga del primer piso a la cara de la columna, con D + L.
estatico = m.resolver()
viga_1 = 1  # primera viga en X del piso 1
comb = estatico.combinar("D+L", {"D": 1.0, "L": 1.0})
d = comb.diagrama(viga_1)
print(
    f"Viga del piso 1: luz flexible = {d['x'][-1]:.2f} m, "
    f"Mz en la cara = {d['Mz'][0]:.1f} kN·m, Mz máximo = {d['Mz'].max():.1f} kN·m"
)
