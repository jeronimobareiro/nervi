# SPDX-License-Identifier: GPL-3.0-or-later
"""Arranque de la aplicación de escritorio."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from .sesion import Sesion, documento_ejemplo
from .ventana import Ventana, icono


def crear_ventana(argumentos: list[str]) -> Ventana:
    """Abre el proyecto indicado en la línea de comandos, o el ejemplo si no hay ninguno."""
    archivos = [a for a in argumentos if not a.startswith("-")]
    ventana = Ventana(Sesion(documento_ejemplo()))
    if archivos:
        ventana.abrir(archivos[0])
    return ventana


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv if argv is None else argv
    app = QApplication.instance() or QApplication(argv)
    app.setApplicationName("Nervi")
    app.setOrganizationName("Nervi")
    app.setWindowIcon(icono())
    app.setStyle("Fusion")
    ventana = crear_ventana(argv[1:])
    ventana.show()
    return app.exec()
