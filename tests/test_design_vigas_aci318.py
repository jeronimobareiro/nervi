# SPDX-License-Identifier: GPL-3.0-or-later
"""Flexión (#22) y cortante (#23) de vigas según ACI 318-19 (experimental).

Cada valor esperado se calcula a mano en la prueba, paso a paso, con las
expresiones de ACI 318-19 que cita el módulo (§9.6.1.2, §9.6.3, §9.7.6.2.2,
§21.2, §22.2, §22.5, §25.2) y estática de vigas. No se transcriben ejemplos de
libros: falta compararlos con ejemplos publicados (ver la bitácora).
"""

import doctest
import math

import pytest

import nervi
from nervi import design
from nervi.design import aci318

pytestmark = pytest.mark.filterwarnings("ignore::nervi.design.ModuloExperimentalWarning")

MAT = aci318.Materiales(fc=28, fy=420)
RAIZ_FC = math.sqrt(28)
EPS_TY = 420 / 200_000


def rel(esperado, tol=1e-6):
    return pytest.approx(esperado, rel=tol)


# --- Flexión ---------------------------------------------------------------


def test_beta1_y_phi():
    assert aci318.beta1(21) == 0.85
    assert aci318.beta1(28) == 0.85
    assert aci318.beta1(35) == pytest.approx(0.80)
    assert aci318.beta1(42) == pytest.approx(0.75)
    assert aci318.beta1(60) == 0.65
    assert aci318.phi_flexion(0.0015, 420) == 0.65  # controlada por compresión
    assert aci318.phi_flexion(EPS_TY + 0.003, 420) == 0.90  # controlada por tracción
    # Transición lineal: a mitad de camino, 0.775.
    assert aci318.phi_flexion(EPS_TY + 0.0015, 420) == pytest.approx(0.775)


def test_armadura_minima():
    # f'c = 28: manda 1.4/fy = 0.003333 > 0.25·√28/420 = 0.003150.
    assert aci318.armadura_minima(300, 500, MAT) == rel(1.4 / 420 * 300 * 500)
    # f'c = 40: manda 0.25·√40/420 = 0.003765.
    m40 = aci318.Materiales(fc=40, fy=420)
    assert aci318.armadura_minima(300, 500, m40) == rel(0.25 * math.sqrt(40) / 420 * 300 * 500)


def test_resistencia_de_seccion_simple():
    b, d, As = 300, 500, 1500
    a = As * 420 / (0.85 * 28 * b)  # 88.235 mm
    c = a / 0.85
    eps_t = 0.003 * (d - c) / c
    Mn = As * 420 * (d - a / 2) / 1e6  # 287.21 kN·m
    r = aci318.resistencia_flexion(b, d, As, MAT)
    assert r.a == rel(a) and r.c == rel(c) and r.eps_t == rel(eps_t)
    assert r.Mn == rel(Mn) and r.phi == 0.90 and r.phiMn == rel(0.9 * Mn)
    assert r.fs == 420


def test_armadura_simple_es_la_inversa_de_la_resistencia():
    b, d = 300, 500
    Mn = 200 / 0.9 * 1e6
    # Despeje cerrado del bloque rectangular: a = d - √(d² - 2Mn/(0.85 f'c b)).
    a = d - math.sqrt(d**2 - 2 * Mn / (0.85 * 28 * b))
    As = 0.85 * 28 * b * a / 420
    r = aci318.armadura_flexion(200, b, d, MAT)
    assert not r.doble and r.As_comp == 0
    assert r.As_req == rel(As)
    assert r.As == r.As_req  # supera As,min = 500 mm²
    assert r.resistencia.phiMn == rel(200)
    assert aci318.armadura_flexion(-200, b, d, MAT).As_req == rel(As)  # signo indistinto


def test_minimo_y_excepcion_de_cuatro_tercios():
    b, d = 300, 500
    as_min = 1.4 / 420 * b * d  # 500 mm²
    chico = aci318.armadura_flexion(20, b, d, MAT)
    assert chico.As_req < 0.75 * as_min
    assert chico.As == rel(4 / 3 * chico.As_req)  # §9.6.1.3
    medio = aci318.armadura_flexion(75, b, d, MAT)
    assert medio.As_req < as_min < 4 / 3 * medio.As_req
    assert medio.As == rel(as_min)  # §9.6.1.2


