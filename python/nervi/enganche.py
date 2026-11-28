# SPDX-License-Identifier: GPL-3.0-or-later
"""Enganche de puntos para dibujar en planta con el mouse.

El cálculo va en Rust (``nervi_core::enganche``: método, fuentes y orden de
prioridad en su documentación, adaptado del ``Snapper`` de FreeCAD Draft). Este
módulo arma la geometría de una planta y traduce el resultado.

>>> idx = IndiceEnganche([(0.0, 0.0)], [((0.0, 0.0), (6.0, 0.0))])
>>> e = idx.enganchar(3.05, 0.1, radio=0.3)
>>> e.tipo, e.punto
('medio', (3.0, 0.0))
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

import numpy as np

from . import _core

__all__ = ["TIPOS", "Enganche", "GeometriaPlanta", "IndiceEnganche", "geometria_planta"]

#: Tipos de enganche, de mayor a menor prioridad, con su nombre para la interfaz.
TIPOS = {
    "punto": "Punto",
    "extremo": "Extremo",
    "cruce": "Cruce",
    "medio": "Medio",
    "perpendicular": "Perpendicular",
    "cerca": "Sobre",
    "cruce_guias": "Cruce de guías",
    "polar": "Polar",
    "prolongacion": "Prolongación",
    "grilla": "Grilla",
    "libre": "",
}

Punto = tuple[float, float]


@dataclass(frozen=True)
class Enganche:
    """Resultado de :meth:`IndiceEnganche.enganchar`."""

    punto: Punto
    tipo: str
    #: Índice del punto (tipo ``"punto"``) o del segmento enganchado.
    elemento: int | None = None
    #: Segundo segmento de un cruce.
    otro: int | None = None
    #: Guía a dibujar: de dónde sale la línea polar o la prolongación hasta el punto.
    guia: tuple[Punto, Punto] | None = None


class IndiceEnganche:
    """Índice espacial de puntos sueltos y segmentos en planta."""

    def __init__(
        self, puntos: Iterable[Sequence[float]], segmentos: Iterable[Sequence[Sequence[float]]]
    ) -> None:
        p = np.asarray(list(puntos), dtype=float).reshape(-1, 2)
        s = np.asarray([(a[0], a[1], b[0], b[1]) for a, b in segmentos], dtype=float).reshape(-1, 4)
        self._indice = _core.IndiceEnganche(p, s)

    @property
    def cantidad(self) -> tuple[int, int]:
        """Cantidad de puntos y de segmentos."""
        return self._indice.cantidad

    def enganchar(
        self,
        x: float,
        y: float,
        radio: float,
        *,
        anterior: Punto | None = None,
        puntos: bool = True,
        extremos: bool = True,
        medios: bool = True,
        cruces: bool = True,
        perpendicular: bool = True,
        cerca: bool = True,
        paso_polar: float = 90.0,
        orto: bool = False,
        recientes: Sequence[int] = (),
        paso_grilla: float = 0.0,
        recorrer_todo: bool = False,
    ) -> Enganche:
        """Engancha el cursor ``(x, y)`` (unidades del modelo).

        ``radio`` es la tolerancia de captura en unidades del modelo (los píxeles de
        tolerancia divididos por la escala de la vista). ``anterior`` es el punto
        anterior del trazo, para las líneas polares cada ``paso_polar`` grados, la
        perpendicular y ``orto``. ``recientes`` son segmentos cuya prolongación sirve
        de guía. ``paso_grilla`` 0 apaga la grilla. ``recorrer_todo`` no usa el
        índice (para comprobarlo).
        """
        d = self._indice.enganchar(
            float(x),
            float(y),
            float(radio),
            anterior=None if anterior is None else (float(anterior[0]), float(anterior[1])),
            puntos=puntos,
            extremos=extremos,
            medios=medios,
            cruces=cruces,
            perpendicular=perpendicular,
            cerca=cerca,
            paso_polar=float(paso_polar),
            orto=orto,
            recientes=[int(k) for k in recientes],
            paso_grilla=float(paso_grilla),
            recorrer_todo=recorrer_todo,
        )
        return Enganche(d["punto"], d["tipo"], d["elemento"], d["otro"], d["guia"])


@dataclass
class GeometriaPlanta:
    """Lo enganchable de una planta y de qué elemento sale cada punto y segmento."""

    indice: IndiceEnganche
    #: ``(lista, id)`` de cada punto del índice.
    origen_puntos: list[tuple[str, int]] = field(default_factory=list)
    #: ``(lista, id)`` de cada segmento del índice.
    origen_segmentos: list[tuple[str, int]] = field(default_factory=list)

    def origen(self, e: Enganche) -> tuple[str, int] | None:
        """El elemento del modelo al que se enganchó, o ``None``."""
        if e.elemento is None:
            return None
        if e.tipo == "punto":
            return self.origen_puntos[e.elemento]
        if e.tipo in ("polar", "grilla", "libre"):
            return None
        return self.origen_segmentos[e.elemento]


def geometria_planta(mf, piso: int | None, ejes: bool = True) -> GeometriaPlanta:
    """Geometría enganchable de la planta ``piso`` de ``mf`` (un
    :class:`nervi.fisico.ModeloFisico`): columnas como puntos; vigas, muros y bordes de
    losas como segmentos por su eje; y los ejes de replanteo si ``ejes``."""
    puntos: list[Punto] = []
    segmentos: list[tuple[Punto, Punto]] = []
    o_p: list[tuple[str, int]] = []
    o_s: list[tuple[str, int]] = []
    if ejes:
        for e in mf.lista("ejes"):
            segmentos.append((tuple(e["p1"]), tuple(e["p2"])))
            o_s.append(("ejes", e["id"]))
    if piso is not None:
        en = mf.en_piso(piso)
        for c in en["columnas"]:
            puntos.append(tuple(c["punto"]))
            o_p.append(("columnas", c["id"]))
        for lista in ("vigas", "muros"):
            for el in en[lista]:
                segmentos.append((tuple(el["p1"]), tuple(el["p2"])))
                o_s.append((lista, el["id"]))
        for losa in en["losas"]:
            c = [tuple(q) for q in losa["contorno"]]
            for k in range(len(c)):
                segmentos.append((c[k], c[(k + 1) % len(c)]))
                o_s.append(("losas", losa["id"]))
    return GeometriaPlanta(IndiceEnganche(puntos, segmentos), o_p, o_s)
