# SPDX-License-Identifier: GPL-3.0-or-later
"""Hormigón armado según ACI 318-19: vigas (flexión #22, cortante #23) y columnas (#24).

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
>>> col = aci318.SeccionColumna.rectangular(400, 400, 3, 3, 20)
>>> col.descripcion
'8Ø20 (ρ = 1.57 %)'
>>> v = aci318.verificar_columna(col, mat, Pu=1000, Mz=150, My=60)
>>> round(float(v.phiMn[0]), 1), round(float(v.razon[0]), 3)
(166.8, 0.969)
"""

from . import detalle, servicio  # servicio (flechas, fisuración) y detalle de armaduras
from .columna import (
    DIAMETROS_COLUMNA,
    DemandaColumna,
    DisenoColumna,
    MagnificacionEje,
    ResistenciaAxial,
    SeccionColumna,
    VerificacionColumna,
    carga_critica,
    coeficiente_cm,
    diagrama_interaccion,
    disenar_columna,
    elegir_armadura_columna,
    factor_magnificacion,
    limite_esbeltez,
    modulo_hormigon,
    phi_compresion,
    resistencia_axial,
    rigidez_efectiva,
    separacion_libre_minima_columna,
    solicitaciones_columna,
    verificar_columna,
)
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
    "DIAMETROS_COLUMNA",
    "DIAMETROS_COMERCIALES",
    "DIAMETROS_ESTRIBO",
    "ES",
    "PHI_CORTANTE",
    "DemandaColumna",
    "DisenoColumna",
    "DisenoViga",
    "DisposicionBarras",
    "Estribos",
    "MagnificacionEje",
    "Materiales",
    "ResistenciaAxial",
    "ResistenciaFlexion",
    "ResultadoCortante",
    "ResultadoFlexion",
    "SeccionColumna",
    "SeccionRectangular",
    "VerificacionColumna",
    "ancho_necesario",
    "area_barra",
    "armadura_cortante",
    "armadura_flexion",
    "armadura_minima",
    "beta1",
    "carga_critica",
    "coeficiente_cm",
    "detalle",
    "diagrama_interaccion",
    "disenar_columna",
    "disenar_viga",
    "elegir_armadura_columna",
    "elegir_barras",
    "elegir_estribos",
    "factor_magnificacion",
    "factor_tamano",
    "limite_esbeltez",
    "modulo_hormigon",
    "phi_compresion",
    "phi_flexion",
    "resistencia_axial",
    "resistencia_flexion",
    "rigidez_efectiva",
    "separacion_libre_minima",
    "separacion_libre_minima_columna",
    "separacion_maxima",
    "servicio",
    "solicitaciones_columna",
    "verificar_columna",
]
