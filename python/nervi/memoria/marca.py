# SPDX-License-Identifier: GPL-3.0-or-later
"""Logo de Nervi y carátula de la memoria, dibujados con ReportLab.

La geometría del isotipo y del logotipo es la de ``docs/marca/`` (polígonos y
trazados SVG), copiada acá para no depender de un lector de SVG. Se dibuja como
vectores, así que la carátula no incrusta imágenes ni fuentes.
"""

from __future__ import annotations

import math
import re

from reportlab.lib import colors

# --- Geometría de la marca (docs/marca/nervi-logotipo-claro.svg) ----------------------
#: Caja del isotipo en unidades del SVG: (x0, y0, ancho, alto), con y hacia abajo.
CAJA_ISOTIPO = (10.9, 2.0, 42.2, 60.0)
#: Caja del logotipo completo (isotipo + palabra).
CAJA_LOGOTIPO = (8.9, 0.0, 160.8, 64.0)

#: Caras del isotipo: (puntos, tono). Tonos: 0 = sombra, 1 = luz, 2 = frente.
ISOTIPO: list[tuple[list[tuple[float, float]], int]] = [
    ([(30.53, 23.23), (30.53, 43.03), (21.71, 48.12), (21.71, 28.32)], 0),
    ([(21.71, 4.00), (30.53, 9.09), (21.71, 14.18), (12.89, 9.09)], 1),
    ([(30.53, 9.09), (42.29, 35.68), (33.47, 40.77), (21.71, 14.18)], 1),
    ([(51.11, 20.97), (51.11, 54.91), (42.29, 60.00), (42.29, 26.06)], 0),
    ([(42.29, 15.88), (51.11, 20.97), (42.29, 26.06), (33.47, 20.97)], 1),
    (
        [
            (12.89, 43.03),
            (12.89, 9.09),
            (21.71, 14.18),
            (33.47, 40.77),
            (33.47, 20.97),
            (42.29, 26.06),
            (42.29, 60.00),
            (33.47, 54.91),
            (21.71, 28.32),
            (21.71, 48.12),
        ],
        2,
    ),
]
#: Colores de la marca para cada tono, sobre fondo claro.
TONOS_CLARO = ("#1E3A8A", "#93C5FD", "#3B82F6")
TINTA_MARCA = "#0F172A"

#: Palabra "Nervi" del logotipo (trazado SVG con M, L, H, V, Q y Z absolutos).
PALABRA = (
    "M66.45 47.09V16.91H71.91L84.8 34.73Q85.02 34.99 85.33 35.45Q85.64 35.92 85.9 36.36"
    "Q86.17 36.8 86.25 37.06H86.47V16.91H91.97V47.09H86.56L73.63 29.14Q73.27 28.61 72.81 27.84"
    "Q72.35 27.07 72.17 26.76H71.95V47.09ZM107.68 47.62Q103.99 47.62 101.52 46.32"
    "Q99.06 45.02 97.83 42.34Q96.59 39.66 96.59 35.52Q96.59 31.34 97.83 28.68"
    "Q99.06 26.02 101.52 24.72Q103.99 23.42 107.68 23.42Q111.03 23.42 113.29 24.67"
    "Q115.56 25.93 116.7 28.52Q117.85 31.12 117.85 35.26V36.84H102.09Q102.18 39 102.75 40.47"
    "Q103.33 41.94 104.54 42.67Q105.75 43.4 107.73 43.4Q108.74 43.4 109.62 43.13"
    "Q110.5 42.87 111.16 42.32Q111.82 41.77 112.19 40.93Q112.57 40.1 112.57 39H117.85"
    "Q117.85 41.2 117.08 42.82Q116.31 44.45 114.92 45.51Q113.53 46.56 111.69 47.09"
    "Q109.84 47.62 107.68 47.62ZM102.18 33.06H112.26Q112.26 31.6 111.93 30.59"
    "Q111.6 29.58 111 28.92Q110.41 28.26 109.57 27.97Q108.74 27.69 107.68 27.69"
    "Q105.97 27.69 104.8 28.26Q103.63 28.83 103.02 30.02Q102.4 31.21 102.18 33.06Z"
    "M121.98 47.09V23.95H126.47L126.91 27.6H127.22Q127.66 26.5 128.3 25.55"
    "Q128.93 24.61 129.95 24.01Q130.96 23.42 132.41 23.42Q133.11 23.42 133.71 23.55"
    "Q134.3 23.68 134.61 23.82V28.88H132.98Q131.62 28.88 130.56 29.25Q129.51 29.62 128.78 30.42"
    "Q128.05 31.21 127.7 32.4Q127.35 33.58 127.35 35.17V47.09ZM143.41 47.09 134.83 23.95"
    "H140.46L144.2 34.38Q144.47 35.12 144.84 36.38Q145.21 37.63 145.61 38.97"
    "Q146.01 40.32 146.27 41.42H146.49Q146.75 40.4 147.11 39.08Q147.46 37.76 147.83 36.49"
    "Q148.21 35.21 148.51 34.38L152.21 23.95H157.67L149.04 47.09ZM160.31 20.38V15.28H165.67"
    "V20.38ZM160.31 47.09V23.95H165.67V47.09Z"
)

_TOKEN = re.compile(r"[MLHVQZ]|-?\d*\.?\d+")


