# SPDX-License-Identifier: GPL-3.0-or-later
"""Materiales, sección rectangular y constantes de ACI 318-19 (experimental).

Unidades: MPa y mm. Los momentos se dan en kN·m y los cortantes en kN, que es lo
que devuelve un modelo armado en kN y m (ver ``docs/convenciones.md``).

Fuentes, todas de ACI 318-19 (se implementa el método y se cita el artículo):

- ``Es = 200 000 MPa`` (§20.2.2.2) y ``εty = fy/Es`` (§21.2.2.1).
- Deformación máxima del hormigón ``εcu = 0.003`` (§22.2.2.1).
- ``f'c`` mínimo de 17 MPa para hormigón estructural (§19.2.1.1).
- Límites de ``fy`` según el uso de la armadura (§20.2.2.4): 550 MPa a flexión y
  420 MPa para estribos de cortante.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass

from ..combinaciones import ModuloExperimentalWarning

#: Módulo de elasticidad de la armadura, MPa (§20.2.2.2).
ES = 200_000.0
#: Deformación última del hormigón a compresión (§22.2.2.1).
EPS_CU = 0.003
#: Diámetros comerciales de barras longitudinales, mm (especificación §5.1).
DIAMETROS_COMERCIALES: tuple[int, ...] = (8, 10, 12, 16, 20, 25, 32)
#: Diámetros comerciales de estribos, mm.
DIAMETROS_ESTRIBO: tuple[int, ...] = (6, 8, 10, 12)


def avisar() -> None:
    warnings.warn(
        "nervi.design.aci318 es experimental y no fue revisado por un ingeniero estructural",
        ModuloExperimentalWarning,
        stacklevel=3,
    )


def area_barra(diametro: float) -> float:
    """Área nominal de una barra de diámetro ``diametro`` (mm²)."""
    return 3.141592653589793 * diametro**2 / 4.0


@dataclass(frozen=True)
class Materiales:
    """Hormigón y acero. ``fc``, ``fy`` y ``fyt`` en MPa.

    ``fyt`` es la fluencia de los estribos (por defecto, ``fy``). ``lam`` es el
    factor de hormigón liviano λ (1.0 para hormigón de peso normal, §19.2.4).
    """

    fc: float
    fy: float = 420.0
    fyt: float | None = None
    lam: float = 1.0

    def __post_init__(self) -> None:
        if self.fc < 17.0:
            raise ValueError(f"f'c = {self.fc} MPa; ACI 318-19 §19.2.1.1 pide al menos 17 MPa")
        if not 0.0 < self.fy <= 550.0:
            raise ValueError(f"fy = {self.fy} MPa; a flexión el límite es 550 MPa (§20.2.2.4)")
        if self.fyt is not None and not 0.0 < self.fyt:
            raise ValueError("fyt tiene que ser positivo")
        if not 0.0 < self.lam <= 1.0:
            raise ValueError("λ tiene que estar entre 0 y 1 (§19.2.4)")

    @property
    def fyt_efectivo(self) -> float:
        return self.fy if self.fyt is None else self.fyt

    @property
    def eps_ty(self) -> float:
        """Deformación de fluencia de la armadura longitudinal (§21.2.2.1)."""
        return self.fy / ES


@dataclass(frozen=True)
class SeccionRectangular:
    """Sección rectangular de viga, en mm.

    ``recubrimiento`` es el recubrimiento libre hasta el estribo; ``d_estribo``, el
    diámetro del estribo; ``d_agregado``, el tamaño máximo nominal del agregado.
    """

    b: float
    h: float
    recubrimiento: float = 40.0
    d_estribo: float = 10.0
    d_agregado: float = 19.0

    def __post_init__(self) -> None:
        if self.b <= 0 or self.h <= 0:
            raise ValueError("b y h tienen que ser positivos (mm)")
        if self.recubrimiento < 0 or self.d_estribo < 0 or self.d_agregado < 0:
            raise ValueError("recubrimiento, d_estribo y d_agregado no pueden ser negativos")
        if 2 * (self.recubrimiento + self.d_estribo) >= min(self.b, self.h):
            raise ValueError("el recubrimiento y el estribo no dejan lugar para la armadura")
