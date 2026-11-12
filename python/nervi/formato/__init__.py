# SPDX-License-Identifier: GPL-3.0-or-later
"""Lectura y escritura de proyectos ``.nrv`` (ver ``docs/formato-nrv.md``).

Un proyecto se maneja como un :class:`Documento`: el manifiesto, el diccionario
de ``modelo.json`` (módulo ``modelo``, versión 1) y los miembros del ZIP que este
programa no interpreta, que se conservan al volver a guardar. Cada módulo tiene
su propia versión y sus migraciones (``docs/formato-nrv.md`` §3.1 y §6).

>>> from nervi import formato
>>> doc = formato.Documento.nuevo()
>>> doc.modelo["tipo"]
'portico_2d'
"""

from .contenedor import (
    MIMETYPE,
    MODULOS,
    VERSION_ESQUEMA,
    Documento,
    FormatoError,
    abrir,
    guardar,
)
from .modelo import construir_modelo, desde_modelo, validar

__all__ = [
    "MIMETYPE",
    "MODULOS",
    "VERSION_ESQUEMA",
    "Documento",
    "FormatoError",
    "abrir",
    "construir_modelo",
    "desde_modelo",
    "guardar",
    "validar",
]
