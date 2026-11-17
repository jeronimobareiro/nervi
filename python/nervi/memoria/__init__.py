# SPDX-License-Identifier: GPL-3.0-or-later
"""Memoria de cálculo en PDF (issue #28).

>>> import nervi
>>> from nervi import memoria
>>> m = nervi.Modelo()
>>> a, b = m.agregar_nudo(0, 0), m.agregar_nudo(5, 0)
>>> viga = m.agregar_barra(a, b, E=2e8, A=0.01, I=1e-4)
>>> m.apoyar(a, rz=False); m.apoyar(b, ux=False, rz=False)
>>> m.carga_uniforme("D", viga, qy=-10)
>>> doc = memoria.memoria_de_calculo(m, datos_proyecto={"Proyecto": "Viga de prueba"})
>>> [s.titulo for s in doc.capitulos][:3]
['Alcance y método', 'Geometría', 'Materiales y secciones']

``doc.guardar_pdf("memoria.pdf")`` escribe el PDF (necesita ReportLab:
``pip install 'nervi[memoria]'``). Los textos salen de una plantilla editable
(``plantilla.toml``). Un módulo de diseño suma su capítulo con
``doc.agregar(Capitulo(...))`` y :func:`tabla_verificaciones`.
"""

from .analisis import CAPITULOS, memoria_de_calculo
from .documento import (
    Capitulo,
    Figura,
    Memoria,
    Parrafo,
    Rotulo,
    Tabla,
    Trazo,
    formatear,
    formatear_factor,
    tabla_verificaciones,
)
from .plantilla import Plantilla

__all__ = [
    "CAPITULOS",
    "Capitulo",
    "Figura",
    "Memoria",
    "Parrafo",
    "Plantilla",
    "Rotulo",
    "Tabla",
    "Trazo",
    "formatear",
    "formatear_factor",
    "memoria_de_calculo",
    "tabla_verificaciones",
]
