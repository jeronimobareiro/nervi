# SPDX-License-Identifier: GPL-3.0-or-later
# Receta de PyInstaller para los instaladores: dos ejecutables en una misma carpeta.
#
# - Nervi (ventana): la interfaz de escritorio, con el visor 3D si PyVista está instalado.
# - nervi-mcp (consola): el servidor MCP para la app de IA de la persona
#   (docs/agentes-ia.md). Comparte bibliotecas con Nervi, así que suma poco.
#
# Uso: pyinstaller --noconfirm packaging/pyinstaller/nervi.spec
# Variable opcional NERVI_ICONO: ruta del .ico (Windows).
import importlib.util
import os

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

AQUI = os.path.dirname(os.path.abspath(SPEC))  # noqa: F821 (lo define PyInstaller)
ICONO = os.environ.get("NERVI_ICONO") or None

datos = collect_data_files("nervi")
if importlib.util.find_spec("pyvista") is not None:
    datos += collect_data_files("pyvista")
ocultos = ["nervi.memoria.pdf"]
# El SDK de MCP carga partes de sí mismo por nombre; se incluye entero salvo su
# línea de comandos (necesita typer, que no se usa).
ocultos_mcp = collect_submodules("mcp", filter=lambda n: not n.startswith("mcp.cli")) + [
    "nervi.ia.servidor"
]

ventana = Analysis(  # noqa: F821
    [os.path.join(AQUI, "nervi_gui.py")], datas=datos, hiddenimports=ocultos
)
consola = Analysis(  # noqa: F821
    [os.path.join(AQUI, "nervi_mcp.py")],
    datas=collect_data_files("mcp"),
    hiddenimports=ocultos_mcp,
)

exe_ventana = EXE(  # noqa: F821
    PYZ(ventana.pure),  # noqa: F821
    ventana.scripts,
    [],
    exclude_binaries=True,
    name="Nervi",
    console=False,
    icon=ICONO,
)
exe_consola = EXE(  # noqa: F821
    PYZ(consola.pure),  # noqa: F821
    consola.scripts,
    [],
    exclude_binaries=True,
    name="nervi-mcp",
    console=True,
    icon=ICONO,
)
COLLECT(  # noqa: F821
    exe_ventana,
    ventana.binaries,
    ventana.datas,
    exe_consola,
    consola.binaries,
    consola.datas,
    name="Nervi",
)
