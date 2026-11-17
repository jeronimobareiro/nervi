# SPDX-License-Identifier: GPL-3.0-or-later
"""Viga continua de hormigón armado de dos tramos, diseñada según ACI 318-19.

**Experimental:** nervi.design.aci318 todavía no fue revisado por un ingeniero
estructural. Modelo en kN y m; sección y materiales en mm y MPa.

Ejecutar con: python examples/viga_hormigon_aci318.py
"""

import warnings

import nervi
from nervi import design
from nervi.design import aci318

warnings.simplefilter("ignore", design.ModuloExperimentalWarning)

seccion = aci318.SeccionRectangular(b=250, h=500, recubrimiento=40, d_estribo=8)
mat = aci318.Materiales(fc=25, fy=420)

m = nervi.Modelo()
nudos = [m.agregar_nudo(x, 0.0) for x in (0.0, 5.0, 10.0)]
props = dict(E=2.35e7, A=0.25 * 0.50, I=0.25 * 0.50**3 / 12)
tramos = [m.agregar_barra(nudos[k], nudos[k + 1], **props) for k in range(2)]
m.apoyar(nudos[0], rz=False)
m.apoyar(nudos[1], ux=False, rz=False)
m.apoyar(nudos[2], ux=False, rz=False)
for k, barra in enumerate(tramos):
    m.carga_uniforme("D", barra, qy=-18.0)
    m.carga_uniforme(f"L{k + 1}", barra, qy=-8.0)

combs = design.generar({"D": "D", "L1": "L", "L2": "L"}, alternar_sobrecarga=True)
res = m.resolver(combinaciones=design.como_diccionario(combs))

for barra in tramos:
    # Apoyos de 250 mm de ancho: la sección crítica a cortante queda a d de su cara.
    v = aci318.disenar_viga(res, barra, seccion, mat, ancho_apoyo_i=250, ancho_apoyo_j=250)
    print(f"Tramo {barra + 1}")
    print(f"  M+ = {v.Mu_pos:7.1f} kN·m ({v.Mu_pos_comb}) → {v.inferior.descripcion}")
    if v.superior is not None:
        print(f"  M- = {v.Mu_neg:7.1f} kN·m ({v.Mu_neg_comb}) → {v.superior.descripcion}")
    estribos = v.estribos.descripcion if v.estribos else "sin estribos por cálculo"
    print(f"  Vu = {v.Vu:7.1f} kN en x = {v.x_Vu:.2f} m ({v.Vu_comb}) → {estribos}")
