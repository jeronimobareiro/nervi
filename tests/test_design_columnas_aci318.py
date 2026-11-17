# SPDX-License-Identifier: GPL-3.0-or-later
"""Columnas de hormigón armado según ACI 318-19 (#24, experimental).

Los valores esperados salen de:

- Cálculos a mano en la prueba, paso a paso, con las expresiones de ACI 318-19
  que cita el módulo (§6.2.5, §6.6.4, §19.2.2, §21.2.2, §22.2, §22.4).
- Una referencia independiente para la flexión biaxial: resultantes calculadas
  con concreteproperties 0.8.0 (MIT, https://github.com/robbievanleeuwen/concrete-properties)
  con el mismo bloque rectangular de §22.2.2.4 y acero elastoplástico, fuera del
  CI (no es dependencia de Nervi). Ese programa integra las barras como áreas y
  Nervi como puntos; se eligieron estados en los que ninguna barra queda cortada
  por el borde del bloque, donde los dos métodos coinciden.

No se transcriben ejemplos de libros: falta compararlos con ejemplos publicados
(ver la bitácora).
"""

import math

import numpy as np
import pytest

import nervi
from nervi import design
from nervi.design import aci318
from nervi.design.aci318 import columna as col

pytestmark = pytest.mark.filterwarnings("ignore::nervi.design.ModuloExperimentalWarning")

MAT = aci318.Materiales(fc=28, fy=420)
FC85 = 0.85 * 28
EPS_TY = 420 / 200_000
AB20 = math.pi * 20**2 / 4


def rel(esperado, tol=1e-6):
    return pytest.approx(esperado, rel=tol)


def cuadrada():
    """400 × 400 mm, 8Ø20 (3 por cara), barras a 40 + 10 + 10 = 60 mm del borde."""
    return aci318.SeccionColumna.rectangular(400, 400, 3, 3, 20)


# --- Sección -------------------------------------------------------------------


def test_geometria_rectangular():
    s = cuadrada()
    assert s.Ag == rel(160_000)
    assert s.barras.shape == (8, 3)
    assert s.Ast == rel(8 * AB20)
    assert s.cuantia == rel(8 * AB20 / 160_000)
    assert sorted({abs(round(v, 6)) for v in s.barras[:, 0]}) == [0.0, 140.0]
    assert s.Iz == rel(400**4 / 12) and s.Iy == rel(400**4 / 12)
    assert s.radio_giro("z") == rel(120.0)  # 0.30 h (§6.2.5.2)
    assert s.separacion_libre() == rel(140 - 20)
    assert s.descripcion == "8Ø20 (ρ = 1.57 %)"
    r = aci318.SeccionColumna.rectangular(300, 500, 2, 4, 25)
    assert r.barras.shape == (8, 3)
    assert r.altura("z") == rel(300) and r.altura("y") == rel(500)


def test_geometria_circular():
    s = aci318.SeccionColumna.circular(500, 8, 20)
    assert s.Ag == rel(math.pi * 250**2, 1e-9)  # polígono de igual área
    assert s.inercia("z") == rel(math.pi * 500**4 / 64, 1e-3)
    assert s.radio_giro("y") == rel(125.0)  # 0.25 D (§6.2.5.2)
    radios = np.hypot(s.barras[:, 0], s.barras[:, 1])
    assert radios == pytest.approx(np.full(8, 250 - 60))


def test_secciones_invalidas():
    with pytest.raises(ValueError, match="convexo"):
        aci318.SeccionColumna([(0, 0), (100, 0), (50, 20), (100, 100), (0, 100)], [(50, 50, 16)])
    with pytest.raises(ValueError, match="fuera"):
        aci318.SeccionColumna([(0, 0), (100, 0), (100, 100), (0, 100)], [(150, 50, 16)])
    with pytest.raises(ValueError, match="2 barras"):
        aci318.SeccionColumna.rectangular(400, 400, 1, 3, 20)
    with pytest.raises(ValueError, match="4 barras"):
        aci318.SeccionColumna.circular(400, 3, 20)


