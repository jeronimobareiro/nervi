# SPDX-License-Identifier: GPL-3.0-or-later
"""Diseño de vigas de hormigón armado según ACI 318-19: flexión (#22) y cortante (#23).

**Experimental.** Implementa métodos de la norma y todavía no fue revisado por un
ingeniero estructural (ver ``AGENTS.md`` y la bitácora). Los resultados no deben
usarse para dimensionar estructuras reales sin verificarlos.

Unidades: MPa y mm en secciones y materiales; kN·m y kN en esfuerzos.

>>> from nervi.design import aci318
>>> mat = aci318.Materiales(fc=28, fy=420)
>>> r = aci318.armadura_flexion(200, b=300, d=500, mat=mat)
>>> round(r.As_req), r.doble, round(r.resistencia.phi, 2)
(1134, False, 0.9)
>>> sec = aci318.SeccionRectangular(b=300, h=550, recubrimiento=40, d_estribo=10)
>>> aci318.elegir_barras(200, sec, mat).descripcion
'3Ø20 + 2Ø12'
>>> aci318.elegir_estribos(250, b=300, d=500, mat=mat, diametros=(10,)).descripcion
'eØ10 c/150 mm (2 ramas)'
"""

from .cortante import (
    PHI_CORTANTE,
    Estribos,
    ResultadoCortante,
    armadura_cortante,
    elegir_estribos,
    factor_tamano,
    separacion_maxima,
)
from .flexion import (
    DisposicionBarras,
    ResistenciaFlexion,
    ResultadoFlexion,
    ancho_necesario,
    armadura_flexion,
    armadura_minima,
    beta1,
    elegir_barras,
    phi_flexion,
    resistencia_flexion,
    separacion_libre_minima,
)
from .materiales import (
    DIAMETROS_COMERCIALES,
    DIAMETROS_ESTRIBO,
    ES,
    Materiales,
    SeccionRectangular,
    area_barra,
)
from .viga import DisenoViga, disenar_viga

__all__ = [
    "DIAMETROS_COMERCIALES",
    "DIAMETROS_ESTRIBO",
    "ES",
    "PHI_CORTANTE",
    "DisenoViga",
    "DisposicionBarras",
    "Estribos",
    "Materiales",
    "ResistenciaFlexion",
    "ResultadoCortante",
    "ResultadoFlexion",
    "SeccionRectangular",
    "ancho_necesario",
    "area_barra",
    "armadura_cortante",
    "armadura_flexion",
    "armadura_minima",
    "beta1",
    "disenar_viga",
    "elegir_barras",
    "elegir_estribos",
    "factor_tamano",
    "phi_flexion",
    "resistencia_flexion",
    "separacion_libre_minima",
    "separacion_maxima",
]
