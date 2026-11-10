# SPDX-License-Identifier: GPL-3.0-or-later
"""Tipos de carga y generación de combinaciones según una norma intercambiable.

Cada norma es un módulo en ``nervi/design/normas/`` con una función
``combinaciones(grupos, opciones) -> list[Combinacion]``. Para sumar una norma
regional (CIRSOC, NBR, la que se decida en el issue #20) alcanza con agregar un
módulo y registrarlo en ``_NORMAS``.
"""

from __future__ import annotations

import importlib
import warnings
from dataclasses import dataclass, field

#: Tipos de carga reconocidos (nomenclatura de ASCE 7 y ACI 318).
TIPOS_CARGA: dict[str, str] = {
    "D": "permanente",
    "L": "sobrecarga de uso",
    "Lr": "sobrecarga de cubierta",
    "S": "nieve",
    "R": "lluvia",
    "W": "viento",
    "E": "sismo",
}

_NORMAS = {"aci318-19": "nervi.design.normas.aci318_19"}


class ModuloExperimentalWarning(UserWarning):
    """Aviso de que un resultado viene de un módulo de diseño sin revisión."""


@dataclass(frozen=True)
class Combinacion:
    """Combinación lineal de casos de carga."""

    nombre: str
    factores: dict[str, float] = field(hash=False)
    #: ``"resistencia"`` o ``"servicio"``.
    estado: str = "resistencia"
    #: Artículo de la norma que la origina, por ejemplo ``"ACI 318-19 5.3.1b"``.
    referencia: str = ""


def normas_disponibles() -> list[str]:
    return sorted(_NORMAS)


def agrupar(tipos: dict[str, str]) -> dict[str, list[str]]:
    """Agrupa los casos por tipo de carga, validando los tipos."""
    grupos: dict[str, list[str]] = {t: [] for t in TIPOS_CARGA}
    for caso, tipo in tipos.items():
        if tipo not in TIPOS_CARGA:
            raise ValueError(
                f"el caso {caso!r} tiene el tipo {tipo!r}; los tipos válidos son "
                + ", ".join(TIPOS_CARGA)
            )
        grupos[tipo].append(caso)
    if not grupos["D"]:
        raise ValueError("hace falta al menos un caso de tipo 'D' (permanente)")
    return grupos


def generar(
    tipos: dict[str, str],
    norma: str = "aci318-19",
    *,
    estados: tuple[str, ...] = ("resistencia",),
    alternar_sobrecarga: bool = False,
    invertir_laterales: bool = True,
    reducir_sobrecarga: bool = False,
) -> list[Combinacion]:
    """Genera las combinaciones de una norma.

    ``tipos`` asigna a cada caso de carga un tipo de :data:`TIPOS_CARGA`, por
    ejemplo ``{"D": "D", "L1": "L", "L2": "L", "Wx": "W"}``.

    - Los casos de tipo ``D`` se suman siempre juntos.
    - Los de tipo ``L`` van juntos, salvo con ``alternar_sobrecarga=True``: entonces
      se generan todas las combinaciones de presencia o ausencia de cada caso
      ``L`` (sobrecarga alternada en vigas continuas). Se limita a 10 casos ``L``.
    - Los de tipo ``Lr``, ``S``, ``R``, ``W`` y ``E`` son alternativos: entra uno por
      combinación. Con ``invertir_laterales=True`` cada caso ``W`` y ``E`` se usa
      con los dos signos (viento y sismo en ambos sentidos).
    - ``reducir_sobrecarga`` aplica la reducción del factor de ``L`` que la norma
      permite en algunos destinos; quien la activa es responsable de que aplique.
    - ``estados`` elige ``"resistencia"``, ``"servicio"`` o ambos.

    Se omiten combinaciones repetidas.
    """
    warnings.warn(
        "nervi.design es experimental y no fue revisado por un ingeniero estructural",
        ModuloExperimentalWarning,
        stacklevel=2,
    )
    if norma not in _NORMAS:
        raise ValueError(f"norma {norma!r} desconocida; disponibles: {normas_disponibles()}")
    for e in estados:
        if e not in ("resistencia", "servicio"):
            raise ValueError(f"estado {e!r} desconocido (resistencia o servicio)")
    grupos = agrupar(tipos)
    if alternar_sobrecarga and len(grupos["L"]) > 10:
        raise ValueError("alternar_sobrecarga admite hasta 10 casos de tipo 'L'")
    modulo = importlib.import_module(_NORMAS[norma])
    opciones = {
        "estados": estados,
        "alternar_sobrecarga": alternar_sobrecarga,
        "invertir_laterales": invertir_laterales,
        "reducir_sobrecarga": reducir_sobrecarga,
    }
    salida: list[Combinacion] = []
    vistos: set[tuple] = set()
    for c in modulo.combinaciones(grupos, opciones):
        clave = (c.estado, tuple(sorted((k, round(v, 12)) for k, v in c.factores.items() if v)))
        if clave not in vistos:
            vistos.add(clave)
            salida.append(c)
    return salida


def como_diccionario(combinaciones: list[Combinacion]) -> dict[str, dict[str, float]]:
    """Formato que acepta ``Modelo.resolver(combinaciones=...)``."""
    return {c.nombre: dict(c.factores) for c in combinaciones}


def nombre_de(prefijo: str, factores: dict[str, float]) -> str:
    """``"5.3.1b: 1.2·D + 1.6·L"``, con los casos en el orden recibido."""
    partes = []
    for caso, f in factores.items():
        if f == 0:
            continue
        signo = "-" if f < 0 else "+"
        partes.append((signo, f"{abs(f):g}·{caso}"))
    texto = " ".join(f"{s} {t}" for s, t in partes).lstrip("+ ")
    if partes and partes[0][0] == "-":
        texto = "-" + texto[2:]
    return f"{prefijo}: {texto}"