def test_phi_compresion():
    assert aci318.phi_compresion(0.001, 420) == 0.65
    assert aci318.phi_compresion(0.001, 420, zunchada=True) == 0.75
    assert aci318.phi_compresion(EPS_TY + 0.003, 420) == 0.90
    assert aci318.phi_compresion(EPS_TY + 0.0015, 420) == pytest.approx(0.775)
    assert aci318.phi_compresion(EPS_TY + 0.0015, 420, zunchada=True) == pytest.approx(0.825)


# --- Resistencia de la sección ----------------------------------------------------


def test_resistencias_axiales():
    s = cuadrada()
    ast = 8 * AB20
    po = FC85 * (160_000 - ast) + 420 * ast  # §22.4.2.2
    ax = aci318.resistencia_axial(s, MAT)
    assert ax.Po == rel(po / 1e3)
    assert ax.phiPn_max == rel(0.65 * 0.80 * po / 1e3)  # §22.4.2.1, estribos
    assert ax.phiPnt == rel(0.90 * 420 * ast / 1e3)  # §22.4.3.1
    zun = aci318.resistencia_axial(s, MAT, zunchada=True)
    assert zun.phiPn_max == rel(0.75 * 0.85 * po / 1e3)


def test_limites_compresion_y_traccion_pura():
    s = cuadrada()
    geo = col._geo(s)
    ax = aci318.resistencia_axial(s, MAT)
    # Eje neutro muy lejos: toda la sección comprimida, todas las barras fluyen.
    pn, mz, my, _, phi = col._seccion_en(geo, MAT, 0.3, 1e9, False)
    assert pn / 1e3 == rel(ax.Po, 1e-6)
    assert abs(mz) < 1e-3 * ax.Po * 1e3 and abs(my) < 1e-3 * ax.Po * 1e3
    assert phi == 0.65
    # Eje neutro casi en el borde: todo el acero en tracción y nada de hormigón.
    pn, _, _, _, phi = col._seccion_en(geo, MAT, 0.3, 1e-6, False)
    assert pn / 1e3 == rel(-ax.Pnt, 1e-6)
    assert phi == 0.90


def test_punto_balanceado_a_mano():
    """Flexión según y (θ = 0) con εt = εty en la capa más traccionada."""
    s = cuadrada()
    dt = 400 - 60
    c = dt * 0.003 / (0.003 + EPS_TY)  # 200 mm
    a = 0.85 * c
    # Capa comprimida (3 barras a 60 mm), capa media (2 barras a 200 mm) y traccionada.
    fs_comp = min(420.0, 200_000 * 0.003 * (c - 60) / c)
    fs_med = 200_000 * 0.003 * (c - 200) / c  # cero: el eje neutro pasa por la capa media
    cc = FC85 * 400 * a
    f_comp = 3 * AB20 * (fs_comp - FC85)
    f_med = 2 * AB20 * (fs_med - (FC85 if 200 <= a else 0.0))
    f_trac = -3 * AB20 * 420
    p = cc + f_comp + f_med + f_trac
    m = cc * (200 - a / 2) + f_comp * 140 - f_trac * 140
    pn, mz, my, eps_t, phi = col._seccion_en(col._geo(s), MAT, 0.0, c, False)
    assert pn == rel(p) and mz == rel(m)
    assert abs(my) < 1e-6 * m
    assert eps_t == rel(EPS_TY) and phi == rel(0.65)


def test_flexion_pura_a_mano():
    """Pu = 0 y Mz solo, 4Ø20 en las esquinas: equilibrio resuelto a mano."""
    s = aci318.SeccionColumna.rectangular(400, 400, 2, 2, 20)
    as_ = 2 * AB20
    # 0.85 f'c b β1 c + As'·600 (c − 60)/c − As fy = 0, con la capa superior elástica
    # y por debajo del bloque (a < 60 mm, no desplaza hormigón): cuadrática en c.
    a2 = FC85 * 400 * 0.85
    a1 = as_ * 600 - as_ * 420
    a0 = -as_ * 600 * 60
    c = (-a1 + math.sqrt(a1**2 - 4 * a2 * a0)) / (2 * a2)
    fs_sup = 600 * (c - 60) / c
    a = 0.85 * c
    assert abs(fs_sup) < 420 and a < 60  # comprobación de las hipótesis
    mn = FC85 * 400 * a * (200 - a / 2) + as_ * fs_sup * 140 + as_ * 420 * 140
    eps_t = 0.003 * (340 - c) / c
    phi = aci318.phi_compresion(eps_t, 420)
    assert phi == 0.90
    v = aci318.verificar_columna(s, MAT, Pu=0.0, Mz=100.0)
    assert v.phiMn[0] == rel(phi * mn / 1e6, 1e-6)
    v = aci318.verificar_columna(s, MAT, Pu=0.0, My=-100.0)
    assert v.phiMn[0] == rel(phi * mn / 1e6, 1e-6)


