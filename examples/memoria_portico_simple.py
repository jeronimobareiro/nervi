# SPDX-License-Identifier: GPL-3.0-or-later
"""Memoria de cálculo en PDF del pórtico de ``portico_simple.py`` (issue #28).

Ejecutar con: python examples/memoria_portico_simple.py [salida.pdf]
Necesita ReportLab: pip install 'nervi[memoria]'.
"""

import sys

from portico_simple import COMBINACIONES, armar_modelo

from nervi.memoria import memoria_de_calculo

m, _viga, _cabeza = armar_modelo()
res = m.resolver(combinaciones=COMBINACIONES)
memoria = memoria_de_calculo(
    m,
    res,
    datos_proyecto={
        "Proyecto": "Pórtico de una crujía (ejemplo)",
        "Ubicación": "Asunción, Paraguay",
        "Comitente": "Ejemplo",
        "Autor": "Ejemplo de Nervi",
        "Revisión": "0",
    },
    fuerza="kN",
    longitud="m",
)
ruta = memoria.guardar_pdf(sys.argv[1] if len(sys.argv) > 1 else "memoria_portico_simple.pdf")
print(f"Memoria de cálculo guardada en {ruta}")
