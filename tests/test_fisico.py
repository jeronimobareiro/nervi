# SPDX-License-Identifier: GPL-3.0-or-later
"""Modelo físico del edificio (issue #73) y módulo ``fisico`` del ``.nrv``."""

import copy
import importlib.util
from pathlib import Path

import pytest

from nervi import formato
from nervi.fisico import ModeloFisico
from nervi.formato import FormatoError
from nervi.proyecto import Proyecto

RAIZ = Path(__file__).resolve().parents[1]


def _ejemplo():
    spec = importlib.util.spec_from_file_location(
        "edificio_fisico", RAIZ / "examples" / "edificio_fisico.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def edificio() -> ModeloFisico:
    return _ejemplo().armar()


@pytest.fixture
def base():
    mf = ModeloFisico()
    pb = mf.agregar_piso("PB", 0.0)
    p1 = mf.agregar_piso("P1", 3.0)
    h = mf.agregar_material("H-25", "hormigon", fc=25.0)
    s = mf.agregar_seccion("C 30x30", "rectangular", b=300.0, h=300.0)
    return mf, pb, p1, h, s


def test_criterio_de_salida_edificio_de_3_pisos(edificio, tmp_path):
    # Criterio de salida de #73: un edificio de 3 pisos con losas y muros se arma,
    # se guarda y se vuelve a abrir igual.
    doc = formato.Documento.nuevo()
    doc.fisico = edificio.a_json()
    ruta = tmp_path / "edificio.nrv"
    formato.guardar(doc, ruta)
    abierto = formato.abrir(ruta)
    assert abierto.avisos == []
    assert abierto.manifiesto["modulos"]["fisico"] == {
        "version": 2,
        "miembros": ["fisico.json"],
        "requerido": False,
    }
    otra = ModeloFisico.desde_json(abierto.fisico)
    assert otra.a_json() == edificio.a_json()
    # Guardar otra vez lo abierto da los mismos bytes de fisico.json.
    ruta2 = tmp_path / "otra.nrv"
    formato.guardar(abierto, ruta2)
    import zipfile

    with zipfile.ZipFile(ruta) as a, zipfile.ZipFile(ruta2) as b:
        assert a.read("fisico.json") == b.read("fisico.json")


def test_consultas_del_edificio(edificio):
    assert len(edificio) == 18 + 21 + 6 + 1
    assert [p["nombre"] for p in edificio.pisos_ordenados()] == [
        "Planta baja",
        "Piso 1",
        "Piso 2",
        "Piso 3",
    ]
    p1 = edificio.pisos_ordenados()[1]["id"]
    en = edificio.en_piso(p1)
    assert len(en["columnas"]) == 6 and len(en["vigas"]) == 7 and len(en["losas"]) == 2
    assert edificio.area_losa(en["losas"][0]["id"]) == 30.0
    assert edificio.altura_columna(en["columnas"][0]["id"]) == 3.0
    assert edificio.largo_viga(en["vigas"][0]["id"]) == 6.0
    muro = edificio.lista("muros")[0]
    assert edificio.nivel(muro["hasta"]) - edificio.nivel(muro["desde"]) == 9.0


def test_area_de_contorno_horario_es_positiva(base):
    mf, _, p1, h, _ = base
    losa = mf.agregar_losa(p1, [(0, 0), (0, 4), (5, 4), (5, 0)], 120.0, h)
    assert mf.area_losa(losa) == 20.0
    assert "tipo" not in mf.elemento("losas", losa)  # ausente vale "maciza"


def test_sin_modelo_fisico_no_se_escribe_el_modulo(tmp_path):
    ruta = tmp_path / "p.nrv"
    formato.guardar(formato.Documento.nuevo(), ruta)
    doc = formato.abrir(ruta)
    assert doc.fisico is None
    assert "fisico" not in doc.manifiesto["modulos"]


def test_ids_consecutivos_y_elementos_inmutables_desde_afuera(base):
    mf, pb, p1, h, s = base
    c1 = mf.agregar_columna((0, 0), pb, p1, s, h, nombre="C1")
    c2 = mf.agregar_columna((5, 0), pb, p1, s, h, nombre="C1")  # nombres repetibles
    assert (c1, c2) == (1, 2)
    copia = mf.elemento("columnas", c1)
    copia["punto"][0] = 99.0
    assert mf.elemento("columnas", c1)["punto"] == [0.0, 0.0]


@pytest.mark.parametrize(
    ("agregar", "mensaje"),
    [
        (lambda mf, pb, p1, h, s: mf.agregar_piso("P1", 6.0), "nombre repetido"),
        (lambda mf, pb, p1, h, s: mf.agregar_piso("P2", 3.0), "ya hay un piso en este nivel"),
        (lambda mf, pb, p1, h, s: mf.agregar_eje("A", (0, 0), (0, 0)), "distinto de p1"),
        (lambda mf, pb, p1, h, s: mf.agregar_material("X", "madera"), "uno de"),
        (lambda mf, pb, p1, h, s: mf.agregar_material("X", "hormigon"), "falta esta clave"),
        (lambda mf, pb, p1, h, s: mf.agregar_material("X", "hormigon", fc=-1.0), "mayor que 0"),
        (
            lambda mf, pb, p1, h, s: mf.agregar_material("X", "hormigon", fc=25.0, fy=420.0),
            "no corresponde",
        ),
        (
            lambda mf, pb, p1, h, s: mf.agregar_material("X", "acero", fy=355.0, fu=300.0),
            "mayor o igual que fy",
        ),
        (
            lambda mf, pb, p1, h, s: mf.agregar_seccion("X", "rectangular", b=200.0),
            "falta esta clave",
        ),
        (
            lambda mf, pb, p1, h, s: mf.agregar_seccion("X", "circular", d=300.0, b=1.0),
            "no corresponde",
        ),
        (lambda mf, pb, p1, h, s: mf.agregar_columna((0, 0), p1, pb, s, h), "más arriba"),
        (lambda mf, pb, p1, h, s: mf.agregar_columna((0, 0), pb, 9, s, h), "no existe el piso 9"),
        (
            lambda mf, pb, p1, h, s: mf.agregar_columna((0, 0), pb, p1, 9, h),
            "no existe la sección 9",
        ),
        (
            lambda mf, pb, p1, h, s: mf.agregar_columna((0, float("nan")), pb, p1, s, h),
            "números finitos",
        ),
        (lambda mf, pb, p1, h, s: mf.agregar_viga(p1, (0, 0), (0, 0), s, h), "distinto de p1"),
        (lambda mf, pb, p1, h, s: mf.agregar_losa(p1, [(0, 0), (1, 0)], 120.0, h), "al menos 3"),
        (
            lambda mf, pb, p1, h, s: mf.agregar_losa(p1, [(0, 0), (1, 0), (2, 0)], 120.0, h),
            "no encierra área",
        ),
        (
            lambda mf, pb, p1, h, s: mf.agregar_losa(
                p1, [(0, 0), (2, 2), (2, 0), (0, 2)], 120.0, h
            ),
            "se corta",
        ),
        (
            lambda mf, pb, p1, h, s: mf.agregar_losa(
                p1, [(0, 0), (1, 0), (1, 1), (0, 0)], 120.0, h
            ),
            "repetidos",
        ),
        (
            lambda mf, pb, p1, h, s: mf.agregar_losa(p1, [(0, 0), (1, 0), (1, 1)], 0.0, h),
            "mayor que 0",
        ),
        (
            lambda mf, pb, p1, h, s: mf.agregar_losa(
                p1, [(0, 0), (1, 0), (1, 1)], 120.0, h, tipo="nervada"
            ),
            "uno de",
        ),
        (
            lambda mf, pb, p1, h, s: mf.agregar_muro((0, 0), (4, 0), pb, p1, 200.0, 99),
            "no existe el material",
        ),
    ],
)
def test_elementos_invalidos_no_cambian_el_modelo(base, agregar, mensaje):
    mf, *ids = base
    antes = mf.a_json()
    with pytest.raises(FormatoError, match=mensaje):
        agregar(mf, *ids)
    assert mf.a_json() == antes


def test_losas_y_muros_solo_de_hormigon(base):
    mf, pb, p1, _, s = base
    acero = mf.agregar_material("F-24", "acero", fy=240.0, fu=370.0)
    mf.agregar_viga(p1, (0, 0), (5, 0), s, acero)  # una viga de acero sí
    with pytest.raises(FormatoError, match="hormigón"):
        mf.agregar_losa(p1, [(0, 0), (1, 0), (1, 1)], 120.0, acero)
    with pytest.raises(FormatoError, match="hormigón"):
        mf.agregar_muro((0, 0), (4, 0), pb, p1, 200.0, acero)


def test_quitar_respeta_las_referencias(base):
    mf, pb, p1, h, s = base
    c = mf.agregar_columna((0, 0), pb, p1, s, h)
    with pytest.raises(FormatoError, match="lo usa columnas 1"):
        mf.quitar("pisos", p1)
    with pytest.raises(FormatoError, match="lo usa columnas 1"):
        mf.quitar("secciones", s)
    mf.quitar("columnas", c)
    mf.quitar("pisos", p1)
    assert [p["id"] for p in mf.lista("pisos")] == [pb]
    with pytest.raises(KeyError):
        mf.quitar("pisos", p1)


@pytest.mark.parametrize(
    ("cambio", "ruta"),
    [
        (lambda d: d.pop("unidades"), "unidades"),
        (lambda d: d["unidades"].update(longitud="pie"), "unidades.longitud"),
        (lambda d: d.update(otra=1), "otra"),
        (lambda d: d["pisos"][0].update(id=0), "pisos[0].id"),
        (lambda d: d["pisos"][1].update(id=1), "pisos[1].id"),
        (lambda d: d["pisos"][0].update(color="rojo"), "pisos[0].color"),
        (lambda d: d["columnas"][0].update(desde=True), "columnas[0].desde"),
        (lambda d: d["vigas"][0].pop("seccion"), "vigas[0].seccion"),
        (lambda d: d["losas"][0].update(contorno="no"), "losas[0].contorno"),
        (lambda d: d["muros"][0].update(nombre=" "), "muros[0].nombre"),
        (lambda d: d.update(extensiones=[]), "extensiones"),
    ],
)
def test_validar_dice_archivo_y_ruta(edificio, cambio, ruta):
    d = edificio.a_json()
    cambio(d)
    with pytest.raises(FormatoError) as e:
        formato.fisico.validar(d)
    assert "fisico.json" in str(e.value) and ruta in str(e.value)


def test_fisico_invalido_no_se_abre(edificio, tmp_path):
    import json
    import zipfile

    doc = formato.Documento.nuevo()
    doc.fisico = edificio.a_json()
    ruta = tmp_path / "p.nrv"
    formato.guardar(doc, ruta)
    malo = tmp_path / "malo.nrv"
    with zipfile.ZipFile(ruta) as zi, zipfile.ZipFile(malo, "w") as zo:
        for info in zi.infolist():
            datos = zi.read(info)
            if info.filename == "fisico.json":
                d = json.loads(datos)
                d["vigas"][0]["piso"] = 77
                datos = json.dumps(d).encode()
            zo.writestr(info, datos, info.compress_type)
    with pytest.raises(FormatoError, match="no existe el piso 77"):
        formato.abrir(malo)


def test_proyecto_edita_y_deshace_el_modelo_fisico(edificio, tmp_path):
    p = Proyecto()
    assert p.fisico is None
    p.editar_fisico(edificio.a_json())
    assert p.fisico == edificio.a_json() and p.modificado
    otro = copy.deepcopy(p.fisico)
    otro["pisos"][0]["nombre"] = "Subsuelo"
    p.editar_fisico(otro)
    p.deshacer()
    assert p.fisico["pisos"][0]["nombre"] == "Planta baja"
    p.deshacer()
    assert p.fisico is None
    p.rehacer()
    ruta = tmp_path / "p.nrv"
    p.guardar(ruta)
    q = Proyecto()
    q.abrir(ruta)
    assert q.fisico == edificio.a_json()
    # Lo hizo la persona: no queda en el historial.
    assert q.doc.historial is None
    with pytest.raises(FormatoError):
        p.editar_fisico({"unidades": {"longitud": "m"}, "pisos": "x"})


def test_ejemplo_corre(capsys):
    _ejemplo().main()
    assert "Guardado y vuelto a abrir igual: True" in capsys.readouterr().out
