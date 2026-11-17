# SPDX-License-Identifier: GPL-3.0-or-later
"""Memoria de cálculo en PDF (issue #28)."""

import runpy
import subprocess
import sys
from pathlib import Path

import pytest

import nervi
from nervi.memoria import (
    CAPITULOS,
    Capitulo,
    Plantilla,
    Tabla,
    formatear,
    formatear_factor,
    memoria_de_calculo,
    tabla_verificaciones,
)
from nervi.memoria.dibujo import Geometria, figura_diagrama

RAIZ = Path(__file__).resolve().parent.parent
EJEMPLOS = RAIZ / "examples"


def _portico():
    ns = runpy.run_path(str(EJEMPLOS / "portico_simple.py"))
    m, viga, cabeza = ns["armar_modelo"]()
    return m, viga, cabeza, ns["COMBINACIONES"]


def _tablas(capitulo):
    for b in capitulo.bloques:
        if isinstance(b, Tabla):
            yield b
        elif isinstance(b, Capitulo):
            yield from _tablas(b)


def _texto_pdf(ruta: Path) -> str:
    """Texto del PDF (necesita pypdf, dependencia de desarrollo)."""
    pypdf = pytest.importorskip("pypdf")
    return "\n".join(p.extract_text() for p in pypdf.PdfReader(ruta).pages)


# --- Formato de números ------------------------------------------------------------
@pytest.mark.parametrize(
    "valor, esperado",
    [
        (0.0, "0"),
        (-1e-15, "0"),
        (119.0833333, "119,1"),
        (-60.9166, "-60,92"),
        (0.000675, "0,000675"),
        (2.5e7, "2,5e7"),
        (1.46e-5, "1,46e-5"),
        (float("nan"), "—"),
    ],
)
def test_formatear(valor, esperado):
    assert formatear(valor) == esperado


def test_formatear_punto_decimal_y_factores():
    assert formatear(1.25, decimal=".") == "1.25"
    assert formatear_factor(1) == "1,0"
    assert formatear_factor(1.2) == "1,2"
    assert formatear_factor(0.75, ".") == "0.75"


# --- Contenido ---------------------------------------------------------------------
def test_memoria_del_ejemplo_tiene_todos_los_capitulos():
    m, _viga, _cabeza, combs = _portico()
    doc = memoria_de_calculo(m, m.resolver(combinaciones=combs))
    titulos = [s.titulo for s in doc.capitulos]
    assert titulos == [CAPITULOS[k] for k in CAPITULOS]
    resultados = doc.capitulos[titulos.index("Resultados")]
    subs = [b.titulo for b in resultados.bloques if isinstance(b, Capitulo)]
    assert subs == ["Caso D", "Caso L", "Caso W"] + [f"Combinación {n}" for n in combs]


def test_tablas_reproducen_los_resultados():
    m, viga, cabeza, combs = _portico()
    res = m.resolver(combinaciones=combs)
    doc = memoria_de_calculo(m, res)
    resultados = doc.capitulos[[s.titulo for s in doc.capitulos].index("Resultados")]
    sub = next(b for b in resultados.bloques if getattr(b, "titulo", "") == "Combinación 1.2D+1.6L")
    tablas = {t.titulo: t for t in _tablas(sub)}
    # Reacciones: N1 (índice 0) es la base izquierda.
    reac = tablas["Reacciones de apoyo (ejes globales)"]
    assert reac.filas[0][0] == "N1"
    r = res["1.2D+1.6L"].reacciones[0]
    assert reac.filas[0][1:] == [formatear(v) for v in r]
    # Momento máximo de la viga y su posición (centro de la luz).
    extremos = tablas["Valores extremos por barra"]
    fila = extremos.filas[viga]
    assert fila[0] == f"B{viga + 1}"
    assert fila[6] == "119,1"
    assert fila[7] == "3"
    # Desplazamiento lateral de la cabeza izquierda.
    despl = tablas["Desplazamientos de los nudos (ejes globales)"]
    assert despl.filas[cabeza][1] == formatear(res["1.2D+1.6L"].desplazamientos[cabeza, 0])


