# SPDX-License-Identifier: GPL-3.0-or-later
"""Diseño de todas las barras de un proyecto (nervi.design.proyecto) y módulo
``diseno`` del formato .nrv."""

import math
import warnings

import pytest

import nervi
from nervi import formato
from nervi.design import aci318, proyecto
from nervi.memoria import memoria_de_calculo


def _portico(fuerza="kN", longitud="m", escala_f=1.0, escala_l=1.0):
    """Pórtico de una crujía (el de ejemplo de la interfaz) en las unidades pedidas."""
    E = 2.5e7 * escala_f / escala_l**2
    col = dict(E=E, A=0.09 * escala_l**2, I=0.30**4 / 12 * escala_l**4)
    viga = dict(E=E, A=0.125 * escala_l**2, I=0.25 * 0.5**3 / 12 * escala_l**4)
    m = nervi.Modelo()
    a, b = m.agregar_nudo(0.0, 0.0), m.agregar_nudo(0.0, 3.0 * escala_l)
    c, d = m.agregar_nudo(6.0 * escala_l, 3.0 * escala_l), m.agregar_nudo(6.0 * escala_l, 0.0)
    m.agregar_barra(a, b, **col)
    v = m.agregar_barra(b, c, **viga)
    m.agregar_barra(d, c, **col)
    m.apoyar(a)
    m.apoyar(d)
    m.carga_uniforme("D", v, qy=-20.0 * escala_f / escala_l)
    m.carga_uniforme("L", v, qy=-10.0 * escala_f / escala_l)
    combs = {"1.4D": {"D": 1.4}, "1.2D+1.6L": {"D": 1.2, "L": 1.6}}
    doc = formato.Documento.desde_modelo(m, combs)
    doc.modelo["unidades"] = {"fuerza": fuerza, "longitud": longitud}
    return doc, combs


def _disenar(doc, combs, diseno=None):
    m, idx = formato.construir_modelo(doc.modelo)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return proyecto.disenar(doc.modelo, diseno, m.resolver(combinaciones=combs), idx)


def test_seccion_equivalente_y_tipo_automatico():
    # Rectángulo 250 x 500 mm: A = 0.125 m², I = b·h³/12.
    assert proyecto.seccion_equivalente(0.125, 0.25 * 0.5**3 / 12, "m") == (250.0, 500.0)
    assert proyecto.seccion_equivalente(1250.0, 25 * 50**3 / 12, "cm") == (250.0, 500.0)
    assert proyecto.tipo_automatico(6.0, 0.0) == "viga"
    assert proyecto.tipo_automatico(0.5, 3.0) == "columna"
    assert proyecto.tipo_automatico(-1.0, 1.0) == "viga"  # a 45° se toma como viga


def test_elementos_automaticos_y_ancho_de_apoyo():
    doc, _ = _portico()
    els = proyecto.elementos(doc.modelo, formato.diseno.nuevo())
    assert [e.tipo for e in els] == ["columna", "viga", "columna"]
    assert (els[0].b, els[0].h) == (300.0, 300.0)
    # La cara del apoyo de la viga está a la mitad del canto de las columnas.
    assert (els[1].apoyo_i, els[1].apoyo_j) == (300.0, 300.0)
    assert not els[1].tipo_manual and not els[1].seccion_manual


def test_elementos_con_datos_del_usuario():
    doc, _ = _portico()
    d = formato.diseno.nuevo()
    d["elementos"] = [
        {"barra": 1, "tipo": "ninguno"},
        {"barra": 2, "h": 600.0},
        {"barra": 3, "h": 400.0},
        {"barra": 99, "tipo": "viga"},  # ya no existe: se ignora
    ]
    els = proyecto.elementos(doc.modelo, d)
    assert [e.tipo for e in els] == ["ninguno", "viga", "columna"]
    assert (els[1].b, els[1].h) == (250.0, 600.0) and els[1].seccion_manual
    assert els[0].tipo_manual
    # Solo la columna B3 llega al nudo j de la viga; B1 ya no es columna.
    assert (els[1].apoyo_i, els[1].apoyo_j) == (0.0, 400.0)


