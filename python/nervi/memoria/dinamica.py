# SPDX-License-Identifier: GPL-3.0-or-later
"""Capítulo «Análisis dinámico» de la memoria: masas, modos y espectros.

Lo arma :func:`capitulo_dinamica` con los resultados de
``nervi.dinamica_plana`` y se suma a la memoria con ``Memoria.agregar``, como
los capítulos de diseño.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

import numpy as np

from ..modelo import Modelo
from .dibujo import Geometria, figura_deformada, figura_diagrama
from .documento import Capitulo, Figura, Rotulo, Tabla, Trazo, formatear, formatear_factor

TITULO = "Análisis dinámico"
#: Formas modales que se dibujan como máximo.
MAX_FIGURAS_MODOS = 6

_METODO = (
    "Análisis modal lineal elástico. Las masas se concentran en los nudos y salen de las "
    "cargas verticales de los casos indicados: m = −F<sub>y</sub> · factor / g, con las "
    "cargas en barras repartidas a sus nudos por estática; actúan en X y en Y. Se resuelve "
    "K φ = ω² M φ y los modos se normalizan a masa (φ<sup>T</sup> M φ = 1). El factor de "
    "participación es Γ = φ<sup>T</sup> M r, la masa efectiva Γ² y la masa participante "
    "Γ² / ΣM en cada dirección."
)
_METODO_ESPECTRO = (
    "Para cada modo, la respuesta es la estática con u = Γ S<sub>a</sub>(T) / ω² φ, con "
    "S<sub>a</sub> interpolada linealmente en el espectro dado. Las respuestas modales se "
    "combinan con SRSS o con CQC (coeficientes de correlación de Der Kiureghian, 1981). Los "
    "valores combinados son absolutos: no tienen signo y no se suman a los casos de carga. "
    "El espectro lo define quien diseña según la norma que corresponda; esta memoria no "
    "aplica factores de reducción ni escalado del cortante basal."
)


def figura_espectro(
    puntos: Sequence[tuple[float, float]],
    periodos: Sequence[float],
    titulo: str,
    formato: Callable[[float], str],
) -> Figura:
    """Curva ``Sa/g`` en función de ``T`` con los periodos de los modos marcados."""
    pts = np.asarray(puntos, dtype=float)
    tmax = max(float(pts[:, 0].max()), float(max(periodos, default=0.0)), 1e-6) * 1.05
    smax = max(float(pts[:, 1].max()), 1e-9)
    ey = 0.45 * tmax / smax  # la curva ocupa un alto de 0,45 del ancho
    fig = Figura(titulo)
    fig.trazos.append(Trazo(np.array([[0.0, 0.0], [tmax, 0.0]]), "estructura"))
    fig.trazos.append(Trazo(np.array([[0.0, 0.0], [0.0, 1.08 * smax * ey]]), "estructura"))
    curva = pts.copy()
    if curva[-1, 0] < tmax:  # fuera del rango se toma el último valor
        curva = np.vstack([curva, [tmax, curva[-1, 1]]])
    curva[:, 1] *= ey
    fig.trazos.append(Trazo(curva, "positivo"))
    paso_t = _paso(tmax)
    for t in np.arange(0.0, tmax + 1e-9, paso_t):
        fig.trazos.append(Trazo(np.array([[t, 0.0], [t, -0.012 * tmax]]), "estructura"))
        fig.rotulos.append(Rotulo(float(t), -0.04 * tmax, formato(float(t)), "barra"))
    paso_s = _paso(smax)
    for s in np.arange(0.0, smax * 1.05 + 1e-12, paso_s):
        y = float(s) * ey
        fig.trazos.append(Trazo(np.array([[0.0, y], [-0.012 * tmax, y]]), "estructura"))
        fig.rotulos.append(Rotulo(-0.05 * tmax, y, formato(float(s)), "barra"))
    for k, t in enumerate(periodos):
        sa = float(np.interp(t, pts[:, 0], pts[:, 1]))
        fig.trazos.append(Trazo(np.array([[t, 0.0], [t, sa * ey]]), "tenue"))
        if k == 0:
            fig.rotulos.append(Rotulo(float(t), sa * ey + 0.035 * tmax, "T1", "barra"))
    fig.rotulos.append(Rotulo(tmax * 0.98, -0.085 * tmax, "T (s)", "barra"))
    fig.rotulos.append(Rotulo(0.0, 1.08 * smax * ey + 0.035 * tmax, "Sa/g", "barra"))
    return fig


def _paso(maximo: float) -> float:
    crudo = maximo / 5
    base = 10 ** np.floor(np.log10(crudo))
    for m in (1, 2, 2.5, 5, 10):
        if m * base >= crudo:
            return float(m * base)
    return float(10 * base)


def capitulo_dinamica(
    modelo: Modelo,
    modal,
    datos: Mapping,
    espectros: Mapping[str, object],
    gravedad: float,
    fuerza: str = "kN",
    longitud: str = "m",
    nombre_nudo: Callable[[int], str] | None = None,
    nombre_barra: Callable[[int], str] | None = None,
    decimal: str = ",",
    cifras: int = 4,
) -> Capitulo:
    """Capítulo con las masas, la tabla modal, las formas modales y, por
    espectro, sus datos, el cortante basal y los diagramas.

    ``modal`` es un ``nervi.dinamica_plana.ResultadosModalPlano``, ``datos`` el
    diccionario de ``dinamica.json`` y ``espectros`` ``{nombre: resultado}`` de
    ``ResultadosModalPlano.espectro``.
    """
    nudo = nombre_nudo or (lambda k: f"N{k + 1}")
    barra = nombre_barra or (lambda k: f"B{k + 1}")

    def num(v: float) -> str:
        return formatear(v, cifras, decimal)

    F, L = fuerza, longitud
    unidad_masa = f"{F}·s²/{L}"
    geo = Geometria(modelo.arreglos())
    s = Capitulo(TITULO, pagina_nueva=True)

    # --- Masas -------------------------------------------------------------------------
    sm = s.subcapitulo("Masas")
    sm.parrafo(_METODO)
    filas = [
        [nombre, formatear_factor(f, decimal)] for nombre, f in datos["masas"]["casos"].items() if f
    ]
    sm.tabla(
        Tabla(
            ["Caso", "Factor"],
            filas,
            titulo="Casos de carga que aportan masa",
            anchos=[2, 1],
            nota=f"g = {num(gravedad)} {L}/s².",
        )
    )
    sm.tabla(
        Tabla(
            ["Dirección", f"Masa ({unidad_masa})"],
            [["X", num(modal.masa_total[0])], ["Y", num(modal.masa_total[1])]],
            titulo="Masa total que puede participar",
            anchos=[1, 1],
            alineacion=["izq", "der"],
        )
    )

    # --- Modos -------------------------------------------------------------------------
    so = s.subcapitulo("Modos de vibración")
    p = 100 * modal.masa_participante
    a = 100 * modal.masa_participante_acumulada
    filas = []
    for k in range(modal.n_modos):
        filas.append(
            [
                str(k + 1),
                num(modal.periodos[k]),
                num(modal.frecuencias[k]),
                *(f"{v:.1f}".replace(".", decimal) for v in (p[k, 0], p[k, 1], a[k, 0], a[k, 1])),
            ]
        )
    so.tabla(
        Tabla(
            [
                "Modo",
                "T (s)",
                "f (Hz)",
                "M<sub>x</sub> %",
                "M<sub>y</sub> %",
                "ΣM<sub>x</sub> %",
                "ΣM<sub>y</sub> %",
            ],
            filas,
            titulo="Periodos y masa participante",
            nota="M %: masa efectiva del modo sobre la masa total de esa dirección; ΣM: acumulada.",
        )
    )
    falta = [d for d, col in (("X", 0), ("Y", 1)) if modal.masa_total[col] > 0 and a[-1, col] < 90]
    if falta:
        so.parrafo(
            "Con los modos calculados la masa participante acumulada no llega al 90 % en "
            + " ni en ".join(falta)
            + ". Las normas sísmicas suelen pedirlo en las direcciones horizontales: "
            "conviene pedir más modos.",
            "aviso",
        )
    for k in range(min(modal.n_modos, MAX_FIGURAS_MODOS)):
        fig = figura_deformada(
            geo,
            modal.modo(k),
            f"Modo {k + 1} · T = {num(modal.periodos[k])} s",
            num,
            grupo="modos",
        )
        fig.titulo = fig.titulo.split(" (×")[0]  # la amplitud de un modo es arbitraria
        so.figura(fig)

    # --- Espectros ---------------------------------------------------------------------
    for e in datos["espectros"]:
        r = espectros.get(e["nombre"])
        if r is None:
            continue
        se = s.subcapitulo(f"Espectro de respuesta «{e['nombre']}»", pagina_nueva=True)
        se.parrafo(_METODO_ESPECTRO)
        z = 100 * e["amortiguamiento"]
        se.tabla(
            Tabla(
                ["Dato", "Valor"],
                [
                    ["Dirección de la excitación", e["direccion"]],
                    ["Combinación modal", e["combinacion"]],
                    ["Amortiguamiento", f"{num(z)} % del crítico"],
                ],
                titulo="Datos del análisis",
                anchos=[1.5, 2],
                alineacion=["izq", "izq"],
            )
        )
        se.figura(figura_espectro(e["puntos"], modal.periodos, "Espectro de diseño", num))
        se.tabla(
            Tabla(
                ["T (s)", "S<sub>a</sub>/g", f"S<sub>a</sub> ({L}/s²)"],
                [[num(t), num(sa), num(sa * gravedad)] for t, sa in e["puntos"]],
                titulo="Puntos del espectro",
                alineacion=["der", "der", "der"],
            )
        )
        col = 0 if e["direccion"] == "X" else 1
        filas = [
            [
                str(k + 1),
                num(modal.periodos[k]),
                num(r.aceleraciones[k] / gravedad),
                num(r.factores[k]),
                num(r.cortante_basal_modal[k, col]),
            ]
            for k in range(modal.n_modos)
        ]
        filas.append(["<b>Combinado</b>", "", "", "", f"<b>{num(r.cortante_basal[col])}</b>"])
        se.tabla(
            Tabla(
                ["Modo", "T (s)", "S<sub>a</sub>/g", "Γ", f"V<sub>basal</sub> ({F})"],
                filas,
                titulo=f"Cortante basal en {e['direccion']}",
                nota=f"Combinación {e['combinacion']} de los cortantes basales modales.",
            )
        )
        grupo = f"esp-{e['nombre']}"
        se.figura(figura_diagrama(geo, r, "M", f"|M| ({F}·{L})", num, grupo))
        se.figura(figura_diagrama(geo, r, "V", f"|V| ({F})", num, grupo))
        se.figura(figura_diagrama(geo, r, "N", f"|N| ({F})", num, grupo))
        se.figura(figura_deformada(geo, r, "Desplazamientos", num, grupo))
        arr = modelo.arreglos()
        apoyados = [
            k
            for k in range(len(arr["coords"]))
            if arr["restricciones"][k].any() or arr["resortes"][k].any()
        ]
        se.tabla(
            Tabla(
                [
                    "Nudo",
                    f"|R<sub>x</sub>| ({F})",
                    f"|R<sub>y</sub>| ({F})",
                    f"|M<sub>z</sub>| ({F}·{L})",
                ],
                [[nudo(k), *(num(v) for v in r.reacciones[k])] for k in apoyados],
                titulo="Reacciones de apoyo (valores absolutos combinados)",
            )
        )
        se.tabla(
            Tabla(
                [
                    "Nudo",
                    f"|u<sub>x</sub>| ({L})",
                    f"|u<sub>y</sub>| ({L})",
                    "|r<sub>z</sub>| (rad)",
                ],
                [[nudo(k), *(num(v) for v in fila)] for k, fila in enumerate(r.desplazamientos)],
                titulo="Desplazamientos de los nudos (valores absolutos combinados)",
            )
        )
        filas = []
        for b in range(len(arr["conectividad"])):
            d = r.diagrama(b)
            if d["x"].size:
                filas.append([barra(b), *(num(np.abs(d[c]).max()) for c in ("N", "V", "M"))])
        se.tabla(
            Tabla(
                ["Barra", f"|N| máx ({F})", f"|V| máx ({F})", f"|M| máx ({F}·{L})"],
                filas,
                titulo="Esfuerzos máximos por barra",
            )
        )
    return s
