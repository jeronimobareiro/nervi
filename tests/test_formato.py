# SPDX-License-Identifier: GPL-3.0-or-later
"""Pruebas del formato .nrv (docs/formato-nrv.md §8)."""

import json
import zipfile

import numpy as np
import pytest

import nervi
from nervi import formato

E = 2.5e7


def _portico():
    m = nervi.Modelo()
    a, b, c, d = (m.agregar_nudo(x, y) for x, y in ((0, 0), (0, 3), (6, 3), (6, 0)))
    m.agregar_barra(a, b, E=E, A=0.09, I=0.3**4 / 12)
    viga = m.agregar_barra(b, c, E=E, A=0.125, I=0.25 * 0.5**3 / 12, articulada_j=True)
    m.agregar_barra(d, c, E=E, A=0.09, I=0.3**4 / 12)
    m.apoyar(a)
    m.apoyar(d, rz=False)
    m.resorte(b, kx=1e3)
    m.carga_uniforme("D", viga, qy=-20.0)
    m.carga_puntual("L", viga, a=2.5, py=-15.0, ejes="global")
    m.carga_trapezoidal("L", viga, qy1=-4.0, qy2=-9.0, a=1.0)  # hasta el nudo j
    m.carga_parcial("D", viga, a=0.5, b=2.0, qx=1.0, qy=-6.0, ejes="global")
    m.carga_nodal("W", b, fx=15.0)
    m.desplazamiento_impuesto("D", a, uy=-0.001)
    return m


def _guardar(tmp_path, doc, nombre="p.nrv"):
    ruta = tmp_path / nombre
    formato.guardar(doc, ruta)
    return ruta


def test_ida_y_vuelta_bit_a_bit(tmp_path):
    m = _portico()
    doc = formato.Documento.desde_modelo(m, {"1.2D+1.6L": {"D": 1.2, "L": 1.6}})
    doc2 = formato.abrir(_guardar(tmp_path, doc))
    assert doc2.modelo == doc.modelo
    m2, _ = formato.construir_modelo(doc2.modelo)
    a1, a2 = m.arreglos(), m2.arreglos()
    for k in a1:
        assert a1[k].dtype == a2[k].dtype
        assert np.array_equal(a1[k], a2[k]), k
    r1, r2 = m.resolver(), m2.resolver()
    assert np.array_equal(r1["D"].reacciones, r2["D"].reacciones)


def test_firma_mimetype(tmp_path):
    ruta = _guardar(tmp_path, formato.Documento.nuevo())
    datos = ruta.read_bytes()
    assert datos[:4] == b"PK\x03\x04"
    assert datos[30 : 38 + len(formato.MIMETYPE)] == b"mimetype" + formato.MIMETYPE.encode()
    with zipfile.ZipFile(ruta) as zf:
        assert zf.infolist()[0].compress_type == zipfile.ZIP_STORED
        man = json.loads(zf.read("nervi.json"))
    assert man["formato"] == "nervi.proyecto" and man["version_esquema"] == 1


def test_conserva_miembros_desconocidos(tmp_path):
    doc = formato.Documento.nuevo()
    doc.otros["vista.json"] = b'{"camara": 1}'
    doc.otros["adjuntos/nota.txt"] = "ñandú".encode()
    doc2 = formato.abrir(_guardar(tmp_path, doc))
    assert doc2.otros == doc.otros


def test_ids_no_consecutivos():
    d = formato.Documento.nuevo().modelo
    d["nudos"] = [{"id": 10, "x": 0.0, "y": 0.0}, {"id": 3, "x": 4.0, "y": 0.0}]
    d["barras"] = [{"id": 7, "i": 10, "j": 3, "E": 2e8, "A": 0.01, "I": 1e-4}]
    d["apoyos"] = [{"nudo": 10, "ux": True, "uy": True, "rz": True}]
    d["casos"] = [{"id": 5, "nombre": "P"}]
    d["cargas_nodales"] = [{"caso": 5, "nudo": 3, "fy": -10.0}]
    m, ind = formato.construir_modelo(d)
    assert ind.nudos == {10: 0, 3: 1} and ind.barras == {7: 0}
    r = m.resolver()
    assert r["P"].reacciones[0, 1] == pytest.approx(10.0)


def _escribir(tmp_path, miembros, primero_comprimido=False):
    ruta = tmp_path / "x.nrv"
    with zipfile.ZipFile(ruta, "w") as zf:
        for nombre, datos in miembros:
            tipo = zipfile.ZIP_STORED
            if nombre != "mimetype" or primero_comprimido:
                tipo = zipfile.ZIP_DEFLATED
            zf.writestr(nombre, datos, tipo)
    return ruta


def _validos(version=1):
    man = {"formato": "nervi.proyecto", "version_esquema": version}
    return [
        ("mimetype", formato.MIMETYPE),
        ("nervi.json", json.dumps(man)),
        ("modelo.json", json.dumps(formato.Documento.nuevo().modelo)),
    ]


def test_version_futura(tmp_path):
    with pytest.raises(formato.FormatoError, match="formato 2"):
        formato.abrir(_escribir(tmp_path, _validos(version=2)))