def test_disenar_portico_coincide_con_disenar_viga():
    doc, combs = _portico()
    res = _disenar(doc, combs)
    assert [r.estado for r in res] == ["pendiente", "cumple", "pendiente"]
    assert "#24" in res[0].mensajes[0]
    viga = res[1]
    # Lo mismo que llamar directamente al módulo de la norma con esos datos.
    m, idx = formato.construir_modelo(doc.modelo)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        directo = aci318.disenar_viga(
            m.resolver(combinaciones=combs),
            idx.barras[2],
            aci318.SeccionRectangular(250, 500, 40, 10, 19),
            aci318.Materiales(fc=25, fy=420, fyt=420),
            ancho_apoyo_i=300,
            ancho_apoyo_j=300,
        )
    assert viga.detalle == directo
    assert viga.armadura == {
        "Inferior": directo.inferior.descripcion,
        "Superior": directo.superior.descripcion,
        "Estribos": directo.estribos.descripcion,
    }
    ver = {v.nombre: v for v in viga.verificaciones}
    assert ver["Flexión M+"].solicitacion == pytest.approx(directo.Mu_pos)
    assert ver["Flexión M+"].resistencia == pytest.approx(directo.inferior.resistencia.phiMn)
    assert ver["Cortante"].resistencia == pytest.approx(directo.estribos.phiVn)
    assert ver["Separación de estribos"].solicitacion == directo.estribos.s
    assert all(v.articulo.startswith("ACI 318-19 §") for v in viga.verificaciones)
    assert all(v.cumple for v in viga.verificaciones)
    assert viga.relacion == max(v.relacion for v in viga.verificaciones)


def test_armadura_minima_con_la_excepcion_de_4_3():
    # La exigida es max(As_req, min(As,min, 4/3·As_req)) (§9.6.1.2 y §9.6.1.3).
    doc, combs = _portico()
    viga = _disenar(doc, combs)[1]
    det, mat = viga.detalle, aci318.Materiales(fc=25)
    for nombre, disp in (("inferior", det.inferior), ("superior", det.superior)):
        v = next(x for x in viga.verificaciones if x.nombre == f"Armadura mínima {nombre}")
        # Con f'c = 25 MPa gobierna 1.4/fy (0.25·√25 = 1.25 < 1.4).
        as_min = max(0.25 * math.sqrt(25), 1.4) / 420 * 250 * disp.d
        assert as_min == pytest.approx(aci318.armadura_minima(250, disp.d, mat))
        assert v.solicitacion == pytest.approx(max(disp.As_req, min(as_min, 4 / 3 * disp.As_req)))
        assert v.resistencia == disp.As


def test_unidades_del_modelo_se_convierten():
    # El mismo pórtico en tf y cm da la misma armadura que en kN y m.
    base = _disenar(*_portico())[1]
    f, l = 1 / 9.80665, 100.0  # kN -> tf, m -> cm
    doc, combs = _portico("tf", "cm", f, l)
    otra = _disenar(doc, combs)[1]
    assert (otra.elemento.b, otra.elemento.h) == (250.0, 500.0)
    assert otra.armadura == base.armadura
    for a, b in zip(otra.verificaciones, base.verificaciones, strict=True):
        assert a.solicitacion == pytest.approx(b.solicitacion, rel=1e-9)


def test_seccion_chica_no_cumple_con_motivo():
    doc, combs = _portico()
    d = formato.diseno.nuevo()
    d["elementos"] = [{"barra": 2, "b": 150.0, "h": 250.0}]
    r = _disenar(doc, combs, d)[1]
    assert r.estado == "no cumple"
    assert r.armadura == {} and "agrand" in r.mensajes[0]


def test_seccion_imposible_da_error():
    doc, combs = _portico()
    d = formato.diseno.nuevo()
    d["elementos"] = [{"barra": 2, "b": 80.0}]
    r = _disenar(doc, combs, d)[1]
    assert r.estado == "error" and "80 × 500" in r.mensajes[0]


def test_registro_de_disenadores_para_columnas(monkeypatch):
    def columna(el, ctx):
        assert ctx.fuerza == "kN" and ctx.combinaciones == ["1.4D", "1.2D+1.6L"]
        v = proyecto.Verificacion("Flexocompresión", 1.0, 2.0, "kN·m", "ACI 318-19 §22.4")
        return proyecto.ResultadoElemento(el, "cumple", {"Longitudinal": "4Ø16"}, [v])

    monkeypatch.setitem(proyecto.DISENADORES, "columna", columna)
    res = _disenar(*_portico())
    assert [r.estado for r in res] == ["cumple", "cumple", "cumple"]
    assert res[0].armadura == {"Longitudinal": "4Ø16"} and res[0].relacion == 0.5


def test_sin_combinaciones_no_se_disena():
    doc, _ = _portico()
    m, idx = formato.construir_modelo(doc.modelo)
    with pytest.raises(ValueError, match="combinaciones"):
        proyecto.disenar(doc.modelo, None, m.resolver(), idx)


