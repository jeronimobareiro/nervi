# SPDX-License-Identifier: GPL-3.0-or-later
"""Capa de proyecto sin interfaz gráfica (``nervi.proyecto``).

Comprueba que se usa sin Qt, que avisa los mismos eventos que antes emitía la
sesión de la interfaz y que da exactamente los mismos resultados que llamar al
motor y al diseño directamente, y que la interfaz (``Sesion``) da lo mismo que
el proyecto sin interfaz.
"""

import subprocess
import sys
import warnings

import numpy as np
import pytest

from nervi import MecanismoError, formato
from nervi.design import proyecto as diseno_proyecto
from nervi.proyecto import Proyecto, Seleccion, documento_ejemplo


def _con_diseno() -> Proyecto:
    p = Proyecto(documento_ejemplo())
    p.calcular()
    return p


def test_no_carga_qt():
    codigo = (
        "import sys, nervi.proyecto as p; p.Proyecto(p.documento_ejemplo()).calcular(); "
        "print(any(m.startswith('PySide6') for m in sys.modules))"
    )
    salida = subprocess.run(
        [sys.executable, "-c", codigo], capture_output=True, text=True, check=True
    )
    assert salida.stdout.strip() == "False"


def test_calcular_da_lo_mismo_que_el_motor():
    p = Proyecto(documento_ejemplo())
    p.calcular()
    modelo, _ = formato.construir_modelo(p.modelo)
    directo = modelo.resolver()
    for caso in directo.casos:
        a, b = p.resultados[caso], directo[caso]
        assert np.array_equal(a.desplazamientos, b.desplazamientos)
        assert np.array_equal(a.reacciones, b.reacciones)
        assert np.array_equal(a.fuerzas_extremo, b.fuerzas_extremo)
    assert p.al_dia and p.combinacion == "1.4D"
    assert p.resultado() is not None


def test_eventos_en_el_mismo_orden_que_las_senales():
    p = Proyecto(documento_ejemplo())
    eventos = []
    cancelar = p.suscribir(eventos.append)
    p.editar(p.copia_modelo())
    assert eventos == ["archivo", "modelo", "resultados", "diseno", "dinamica"]
    eventos.clear()
    p.nuevo()
    assert eventos == list(Proyecto.EVENTOS)
    cancelar()
    eventos.clear()
    p.nuevo(documento_ejemplo())
    assert eventos == []


def test_mecanismo_selecciona_el_nudo():
    p = Proyecto(documento_ejemplo())
    modelo = p.copia_modelo()
    modelo["apoyos"] = []
    p.editar(modelo)
    with pytest.raises(MecanismoError):
        p.calcular()
    assert p.inestabilidad is not None
    assert p.seleccion == Seleccion("nudo", p.inestabilidad.nudo)
    assert p.avisos[0].nivel == "error"


def test_disenar_da_lo_mismo_que_el_diseno_directo():
    p = _con_diseno()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        desde_proyecto = p.disenar()
        modelo, indices = formato.construir_modelo(p.modelo)
        comb = {c["nombre"]: c["factores"] for c in p.modelo["combinaciones"]}
        res = modelo.resolver(combinaciones=comb)
        directo = diseno_proyecto.disenar(p.modelo, p.diseno, res, indices)
    assert [r.elemento.barra for r in desde_proyecto] == [r.elemento.barra for r in directo]
    for a, b in zip(desde_proyecto, directo, strict=True):
        assert a.armadura == b.armadura
        assert a.relacion == b.relacion
        assert [(v.solicitacion, v.resistencia) for v in a.verificaciones] == [
            (v.solicitacion, v.resistencia) for v in b.verificaciones
        ]
    assert p.doc.diseno is not None and p.modificado


def test_guardar_abrir_y_memoria(tmp_path):
    p = _con_diseno()
    p.guardar(tmp_path / "portico")
    assert p.ruta == tmp_path / "portico.nrv" and not p.modificado
    q = Proyecto()
    q.abrir(p.ruta)
    assert q.modelo == p.modelo
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        memoria = q.memoria()
    assert memoria.datos["Proyecto"] == "portico"
    assert memoria.capitulos


def test_sesion_de_la_interfaz_da_lo_mismo(tmp_path):
    pytest.importorskip("PySide6.QtCore", exc_type=ImportError)
    from nervi.gui.sesion import Sesion

    p, s = Proyecto(documento_ejemplo()), Sesion(documento_ejemplo())
    assert isinstance(s, Proyecto)
    senales = []
    s.resultados_cambiados.connect(lambda: senales.append("resultados"))
    eventos = []
    s.suscribir(eventos.append)
    for x in (p, s):
        x.calcular()
    assert senales == eventos == ["resultados"]
    for caso in p.resultados.casos:
        assert np.array_equal(
            p.resultados[caso].fuerzas_extremo, s.resultados[caso].fuerzas_extremo
        )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        a, b = p.disenar(), s.disenar()
    assert [(r.armadura, r.relacion) for r in a] == [(r.armadura, r.relacion) for r in b]
