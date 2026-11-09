"""Pórtico de una crujía con carga gravitatoria y viento (unidades kN, m).

Ejecutar con: python examples/portico_simple.py
"""

import nervi

E = 2.5e7  # hormigón, kN/m²
COLUMNA = dict(E=E, A=0.30 * 0.30, I=0.30 * 0.30**3 / 12)
VIGA = dict(E=E, A=0.25 * 0.50, I=0.25 * 0.50**3 / 12)

m = nervi.Modelo()
base_izq = m.agregar_nudo(0.0, 0.0)
cabeza_izq = m.agregar_nudo(0.0, 3.0)
cabeza_der = m.agregar_nudo(6.0, 3.0)
base_der = m.agregar_nudo(6.0, 0.0)

m.agregar_barra(base_izq, cabeza_izq, **COLUMNA)
viga = m.agregar_barra(cabeza_izq, cabeza_der, **VIGA)
m.agregar_barra(base_der, cabeza_der, **COLUMNA)
m.apoyar(base_izq)
m.apoyar(base_der)

m.carga_uniforme("D", viga, qy=-20.0)
m.carga_uniforme("L", viga, qy=-10.0)
m.carga_nodal("W", cabeza_izq, fx=15.0)

res = m.resolver()
for nombre, factores in {
    "1.4D": {"D": 1.4},
    "1.2D+1.6L": {"D": 1.2, "L": 1.6},
    "1.2D+1.0L+1.0W": {"D": 1.2, "L": 1.0, "W": 1.0},
}.items():
    c = res.combinar(nombre, factores)
    d = c.diagrama(viga)
    print(
        f"{nombre:>16}:  M+ viga = {d['M'].max():7.2f} kN·m   M- viga = {d['M'].min():7.2f} kN·m   "
        f"desplazamiento lateral = {c.desplazamientos[cabeza_izq, 0] * 1000:6.2f} mm"
    )
