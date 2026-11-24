# SPDX-License-Identifier: GPL-3.0-or-later
"""Consultas para agentes de IA (``nervi.ia``) y servidor MCP ``nervi-mcp``.

Las herramientas tienen que devolver exactamente los números del motor, no cambiar
nunca el archivo y explicar por qué no pueden responder cuando no pueden."""

import asyncio
import json
import os
import subprocess
import sys
import warnings

import numpy as np
import pytest

from nervi import resultados
from nervi.design import proyecto as diseno_proyecto
from nervi.ia.herramientas import (
    NOMBRES,
    ErrorConsulta,
    FuenteArchivo,
    FuenteProyecto,
    Herramientas,
)
from nervi.proyecto import Proyecto, documento_ejemplo


@pytest.fixture
def proyecto():
    return Proyecto(documento_ejemplo())


@pytest.fixture
def h(proyecto):
    return Herramientas(FuenteProyecto(proyecto))


@pytest.fixture
def archivo(tmp_path):
    p = Proyecto(documento_ejemplo())
    ruta = tmp_path / "portico.nrv"
    p.guardar(ruta)
    return ruta


def test_publica_todas_las_herramientas(h):
    for nombre in NOMBRES:
        funcion = getattr(h, nombre)
        assert callable(funcion) and funcion.__doc__.strip()


def test_resumen(h, proyecto):
    r = h.resumen_proyecto()
    assert r["unidades"] == proyecto.modelo["unidades"]
    assert r["casos"] == ["D", "L", "W"]
    assert r["apoyos"][0]["nudo"] == "N1"
    assert r["tiene_datos_de_diseno"] is False
    assert r["huella_modelo"].startswith("sha256:")
    json.dumps(r)


def test_leer_nudo_da_los_numeros_del_motor(h, proyecto):
    _m, res, indices = proyecto._resolver_con_combinaciones()
    k = indices.nudos[2]
    for forma in (2, "2", "N2", " n2 "):
        r = h.leer_nudo(forma, "1.4D")
        d = r["resultados"]["1.4D"]["desplazamientos"]
        assert [d["ux"], d["uy"], d["rz"]] == res["1.4D"].desplazamientos[k].tolist()
        assert "reacciones" not in r["resultados"]["1.4D"]  # N2 no tiene apoyo
    todos = h.leer_nudo("N1")
    assert set(todos["resultados"]) == {*res.casos, *res.combinaciones}
    rx = todos["resultados"]["D"]["reacciones"]["Rx"]
    assert rx == float(res["D"].reacciones[indices.nudos[1], 0])


def test_leer_barra_extremos_y_diagrama(h, proyecto):
    _m, res, indices = proyecto._resolver_con_combinaciones()
    k = indices.barras[2]
    r = h.leer_barra("B2", "1.2D+1.6L")
    diagrama = res["1.2D+1.6L"].diagrama(k)
    for c, v in diagrama.items():
        assert np.array_equal(r["diagrama"][c], v)
    assert r["extremos"]["M"]["max"] == float(diagrama["M"].max())
    assert r["extremos"]["M"]["x_max"] == float(diagrama["x"][diagrama["M"].argmax()])
    assert list(r["fuerzas_extremo"].values()) == res["1.2D+1.6L"].fuerzas_extremo[k].tolist()


def test_envolvente_y_reacciones(h, proyecto):
    _m, res, indices = proyecto._resolver_con_combinaciones()
    env = h.envolvente_barra(2)["envolvente"]
    maximos = [res[c].diagrama(indices.barras[2])["M"].max() for c in res.combinaciones]
    assert env["M"]["max"] == float(max(maximos))
    assert env["M"]["combinacion_max"] in res.combinaciones
    reac = h.leer_reacciones()["apoyos"]["N1"]["Ry"]
    ry = [res[c].reacciones[indices.nudos[1], 1] for c in res.combinaciones]
    assert (reac["max"], reac["min"]) == (float(max(ry)), float(min(ry)))
    una = h.leer_reacciones("W")["apoyos"]["N4"]
    assert una["Mz"] == float(res["W"].reacciones[indices.nudos[4], 2])


@pytest.mark.parametrize(
    "llamada, texto",
    [
        (lambda h: h.leer_nudo("N99"), "No existe el nudo N99"),
        (lambda h: h.leer_nudo("B2"), "no es un id de nudo"),
        (lambda h: h.leer_nudo(True), "no es un id de nudo"),
        (lambda h: h.leer_barra(1, "2D"), "No hay un caso ni una combinación '2D'"),
        (lambda h: h.leer_verificaciones(), "no tiene datos de diseño"),
        (lambda h: h.leer_modos(), "no tiene datos de dinámica"),
    ],
)
def test_errores_que_entiende_el_agente(h, llamada, texto):
    with pytest.raises(ErrorConsulta, match=texto):
        llamada(h)


def test_mecanismo_se_explica(proyecto):
    m = proyecto.copia_modelo()
    m["apoyos"] = [{"nudo": 1, "ux": True, "uy": True, "rz": False}]
    proyecto.editar(m)
    with pytest.raises(ErrorConsulta, match="no se puede calcular"):
        Herramientas(FuenteProyecto(proyecto)).listar_resultados()


