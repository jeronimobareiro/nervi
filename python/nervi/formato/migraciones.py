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


def diseno_1_a_2(datos: Datos) -> Datos:
    """``diseno`` 1 → 2: agrega ``criterios.diametros_columna`` con todos los
    diámetros, que es lo que la versión 1 usaba sin guardarlo. Los resultados no
    cambian."""
    d = dict(datos)
    diseno = dict(d["diseno.json"])
    criterios = dict(diseno.get("criterios", {}))
    criterios.setdefault("diametros_columna", [12, 16, 20, 25, 32])
    diseno["criterios"] = criterios
    d["diseno.json"] = diseno
    return d


#: módulo -> versión de origen -> función que lleva a la versión siguiente.
MIGRACIONES: dict[str, dict[int, Migracion]] = {
    "modelo": {},
    "diseno": {1: diseno_1_a_2},
    "dinamica": {},
    "proyecto": {},
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