@pytest.mark.parametrize(
    ("theta", "dn", "n", "mx", "my"),
    [
        (0.0, 150.0, 580042.957, 304966008.7, 0.0),
        (0.4, 250.0, 1026233.508, 323454194.7, -32153686.9),
        (-2.0, 300.0, 2231119.936, -166004365.9, 132212948.2),
        (2.7, 600.0, 4078920.446, -84535054.5, -18818328.1),
    ],
)
def test_biaxial_contra_concreteproperties_rectangular(theta, dn, n, mx, my):
    # concreteproperties: 300 (x) × 500 (y), 3 barras arriba y abajo y 1 por lado,
    # Ø20 a 50 mm libres del borde. Su ángulo del eje neutro es θ; en Nervi la
    # fibra más comprimida está en θ + 90°.
    s = aci318.SeccionColumna.rectangular(300, 500, 3, 3, 20)
    pn, mz, my_, _, _ = col._seccion_en(col._geo(s), MAT, theta + math.pi / 2, dn, False)
    assert pn == rel(n, 1e-4)
    assert math.hypot(mz, my_) == rel(math.hypot(mx, my), 1e-4)


def test_biaxial_contra_concreteproperties_circular():
    s = aci318.SeccionColumna.circular(500, 8, 20)
    pn, mz, my, _, _ = col._seccion_en(col._geo(s), MAT, 0.7 + math.pi / 2, 350.0, False)
    assert pn == rel(3267229.533, 5e-4)
    assert math.hypot(mz, my) == rel(math.hypot(233283386.1, 195626757.9), 5e-4)


def test_biaxial_contra_fibras():
    """Integración independiente con una malla fina de fibras de hormigón."""
    s = aci318.SeccionColumna.rectangular(300, 500, 3, 4, 20)
    n = 600
    y = (np.arange(n) + 0.5) / n * 300 - 150
    z = (np.arange(n) + 0.5) / n * 500 - 250
    yy, zz = np.meshgrid(y, z)
    da = 300 * 500 / n**2
    for theta, c in ((0.7, 220.0), (2.2, 330.0), (-1.0, 140.0)):
        u = (math.cos(theta), math.sin(theta))
        smax = max(abs(150 * u[0]) + abs(250 * u[1]), 0)
        prof = smax - (yy * u[0] + zz * u[1])
        bloque = prof <= 0.85 * c
        cc = FC85 * da * bloque.sum()
        mz = FC85 * da * (yy * bloque).sum()
        my = -FC85 * da * (zz * bloque).sum()
        for yb, zb, db in s.barras:
            pr = smax - (yb * u[0] + zb * u[1])
            f = (
                math.pi
                * db**2
                / 4
                * (max(-420, min(420, 600 * (c - pr) / c)) - (FC85 if pr <= 0.85 * c else 0))
            )
            cc += f
            mz += f * yb
            my -= f * zb
        pn, mzn, myn, _, _ = col._seccion_en(col._geo(s), MAT, theta, c, False)
        assert pn == rel(cc, 2e-3)
        assert math.hypot(mzn, myn) == rel(math.hypot(mz, my), 2e-3)


