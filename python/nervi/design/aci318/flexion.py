# SPDX-License-Identifier: GPL-3.0-or-later
"""Flexión de vigas rectangulares de hormigón armado según ACI 318-19 (experimental).

Issue #22. Unidades: MPa y mm; momentos en kN·m.

Método (ACI 318-19, se cita el artículo y no se transcriben tablas):

- Hipótesis de diseño de §22.2: secciones planas, ``εcu = 0.003`` (§22.2.2.1),
  bloque rectangular equivalente de ``0.85 f'c`` y profundidad ``a = β1 c``
  (§22.2.2.4.1), con ``β1`` según §22.2.2.4.3; acero elastoplástico (§20.2.2.1).
- Factor de reducción ``φ`` en función de ``εt`` (§21.2.2): 0.90 si
  ``εt ≥ εty + 0.003`` (controlada por tracción), 0.65 si ``εt ≤ εty``
  (controlada por compresión) y lineal entre ambos.
- Deformación mínima ``εt ≥ 0.004`` para vigas no pretensadas (§9.3.3.1).
- Armadura mínima (§9.6.1.2) y su excepción de 4/3 de la requerida (§9.6.1.3).
- Separación libre mínima entre barras de una capa (§25.2.1) y entre capas (§25.2.2).

La resistencia se calcula por compatibilidad de deformaciones (equilibrio de la
sección resuelto por bisección sobre la profundidad del eje neutro), así que vale
también cuando la armadura de compresión no fluye.

El cálculo (resistencia, armadura simple y búsqueda de barras) corre en Rust, en
``nervi_core::diseno::viga``; este módulo valida los datos y arma los resultados.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from ... import _core
from .materiales import (
    DIAMETROS_COMERCIALES,
    EPS_CU,
    ES,
    Materiales,
    SeccionRectangular,
    avisar,
)

#: Deformación mínima de la armadura traccionada en vigas (§9.3.3.1).
EPS_T_MIN_VIGAS = 0.004
#: Separación libre mínima entre capas de barras, mm (§25.2.2).
SEPARACION_ENTRE_CAPAS = 25.0


def beta1(fc: float) -> float:
    """Factor ``β1`` del bloque rectangular equivalente (§22.2.2.4.3)."""
    if fc <= 28.0:
        return 0.85
    if fc >= 55.0:
        return 0.65
    return 0.85 - 0.05 * (fc - 28.0) / 7.0


def phi_flexion(eps_t: float, fy: float) -> float:
    """Factor ``φ`` para momento sin pretensado, según ``εt`` (§21.2.2)."""
    eps_ty = fy / ES
    if eps_t >= eps_ty + 0.003:
        return 0.90
    if eps_t <= eps_ty:
        return 0.65
    return 0.65 + 0.25 * (eps_t - eps_ty) / 0.003


def armadura_minima(b: float, d: float, mat: Materiales) -> float:
    """``As,min`` de vigas no pretensadas, mm² (§9.6.1.2)."""
    return max(0.25 * math.sqrt(mat.fc) / mat.fy, 1.4 / mat.fy) * b * d


@dataclass(frozen=True)
class ResistenciaFlexion:
    """Resultado de :func:`resistencia_flexion`."""

    #: Momento nominal y de diseño, kN·m.
    Mn: float
    phi: float
    phiMn: float
    #: Profundidad del eje neutro y del bloque de compresión, mm.
    c: float
    a: float
    #: Deformación de la capa de armadura más traccionada.
    eps_t: float
    #: Tensión en la armadura traccionada (centroide) y comprimida, MPa (compresión > 0).
    fs: float
    fs_comp: float


def resistencia_flexion(
    b: float,
    d: float,
    As: float,
    mat: Materiales,
    *,
    As_comp: float = 0.0,
    d_comp: float = 0.0,
    dt: float | None = None,
) -> ResistenciaFlexion:
    """Resistencia a flexión de una sección rectangular (mm, mm², MPa → kN·m).

    ``d`` es la altura útil al centroide de la armadura traccionada ``As``; ``dt``,
    la de la capa más traccionada (por defecto ``d``); ``As_comp`` es la armadura
    comprimida, a ``d_comp`` de la fibra comprimida.
    """
    avisar()
    return _resistencia(b, d, As, mat, As_comp, d_comp, d if dt is None else dt)


def _resistencia(
    b: float, d: float, As: float, mat: Materiales, As_comp: float, d_comp: float, dt: float
) -> ResistenciaFlexion:
    if b <= 0 or d <= 0 or As < 0 or As_comp < 0:
        raise ValueError("b y d tienen que ser positivos y las áreas no negativas")
    if As_comp > 0 and not 0 < d_comp < d:
        raise ValueError("d_comp tiene que estar entre 0 y d")
    return ResistenciaFlexion(
        *_core.viga_resistencia(
            _core.VERSION_CONTRATO_DISENO, b, d, As, mat.fc, mat.fy, As_comp, d_comp, dt
        )
    )


@dataclass(frozen=True)
class ResultadoFlexion:
    """Resultado de :func:`armadura_flexion`. Áreas en mm², momentos en kN·m."""

    Mu: float
    #: Armadura traccionada necesaria por resistencia.
    As_req: float
    #: Armadura mínima de §9.6.1.2.
    As_min: float
    #: Armadura traccionada de diseño: ``max(As_req, min(As_min, 4/3·As_req))`` (§9.6.1.3).
    As: float
    #: Armadura comprimida necesaria (0 si alcanza con armadura simple).
    As_comp: float
    doble: bool
    #: Resistencia con ``As`` y ``As_comp``.
    resistencia: ResistenciaFlexion
    #: Límite de ``εt`` usado.
    eps_t_min: float


def armadura_flexion(
    Mu: float,
    b: float,
    d: float,
    mat: Materiales,
    *,
    dt: float | None = None,
    d_comp: float | None = None,
    eps_t_min: float | None = None,
) -> ResultadoFlexion:
    """Armadura de una sección rectangular para el momento último ``Mu`` (kN·m).

    Se usa el valor absoluto de ``Mu``; ``b`` y ``d`` en mm. Por defecto se exige
    que la sección quede **controlada por tracción** (``εt ≥ εty + 0.003``, φ = 0.90);
    ``eps_t_min`` puede bajarse hasta 0.004 (§9.3.3.1), con φ menor. Si la
    armadura simple no alcanza con ese límite, se agrega armadura de compresión a
    ``d_comp`` de la fibra comprimida (hace falta indicarlo).
    """
    avisar()
    dt = d if dt is None else dt
    if dt < d:
        raise ValueError("dt (capa más traccionada) no puede ser menor que d")
    lim = mat.eps_ty + 0.003 if eps_t_min is None else eps_t_min
    if lim < EPS_T_MIN_VIGAS:
        raise ValueError(f"eps_t_min = {lim}; en vigas el mínimo es 0.004 (§9.3.3.1)")
    mu = abs(Mu)
    as_min = armadura_minima(b, d, mat)

    # Armadura simple que deja exactamente εt = lim en la capa extrema y, si alcanza,
    # la armadura simple por bisección sobre el área (en Rust).
    as_lim, c_lim, t_lim, simple = _core.viga_armadura_simple(
        _core.VERSION_CONTRATO_DISENO, mu, b, d, dt, mat.fc, mat.fy, lim
    )
    r_lim = ResistenciaFlexion(*t_lim)
    if simple is not None:
        as_req, as_dis, t = simple  # As de diseño según §9.6.1.2 y §9.6.1.3
        return ResultadoFlexion(Mu, as_req, as_min, as_dis, 0.0, False, ResistenciaFlexion(*t), lim)

    if d_comp is None:
        raise ValueError(
            f"Mu = {mu:g} kN·m supera φMn = {r_lim.phiMn:.4g} kN·m con armadura simple y "
            f"εt ≥ {lim:g}: hace falta armadura de compresión (indicá d_comp) o una "
            "sección mayor"
        )
    if not 0 < d_comp < d:
        raise ValueError("d_comp tiene que estar entre 0 y d")
    # Doble armadura con el eje neutro fijo en c_lim: el par As'·f's / As2·fy toma el resto.
    a_lim = beta1(mat.fc) * c_lim
    fsc = min(mat.fy, ES * EPS_CU * (c_lim - d_comp) / c_lim)
    fsc_neto = fsc - (0.85 * mat.fc if a_lim > d_comp else 0.0)
    if fsc_neto <= 0:
        raise ValueError("la armadura de compresión está demasiado cerca del eje neutro")
    dmn = (mu / r_lim.phi - r_lim.Mn) * 1e6  # N·mm
    as_comp = dmn / (fsc_neto * (d - d_comp))
    as_req = as_lim + as_comp * fsc_neto / mat.fy
    as_dis = max(as_req, as_min)
    r = _resistencia(b, d, as_dis, mat, as_comp, d_comp, dt)
    return ResultadoFlexion(Mu, as_req, as_min, as_dis, as_comp, True, r, lim)


def separacion_libre_minima(d_b: float, d_agregado: float) -> float:
    """Separación libre mínima entre barras paralelas de una capa, mm (§25.2.1)."""
    return max(25.0, d_b, 4.0 / 3.0 * d_agregado)


def ancho_necesario(diametros: list[float], seccion: SeccionRectangular) -> float:
    """Ancho mínimo de viga para una capa de barras, mm (especificación §5.1)."""
    s = separacion_libre_minima(max(diametros), seccion.d_agregado)
    n = len(diametros)
    return 2 * (seccion.recubrimiento + seccion.d_estribo) + sum(diametros) + (n - 1) * s


@dataclass(frozen=True)
class DisposicionBarras:
    """Barras elegidas por :func:`elegir_barras`. Medidas en mm, áreas en mm²."""

    #: Diámetros de cada capa, empezando por la más cercana a la cara traccionada.
    capas: tuple[tuple[int, ...], ...]
    As: float
    d: float
    dt: float
    #: Ancho necesario de la capa más ancha y separación libre mínima usada.
    b_nec: float
    s_libre: float
    #: Armadura requerida con la ``d`` de esta disposición y su exceso relativo.
    As_req: float
    exceso: float
    resistencia: ResistenciaFlexion = field(repr=False)

    @property
    def descripcion(self) -> str:
        """Por ejemplo ``"3Ø20 + 2Ø16"`` o ``"capa 1: 4Ø25 · capa 2: 2Ø25"``."""

        def capa(ds: tuple[int, ...]) -> str:
            cuenta: dict[int, int] = {}
            for x in ds:
                cuenta[x] = cuenta.get(x, 0) + 1
            return " + ".join(f"{n}Ø{x}" for x, n in sorted(cuenta.items(), reverse=True))

        if len(self.capas) == 1:
            return capa(self.capas[0])
        return " · ".join(f"capa {i + 1}: {capa(c)}" for i, c in enumerate(self.capas))


def elegir_barras(
    Mu: float,
    seccion: SeccionRectangular,
    mat: Materiales,
    *,
    diametros: tuple[int, ...] = DIAMETROS_COMERCIALES,
    max_capas: int = 2,
    max_barras: int = 12,
    eps_t_min: float | None = None,
) -> DisposicionBarras:
    """Elige barras comerciales para ``Mu`` (kN·m) con armadura simple.

    Primero prueba una capa (uno o dos diámetros) y devuelve la disposición válida
    de **menor área** (a igualdad, menos barras). Solo si ninguna capa simple
    alcanza, prueba dos capas (un diámetro por capa). Válida significa: entra en el
    ancho con la separación libre de §25.2.1,
    ``φMn ≥ Mu`` con la ``d`` real de la disposición, ``εt`` sobre el límite y
    armadura mínima (§9.6.1.2-3). La segunda capa reduce ``d`` y eso se tiene en cuenta.
    """
    avisar()
    if max_capas not in (1, 2):
        raise ValueError("max_capas tiene que ser 1 o 2")
    mu = abs(Mu)
    lim = mat.eps_ty + 0.003 if eps_t_min is None else eps_t_min
    if lim < EPS_T_MIN_VIGAS:
        raise ValueError("en vigas eps_t_min no puede ser menor que 0.004 (§9.3.3.1)")
    elegida = _core.viga_elegir_barras(
        _core.VERSION_CONTRATO_DISENO, mu, seccion.b, seccion.h, seccion.recubrimiento,
        seccion.d_estribo, seccion.d_agregado, mat.fc, mat.fy, lim,
        np.asarray(diametros, dtype=np.float64), max_capas, max_barras,
    )  # fmt: skip
    if elegida is not None:
        indices, area, d, dt, b_nec, s_libre, as_req, t = elegida
        return DisposicionBarras(
            capas=tuple(tuple(diametros[i] for i in capa) for capa in indices),
            As=area,
            d=d,
            dt=dt,
            b_nec=b_nec,
            s_libre=s_libre,
            As_req=as_req,
            exceso=area / as_req - 1.0 if as_req > 0 else math.inf,
            resistencia=ResistenciaFlexion(*t),
        )
    raise ValueError(
        f"no hay una disposición de barras con armadura simple para Mu = {mu:g} kN·m en "
        f"{seccion.b:g} x {seccion.h:g} mm; agrandá la sección o usá armadura de compresión"
    )
