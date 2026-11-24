# SPDX-License-Identifier: GPL-3.0-or-later
"""Importación de DXF (python/nervi/importar/dxf.py): lectura y armado del modelo."""

import doctest

import pytest

from nervi.formato import modelo as fmodelo
from nervi.importar import dxf


def _dxf(entidades: list[str], insunits: int | None = None) -> str:
    """Arma un DXF en texto con las entidades dadas (cada una ya en pares)."""
    cabecera = ["0", "SECTION", "2", "HEADER"]
    if insunits is not None:
        cabecera += ["9", "$INSUNITS", "70", str(insunits)]
    cabecera += ["0", "ENDSEC"]
    cuerpo = ["0", "SECTION", "2", "ENTITIES"]
    for e in entidades:
        cuerpo += e.strip().split("\n")
    cuerpo += ["0", "ENDSEC", "0", "EOF"]
    return "\n".join(cabecera + cuerpo) + "\n"


def _linea(xa, ya, xb, yb, capa="0") -> str:
    return f"0\nLINE\n8\n{capa}\n10\n{xa}\n20\n{ya}\n11\n{xb}\n21\n{yb}"


def _lw(puntos, capa="0", cerrada=False, bulge_en=None) -> str:
    pares = f"0\nLWPOLYLINE\n8\n{capa}\n90\n{len(puntos)}\n70\n{1 if cerrada else 0}"
    for k, (x, y) in enumerate(puntos):
        pares += f"\n10\n{x}\n20\n{y}"
        if bulge_en == k:
            pares += "\n42\n0.5"
    return pares


def _coords(modelo):
    return sorted((n["x"], n["y"]) for n in modelo["nudos"])


def test_doctest_del_modulo():
    assert doctest.testmod(dxf).failed == 0


def test_ejemplo_da_un_portico_valido():
    r = dxf.importar(dxf.leer_texto(dxf._EJEMPLO))
    fmodelo.validar(r.modelo)
    assert _coords(r.modelo) == [(0, 0), (0, 3), (6, 0), (6, 3)]
    assert (r.nudos_nuevos, r.barras_nuevas) == (4, 3)
    assert any("1 textos" in a for a in r.avisos)


def test_unidad_declarada_y_elegida():
    texto = _dxf([_linea(0, 0, 500, 0)], insunits=5)
    d = dxf.leer_texto(texto)
    assert d.unidad == "cm"
    assert _coords(dxf.importar(d).modelo) == [(0, 0), (5, 0)]
    # La elegida manda sobre la declarada.
    assert _coords(dxf.importar(d, unidad="mm").modelo) == [(0, 0), (0.5, 0)]


def test_sin_unidad_pide_elegirla():
    d = dxf.leer_texto(_dxf([_linea(0, 0, 1, 0)]))
    assert d.unidad is None
    with pytest.raises(dxf.DXFError, match="unidad"):
        dxf.importar(d)
    assert len(dxf.importar(d, unidad="m").modelo["barras"]) == 1


def test_t_y_cruce_cortan_las_barras():
    # Una viga de 0 a 6 con una columna que llega en x=3 (T) y una diagonal que la cruza.
    texto = _dxf(
        [_linea(0, 3, 6, 3), _linea(3, 0, 3, 3), _linea(4, 2, 5, 4)],
        insunits=6,
    )
    r = dxf.importar(dxf.leer_texto(texto), al_origen=False)
    assert (3, 3) in _coords(r.modelo) and (4.5, 3) in _coords(r.modelo)
    # Viga en 3 tramos, columna 1, diagonal en 2.
    assert len(r.modelo["barras"]) == 6
    fmodelo.validar(r.modelo)


def test_extremos_cercanos_se_unen_con_la_tolerancia():
    # La columna termina 4 mm por debajo de la viga: con 1 cm se une, con 1 mm no.
    texto = _dxf([_linea(0, 3000, 6000, 3000), _linea(0, 0, 0, 2996)], insunits=4)
    d = dxf.leer_texto(texto)
    assert len(dxf.importar(d).modelo["nudos"]) == 3
    assert len(dxf.importar(d, tolerancia=0.001).modelo["nudos"]) == 4


def test_lineas_cortas_y_repetidas_se_descartan():
    texto = _dxf(
        [_linea(0, 0, 0, 3), _linea(0, 3, 0, 0), _linea(5, 5, 5, 5.001)],
        insunits=6,
    )
    r = dxf.importar(dxf.leer_texto(texto))
    assert len(r.modelo["barras"]) == 1
    assert len(r.modelo["nudos"]) == 2
    assert any("repetidas" in a for a in r.avisos)
    assert any("más cortas" in a for a in r.avisos)


def test_polilineas_cerradas_y_con_arcos():
    texto = _dxf(
        [_lw([(0, 0), (4, 0), (4, 3), (0, 3)], cerrada=True, bulge_en=1)],
        insunits=6,
    )
    d = dxf.leer_texto(texto)
    assert d.arcos_en_polilineas == 1
    r = dxf.importar(d)
    assert len(r.modelo["barras"]) == 4
    assert any("curvos" in a for a in r.avisos)


