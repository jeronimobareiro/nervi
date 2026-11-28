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
from nervi.proyecto import PERSONA, Proyecto, Seleccion, documento_ejemplo, resumir_cambios


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
    assert eventos == ["archivo", "modelo", "resultados", "diseno", "dinamica", "historial"]
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


# --- Deshacer, rehacer y propuestas -------------------------------------------------


def _mover_n2(p: Proyecto, y: float) -> dict:
    modelo = p.copia_modelo()
    modelo["nudos"][1]["y"] = y
    return modelo


def test_deshacer_y_rehacer_el_modelo():
    p = Proyecto(documento_ejemplo())
    original = p.copia_modelo()
    assert not p.puede_deshacer and p.deshacer() is None
    p.editar(_mover_n2(p, 3.5), descripcion="Mover N2")
    p.editar(_mover_n2(p, 4.0))
    assert p.que_deshacer == "Editar el modelo"
    p.deshacer()
    assert p.modelo["nudos"][1]["y"] == 3.5 and p.que_rehacer == "Editar el modelo"
    eventos = []
    p.suscribir(eventos.append)
    assert p.deshacer().descripcion == "Mover N2"
    assert p.modelo == original
    assert eventos == ["archivo", "modelo", "resultados", "diseno", "dinamica", "historial"]
    assert not p.puede_deshacer and p.puede_rehacer
    p.rehacer()
    assert p.modelo["nudos"][1]["y"] == 3.5
    # Un cambio nuevo borra lo que se podía rehacer.
    p.editar(_mover_n2(p, 5.0))
    assert not p.puede_rehacer
    # Las ediciones a mano no van al historial del archivo.
    assert p.doc.historial is None


def test_deshacer_diseno_y_dinamica_vuelve_a_sin_datos():
    p = Proyecto(documento_ejemplo())
    assert p.doc.diseno is None and p.doc.dinamica is None
    d = p.diseno
    d["hormigon"]["fc"] = 30.0
    p.editar_diseno(d)
    din = p.dinamica
    din["masas"]["casos"] = {"D": 1.0}
    p.editar_dinamica(din)
    p.deshacer()
    assert p.doc.dinamica is None and p.doc.diseno["hormigon"]["fc"] == 30.0
    p.deshacer()
    assert p.doc.diseno is None
    p.rehacer()
    assert p.doc.diseno["hormigon"]["fc"] == 30.0


def test_lo_guardado_para_deshacer_no_cambia_si_se_toca_el_modelo():
    p = Proyecto(documento_ejemplo())
    original = p.copia_modelo()
    nuevo = _mover_n2(p, 3.5)
    p.editar(nuevo)
    nuevo["nudos"][1]["y"] = 99.0  # quien editó sigue teniendo el diccionario
    p.deshacer()
    assert p.modelo == original
    p.rehacer()
    assert p.modelo["nudos"][1]["y"] == 3.5


def test_abrir_otro_proyecto_borra_deshacer_y_propuestas():
    p = Proyecto(documento_ejemplo())
    p.editar(_mover_n2(p, 3.5))
    p.proponer(_mover_n2(p, 4.0), "ia: prueba")
    p.nuevo(documento_ejemplo())
    assert not p.puede_deshacer and p.propuestas == []


def test_propuesta_no_cambia_nada_hasta_aplicarla():
    p = Proyecto(documento_ejemplo())
    original = p.copia_modelo()
    eventos = []
    p.suscribir(eventos.append)
    prop = p.proponer(_mover_n2(p, 3.5), "ia: Claude", "Subir N2")
    assert eventos == ["historial"]
    assert p.modelo == original and not p.modificado
    assert prop.resumen == ["Cambia N2 (y)"]
    assert [x.id for x in p.propuestas] == [prop.id]
    p.aplicar(prop.id)
    assert p.modelo["nudos"][1]["y"] == 3.5 and p.propuestas == []
    assert p.que_deshacer == "Subir N2"
    (cambio,) = p.doc.historial["cambios"]
    assert (cambio["accion"], cambio["origen"], cambio["resumen"]) == (
        "aplicar",
        "ia: Claude",
        ["Cambia N2 (y)"],
    )
    p.deshacer()
    assert p.modelo == original
    assert [c["accion"] for c in p.doc.historial["cambios"]] == ["aplicar", "deshacer"]


