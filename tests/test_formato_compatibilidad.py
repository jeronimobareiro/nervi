# SPDX-License-Identifier: GPL-3.0-or-later
"""Compatibilidad del formato .nrv para siempre (docs/formato-nrv.md §6).

Los archivos de ``tests/datos/nrv/`` son la garantía de que un proyecto hecho con
una versión vieja de Nervi se sigue abriendo y da los mismos resultados. No se
borran, no se regeneran y no se editan: si una prueba de este archivo falla, el
error está en el cambio nuevo, no en el archivo de referencia.
"""

import json
import zipfile
from pathlib import Path

import numpy as np
import pytest

from nervi import formato

DATOS = Path(__file__).parent / "datos" / "nrv"
REFERENCIAS = sorted(DATOS.glob("*.nrv"))


def _esperado(ruta: Path) -> dict:
    base = ruta.name.removesuffix(".nrv").removesuffix("-sin-modulos")
    return json.loads((DATOS / f"{base}.esperado.json").read_text(encoding="utf-8"))


def test_hay_archivos_de_referencia():
    # Cada módulo que conoce Nervi tiene al menos un archivo de cada versión publicada.
    for nombre, modulo in formato.MODULOS.items():
        for v in range(1, modulo.version + 1):
            assert list(DATOS.glob(f"{nombre}-v{v}*.nrv")), f"falta {nombre}-v{v}.nrv"


@pytest.mark.parametrize("ruta", REFERENCIAS, ids=lambda p: p.name)
def test_archivo_de_referencia_se_abre_y_da_lo_mismo(ruta, tmp_path):
    esperado = _esperado(ruta)
    doc = formato.abrir(ruta)
    assert doc.avisos == []
    m, _ = formato.construir_modelo(doc.modelo)
    res = m.resolver()
    assert res.casos == list(esperado["casos"])
    for nombre, valores in esperado["casos"].items():
        for clave, v in valores.items():
            np.testing.assert_allclose(
                getattr(res[nombre], clave), np.array(v), rtol=1e-9, atol=1e-12, err_msg=clave
            )
    # Guardar con esta versión y volver a abrir conserva el modelo.
    copia = tmp_path / "copia.nrv"
    formato.guardar(doc, copia)
    assert formato.abrir(copia).modelo == doc.modelo


def _con_manifiesto(tmp_path, cambio, extra=()):
    origen = DATOS / "modelo-v1.nrv"
    destino = tmp_path / "p.nrv"
    with zipfile.ZipFile(origen) as zi, zipfile.ZipFile(destino, "w") as zo:
        for info in zi.infolist():
            datos = zi.read(info)
            if info.filename == "nervi.json":
                man = json.loads(datos)
                cambio(man)
                datos = json.dumps(man).encode()
            zo.writestr(info, datos, info.compress_type)
        for nombre, datos in extra:
            zo.writestr(nombre, datos)
    return destino


def _modulo(nombre, version, miembros, requerido):
    def cambio(man):
        man["modulos"][nombre] = {"version": version, "miembros": miembros, "requerido": requerido}

    return cambio


def test_modulo_desconocido_opcional_se_conserva(tmp_path):
    # Hasta la entrada 2026-11-17-07 esta prueba usaba "diseno", que desde entonces
    # es un módulo conocido; "resultados" sigue siendo uno que Nervi no lee.
    ruta = _con_manifiesto(
        tmp_path,
        _modulo("resultados", 1, ["resultados.json", "resultados/"], False),
        [("resultados.json", '{"sha": "x"}'), ("resultados/casos.json", "[]")],
    )
    doc = formato.abrir(ruta)
    assert len(doc.avisos) == 1 and "'resultados'" in doc.avisos[0]
    formato.guardar(doc, ruta)
    doc2 = formato.abrir(ruta)
    assert doc2.manifiesto["modulos"]["resultados"]["version"] == 1
    assert doc2.otros["resultados.json"] == b'{"sha": "x"}'
    assert doc2.otros["resultados/casos.json"] == b"[]"
    assert doc2.manifiesto["modulos"]["modelo"] == formato.MODULOS["modelo"].entrada()


def test_diseno_de_version_futura_se_conserva(tmp_path):
    # Hasta la entrada 2026-11-24-01 esta prueba usaba la versión 2, que desde
    # entonces es la que escribe Nervi; la 3 sigue siendo una versión futura.
    ruta = _con_manifiesto(
        tmp_path,
        _modulo("diseno", 3, ["diseno.json"], False),
        [("diseno.json", '{"norma": "ACI 318-25"}')],
    )
    doc = formato.abrir(ruta)
    assert doc.diseno is None
    assert len(doc.avisos) == 1 and "'diseno' versión 3" in doc.avisos[0]
    formato.guardar(doc, ruta)
    doc2 = formato.abrir(ruta)
    assert doc2.manifiesto["modulos"]["diseno"]["version"] == 3
    assert doc2.otros["diseno.json"] == b'{"norma": "ACI 318-25"}'