def test_envolvente_elige_la_combinacion_que_manda():
    m, viga, _cabeza, combs = _portico()
    doc = memoria_de_calculo(m, m.resolver(combinaciones=combs))
    env = next(_tablas(doc.capitulos[-1]))
    fila_m = next(f for f in env.filas if f[0] == f"B{viga + 1}" and f[1].startswith("M"))
    assert fila_m[2:4] == ["119,1", "1.2D+1.6L"]
    assert fila_m[4:6] == ["-62,09", "1.2D+1.0L+1.0W"]


def test_combinaciones_sin_resolver_se_calculan_por_superposicion():
    m, _viga, _cabeza, combs = _portico()
    res = m.resolver()
    doc = memoria_de_calculo(m, res, combinaciones=combs, incluir_casos=False)
    resultados = doc.capitulos[[s.titulo for s in doc.capitulos].index("Resultados")]
    subs = [b.titulo for b in resultados.bloques if isinstance(b, Capitulo)]
    assert subs == [f"Combinación {n}" for n in combs]
    tabla = next(t for t in _tablas(doc.capitulos[4]))
    assert tabla.filas[1] == ["1.2D+1.6L", "1,2·D + 1,6·L"]


def test_cargas_de_todos_los_tipos():
    m = nervi.Modelo()
    a, b = m.agregar_nudo(0, 0), m.agregar_nudo(6, 0)
    barra = m.agregar_barra(a, b, E=2e8, A=0.01, I=1e-4)
    m.apoyar(a)
    m.resorte(b, ky=1e4)
    m.carga_uniforme("D", barra, qy=-5, ejes="global")
    m.carga_puntual("D", barra, 2.0, py=-10)
    m.carga_trapezoidal("D", barra, qy1=-2, qy2=-6, a=1, b=4)
    m.carga_termica("T", barra, alfa=1.2e-5, dt=20, gradiente=10, h=0.3)
    m.carga_momento("D", barra, 3.0, 4.0)
    m.desplazamiento_impuesto("A", a, uy=-0.01)
    doc = memoria_de_calculo(m)
    cargas = doc.capitulos[3]
    tipos = [f[1] for t in _tablas(cargas) if t.titulo == "Cargas en barras" for f in t.filas]
    assert tipos == ["Uniforme", "Puntual", "Trapezoidal", "Momento", "Térmica"]
    assert any(t.titulo.startswith("Desplazamientos impuestos") for t in _tablas(cargas))


def test_nombres_y_unidades_propios():
    m, _viga, _cabeza, _combs = _portico()
    doc = memoria_de_calculo(
        m, nombres_nudos={0: "A"}, nombres_barras=lambda k: f"C-{k}", fuerza="tf", longitud="cm"
    )
    nudos = next(_tablas(doc.capitulos[1]))
    assert [f[0] for f in nudos.filas] == ["A", "N2", "N3", "N4"]
    assert nudos.columnas[1] == "x (cm)"
    barras = list(_tablas(doc.capitulos[1]))[1]
    assert [f[0] for f in barras.filas] == ["C-0", "C-1", "C-2"]


def test_plantilla_propia(tmp_path):
    propia = tmp_path / "plantilla.toml"
    propia.write_text(
        'titulo = "Memoria del galpón"\ndecimal = "."\n'
        '[textos]\nalcance = "Proyecto {proyecto}."\n',
        encoding="utf-8",
    )
    m, _viga, _cabeza, _combs = _portico()
    doc = memoria_de_calculo(m, plantilla=propia, datos_proyecto={"Proyecto": "Galpón"})
    assert doc.titulo == "Memoria del galpón"
    assert doc.capitulos[0].bloques[0].texto == "Proyecto Galpón."
    # Lo que no cambia sale de la plantilla por defecto.
    assert doc.capitulos[0].bloques[1].texto.startswith("El análisis es lineal elástico")
    tipos = next(_tablas(doc.capitulos[2]))
    assert tipos.filas[0][2] == "0.09"


def test_plantilla_por_defecto_tiene_todas_las_claves():
    pl = Plantilla.cargar(variables={"proyecto": "X"})
    for clave in ("alcance", "metodo", "convenciones", "unidades", "cargas", "resultados"):
        assert pl.texto(clave)
    assert "{version}" in pl.texto("portada.aviso")  # variable sin valor: queda tal cual


