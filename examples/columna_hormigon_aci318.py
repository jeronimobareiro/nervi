# SPDX-License-Identifier: GPL-3.0-or-later
"""Columna de un pórtico espacial de un piso, verificada y armada según ACI 318-19.

**Experimental:** nervi.design.aci318 todavía no fue revisado por un ingeniero
estructural. Modelo en kN y m; sección y materiales en mm y MPa.

El pórtico se supone arriostrado (no desplazable), así que la esbeltez se trata
con la magnificación de momentos de §6.6.4.5.

Ejecutar con: python examples/columna_hormigon_aci318.py
"""

import warnings

import nervi
from nervi import design
from nervi.design import aci318
from nervi.secciones import rectangular

warnings.simplefilter("ignore", design.ModuloExperimentalWarning)

E, G = 2.35e7, 1.0e7
col = rectangular(0.40, 0.40)
viga = rectangular(0.25, 0.50)

m = nervi.Modelo3D()
base = [m.agregar_nudo(x, y, 0.0) for x, y in ((0, 0), (6, 0), (6, 5), (0, 5))]
arriba = [m.agregar_nudo(x, y, 4.0) for x, y in ((0, 0), (6, 0), (6, 5), (0, 5))]
columnas = [m.agregar_barra(b, a, E, G, seccion=col) for b, a in zip(base, arriba, strict=True)]
vigas = [m.agregar_barra(arriba[k], arriba[(k + 1) % 4], E, G, seccion=viga) for k in range(4)]
for n in base:
    m.apoyar(n)
for n in arriba:  # arriostramiento lateral: el pórtico no se desplaza
    m.apoyar(n, ux=True, uy=True, uz=False, rx=False, ry=False, rz=False)
for v in vigas:
    m.carga_uniforme("D", v, qz=-30.0, ejes="global")
    m.carga_uniforme("L", v, qz=-12.0, ejes="global")
m.carga_nodal("D", arriba[0], fz=-400.0)
res = m.resolver()

combs = design.generar({"D": "D", "L": "L"})
mat = aci318.Materiales(fc=25, fy=420)
seccion = aci318.SeccionColumna.rectangular(400, 400, n_y=3, n_z=3, diametro=16)

d = aci318.disenar_columna(res, columnas[0], seccion, mat, combs, permanentes=["D"])
print(f"Sección dada: {d.seccion.descripcion}, razón demanda/capacidad {d.razon:.2f}")
c = d.critica
print(f"  manda {c.combinacion}: Pu = {c.Pu:.0f} kN, Mz = {c.Mz:.1f} kN·m, My = {c.My:.1f} kN·m")
for eje, e in d.esbeltez[c.combinacion].items():
    texto = f"δ = {e.delta:.2f}" if e.esbelta else "no esbelta"
    print(f"  eje {eje}: k·lu/r = {e.esbeltez:.1f} (límite {e.limite:.1f}), {texto}")
for aviso in d.avisos:
    print("  aviso:", aviso)

armada = aci318.disenar_columna(
    res, columnas[0], seccion, mat, combs, permanentes=["D"], buscar_armadura=True
)
print(f"Armadura mínima que cumple: {armada.seccion.descripcion}, razón {armada.razon:.2f}")

curva = aci318.diagrama_interaccion(armada.seccion, mat, n=8)
print("Curva de interacción según Mz (φPn kN, φMn kN·m):")
for p, mm in zip(curva["phiPn"], curva["phiMn"], strict=True):
    print(f"  {min(p, float(curva['phiPn_max'])):8.0f} {mm:8.1f}")
