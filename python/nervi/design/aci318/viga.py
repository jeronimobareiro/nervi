# SPDX-License-Identifier: GPL-3.0-or-later
"""Diseño de una barra del modelo como viga, a partir de sus envolventes (experimental).

Usa :func:`nervi.design.envolvente`. Por defecto supone el modelo en **kN y m**;
si está en otras unidades, ``fuerza`` y ``longitud`` dicen cuáles y los esfuerzos
se convierten a kN·m y kN antes de diseñar. La sección y los materiales van en mm
y MPa.

- Flexión: el momento positivo máximo (tracciona abajo, ``-y`` local) da la
  armadura inferior y el negativo mínimo, la superior.
- Cortante: el cortante de diseño es el mayor en valor absoluto entre las
  secciones críticas a ``d`` de la cara de cada apoyo (ACI 318-19 §9.4.3.2). Quien
  usa la función es responsable de que se cumplan las condiciones de ese artículo
  (reacción que comprime la cara, sin cargas concentradas entre la cara y ``d``);
  si no, ``seccion_critica_a_d=False`` toma el máximo en toda la luz.
- Si la barra tiene axil importante (``|Nu| > 0.1 f'c Ag``), deja de ser una viga
  para §9.3.3.1 y se avisa.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass

import numpy as np

from ...modelo import Resultados
from ..envolvente import envolvente
from .cortante import Estribos, ResultadoCortante, armadura_cortante, elegir_estribos
from .flexion import DisposicionBarras, elegir_barras
from .materiales import DIAMETROS_COMERCIALES, Materiales, SeccionRectangular, avisar

#: Factores para pasar las unidades de ``modelo.json`` a kN y m (1 kgf = 9.80665 N).
A_KN = {"N": 1e-3, "kN": 1.0, "kgf": 9.80665e-3, "tf": 9.80665}
A_M = {"mm": 1e-3, "cm": 1e-2, "m": 1.0}


@dataclass(frozen=True)
class DisenoViga:
    """Resultado de :func:`disenar_viga`. Momentos en kN·m, cortantes en kN."""

    barra: int
    #: Momento positivo de diseño y combinación que lo produce.
    Mu_pos: float
    Mu_pos_comb: str
    #: Momento negativo de diseño (valor negativo) y su combinación.
    Mu_neg: float
    Mu_neg_comb: str
    #: Cortante de diseño (valor absoluto), su posición (m) y combinación.
    Vu: float
    x_Vu: float
    Vu_comb: str
    #: Barras inferiores y superiores (``None`` si ese momento no aparece).
    inferior: DisposicionBarras | None
    superior: DisposicionBarras | None
    #: Estribos (``None`` si no hacen falta por cálculo).
    estribos: Estribos | None
    #: Altura útil (mm) y verificación a cortante usadas para los estribos.
    d_cortante: float = 0.0
    cortante: ResultadoCortante | None = None


def disenar_viga(
    res: Resultados,
    barra: int,
    seccion: SeccionRectangular,
    mat: Materiales,
    *,
    combinaciones: list[str] | None = None,
    ancho_apoyo_i: float = 0.0,
    ancho_apoyo_j: float = 0.0,
    seccion_critica_a_d: bool = True,
    diametros: tuple[int, ...] = DIAMETROS_COMERCIALES,
    diametros_estribo: tuple[int, ...] | None = None,
    fuerza: str = "kN",
    longitud: str = "m",
) -> DisenoViga:
    """Armadura longitudinal y estribos de la barra ``barra`` con sus envolventes.

    ``ancho_apoyo_i`` y ``ancho_apoyo_j`` son los anchos de los apoyos (mm) en cada
    extremo, para ubicar su cara. Por defecto los estribos usan el diámetro
    ``seccion.d_estribo``, que es el mismo que se supuso para ubicar las barras.
    ``fuerza`` y ``longitud`` son las unidades del modelo (las de ``modelo.json``).
    """
    avisar()
    try:
        ff, fl = A_KN[fuerza], A_M[longitud]
    except KeyError:
        raise ValueError(f"unidades no reconocidas: {fuerza}, {longitud}") from None
    env = dict(envolvente(res, barra, combinaciones))
    env["x"] = env["x"] * fl
    for c, f in (("M", ff * fl), ("V", ff), ("N", ff)):
        env[f"{c}_max"] = env[f"{c}_max"] * f
        env[f"{c}_min"] = env[f"{c}_min"] * f
    x = env["x"]
    largo = float(x[-1])

    n_abs = float(np.max(np.abs(np.concatenate([env["N_max"], env["N_min"]]))))
    if n_abs * 1e3 > 0.1 * mat.fc * seccion.b * seccion.h:
        warnings.warn(
            f"la barra {barra} tiene |Nu| = {n_abs:.4g} kN > 0.1·f'c·Ag: no se comporta como "
            "viga (§9.3.3.1) y el diseño a flexión simple no aplica",
            UserWarning,
            stacklevel=2,
        )

    i_pos = int(np.argmax(env["M_max"]))
    i_neg = int(np.argmin(env["M_min"]))
    mu_pos, mu_neg = float(env["M_max"][i_pos]), float(env["M_min"][i_neg])
    # Momentos del orden del error de redondeo (por ejemplo en un apoyo simple) no cuentan.
    tol = 1e-9 * max(abs(mu_pos), abs(mu_neg), 1.0)
    inferior = elegir_barras(mu_pos, seccion, mat, diametros=diametros) if mu_pos > tol else None
    superior = elegir_barras(-mu_neg, seccion, mat, diametros=diametros) if mu_neg < -tol else None

    # Altura útil y cuantía para cortante: la menor de las disposiciones (conservador).
    disp = [r for r in (inferior, superior) if r is not None]
    if disp:
        d = min(r.d for r in disp)
        rho_w = min(r.As for r in disp) / (seccion.b * d)
    else:
        d = seccion.h - seccion.recubrimiento - seccion.d_estribo - 8.0
        rho_w = None

    v_abs = np.maximum(np.abs(env["V_max"]), np.abs(env["V_min"]))
    usa_max = np.abs(env["V_max"]) >= np.abs(env["V_min"])
    comb_v = np.where(usa_max, env["V_max_comb"], env["V_min_comb"])
    if seccion_critica_a_d:
        xi = (ancho_apoyo_i / 2.0 + d) / 1000.0
        xj = largo - (ancho_apoyo_j / 2.0 + d) / 1000.0
    else:
        xi, xj = 0.0, largo
    if xi >= xj:
        xi = xj = largo / 2.0
    # Valores en las secciones críticas, interpolando la envolvente de cada signo.
    candidatos = [
        (float(v_abs[k]), float(x[k]), str(comb_v[k])) for k in range(x.size) if xi <= x[k] <= xj
    ]
    for xc in (xi, xj):
        k = int(np.clip(np.searchsorted(x, xc), 1, x.size - 1))
        vmax = float(np.interp(xc, x, env["V_max"]))
        vmin = float(np.interp(xc, x, env["V_min"]))
        if abs(vmax) >= abs(vmin):
            candidatos.append((abs(vmax), xc, str(env["V_max_comb"][k])))
        else:
            candidatos.append((abs(vmin), xc, str(env["V_min_comb"][k])))
    vu, x_vu, vu_comb = max(candidatos, key=lambda c: c[0])

    estribos = elegir_estribos(
        vu,
        seccion.b,
        d,
        mat,
        rho_w=rho_w,
        diametros=(int(seccion.d_estribo),) if diametros_estribo is None else diametros_estribo,
    )
    cortante = (
        None if estribos is not None else armadura_cortante(vu, seccion.b, d, mat, rho_w=rho_w)
    )
    return DisenoViga(
        barra=barra,
        Mu_pos=mu_pos,
        Mu_pos_comb=str(env["M_max_comb"][i_pos]),
        Mu_neg=mu_neg,
        Mu_neg_comb=str(env["M_min_comb"][i_neg]),
        Vu=vu,
        x_Vu=x_vu,
        Vu_comb=vu_comb,
        inferior=inferior,
        superior=superior,
        estribos=estribos,
        d_cortante=d,
        cortante=estribos.requerido if estribos is not None else cortante,
    )
