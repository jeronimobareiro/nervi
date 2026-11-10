# SPDX-License-Identifier: GPL-3.0-or-later
"""Interfaz gráfica de escritorio de Nervi (PySide6).

Se instala con ``pip install nervi[gui]`` y se abre con ``nervi-gui`` o
``python -m nervi.gui [proyecto.nrv]``. La interfaz es una capa delgada: no
calcula ni guarda nada por su cuenta, usa ``nervi`` y ``nervi.formato``.
"""

from .app import main

__all__ = ["main"]