def test_polyline_con_vertices():
    poli = (
        "0\nPOLYLINE\n8\nP\n66\n1\n70\n0\n"
        "0\nVERTEX\n8\nP\n10\n0\n20\n0\n"
        "0\nVERTEX\n8\nP\n10\n0\n20\n3\n"
        "0\nVERTEX\n8\nP\n10\n5\n20\n3\n"
        "0\nSEQEND\n8\nP"
    )
    d = dxf.leer_texto(_dxf([poli, _linea(9, 9, 9, 10, capa="Q")], insunits=6))
    assert len(d.capas["P"]) == 2 and len(d.capas["Q"]) == 1


def test_capas_elegidas():
    texto = _dxf(
        [_linea(0, 0, 0, 3, "EJES"), _linea(0, 0, 0, 3, "COL"), _linea(0, 3, 5, 3, "VIG")],
        insunits=6,
    )
    d = dxf.leer_texto(texto)
    r = dxf.importar(d, capas=["COL", "VIG"])
    assert len(r.modelo["barras"]) == 2
    with pytest.raises(dxf.DXFError, match="no tienen líneas"):
        dxf.importar(d, capas=["NADA"])


def test_empotrar_la_base():
    texto = _dxf([_linea(0, 0, 0, 3), _linea(5, 0, 5, 3), _linea(0, 3, 5, 3)], insunits=6)
    r = dxf.importar(dxf.leer_texto(texto), empotrar_base=True)
    apoyados = {a["nudo"] for a in r.modelo["apoyos"]}
    abajo = {n["id"] for n in r.modelo["nudos"] if n["y"] == 0}
    assert apoyados == abajo and len(abajo) == 2
    assert all(a["ux"] and a["uy"] and a["rz"] for a in r.modelo["apoyos"])


def test_se_suma_a_un_modelo_existente():
    base = fmodelo.nuevo()
    base["unidades"] = {"fuerza": "tf", "longitud": "cm"}
    base["nudos"] = [{"id": 1, "x": 0, "y": 0}, {"id": 7, "x": 0, "y": 300}]
    base["barras"] = [{"id": 4, "i": 1, "j": 7, "E": 250, "A": 900, "I": 67500}]
    # Una viga en metros que arranca en el nudo 7 existente.
    texto = _dxf([_linea(0, 3, 5, 3)], insunits=6)
    r = dxf.importar(dxf.leer_texto(texto), base=base)
    fmodelo.validar(r.modelo)
    assert base["barras"] == [{"id": 4, "i": 1, "j": 7, "E": 250, "A": 900, "I": 67500}]
    nueva = r.modelo["barras"][-1]
    assert (nueva["id"], nueva["i"], nueva["j"]) == (5, 7, 8)
    assert (nueva["E"], nueva["A"], nueva["I"]) == (250, 900, 67500)
    assert {"id": 8, "x": 500, "y": 300} in r.modelo["nudos"]
    assert r.nudos_nuevos == 1


def test_una_linea_que_pasa_por_un_nudo_existente_se_corta_ahi():
    # El modelo tiene una columna de 0 a 3 m; el dibujo, una de 0 a 6 m encima.
    base = fmodelo.nuevo()
    base["nudos"] = [{"id": 1, "x": 0, "y": 0}, {"id": 2, "x": 0, "y": 3}]
    base["barras"] = [{"id": 1, "i": 1, "j": 2, "E": 1, "A": 1, "I": 1}]
    r = dxf.importar(dxf.leer_texto(_dxf([_linea(0, 0, 0, 6)], insunits=6)), base=base)
    assert [(b["i"], b["j"]) for b in r.modelo["barras"]] == [(1, 2), (2, 3)]
    assert any("repetidas" in a for a in r.avisos)


def test_seccion_por_omision_en_las_unidades_del_modelo():
    base = fmodelo.nuevo()
    base["unidades"] = {"fuerza": "kgf", "longitud": "cm"}
    r = dxf.importar(dxf.leer_texto(_dxf([_linea(0, 0, 1, 0)], insunits=6)), base=base)
    b = r.modelo["barras"][0]
    assert b["A"] == pytest.approx(900)
    assert b["I"] == pytest.approx(30**4 / 12)
    assert b["E"] == pytest.approx(2.5e7 / 0.00980665 / 1e4)


def test_archivos_que_no_son_dxf(tmp_path):
    binario = tmp_path / "b.dxf"
    binario.write_bytes(b"AutoCAD Binary DXF\r\n\x1a\x00")
    with pytest.raises(dxf.DXFError, match="binario"):
        dxf.leer(binario)
    with pytest.raises(dxf.DXFError):
        dxf.leer_texto("hola\nmundo\n")
    latin = tmp_path / "l.dxf"
    latin.write_bytes(_dxf([_linea(0, 0, 1, 0, capa="VIGAS_AÑO")], 6).encode("cp1252"))
    assert "VIGAS_AÑO" in dxf.leer(latin).capas
