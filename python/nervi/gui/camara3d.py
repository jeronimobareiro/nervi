# SPDX-License-Identifier: GPL-3.0-or-later
"""Cámara del visor: giro tipo plato con Z siempre arriba (sin VTK ni Qt).

El visor único (vista de frente y vista 3D, ver ``docs/diseno-interfaz.md`` §Visor)
mira el modelo con esta cámara:

- **acimut** (grados): giro alrededor de Z. Con 0 se mira hacia +Y, con X a la
  derecha: la vista de frente del pórtico plano, igual que la vista 2D.
- **elevación** (grados, de −90 a 90): cuánto se mira desde arriba. Con 90, en planta.
- **centro**: punto del modelo que cae en el centro del lienzo.
- **escala**: píxeles de pantalla por unidad de longitud del modelo (como la vista 2D).

El giro no tiene rolido: la Z del modelo queda siempre vertical en pantalla, así el
modelo nunca se tumba. Girar, desplazar y acercar dejan fijo en la pantalla el punto
que corresponde (el centro de giro o el punto bajo el cursor).

Solo cambia cómo se mira el modelo y no recorre sus elementos, por eso queda en
Python (regla de rendimiento de ``AGENTS.md``).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

import numpy as np

#: Grados de giro por píxel arrastrado.
GRADOS_POR_PIXEL = 0.4
#: Ángulo de visión vertical de la perspectiva, en grados.
ANGULO_PERSPECTIVA = 30.0
#: Vistas con nombre: (acimut, elevación).
VISTAS = {
    "frente": (0.0, 0.0),
    "planta": (0.0, 90.0),
    "lateral": (90.0, 0.0),
    "isometrica": (-32.0, 24.0),
}
#: Vista que da cada extremo de eje de la brújula: se mira desde ese lado.
EXTREMOS = {
    "+X": (90.0, 0.0),
    "-X": (-90.0, 0.0),
    "+Y": (180.0, 0.0),
    "-Y": (0.0, 0.0),
    "+Z": (0.0, 90.0),
    "-Z": (0.0, -90.0),
}


@dataclass(frozen=True)
class Camara3D:
    acimut: float
    elevacion: float
    centro: tuple[float, float, float]
    escala: float
    perspectiva: bool = False

    # --- Ejes de la pantalla en coordenadas del modelo ---------------------------------
    def ejes(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """``(derecha, arriba, hacia_quien_mira)``, unitarios y ortogonales."""
        a, e = math.radians(self.acimut), math.radians(self.elevacion)
        ca, sa, ce, se = math.cos(a), math.sin(a), math.cos(e), math.sin(e)
        derecha = np.array([ca, sa, 0.0])
        arriba = np.array([-sa * se, ca * se, ce])
        return derecha, arriba, np.cross(derecha, arriba)

    def a_pantalla(self, punto, ancho: float, alto: float) -> tuple[float, float]:
        """Punto del modelo -> píxel del lienzo (origen arriba a la izquierda), con la
        proyección paralela (la perspectiva coincide con ella en el plano del centro)."""
        d, u, _ = self.ejes()
        v = np.asarray(punto, float) - np.asarray(self.centro)
        return (ancho / 2 + self.escala * float(v @ d), alto / 2 - self.escala * float(v @ u))

    def en_plano(self, x: float, y: float, ancho: float, alto: float) -> np.ndarray:
        """Punto del plano que pasa por el centro, perpendicular a la mirada, bajo el
        píxel ``(x, y)``."""
        d, u, _ = self.ejes()
        return (
            np.asarray(self.centro, float)
            + d * (x - ancho / 2) / self.escala
            - u * (y - alto / 2) / self.escala
        )

    # --- Navegación ------------------------------------------------------------------
    def girar(self, dx: float, dy: float, pivote=None) -> Camara3D:
        """Gira ``dx``, ``dy`` píxeles arrastrados alrededor de ``pivote`` (o del centro).

        Arrastrar a la derecha gira el modelo hacia la derecha; hacia abajo, lo muestra
        más desde arriba. El pivote queda en el mismo lugar de la pantalla."""
        acimut = _normalizar(self.acimut - dx * GRADOS_POR_PIXEL)
        elevacion = min(90.0, max(-90.0, self.elevacion + dy * GRADOS_POR_PIXEL))
        return self.orientar(acimut, elevacion, pivote)

    def orientar(self, acimut: float, elevacion: float, pivote=None) -> Camara3D:
        """La misma cámara mirando con otro acimut y elevación, con ``pivote`` fijo."""
        nueva = replace(self, acimut=acimut, elevacion=elevacion)
        if pivote is None:
            return nueva
        p = np.asarray(pivote, float)
        d, u, n = self.ejes()
        v = p - np.asarray(self.centro)
        a, b, k = float(v @ d), float(v @ u), float(v @ n)
        d2, u2, n2 = nueva.ejes()
        return replace(nueva, centro=tuple(p - a * d2 - b * u2 - k * n2))

    def desplazar(self, dx: float, dy: float) -> Camara3D:
        """Mueve la vista ``dx``, ``dy`` píxeles: el modelo sigue al mouse."""
        d, u, _ = self.ejes()
        c = np.asarray(self.centro) - d * dx / self.escala + u * dy / self.escala
        return replace(self, centro=tuple(c))

    def acercar(self, factor: float, x: float, y: float, ancho: float, alto: float) -> Camara3D:
        """Multiplica la escala por ``factor`` dejando fijo el punto bajo ``(x, y)``."""
        p = self.en_plano(x, y, ancho, alto)
        nueva = replace(self, escala=self.escala * factor)
        d, u, _ = nueva.ejes()
        c = p - d * (x - ancho / 2) / nueva.escala + u * (y - alto / 2) / nueva.escala
        return replace(nueva, centro=tuple(c))

    # --- Paso a otras formas de ver ---------------------------------------------------
    @classmethod
    def de_frente(cls, escala: float, cx: float, cy: float) -> Camara3D:
        """La cámara que muestra lo mismo que la vista 2D: ``(x, y)`` del pórtico plano
        es ``(x, 0, y)`` (``escena3d``)."""
        return cls(0.0, 0.0, (cx, 0.0, cy), escala)

    def es_frente(self, tolerancia: float = 1e-6) -> bool:
        return abs(_normalizar(self.acimut)) < tolerancia and abs(self.elevacion) < tolerancia

    def a_vtk(self, alto: float) -> dict:
        """Parámetros de la cámara de VTK para un lienzo de ``alto`` píxeles."""
        _, u, n = self.ejes()
        medio_alto = alto / (2 * self.escala)  # mitad del alto visible, en unidades
        distancia = medio_alto / math.tan(math.radians(ANGULO_PERSPECTIVA / 2))
        c = np.asarray(self.centro, float)
        return {
            "focal_point": tuple(c),
            "position": tuple(c + n * distancia),
            "up": tuple(u),
            "parallel_scale": medio_alto,
            "view_angle": ANGULO_PERSPECTIVA,
            "parallel_projection": not self.perspectiva,
        }


def _normalizar(angulo: float) -> float:
    """Ángulo en (−180, 180]."""
    a = math.fmod(angulo, 360.0)
    if a <= -180.0:
        a += 360.0
    elif a > 180.0:
        a -= 360.0
    return a


def encuadre(
    puntos,
    ancho: float,
    alto: float,
    vista: str | tuple[float, float] = "isometrica",
    margen: float = 0.12,
    perspectiva: bool = False,
) -> Camara3D:
    """Cámara que muestra todos los ``puntos`` (``(n, 3)``) desde ``vista`` (nombre de
    :data:`VISTAS` o ``(acimut, elevación)``), con ``margen`` del lado del lienzo."""
    acimut, elevacion = VISTAS[vista] if isinstance(vista, str) else vista
    base = Camara3D(acimut, elevacion, (0.0, 0.0, 0.0), 1.0, perspectiva)
    pts = np.atleast_2d(np.asarray(puntos, float))
    if pts.size == 0:
        return base
    d, u, _ = base.ejes()
    px, py = pts @ d, pts @ u
    medio = (pts.min(axis=0) + pts.max(axis=0)) / 2
    # Centro: el del rectángulo que ocupan en pantalla, a la profundidad del medio.
    cx, cy = (px.min() + px.max()) / 2, (py.min() + py.max()) / 2
    centro = medio + d * (cx - medio @ d) + u * (cy - medio @ u)
    tam = max(float(np.ptp(pts, axis=0).max()), 1e-9)
    w = max(float(np.ptp(px)), 0.3 * tam)
    h = max(float(np.ptp(py)), 0.3 * tam)
    util = 1 - 2 * margen
    escala = min(ancho * util / w, alto * util / h)
    return replace(base, centro=tuple(centro), escala=escala)


def interpolar(a: Camara3D, b: Camara3D, t: float) -> Camara3D:
    """Cámara intermedia para la transición de ``a`` a ``b`` (``t`` de 0 a 1): el
    acimut por el camino más corto y la escala en proporción geométrica."""
    s = t * t * (3 - 2 * t)  # suave al empezar y al terminar
    da = _normalizar(b.acimut - a.acimut)
    centro = np.asarray(a.centro) + (np.asarray(b.centro) - np.asarray(a.centro)) * s
    return Camara3D(
        _normalizar(a.acimut + da * s),
        a.elevacion + (b.elevacion - a.elevacion) * s,
        tuple(centro),
        a.escala * (b.escala / a.escala) ** s,
        b.perspectiva if t >= 1 else a.perspectiva,
    )
