# SPDX-License-Identifier: GPL-3.0-or-later
"""Cargas por planta: reparto de las losas a vigas y muros (issue #78).

Criterio de salida del issue: equilibrio global exacto y reparto tributario contra
cálculo a mano en losas rectangulares.
"""

import importlib.util
import math
from pathlib import Path

import pytest

from nervi import formato
from nervi.fisico import ModeloFisico
from nervi.formato.errores import FormatoError
from nervi.reparto import PESO_HORMIGON

RAIZ = Path(__file__).resolve().parents[1]


def _rect(longitud="m", escala=1.0, **cargas_piso):
    """Losa de 6 x 4 m con vigas en los cuatro lados, en el piso 1."""
    mf = ModeloFisico(longitud)
    mf.agregar_piso("PB", 0.0)
    p1 = mf.agregar_piso("P1", 3.0 * escala, **cargas_piso)
    h = mf.agregar_material("H-25", "hormigon", fc=25.0)
    s = mf.agregar_seccion("V", "rectangular", b=200.0, h=500.0)
    c = [(0.0, 0.0), (6.0 * escala, 0.0), (6.0 * escala, 4.0 * escala), (0.0, 4.0 * escala)]
    for k in range(4):
        mf.agregar_viga(p1, c[k], c[(k + 1) % 4], s, h, nombre=f"V{k + 1}")
    mf.agregar_losa(p1, c, 150.0, h, nombre="L1")
    return mf


def test_losa_rectangular_contra_calculo_a_mano():
    mf = _rect(permanente=1.0, sobrecarga=2.0)
    r = mf.repartir_cargas()
    assert r.avisos == [] and r.repartidas == {1}
    # Peso propio: 0,15 m · 25 kN/m³ = 3,75 kN/m².
    assert mf.cargas_losa(1) == {
        "peso_propio": pytest.approx(0.15 * PESO_HORMIGON),
        "permanente": 1.0,
        "sobrecarga": 2.0,
    }
    # Vigas largas: trapecio de 8 m²; cortas: triángulo de 4 m².
    for viga, area in ((1, 8.0), (2, 4.0), (3, 8.0), (4, 4.0)):
        assert r.area_tributaria(("vigas", viga)) == pytest.approx(area, rel=1e-14)
        assert r.resultante(("vigas", viga), "sobrecarga") == pytest.approx(2.0 * area)
    # V1: carga de 0 a 4 kN/m entre 0 y 2 m, 4 kN/m hasta 4 m y vuelve a 0 en 6 m.
    tramos = sorted(r.de_viga(1), key=lambda t: t.a)
    extremos = [x for t in tramos for x in (t.a, t.b)]
    assert extremos == pytest.approx([0, 2, 2, 4, 4, 6])
    cargas = [q for t in tramos for q in t.cargas["sobrecarga"]]
    assert cargas == pytest.approx([0.0, 4.0, 4.0, 4.0, 4.0, 0.0])
    assert all(t.piso == 2 for t in tramos)


def test_equilibrio_global_exacto_en_el_edificio_de_ejemplo():
    spec = importlib.util.spec_from_file_location(
        "edificio_fisico", RAIZ / "examples" / "edificio_fisico.py"
    )
    ejemplo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ejemplo)
    mf = ejemplo.armar()
    r = mf.repartir_cargas()
    assert r.avisos == []
    assert r.repartidas == {losa["id"] for losa in mf.lista("losas")}
    for caso in r.casos:
        assert math.isclose(r.total(caso), r.total_losas(caso), rel_tol=1e-13)
    assert r.total_losas("peso_propio") == pytest.approx(6 * 30.0 * 0.12 * 25.0)
    # La viga entre las dos losas recibe dos trapecios de (6 + 1)/2 · 2,5 = 8,75 m².
    piso1 = mf.pisos_ordenados()[1]["id"]
    v = next(
        x for x in mf.en_piso(piso1)["vigas"] if x["p1"] == [0.0, 0.0] and x["p2"] == [6.0, 0.0]
    )
    assert r.area_tributaria(("vigas", v["id"])) == pytest.approx(8.75)


def test_misma_carga_en_otra_unidad():
    # El mismo edificio en mm da las mismas cargas lineales y abscisas en mm.
    en_m = _rect(sobrecarga=2.0).repartir_cargas()
    en_mm = _rect("mm", 1000.0, sobrecarga=2.0).repartir_cargas()
    for viga in range(1, 5):
        a = sorted(en_m.de_viga(viga), key=lambda t: t.a)
        b = sorted(en_mm.de_viga(viga), key=lambda t: t.a)
        assert [t.a * 1000 for t in a] == pytest.approx([t.a for t in b])
        for x, y in zip(a, b, strict=True):
            assert x.cargas["sobrecarga"] == pytest.approx(y.cargas["sobrecarga"])
        assert en_m.resultante(("vigas", viga), "sobrecarga") == pytest.approx(
            en_mm.resultante(("vigas", viga), "sobrecarga")
        )


