# SPDX-License-Identifier: GPL-3.0-or-later
"""Diseño: combinaciones de carga normativas y envolventes de esfuerzos.

**Experimental.** Este módulo implementa métodos de normas y todavía no fue
revisado por un ingeniero estructural (ver ``AGENTS.md`` y la bitácora). Los
resultados no deben usarse para dimensionar estructuras reales sin verificarlos.

>>> import nervi
>>> from nervi import design
>>> m = nervi.Modelo()
>>> a, b = m.agregar_nudo(0, 0), m.agregar_nudo(5, 0)
>>> barra = m.agregar_barra(a, b, E=2e8, A=0.01, I=1e-4)
>>> m.apoyar(a, rz=False); m.apoyar(b, ux=False, rz=False)
>>> m.carga_uniforme("D", barra, qy=-10); m.carga_uniforme("L", barra, qy=-5)
>>> combs = design.generar({"D": "D", "L": "L"}, norma="aci318-19")
>>> [c.nombre for c in combs]
['5.3.1a: 1.4·D', '5.3.1b: 1.2·D + 1.6·L']
>>> res = m.resolver(combinaciones=design.como_diccionario(combs))
>>> env = design.envolvente(res, barra)
>>> float(round(env["M_max"].max(), 3)), env["M_max_comb"][env["M_max"].argmax()]
(62.5, '5.3.1b: 1.2·D + 1.6·L')
"""

from .combinaciones import (
    TIPOS_CARGA,
    Combinacion,
    ModuloExperimentalWarning,
    como_diccionario,
    generar,
    normas_disponibles,
)
from .envolvente import envolvente, envolvente_reacciones

__all__ = [
    "TIPOS_CARGA",
    "Combinacion",
    "ModuloExperimentalWarning",
    "como_diccionario",
    "envolvente",
    "envolvente_reacciones",
    "generar",
    "normas_disponibles",
]