def test_simetria_y_direccion():
    s = cuadrada()
    v = aci318.verificar_columna(s, MAT, [800, 800, 800], [100, 0, 0], [0, 100, -100])
    assert v.phiMn[1] == rel(v.phiMn[0], 1e-6)
    assert v.phiMn[2] == rel(v.phiMn[0], 1e-6)
    # En diagonal la capacidad es menor que según los ejes (sección cuadrada).
    d = aci318.verificar_columna(s, MAT, 800, 100, 100)
    assert d.phiMn[0] < v.phiMn[0]
    # En una sección circular casi no depende de la dirección: solo por la posición
    # discreta de las barras (menos de 1 % con 12 barras).
    c = aci318.SeccionColumna.circular(500, 12, 20)
    r = aci318.verificar_columna(c, MAT, [1500, 1500], [100, 70], [0, 71.4])
    assert r.phiMn[1] == rel(r.phiMn[0], 1e-2)
    # Girar la dirección 30° (lo que separa dos barras) es una simetría exacta.
    t = math.radians(30)
    r = aci318.verificar_columna(
        c, MAT, [1500, 1500], [100, 100 * math.cos(t)], [0, 100 * math.sin(t)]
    )
    assert r.phiMn[1] == rel(r.phiMn[0], 1e-6)


def test_razones_de_verificacion():
    s = cuadrada()
    ax = aci318.resistencia_axial(s, MAT)
    v = aci318.verificar_columna(s, MAT, [ax.phiPn_max * 1.1, -ax.phiPnt * 0.5, 0.0], 0.0, 0.0)
    assert v.razon[0] == rel(1.1) and v.razon[1] == rel(0.5) and v.razon[2] == 0.0
    # Con momento y una carga mayor que la resistencia sin tope: razón infinita.
    v = aci318.verificar_columna(s, MAT, ax.Po, 10.0)
    assert math.isinf(v.razon[0]) and not v.cumple
    # Sobre la curva de interacción, la razón vale 1.
    d = aci318.diagrama_interaccion(s, MAT, angulo=0.4, n=12)
    k = 6
    m = d["phiMn"][k]
    v = aci318.verificar_columna(s, MAT, d["phiPn"][k], m * math.cos(0.4), m * math.sin(0.4))
    assert v.razon_momento[0] == rel(1.0, 1e-6)


def test_diagrama_de_interaccion():
    s = cuadrada()
    ax = aci318.resistencia_axial(s, MAT)
    d = aci318.diagrama_interaccion(s, MAT, n=30)
    assert d["phiPn"][0] == rel(-ax.phiPnt) and d["phiMn"][0] == 0.0
    assert d["phiPn"][-1] == rel(0.65 * ax.Po) and d["phiMn"][-1] == 0.0
    assert float(d["phiPn_max"]) == rel(ax.phiPn_max)
    assert np.all(np.diff(d["phiPn"]) > 0)
    assert np.all(d["phi"] >= 0.65) and np.all(d["phi"] <= 0.90)
    # El momento máximo está cerca del punto balanceado (φ = 0.65 a cada lado).
    k = int(np.argmax(d["phiMn"]))
    assert 0 < k < d["phiPn"].size - 1


# --- Esbeltez -------------------------------------------------------------------


def test_funciones_de_esbeltez():
    assert aci318.limite_esbeltez(-1.0) == rel(22.0)  # curvatura simple
    assert aci318.limite_esbeltez(0.5) == 40.0  # 34 + 6 > 40
    assert aci318.limite_esbeltez(0.25, desplazable=True) == 22.0
    assert aci318.coeficiente_cm(-1.0) == rel(1.0)
    assert aci318.coeficiente_cm(0.5) == rel(0.4)
    assert aci318.coeficiente_cm(0.5, cargas_transversales=True) == 1.0
    assert aci318.modulo_hormigon(MAT) == rel(4700 * math.sqrt(28))
    ei = aci318.rigidez_efectiva(MAT, 1e9, 0.6)
    assert ei == rel(0.4 * 4700 * math.sqrt(28) * 1e9 / 1.6)
    assert aci318.carga_critica(ei, 1.0, 3000) == rel(math.pi**2 * ei / 3000**2 / 1e3)
    assert aci318.factor_magnificacion(100, 1000, 0.6) == 1.0
    assert aci318.factor_magnificacion(600, 1000, 1.0) == rel(1 / (1 - 0.8))
    assert math.isinf(aci318.factor_magnificacion(750, 1000, 1.0))