def test_propuesta_sobre_un_modelo_que_cambio_no_se_aplica():
    p = Proyecto(documento_ejemplo())
    prop = p.proponer(_mover_n2(p, 3.5), "ia: Claude")
    p.editar(_mover_n2(p, 4.0))
    with pytest.raises(ValueError, match="cambió"):
        p.aplicar(prop.id)
    assert p.modelo["nudos"][1]["y"] == 4.0
    p.descartar(prop.id)
    assert p.propuestas == []
    with pytest.raises(KeyError):
        p.aplicar(prop.id)


def test_propuesta_invalida_o_sin_origen():
    p = Proyecto(documento_ejemplo())
    malo = p.copia_modelo()
    malo["barras"][0]["i"] = 99
    with pytest.raises(formato.FormatoError):
        p.proponer(malo, "ia: Claude")
    for origen in ("", "  ", PERSONA):
        with pytest.raises(ValueError):
            p.proponer(p.copia_modelo(), origen)
    assert p.propuestas == []


def test_historial_se_guarda_y_se_abre(tmp_path):
    p = Proyecto(documento_ejemplo())
    p.aplicar(p.proponer(_mover_n2(p, 3.5), "importador: DXF", "Planta").id)
    p.guardar(tmp_path / "p.nrv")
    q = Proyecto()
    q.abrir(tmp_path / "p.nrv")
    assert q.doc.historial == p.doc.historial
    assert "historial" in q.doc.manifiesto["modulos"]


def test_resumir_cambios():
    p = Proyecto(documento_ejemplo())
    antes = p.copia_modelo()
    despues = p.copia_modelo()
    despues["nudos"].append({"id": 5, "x": 9.0, "y": 0.0})
    despues["barras"] = [b for b in despues["barras"] if b["id"] != 3]
    despues["casos"][0]["nombre"] = "PP"
    despues["cargas_barra"].append(dict(despues["cargas_barra"][0]))
    despues["unidades"] = {"fuerza": "N", "longitud": "m"}
    assert resumir_cambios(antes, despues) == [
        "Cambia las unidades",
        "Agrega N5",
        "Cambia caso PP (nombre)",
        "Cargas en barras: 2 → 3",
        "Quita B3",
    ]
    assert resumir_cambios(antes, antes) == []


def _edificio():
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "examples"))
    from edificio_fisico import armar

    return armar()


def test_con_edificio_manda_el_edificio():
    """Con modelo físico, calcular resuelve el modelo de cálculo generado (#74): casos
    D y L y las combinaciones de ACI 318-19 §5.3.1; cambiar el edificio lo invalida."""
    from nervi.idealizacion import COMBINACIONES

    p = Proyecto()
    assert not p.es_edificio
    mf = _edificio()
    p.editar_fisico(mf.a_json())
    assert p.es_edificio
    assert p.nombres_resultado() == ["1.4D", "1.2D+1.6L", "D", "L"]
    assert p.avisos[0].nivel == "ok" and "barras" in p.avisos[0].texto
    assert any("sobre el muro" in a.texto for a in p.avisos)
    eventos = []
    p.suscribir(eventos.append)
    p.calcular()
    assert p.edificio_al_dia and "resultados" in eventos
    assert p.combinacion == "1.4D"
    directo = mf.modelo_calculo().modelo.resolver()
    np.testing.assert_allclose(
        p.resultado_edificio().desplazamientos,
        directo.combinar("1.4D", COMBINACIONES["1.4D"]).desplazamientos,
        rtol=1e-12,
        atol=1e-15,
    )
    p.elegir_combinacion("L")
    np.testing.assert_array_equal(p.resultado_edificio().reacciones, directo["L"].reacciones)
    mc = p.modelo_calculo()
    assert p.modelo_calculo() is mc  # guardado hasta que cambie el edificio
    p.editar_fisico(mf.a_json())
    assert not p.edificio_al_dia and p.resultado_edificio() is None
    assert p.modelo_calculo() is not mc
    # Deshacer hasta sin edificio vuelve al pórtico plano.
    p.deshacer()
    p.deshacer()
    assert not p.es_edificio
