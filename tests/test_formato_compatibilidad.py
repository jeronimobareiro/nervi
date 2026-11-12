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
    ruta = _con_manifiesto(
        tmp_path,
        _modulo("diseno", 1, ["diseno.json", "diseno/"], False),
        [("diseno.json", '{"norma": "ACI 318-19"}'), ("diseno/vigas.json", "[]")],
    )
    doc = formato.abrir(ruta)
    assert len(doc.avisos) == 1 and "'diseno'" in doc.avisos[0]
    formato.guardar(doc, ruta)
    doc2 = formato.abrir(ruta)
    assert doc2.manifiesto["modulos"]["diseno"]["version"] == 1
    assert doc2.otros["diseno.json"] == b'{"norma": "ACI 318-19"}'
    assert doc2.otros["diseno/vigas.json"] == b"[]"
    assert doc2.manifiesto["modulos"]["modelo"] == formato.MODULOS["modelo"].entrada()


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
