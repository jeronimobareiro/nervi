# SPDX-License-Identifier: GPL-3.0-or-later
"""Modelo físico de un edificio de tres pisos (issue #73).

El mismo edificio de ``edificio_diafragma_3d.py`` (2 x 1 vanos de 6 m y 5 m,
pisos de 3 m, columnas de 40 x 40 y vigas de 25 x 50), ahora descripto como
objetos físicos: pisos con su nivel, ejes, columnas, vigas, losas macizas de
12 cm y un muro de 20 cm en el eje A. Se guarda en un ``.nrv`` (módulo
``fisico``), se vuelve a abrir y se comprueba que quedó igual.

Cargas por planta (issue #78): los pisos llevan 1,5 kN/m² de permanente y
2 kN/m² de sobrecarga, la azotea 1 kN/m² de sobrecarga; el peso propio sale del
espesor de cada losa. Se reparten a las vigas por áreas tributarias y se
comprueba el equilibrio: lo que reciben las vigas es lo que pesan las losas.

Modelo de cálculo (issue #74): se genera el pórtico espacial desde el edificio
(columnas y vigas con brazos rígidos, un diafragma por piso, empotramientos y las
cargas de las losas), se resuelve y se muestran los momentos de una viga, leídos
sobre la viga del edificio aunque el cálculo la haya partido en barras.

Coordenadas y niveles en m; secciones y espesores en mm; resistencias en MPa.
"""

import tempfile
from itertools import pairwise
from pathlib import Path

from nervi import formato
from nervi.fisico import ModeloFisico

XS = (0.0, 6.0, 12.0)
YS = (0.0, 5.0)
ALTURA_PISO = 3.0
N_PISOS = 3


def armar() -> ModeloFisico:
    mf = ModeloFisico("m")
    pisos = [mf.agregar_piso("Planta baja", 0.0)]
    pisos += [
        mf.agregar_piso(
            f"Piso {k}",
            k * ALTURA_PISO,
            permanente=1.5,
            sobrecarga=1.0 if k == N_PISOS else 2.0,
        )
        for k in range(1, N_PISOS + 1)
    ]
    for n, x in zip("ABC", XS, strict=True):
        mf.agregar_eje(n, (x, YS[0] - 1.0), (x, YS[-1] + 1.0))
    for n, y in zip("12", YS, strict=True):
        mf.agregar_eje(n, (XS[0] - 1.0, y), (XS[-1] + 1.0, y))

    h25 = mf.agregar_material("H-25", "hormigon", fc=25.0)
    col = mf.agregar_seccion("C 40x40", "rectangular", b=400.0, h=400.0)
    vig = mf.agregar_seccion("V 25x50", "rectangular", b=250.0, h=500.0)

    for abajo, arriba in pairwise(pisos):
        for n, x in zip("ABC", XS, strict=True):
            for m, y in zip("12", YS, strict=True):
                mf.agregar_columna((x, y), abajo, arriba, col, h25, nombre=f"C{n}{m}")
        k = pisos.index(arriba)
        tramos = [((x1, y), (x2, y)) for y in YS for x1, x2 in pairwise(XS)]
        tramos += [((x, YS[0]), (x, YS[1])) for x in XS]
        for j, (a, b) in enumerate(tramos, start=1):
            mf.agregar_viga(arriba, a, b, vig, h25, nombre=f"V{k}0{j}")
        for j, (x1, x2) in enumerate(pairwise(XS), start=1):
            contorno = [(x1, YS[0]), (x2, YS[0]), (x2, YS[1]), (x1, YS[1])]
            mf.agregar_losa(arriba, contorno, 120.0, h25, nombre=f"L{k}0{j}")
    mf.agregar_muro((XS[0], YS[0]), (XS[0], YS[1]), pisos[0], pisos[-1], 200.0, h25, nombre="M1")
    return mf


def main() -> None:
    mf = armar()
    print(f"{len(mf)} elementos en {len(mf.lista('pisos'))} niveles")
    for piso in mf.pisos_ordenados():
        en = mf.en_piso(piso["id"])
        area = sum(mf.area_losa(losa["id"]) for losa in en["losas"])
        print(
            f"  {piso['nombre']:12s} nivel {piso['nivel']:5.2f} m: "
            f"{len(en['columnas'])} columnas, {len(en['vigas'])} vigas, "
            f"{len(en['losas'])} losas ({area:.1f} m²)"
        )

    doc = formato.Documento.nuevo()
    doc.fisico = mf.a_json()
    with tempfile.TemporaryDirectory() as carpeta:
        ruta = Path(carpeta) / "edificio.nrv"
        formato.guardar(doc, ruta)
        otra = ModeloFisico.desde_json(formato.abrir(ruta).fisico)
    print("Guardado y vuelto a abrir igual:", otra.a_json() == mf.a_json())

    reparto = mf.repartir_cargas()
    print("Cargas de las losas repartidas a las vigas (kN):")
    for caso in reparto.casos:
        print(
            f"  {caso:12s} vigas {reparto.total(caso):8.3f}  losas {reparto.total_losas(caso):8.3f}"
        )
    piso1 = mf.pisos_ordenados()[1]["id"]
    print("Vigas del Piso 1 (resultante por caso, kN):")
    for viga in mf.en_piso(piso1)["vigas"]:
        r = [reparto.resultante(("vigas", viga["id"]), c) for c in reparto.casos]
        print(f"  {viga['nombre']}: " + "  ".join(f"{x:7.3f}" for x in r))

    mc = mf.modelo_calculo()
    print(
        f"Modelo de cálculo: {len(mc.nudos)} nudos, {mc.n_barras} barras, "
        f"{len(mc.maestros)} diafragmas, {len(mc.apoyos)} apoyos"
    )
    for aviso in mc.avisos:
        print(f"  Aviso: {aviso.texto(mf)}")
    res = mc.modelo.resolver()
    comb = res.combinar("1.2D+1.6L", {"D": 1.2, "L": 1.6})
    print(f"Reacción vertical total con D: {res['D'].reacciones[:, 2].sum():.3f} kN")
    viga = next(v for v in mf.lista("vigas") if v["nombre"] == "V102")
    d = mc.diagrama(comb, "vigas", viga["id"])
    print(
        f"V102 con 1.2D+1.6L: M en las caras {d['Mz'][0]:.2f} y {d['Mz'][-1]:.2f} kN·m, "
        f"M+ máximo {d['Mz'].max():.2f} kN·m"
    )


if __name__ == "__main__":
    main()
