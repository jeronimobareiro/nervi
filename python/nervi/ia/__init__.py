# SPDX-License-Identifier: GPL-3.0-or-later
"""Integración con agentes de IA (línea transversal de ``docs/hoja-de-ruta.md``).

* :mod:`nervi.ia.herramientas`: las consultas que puede hacer un agente sobre un
  proyecto, como funciones comunes de Python (no dependen de MCP).
* :mod:`nervi.ia.servidor`: servidor MCP ``nervi-mcp`` que las publica para que el
  agente de la persona (Claude, ChatGPT, Gemini u otro cliente MCP) las use.
  Necesita ``pip install nervi[ia]``.

Regla de la integración: el agente nunca produce un número de resultado. Toda cifra
sale del motor de Nervi por una herramienta, y lo que cambie el proyecto llega como
propuesta (``Proyecto.proponer``) que la persona aplica o descarta.
"""
