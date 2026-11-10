# SPDX-License-Identifier: GPL-3.0-or-later
"""Migraciones entre versiones del esquema ``.nrv`` (``docs/formato-nrv.md`` §6).

Cada migración es una función pura ``migrar_N_a_M(manifiesto, modelo)`` que
devuelve los diccionarios en la versión siguiente. Hoy solo existe el esquema 1,
así que la cadena está vacía.
"""

from __future__ import annotations

from collections.abc import Callable

Migracion = Callable[[dict, dict], tuple[dict, dict]]

#: versión de origen -> función que lleva a la versión siguiente
MIGRACIONES: dict[int, Migracion] = {}


def migrar(manifiesto: dict, modelo: dict, hasta: int) -> tuple[dict, dict]:
    """Aplica en cadena las migraciones desde la versión del manifiesto hasta ``hasta``."""
    version = int(manifiesto["version_esquema"])
    while version < hasta:
        manifiesto, modelo = MIGRACIONES[version](manifiesto, modelo)
        version += 1
        manifiesto["version_esquema"] = version
    return manifiesto, modelo