def test_la_losa_reemplaza_las_cargas_del_piso_y_peso_del_material():
    mf = _rect(permanente=1.0, sobrecarga=2.0)
    mf.editar("losas", 1, sobrecarga=5.0)
    liviano = mf.agregar_material("HL", "hormigon", fc=20.0, peso=18.0)
    mf.editar("losas", 1, material=liviano)
    q = mf.cargas_losa(1)
    assert q["sobrecarga"] == 5.0 and q["permanente"] == 1.0
    assert q["peso_propio"] == pytest.approx(0.15 * 18.0)
    r = mf.repartir_cargas()
    assert r.total("sobrecarga") == pytest.approx(5.0 * 24.0)


def test_muros_apoyan_las_losas_de_los_pisos_que_alcanzan():
    # Losa de 6 x 4 m en el piso 2, apoyada en dos muros que van de PB al piso 2.
    mf = ModeloFisico()
    pb = mf.agregar_piso("PB", 0.0)
    mf.agregar_piso("P1", 3.0)
    p2 = mf.agregar_piso("P2", 6.0, sobrecarga=3.0)
    h = mf.agregar_material("H", "hormigon", fc=25.0)
    m1 = mf.agregar_muro((0.0, 0.0), (6.0, 0.0), pb, p2, 200.0, h)
    m2 = mf.agregar_muro((6.0, 4.0), (0.0, 4.0), pb, p2, 200.0, h)
    mf.agregar_losa(p2, [(0, 0), (6, 0), (6, 4), (0, 4)], 120.0, h)
    r = mf.repartir_cargas()
    # Losa en una dirección: cada muro recibe 2 m de ancho, 6 kN/m.
    for m in (m1, m2):
        assert r.resultante(("muros", m), "sobrecarga") == pytest.approx(36.0)
        assert {t.piso for t in r.de_muro(m)} == {p2}
        assert all(t.cargas["sobrecarga"] == pytest.approx((6.0, 6.0)) for t in r.de_muro(m))


def test_avisos_y_losas_sin_repartir():
    mf = ModeloFisico()
    mf.agregar_piso("PB", 0.0)
    p1 = mf.agregar_piso("P1", 3.0, sobrecarga=2.0)
    h = mf.agregar_material("H", "hormigon", fc=25.0)
    mf.agregar_losa(p1, [(0, 0), (4, 0), (4, 2), (2, 2), (2, 4), (0, 4)], 120.0, h)
    mf.agregar_losa(p1, [(10, 0), (14, 0), (14, 4), (10, 4)], 120.0, h)
    r = mf.repartir_cargas()
    assert r.repartidas == set() and r.tramos == []
    assert [a.motivo for a in r.avisos] == ["no_convexa", "sin_apoyos"]
    assert "no es convexa" in r.avisos[0].texto and "La losa 1" in r.avisos[0].texto
    assert r.total("sobrecarga") == 0.0 == r.total_losas("sobrecarga")


def test_zonas_tributarias_cubren_la_losa():
    mf = _rect()
    r = mf.repartir_cargas()
    assert len(r.zonas) == 4
    area = 0.0
    for z in r.zonas:
        c = z.contorno
        area += 0.5 * sum(
            c[k][0] * c[(k + 1) % len(c)][1] - c[(k + 1) % len(c)][0] * c[k][1]
            for k in range(len(c))
        )
        assert len(z.apoyos) == 1 and z.apoyos[0][0] == "vigas"
    assert area == pytest.approx(24.0, rel=1e-14)


@pytest.mark.parametrize(
    ("lista", "clave", "valor", "motivo"),
    [
        ("pisos", "sobrecarga", -1.0, "negativa"),
        ("losas", "permanente", "2", "número"),
        ("materiales", "peso", 0.0, "mayor que 0"),
    ],
)
def test_cargas_invalidas(lista, clave, valor, motivo):
    mf = _rect()
    with pytest.raises(FormatoError, match=motivo):
        mf.editar(lista, 1, **{clave: valor})


def test_cargas_se_guardan_en_el_nrv(tmp_path):
    mf = _rect(permanente=1.5, sobrecarga=2.0)
    mf.editar("losas", 1, sobrecarga=3.0)
    doc = formato.Documento.nuevo()
    doc.fisico = mf.a_json()
    ruta = tmp_path / "cargas.nrv"
    formato.guardar(doc, ruta)
    abierto = formato.abrir(ruta)
    assert abierto.manifiesto["modulos"]["fisico"]["version"] == 2
    otra = ModeloFisico.desde_json(abierto.fisico)
    assert otra.a_json() == mf.a_json()
    assert otra.cargas_losa(1)["sobrecarga"] == 3.0