def _subtrazados(d: str) -> list[list[tuple]]:
    """Segmentos de un trazado SVG absoluto: ``("M", p)``, ``("L", p)``, ``("Q", c, p)``."""
    tokens = _TOKEN.findall(d)
    salida: list[list[tuple]] = []
    actual: list[tuple] = []
    k, cmd = 0, ""
    x = y = 0.0

    def num() -> float:
        nonlocal k
        k += 1
        return float(tokens[k - 1])

    while k < len(tokens):
        if tokens[k].isalpha():
            cmd = tokens[k]
            k += 1
            if cmd == "Z":
                salida.append(actual)
                actual = []
                continue
        if cmd == "M":
            x, y = num(), num()
            actual = [("M", (x, y))]
            cmd = "L"  # pares siguientes: líneas implícitas
        elif cmd == "L":
            x, y = num(), num()
            actual.append(("L", (x, y)))
        elif cmd == "H":
            x = num()
            actual.append(("L", (x, y)))
        elif cmd == "V":
            y = num()
            actual.append(("L", (x, y)))
        elif cmd == "Q":
            c = (num(), num())
            x, y = num(), num()
            actual.append(("Q", c, (x, y)))
    if actual:
        salida.append(actual)
    return salida


_PALABRA = _subtrazados(PALABRA)


class _Lugar:
    """Lleva coordenadas del SVG (y hacia abajo) al papel (y hacia arriba)."""

    def __init__(self, caja, x: float, y: float, alto: float, giro: float = 0.0) -> None:
        self.x0, self.y0, _w, h = caja
        self.e = alto / h
        self.x, self.y = x, y
        self.c, self.s = math.cos(giro), math.sin(giro)

    def __call__(self, p: tuple[float, float]) -> tuple[float, float]:
        u = (p[0] - self.x0) * self.e
        v = -(p[1] - self.y0) * self.e
        return (self.x + u * self.c - v * self.s, self.y + u * self.s + v * self.c)


def isotipo(c, x: float, y: float, alto: float, tonos=TONOS_CLARO, giro: float = 0.0) -> None:
    """Dibuja el isotipo con la esquina superior izquierda de su caja en ``(x, y)``."""
    lugar = _Lugar(CAJA_ISOTIPO, x, y, alto, giro)
    for puntos, tono in ISOTIPO:
        p = c.beginPath()
        q = [lugar(pt) for pt in puntos]
        p.moveTo(*q[0])
        for pt in q[1:]:
            p.lineTo(*pt)
        p.close()
        color = tonos[tono]
        c.setFillColor(colors.HexColor(color) if isinstance(color, str) else color)
        c.drawPath(p, stroke=0, fill=1)


def logotipo(
    c, x: float, y: float, alto: float, tonos=TONOS_CLARO, tinta: str = TINTA_MARCA
) -> float:
    """Isotipo y palabra "Nervi" con la esquina superior izquierda en ``(x, y)``.
    Devuelve el ancho dibujado."""
    e = alto / CAJA_LOGOTIPO[3]
    isotipo(
        c,
        x + (CAJA_ISOTIPO[0] - CAJA_LOGOTIPO[0]) * e,
        y - CAJA_ISOTIPO[1] * e,
        CAJA_ISOTIPO[3] * e,
        tonos,
    )
    lugar = _Lugar(CAJA_LOGOTIPO, x, y, alto)
    p = c.beginPath()
    for sub in _PALABRA:
        actual = None
        for seg in sub:
            if seg[0] == "M":
                actual = lugar(seg[1])
                p.moveTo(*actual)
            elif seg[0] == "L":
                actual = lugar(seg[1])
                p.lineTo(*actual)
            else:  # cuadrática -> cúbica
                q0, q1, q2 = actual, lugar(seg[1]), lugar(seg[2])
                c1 = (q0[0] + 2 / 3 * (q1[0] - q0[0]), q0[1] + 2 / 3 * (q1[1] - q0[1]))
                c2 = (q2[0] + 2 / 3 * (q1[0] - q2[0]), q2[1] + 2 / 3 * (q1[1] - q2[1]))
                p.curveTo(*c1, *c2, *q2)
                actual = q2
        p.close()
    c.setFillColor(colors.HexColor(tinta))
    c.drawPath(p, stroke=0, fill=1, fillMode=0)
    return CAJA_LOGOTIPO[2] * e


def aclarado(color: str, intensidad: float) -> colors.Color:
    """``color`` mezclado con blanco (``intensidad`` 1: el color, 0: blanco), opaco.
    El patrón de la carátula usa colores opacos aclarados y no transparencias: con
    transparencia se ven las caras del isotipo superpuestas."""
    k = colors.HexColor(color)
    return colors.Color(*(1 - intensidad + intensidad * v for v in (k.red, k.green, k.blue)))


def patron(c, x0: float, y0: float, x1: float, y1: float, paso: float = 57.0) -> None:
    """Isotipos de Nervi en patrón escalonado dentro de ``[x0, x1] × [y0, y1]``
    (puntos). Más presentes arriba a la izquierda y desvaneciéndose hacia abajo y
    a la derecha; muy claros, para gastar poca tinta al imprimir."""
    paso_y, alto = paso * 1.175, paso * 0.725
    diagonal = math.hypot(x1 - x0, y1 - y0)
    fila = 0
    y = y1
    while y > y0:
        x = x0 - paso + (fila % 2) * paso / 2
        while x < x1 + paso:
            d = math.hypot(x - x0, y1 - y) / diagonal
            a = 0.22 * max(0.0, 1 - 1.5 * d) ** 1.5
            if a > 0.01:
                isotipo(c, x, y, alto, tuple(aclarado(t, a) for t in TONOS_CLARO))
            x += paso
        y -= paso_y
        fila += 1


def borde_isotipo(alto: float) -> float:
    """Distancia del borde de la caja del logotipo al borde visible del isotipo."""
    izquierda = min(x for puntos, _ in ISOTIPO for x, _y in puntos)
    return (izquierda - CAJA_LOGOTIPO[0]) * alto / CAJA_LOGOTIPO[3]
