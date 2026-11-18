# SPDX-License-Identifier: GPL-3.0-or-later
"""Flechas, fisuración y detalle de armaduras según ACI 318-19 (experimental).

Cada valor esperado se calcula a mano en la prueba con las expresiones que cita
el módulo (§19.2, §24.2, §24.3, §25.3, §25.4, §25.5, §9.7.3) y la estática de
vigas (flecha de una viga simplemente apoyada con carga uniforme,
``5 w L⁴ / 384 EI``). Las expresiones en unidades SI se contrastan con las
equivalentes de la norma en unidades inglesas (``ld = 38 db`` para barras No. 6 y
menores de grado 60 con ``f'c = 4000 psi``, y otras); falta compararlas con
ejemplos resueltos publicados (ver la bitácora).
"""

import math

import numpy as np
import pytest

import nervi
from nervi import design, memoria
from nervi.design import aci318
from nervi.design.aci318 import detalle, servicio

pytestmark = pytest.mark.filterwarnings("ignore::nervi.design.ModuloExperimentalWarning")

MAT = aci318.Materiales(fc=28, fy=420)
RAIZ = math.sqrt(28)
PSI = 6.894757e-3  # MPa por psi


def rel(esperado, tol=1e-6):
    return pytest.approx(esperado, rel=tol)


# --- Propiedades de la sección ------------------------------------------------


def test_modulos_y_momento_de_fisuracion():
    assert servicio.modulo_elasticidad(MAT) == rel(4700 * RAIZ)  # 24 870 MPa
    assert servicio.modulo_rotura(MAT) == rel(0.62 * RAIZ)  # 3.281 MPa
    liviano = aci318.Materiales(fc=28, fy=420, lam=0.75)
    assert servicio.modulo_rotura(liviano) == rel(0.75 * 0.62 * RAIZ)
    sec = aci318.SeccionRectangular(b=300, h=500)
    ig = 300 * 500**3 / 12  # 3.125e9 mm⁴
    assert servicio.inercia_bruta(sec) == rel(ig)
    # Mcr = fr Ig / (h/2) = 3.2807 · 3.125e9 / 250 = 41.01 kN·m
    assert servicio.momento_fisuracion(sec, MAT) == rel(0.62 * RAIZ * ig / 250 / 1e6)
    assert servicio.momento_fisuracion(sec, MAT) == pytest.approx(41.01, abs=0.01)


def test_inercia_fisurada_armadura_simple():
    # Ec = 25 000 MPa → n = 8. Equilibrio: 150 x² = 8·1500·(450 - x)
    # → 150 x² + 12 000 x - 5.4e6 = 0 → x = (-12 000 + √(1.44e8 + 3.24e9)) / 300
    x = (-12_000 + math.sqrt(12_000**2 + 4 * 150 * 5.4e6)) / 300
    assert x == pytest.approx(153.907, abs=1e-3)
    icr = 300 * x**3 / 3 + 8 * 1500 * (450 - x) ** 2
    sf = servicio.seccion_fisurada(300, 450, 1500, MAT, Ec=25_000)
    assert sf.n == rel(8.0)
    assert sf.x == rel(x)
    assert sf.Icr == rel(icr)
    assert sf.Icr == pytest.approx(1.4167e9, rel=1e-4)


def test_inercia_fisurada_con_armadura_comprimida():
    # n = 8, As' = 600 mm² a 60 mm: momento estático nulo respecto del eje neutro.
    sf = servicio.seccion_fisurada(300, 450, 1500, MAT, As_comp=600, d_comp=60, Ec=25_000)
    x = sf.x
    assert 300 * x**2 / 2 + 7 * 600 * (x - 60) == pytest.approx(8 * 1500 * (450 - x), rel=1e-9)
    icr = 300 * x**3 / 3 + 7 * 600 * (x - 60) ** 2 + 8 * 1500 * (450 - x) ** 2
    assert sf.Icr == rel(icr)
    # La armadura comprimida sube el eje neutro y aumenta Icr.
    simple = servicio.seccion_fisurada(300, 450, 1500, MAT, Ec=25_000)
    assert sf.x < simple.x and sf.Icr > simple.Icr