def test_capitulo_de_la_memoria():
    doc, combs = _portico()
    res = _disenar(doc, combs)
    m, _ = formato.construir_modelo(doc.modelo)
    mem = memoria_de_calculo(m, m.resolver(combinaciones=combs))
    cap = mem.agregar(proyecto.capitulo_memoria(res, formato.diseno.nuevo()))
    assert cap.titulo == "Diseño de hormigón armado (ACI 318-19)"
    assert cap.bloques[0].estilo == "aviso"
    tablas = [b for b in cap.bloques if isinstance(b, nervi.memoria.Tabla)]
    assert [t.titulo for t in tablas] == ["Armaduras", "Verificaciones"]
    assert [f[0] for f in tablas[0].filas] == ["B1", "B2", "B3"]
    assert tablas[0].filas[1][3] == res[1].armadura["Inferior"]
    assert len(tablas[1].filas) == len(res[1].verificaciones)
    assert all(f[5] == "Cumple" for f in tablas[1].filas)
    assert any("#24" in getattr(b, "texto", "") for b in cap.bloques)


# --- Módulo "diseno" del formato .nrv ------------------------------------------------


def test_diseno_se_guarda_y_se_abre(tmp_path):
    doc, _ = _portico()
    assert doc.diseno is None
    formato.guardar(doc, tmp_path / "sin.nrv")
    assert "diseno" not in formato.abrir(tmp_path / "sin.nrv").manifiesto["modulos"]

    doc.diseno = formato.diseno.nuevo()
    doc.diseno["elementos"] = [{"barra": 2, "b": 300.0, "h": 600.0}]
    formato.guardar(doc, tmp_path / "con.nrv")
    otro = formato.abrir(tmp_path / "con.nrv")
    assert otro.avisos == []
    assert otro.manifiesto["modulos"]["diseno"] == formato.MODULOS["diseno"].entrada()
    assert otro.diseno == doc.diseno
    assert len(otro.diseno["modelo_sha256"]) == 64


def test_diseno_avisa_si_otro_programa_cambio_el_modelo(tmp_path):
    import zipfile

    doc, _ = _portico()
    doc.diseno = formato.diseno.nuevo()
    ruta = tmp_path / "p.nrv"
    formato.guardar(doc, ruta)
    # Simula un programa que no conoce "diseno": cambia el modelo y conserva diseno.json.
    copia = tmp_path / "q.nrv"
    with zipfile.ZipFile(ruta) as zi, zipfile.ZipFile(copia, "w") as zo:
        for info in zi.infolist():
            datos = zi.read(info)
            if info.filename == "modelo.json":
                datos = datos.replace(b'"y": 3.0', b'"y": 3.5')
            zo.writestr(info, datos, info.compress_type)
    otro = formato.abrir(copia)
    assert len(otro.avisos) == 1 and "cambió" in otro.avisos[0]
    assert otro.diseno is not None


@pytest.mark.parametrize(
    ("cambio", "ruta"),
    [
        (lambda d: d.update(norma="CIRSOC 201"), "norma"),
        (lambda d: d["hormigon"].update(fc=-1), "hormigon.fc"),
        (lambda d: d["acero"].update(fy="420"), "acero.fy"),
        (lambda d: d["criterios"].update(d_estribo=9), "criterios.d_estribo"),
        (lambda d: d["criterios"].pop("recubrimiento"), "criterios.recubrimiento"),
        (lambda d: d.update(elementos=[{"barra": 1}, {"barra": 1}]), "elementos[1].barra"),
        (lambda d: d.update(elementos=[{"barra": 1, "tipo": "losa"}]), "elementos[0].tipo"),
        (lambda d: d.update(elementos=[{"barra": 1, "b": 0}]), "elementos[0].b"),
        (lambda d: d.update(otra=1), "otra"),
        (lambda d: d.update(modelo_sha256="abc"), "modelo_sha256"),
    ],
)
def test_diseno_invalido(cambio, ruta):
    d = formato.diseno.nuevo()
    cambio(d)
    with pytest.raises(formato.FormatoError) as e:
        formato.diseno.validar(d)
    assert e.value.miembro == "diseno.json" and e.value.ruta == ruta


def test_unidades_de_viga_no_reconocidas():
    doc, combs = _portico()
    m, idx = formato.construir_modelo(doc.modelo)
    with pytest.raises(ValueError, match="unidades"), warnings.catch_warnings():
        warnings.simplefilter("ignore")
        aci318.disenar_viga(
            m.resolver(combinaciones=combs),
            idx.barras[2],
            aci318.SeccionRectangular(250, 500),
            aci318.Materiales(fc=25),
            fuerza="lbf",
        )
