# SPDX-License-Identifier: GPL-3.0-or-later
"""Figuras de la memoria: geometría, diagramas N/V/M y deformada.

Todo se calcula en coordenadas del modelo; el renderizador solo escala y dibuja.
Se siguen las convenciones de dibujo de la interfaz (``gui/vista2d.py``): el
momento se dibuja del lado traccionado (``-y`` local) y el axil y el cortante
positivos del lado ``+y`` local.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

from ..modelo import ResultadoCaso
from .documento import Figura, Rotulo, Trazo

#: Largo del mayor valor de un diagrama, como fracción del tamaño de la estructura.
FRACCION_DIAGRAMA = 0.15
#: Desplazamiento máximo de la deformada, como fracción del tamaño de la estructura.
FRACCION_DEFORMADA = 0.10


class Geometria:
    """Coordenadas y barras del modelo, con los vectores locales de cada barra."""

    def __init__(self, arreglos: dict[str, np.ndarray]) -> None:
        self.coords = arreglos["coords"]
        self.conect = arreglos["conectividad"]
        self.restricciones = arreglos["restricciones"]
        self.resortes = arreglos["resortes"]
        self.liberaciones = arreglos["liberaciones"]
        dif = self.coords[self.conect[:, 1]] - self.coords[self.conect[:, 0]]
        self.longitudes = np.hypot(dif[:, 0], dif[:, 1])
        self.ex = dif / np.maximum(self.longitudes, 1e-12)[:, None]
        self.ey = np.column_stack([-self.ex[:, 1], self.ex[:, 0]])
        xmin, ymin = self.coords.min(axis=0)
        xmax, ymax = self.coords.max(axis=0)
        self.tam = float(max(xmax - xmin, ymax - ymin, 1e-9))

    def trazos_estructura(self, estilo: str = "estructura") -> list[Trazo]:
        trazos = [Trazo(self.coords[[i, j]], estilo) for i, j in self.conect]  # barras
        if estilo == "estructura":
            trazos += self.trazos_apoyos() + self.trazos_articulaciones()
        return trazos

    def trazos_apoyos(self) -> list[Trazo]:
        """Empotramiento: línea con rayado; articulación fija: triángulo;
        rodillo: triángulo con línea; resorte: zigzag."""
        trazos: list[Trazo] = []
        s = 0.035 * self.tam
        for k, (rx, ry, rz) in enumerate(self.restricciones.astype(bool)):
            x, y = self.coords[k]
            if rx and ry and rz:
                trazos.append(Trazo(np.array([[x - s, y], [x + s, y]]), "apoyo"))
                for t in np.linspace(-s, s, 5):
                    trazos.append(
                        Trazo(np.array([[x + t, y], [x + t - 0.5 * s, y - 0.5 * s]]), "apoyo")
                    )
            elif rx or ry:
                # Triángulo bajo el nudo (o al costado si solo restringe X).
                if ry:
                    tri = np.array([[x, y], [x - 0.8 * s, y - 1.2 * s], [x + 0.8 * s, y - 1.2 * s]])
                    base = np.array([[x - s, y - 1.5 * s], [x + s, y - 1.5 * s]])
                else:
                    tri = np.array([[x, y], [x - 1.2 * s, y - 0.8 * s], [x - 1.2 * s, y + 0.8 * s]])
                    base = np.array([[x - 1.5 * s, y - s], [x - 1.5 * s, y + s]])
                trazos.append(Trazo(tri, "apoyo", cerrado=True))
                if not (rx and ry):
                    trazos.append(Trazo(base, "apoyo"))
            elif rz:
                trazos.append(Trazo(_cuadrado(x, y, 0.5 * s), "apoyo", cerrado=True))
        for k, (kx, ky, kr) in enumerate(self.resortes):
            x, y = self.coords[k]
            if ky > 0:
                zig = [[x, y]] + [
                    [x + (0.4 * s if n % 2 else -0.4 * s), y - (n + 1) * 0.3 * s] for n in range(5)
                ]
                zig.append([x, y - 1.8 * s])
                trazos.append(Trazo(np.array(zig), "apoyo"))
            if kx > 0:
                zig = [[x, y]] + [
                    [x - (n + 1) * 0.3 * s, y + (0.4 * s if n % 2 else -0.4 * s)] for n in range(5)
                ]
                zig.append([x - 1.8 * s, y])
                trazos.append(Trazo(np.array(zig), "apoyo"))
            if kr > 0:
                ang = np.linspace(0, 1.5 * np.pi, 16)
                r = 0.6 * s
                trazos.append(
                    Trazo(np.column_stack([x + r * np.cos(ang), y + r * np.sin(ang)]), "apoyo")
                )
        return trazos

    def trazos_articulaciones(self) -> list[Trazo]:
        """Círculo chico cerca del extremo con el momento liberado."""
        trazos = []
        r = 0.012 * self.tam
        for b, lib in enumerate(self.liberaciones.astype(bool)):
            i, j = self.conect[b]
            for extremo, nudo, signo in ((2, i, 1.0), (5, j, -1.0)):
                if lib[extremo]:
                    c = self.coords[nudo] + signo * self.ex[b] * 2.0 * r
                    ang = np.linspace(0, 2 * np.pi, 17)
                    trazos.append(
                        Trazo(
                            np.column_stack([c[0] + r * np.cos(ang), c[1] + r * np.sin(ang)]),
                            "estructura",
                            cerrado=True,
                        )
                    )
        return trazos


def _cuadrado(x: float, y: float, s: float) -> np.ndarray:
    return np.array([[x - s, y - s], [x + s, y - s], [x + s, y + s], [x - s, y + s]])


def figura_geometria(
    geo: Geometria, nombre_nudo: Callable[[int], str], nombre_barra: Callable[[int], str]
) -> Figura:
    """Estructura con apoyos y la numeración de nudos y barras."""
    fig = Figura("Geometría, apoyos y numeración", geo.trazos_estructura())
    d = 0.03 * geo.tam
    for k, (x, y) in enumerate(geo.coords):
        fig.rotulos.append(Rotulo(x + 0.7 * d, y + 0.7 * d, nombre_nudo(k), "nudo"))
    for b, (i, j) in enumerate(geo.conect):
        medio = 0.5 * (geo.coords[i] + geo.coords[j]) + geo.ey[b] * d
        fig.rotulos.append(Rotulo(medio[0], medio[1], nombre_barra(b), "barra"))
    return fig


def figura_diagrama(
    geo: Geometria,
    res: ResultadoCaso,
    clave: str,
    titulo: str,
    formato: Callable[[float], str],
    grupo: str = "",
) -> Figura:
    """Diagrama ``N``, ``V`` o ``M`` de un caso o combinación, con los valores
    en los extremos de cada barra y en sus máximos y mínimos."""
    fig = Figura(titulo, geo.trazos_estructura("tenue"), grupo=grupo)
    diags = [res.diagrama(b) for b in range(len(geo.conect))]
    maximo = max((float(np.abs(d[clave]).max()) for d in diags if d[clave].size), default=0.0)
    if maximo <= 1e-9 * max(1.0, maximo):
        fig.titulo += " (nulo)"
        return fig
    largo = FRACCION_DIAGRAMA * geo.tam / maximo
    lado = -1.0 if clave == "M" else 1.0
    for b, d in enumerate(diags):
        if not d["x"].size:
            continue
        pi = geo.coords[geo.conect[b, 0]]
        pj = geo.coords[geo.conect[b, 1]]
        xs = d["x"] / max(float(d["x"][-1]), 1e-12) * geo.longitudes[b]
        vals = d[clave]
        for signo, estilo in ((1.0, "positivo"), (-1.0, "negativo")):
            parte = np.where(signo * vals > 0, vals, 0.0)
            if not np.any(parte):
                continue
            pts = pi + np.outer(xs, geo.ex[b]) + np.outer(lado * parte * largo, geo.ey[b])
            fig.trazos.append(Trazo(np.vstack([pi, pts, pj]), estilo, cerrado=True, relleno=True))
        indices = {0, len(vals) - 1, int(np.argmax(vals)), int(np.argmin(vals))}
        ya: list[float] = []
        for idx in sorted(indices):
            v = float(vals[idx])
            if abs(v) < 0.02 * maximo:
                continue
            # No repetir el mismo valor en el mismo lugar (estaciones dobles en saltos).
            if any(abs(xs[idx] - x0) < 0.08 * geo.longitudes[b] for x0 in ya):
                continue
            ya.append(float(xs[idx]))
            separacion = lado * v * largo + lado * np.copysign(0.035 * geo.tam, v)
            p = pi + geo.ex[b] * xs[idx] + geo.ey[b] * separacion
            fig.rotulos.append(Rotulo(float(p[0]), float(p[1]), formato(v), "valor"))
    return fig


def figura_deformada(
    geo: Geometria,
    res: ResultadoCaso,
    titulo: str,
    formato: Callable[[float], str],
    grupo: str = "",
) -> Figura:
    """Deformada amplificada, con el factor de amplificación en el título."""
    fig = Figura(titulo, geo.trazos_estructura("tenue"), grupo=grupo)
    diags = [res.diagrama(b) for b in range(len(geo.conect))]
    maximo = max((float(np.hypot(d["u"], d["v"]).max()) for d in diags if d["u"].size), default=0.0)
    if maximo <= 1e-15:
        fig.titulo += " (nula)"
        return fig
    amplif = FRACCION_DEFORMADA * geo.tam / maximo
    for b, d in enumerate(diags):
        pi = geo.coords[geo.conect[b, 0]]
        xs = d["x"] / max(float(d["x"][-1]), 1e-12) * geo.longitudes[b]
        pts = pi + np.outer(xs + d["u"] * amplif, geo.ex[b]) + np.outer(d["v"] * amplif, geo.ey[b])
        fig.trazos.append(Trazo(pts, "deformada"))
    fig.titulo += f" (×{formato(amplif)})"
    return fig
