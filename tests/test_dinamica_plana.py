# SPDX-License-Identifier: GPL-3.0-or-later
"""Análisis modal y espectral del pórtico plano (``nervi.dinamica_plana``).

El motor es el del pórtico espacial (``tests/test_dinamica_3d.py`` y
``crates/nervi-core/tests/dinamica_3d.rs``); acá se verifica el paso del plano
al plano XZ y de vuelta, contra soluciones cerradas y contra el motor plano.
"""

import json
from pathlib import Path

import numpy as np
import pytest

import nervi
from nervi import dinamica_plana, formato

G = 9.80665
E = 2.5e7


def _columna(h=3.0, inercia=6.75e-4, peso=98.0665):
    m = nervi.Modelo()
    a, b = m.agregar_nudo(0, 0), m.agregar_nudo(0, h)
    m.agregar_barra(a, b, E=E, A=0.09, I=inercia)
    m.apoyar(a)
    m.carga_nodal("D", b, fy=-peso)
    return m


def test_voladizo_con_masa_en_la_punta():
    # T = 2π √(m h³ / 3EI) con m = P / g.
    h, inercia = 3.0, 6.75e-4
    modal = dinamica_plana.modal(_columna(h, inercia), {"D": 1.0}, G, n_modos=2)
    k = 3 * E * inercia / h**3
    assert modal.periodos[0] == pytest.approx(2 * np.pi * np.sqrt(10.0 / k), rel=1e-9)
    # El primer modo es horizontal; el segundo, axial (vertical).
    np.testing.assert_allclose(modal.masa_participante[0], [1.0, 0.0], atol=1e-12)
    np.testing.assert_allclose(modal.masa_participante[1], [0.0, 1.0], atol=1e-12)
    assert modal.periodos[1] == pytest.approx(2 * np.pi * np.sqrt(10.0 * h / (E * 0.09)))
    np.testing.assert_allclose(modal.masa_total, [10.0, 10.0])
    # Espectro: V = m Sa, M en la base = V h y u = Sa / ω².
    sa = 4.0
    r = modal.espectro([(0.0, sa), (5.0, sa)], "X")
    assert r.cortante_basal[0] == pytest.approx(10.0 * sa)
    assert r.reacciones[0, 0] == pytest.approx(10.0 * sa)
    assert r.reacciones[0, 2] == pytest.approx(10.0 * sa * h)
    assert r.desplazamientos[1, 0] == pytest.approx(sa / modal.omegas[0] ** 2)
    d = r.diagrama(0)
    np.testing.assert_allclose(np.abs(d["M"]), 10.0 * sa * (h - d["x"]), rtol=1e-9, atol=1e-9)
    assert np.all(r.desplazamientos >= 0) and np.all(r.reacciones >= 0)


def _edificio_de_cortante(k_piso=2e4, masa=10.0, h=3.0):
    """Dos pisos con vigas casi rígidas: cada piso es un resorte de rigidez
    ``2 · 12 EI / h³`` (dos columnas empotradas en los dos extremos)."""
    inercia = k_piso * h**3 / (24 * E)
    m = nervi.Modelo()
    n = [[m.agregar_nudo(x, p * h) for x in (0.0, 6.0)] for p in range(3)]
    for p in range(2):
        for c in range(2):
            m.agregar_barra(n[p][c], n[p + 1][c], E=E, A=1e3, I=inercia)
        m.agregar_barra(n[p + 1][0], n[p + 1][1], E=E, A=1e3, I=1e3)
    for c in range(2):
        m.apoyar(n[0][c])
    for p in (1, 2):
        for c in range(2):
            m.carga_nodal("D", n[p][c], fy=-masa * G / 2)
    return m