def test_inercia_efectiva():
    ig, icr, mcr = 3.125e9, 1.0e9, 40.0
    # Sin fisurar hasta (2/3) Mcr.
    assert servicio.inercia_efectiva(20.0, mcr, ig, icr) == ig
    assert servicio.inercia_efectiva(-2 / 3 * mcr, mcr, ig, icr) == ig
    # Ma = Mcr: Ie = Icr / (1 - (2/3)² (1 - Icr/Ig)) = 1e9 / (1 - 4/9 · 0.68)
    assert servicio.inercia_efectiva(mcr, mcr, ig, icr) == rel(1e9 / (1 - 4 / 9 * 0.68))
    # Continuidad en (2/3) Mcr y tendencia a Icr para Ma grande.
    assert servicio.inercia_efectiva(2 / 3 * mcr * (1 + 1e-9), mcr, ig, icr) == rel(ig, 1e-6)
    assert servicio.inercia_efectiva(1e6, mcr, ig, icr) == rel(icr, 1e-6)
    with pytest.raises(ValueError):
        servicio.inercia_efectiva(50, mcr, ig, 2 * ig)


# --- Flechas diferidas y límites ---------------------------------------------


def test_factor_xi_y_multiplicador_diferido():
    assert servicio.factor_xi(3) == 1.0
    assert servicio.factor_xi(6) == 1.2
    assert servicio.factor_xi(12) == 1.4
    assert servicio.factor_xi(60) == 2.0
    assert servicio.factor_xi(240) == 2.0
    assert servicio.factor_xi(9) == pytest.approx(1.3)  # interpolación
    with pytest.raises(ValueError):
        servicio.factor_xi(1)
    # λΔ = 2 / (1 + 50 · 0.01) = 1.333
    assert servicio.factor_diferido(60, 0.01) == rel(2 / 1.5)
    assert servicio.factor_diferido(60) == 2.0


def test_limites_de_flecha():
    assert servicio.limite_flecha(6000, "cubierta") == rel(6000 / 180)
    assert servicio.limite_flecha(6000, "piso") == rel(6000 / 360)
    assert servicio.limite_flecha(6000, "sensibles") == rel(6000 / 480)
    assert servicio.limite_flecha(6000, "no_sensibles") == rel(6000 / 240)
    with pytest.raises(ValueError):
        servicio.limite_flecha(6000, "puente")


# --- Fisuración --------------------------------------------------------------


def test_separacion_maxima_fisuracion():
    # fs = (2/3)·420 = 280 MPa, cc = 50 mm: min(380 - 125, 300) = 255 mm.
    assert servicio.separacion_maxima_fisuracion(280, 50) == rel(255.0)
    # Recubrimiento chico: manda 300 (280/fs).
    assert servicio.separacion_maxima_fisuracion(280, 20) == rel(300.0)
    # fs = 200 MPa, cc = 40: min(380·1.4 - 100, 300·1.4) = min(432, 420) = 420.
    assert servicio.separacion_maxima_fisuracion(200, 40) == rel(420.0)


def test_verificar_fisuracion_con_disposicion():
    sec = aci318.SeccionRectangular(b=300, h=550, recubrimiento=40, d_estribo=10)
    disp = aci318.elegir_barras(200, sec, MAT, diametros=(20,))
    assert disp.capas == ((20, 20, 20, 20),)
    # Ancho libre entre estribos 300 - 2·50 = 200; libre entre barras (200 - 80)/3 = 40;
    # entre centros 40 + 20 = 60 mm.
    f = servicio.verificar_fisuracion(disp, sec, MAT)
    assert f.s == rel(60.0)
    assert f.fs == rel(280.0) and not f.fs_calculada
    assert f.s_max == rel(min(380 - 2.5 * 40, 300))
    assert f.cumple
    # Con el momento de servicio: fs = n Ms (dt - x) / Icr.
    ms = 130.0
    sf = servicio.seccion_fisurada(300, disp.d, disp.As, MAT)
    esperado = sf.n * ms * 1e6 * (disp.dt - sf.x) / sf.Icr
    fc = servicio.verificar_fisuracion(disp, sec, MAT, Ms=ms)
    assert fc.fs_calculada and fc.fs == rel(esperado)
    # Aproximación clásica fs ≈ Ms / (As · 0.9 d): mismo orden de magnitud.
    assert fc.fs == pytest.approx(ms * 1e6 / (disp.As * 0.9 * disp.d), rel=0.05)