def columna_biarticulada(m_sup=50.0, m_inf=-50.0, axil=1000.0, altura=6.0):
    """Columna vertical articulada en los dos extremos y arriostrada (no desplazable).

    Momentos nodales alrededor de Y global en los extremos: con ``m_sup = -m_inf``
    la barra queda en curvatura simple con momento constante.
    """
    m = nervi.Modelo3D()
    a, b = m.agregar_nudo(0, 0, 0), m.agregar_nudo(0, 0, altura)
    barra = m.agregar_barra(a, b, E=2.5e7, G=1e7, A=0.16, Iy=2e-3, Iz=2e-3, J=3e-3)
    m.apoyar(a, rx=False, ry=False, rz=True)
    m.apoyar(b, uz=False, rx=False, ry=False, rz=False)
    m.carga_nodal("D", b, fz=-axil, my=m_sup)
    m.carga_nodal("D", a, my=m_inf)
    return m.resolver(), barra


def test_magnificacion_curvatura_simple_a_mano():
    res, barra = columna_biarticulada()
    r = aci318.disenar_columna(res, barra, cuadrada(), MAT, {"U": {"D": 1.4}}, permanentes=["D"])
    e = r.esbeltez["U"]["z"]
    pu, m2 = 1400.0, 70.0
    assert e.esbeltez == rel(6000 / 120) and e.limite == rel(22.0) and e.esbelta
    assert e.m1_m2 == rel(-1.0) and abs(e.M2) == rel(m2)
    assert e.Cm == rel(1.0) and e.beta_dns == 1.0
    ei = 0.4 * 4700 * math.sqrt(28) * 400**4 / 12 / 2  # βdns = 1
    pc = math.pi**2 * ei / 6000**2 / 1e3
    delta = 1 / (1 - pu / (0.75 * pc))
    assert e.Pc == rel(pc) and e.delta == rel(delta)
    assert abs(e.Mc) == rel(delta * m2) and not e.usa_m2_min
    # Fuera del plano no hay momento: manda el mínimo de §6.6.4.5.4 con Cm = 1.
    ey = r.esbeltez["U"]["y"]
    assert ey.usa_m2_min and ey.Cm == 1.0
    assert abs(ey.Mc) == rel(delta * pu * (15 + 0.03 * 400) / 1e3)
    # Puntos magnificados: uno por eje, con el mínimo en un eje por vez.
    mag = [d for d in r.demandas if d.x is None]
    assert len(mag) == 2
    assert abs(mag[0].Mz) == rel(delta * m2) and mag[0].My == pytest.approx(0.0, abs=1e-9)
    assert abs(mag[1].My) == rel(abs(ey.Mc)) and abs(mag[1].Mz) == rel(delta * m2)
    assert any("1.4 veces" in a for a in r.avisos)  # δ = 2.79 (§6.2.5.3)


def test_magnificacion_curvatura_doble_y_beta_dns():
    # Momentos de extremo opuestos en el diagrama: curvatura doble, M1/M2 = +0.5.
    res, barra = columna_biarticulada(m_sup=-20.0, m_inf=-40.0, axil=600.0)
    combs = {"U": {"D": 1.2}}
    r = aci318.disenar_columna(res, barra, cuadrada(), MAT, combs, permanentes=[])
    e = r.esbeltez["U"]["z"]
    assert e.m1_m2 == rel(0.5)
    assert e.limite == 40.0 and e.esbelta  # 50 > 40
    assert e.Cm == rel(0.4) and e.beta_dns == 0.0
    # δ = máx(1, Cm/(1 − Pu/0.75Pc)); con Cm = 0.4 da 1 y Mc es el mayor de extremo.
    ei = 0.4 * 4700 * math.sqrt(28) * 400**4 / 12
    pc = math.pi**2 * ei / 6000**2 / 1e3
    assert e.delta == rel(max(1.0, 0.4 / (1 - 720 / (0.75 * pc))))
    assert abs(e.Mc) == rel(48.0)


def test_columna_corta_no_magnifica():
    res, barra = columna_biarticulada(altura=2.0)
    r = aci318.disenar_columna(res, barra, cuadrada(), MAT, {"U": {"D": 1.4}})
    assert not r.esbeltez["U"]["z"].esbelta  # 2000/120 = 16.7 < 22
    assert all(d.x is not None for d in r.demandas)
    assert r.critica.Pu == rel(1400) and abs(r.critica.Mz) == rel(70)


