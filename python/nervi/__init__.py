# SPDX-License-Identifier: GPL-3.0-or-later
"""Nervi: análisis y dimensionamiento estructural de código abierto.

Fase 1: pórtico plano lineal elástico (``Modelo``). Fase 2a: pórtico espacial
(``Modelo3D``, con secciones habituales en ``nervi.secciones``).

>>> import nervi
>>> m = nervi.Modelo()
>>> a, b = m.agregar_nudo(0, 0), m.agregar_nudo(3, 0)
>>> barra = m.agregar_barra(a, b, E=2e8, A=0.01, I=1e-4)
>>> m.apoyar(a)
>>> m.carga_nodal("P", b, fy=-10)
>>> r = m.resolver()
>>> float(round(r["P"].desplazamientos[b, 1], 6))
-0.0045
"""

from . import secciones
from ._core import MecanismoError
from .modelo import Modelo, ResultadoCaso, Resultados
from .modelo3d import Modelo3D, ResultadoCaso3D, Resultados3D

__all__ = [
    "MecanismoError",
    "Modelo",
    "Modelo3D",
    "ResultadoCaso",
    "ResultadoCaso3D",
    "Resultados",
    "Resultados3D",
    "secciones",
]