# --- Flechas de un modelo -----------------------------------------------------


def _viga_simple(E, luz=6.0, qd=-15.0, ql=-10.0):
    m = nervi.Modelo()
    a, b = m.agregar_nudo(0, 0), m.agregar_nudo(luz, 0)
    barra = m.agregar_barra(a, b, E=E, A=0.3 * 0.55, I=0.3 * 0.55**3 / 12)
    m.apoyar(a, rz=False)
    m.apoyar(b, ux=False, rz=False)
    m.carga_uniforme("D", barra, qy=qd)
    m.carga_uniforme("L", barra, qy=ql)
    combs = design.generar({"D": "D", "L": "L"})
    res = m.resolver(n_estaciones=21, combinaciones=design.como_diccionario(combs))
    return m, res, barra


@pytest.mark.parametrize("E", [2.4870e7, 1.0e7])
def test_flecha_viga_simple_contra_formula_cerrada(E):
    """La flecha no depende del E del modelo: se reescala con Ec·Ie."""
    sec = aci318.SeccionRectangular(b=300, h=550, recubrimiento=40, d_estribo=10)
    m, res, barra = _viga_simple(E)
    dis = aci318.disenar_viga(res, barra, sec, MAT)
    s = servicio.verificar_servicio_viga(
        res,
        m,
        barra,
        dis,
        sec,
        MAT,
        permanentes=["D"],
        sobrecargas=["L"],
        fraccion_sostenida=0.25,
        elementos="sensibles",
    )
    L = 6000.0  # mm
    ec = 4700 * RAIZ
    ig = 300 * 550**3 / 12
    mcr = 0.62 * RAIZ * ig / 275 / 1e6
    icr = servicio.seccion_fisurada(300, dis.inferior.d, dis.inferior.As, MAT).Icr
    md, mdl = 15 * 36 / 8, 25 * 36 / 8  # 67.5 y 112.5 kN·m
    assert s.Ma_D == rel(md) and s.Ma_DL == rel(mdl)
    assert s.Mcr == rel(mcr)

    def ie(ma):
        return icr / (1 - (2 / 3 * mcr / ma) ** 2 * (1 - icr / ig))

    assert s.Ie_D == rel(ie(md)) and s.Ie_DL == rel(ie(mdl))
    # w en N/mm = kN/m.
    dd = 5 * 15 * L**4 / (384 * ec * ie(md))
    ddl = 5 * 25 * L**4 / (384 * ec * ie(mdl))
    assert s.x == rel(3000.0)
    assert s.delta_D == rel(dd, 1e-6)
    assert s.delta_DL == rel(ddl, 1e-6)
    assert s.delta_L == rel(ddl - dd, 1e-6)
    sost = dd + 0.25 * (ddl - dd)
    assert s.delta_sostenida == rel(sost, 1e-6)
    assert s.lambda_delta == 2.0
    assert s.delta_diferida == rel(2 * sost, 1e-6)
    nombres = [n for n, *_ in s.limites]
    assert nombres == [
        "inmediata por sobrecarga (piso)",
        "diferida + sobrecarga (elementos sensibles)",
    ]
    assert s.limites[0][2] == rel(L / 360) and s.limites[1][2] == rel(L / 480)
    assert s.limites[1][1] == rel(2 * sost + ddl - dd, 1e-6)
    assert s.fisuracion_superior is None and s.fisuracion_inferior is not None


