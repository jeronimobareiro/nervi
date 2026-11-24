# SPDX-License-Identifier: GPL-3.0-or-later
"""Servidor MCP ``nervi-mcp``: el agente de IA de la persona consulta un proyecto.

Publica las consultas de :mod:`nervi.ia.herramientas` como herramientas MCP de solo
lectura sobre un ``.nrv`` en disco. El agente (Claude Desktop, Claude Code, ChatGPT,
Gemini u otro cliente MCP) lo lanza por ``stdio``::

    nervi-mcp ruta/al/proyecto.nrv

Nada de lo que publica cambia el archivo. Cómo conectarlo: ``docs/agentes-ia.md``.
Necesita ``pip install nervi[ia]`` (SDK oficial de MCP, licencia MIT).
"""

from __future__ import annotations

import argparse
import functools
import json
import sys

from .herramientas import NOMBRES, ErrorConsulta, FuenteArchivo, FuenteProyecto, Herramientas

try:  # SDK de MCP 2.x
    from mcp.server.mcpserver import MCPServer as _Servidor
    from mcp.server.mcpserver.exceptions import ToolError
except ImportError:  # SDK de MCP 1.x
    from mcp.server.fastmcp import FastMCP as _Servidor
    from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations

INSTRUCCIONES = """\
Nervi es un programa de cálculo estructural (pórticos planos, método de rigidez). \
Estas herramientas leen un proyecto de Nervi y sus resultados; ninguna lo cambia.

Reglas:
- Nunca inventes ni estimes un número de resultado. Toda cifra que des tiene que \
salir de una herramienta; decí de cuál, y con qué caso o combinación.
- Los nudos se nombran N1, N2, … y las barras B1, B2, …, como en la interfaz.
- Las unidades son las del modelo (campo "unidades"); no las conviertas sin avisar.
- Los números vienen sin redondear. Al contestar redondeá con criterio, pero no \
cambies el valor.
- El diseño de hormigón es experimental: repetí su aviso cuando lo uses.
- Si algo no se puede calcular, explicá el motivo que da la herramienta; no lo suplas.
- La responsabilidad del cálculo es de la persona profesional que firma.
"""

_SOLO_LECTURA = ToolAnnotations.model_validate(
    {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}
)


def _publicar(funcion):
    """La herramienta tal cual, con los errores de consulta como error de herramienta."""

    @functools.wraps(funcion)
    def herramienta(*args, **kwargs):
        try:
            return funcion(*args, **kwargs)
        except ErrorConsulta as e:
            raise ToolError(str(e)) from None

    return herramienta


def crear_servidor(fuente: FuenteArchivo | FuenteProyecto) -> _Servidor:
    """Servidor MCP con las herramientas de solo lectura sobre ``fuente``."""
    h = Herramientas(fuente)
    servidor = _Servidor(name="nervi", instructions=INSTRUCCIONES)
    for nombre in NOMBRES:
        funcion = getattr(h, nombre)
        servidor.add_tool(
            _publicar(funcion),
            name=nombre,
            description=" ".join(funcion.__doc__.split()),
            annotations=_SOLO_LECTURA,
        )

    @servidor.resource(
        "nervi://modelo",
        name="modelo",
        description="modelo.json del proyecto (nudos, barras, apoyos, cargas, casos).",
        mime_type="application/json",
    )
    def modelo() -> str:
        return json.dumps(_publicar(h.leer_modelo)(), ensure_ascii=False)

    @servidor.resource(
        "nervi://resultados",
        name="resultados",
        description="Todos los resultados sin redondear (formato nervi-resultados v1).",
        mime_type="application/json",
    )
    def resultados() -> str:
        return json.dumps(_publicar(h.resultados_completos)(), ensure_ascii=False)

    return servidor


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada de ``nervi-mcp``."""
    parser = argparse.ArgumentParser(
        prog="nervi-mcp",
        description="Servidor MCP de solo lectura: un agente de IA consulta un proyecto .nrv.",
    )
    parser.add_argument("proyecto", help="archivo .nrv que va a consultar el agente")
    args = parser.parse_args(argv)
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
