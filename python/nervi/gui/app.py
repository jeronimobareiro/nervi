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


def comprobar_visor3d(captura: str | None = None) -> int:
    """Prueba del visor 3D para el ejecutable empaquetado (``--comprobar-visor3d``).

    Comprueba que PyVista, pyvistaqt y VTK estén incluidos y, con ``captura``,
    renderiza el pórtico de ejemplo a esa imagen sin pantalla. Devuelve 0 si
    todo anda (el ejecutable de Windows no tiene consola: se mira el código).
    """
    from . import vista3d

    motivo = vista3d.disponible()
    if motivo is not None:
        print(motivo, file=sys.stderr)
        return 1
    import vtkmodules.vtkRenderingOpenGL2  # noqa: F401  (el render real de VTK)

    if captura:
        from pathlib import Path

        sesion = Sesion(documento_ejemplo())
        sesion.calcular()
        ruta = vista3d.capturar(
            sesion.modelo, captura, sesion.resultado(), sesion.indices, "M", sesion.combinacion
        )
        if not Path(ruta).is_file() or Path(ruta).stat().st_size == 0:
            print(f"no se pudo escribir {ruta}", file=sys.stderr)
            return 1
    print("visor 3D: ok")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv if argv is None else argv
    if "--comprobar-visor3d" in argv:
        resto = argv[argv.index("--comprobar-visor3d") + 1 :]
        return comprobar_visor3d(resto[0] if resto else None)
    app = QApplication.instance() or QApplication(argv)
    app.setApplicationName("Nervi")
    app.setOrganizationName("Nervi")
    app.setWindowIcon(icono())
    app.setStyle("Fusion")
    ventana = crear_ventana(argv[1:])
    ventana.show()
    return app.exec()