def test_flecha_en_otras_unidades():
    """El mismo modelo en N y mm da las mismas flechas."""
    sec = aci318.SeccionRectangular(b=300, h=550, recubrimiento=40, d_estribo=10)
    m, res, barra = _viga_simple(2.487e7)
    dis = aci318.disenar_viga(res, barra, sec, MAT)
    ref = servicio.verificar_servicio_viga(
        res, m, barra, dis, sec, MAT, permanentes=["D"], sobrecargas=["L"]
    )
    mm = nervi.Modelo()
    a, b = mm.agregar_nudo(0, 0), mm.agregar_nudo(6000, 0)
    bb = mm.agregar_barra(a, b, E=24_870.0, A=300 * 550, I=300 * 550**3 / 12)
    mm.apoyar(a, rz=False)
    mm.apoyar(b, ux=False, rz=False)
    mm.carga_uniforme("D", bb, qy=-15.0)  # N/mm
    mm.carga_uniforme("L", bb, qy=-10.0)
    r2 = mm.resolver(n_estaciones=21)
    s = servicio.verificar_servicio_viga(
        r2,
        mm,
        bb,
        dis,
        sec,
        MAT,
        permanentes=["D"],
        sobrecargas=["L"],
        fuerza="N",
        longitud="mm",
    )
    assert s.delta_D == rel(ref.delta_D, 1e-9)
    assert s.delta_L == rel(ref.delta_L, 1e-9)
    assert s.Ma_DL == rel(ref.Ma_DL, 1e-9)


def test_flechas_viga_continua_promedia_ie():
    seccion = aci318.SeccionRectangular(b=250, h=500, recubrimiento=40, d_estribo=8)
    mat = aci318.Materiales(fc=25, fy=420)
    m = nervi.Modelo()
    nudos = [m.agregar_nudo(x, 0.0) for x in (0.0, 5.0, 10.0)]
    props = dict(E=2.35e7, A=0.25 * 0.50, I=0.25 * 0.50**3 / 12)
    tramos = [m.agregar_barra(nudos[k], nudos[k + 1], **props) for k in range(2)]
    m.apoyar(nudos[0], rz=False)
    m.apoyar(nudos[1], ux=False, rz=False)
    m.apoyar(nudos[2], ux=False, rz=False)
    for barra in tramos:
        m.carga_uniforme("D", barra, qy=-18.0)
        m.carga_uniforme("L", barra, qy=-8.0)
    combs = design.generar({"D": "D", "L": "L"})
    res = m.resolver(n_estaciones=41, combinaciones=design.como_diccionario(combs))
    dis = aci318.disenar_viga(res, 0, seccion, mat)
    s = servicio.verificar_servicio_viga(
        res, m, 0, dis, seccion, mat, permanentes=["D"], sobrecargas=["L"]
    )
    # Momento en el apoyo central w L²/8 = 26·25/8 = 81.25 kN·m (servicio D + L).
    assert s.Ma_extremos_DL[1] == rel(81.25, 1e-9)
    assert s.Ma_extremos_DL[0] == pytest.approx(0.0, abs=1e-9)
    ig = servicio.inercia_bruta(seccion)
    mcr = servicio.momento_fisuracion(seccion, mat)
    ie_c = servicio.inercia_efectiva(s.Ma_DL, mcr, ig, s.Icr_centro)
    ie_a = servicio.inercia_efectiva(81.25, mcr, ig, s.Icr_apoyo)
    assert s.Ie_DL == rel(0.5 * (ie_c + ie_a))
    # Flecha elástica de un tramo extremo de viga continua de dos tramos iguales con
    # carga uniforme en ambos: máximo w L⁴ / (185 EI) a 0.4215 L del apoyo extremo.
    ec = servicio.modulo_elasticidad(mat)
    esperado = 26 * 5000**4 / (185 * ec * s.Ie_DL)
    assert s.delta_DL == pytest.approx(esperado, rel=0.01)
    assert s.x == pytest.approx(0.4215 * 5000, abs=5000 / 40)


def test_servicio_valida_entradas():
    sec = aci318.SeccionRectangular(b=300, h=550)
    m, res, barra = _viga_simple(2.487e7)
    dis = aci318.disenar_viga(res, barra, sec, MAT)
    kw = dict(permanentes=["D"], sobrecargas=["L"])
    with pytest.raises(ValueError):
        servicio.verificar_servicio_viga(res, m, barra, dis, sec, MAT, uso="puente", **kw)
    with pytest.raises(ValueError):
        servicio.verificar_servicio_viga(res, m, barra, dis, sec, MAT, elementos="x", **kw)
    with pytest.raises(ValueError):
        servicio.verificar_servicio_viga(res, m, barra, dis, sec, MAT, fraccion_sostenida=2, **kw)
    with pytest.raises(ValueError):
        servicio.verificar_servicio_viga(res, m, barra, dis, sec, MAT, fuerza="lb", **kw)


