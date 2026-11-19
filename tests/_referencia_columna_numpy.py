# SPDX-License-Identifier: GPL-3.0-or-later
"""Versión NumPy de la flexocompresión biaxial de columnas, como referencia.

Es el núcleo que tenía ``nervi.design.aci318.columna`` antes de pasar a Rust
(entrada de bitácora 2026-11-19-04), copiado sin cambios. Solo lo usa
``test_columna_rust.py`` para comparar la versión Rust durante la transición;
se puede borrar una versión después (ver ``docs/ESTADO.md``).
"""

from __future__ import annotations

import math

import numpy as np

from nervi.design.aci318.columna import phi_compresion
from nervi.design.aci318.flexion import beta1
from nervi.design.aci318.materiales import EPS_CU, ES

_N_THETA = 48
_IT_C = 42
_IT_THETA = 22


def _bloque(v: np.ndarray, u: np.ndarray, s: np.ndarray):
    """Área y momentos estáticos ``∫y dA``, ``∫z dA`` de ``{p ∈ polígono : u·p ≥ s}``.

    ``v`` (k, 2) convexo antihorario; ``u`` (M, 2) unitarios; ``s`` (M,). Recorte
    exacto del polígono con el semiplano, vectorizado sobre los M casos.
    """
    d = u @ v.T - s[:, None]  # (M, k): distancia con signo de cada vértice al corte
    d1 = np.roll(d, -1, axis=1)
    p0 = v[None, :, :]
    p1 = np.roll(v, -1, axis=0)[None, :, :]
    in0, in1 = d >= 0.0, d1 >= 0.0
    cambia = in0 != in1
    den = np.where(cambia, d - d1, 1.0)
    t = np.where(cambia, d / den, 0.0)[..., None]
    x = p0 + t * (p1 - p0)  # intersección del lado con el corte (si cambia de lado)
    a = np.where(in0[..., None], p0, x)
    b = np.where(in1[..., None], p1, x)
    tramo = (in0 | in1)[..., None]
    a = np.where(tramo, a, 0.0)
    b = np.where(tramo, b, 0.0)
    salida = (in0 & ~in1)[..., None]
    entrada = (~in0 & in1)[..., None]
    pe = np.where(salida, x, 0.0).sum(axis=1)  # punto donde el contorno sale del bloque
    pn = np.where(entrada, x, 0.0).sum(axis=1)  # punto donde vuelve a entrar
    # Lados del contorno dentro del bloque más el tramo del corte (de pe a pn).
    a = np.concatenate([a, pe[:, None, :]], axis=1)
    b = np.concatenate([b, pn[:, None, :]], axis=1)
    cr = a[..., 0] * b[..., 1] - b[..., 0] * a[..., 1]
    area = 0.5 * cr.sum(axis=1)
    sy = ((a[..., 0] + b[..., 0]) * cr).sum(axis=1) / 6.0
    sz = ((a[..., 1] + b[..., 1]) * cr).sum(axis=1) / 6.0
    return area, sy, sz


def _geo(seccion):
    return seccion.contorno, seccion.barras[:, :2], seccion.areas


def _agregar_eje(geo):
    v, pb, ab = geo
    if pb.ndim == 2:
        return geo
    return v, pb[..., None, :, :], ab[..., None, :]


def _seccion_en(geo, mat, theta, c, zunchada: bool):
    """Resultantes nominales para el eje neutro de inclinación ``theta`` y profundidad ``c``.

    ``u = (cos θ, sin θ)`` apunta hacia la fibra más comprimida. Devuelve ``Pn`` (N,
    compresión > 0), ``Mz`` y ``My`` (N·mm, convención del módulo), ``εt`` y ``φ``.
    """
    v, pb, ab = geo
    theta = np.asarray(theta, dtype=np.float64)
    c = np.asarray(c, dtype=np.float64)
    forma = np.broadcast_shapes(theta.shape, c.shape, pb.shape[:-2])
    theta, c = np.broadcast_to(theta, forma), np.broadcast_to(c, forma)
    u = np.stack([np.cos(theta), np.sin(theta)], axis=-1)  # forma + (2,)
    proy = u @ v.T
    s_max = proy.max(axis=-1)
    a = np.minimum(beta1(mat.fc) * c, s_max - proy.min(axis=-1))
    area, sy, sz = (r.reshape(forma) for r in _bloque(v, u.reshape(-1, 2), (s_max - a).ravel()))
    fc85 = 0.85 * mat.fc
    prof = s_max[..., None] - (u[..., None, :] * pb).sum(axis=-1)  # forma + (n,)
    eps = EPS_CU * (c[..., None] - prof) / c[..., None]
    fs = np.clip(ES * eps, -mat.fy, mat.fy) - np.where(prof <= a[..., None], fc85, 0.0)
    f = fs * ab
    pn = fc85 * area + f.sum(axis=-1)
    mz = fc85 * sy + (f * pb[..., 0]).sum(axis=-1)
    my = -(fc85 * sz + (f * pb[..., 1]).sum(axis=-1))
    dt = np.where(ab > 0, prof, -np.inf).max(axis=-1)  # barra más traccionada
    eps_t = EPS_CU * (dt - c) / c
    phi = np.asarray(phi_compresion(eps_t, mat.fy, zunchada))
    return pn, mz, my, eps_t, phi


