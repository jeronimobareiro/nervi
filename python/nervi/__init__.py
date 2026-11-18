# SPDX-License-Identifier: GPL-3.0-or-later
"""Nervi: análisis y dimensionamiento estructural de código abierto.

Fase 1: pórtico plano lineal elástico (``Modelo``). Fase 2a: pórtico espacial
(``Modelo3D``, con secciones habituales en ``nervi.secciones``). Fase 2b:
análisis modal y espectro de respuesta (``Modelo3D.modal``, ``nervi.dinamica``).

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

from . import dinamica, secciones
from ._core import MecanismoError
from .dinamica import ResultadoEspectro3D, ResultadosModal3D
from .modelo import Modelo, ResultadoCaso, Resultados
from .modelo3d import Modelo3D, ResultadoCaso3D, Resultados3D

__all__ = [
    "MecanismoError",
    "Modelo",
    "Modelo3D",
    "ResultadoCaso",
    "ResultadoCaso3D",
    "ResultadoEspectro3D",
    "Resultados",
    "Resultados3D",
    "ResultadosModal3D",
    "dinamica",
    "secciones",
]
