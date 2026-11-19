# SPDX-License-Identifier: GPL-3.0-or-later
"""Módulo ``dinamica`` del formato ``.nrv`` (``dinamica.json``, versión 1).

Guarda los datos del análisis modal y espectral del pórtico plano: de qué casos
sale la masa, cuántos modos se piden y los espectros de respuesta. **No** guarda
resultados: se recalculan desde el modelo (``docs/formato-nrv.md`` §4c).

* ``masas.casos``: ``{nombre de caso: factor}``; la masa es ``-Fy · factor / g``
  con ``g`` según la unidad de longitud del modelo.
* ``espectros[].puntos``: pares ``[T, Sa]`` con ``T`` en segundos crecientes y
  ``Sa`` como **fracción de g** (adimensional), como se dan los espectros de
  diseño.

>>> d = nuevo()
>>> d["n_modos"], d["masas"]["casos"]
(12, {})
>>> validar(d)
"""

from __future__ import annotations

import copy
import math

from .errores import FormatoError

MIEMBRO = "dinamica.json"
DIRECCIONES = ("X", "Y")
COMBINACIONES = ("CQC", "SRSS")
MAX_MODOS = 200

_DEFECTO = {"masas": {"casos": {}}, "n_modos": 12, "espectros": []}


def nuevo() -> dict:
    """Sin masas ni espectros, 12 modos."""
    return copy.deepcopy(_DEFECTO)


def espectro_ejemplo(nombre: str = "Sismo X", direccion: str = "X") -> dict:
    """Espectro de forma típica (meseta de 0,1 a 0,5 s y rama 1/T), solo para
    empezar: los valores los tiene que dar la norma que corresponda."""
    puntos = [[0.0, 0.4], [0.1, 1.0], [0.5, 1.0]]
    puntos += [[t, round(0.5 / t, 4)] for t in (0.75, 1.0, 1.5, 2.0, 3.0, 4.0)]
    return {
        "nombre": nombre,
        "direccion": direccion,
        "combinacion": "CQC",
        "amortiguamiento": 0.05,
        "puntos": puntos,
    }


def _err(motivo: str, ruta: str) -> FormatoError:
    return FormatoError(motivo, MIEMBRO, ruta)


def _numero(v, ruta: str) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise _err("tiene que ser un número", ruta)
    return float(v)


def _objeto(d, ruta: str, claves: dict[str, bool]) -> dict:
    if not isinstance(d, dict):
        raise _err("tiene que ser un objeto", ruta)
    for clave in d:
        if clave not in claves:
            raise _err("clave desconocida", f"{ruta}.{clave}" if ruta else clave)
    for clave, obligatoria in claves.items():
        if obligatoria and clave not in d:
            raise _err("falta esta clave", f"{ruta}.{clave}" if ruta else clave)
    return d


def validar(d: dict) -> None:
    """Valida ``dinamica.json``. Lanza :class:`FormatoError` con la ruta del error.

    Los nombres de casos no se comparan con el modelo: si uno ya no existe, el
    análisis lo informa al calcular (el modelo puede cambiar después)."""
    _objeto(d, "", {"masas": True, "n_modos": True, "espectros": True, "extensiones": False})
    _objeto(d["masas"], "masas", {"casos": True})
    casos = d["masas"]["casos"]
    if not isinstance(casos, dict):
        raise _err("tiene que ser un objeto {caso: factor}", "masas.casos")
    for nombre, f in casos.items():
        if not nombre:
            raise _err("nombre de caso vacío", "masas.casos")
        if _numero(f, f"masas.casos.{nombre}") < 0:
            raise _err(f"= {f}: tiene que ser ≥ 0", f"masas.casos.{nombre}")
    n = d["n_modos"]
    if isinstance(n, bool) or not isinstance(n, int) or not 1 <= n <= MAX_MODOS:
        raise _err(f"tiene que ser un entero entre 1 y {MAX_MODOS}", "n_modos")
    if not isinstance(d["espectros"], list):
        raise _err("tiene que ser una lista", "espectros")
    nombres = set()
    for k, e in enumerate(d["espectros"]):
        ruta = f"espectros[{k}]"
        _objeto(
            e,
            ruta,
            {
                "nombre": True,
                "direccion": True,
                "combinacion": True,
                "amortiguamiento": True,
                "puntos": True,
            },
        )
        if not isinstance(e["nombre"], str) or not e["nombre"].strip():
            raise _err("tiene que ser un texto no vacío", f"{ruta}.nombre")
        if e["nombre"] in nombres:
            raise _err(f"el nombre {e['nombre']!r} se repite", f"{ruta}.nombre")
        nombres.add(e["nombre"])
        if e["direccion"] not in DIRECCIONES:
            raise _err(
                f"= {e['direccion']!r}: direcciones válidas {DIRECCIONES}", f"{ruta}.direccion"
            )
        if e["combinacion"] not in COMBINACIONES:
            raise _err(
                f"= {e['combinacion']!r}: combinaciones válidas {COMBINACIONES}",
                f"{ruta}.combinacion",
            )
        z = _numero(e["amortiguamiento"], f"{ruta}.amortiguamiento")
        if not 0.0 <= z < 1.0:
            raise _err(f"= {z}: tiene que estar entre 0 y 1", f"{ruta}.amortiguamiento")
        puntos = e["puntos"]
        if not isinstance(puntos, list) or not puntos:
            raise _err("tiene que ser una lista no vacía de pares [T, Sa]", f"{ruta}.puntos")
        anterior = -math.inf
        for p, par in enumerate(puntos):
            rp = f"{ruta}.puntos[{p}]"
            if not isinstance(par, list) or len(par) != 2:
                raise _err("tiene que ser un par [T, Sa]", rp)
            t, sa = _numero(par[0], rp), _numero(par[1], rp)
            if t < 0 or sa < 0:
                raise _err("T y Sa tienen que ser ≥ 0", rp)
            if t <= anterior:
                raise _err("los periodos tienen que ser crecientes", rp)
            anterior = t
    if "extensiones" in d and not isinstance(d["extensiones"], dict):
        raise _err("tiene que ser un objeto", "extensiones")