def test_doble_armadura():
    b, d, dp, Mu = 300, 500, 60, 600
    # Eje neutro para εt = εty + 0.003 (controlada por tracción).
    c = 0.003 * d / (0.003 + EPS_TY + 0.003)  # 185.19 mm
    a = 0.85 * c
    Cc = 0.85 * 28 * b * a
    As1 = Cc / 420
    Mn1 = Cc * (d - a / 2) / 1e6  # 473.50 kN·m
    fsp = min(420, 200_000 * 0.003 * (c - dp) / c)  # 405.6 MPa: no fluye
    fsp_neto = fsp - 0.85 * 28  # la barra está dentro del bloque
    dMn = (Mu / 0.9 - Mn1) * 1e6
    As_comp = dMn / (fsp_neto * (d - dp))
    As = As1 + As_comp * fsp_neto / 420
    r = aci318.armadura_flexion(Mu, b, d, MAT, d_comp=dp)
    assert r.doble
    assert r.As_comp == rel(As_comp) and r.As == rel(As)
    # La resistencia por compatibilidad de deformaciones da lo mismo.
    assert r.resistencia.c == rel(c, 1e-6)
    assert r.resistencia.fs_comp == rel(fsp, 1e-6)
    assert r.resistencia.phiMn == rel(Mu, 1e-6)
    with pytest.raises(ValueError, match="armadura de compresión"):
        aci318.armadura_flexion(Mu, b, d, MAT)


def test_eps_t_minimo_de_vigas():
    with pytest.raises(ValueError, match=r"0\.004"):
        aci318.armadura_flexion(100, 300, 500, MAT, eps_t_min=0.003)
    # Con εt ≥ 0.004 se admite φ < 0.9 y la sección simple resiste más.
    # 428 kN·m está entre φMn controlada por tracción (426.2) y con εt = 0.004 (429.9).
    with pytest.raises(ValueError, match="compresión"):
        aci318.armadura_flexion(428, 300, 500, MAT)
    tr = aci318.armadura_flexion(428, 300, 500, MAT, eps_t_min=0.004)
    assert not tr.doble
    assert tr.resistencia.eps_t >= 0.004 - 1e-9
    assert tr.resistencia.phi == rel(0.65 + 0.25 * (tr.resistencia.eps_t - EPS_TY) / 0.003)
    assert tr.resistencia.phi < 0.9
    assert tr.resistencia.phiMn == rel(428)


def test_separacion_y_ancho():
    assert aci318.separacion_libre_minima(16, 19) == pytest.approx(4 / 3 * 19)
    assert aci318.separacion_libre_minima(32, 19) == 32
    assert aci318.separacion_libre_minima(12, 10) == 25
    sec = aci318.SeccionRectangular(300, 550, recubrimiento=40, d_estribo=10, d_agregado=19)
    assert aci318.ancho_necesario([20, 20, 20, 12, 12], sec) == pytest.approx(
        2 * 50 + 3 * 20 + 2 * 12 + 4 * (4 / 3 * 19)
    )


def test_elegir_barras_en_una_capa():
    sec = aci318.SeccionRectangular(300, 550, recubrimiento=40, d_estribo=10, d_agregado=19)
    r = aci318.elegir_barras(200, sec, MAT)
    assert r.descripcion == "3Ø20 + 2Ø12"
    a20, a12 = math.pi * 20**2 / 4, math.pi * 12**2 / 4
    As = 3 * a20 + 2 * a12
    d = 550 - (3 * a20 * 60 + 2 * a12 * 56) / As  # centroides a 50 + db/2
    assert r.As == rel(As) and r.d == rel(d) and r.dt == rel(550 - 56)
    assert r.b_nec == pytest.approx(2 * 50 + 84 + 4 * (4 / 3 * 19)) and r.b_nec <= 300
    assert r.resistencia.phiMn >= 200 and r.resistencia.phi == 0.9
    # La opción de una capa con menos área (3Ø20 + 1Ø16) no alcanza.
    menor = 3 * a20 + math.pi * 16**2 / 4
    assert menor < r.As
    d_menor = 550 - (3 * a20 * 60 + math.pi * 16**2 / 4 * 58) / menor
    assert aci318.armadura_flexion(200, 300, d_menor, MAT).As > menor


def test_elegir_barras_en_dos_capas():
    sec = aci318.SeccionRectangular(250, 650, recubrimiento=40, d_estribo=10, d_agregado=19)
    r = aci318.elegir_barras(400, sec, MAT)
    assert r.capas == ((32, 32), (20, 20))
    a32, a20 = math.pi * 32**2 / 4, math.pi * 20**2 / 4
    y1, y2 = 50 + 16, 50 + 32 + 25 + 10  # §25.2.2: 25 mm libres entre capas
    d = 650 - (2 * a32 * y1 + 2 * a20 * y2) / (2 * a32 + 2 * a20)
    assert r.d == rel(d) and r.dt == rel(650 - y1)
    assert r.resistencia.phiMn >= 400
    # Con una sola capa no hay solución en 250 mm.
    with pytest.raises(ValueError, match="no hay una disposición"):
        aci318.elegir_barras(400, sec, MAT, max_capas=1)