def test_servicio_avisa_armadura_de_piel_y_falla_flecha():
    sec = aci318.SeccionRectangular(b=300, h=950)
    m, res, barra = _viga_simple(2.487e7, luz=6.0)
    dis = aci318.disenar_viga(res, barra, sec, MAT)
    s = servicio.verificar_servicio_viga(
        res, m, barra, dis, sec, MAT, permanentes=["D"], sobrecargas=["L"]
    )
    assert any("§9.7.2.3" in a for a in s.avisos)
    # Una viga chata y larga no cumple la flecha.
    chata = aci318.SeccionRectangular(b=300, h=350, recubrimiento=30, d_estribo=8)
    m2, res2, b2 = _viga_simple(2.487e7, luz=8.0, qd=-8.0, ql=-6.0)
    dis2 = aci318.disenar_viga(res2, b2, chata, MAT)
    s2 = servicio.verificar_servicio_viga(
        res2, m2, b2, dis2, chata, MAT, permanentes=["D"], sobrecargas=["L"]
    )
    assert not s2.cumple


def test_filas_para_la_memoria():
    sec = aci318.SeccionRectangular(b=300, h=550, recubrimiento=40, d_estribo=10)
    m, res, barra = _viga_simple(2.487e7)
    dis = aci318.disenar_viga(res, barra, sec, MAT)
    s = servicio.verificar_servicio_viga(
        res, m, barra, dis, sec, MAT, permanentes=["D"], sobrecargas=["L"]
    )
    det = detalle.detallar_viga(dis, sec, MAT, continua=False)
    filas = s.filas_memoria("V1") + det.filas_memoria("V1")
    tabla = memoria.tabla_verificaciones(filas, unidades="mm")
    assert len(tabla.filas) == len(filas) == 4
    assert all(f[5] == "Cumple" for f in tabla.filas)
    assert tabla.filas[0][6] == "ACI 318-19 §24.2.2"
    assert len(det.tabla_memoria()) == 1


# --- Detalle de armaduras -----------------------------------------------------


def test_longitud_desarrollo_general():
    # db = 20, cb = 60 → (cb + Ktr)/db = 3 → se limita a 2.5; ψs = 0.8.
    d = detalle.longitud_desarrollo(20, MAT, cb=60)
    esperado = 420 * 0.8 / (1.1 * RAIZ * 2.5) * 20  # 461.8 mm
    assert d.ld == rel(esperado)
    assert d.confinamiento == 2.5
    # Barra superior: ψt = 1.3.
    assert detalle.longitud_desarrollo(20, MAT, cb=60, superior=True).ld == rel(1.3 * esperado)
    # db = 25, cb = 40, Ktr de estribos Ø10 c/150 de 2 ramas con 4 barras:
    ktr = detalle.indice_ktr(2 * math.pi * 25, 150, 4)
    assert ktr == rel(40 * 157.0796 / 600, 1e-5)  # 10.47 mm
    d25 = detalle.longitud_desarrollo(25, MAT, cb=40, Ktr=ktr)
    assert d25.psi_s == 1.0
    assert d25.ld == rel(420 / (1.1 * RAIZ * ((40 + ktr) / 25)) * 25)
    # Mínimo absoluto de 300 mm y reducción por armadura en exceso.
    assert detalle.longitud_desarrollo(8, MAT, cb=40).ld == 300.0
    red = detalle.longitud_desarrollo(20, MAT, cb=60, As_req_prov=0.8)
    assert red.ld == rel(0.8 * esperado)


def test_longitud_desarrollo_epoxi_y_limites():
    # Epoxi con recubrimiento menor que 3 db: ψe = 1.5; ψt·ψe = 1.95 → 1.7.
    d = detalle.longitud_desarrollo(20, MAT, cb=50, superior=True, epoxi=True, recubrimiento=40)
    assert d.psi_e == 1.5
    assert d.ld == rel(420 * 1.7 * 0.8 / (1.1 * RAIZ * 2.5) * 20)
    # Epoxi con recubrimiento y separación holgados: ψe = 1.2.
    assert detalle.psi_e(True, 70, 130, 20) == 1.2
    # √f'c ≤ 8.3 MPa.
    alto = aci318.Materiales(fc=90, fy=420)
    assert detalle.longitud_desarrollo(25, alto, cb=70).ld == rel(420 / (1.1 * 8.3 * 2.5) * 25)
    assert detalle.psi_g(420) == 1.0 and detalle.psi_g(550) == 1.15 and detalle.psi_g(690) == 1.3


