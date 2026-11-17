# SPDX-License-Identifier: GPL-3.0-or-later
"""Flechas, fisuración y detalle de armaduras de una viga continua (ACI 318-19).

Sigue a ``viga_hormigon_aci318.py``: diseña los dos tramos y después verifica el
servicio (flechas inmediatas y diferidas, separación de barras) y calcula
anclajes, ganchos y empalmes.

**Experimental:** nervi.design.aci318 todavía no fue revisado por un ingeniero
estructural. Modelo en kN y m; sección y materiales en mm y MPa.

Ejecutar con: python examples/viga_hormigon_servicio_aci318.py
"""

import warnings

import nervi
from nervi import design
from nervi.design import aci318
from nervi.design.aci318 import detalle, servicio

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
    v = aci318.disenar_viga(res, barra, seccion, mat, ancho_apoyo_i=250, ancho_apoyo_j=250)
    s = servicio.verificar_servicio_viga(
        res,
        m,
        barra,
        v,
        seccion,
        mat,
        permanentes=["D"],
        sobrecargas=["L1", "L2"],
        elementos="sensibles",  # tabiques que se pueden fisurar: l/480
    )
    det = detalle.detallar_viga(v, seccion, mat, continua=True, luz_libre=4750)
    print(f"Tramo {barra + 1}: {v.inferior.descripcion} abajo")
    print(f"  Mcr = {s.Mcr:.1f} kN·m, Ma(D+L) = {s.Ma_DL:.1f} kN·m, Ie/Ig = {s.Ie_DL / s.Ig:.2f}")
    print(
        f"  flechas: D {s.delta_D:.1f} mm, L {s.delta_L:.1f} mm, "
        f"diferida {s.delta_diferida:.1f} mm (λΔ = {s.lambda_delta:.2f})"
    )
    for nombre, f, adm, _ in s.limites:
        estado = "cumple" if f <= adm else "NO CUMPLE"
        print(f"  {nombre}: {f:.1f} mm ≤ {adm:.1f} mm → {estado}")
    for a in (det.inferior, det.superior):
        if a is None:
            continue
        print(
            f"  {a.posicion} {a.descripcion}: ld = {a.desarrollo.ld:.0f} mm, "
            f"gancho ldh = {a.gancho.ldh:.0f} mm, empalme clase B = {a.empalme_clase_b:.0f} mm"
        )