def test_no_es_zip(tmp_path):
    ruta = tmp_path / "nero.nrv"
    ruta.write_bytes(b"\x00NERO VCD compilation")
    with pytest.raises(formato.FormatoError, match="no es un archivo ZIP"):
        formato.abrir(ruta)


def test_zip_cualquiera(tmp_path):
    with pytest.raises(formato.FormatoError, match="mimetype"):
        formato.abrir(_escribir(tmp_path, [("hola.txt", "hola")]))


def test_mimetype_comprimido(tmp_path):
    with pytest.raises(formato.FormatoError, match="sin comprimir"):
        formato.abrir(_escribir(tmp_path, _validos(), primero_comprimido=True))


def test_ruta_con_puntos(tmp_path):
    with pytest.raises(formato.FormatoError, match="no permitido"):
        formato.abrir(_escribir(tmp_path, [*_validos(), ("../fuera.txt", "x")]))


@pytest.mark.parametrize(
    ("cambio", "mensaje"),
    [
        (lambda d: d["barras"][0].update(j=17), r"barras\[0\]\.j.*no existe el nudo 17"),
        (lambda d: d["barras"][0].update(E=0), r"barras\[0\]\.E.*mayor que cero"),
        (lambda d: d["barras"][0].update(j=1), r"distintos"),
        (lambda d: d["nudos"][1].update(id=1), r"id repetido"),
        (lambda d: d["casos"].append({"id": 2, "nombre": "D"}), r"repetido"),
        (lambda d: d["nudos"][0].update(x=float("nan")), r"número finito"),
        (lambda d: d.update(sobra=1), r"clave desconocida"),
        (lambda d: d["combinaciones"].append({"nombre": "C", "factores": {"Z": 1}}), "caso 'Z'"),
        (
            lambda d: d["cargas_barra"].append(
                {"caso": 1, "barra": 1, "tipo": "puntual", "ejes": "local", "a": 9.0}
            ),
            r"entre 0 y la longitud",
        ),
        (
            lambda d: d["cargas_barra"].append(
                {"caso": 1, "barra": 1, "tipo": "trapezoidal", "ejes": "local", "a": 3.0, "b": 2.0}
            ),
            r"cargas_barra\[0\]\.b.*mayor que a",
        ),
        (
            lambda d: d["cargas_barra"].append(
                {"caso": 1, "barra": 1, "tipo": "trapezoidal", "ejes": "local", "b": 5.0}
            ),
            r"no pasar la longitud",
        ),
        (
            lambda d: d["cargas_barra"].append(
                {"caso": 1, "barra": 1, "tipo": "trapezoidal", "ejes": "local", "qy": -1.0}
            ),
            r"no 'qy'",
        ),
        (
            lambda d: d["cargas_barra"].append(
                {"caso": 1, "barra": 1, "tipo": "lineal", "ejes": "local"}
            ),
            r"'trapezoidal'",
        ),
    ],
)
def test_validacion(cambio, mensaje):
    d = formato.Documento.nuevo().modelo
    d["nudos"] = [{"id": 1, "x": 0.0, "y": 0.0}, {"id": 2, "x": 4.0, "y": 0.0}]
    d["barras"] = [{"id": 1, "i": 1, "j": 2, "E": 2e8, "A": 0.01, "I": 1e-4}]
    d["casos"] = [{"id": 1, "nombre": "D"}]
    formato.validar(d)
    cambio(d)
    with pytest.raises(formato.FormatoError, match=mensaje):
        formato.validar(d)


def test_copia_bak_y_sin_tmp(tmp_path):
    doc = formato.Documento.nuevo()
    ruta = _guardar(tmp_path, doc)
    formato.guardar(doc, ruta, copia_bak=True)
    assert (tmp_path / "p.nrv.bak").exists()
    assert not (tmp_path / "p.nrv.tmp").exists()


def test_trapezoidal_hasta_el_nudo_j_sigue_a_la_barra():
    """Sin "b", la carga llega al nudo j aunque la barra cambie de longitud."""
    d = formato.Documento.nuevo().modelo
    d["nudos"] = [{"id": 1, "x": 0.0, "y": 0.0}, {"id": 2, "x": 4.0, "y": 0.0}]
    d["barras"] = [{"id": 1, "i": 1, "j": 2, "E": 2e8, "A": 0.01, "I": 1e-4}]
    d["apoyos"] = [{"nudo": 1, "ux": True, "uy": True}, {"nudo": 2, "uy": True}]
    d["casos"] = [{"id": 1, "nombre": "D"}]
    d["cargas_barra"] = [
        {"caso": 1, "barra": 1, "tipo": "trapezoidal", "ejes": "local", "qy1": -3.0, "qy2": -3.0}
    ]
    for largo in (4.0, 6.0):
        d["nudos"][1]["x"] = largo
        formato.validar(d)
        m, _ = formato.construir_modelo(d)
        r = m.resolver()["D"].reacciones
        assert r[:, 1].sum() == pytest.approx(3.0 * largo)


def test_tipo_de_carga_sin_esquema_da_error_claro():
    m = _portico()
    m._cargas_barra.append((0, 0, 3, 0, 1e-5, 20.0, 0.0, 0.5, 0.0, 0.0))
    with pytest.raises(formato.FormatoError, match="tipo de carga en barra 3"):
        formato.desde_modelo(m)
