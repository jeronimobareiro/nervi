# SPDX-License-Identifier: GPL-3.0-or-later
"""Envolventes de esfuerzos y de reacciones sobre un conjunto de combinaciones."""

from __future__ import annotations

import numpy as np

from ..modelo import Resultados

_COMPONENTES = ("N", "V", "M", "u", "v")


def envolvente(
    res: Resultados, barra: int, combinaciones: list[str] | None = None
) -> dict[str, np.ndarray]:
    """Máximo y mínimo de cada esfuerzo en cada estación de la barra.

    ``combinaciones`` son nombres resueltos con ``Modelo.resolver(combinaciones=...)``
    (por defecto, todas). Devuelve ``x`` y, para cada componente ``N, V, M, u, v``,
    los arreglos ``<c>_max``, ``<c>_min`` y ``<c>_max_comb``, ``<c>_min_comb`` con el
    nombre de la combinación que produce cada extremo.
    """
    nombres = res.combinaciones if combinaciones is None else list(combinaciones)
    if not nombres:
        raise ValueError("no hay combinaciones: pasalas a Modelo.resolver(combinaciones=...)")
    faltan = [n for n in nombres if n not in res.combinaciones]
    if faltan:
        raise ValueError(
            f"{faltan} no se resolvieron junto con el modelo; las envolventes necesitan "
            "combinaciones pasadas a Modelo.resolver(combinaciones=...)"
        )
    diags = [res[n].diagrama(barra) for n in nombres]
    x = diags[0]["x"]
    salida: dict[str, np.ndarray] = {"x": x}
    etiquetas = np.array(nombres, dtype=object)
    for comp in _COMPONENTES:
        valores = np.vstack([d[comp] for d in diags])
        imax, imin = valores.argmax(axis=0), valores.argmin(axis=0)
        cols = np.arange(x.size)
        salida[f"{comp}_max"] = valores[imax, cols]
        salida[f"{comp}_min"] = valores[imin, cols]
        salida[f"{comp}_max_comb"] = etiquetas[imax]
        salida[f"{comp}_min_comb"] = etiquetas[imin]
    return salida


def envolvente_reacciones(
    res: Resultados, combinaciones: list[str] | None = None
) -> dict[str, np.ndarray]:
    """Máximo y mínimo de cada reacción ``(n_nudos, 3)`` con su combinación."""
    nombres = res.combinaciones if combinaciones is None else list(combinaciones)
    if not nombres:
        raise ValueError("no hay combinaciones para la envolvente")
    valores = np.stack([res[n].reacciones for n in nombres])
    etiquetas = np.array(nombres, dtype=object)
    imax, imin = valores.argmax(axis=0), valores.argmin(axis=0)
    return {
        "max": valores.max(axis=0),
        "min": valores.min(axis=0),
        "max_comb": etiquetas[imax],
        "min_comb": etiquetas[imin],
    }