def test_referencia_del_modulo_diseno():
    # Los datos de diseño de diseno-v1.nrv se leen igual que cuando se guardaron.
    from nervi.design import proyecto

    esperado = _esperado(DATOS / "diseno-v1.nrv")["diseno"]
    doc = formato.abrir(DATOS / "diseno-v1.nrv")
    d = doc.diseno
    mat = esperado["materiales"]
    assert d["hormigon"]["fc"] == mat["fc"]
    assert d["acero"] == {"fy": mat["fy"], "fyt": mat["fyt"]}
    assert d["criterios"]["d_estribo"] == mat["d_estribo"]
    for el in proyecto.elementos(doc.modelo, d):
        e = esperado[f"B{el.barra}"]
        assert (el.tipo, el.b, el.h) == (e["tipo"], e["b"], e["h"])
    # La versión 1 buscaba la armadura de columnas con todos los diámetros: la
    # migración a la versión 2 lo deja escrito y los resultados no cambian.
    assert doc.migrado_desde == {"diseno": 1}
    assert d["criterios"]["diametros_columna"] == [12, 16, 20, 25, 32]


def test_referencia_del_modulo_diseno_v2():
    # diseno-v2.nrv limita las columnas a Ø16: la armadura sale con esas barras.
    import warnings

    from nervi.design import proyecto

    esperado = _esperado(DATOS / "diseno-v2.nrv")["diseno"]
    doc = formato.abrir(DATOS / "diseno-v2.nrv")
    d = doc.diseno
    assert doc.migrado_desde is None
    assert d["criterios"]["diametros_columna"] == esperado["diametros_columna"]
    m, indices = formato.construir_modelo(doc.modelo)
    combinaciones = {c["nombre"]: c["factores"] for c in doc.modelo["combinaciones"]}
    res = m.resolver(combinaciones=combinaciones)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        resultados = {r.elemento.barra: r for r in proyecto.disenar(doc.modelo, d, res, indices)}
    e = esperado["B1"]
    col = resultados[1]
    sec = col.detalle.seccion
    assert col.estado == e["estado"]
    assert sec.barras.shape[0] == e["barras"]
    assert sec.dimensiones["diametro"] == e["diametro"]


def test_referencia_del_modulo_proyecto():
    esperado = _esperado(DATOS / "proyecto-v1.nrv")["proyecto"]
    doc = formato.abrir(DATOS / "proyecto-v1.nrv")
    assert doc.proyecto == esperado
    assert formato.proyecto.para_caratula(doc.proyecto)["Ubicación"] == "Asunción, Paraguay"


def test_referencia_del_modulo_historial():
    # El historial de historial-v1.nrv se lee igual que cuando se guardó, y su última
    # huella es la del modelo guardado.
    from nervi.resultados import huella

    esperado = _esperado(DATOS / "historial-v1.nrv")["historial"]
    doc = formato.abrir(DATOS / "historial-v1.nrv")
    assert doc.historial == esperado
    assert [c["accion"] for c in doc.historial["cambios"]] == ["aplicar", "aplicar", "deshacer"]
    assert doc.historial["cambios"][-1]["huella_despues"] == huella(doc.modelo)


def test_modulo_desconocido_requerido_no_abre(tmp_path):
    ruta = _con_manifiesto(
        tmp_path, _modulo("portico_3d", 1, ["portico_3d.json"], True), [("portico_3d.json", "{}")]
    )
    with pytest.raises(formato.FormatoError, match=r"'portico_3d'.*Actualizá Nervi"):
        formato.abrir(ruta)


def test_modelo_de_version_futura_no_abre(tmp_path):
    def cambio(man):
        man["modulos"]["modelo"]["version"] = 2

    with pytest.raises(formato.FormatoError, match="'modelo' versión 2"):
        formato.abrir(_con_manifiesto(tmp_path, cambio))


def test_falta_el_modulo_modelo(tmp_path):
    def cambio(man):
        del man["modulos"]["modelo"]

    with pytest.raises(formato.FormatoError, match="'modelo'"):
        formato.abrir(_con_manifiesto(tmp_path, cambio))


@pytest.mark.parametrize(
    ("entrada", "mensaje"),
    [
        ({"version": 0, "miembros": ["x.json"]}, "entero"),
        ({"version": 1, "miembros": []}, "miembros"),
        ({"version": 1, "miembros": ["../x.json"]}, "miembros"),
        ({"version": 1, "miembros": ["x.json"], "requerido": "si"}, "true o false"),
    ],
)
def test_manifiesto_de_modulos_invalido(tmp_path, entrada, mensaje):
    def cambio(man):
        man["modulos"]["otro"] = entrada

    with pytest.raises(formato.FormatoError, match=mensaje):
        formato.abrir(_con_manifiesto(tmp_path, cambio))


def test_migracion_de_un_modulo(tmp_path, monkeypatch):
    # Simula el futuro: el módulo "modelo" pasa a la versión 2 y renombra una clave.
    from nervi.formato import contenedor, migraciones

    def migrar_1_a_2(datos):
        datos["modelo.json"]["extensiones"]["prueba.migrado"] = True
        return datos

    monkeypatch.setitem(migraciones.MIGRACIONES, "modelo", {1: migrar_1_a_2})
    monkeypatch.setitem(
        contenedor.MODULOS, "modelo", contenedor.Modulo("modelo", 2, ("modelo.json",), True)
    )
    doc = formato.abrir(DATOS / "modelo-v1-sin-modulos.nrv")
    assert doc.migrado_desde == {"modelo": 1}
    assert doc.modelo["extensiones"] == {"prueba.migrado": True}
    formato.guardar(doc, tmp_path / "p.nrv")
    assert formato.abrir(tmp_path / "p.nrv").manifiesto["modulos"]["modelo"]["version"] == 2