def test_verificaciones_y_modos_iguales_al_proyecto(proyecto):
    proyecto.editar_diseno(proyecto.diseno)
    din = proyecto.dinamica
    din["masas"]["casos"] = {"D": 1.0}
    proyecto.editar_dinamica(din)
    h = Herramientas(FuenteProyecto(proyecto))
    r = h.leer_verificaciones("B2")
    assert r["aviso"] == diseno_proyecto.AVISO_EXPERIMENTAL
    assert [e["barra"] for e in r["elementos"]] == ["B2"]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        directo = proyecto.disenar()
    b2 = next(x for x in directo if x.elemento.barra == 2)
    assert r["elementos"][0]["relacion"] == b2.relacion
    modos = h.leer_modos()["modos"]
    analisis = proyecto.analizar_dinamica()
    assert [m["periodo_s"] for m in modos] == analisis.modal.periodos.tolist()


def test_archivo_no_cambia_y_se_relee(archivo):
    antes = archivo.read_bytes()
    h = Herramientas(FuenteArchivo(archivo))
    for nombre in ("resumen_proyecto", "leer_modelo", "revisar_modelo", "listar_resultados"):
        json.dumps(getattr(h, nombre)())
    h.leer_barra("B1", "D")
    huella = h.resumen_proyecto()["huella_modelo"]
    h.leer_reacciones()
    assert archivo.read_bytes() == antes
    # La persona cambia el proyecto y lo guarda: la siguiente consulta ve lo nuevo.
    p = Proyecto()
    p.abrir(archivo)
    m = p.copia_modelo()
    m["nudos"][1]["y"] += 0.5
    p.editar(m)
    p.guardar()
    os.utime(archivo, ns=(1, 1))  # por si el sistema de archivos tiene poca resolución
    assert h.leer_modelo()["nudos"][1]["y"] == m["nudos"][1]["y"]
    assert h.resumen_proyecto()["huella_modelo"] == resultados.huella(m) != huella


def test_archivo_que_no_existe(tmp_path):
    with pytest.raises(ErrorConsulta, match="No se puede leer"):
        Herramientas(FuenteArchivo(tmp_path / "no.nrv")).resumen_proyecto()


# --- Servidor MCP ------------------------------------------------------------------------


def test_servidor_lista_y_llama(proyecto):
    pytest.importorskip("mcp")
    from nervi.ia.servidor import crear_servidor

    s = crear_servidor(FuenteProyecto(proyecto))

    async def probar():
        herramientas = await s.list_tools()
        assert [t.name for t in herramientas] == list(NOMBRES)
        for t in herramientas:
            assert t.annotations.model_dump(by_alias=True)["readOnlyHint"] is True
        salida = await s.call_tool("leer_nudo", {"nudo": "N2", "resultado": "D"})
        contenido = salida if isinstance(salida, list | tuple) else salida.content
        if isinstance(contenido, tuple):  # SDK 1.x: (contenido, estructurado)
            contenido = contenido[0]
        datos = json.loads(contenido[0].text)
        assert datos == Herramientas(FuenteProyecto(proyecto)).leer_nudo("N2", "D")
        with pytest.raises(Exception, match="No existe el nudo N9"):
            await s.call_tool("leer_nudo", {"nudo": "N9"})

    asyncio.run(probar())


def _rpc(proceso, id_, metodo, params=None):
    mensaje = {"jsonrpc": "2.0", "id": id_, "method": metodo, "params": params or {}}
    proceso.stdin.write(json.dumps(mensaje) + "\n")
    proceso.stdin.flush()
    while True:
        linea = proceso.stdout.readline()
        assert linea, proceso.stderr.read()
        respuesta = json.loads(linea)
        if respuesta.get("id") == id_:
            return respuesta


def test_sesion_stdio_de_punta_a_punta(archivo):
    """Lo que hace un cliente MCP real: lanzar ``nervi-mcp`` y hablarle por stdio."""
    pytest.importorskip("mcp")
    antes = archivo.read_bytes()
    proceso = subprocess.Popen(
        [sys.executable, "-m", "nervi.ia.servidor", str(archivo)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    try:
        inicio = _rpc(
            proceso,
            1,
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "prueba", "version": "0"},
            },
        )
        assert inicio["result"]["serverInfo"]["name"] == "nervi"
        assert "Nunca inventes" in inicio["result"]["instructions"]
        proceso.stdin.write(
            json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n"
        )
        proceso.stdin.flush()
        lista = _rpc(proceso, 2, "tools/list")["result"]["tools"]
        assert [t["name"] for t in lista] == list(NOMBRES)
        r = _rpc(proceso, 3, "tools/call", {"name": "leer_reacciones", "arguments": {}})
        datos = json.loads(r["result"]["content"][0]["text"])
        assert datos == Herramientas(FuenteArchivo(archivo)).leer_reacciones()
        error = _rpc(
            proceso,
            4,
            "tools/call",
            {"name": "leer_barra", "arguments": {"barra": 7, "resultado": "D"}},
        )
        assert error["result"]["isError"] is True
        assert "No existe la barra B7" in error["result"]["content"][0]["text"]
        recurso = _rpc(proceso, 5, "resources/read", {"uri": "nervi://modelo"})
        assert json.loads(recurso["result"]["contents"][0]["text"])["barras"]
    finally:
        proceso.stdin.close()
        proceso.wait(timeout=10)
        proceso.stdout.close()
        proceso.stderr.close()
    assert archivo.read_bytes() == antes


def test_main_con_archivo_que_no_existe(tmp_path, capsys):
    pytest.importorskip("mcp")
    from nervi.ia.servidor import main

    assert main([str(tmp_path / "no.nrv")]) == 2
    assert "No se puede leer" in capsys.readouterr().err
