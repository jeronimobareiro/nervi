# SPDX-License-Identifier: GPL-3.0-or-later
"""Módulo ``proyecto`` del formato ``.nrv`` (``proyecto.json``, versión 1).

Guarda los datos que identifican el proyecto y salen en la carátula de la
memoria: nombre, ubicación, comitente, autor, fecha y revisión. Son textos libres
y todos opcionales (``docs/formato-nrv.md`` §4d).

>>> d = nuevo()
>>> d["datos"]
{}
>>> validar({"datos": {"nombre": "Edificio Sur", "revision": "B"}})
"""

from __future__ import annotations

import copy

from .errores import FormatoError

MIEMBRO = "proyecto.json"
#: Clave de cada dato y su nombre en la carátula de la memoria, en orden.
CAMPOS = {
    "nombre": "Proyecto",
    "ubicacion": "Ubicación",
    "comitente": "Comitente",
    "autor": "Autor",
    "fecha": "Fecha",
    "revision": "Revisión",
}
MAX_CARACTERES = 500

_DEFECTO: dict = {"datos": {}}


def nuevo() -> dict:
    """Sin datos: la memoria usa el nombre del archivo como nombre del proyecto."""
    return copy.deepcopy(_DEFECTO)


def _err(motivo: str, ruta: str) -> FormatoError:
    return FormatoError(motivo, MIEMBRO, ruta)


def validar(d: dict) -> None:
    """Valida ``proyecto.json``. Lanza :class:`FormatoError` con la ruta del error."""
    if not isinstance(d, dict):
        raise _err("tiene que ser un objeto", "")
    for clave in d:
        if clave not in ("datos", "extensiones"):
            raise _err("clave desconocida", clave)
    if "datos" not in d:
        raise _err("falta esta clave", "datos")
    datos = d["datos"]
    if not isinstance(datos, dict):
        raise _err("tiene que ser un objeto", "datos")
    for clave, valor in datos.items():
        if clave not in CAMPOS:
            raise _err(f"clave desconocida; válidas {tuple(CAMPOS)}", f"datos.{clave}")
        if not isinstance(valor, str):
            raise _err("tiene que ser un texto", f"datos.{clave}")
        if len(valor) > MAX_CARACTERES:
            raise _err(f"tiene más de {MAX_CARACTERES} caracteres", f"datos.{clave}")
    if "extensiones" in d and not isinstance(d["extensiones"], dict):
        raise _err("tiene que ser un objeto", "extensiones")


def para_caratula(d: dict | None) -> dict[str, str]:
    """Los datos cargados, con el nombre que llevan en la carátula de la memoria."""
    datos = (d or {}).get("datos", {})
    return {CAMPOS[k]: datos[k].strip() for k in CAMPOS if datos.get(k, "").strip()}