# --- Extensión: verificaciones de diseño -------------------------------------------
def test_tabla_verificaciones():
    t = tabla_verificaciones(
        [("B2", "Flexión", -119.1, 150.0, "ACI 318-19 §9.5.1.1"), ("B2", "Corte", 90, 80, "x")],
        unidades="kN·m",
    )
    assert t.filas[0][2:6] == ["-119,1", "150", "0,79", "Cumple"]
    assert t.filas[1][5] == "NO CUMPLE"
    assert t.columnas[2] == "Solicitación (kN·m)"


def test_agregar_capitulo_de_diseno(tmp_path):
    m, _viga, _cabeza, combs = _portico()
    doc = memoria_de_calculo(m, m.resolver(combinaciones=combs))
    diseno = Capitulo("Verificaciones de diseño")
    diseno.parrafo("Ejemplo de capítulo agregado por un módulo de diseño.")
    diseno.tabla(tabla_verificaciones([("B2", "Flexión", 119.1, 150.0, "ACI 318-19 §9.5")]))
    doc.agregar(diseno, antes_de=CAPITULOS["envolvente"])
    pytest.importorskip("reportlab")
    titulos = [s.titulo for s in doc.capitulos]
    assert titulos.index("Verificaciones de diseño") == titulos.index("Envolventes") - 1
    ruta = doc.guardar_pdf(tmp_path / "con_diseno.pdf")
    assert "Verificaciones de diseño" in _texto_pdf(ruta)


# --- Dibujo ------------------------------------------------------------------------
def test_momento_positivo_se_dibuja_del_lado_traccionado():
    m = nervi.Modelo()
    a, b = m.agregar_nudo(0, 0), m.agregar_nudo(4, 0)
    barra = m.agregar_barra(a, b, E=2e8, A=0.01, I=1e-4)
    m.apoyar(a, rz=False)
    m.apoyar(b, ux=False, rz=False)
    m.carga_uniforme("D", barra, qy=-10)
    res = m.resolver()
    geo = Geometria(m.arreglos())
    fig = figura_diagrama(geo, res["D"], "M", "M", str)
    positivos = [t for t in fig.trazos if t.estilo == "positivo"]
    assert len(positivos) == 1
    assert positivos[0].puntos[:, 1].min() < -0.1  # abajo de la viga
    assert not [t for t in fig.trazos if t.estilo == "negativo"]
    assert any(r.texto == "20.0" for r in fig.rotulos)  # qL²/8 = 20 en el centro


# --- PDF ---------------------------------------------------------------------------
def test_pdf_del_ejemplo(tmp_path):
    """Lo que pide el issue #28: la memoria de examples/portico_simple.py se genera."""
    pytest.importorskip("reportlab")
    salida = tmp_path / "memoria.pdf"
    subprocess.run(
        [sys.executable, str(EJEMPLOS / "memoria_portico_simple.py"), str(salida)],
        check=True,
        cwd=tmp_path,
    )
    assert salida.read_bytes().startswith(b"%PDF")
    texto = _texto_pdf(salida)
    for esperado in (
        "Memoria de cálculo estructural",
        "Pórtico de una crujía (ejemplo)",
        "Índice",
        "Combinación 1.2D+1.6L",
        "Envolvente de esfuerzos",
        "119,1",
    ):
        assert esperado in texto, esperado


def test_pdf_con_simbolos_griegos(tmp_path):
    pytest.importorskip("reportlab")
    m = nervi.Modelo()
    a, b = m.agregar_nudo(0, 0), m.agregar_nudo(5, 0)
    barra = m.agregar_barra(a, b, E=2e8, A=0.01, I=1e-4)
    m.apoyar(a)
    m.apoyar(b)
    m.carga_termica("T", barra, alfa=1e-5, dt=30)
    ruta = memoria_de_calculo(m).guardar_pdf(tmp_path / "termica.pdf")
    assert "Térmica" in _texto_pdf(ruta)


def test_doctest_del_modulo():
    import doctest

    import nervi.memoria as mod

    assert doctest.testmod(mod).failed == 0
