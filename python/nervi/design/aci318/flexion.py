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
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from itertools import combinations

from .materiales import (
    DIAMETROS_COMERCIALES,
    EPS_CU,
    ES,
    Materiales,
    SeccionRectangular,
    area_barra,
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
    fc, fy, b1 = mat.fc, mat.fy, beta1(mat.fc)

    def tension(eps: float) -> float:  # §20.2.2.1, elastoplástico
        return max(-fy, min(fy, ES * eps))

    def fuerzas(c: float) -> tuple[float, float, float, float]:
        a = b1 * c
        cc = 0.85 * fc * b * a  # §22.2.2.4.1
        fs = tension(EPS_CU * (d - c) / c)  # tracción > 0
        fsc = tension(EPS_CU * (c - d_comp) / c) if As_comp else 0.0  # compresión > 0
        # Si la barra comprimida está dentro del bloque, se descuenta el hormigón que desplaza.
        cs = As_comp * (fsc - (0.85 * fc if a > d_comp else 0.0))
        return cc + cs - As * fs, a, fs, fsc

    if As == 0.0:
        return ResistenciaFlexion(0.0, 0.9, 0.0, 0.0, 0.0, math.inf, 0.0, 0.0)
    lo, hi = 1e-9 * d, d
    while fuerzas(hi)[0] < 0:  # en secciones muy armadas el eje neutro baja de d
        hi *= 2.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if fuerzas(mid)[0] < 0:
            lo = mid
        else:
            hi = mid
        if hi - lo < 1e-10 * d:
            break
    c = 0.5 * (lo + hi)
    _, a, fs, fsc = fuerzas(c)
    cc = 0.85 * fc * b * a
    cs = As_comp * (fsc - (0.85 * fc if a > d_comp else 0.0))
    mn = (cc * (d - a / 2.0) + cs * (d - d_comp)) / 1e6  # N·mm → kN·m
    eps_t = EPS_CU * (dt - c) / c
    phi = phi_flexion(eps_t, fy)
    return ResistenciaFlexion(mn, phi, phi * mn, c, a, eps_t, fs, fsc)


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

    # Armadura simple que deja exactamente εt = lim en la capa extrema.
    c_lim = EPS_CU * dt / (EPS_CU + lim)
    as_lim = 0.85 * mat.fc * b * beta1(mat.fc) * c_lim / mat.fy
    r_lim = _resistencia(b, d, as_lim, mat, 0.0, 0.0, dt)

    if mu <= r_lim.phiMn:
        lo, hi = 0.0, as_lim
        for _ in range(200):
            mid = 0.5 * (lo + hi)
            if _resistencia(b, d, mid, mat, 0.0, 0.0, dt).phiMn < mu:
                lo = mid
            else:
                hi = mid
            if hi - lo < 1e-9 * as_lim:
                break
        as_req = hi
        as_dis = max(as_req, min(as_min, 4.0 / 3.0 * as_req))  # §9.6.1.2 y §9.6.1.3
        r = _resistencia(b, d, as_dis, mat, 0.0, 0.0, dt)
        return ResultadoFlexion(Mu, as_req, as_min, as_dis, 0.0, False, r, lim)

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


def _candidatas_una_capa(diametros: tuple[int, ...], max_barras: int):
    """Un diámetro, o dos con el mayor en las esquinas (al menos dos barras)."""
    for db in diametros:
        for n in range(2, max_barras + 1):
            yield ((db,) * n,)
    for d1, d2 in combinations(sorted(diametros, reverse=True), 2):
        for n1 in range(2, max_barras):
            for n2 in range(1, max_barras - n1 + 1):
                yield ((d1,) * n1 + (d2,) * n2,)


def _candidatas_dos_capas(diametros: tuple[int, ...], max_barras: int):
    """Un diámetro por capa, el de la segunda no mayor; la segunda capa va alineada
    sobre la primera, con al menos dos barras y no más que la primera."""
    for d1 in diametros:
        for d2 in (x for x in diametros if x <= d1):
            for n1 in range(2, max_barras - 1):
                for n2 in range(2, min(n1, max_barras - n1) + 1):
                    yield ((d1,) * n1, (d2,) * n2)


def _geometria(capas, seccion: SeccionRectangular) -> tuple[float, float, float]:
    """Área, altura útil al centroide y a la capa extrema."""
    base = seccion.recubrimiento + seccion.d_estribo
    area = momento = 0.0
    y_min = math.inf
    y_capa = base  # cara inferior de la capa actual
    for capa in capas:
        dmax = max(capa)
        for db in capa:
            y = y_capa + db / 2.0
            a = area_barra(db)
            area += a
            momento += a * y
            y_min = min(y_min, y)
        y_capa += dmax + SEPARACION_ENTRE_CAPAS  # §25.2.2, barras alineadas
    return area, seccion.h - momento / area, seccion.h - y_min


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
    familias = [_candidatas_una_capa(tuple(diametros), max_barras)]
    if max_capas == 2:
        familias.append(_candidatas_dos_capas(tuple(diametros), max_barras))
    requerida: dict[tuple[float, float], ResultadoFlexion | None] = {}
    for familia in familias:
        elegida = _mejor_disposicion(familia, mu, seccion, mat, lim, requerida)
        if elegida is not None:
            return elegida
    raise ValueError(
        f"no hay una disposición de barras con armadura simple para Mu = {mu:g} kN·m en "
        f"{seccion.b:g} x {seccion.h:g} mm; agrandá la sección o usá armadura de compresión"
    )


def _mejor_disposicion(familia, mu, seccion, mat, lim, requerida) -> DisposicionBarras | None:
    cands = []
    for capas in familia:
        area, d, dt = _geometria(capas, seccion)
        cands.append((area, sum(len(c) for c in capas), capas, d, dt))
    cands.sort(key=lambda c: c[:2])
    for area, _, capas, d, dt in cands:
        b_nec = max(ancho_necesario(list(c), seccion) for c in capas)
        if b_nec > seccion.b + 1e-9:
            continue
        clave = (round(d, 6), round(dt, 6))
        if clave not in requerida:
            try:
                requerida[clave] = armadura_flexion(mu, seccion.b, d, mat, dt=dt, eps_t_min=lim)
            except ValueError:
                requerida[clave] = None
        req = requerida[clave]
        if req is None or area < req.As - 1e-9:
            continue
        r = _resistencia(seccion.b, d, area, mat, 0.0, 0.0, dt)
        if r.phiMn < mu - 1e-9 or r.eps_t < lim - 1e-12:
            continue
        s = separacion_libre_minima(max(max(c) for c in capas), seccion.d_agregado)
        return DisposicionBarras(
            capas=capas,
            As=area,
            d=d,
            dt=dt,
            b_nec=b_nec,
            s_libre=s,
            As_req=req.As_req,
            exceso=area / req.As_req - 1.0 if req.As_req > 0 else math.inf,
            resistencia=r,
        )
    return None
