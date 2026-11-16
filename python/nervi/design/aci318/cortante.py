# SPDX-License-Identifier: GPL-3.0-or-later
"""Cortante en vigas no pretensadas según ACI 318-19 (experimental).

Issue #23. Unidades: MPa y mm; cortantes en kN.

Método (ACI 318-19, se cita el artículo y no se transcriben tablas):

- ``φVn ≥ Vu`` con ``Vn = Vc + Vs`` (§22.5.1.1) y ``φ = 0.75`` (§21.2.1).
- ``√f'c ≤ 8.3 MPa`` en el cálculo de ``Vc`` (§22.5.3.1); ``fyt ≤ 420 MPa`` para
  armadura de cortante (§20.2.2.4).
- ``Vc`` con estribos ``Av ≥ Av,min``: expresión simplificada ``0.17 λ √f'c bw d``
  (§22.5.5.1, opción a). Sin estribos: ``0.66 λs λ rho_w^(1/3) √f'c bw d``
  (§22.5.5.1, opción c), con el factor de tamaño ``λs`` de §22.5.5.1.3 y el tope
  ``0.42 λ √f'c bw d`` de §22.5.5.1.1. Sin carga axial (``Nu = 0``).
- Límite de la sección: ``Vu ≤ φ (Vc + 0.66 √f'c bw d)`` (§22.5.1.2).
- Estribos verticales: ``Vs = Av fyt d / s`` (§22.5.8.5.3).
- ``Av,min/s`` (§9.6.3.4) donde ``Vu > φ 0.083 λ √f'c bw d`` (§9.6.3.1). No se
  aplican las excepciones de §9.6.3.1 para vigas bajas o losas.
- Separación máxima (§9.7.6.2.2): ``min(d/2, 600)``, o ``min(d/4, 300)`` si
  ``Vs > 0.33 √f'c bw d``.
- Sección crítica a ``d`` de la cara del apoyo (§9.4.3.2): ver
  :func:`nervi.design.aci318.disenar_viga`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .materiales import DIAMETROS_ESTRIBO, Materiales, area_barra, avisar

#: Factor de reducción de cortante (§21.2.1).
PHI_CORTANTE = 0.75
#: Fluencia máxima de la armadura de cortante, MPa (§20.2.2.4).
FYT_MAX_CORTANTE = 420.0


def _raiz_fc(mat: Materiales) -> float:
    return min(math.sqrt(mat.fc), 8.3)  # §22.5.3.1


def factor_tamano(d: float) -> float:
    """Factor de efecto de tamaño ``λs`` (§22.5.5.1.3), con ``d`` en mm."""
    return min(1.0, math.sqrt(2.0 / (1.0 + 0.004 * d)))


def separacion_maxima(Vs: float, b: float, d: float, mat: Materiales) -> float:
    """Separación máxima de estribos verticales, mm (§9.7.6.2.2). ``Vs`` en kN."""
    if Vs * 1e3 <= 0.33 * _raiz_fc(mat) * b * d:
        return min(d / 2.0, 600.0)
    return min(d / 4.0, 300.0)


@dataclass(frozen=True)
class ResultadoCortante:
    """Resultado de :func:`armadura_cortante`. Fuerzas en kN, ``Av/s`` en mm²/mm."""

    Vu: float
    phi: float
    Vc: float
    #: ``Vs`` necesario por resistencia (0 si alcanza el hormigón).
    Vs_req: float
    #: ``Av/s`` por resistencia, mínimo de §9.6.3.4 y de diseño (el mayor).
    Av_s_req: float
    Av_s_min: float
    Av_s: float
    #: Si hacen falta estribos (por resistencia o por mínimo).
    requiere_estribos: bool
    #: Separación máxima con el ``Vs`` requerido, mm.
    s_max: float
    #: ``φ (Vc + 0.66 √f'c bw d)``: tope de §22.5.1.2.
    Vu_max_seccion: float


def armadura_cortante(
    Vu: float,
    b: float,
    d: float,
    mat: Materiales,
    *,
    rho_w: float | None = None,
) -> ResultadoCortante:
    """Estribos verticales necesarios para el cortante último ``Vu`` (kN).

    ``b`` y ``d`` en mm. ``rho_w = As/(bw d)`` de la armadura traccionada permite
    verificar la sección sin estribos con §22.5.5.1c; si no se da, se ponen al menos
    estribos mínimos. Lanza ``ValueError`` si la sección no alcanza (§22.5.1.2).
    """
    avisar()
    fyt = mat.fyt_efectivo
    if fyt > FYT_MAX_CORTANTE:
        raise ValueError(f"fyt = {fyt} MPa; para cortante el límite es 420 MPa (§20.2.2.4)")
    vu = abs(Vu) * 1e3  # N
    phi = PHI_CORTANTE
    rf = _raiz_fc(mat)
    vc_a = 0.17 * mat.lam * rf * b * d  # §22.5.5.1a
    vu_max = phi * (vc_a + 0.66 * rf * b * d)  # §22.5.1.2
    if vu > vu_max * (1 + 1e-12):
        raise ValueError(
            f"Vu = {vu / 1e3:g} kN supera φ(Vc + 0.66√f'c·bw·d) = {vu_max / 1e3:.4g} kN "
            "(§22.5.1.2): hay que agrandar la sección"
        )
    umbral = phi * 0.083 * mat.lam * rf * b * d  # §9.6.3.1
    sin_estribos = False
    if rho_w is not None and vu <= umbral:
        vc_c = 0.66 * factor_tamano(d) * mat.lam * rho_w ** (1 / 3) * rf * b * d  # §22.5.5.1c
        vc_c = min(vc_c, 0.42 * mat.lam * rf * b * d)  # §22.5.5.1.1
        sin_estribos = vu <= phi * vc_c
    if sin_estribos:
        return ResultadoCortante(
            Vu, phi, vc_c / 1e3, 0.0, 0.0, 0.0, 0.0, False, min(d / 2, 600.0), vu_max / 1e3
        )
    vs_req = max(vu / phi - vc_a, 0.0)
    av_s_req = vs_req / (fyt * d)  # §22.5.8.5.3
    av_s_min = max(0.062 * rf, 0.35) * b / fyt  # §9.6.3.4
    return ResultadoCortante(
        Vu,
        phi,
        vc_a / 1e3,
        vs_req / 1e3,
        av_s_req,
        av_s_min,
        max(av_s_req, av_s_min),
        True,
        separacion_maxima(vs_req / 1e3, b, d, mat),
        vu_max / 1e3,
    )


@dataclass(frozen=True)
class Estribos:
    """Estribos elegidos por :func:`elegir_estribos`."""

    diametro: int
    ramas: int
    #: Separación, mm.
    s: float
    #: Área de las ramas (mm²) y ``Av/s`` provisto (mm²/mm).
    Av: float
    Av_s: float
    #: ``Vs`` provisto y ``φVn``, kN.
    Vs: float
    phiVn: float
    requerido: ResultadoCortante

    @property
    def descripcion(self) -> str:
        """Por ejemplo ``"eØ8 c/150 mm (2 ramas)"``."""
        return f"eØ{self.diametro} c/{self.s:g} mm ({self.ramas} ramas)"


def elegir_estribos(
    Vu: float,
    b: float,
    d: float,
    mat: Materiales,
    *,
    rho_w: float | None = None,
    diametros: tuple[int, ...] = DIAMETROS_ESTRIBO,
    ramas: tuple[int, ...] = (2,),
    s_min: float = 75.0,
    paso: float = 25.0,
) -> Estribos | None:
    """Elige diámetro, ramas y separación de estribos para ``Vu`` (kN).

    La separación se redondea hacia abajo a múltiplos de ``paso`` y no baja de
    ``s_min``. Se elige la opción con menor acero por metro (``Av/s``) y, a igualdad,
    la de mayor separación. Devuelve ``None`` si no hacen falta estribos.
    """
    req = armadura_cortante(Vu, b, d, mat, rho_w=rho_w)
    if not req.requiere_estribos:
        return None
    fyt = mat.fyt_efectivo
    mejor: Estribos | None = None
    for db in diametros:
        for n in ramas:
            av = n * area_barra(db)
            s_lim = av / req.Av_s if req.Av_s > 0 else math.inf
            s = math.floor(min(s_lim, req.s_max) / paso + 1e-9) * paso
            # La separación máxima depende del Vs provisto (§9.7.6.2.2).
            while s >= s_min and s > separacion_maxima(av * fyt * d / s / 1e3, b, d, mat):
                s -= paso
            if s < s_min:
                continue
            vs = av * fyt * d / s / 1e3
            cand = Estribos(db, n, s, av, av / s, vs, req.phi * (req.Vc + vs), req)
            if mejor is None or (cand.Av_s, -cand.s) < (mejor.Av_s, -mejor.s):
                mejor = cand
    if mejor is None:
        raise ValueError(
            f"ningún estribo de {diametros} mm con {ramas} ramas cumple con s ≥ {s_min:g} mm "
            f"para Vu = {abs(Vu):g} kN"
        )
    return mejor
