# SPDX-License-Identifier: GPL-3.0-or-later
"""Servidor MCP ``nervi-mcp``: el agente de IA de la persona consulta Nervi.

Lo lanza la app de IA (Claude Desktop, Claude Code, Gemini CLI u otro cliente MCP)
y le habla por ``stdio``. Tiene dos modos:

* ``nervi-mcp`` sin argumentos: se conecta con la **ventana de Nervi abierta**
  cuando la persona toca "Conectar con mi IA" (:mod:`nervi.ia.canal`). Consulta lo
  que la persona tiene abierto, lee su selección y deja propuestas de cambio que
  ella aplica o descarta en la ventana.
* ``nervi-mcp proyecto.nrv``: consulta un archivo guardado, solo lectura.

Cómo conectarlo: ``docs/agentes-ia.md``. Necesita ``pip install nervi[ia]`` (SDK
oficial de MCP, licencia MIT).
"""

from __future__ import annotations

import argparse
import functools
import inspect
import json
import sys
from collections.abc import Callable

from . import canal
from .herramientas import (
    NOMBRES,
    NOMBRES_VENTANA,
    ErrorConsulta,
    FuenteArchivo,
    FuenteProyecto,
    Herramientas,
)

try:  # SDK de MCP 2.x
    from mcp.server.mcpserver import MCPServer as _Servidor
    from mcp.server.mcpserver.exceptions import ToolError
except ImportError:  # SDK de MCP 1.x
    from mcp.server.fastmcp import FastMCP as _Servidor
    from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations

INSTRUCCIONES = """\
Nervi es un programa de cálculo estructural (pórticos planos, método de rigidez). \
Estas herramientas consultan un proyecto de Nervi y sus resultados.

Reglas:
- Nunca inventes ni estimes un número de resultado. Toda cifra que des tiene que \
salir de una herramienta; decí de cuál, y con qué caso o combinación.
- Los nudos se nombran N1, N2, … y las barras B1, B2, …, como en la interfaz.
- Las unidades son las del modelo (campo "unidades"); no las conviertas sin avisar.
- Los números vienen sin redondear. Al contestar redondeá con criterio, pero no \
cambies el valor.
- El diseño de hormigón es experimental: repetí su aviso cuando lo uses.
- Si algo no se puede calcular, explicá el motivo que da la herramienta; no lo suplas.
- No podés cambiar el proyecto. Con la ventana abierta podés proponer un cambio \
(proponer_modelo): la persona lo revisa y decide si lo aplica. No digas que un \
cambio está hecho hasta que listar_propuestas muestre que ya no está pendiente y \
leer_modelo lo refleje.
- La responsabilidad del cálculo es de la persona profesional que firma.
"""


def _anotaciones(solo_lectura: bool) -> ToolAnnotations:
    return ToolAnnotations.model_validate(
        {
            "readOnlyHint": solo_lectura,
            "destructiveHint": False,
            "idempotentHint": solo_lectura,
            "openWorldHint": False,
        }
    )


def _publicar(nombre: str, ejecutar: Callable[[str, dict], object]):
    """Función con la firma de ``Herramientas.<nombre>`` que pasa la llamada a
    ``ejecutar`` y convierte los errores de consulta en errores de herramienta."""
    original = getattr(Herramientas, nombre)
    firma = inspect.signature(original)
    firma = firma.replace(parameters=list(firma.parameters.values())[1:])  # sin self

    @functools.wraps(original)
    def herramienta(*args, **kwargs):
        argumentos = firma.bind(*args, **kwargs)
        try:
            return ejecutar(nombre, dict(argumentos.arguments))
        except ErrorConsulta as e:
            raise ToolError(str(e)) from None

    del herramienta.__wrapped__
    herramienta.__signature__ = firma
    return herramienta


def crear_servidor(
    fuente: FuenteArchivo | FuenteProyecto | None = None,
    ejecutar: Callable[[str, dict], object] | None = None,
    nombres: tuple[str, ...] | None = None,
) -> _Servidor:
    """Servidor MCP sobre ``fuente`` o, sin fuente, sobre la ventana abierta (cada
    llamada pasa por :func:`nervi.ia.canal.consultar`). ``ejecutar`` y ``nombres``
    sirven para pruebas."""
    if ejecutar is None:
        if fuente is None:
            ejecutar = canal.consultar
            nombres = nombres or NOMBRES + NOMBRES_VENTANA
        else:
            h = Herramientas(fuente)
            ejecutar = h.ejecutar
            nombres = nombres or h.nombres
    nombres = nombres or NOMBRES
    servidor = _Servidor(name="nervi", instructions=INSTRUCCIONES)
    for nombre in nombres:
        funcion = getattr(Herramientas, nombre)
        servidor.add_tool(
            _publicar(nombre, ejecutar),
            name=nombre,
            description=" ".join(funcion.__doc__.split()),
            annotations=_anotaciones(nombre != "proponer_modelo"),
        )

    def leer(nombre: str) -> str:
        try:
            return json.dumps(ejecutar(nombre, {}), ensure_ascii=False)
        except ErrorConsulta as e:
            raise ToolError(str(e)) from None

    @servidor.resource(
        "nervi://modelo",
        name="modelo",
        description="modelo.json del proyecto (nudos, barras, apoyos, cargas, casos).",
        mime_type="application/json",
    )
    def modelo() -> str:
        return leer("leer_modelo")

    if fuente is not None:  # por el canal serían varios MB en cada pedido

        @servidor.resource(
            "nervi://resultados",
            name="resultados",
            description="Todos los resultados sin redondear (formato nervi-resultados v1).",
            mime_type="application/json",
        )
        def resultados() -> str:
            h = Herramientas(fuente)
            try:
                return json.dumps(h.resultados_completos(), ensure_ascii=False)
            except ErrorConsulta as e:
                raise ToolError(str(e)) from None

    return servidor


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada de ``nervi-mcp``."""
    parser = argparse.ArgumentParser(
        prog="nervi-mcp",
        description=(
            "Servidor MCP para que un agente de IA consulte Nervi. Sin argumentos se "
            "conecta con la ventana abierta («Conectar con mi IA»); con un .nrv, "
            "consulta ese archivo, solo lectura."
        ),
    )
    parser.add_argument("proyecto", nargs="?", help="archivo .nrv a consultar (solo lectura)")
    args = parser.parse_args(argv)
    if args.proyecto is None:
        crear_servidor().run("stdio")
        return 0
    fuente = FuenteArchivo(args.proyecto)
    try:
        fuente.proyecto()
    except ErrorConsulta as e:
        print(f"nervi-mcp: {e}", file=sys.stderr)
        return 2
    crear_servidor(fuente).run("stdio")
    return 0


if __name__ == "__main__":
    sys.exit(main())