def test_longitud_desarrollo_simplificada_contra_unidades_inglesas():
    """La norma en unidades inglesas da ld = fy/(25 √f'c) db para No. 6 y menores y
    fy/(20 √f'c) db para No. 7 y mayores (condiciones favorables). Con grado 60
    (413.7 MPa) y 4000 psi (27.58 MPa) son 37.9 db y 47.4 db. Las constantes de la
    versión SI (2.1, 1.7, 1.4, 1.1) están redondeadas respecto de la conversión
    exacta (2.07, 1.66, 1.38, 1.10), así que se compara con 3 % de tolerancia."""
    mat = aci318.Materiales(fc=4000 * PSI, fy=60_000 * PSI)
    chica = detalle.longitud_desarrollo_simplificada(16, mat, condiciones_favorables=True)
    grande = detalle.longitud_desarrollo_simplificada(25, mat, condiciones_favorables=True)
    assert chica.ld / 16 == pytest.approx(60_000 / (25 * math.sqrt(4000)), rel=0.03)
    assert grande.ld / 25 == pytest.approx(60_000 / (20 * math.sqrt(4000)), rel=0.03)
    # Otros casos: 1.4 y 1.1 en el divisor (fy/(16.67√f'c) y fy/(13.33√f'c) en inglesas).
    o = detalle.longitud_desarrollo_simplificada(16, mat, condiciones_favorables=False)
    assert o.ld / 16 == pytest.approx(3 * 60_000 / (50 * math.sqrt(4000)), rel=0.03)
    sup = detalle.longitud_desarrollo_simplificada(
        25, MAT, condiciones_favorables=True, superior=True
    )
    assert sup.ld == rel(420 * 1.3 / (1.7 * RAIZ) * 25)


def test_gancho_normal():
    # f'c = 28 → ψc = 28/105 + 0.6 = 0.8667. Sin confinamiento ni núcleo: ψr = 1.6, ψo = 1.25.
    g = detalle.gancho_normal(20, MAT)
    pc = 28 / 105 + 0.6
    assert g.psi_c == rel(pc)
    assert g.ldh == rel(420 * 1.6 * 1.25 * pc / (23 * RAIZ) * 20**1.5)
    assert g.prolongacion == 12 * 20 and g.diametro_doblado == 6 * 20
    g180 = detalle.gancho_normal(12, MAT, angulo=180, confinado=True, dentro_del_nucleo=True)
    assert g180.prolongacion == 65.0  # max(4·12, 65)
    # ψr = ψo = 1: 420·0.8667/(23·√28)·12^1.5 = 124.4 → manda 150 mm.
    assert g180.ldh == 150.0
    assert detalle.diametro_doblado(32) == 8 * 32
    assert detalle.psi_c(45) == 1.0
    with pytest.raises(ValueError):
        detalle.gancho_normal(20, MAT, angulo=135)


def test_gancho_contra_unidades_inglesas():
    """ldh = fy ψe ψr ψo ψc / (55 λ √f'c) db^1.5 en inglesas; barra No. 8 (1 in)."""
    fc_psi, fy_psi = 4000.0, 60_000.0
    mat = aci318.Materiales(fc=fc_psi * PSI, fy=fy_psi * PSI)
    pc_us = fc_psi / 15_000 + 0.6
    ldh_in = fy_psi * 1.6 * 1.25 * pc_us / (55 * math.sqrt(fc_psi)) * 1.0**1.5
    g = detalle.gancho_normal(25.4, mat)
    assert g.ldh == pytest.approx(ldh_in * 25.4, rel=0.01)