def _profundidad_para(geo, mat, theta, p_obj, zunchada):
    """Profundidad ``c`` del eje neutro con ``φPn = p_obj`` (N), por bisección logarítmica.

    Devuelve ``c`` y una máscara de los casos con solución.
    """
    u = np.stack([np.cos(theta), np.sin(theta)], axis=-1)
    proy = u @ geo[0].T
    h = proy.max(axis=-1) - proy.min(axis=-1)
    lo = np.log(1e-6 * h)
    hi = np.log(1e4 * h)

    def f(logc):
        pn, _, _, _, phi = _seccion_en(geo, mat, theta, np.exp(logc), zunchada)
        return phi * pn - p_obj

    ok = (f(lo) <= 0.0) & (f(hi) >= 0.0)
    for _ in range(_IT_C):
        mid = 0.5 * (lo + hi)
        neg = f(mid) < 0.0
        lo = np.where(neg, mid, lo)
        hi = np.where(neg, hi, mid)
    return np.exp(0.5 * (lo + hi)), ok


def _capacidad_en_direccion(geo, mat, p_obj, alfa, zunchada):
    """Resistencia de diseño con ``φPn = p_obj`` (N) en la dirección ``alfa`` del
    plano ``(Mz, My)``. Vectorizado sobre ``p_obj`` y ``alfa`` (y sobre las armaduras
    si ``geo`` trae varias). Devuelve ``φMn`` (N·mm), ``θ``, ``c`` y ``ok``.

    Primero recorre :data:`_N_THETA` inclinaciones del eje neutro hasta encontrar
    dos vecinas cuyo momento resistente queda a cada lado de ``alfa``; después
    ajusta la inclinación por bisección.
    """
    p_obj = np.asarray(p_obj, dtype=np.float64)
    alfa = np.asarray(alfa, dtype=np.float64)
    forma = np.broadcast_shapes(p_obj.shape, alfa.shape, geo[1].shape[:-2])
    p_obj, alfa = np.broadcast_to(p_obj, forma), np.broadcast_to(alfa, forma)
    dz, dy = np.cos(alfa), np.sin(alfa)
    geo_g = _agregar_eje(geo)
    th = np.broadcast_to(2.0 * math.pi * np.arange(_N_THETA) / _N_THETA, (*forma, _N_THETA))
    pp = p_obj[..., None]
    c, ok = _profundidad_para(geo_g, mat, th, pp, zunchada)
    _, mz, my, _, phi = _seccion_en(geo_g, mat, th, c, zunchada)
    mz, my = phi * mz, phi * my
    cruz = mz * dy[..., None] - my * dz[..., None]
    punto = mz * dz[..., None] + my * dy[..., None]
    cruz1, ok1 = np.roll(cruz, -1, axis=-1), np.roll(ok, -1, axis=-1)
    cand = ok & ok1 & (np.sign(cruz) != np.sign(cruz1)) & (punto > 0)
    tiene = cand.any(axis=-1)
    j = np.argmax(cand, axis=-1)
    paso = 2.0 * math.pi / _N_THETA
    t0 = j * paso
    t1 = t0 + paso
    f0 = np.take_along_axis(cruz, j[..., None], axis=-1)[..., 0]
    for _ in range(_IT_THETA):
        tm = 0.5 * (t0 + t1)
        cm, _ = _profundidad_para(geo, mat, tm, p_obj, zunchada)
        _, mzm, mym, _, phim = _seccion_en(geo, mat, tm, cm, zunchada)
        fm = phim * (mzm * dy - mym * dz)
        mismo = np.sign(fm) == np.sign(f0)
        t0 = np.where(mismo, tm, t0)
        f0 = np.where(mismo, fm, f0)
        t1 = np.where(mismo, t1, tm)
    tf = 0.5 * (t0 + t1)
    cf, okf = _profundidad_para(geo, mat, tf, p_obj, zunchada)
    _, mzf, myf, _, phif = _seccion_en(geo, mat, tf, cf, zunchada)
    cap = phif * (mzf * dz + myf * dy)
    valido = tiene & okf
    return np.where(valido, cap, 0.0), tf, cf, valido


def _razones(geo, mat, pu, mz, my, zunchada, phi_pn_max, phi_pnt):
    """``(φMn, razón de momento, razón axial, razón)`` en kN·m y adimensionales."""
    mu = np.hypot(mz, my)
    alfa = np.arctan2(my, mz)
    cap, _, _, ok = _capacidad_en_direccion(geo, mat, pu * 1e3, alfa, zunchada)
    cap = cap / 1e6
    hay_momento = mu > 1e-9
    with np.errstate(divide="ignore", invalid="ignore"):
        r_m = np.where(ok & (cap > 0), mu / np.where(cap > 0, cap, 1.0), np.inf)
    # Sin momento, manda la razón axial; con momento y una carga fuera de la
    # superficie de interacción, la razón es infinita.
    r_m = np.where(hay_momento, r_m, 0.0)
    r_a = np.where(pu >= 0.0, pu / phi_pn_max, -pu / phi_pnt)
    return np.where(ok, cap, 0.0), r_m, r_a, np.maximum(r_m, r_a)