def test_edificio_de_cortante_de_dos_pisos():
    k, masa = 2e4, 10.0
    modal = dinamica_plana.modal(_edificio_de_cortante(k, masa), {"D": 1.0}, G, n_modos=2)
    w2 = np.array([(3 - np.sqrt(5)) / 2, (3 + np.sqrt(5)) / 2]) * k / masa
    np.testing.assert_allclose(modal.omegas**2, w2, rtol=1e-5)  # vigas casi rígidas
    # Formas con el número de oro: φ2/φ1 = φ (modo 1) y -1/φ (modo 2).
    oro = (1 + np.sqrt(5)) / 2
    formas = modal.formas()
    for k_modo, razon in ((0, oro), (1, -1 / oro)):
        assert formas[k_modo, 4, 0] / formas[k_modo, 2, 0] == pytest.approx(razon, rel=1e-5)
    # Masa efectiva cerrada: Γ² con φ normalizado a masa.
    np.testing.assert_allclose(modal.masa_participante_acumulada[-1, 0], 1.0, rtol=1e-6)
    gamma1 = masa * (1 + oro) / np.sqrt(masa * (1 + oro**2))
    assert modal.masas_efectivas[0, 0] == pytest.approx(gamma1**2, rel=1e-5)
    # SRSS con espectro constante: V = Sa √(Σ M_ef²); CQC con modos separados, casi igual.
    sa = 3.0
    srss = modal.espectro([(0, sa), (9, sa)], "X", combinacion="SRSS")
    esperado = sa * np.sqrt(np.sum(modal.masas_efectivas[:, 0] ** 2))
    assert srss.cortante_basal[0] == pytest.approx(esperado, rel=1e-9)
    np.testing.assert_allclose(
        srss.cortante_basal_modal[:, 0] ** 2, (sa * modal.masas_efectivas[:, 0]) ** 2, rtol=1e-9
    )
    cqc = modal.espectro([(0, sa), (9, sa)], "X", combinacion="CQC")
    assert cqc.cortante_basal[0] == pytest.approx(esperado, rel=0.02)
    assert cqc.combinacion == "CQC" and cqc.direccion == "X"


def test_modo_como_resultado_del_plano():
    m = _edificio_de_cortante()
    modal = dinamica_plana.modal(m, {"D": 1.0}, G, n_modos=2)
    for k, modo in enumerate(modal.modos()):
        assert modo.nombre == f"Modo {k + 1}"
        u = modo.desplazamientos
        # Escalado a traslación máxima 1 y misma forma que el modo normalizado a masa.
        assert np.abs(u[:, :2]).max() == pytest.approx(1.0)
        phi = modal.formas()[k]
        escala = u[4, 0] / phi[4, 0]
        np.testing.assert_allclose(u, escala * phi, atol=1e-9)
        # Equilibrio: las reacciones equilibran las fuerzas de inercia ω² M u.
        inercia_x = modal.omegas[k] ** 2 * 5.0 * u[[2, 3, 4, 5], 0].sum()
        assert modo.reacciones[:, 0].sum() == pytest.approx(-inercia_x, rel=1e-6)
    assert modal.modo(0) is modal.modos()[0]


def test_conversion_al_plano_xz_coincide_con_el_motor_plano():
    # Pórtico con articulación, resorte, barra inclinada y cargas en ejes locales y
    # globales: el modelo espacial resuelto y llevado al plano da lo mismo.
    m = nervi.Modelo()
    a, b, c, d = (m.agregar_nudo(*p) for p in ((0, 0), (0, 3), (5, 4), (5, 0)))
    m.agregar_barra(a, b, E=E, A=0.09, I=6.75e-4)
    m.agregar_barra(c, b, E=E, A=0.12, I=2.5e-3, articulada_i=True)  # de derecha a izquierda
    m.agregar_barra(d, c, E=E, A=0.09, I=6.75e-4)
    m.apoyar(a)
    m.apoyar(d, rz=False)
    m.resorte(d, krz=5e3)
    m.carga_uniforme("D", 1, qy=-12.0, ejes="global")
    m.carga_puntual("D", 1, 2.0, py=-30.0)
    m.carga_trapezoidal("D", 0, qy1=2.0, qy2=6.0, a=0.5, b=2.5)
    m.carga_nodal("D", b, fx=8.0, mz=5.0)
    plano = m.resolver()["D"]
    espacial = dinamica_plana.modelo_espacial(m).resolver()["D"]
    r = dinamica_plana._caso_plano("D", espacial)
    np.testing.assert_allclose(r.desplazamientos, plano.desplazamientos, rtol=1e-8, atol=1e-12)
    np.testing.assert_allclose(r.reacciones, plano.reacciones, rtol=1e-8, atol=1e-9)
    np.testing.assert_allclose(r.fuerzas_extremo, plano.fuerzas_extremo, rtol=1e-8, atol=1e-9)
    for barra in range(3):
        d3, d2 = r.diagrama(barra), plano.diagrama(barra)
        # Se compara fuera de los saltos (estaciones repetidas en el motor plano).
        saltos = d2["x"][1:][np.diff(d2["x"]) == 0]
        lejos = np.all(np.abs(d3["x"][:, None] - saltos[None, :]) > 1e-9, axis=1)
        for clave in ("N", "V", "M", "v"):
            np.testing.assert_allclose(
                d3[clave][lejos],
                np.interp(d3["x"][lejos], d2["x"], d2[clave]),
                rtol=1e-6,
                atol=1e-6,
            )