def test_compresion_y_empalmes():
    # ldc = max(0.24·420/√28, 0.043·420)·20 = max(381.0, 361.2) = 381.0 mm
    assert detalle.longitud_desarrollo_compresion(20, MAT) == rel(0.24 * 420 / RAIZ * 20)
    assert detalle.longitud_desarrollo_compresion(20, MAT, confinada=True) == rel(
        0.75 * 0.24 * 420 / RAIZ * 20
    )
    assert detalle.longitud_desarrollo_compresion(8, MAT) == 200.0
    # Empalme comprimido: 0.071·420·20 = 596.4 mm (≈ 30 db, como 0.0005 fy db en inglesas).
    assert detalle.empalme_compresion(20, MAT) == rel(596.4)
    m550 = aci318.Materiales(fc=28, fy=550)
    assert detalle.empalme_compresion(20, m550) == rel((0.13 * 550 - 24) * 20)
    m18 = aci318.Materiales(fc=18, fy=420)
    assert detalle.empalme_compresion(20, m18) == rel(596.4 * 4 / 3)
    # Empalme traccionado.
    assert detalle.empalme_traccion(600, "B") == rel(780.0)
    assert detalle.empalme_traccion(600, "A") == rel(600.0)
    assert detalle.empalme_traccion(200, "B") == 300.0
    with pytest.raises(ValueError):
        detalle.empalme_traccion(600, "C")


def test_detallar_viga_continua():
    seccion = aci318.SeccionRectangular(b=250, h=500, recubrimiento=40, d_estribo=8)
    mat = aci318.Materiales(fc=25, fy=420)
    m = nervi.Modelo()
    nudos = [m.agregar_nudo(x, 0.0) for x in (0.0, 5.0, 10.0)]
    props = dict(E=2.35e7, A=0.25 * 0.50, I=0.25 * 0.50**3 / 12)
    tramos = [m.agregar_barra(nudos[k], nudos[k + 1], **props) for k in range(2)]
    m.apoyar(nudos[0], rz=False)
    m.apoyar(nudos[1], ux=False, rz=False)
    m.apoyar(nudos[2], ux=False, rz=False)
    for barra in tramos:
        m.carga_uniforme("D", barra, qy=-18.0)
        m.carga_uniforme("L", barra, qy=-8.0)
    combs = design.generar({"D": "D", "L": "L"})
    res = m.resolver(combinaciones=design.como_diccionario(combs))
    dis = aci318.disenar_viga(
        res, 0, seccion, mat, ancho_apoyo_i=250, ancho_apoyo_j=250, diametros=(12, 16)
    )
    det = detalle.detallar_viga(dis, seccion, mat, luz_libre=4750)
    assert det.cumple
    for a, disp in ((det.inferior, dis.inferior), (det.superior, dis.superior)):
        capa = disp.capas[0]
        db = max(capa)
        libre = (250 - 2 * 48 - sum(capa)) / (len(capa) - 1)
        assert a.s_libre == rel(libre)
        cb = min(48 + db / 2, (libre + db) / 2)
        e = dis.estribos
        ktr = 40 * e.ramas * math.pi * e.diametro**2 / 4 / (e.s * len(capa)) if e else 0.0
        conf = min((cb + ktr) / db, 2.5)
        pt = 1.3 if a.posicion == "superior" else 1.0
        ld = max(420 * pt * detalle.psi_s(db) / (1.1 * 5.0 * conf) * db, 300.0)
        assert a.desarrollo.ld == rel(ld)
        assert a.empalme_clase_b == rel(max(1.3 * ld, 300.0))
        assert a.prolongacion_corte == rel(max(disp.d, 12 * db))
    n_inf = sum(len(c) for c in dis.inferior.capas)
    assert det.inferior.barras_continuas == max(math.ceil(n_inf / 4), 2)
    db_sup = max(dis.superior.capas[0])
    assert det.superior.longitud_continua == rel(max(dis.superior.d, 12 * db_sup, 4750 / 16))
    assert det.superior.desarrollo.psi_t == 1.3
    sin_luz = detalle.detallar_viga(dis, seccion, mat)
    assert sin_luz.avisos


def test_api_publica():
    assert aci318.servicio is servicio and aci318.detalle is detalle
    assert np.isfinite(servicio.momento_fisuracion(aci318.SeccionRectangular(300, 500), MAT))