def test_desplazable():
    res, barra = columna_biarticulada()
    with pytest.raises(ValueError, match="delta_s"):
        aci318.disenar_columna(res, barra, cuadrada(), MAT, {"U": {"D": 1.4}}, desplazable=True)
    r = aci318.disenar_columna(
        res, barra, cuadrada(), MAT, {"U": {"D": 1.4}}, desplazable=True, delta_s=1.5, k=1.2
    )
    e = r.esbeltez["U"]["z"]
    assert e.limite == 22.0 and e.esbeltez == rel(1.2 * 6000 / 120) and e.delta == 1.5
    assert abs(r.critica.Mz) == rel(1.5 * 70)


# --- Diseño desde el modelo -------------------------------------------------------


def test_disenar_desde_portico_plano():
    m = nervi.Modelo()
    a, b = m.agregar_nudo(0, 0), m.agregar_nudo(0, 3)
    barra = m.agregar_barra(a, b, E=2.5e7, A=0.16, I=2e-3)
    m.apoyar(a)
    m.carga_nodal("D", b, fy=-800)
    m.carga_nodal("W", b, fx=40)
    combs = design.generar({"D": "D", "W": "W"})
    res = m.resolver(combinaciones=design.como_diccionario(combs))
    r = aci318.disenar_columna(res, barra, cuadrada(), MAT, combs, permanentes=["D"])
    assert set(r.esbeltez[combs[0].nombre]) == {"z"}  # en el plano solo hay Mz
    # Manda la base con 1.2·D ± 1.0·W: Pu = 960 kN, |M| = 40·3 = 120 kN·m.
    assert r.critica.x == 0.0
    assert r.critica.Pu == rel(960) and abs(r.critica.Mz) == rel(120)
    v = aci318.verificar_columna(cuadrada(), MAT, 960, 120)
    assert r.razon == rel(float(v.razon[0]))
    assert r.cumple and r.avisos == []
    # También acepta los nombres de las combinaciones ya resueltas.
    r2 = aci318.disenar_columna(res, barra, cuadrada(), MAT, res.combinaciones)
    assert r2.razon == rel(r.razon)


def test_buscar_armadura_minima():
    res, barra = columna_biarticulada(axil=800.0)
    combs = {"U": {"D": 1.4}}
    r = aci318.disenar_columna(
        res, barra, cuadrada(), MAT, combs, permanentes=["D"], buscar_armadura=True
    )
    assert r.cumple
    assert 0.01 <= r.seccion.cuantia <= 0.08
    # Ninguna de las armaduras más livianas que la elegida alcanza.
    puntos, _, _ = aci318.solicitaciones_columna(
        res, barra, cuadrada(), MAT, combs, permanentes=["D"]
    )
    for area, _, cantidad, d in col._candidatas(cuadrada(), aci318.DIAMETROS_COLUMNA, False):
        if area >= r.seccion.Ast - 1e-6:
            break
        sec = cuadrada().con_barras(cantidad, d)
        assert not col._verificar_puntos(sec, MAT, puntos, False).cumple


def test_buscar_armadura_sin_solucion():
    res, barra = columna_biarticulada(axil=8000.0)
    with pytest.raises(ValueError, match="agrandá la sección"):
        aci318.disenar_columna(res, barra, cuadrada(), MAT, {"U": {"D": 1.4}}, buscar_armadura=True)


def test_avisos_de_la_seccion():
    res, barra = columna_biarticulada(altura=2.0, axil=100.0)
    poca = aci318.SeccionColumna.rectangular(400, 400, 2, 2, 16)  # ρ = 0.5 %
    r = aci318.disenar_columna(res, barra, poca, MAT, {"U": {"D": 1.4}})
    assert any("< 1 %" in a for a in r.avisos)
    junta = aci318.SeccionColumna.rectangular(300, 300, 5, 5, 25)
    r = aci318.disenar_columna(res, barra, junta, MAT, {"U": {"D": 1.4}})
    assert any("§25.2.3" in a for a in r.avisos)