def test_masa_desde_cargas_en_barras():
    # Viga inclinada dibujada de derecha a izquierda (y local hacia abajo) sobre dos
    # columnas: toda su carga vertical llega a nudos libres y es masa en X.
    m = nervi.Modelo()
    a, b, c, d = (m.agregar_nudo(*p) for p in ((0, 0), (0, 3), (5, 4), (5, 0)))
    m.agregar_barra(a, b, E=E, A=0.09, I=6.75e-4)
    viga = m.agregar_barra(c, b, E=E, A=0.12, I=2.5e-3)
    m.agregar_barra(d, c, E=E, A=0.09, I=6.75e-4)
    m.apoyar(a)
    m.apoyar(d)
    largo = np.hypot(5, 1)
    m.carga_uniforme("D", viga, qy=-10.0, ejes="global")  # 10 L hacia abajo
    m.carga_uniforme("L", viga, qy=2.0)  # local: 2 · 5 / L · L = 10 hacia abajo
    m.carga_puntual("L", viga, 1.0, px=4.0)  # a lo largo de la barra: 4 · 1 / L hacia abajo
    m.carga_termica("T", viga, 1e-5, dt=20.0)  # no aporta masa
    modal = dinamica_plana.modal(m, {"D": 1.0, "L": 0.5, "T": 1.0}, G, n_modos=2)
    total = (10.0 * largo + 0.5 * (10.0 + 4.0 / largo)) / G
    np.testing.assert_allclose(modal.masa_total, [total, total], rtol=1e-9)


def test_errores():
    m = _columna()
    with pytest.raises(ValueError):
        dinamica_plana.modal(m, {}, G)
    modal = dinamica_plana.modal(m, {"D": 1.0}, G, n_modos=1)
    with pytest.raises(ValueError, match="dirección"):
        modal.espectro([(0, 1.0)], "Z")
    assert "ResultadosModalPlano(1 modos" in repr(modal)
    assert "modo" in modal.tabla()


# --- Formato .nrv ------------------------------------------------------------------------
DATOS = Path(__file__).parent / "datos" / "nrv"


def test_validar_dinamica():
    d = formato.dinamica.nuevo()
    d["espectros"].append(formato.dinamica.espectro_ejemplo())
    formato.dinamica.validar(d)
    malos = [
        (lambda x: x.update(n_modos=0), "n_modos"),
        (lambda x: x["masas"]["casos"].update(D=-1), "masas.casos.D"),
        (lambda x: x["espectros"][0].update(direccion="Z"), "direccion"),
        (lambda x: x["espectros"][0].update(combinacion="ABS"), "combinacion"),
        (lambda x: x["espectros"][0].update(amortiguamiento=1.5), "amortiguamiento"),
        (lambda x: x["espectros"][0].update(puntos=[[1, 1], [0.5, 1]]), "puntos[1]"),
        (lambda x: x["espectros"][0].update(puntos=[]), "puntos"),
        (lambda x: x["espectros"].append(dict(x["espectros"][0])), "espectros[1].nombre"),
        (lambda x: x.update(otra=1), "otra"),
    ]
    for cambio, ruta in malos:
        e = json.loads(json.dumps(d))
        cambio(e)
        with pytest.raises(formato.FormatoError) as err:
            formato.dinamica.validar(e)
        assert ruta in err.value.ruta


