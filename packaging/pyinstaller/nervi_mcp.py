# SPDX-License-Identifier: GPL-3.0-or-later
"""Punto de entrada de ``nervi-mcp`` dentro del instalador (PyInstaller).

Es un ejecutable de consola aparte del de la ventana: la app de IA le habla por la
entrada y salida estándar, que un ejecutable de ventana no tiene en Windows.
"""

import sys

from nervi.ia.servidor import main

if __name__ == "__main__":
    sys.exit(main())