# --- Cortante --------------------------------------------------------------


def test_cortante_con_estribos():
    b, d, Vu = 300, 500, 250
    Vc = 0.17 * RAIZ_FC * b * d / 1e3  # 134.93 kN, §22.5.5.1a
    Vs = Vu / 0.75 - Vc  # 198.40 kN
    r = aci318.armadura_cortante(Vu, b, d, MAT)
    assert r.Vc == rel(Vc) and r.Vs_req == rel(Vs)
    assert r.Av_s_req == rel(Vs * 1e3 / (420 * d))  # §22.5.8.5.3
    assert r.Av_s_min == rel(0.35 * b / 420)  # §9.6.3.4: 0.35 > 0.062√28
    assert r.s_max == 250  # Vs < 0.33√f'c bw d → d/2
    e = aci318.elegir_estribos(Vu, b, d, MAT, diametros=(10,))
    # 2 ramas Ø10: s ≤ 157.08/0.9448 = 166 mm → 150 mm.
    assert (e.diametro, e.ramas, e.s) == (10, 2, 150)
    assert e.phiVn == rel(0.75 * (Vc + 2 * math.pi * 25 * 420 * d / 150 / 1e3))
    assert e.phiVn >= Vu


def test_cortante_alto_reduce_la_separacion_maxima():
    b, d, Vu = 300, 500, 450
    Vc = 0.17 * RAIZ_FC * b * d / 1e3
    assert Vu / 0.75 - Vc > 0.33 * RAIZ_FC * b * d / 1e3
    r = aci318.armadura_cortante(Vu, b, d, MAT)
    assert r.s_max == 125  # min(d/4, 300)
    # Ø10 pediría s = 70 mm < 75; Ø12: 226.2/2.2146 = 102 → 100 mm.
    e = aci318.elegir_estribos(Vu, b, d, MAT, diametros=(10, 12))
    assert (e.diametro, e.s) == (12, 100)


def test_limite_de_la_seccion():
    b, d = 300, 500
    tope = 0.75 * (0.17 + 0.66) * RAIZ_FC * b * d / 1e3  # §22.5.1.2
    assert aci318.armadura_cortante(tope * 0.999, b, d, MAT).Vu_max_seccion == rel(tope)
    with pytest.raises(ValueError, match=r"22\.5\.1\.2"):
        aci318.armadura_cortante(tope * 1.01, b, d, MAT)


def test_cortante_bajo_sin_estribos():
    b, d = 300, 500
    lam_s = math.sqrt(2 / (1 + 0.004 * d))  # §22.5.5.1.3
    assert aci318.factor_tamano(d) == rel(lam_s)
    vc = 0.66 * lam_s * 0.01 ** (1 / 3) * RAIZ_FC * b * d / 1e3  # §22.5.5.1c
    r = aci318.armadura_cortante(20, b, d, MAT, rho_w=0.01)
    assert not r.requiere_estribos and r.Vc == rel(vc)
    assert aci318.elegir_estribos(20, b, d, MAT, rho_w=0.01) is None
    # Sin la cuantía no se puede verificar §22.5.5.1c: van estribos mínimos.
    m = aci318.armadura_cortante(20, b, d, MAT)
    assert m.requiere_estribos and m.Av_s == m.Av_s_min
    # Sobre el umbral de §9.6.3.1 hacen falta estribos aunque el hormigón alcance.
    umbral = 0.75 * 0.083 * RAIZ_FC * b * d / 1e3
    assert aci318.armadura_cortante(umbral * 1.01, b, d, MAT, rho_w=0.02).requiere_estribos


def test_fyt_limitado():
    with pytest.raises(ValueError, match="420"):
        aci318.armadura_cortante(100, 300, 500, aci318.Materiales(fc=28, fy=500))
    assert aci318.armadura_cortante(
        100, 300, 500, aci318.Materiales(fc=28, fy=500, fyt=420)
    ).requiere_estribos


# --- Viga del modelo -------------------------------------------------------

E, A, I = 2.5e7, 0.165, 0.0042


