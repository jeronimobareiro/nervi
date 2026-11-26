# SPDX-License-Identifier: GPL-3.0-or-later
"""Cambios de varios elementos del modelo físico a la vez (issue #73): editar,
quitar un piso con lo que lo usa, cambiar niveles y copiar plantas."""

import importlib.util
from pathlib import Path

import pytest

from nervi.fisico import ModeloFisico
from nervi.formato.errores import FormatoError

RAIZ = Path(__file__).resolve().parents[1]


@pytest.fixture
def edificio() -> ModeloFisico:
    spec = importlib.util.spec_from_file_location(
        "edificio_fisico", RAIZ / "examples" / "edificio_fisico.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.armar()


def _piso(mf: ModeloFisico, nombre: str) -> int:
    return next(p["id"] for p in mf.lista("pisos") if p["nombre"] == nombre)


def test_editar_cambia_y_valida(edificio):
    viga = edificio.lista("vigas")[0]["id"]
    edificio.editar("vigas", viga, p2=(7.0, 0.0), nombre="VX")
    v = edificio.elemento("vigas", viga)
    assert v["p2"] == [7.0, 0.0] and v["nombre"] == "VX"
    assert edificio.largo_viga(viga) == pytest.approx(7.0)
    edificio.editar("vigas", viga, nombre=None)
    assert "nombre" not in edificio.elemento("vigas", viga)


def test_editar_invalido_no_cambia_nada(edificio):
    antes = edificio.a_json()
    viga = edificio.lista("vigas")[0]["id"]
    with pytest.raises(FormatoError):
        edificio.editar("vigas", viga, seccion=999)
    with pytest.raises(FormatoError):
        edificio.editar("pisos", _piso(edificio, "Piso 1"), nombre="Piso 2")
    with pytest.raises(ValueError):
        edificio.editar("vigas", viga, id=500)
    with pytest.raises(KeyError):
        edificio.editar("vigas", 999, nombre="X")
    assert edificio.a_json() == antes


def test_elementos_en_piso_y_piso_de_abajo(edificio):
    p1, pb = _piso(edificio, "Piso 1"), _piso(edificio, "Planta baja")
    # 6 columnas que llegan desde abajo, 7 vigas y 2 losas.
    assert edificio.elementos_en_piso(p1) == 15
    assert edificio.piso_de_abajo(p1) == pb
    assert edificio.piso_de_abajo(pb) is None


def test_quitar_piso_quita_lo_que_lo_usa(edificio):
    p2 = _piso(edificio, "Piso 2")
    # Vigas y losas del piso 2 y las columnas que nacen o terminan en él. El muro va
    # de Planta baja a Piso 3: pasa por el piso 2 pero no lo usa, y queda.
    n = edificio.quitar_piso(p2)
    assert n == 7 + 2 + 12
    assert p2 not in [p["id"] for p in edificio.lista("pisos")]
    assert len(edificio.lista("columnas")) == 6
    assert len(edificio.lista("muros")) == 1
    with pytest.raises(KeyError):
        edificio.quitar_piso(p2)


def test_cambiar_nivel_con_y_sin_mover_arriba(edificio):
    p1, p2, p3 = (_piso(edificio, f"Piso {k}") for k in (1, 2, 3))
    edificio.cambiar_nivel(p1, 3.5, mover_arriba=True)
    assert [edificio.nivel(p) for p in (p1, p2, p3)] == [3.5, 6.5, 9.5]
    edificio.cambiar_nivel(p1, 4.0)
    assert [edificio.nivel(p) for p in (p1, p2, p3)] == [4.0, 6.5, 9.5]
    antes = edificio.a_json()
    with pytest.raises(FormatoError):
        edificio.cambiar_nivel(p1, 6.5)  # dos pisos al mismo nivel
    assert edificio.a_json() == antes


def test_copiar_piso(edificio):
    p1, p3 = _piso(edificio, "Piso 1"), _piso(edificio, "Piso 3")
    nuevo = edificio.agregar_piso("Piso 4", 12.0)
    n = edificio.copiar_piso(p1, [nuevo, p1], ["columnas", "vigas"])
    assert n == 6 + 7
    en = edificio.en_piso(nuevo)
    assert len(en["columnas"]) == 6 and len(en["vigas"]) == 7 and not en["losas"]
    assert all(c["desde"] == p3 and c["hasta"] == nuevo for c in en["columnas"])
    # Lo que ya había se conserva y los ids son nuevos.
    assert len(edificio.en_piso(p1)["vigas"]) == 7
    ids = [v["id"] for v in edificio.lista("vigas")]
    assert len(ids) == len(set(ids))
    # A la planta más baja no se copian columnas: no tienen de dónde nacer.
    pb = _piso(edificio, "Planta baja")
    assert edificio.copiar_piso(p1, [pb], ["columnas"]) == 0
    with pytest.raises(ValueError):
        edificio.copiar_piso(p1, [nuevo], ["ejes"])


def test_se_guarda_igual_despues_de_editar(edificio):
    edificio.copiar_piso(_piso(edificio, "Piso 1"), [_piso(edificio, "Piso 2")], ["losas"])
    datos = edificio.a_json()
    assert ModeloFisico.desde_json(datos).a_json() == datos
