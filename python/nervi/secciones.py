# SPDX-License-Identifier: GPL-3.0-or-later
"""Propiedades de secciones habituales para el pórtico espacial.

Cada función devuelve un diccionario ``{"A", "Iy", "Iz", "J"}`` que se puede
pasar a :meth:`nervi.Modelo3D.agregar_barra` con ``seccion=...``.

Ejes de la sección (ver ``docs/convenciones.md``): el canto ``h`` se mide sobre
el eje ``y`` local y el ancho ``b`` sobre el ``z`` local, así que ``Iz`` es la
inercia de la flexión en el plano ``x-y`` (la de cargas gravitatorias en una
viga con los ejes por defecto, donde ``y`` apunta hacia arriba).

Fuentes: S. Timoshenko y J. N. Goodier, *Theory of Elasticity*, 3.ª ed., §109
(torsión de la barra rectangular, serie exacta) y §104 (sección circular);
W. C. Young y R. G. Budynas, *Roark's Formulas for Stress and Strain*, 7.ª ed.,
tabla A.1 (áreas e inercias) y tabla 10.7 (constantes de torsión).
"""

from __future__ import annotations

import math


def _positivo(**valores: float) -> None:
    for nombre, v in valores.items():
        if not (math.isfinite(v) and v > 0.0):
            raise ValueError(f"{nombre} = {v}; debe ser positivo")


def torsion_rectangular(lado_mayor: float, lado_menor: float, terminos: int = 50) -> float:
    """Constante de torsión de Saint-Venant de un rectángulo, serie exacta
    (Timoshenko y Goodier, §109):

    ``J = a b³/3 · [1 - (192/π⁵)(b/a) Σ_{n impar} tanh(nπa/2b)/n⁵]``, con ``a ≥ b``.
    La serie converge como ``1/n⁵``: con 50 términos el error relativo es menor
    que 1e-12.
    """
    a, b = max(lado_mayor, lado_menor), min(lado_mayor, lado_menor)
    _positivo(lado_mayor=a, lado_menor=b)
    suma = 0.0
    for k in range(terminos):
        n = 2 * k + 1
        suma += math.tanh(n * math.pi * a / (2.0 * b)) / n**5
    return a * b**3 / 3.0 * (1.0 - 192.0 / math.pi**5 * (b / a) * suma)


def rectangular(b: float, h: float) -> dict[str, float]:
    """Sección rectangular maciza de ancho ``b`` (sobre ``z`` local) y canto
    ``h`` (sobre ``y`` local)."""
    _positivo(b=b, h=h)
    return {
        "A": b * h,
        "Iy": h * b**3 / 12.0,
        "Iz": b * h**3 / 12.0,
        "J": torsion_rectangular(b, h),
    }


def circular(d: float) -> dict[str, float]:
    """Sección circular maciza de diámetro ``d``: ``J = πd⁴/32`` (momento polar)."""
    _positivo(d=d)
    i = math.pi * d**4 / 64.0
    return {"A": math.pi * d**2 / 4.0, "Iy": i, "Iz": i, "J": 2.0 * i}


def tubo_circular(d: float, e: float) -> dict[str, float]:
    """Tubo circular de diámetro exterior ``d`` y espesor ``e`` (``0 < e ≤ d/2``)."""
    _positivo(d=d, e=e)
    if e > d / 2.0:
        raise ValueError(f"el espesor {e} es mayor que el radio {d / 2.0}")
    di = d - 2.0 * e
    i = math.pi * (d**4 - di**4) / 64.0
    return {"A": math.pi * (d**2 - di**2) / 4.0, "Iy": i, "Iz": i, "J": 2.0 * i}
