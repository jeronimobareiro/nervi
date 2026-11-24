# SPDX-License-Identifier: GPL-3.0-or-later
"""Resultados a precisión completa (``nervi.resultados``): ida y vuelta exacta."""

import json
import warnings

import numpy as np
import pytest

from nervi import resultados
from nervi.proyecto import Proyecto, documento_ejemplo


@pytest.fixture
def proyecto():
    return Proyecto(documento_ejemplo())


def _comparar(guardado: dict, r, modelo: dict, indices) -> None:
    """Cada número guardado es exactamente el del motor (sin tolerancia)."""
    for n, k in indices.nudos.items():
        assert np.array_equal(guardado["desplazamientos"][f"N{n}"], r.desplazamientos[k])
    for a in modelo["apoyos"]:
        k = indices.nudos[a["nudo"]]
        assert np.array_equal(guardado["reacciones"][f"N{a['nudo']}"], r.reacciones[k])
    for b, k in indices.barras.items():
        assert np.array_equal(guardado["fuerzas_extremo"][f"B{b}"], r.fuerzas_extremo[k])
        diagrama = r.diagrama(k)
        assert set(guardado["diagramas"][f"B{b}"]) == set(diagrama)
        for c, v in diagrama.items():
            assert np.array_equal(guardado["diagramas"][f"B{b}"][c], v)


def test_ida_y_vuelta_exacta(proyecto, tmp_path):
    ruta = proyecto.exportar_resultados(tmp_path / "portico.resultados.json")
    datos = resultados.leer(ruta)
    _modelo, res, indices = proyecto._resolver_con_combinaciones()
    assert list(datos["casos"]) == res.casos == ["D", "L", "W"]
    assert list(datos["combinaciones"]) == res.combinaciones
    for c in res.casos:
        _comparar(datos["casos"][c], res[c], proyecto.modelo, indices)
    for c in res.combinaciones:
        assert datos["combinaciones"][c]["factores"] == res.factores(c)
        _comparar(datos["combinaciones"][c], res[c], proyecto.modelo, indices)


def test_no_redondea_como_la_memoria(proyecto):
    from nervi.memoria.documento import formatear

    datos = proyecto.resultados_completos()
    _modelo, res, indices = proyecto._resolver_con_combinaciones()
    ry = datos["combinaciones"]["1.4D"]["reacciones"]["N1"][1]
    assert ry == float(res["1.4D"].reacciones[indices.nudos[1], 1])
    # La memoria muestra el número redondeado; acá queda con todas sus cifras.
    assert formatear(ry) != repr(ry)
    assert json.loads(json.dumps(datos)) == datos


def test_encabezado_y_huella(proyecto):
    datos = proyecto.resultados_completos()
    assert (datos["formato"], datos["version"]) == ("nervi-resultados", 1)
    assert set(datos["contratos"]) == {"plano", "espacial", "dinamica", "diseno"}
    assert datos["unidades"] == proyecto.modelo["unidades"]
    assert datos["huella_modelo"] == resultados.huella(proyecto.modelo)
    modelo = proyecto.copia_modelo()
    modelo["nudos"][1]["y"] = 3.5
    assert resultados.huella(modelo) != datos["huella_modelo"]
    # El orden de las claves no cambia la huella.
    assert resultados.huella(dict(reversed(list(modelo.items())))) == resultados.huella(modelo)


def test_diseno_y_dinamica_solo_si_estan_al_dia(proyecto):
    datos = proyecto.resultados_completos()
    assert "diseno" not in datos and "dinamica" not in datos
    assert proyecto.doc.diseno is None  # exportar no diseña por su cuenta
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        disenados = proyecto.disenar()
    din = proyecto.dinamica
    din["masas"]["casos"] = {"D": 1.0}
    proyecto.editar_dinamica(din)
    analisis = proyecto.analizar_dinamica()
    datos = json.loads(json.dumps(proyecto.resultados_completos()))
    for guardado, r in zip(datos["diseno"], disenados, strict=True):
        assert guardado["barra"] == f"B{r.elemento.barra}"
        assert guardado["armadura"] == r.armadura
        assert guardado["relacion"] == r.relacion
        for g, v in zip(guardado["verificaciones"], r.verificaciones, strict=True):
            assert (g["solicitacion"], g["resistencia"]) == (v.solicitacion, v.resistencia)
            assert g["articulo"] == v.articulo
    modos = datos["dinamica"]["modos"]
    assert [m["periodo"] for m in modos] == analisis.modal.periodos.tolist()
    assert datos["dinamica"]["gravedad"] == analisis.gravedad


def test_leer_rechaza_otros_archivos(tmp_path):
    otro = tmp_path / "otro.json"
    otro.write_text('{"formato": "otro"}', encoding="utf-8")
    with pytest.raises(resultados.ResultadosError):
        resultados.leer(otro)
    nuevo = tmp_path / "nuevo.json"
    nuevo.write_text('{"formato": "nervi-resultados", "version": 99}', encoding="utf-8")
    with pytest.raises(resultados.ResultadosError, match="99"):
        resultados.leer(nuevo)


def test_guardar_rechaza_no_finitos(tmp_path):
    with pytest.raises(ValueError, match=r"casos\.D\[1\]"):
        resultados.guardar({"casos": {"D": [1.0, float("nan")]}}, tmp_path / "r.json")