def test_dinamica_se_guarda_y_se_abre(tmp_path):
    doc = formato.Documento.nuevo()
    assert doc.dinamica is None
    ruta = tmp_path / "p.nrv"
    formato.guardar(doc, ruta)
    assert "dinamica" not in formato.abrir(ruta).manifiesto["modulos"]
    doc.dinamica = formato.dinamica.nuevo()
    doc.dinamica["espectros"].append(formato.dinamica.espectro_ejemplo())
    formato.guardar(doc, ruta)
    leido = formato.abrir(ruta)
    assert leido.dinamica == doc.dinamica
    assert leido.manifiesto["modulos"]["dinamica"]["version"] == 1


def test_referencia_del_modulo_dinamica():
    # dinamica-v1.nrv se lee igual y da los mismos periodos y cortantes.
    esperado = json.loads((DATOS / "dinamica-v1.esperado.json").read_text(encoding="utf-8"))
    esperado = esperado["dinamica"]
    doc = formato.abrir(DATOS / "dinamica-v1.nrv")
    assert doc.dinamica == esperado["datos"]
    m, _ = formato.construir_modelo(doc.modelo)
    d = doc.dinamica
    modal = dinamica_plana.modal(m, d["masas"]["casos"], G, n_modos=d["n_modos"])
    np.testing.assert_allclose(modal.periodos, esperado["periodos"], rtol=1e-9)
    np.testing.assert_allclose(modal.masa_total, esperado["masa_total"], rtol=1e-12)
    np.testing.assert_allclose(
        modal.masas_efectivas, esperado["masas_efectivas"], rtol=1e-6, atol=1e-9
    )
    for e in d["espectros"]:
        r = modal.espectro(
            [(t, s * G) for t, s in e["puntos"]],
            e["direccion"],
            e["amortiguamiento"],
            e["combinacion"],
        )
        np.testing.assert_allclose(
            r.cortante_basal,
            esperado["espectros"][e["nombre"]]["cortante_basal"],
            rtol=1e-6,
            atol=1e-9,
        )


# --- Memoria -----------------------------------------------------------------------------
def test_capitulo_de_la_memoria(tmp_path):
    pytest.importorskip("reportlab")
    pypdf = pytest.importorskip("pypdf")
    from nervi import memoria
    from nervi.memoria.dinamica import capitulo_dinamica

    m = _edificio_de_cortante()
    modal = dinamica_plana.modal(m, {"D": 1.0}, G, n_modos=2)
    datos = formato.dinamica.nuevo()
    datos["masas"]["casos"] = {"D": 1.0}
    datos["espectros"].append(formato.dinamica.espectro_ejemplo())
    e = datos["espectros"][0]
    espectros = {e["nombre"]: modal.espectro([(t, s * G) for t, s in e["puntos"]], "X")}
    doc = memoria.memoria_de_calculo(m)
    cap = capitulo_dinamica(m, modal, datos, espectros, G)
    doc.agregar(cap)
    titulos = [b.titulo for b in cap.bloques if isinstance(b, memoria.Capitulo)]
    assert titulos == ["Masas", "Modos de vibración", "Espectro de respuesta «Sismo X»"]
    ruta = doc.guardar_pdf(tmp_path / "m.pdf")
    texto = "".join(p.extract_text() for p in pypdf.PdfReader(ruta).pages)
    for frase in ("Análisis dinámico", "Periodos y masa participante", "Cortante basal en X"):
        assert frase in texto
    # Con pocos modos avisa que no se llega al 90 % de masa.
    modal1 = dinamica_plana.modal(m, {"D": 1.0}, G, n_modos=1)
    cap1 = capitulo_dinamica(m, modal1, {**datos, "espectros": []}, {}, G)
    modos = cap1.bloques[1]
    assert any(getattr(b, "estilo", "") == "aviso" for b in modos.bloques)
