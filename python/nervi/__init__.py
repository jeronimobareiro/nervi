# SPDX-License-Identifier: GPL-3.0-or-later
"""Nervi: análisis y dimensionamiento estructural de código abierto.

Fase 1: pórtico plano lineal elástico.

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

from ._core import MecanismoError
from .modelo import Modelo, ResultadoCaso, Resultados

__all__ = ["MecanismoError", "Modelo", "ResultadoCaso", "Resultados"]