def _simple(largo=6.0):
    m = nervi.Modelo()
    a, b = m.agregar_nudo(0, 0), m.agregar_nudo(largo, 0)
    barra = m.agregar_barra(a, b, E=E, A=A, I=I)
    m.apoyar(a, rz=False)
    m.apoyar(b, ux=False, rz=False)
    m.carga_uniforme("D", barra, qy=-20)
    m.carga_uniforme("L", barra, qy=-10)
    combs = design.generar({"D": "D", "L": "L"})
    return m.resolver(combinaciones=design.como_diccionario(combs)), barra


def test_disenar_viga_simple():
    res, barra = _simple()
    sec = aci318.SeccionRectangular(300, 550)
    v = aci318.disenar_viga(res, barra, sec, MAT)
    w = 1.2 * 20 + 1.6 * 10  # 40 kN/m, 5.3.1b
    assert v.Mu_pos == rel(w * 36 / 8) and v.Mu_pos_comb.startswith("5.3.1b")
    assert v.superior is None
    assert v.inferior == aci318.elegir_barras(w * 36 / 8, sec, MAT)
    d = v.inferior.d
    # Sección crítica a d de la cara (apoyo puntual): Vu = wL/2 - w·d.
    assert v.x_Vu == pytest.approx(d / 1000) or v.x_Vu == pytest.approx(6 - d / 1000)
    assert v.Vu == rel(w * 3 - w * d / 1000)
    esperado = aci318.elegir_estribos(
        v.Vu, 300, d, MAT, rho_w=v.inferior.As / (300 * d), diametros=(10,)
    )
    assert v.estribos == esperado
    # Con apoyos de 300 mm la sección crítica se corre 150 mm.
    v2 = aci318.disenar_viga(res, barra, sec, MAT, ancho_apoyo_i=300, ancho_apoyo_j=300)
    assert v2.Vu == rel(w * 3 - w * (150 + d) / 1000)
    v3 = aci318.disenar_viga(res, barra, sec, MAT, seccion_critica_a_d=False)
    assert v3.Vu == rel(w * 3)


def test_disenar_viga_continua_tiene_armadura_superior():
    m = nervi.Modelo()
    for k in range(3):
        m.agregar_nudo(5.0 * k, 0)
    b1 = m.agregar_barra(0, 1, E=E, A=A, I=I)
    b2 = m.agregar_barra(1, 2, E=E, A=A, I=I)
    m.apoyar(0, rz=False)
    m.apoyar(1, ux=False, rz=False)
    m.apoyar(2, ux=False, rz=False)
    for b in (b1, b2):
        m.carga_uniforme("D", b, qy=-20)
    res = m.resolver(combinaciones=design.como_diccionario(design.generar({"D": "D"})))
    v = aci318.disenar_viga(res, b1, aci318.SeccionRectangular(300, 500), MAT)
    # Viga continua de dos tramos iguales: M_B = -wL²/8 con w = 1.4·20.
    assert v.Mu_neg == rel(-28 * 25 / 8)
    assert v.superior is not None and v.superior.resistencia.phiMn >= 28 * 25 / 8
    assert v.inferior.resistencia.phiMn >= v.Mu_pos


def test_aviso_de_axil_importante():
    m = nervi.Modelo()
    a, b = m.agregar_nudo(0, 0), m.agregar_nudo(5, 0)
    barra = m.agregar_barra(a, b, E=E, A=A, I=I)
    m.apoyar(a, rz=False)
    m.apoyar(b, ux=False, rz=False)
    m.carga_uniforme("D", barra, qy=-20)
    # 1.4·2000 kN de compresión > 0.1·f'c·Ag = 462 kN.
    m.carga_nodal("D", b, fx=-2000)
    res = m.resolver(combinaciones={"U": {"D": 1.4}})
    with pytest.warns(UserWarning, match=r"9\.3\.3\.1"):
        aci318.disenar_viga(res, barra, aci318.SeccionRectangular(300, 550), MAT)


def test_aviso_experimental_y_validaciones():
    with pytest.warns(design.ModuloExperimentalWarning):
        aci318.armadura_flexion(100, 300, 500, MAT)
    with pytest.raises(ValueError, match="17 MPa"):
        aci318.Materiales(fc=14)
    with pytest.raises(ValueError, match="550"):
        aci318.Materiales(fc=28, fy=600)
    with pytest.raises(ValueError, match="lugar"):
        aci318.SeccionRectangular(100, 500, recubrimiento=40, d_estribo=12)


def test_doctest_del_modulo():
    assert doctest.testmod(aci318).failed == 0
