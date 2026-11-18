# SPDX-License-Identifier: GPL-3.0-or-later
"""Diseño: combinaciones de carga normativas y envolventes de esfuerzos.

**Experimental.** Este módulo implementa métodos de normas y todavía no fue
revisado por un ingeniero estructural (ver ``AGENTS.md`` y la bitácora). Los
resultados no deben usarse para dimensionar estructuras reales sin verificarlos.

El diseño de hormigón armado según ACI 318-19 está en :mod:`nervi.design.aci318`:
vigas (flexión y cortante) y columnas (flexocompresión biaxial y esbeltez). El diseño
de todas las barras de un proyecto (lo que usa la interfaz) está en
:mod:`nervi.design.proyecto`.

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

from . import (
    aci318,  # hormigón armado: vigas (#22, #23) y columnas (#24)
    proyecto,  # diseño de todo el pórtico (etapa Diseño de la interfaz)
)
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
    "aci318",
    "como_diccionario",
    "envolvente",
    "envolvente_reacciones",
    "generar",
    "normas_disponibles",
    "proyecto",
]
