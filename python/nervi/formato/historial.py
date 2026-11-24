# SPDX-License-Identifier: GPL-3.0-or-later
"""Módulo ``historial`` del formato ``.nrv`` (``historial.json``, versión 1).

Registro de los cambios al proyecto que **no** hizo la persona a mano: los que
propuso un agente de IA, un importador o un complemento y la persona aplicó, y
si después los deshizo o los rehízo (``docs/formato-nrv.md`` §4d). Sirve para
auditar un proyecto: qué cambió, quién lo propuso y sobre qué modelo.

Las ediciones a mano no se registran (serían miles por sesión); deshacer y
rehacer viven solo mientras el proyecto está abierto.

>>> h = nuevo()
>>> h["cambios"]
[]
>>> validar(h)
"""

from __future__ import annotations

import copy
import re

from .errores import FormatoError

MIEMBRO = "historial.json"
#: Qué se hizo con un cambio propuesto.
ACCIONES = ("aplicar", "deshacer", "rehacer")
#: Partes del proyecto que puede tocar un cambio.
PARTES = ("modelo", "diseno", "dinamica")
#: Se guardan los últimos cambios; los más viejos se descartan al agregar.
MAX_CAMBIOS = 2000

_HUELLA = re.compile(r"^sha256:[0-9a-f]{64}$")
_FECHA = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_DEFECTO = {"cambios": []}


def nuevo() -> dict:
    """Historial vacío."""
    return copy.deepcopy(_DEFECTO)


def _err(motivo: str, ruta: str) -> FormatoError:
    return FormatoError(motivo, MIEMBRO, ruta)


def _texto(v, ruta: str, vacio: bool = False) -> None:
    if not isinstance(v, str) or (not vacio and not v.strip()):
        raise _err("tiene que ser un texto" + ("" if vacio else " no vacío"), ruta)


def validar(h: dict) -> None:
    """Valida ``historial.json``. Lanza :class:`FormatoError` con la ruta del error."""
    if not isinstance(h, dict):
        raise _err("tiene que ser un objeto", "")
    for clave in h:
        if clave not in ("cambios", "extensiones"):
            raise _err("clave desconocida", clave)
    if "cambios" not in h:
        raise _err("falta esta clave", "cambios")
    cambios = h["cambios"]
    if not isinstance(cambios, list):
        raise _err("tiene que ser una lista", "cambios")
    if len(cambios) > MAX_CAMBIOS:
        raise _err(f"tiene más de {MAX_CAMBIOS} cambios", "cambios")
    claves = {
        "fecha": True,
        "accion": True,
        "parte": True,
        "origen": True,
        "descripcion": True,
        "resumen": True,
        "huella_antes": True,
        "huella_despues": True,
    }
    for k, c in enumerate(cambios):
        ruta = f"cambios[{k}]"
        if not isinstance(c, dict):
            raise _err("tiene que ser un objeto", ruta)
        for clave in c:
            if clave not in claves:
                raise _err("clave desconocida", f"{ruta}.{clave}")
        for clave in claves:
            if clave not in c:
                raise _err("falta esta clave", f"{ruta}.{clave}")
        if not isinstance(c["fecha"], str) or not _FECHA.match(c["fecha"]):
            raise _err("tiene que ser una fecha UTC AAAA-MM-DDTHH:MM:SSZ", f"{ruta}.fecha")
        if c["accion"] not in ACCIONES:
            raise _err(f"= {c['accion']!r}: acciones válidas {ACCIONES}", f"{ruta}.accion")
        if c["parte"] not in PARTES:
            raise _err(f"= {c['parte']!r}: partes válidas {PARTES}", f"{ruta}.parte")
        _texto(c["origen"], f"{ruta}.origen")
        _texto(c["descripcion"], f"{ruta}.descripcion", vacio=True)
        if not isinstance(c["resumen"], list):
            raise _err("tiene que ser una lista de textos", f"{ruta}.resumen")
        for j, r in enumerate(c["resumen"]):
            _texto(r, f"{ruta}.resumen[{j}]")
        for clave in ("huella_antes", "huella_despues"):
            if not isinstance(c[clave], str) or not _HUELLA.match(c[clave]):
                raise _err("tiene que ser 'sha256:' y 64 dígitos hexadecimales", f"{ruta}.{clave}")
    if "extensiones" in h and not isinstance(h["extensiones"], dict):
        raise _err("tiene que ser un objeto", "extensiones")
