# SPDX-License-Identifier: GPL-3.0-or-later
"""Migraciones del formato ``.nrv`` (``docs/formato-nrv.md`` §6).

Cada módulo del proyecto (``modelo``, y más adelante ``diseno``, ``resultados``…)
tiene su propia versión y su propia cadena de migraciones. Una migración es una
función pura ``migrar(datos) -> datos`` que lleva el módulo de la versión ``N``
a la ``N + 1``; ``datos`` es un diccionario ``miembro del ZIP -> JSON``.

Reglas que no se rompen (``AGENTS.md``): una migración publicada **nunca** se
borra ni se cambia, y cada versión de cada módulo tiene un archivo de referencia
en ``tests/datos/nrv/`` que el CI abre en cada cambio.
"""

from __future__ import annotations

from collections.abc import Callable

Datos = dict[str, dict]
Migracion = Callable[[Datos], Datos]

#: módulo -> versión de origen -> función que lleva a la versión siguiente.
#: Hoy todos los módulos están en su versión 1, así que las cadenas están vacías.
MIGRACIONES: dict[str, dict[int, Migracion]] = {
    "modelo": {},
}


def migrar(modulo: str, datos: Datos, desde: int, hasta: int) -> Datos:
    """Aplica en cadena las migraciones de ``modulo`` desde ``desde`` hasta ``hasta``."""
    cadena = MIGRACIONES.get(modulo, {})
    version = desde
    while version < hasta:
        if version not in cadena:
            raise LookupError(
                f"falta la migración del módulo {modulo!r} de {version} a {version + 1}"
            )
        datos = cadena[version](datos)
        version += 1
    return datos
