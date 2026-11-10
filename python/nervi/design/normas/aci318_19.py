# SPDX-License-Identifier: GPL-3.0-or-later
"""Combinaciones de carga de ACI 318-19, capítulo 5 (experimental).

Fuentes:

- Resistencia: ACI 318-19 §5.3.1 (combinaciones 5.3.1a a 5.3.1g, coincidentes
  con ASCE/SEI 7-16 §2.3.1) y §5.3.3 (reducción del factor de ``L``).
- Servicio: ACI 318-19 §24.2 (flechas inmediatas con cargas de servicio, sin
  mayorar): ``D``, ``D + L`` y ``D + L`` más una carga de cubierta.

Se implementa el método y se cita el artículo; no se transcribe la tabla. Las
combinaciones con ``H``, ``F`` y ``T`` (empuje de suelos, fluidos y efectos
diferidos) no están incluidas todavía.
"""

from __future__ import annotations

from collections.abc import Iterator
from itertools import combinations as subconjuntos

from ..combinaciones import Combinacion, nombre_de

_REF = "ACI 318-19 "


def _sobrecargas(casos_l: list[str], alternar: bool) -> list[list[str]]:
    """Juegos de casos de sobrecarga presentes a la vez."""
    if not casos_l:
        return [[]]
    if not alternar:
        return [list(casos_l)]
    return [list(s) for n in range(len(casos_l), -1, -1) for s in subconjuntos(casos_l, n)]


def _laterales(casos: list[str], invertir: bool) -> list[tuple[str, float]]:
    return [(c, s) for c in casos for s in ((1.0, -1.0) if invertir else (1.0,))]


def combinaciones(grupos: dict[str, list[str]], opciones: dict) -> Iterator[Combinacion]:
    """Combinaciones de §5.3.1 y de servicio. Los términos "Lr o S o R" se generan
    con cada caso de cubierta y también sin ninguno, porque una carga de cubierta
    puede aliviar algún esfuerzo (por ejemplo en un voladizo)."""
    d = grupos["D"]
    juegos_l = _sobrecargas(grupos["L"], opciones["alternar_sobrecarga"])
    cubierta = grupos["Lr"] + grupos["S"] + grupos["R"]
    nieve = grupos["S"]
    viento = _laterales(grupos["W"], opciones["invertir_laterales"])
    sismo = _laterales(grupos["E"], opciones["invertir_laterales"])
    # §5.3.3: el factor 1.0 de L en 5.3.1c, d y e puede bajar a 0.5 en algunos destinos.
    f_l = 0.5 if opciones["reducir_sobrecarga"] else 1.0

    def comb(articulo: str, *partes: tuple[list[str] | str, float]) -> Combinacion:
        factores: dict[str, float] = {}
        for casos, f in partes:
            for c in [casos] if isinstance(casos, str) else casos:
                factores[c] = factores.get(c, 0.0) + f
        return Combinacion(nombre_de(articulo, factores), factores, "resistencia", _REF + articulo)

    if "resistencia" in opciones["estados"]:
        yield comb("5.3.1a", (d, 1.4))
        for jl in juegos_l:
            # 5.3.1b: 1.2D + 1.6L + 0.5(Lr o S o R)
            for x in [None, *cubierta]:
                yield comb("5.3.1b", (d, 1.2), (jl, 1.6), *([(x, 0.5)] if x else []))
            # 5.3.1c: 1.2D + 1.6(Lr o S o R) + (1.0L o 0.5W)
            for x in cubierta:
                yield comb("5.3.1c", (d, 1.2), (x, 1.6), (jl, f_l))
                for w, s in viento:
                    yield comb("5.3.1c", (d, 1.2), (x, 1.6), (w, 0.5 * s))
            # 5.3.1d: 1.2D + 1.0W + 1.0L + 0.5(Lr o S o R)
            for w, s in viento:
                for x in [None, *cubierta]:
                    yield comb("5.3.1d", (d, 1.2), (w, s), (jl, f_l), *([(x, 0.5)] if x else []))
            # 5.3.1e: 1.2D + 1.0E + 1.0L + 0.2S
            for e, s in sismo:
                for x in [None, *nieve]:
                    yield comb("5.3.1e", (d, 1.2), (e, s), (jl, f_l), *([(x, 0.2)] if x else []))
        # 5.3.1f: 0.9D + 1.0W ; 5.3.1g: 0.9D + 1.0E
        for w, s in viento:
            yield comb("5.3.1f", (d, 0.9), (w, s))
        for e, s in sismo:
            yield comb("5.3.1g", (d, 0.9), (e, s))

    if "servicio" in opciones["estados"]:

        def serv(*partes: tuple[list[str] | str, float]) -> Combinacion:
            c = comb("24.2", *partes)
            return Combinacion("Servicio " + c.nombre, c.factores, "servicio", c.referencia)

        yield serv((d, 1.0))
        for jl in juegos_l:
            if jl:
                yield serv((d, 1.0), (jl, 1.0))
            for x in cubierta:
                yield serv((d, 1.0), (jl, 1.0), (x, 1.0))
