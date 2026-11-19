# SPDX-License-Identifier: GPL-3.0-or-later
"""Columnas de hormigón armado según ACI 318-19: flexocompresión biaxial y esbeltez.

Issue #24. **Experimental**: no fue revisado por un ingeniero estructural.

Unidades: mm y MPa en secciones y materiales; kN y kN·m en esfuerzos (un modelo
armado en kN y m).

Ejes y signos de la sección
---------------------------
La sección se describe en los ejes locales ``y, z`` de la barra (los de
:class:`nervi.Modelo3D`), con el origen en el baricentro de la sección bruta.

- ``Pu`` es positivo en **compresión** (al revés que ``N`` del modelo: ``Pu = -N``).
- ``Mz`` sigue la convención del modelo: positivo si tracciona la fibra ``-y``
  (comprime la ``+y``). En el pórtico plano es ``M``.
- ``My`` sigue la convención del modelo: positivo si tracciona la fibra ``+z``
  (comprime la ``-z``).

Método (ACI 318-19; se implementa el método y se cita el artículo)
-------------------------------------------------------------------
- Hipótesis de §22.2: secciones planas, ``εcu = 0.003`` (§22.2.2.1), bloque
  rectangular de ``0.85 f'c`` hasta la profundidad ``a = β1 c`` medida en
  perpendicular al eje neutro (§22.2.2.4), acero elastoplástico (§20.2.2.1). El
  eje neutro puede tener cualquier inclinación (flexión biaxial, §22.4.1).
- El bloque de compresión se integra **exactamente** recortando el contorno de
  la sección (un polígono convexo) con el semiplano ``profundidad ≤ a``. Las
  barras son fibras puntuales; las que caen dentro del bloque descuentan el
  hormigón que desplazan. La sección circular se representa con un polígono de
  :data:`LADOS_CIRCULO` lados de igual área que el círculo.
- ``φ`` según ``εt`` de la barra más traccionada (§21.2.2): 0.65 con estribos o
  0.75 con zuncho en compresión controlada, 0.90 controlada por tracción, lineal
  entre ambos.
- Compresión máxima ``φPn,max = φ·0.80·Po`` con estribos y ``φ·0.85·Po`` con
  zuncho (§22.4.2.1), ``Po = 0.85 f'c (Ag − Ast) + fy Ast`` (§22.4.2.2). Tracción
  pura ``φPnt = 0.90 fy Ast`` (§22.4.3.1).
- Verificación de una solicitación ``(Pu, Mz, My)``: se busca, con ``Pu`` fijo,
  la resistencia de diseño en la misma dirección del momento (curva de
  interacción a carga constante). La razón demanda/capacidad es la mayor entre
  ``|Mu|/φMn`` y ``Pu/φPn,max`` (o ``|Pu|/φPnt`` en tracción).
- Cuantía ``0.01 ≤ ρ ≤ 0.08`` (§10.6.1.1), cantidad mínima de barras (§10.7.3.1)
  y separación libre mínima entre barras longitudinales de columnas (§25.2.3).

Esbeltez por magnificación de momentos (§6.6.4), porque Nervi todavía no tiene
análisis P-Δ:

- Se desprecia si ``k·lu/r ≤ 34 + 12·M1/M2`` y ``≤ 40`` en pórticos no
  desplazables, o ``k·lu/r ≤ 22`` en desplazables (§6.2.5.1), con ``M1/M2``
  negativo en curvatura simple; ``r = 0.30 h`` en rectángulos, ``0.25 D`` en
  círculos (§6.2.5.2) y ``√(Ig/Ag)`` en otras formas.
- No desplazables (§6.6.4.5): ``δ = Cm / (1 − Pu/(0.75 Pc)) ≥ 1``,
  ``Pc = π² (EI)eff / (k lu)²`` (§6.6.4.4.2), ``(EI)eff = 0.4 Ec Ig / (1 + βdns)``
  (§6.6.4.4.4a), ``Ec = 4700 √f'c`` (§19.2.2.1b), ``Cm = 0.6 − 0.4 M1/M2`` sin
  cargas transversales y 1.0 con ellas (§6.6.4.5.3), y momento mínimo
  ``M2,min = Pu (15 + 0.03 h)`` en mm (§6.6.4.5.4), con ``Cm = 1`` si manda.
- Desplazables (§6.6.4.6): Nervi no calcula ``δs`` (hace falta el índice de
  estabilidad del piso o un análisis P-Δ); quien diseña lo da con ``delta_s`` y
  se aplica, del lado seguro, a todo el momento de la barra en ese eje.
- Se avisa si el momento de segundo orden supera 1.4 veces el de primer orden
  (§6.2.5.3).
"""

from __future__ import annotations

import math
import warnings
from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np

from ... import _core
from .materiales import ES, Materiales, area_barra, avisar

#: Lados del polígono que representa una sección circular.
LADOS_CIRCULO = 96
#: Diámetros de barra longitudinal que prueba :func:`elegir_armadura_columna`, mm.
DIAMETROS_COLUMNA: tuple[int, ...] = (12, 16, 20, 25, 32)
#: Cuantías mínima y máxima de armadura longitudinal (§10.6.1.1).
CUANTIA_MIN = 0.01
CUANTIA_MAX = 0.08


# --- Sección ---------------------------------------------------------------------


def _propiedades_poligono(v: np.ndarray) -> tuple[float, float, float, float, float]:
    """Área, centroide ``(y, z)`` e inercias ``Iz = ∫y² dA``, ``Iy = ∫z² dA`` (origen)."""
    y, z = v[:, 0], v[:, 1]
    y1, z1 = np.roll(y, -1), np.roll(z, -1)
    cr = y * z1 - y1 * z
    a = 0.5 * cr.sum()
    yc = ((y + y1) * cr).sum() / (6.0 * a)
    zc = ((z + z1) * cr).sum() / (6.0 * a)
    iz = ((y * y + y * y1 + y1 * y1) * cr).sum() / 12.0
    iy = ((z * z + z * z1 + z1 * z1) * cr).sum() / 12.0
    return float(a), float(yc), float(zc), float(iz), float(iy)


class SeccionColumna:
    """Sección de columna: contorno convexo de hormigón y barras puntuales (mm).

    ``contorno`` es un arreglo ``(k, 2)`` de vértices ``(y, z)`` y ``barras`` uno
    ``(n, 3)`` con ``(y, z, diámetro)``. El origen se traslada al baricentro de la
    sección bruta. Conviene construirla con :meth:`rectangular` o :meth:`circular`.
    """

    def __init__(
        self,
        contorno: np.ndarray,
        barras: np.ndarray,
        *,
        forma: str = "general",
        dimensiones: dict[str, float] | None = None,
        recubrimiento: float = 40.0,
        d_estribo: float = 10.0,
        d_agregado: float = 19.0,
    ) -> None:
        v = np.asarray(contorno, dtype=np.float64).reshape(-1, 2)
        b = np.asarray(barras, dtype=np.float64).reshape(-1, 3)
        if v.shape[0] < 3:
            raise ValueError("el contorno necesita al menos 3 vértices")
        a, yc, zc, _, _ = _propiedades_poligono(v)
        if a < 0:  # se ordena en sentido antihorario
            v = v[::-1].copy()
            a = -a
        if a <= 0:
            raise ValueError("el contorno no tiene área")
        e1, e2 = np.roll(v, -1, 0) - v, np.roll(v, -2, 0) - np.roll(v, -1, 0)
        cruz = e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0]
        if np.any(cruz < -1e-9 * a):
            raise ValueError("el contorno tiene que ser convexo")
        if b.shape[0] == 0:
            raise ValueError("la sección no tiene barras")
        if np.any(b[:, 2] <= 0):
            raise ValueError("los diámetros de las barras tienen que ser positivos")
        self.contorno = v - (yc, zc)
        self.barras = b - (yc, zc, 0.0)
        self.forma = forma
        self.dimensiones = dict(dimensiones or {})
        self.recubrimiento = float(recubrimiento)
        self.d_estribo = float(d_estribo)
        self.d_agregado = float(d_agregado)
        _, _, _, self.Iz, self.Iy = _propiedades_poligono(self.contorno)
        self.Ag = a
        self.areas = area_barra(self.barras[:, 2])
        fuera = ~self._contiene(self.barras[:, 0], self.barras[:, 1])
        if fuera.any():
            yb, zb = self.barras[int(np.argmax(fuera)), :2]
            raise ValueError(f"la barra en ({yb:.1f}, {zb:.1f}) queda fuera del hormigón")

    def _contiene(self, y, z) -> np.ndarray:
        """Si cada punto ``(y, z)`` está dentro del contorno (o en el borde)."""
        v = self.contorno
        e = np.roll(v, -1, 0) - v
        y, z = np.asarray(y, dtype=np.float64)[:, None], np.asarray(z, dtype=np.float64)[:, None]
        return np.all(e[:, 0] * (z - v[:, 1]) - e[:, 1] * (y - v[:, 0]) >= -1e-9, axis=1)

    # --- Constructores ---------------------------------------------------------
    @classmethod
    def rectangular(
        cls,
        hy: float,
        hz: float,
        n_y: int = 2,
        n_z: int = 2,
        diametro: float = 16.0,
        *,
        recubrimiento: float = 40.0,
        d_estribo: float = 10.0,
        d_agregado: float = 19.0,
    ) -> SeccionColumna:
        """Rectángulo de ``hy`` (según ``y`` local) por ``hz`` (según ``z``), en mm.

        Las barras van en el perímetro, todas del mismo ``diametro``: ``n_y`` en
        cada cara paralela a ``y`` (las de ``z = ±hz/2``) y ``n_z`` en cada cara
        paralela a ``z``, contando las esquinas en ambas. En total,
        ``2·n_y + 2·n_z − 4`` barras. ``recubrimiento`` es el libre hasta el estribo.
        """
        if hy <= 0 or hz <= 0:
            raise ValueError("hy y hz tienen que ser positivos (mm)")
        if n_y < 2 or n_z < 2:
            raise ValueError("hacen falta al menos 2 barras por cara (4 en total, §10.7.3.1)")
        e = recubrimiento + d_estribo + diametro / 2.0
        ey, ez = hy / 2.0 - e, hz / 2.0 - e
        if ey <= 0 or ez <= 0:
            raise ValueError("el recubrimiento y el estribo no dejan lugar para las barras")
        pos = set()
        for y in np.linspace(-ey, ey, n_y):
            pos.add((round(float(y), 9), ez))
            pos.add((round(float(y), 9), -ez))
        for z in np.linspace(-ez, ez, n_z):
            pos.add((ey, round(float(z), 9)))
            pos.add((-ey, round(float(z), 9)))
        barras = np.array([(y, z, diametro) for y, z in sorted(pos)])
        contorno = np.array(
            [(-hy / 2, -hz / 2), (hy / 2, -hz / 2), (hy / 2, hz / 2), (-hy / 2, hz / 2)]
        )
        return cls(
            contorno,
            barras,
            forma="rectangular",
            dimensiones={"hy": hy, "hz": hz, "n_y": n_y, "n_z": n_z, "diametro": diametro},
            recubrimiento=recubrimiento,
            d_estribo=d_estribo,
            d_agregado=d_agregado,
        )

    @classmethod
    def circular(
        cls,
        D: float,
        n_barras: int = 6,
        diametro: float = 16.0,
        *,
        recubrimiento: float = 40.0,
        d_estribo: float = 10.0,
        d_agregado: float = 19.0,
    ) -> SeccionColumna:
        """Círculo de diámetro ``D`` (mm) con ``n_barras`` iguales repartidas en una
        circunferencia, la primera sobre el eje ``+y``."""
        if D <= 0:
            raise ValueError("D tiene que ser positivo (mm)")
        if n_barras < 4:
            raise ValueError("hacen falta al menos 4 barras (6 con zuncho, §10.7.3.1)")
        rb = D / 2.0 - recubrimiento - d_estribo - diametro / 2.0
        if rb <= 0:
            raise ValueError("el recubrimiento y el estribo no dejan lugar para las barras")
        n = LADOS_CIRCULO
        # Radio del polígono de igual área que el círculo.
        rp = D / 2.0 * math.sqrt(2.0 * math.pi / (n * math.sin(2.0 * math.pi / n)))
        t = 2.0 * math.pi * np.arange(n) / n + math.pi / n
        contorno = np.column_stack([rp * np.cos(t), rp * np.sin(t)])
        tb = 2.0 * math.pi * np.arange(n_barras) / n_barras
        barras = np.column_stack([rb * np.cos(tb), rb * np.sin(tb), np.full(n_barras, diametro)])
        return cls(
            contorno,
            barras,
            forma="circular",
            dimensiones={"D": D, "n_barras": n_barras, "diametro": diametro},
            recubrimiento=recubrimiento,
            d_estribo=d_estribo,
            d_agregado=d_agregado,
        )

    def con_barras(self, cantidad: tuple[int, ...] | int, diametro: float) -> SeccionColumna:
        """La misma sección rectangular o circular con otra armadura.

        ``cantidad`` es ``(n_y, n_z)`` en la rectangular y ``n_barras`` en la circular.
        """
        kw = {
            "recubrimiento": self.recubrimiento,
            "d_estribo": self.d_estribo,
            "d_agregado": self.d_agregado,
        }
        if self.forma == "rectangular":
            n_y, n_z = cantidad  # type: ignore[misc]
            return SeccionColumna.rectangular(
                self.dimensiones["hy"], self.dimensiones["hz"], n_y, n_z, diametro, **kw
            )
        if self.forma == "circular":
            return SeccionColumna.circular(self.dimensiones["D"], int(cantidad), diametro, **kw)
        raise ValueError("solo se cambia la armadura de secciones rectangulares o circulares")

    # --- Propiedades -----------------------------------------------------------
    @property
    def Ast(self) -> float:
        """Área total de armadura longitudinal, mm²."""
        return float(self.areas.sum())

    @property
    def cuantia(self) -> float:
        """``ρ = Ast/Ag``."""
        return self.Ast / self.Ag

    def altura(self, eje: str) -> float:
        """Dimensión de la sección en la dirección de la flexión: ``eje="z"`` (``Mz``)
        es la extensión según ``y``; ``eje="y"`` (``My``), según ``z``."""
        k = 0 if eje == "z" else 1
        return float(np.ptp(self.contorno[:, k]))

    def inercia(self, eje: str) -> float:
        """Inercia bruta para flexión alrededor de ``eje`` (``"z"`` o ``"y"``), mm⁴."""
        return self.Iz if eje == "z" else self.Iy

    def radio_giro(self, eje: str) -> float:
        """Radio de giro de §6.2.5.2: 0.30 h (rectángulo), 0.25 D (círculo) o √(Ig/Ag)."""
        if self.forma == "rectangular":
            return 0.30 * self.altura(eje)
        if self.forma == "circular":
            return 0.25 * self.dimensiones["D"]
        return math.sqrt(self.inercia(eje) / self.Ag)

    def separacion_libre(self) -> float:
        """Menor separación libre entre barras longitudinales vecinas, mm."""
        p = self.barras
        if p.shape[0] < 2:
            return math.inf
        dist = np.hypot(p[:, None, 0] - p[None, :, 0], p[:, None, 1] - p[None, :, 1])
        libre = dist - (p[:, None, 2] + p[None, :, 2]) / 2.0
        np.fill_diagonal(libre, np.inf)
        return float(libre.min())

    @property
    def descripcion(self) -> str:
        """Por ejemplo ``'8Ø20 (ρ = 1.40 %)'``."""
        ds = sorted({float(d) for d in self.barras[:, 2]}, reverse=True)
        partes = [f"{int(np.sum(self.barras[:, 2] == d))}Ø{d:g}" for d in ds]
        return " + ".join(partes) + f" (ρ = {100 * self.cuantia:.2f} %)"

    def __repr__(self) -> str:
        return f"SeccionColumna({self.forma}, {self.dimensiones}, {self.descripcion})"


def separacion_libre_minima_columna(d_b: float, d_agregado: float) -> float:
    """Separación libre mínima entre barras longitudinales de columnas, mm (§25.2.3)."""
    return max(40.0, 1.5 * d_b, 4.0 / 3.0 * d_agregado)


def phi_compresion(eps_t, fy: float, zunchada: bool = False):
    """``φ`` para flexocompresión sin pretensado según ``εt`` (§21.2.2).

    Acepta escalares o arreglos. ``zunchada`` elige 0.75 (zuncho) en vez de 0.65.
    """
    phi_c = 0.75 if zunchada else 0.65
    eps_ty = fy / ES
    t = np.clip((np.asarray(eps_t, dtype=np.float64) - eps_ty) / 0.003, 0.0, 1.0)
    salida = phi_c + (0.90 - phi_c) * t
    return float(salida) if np.ndim(salida) == 0 else salida


@dataclass(frozen=True)
class ResistenciaAxial:
    """Resistencias axiales de la sección, kN."""

    Po: float
    #: ``φPn,max`` (§22.4.2.1).
    phiPn_max: float
    #: Tracción pura nominal y de diseño (§22.4.3.1).
    Pnt: float
    phiPnt: float


def resistencia_axial(
    seccion: SeccionColumna, mat: Materiales, zunchada: bool = False
) -> ResistenciaAxial:
    """``Po``, ``φPn,max`` y ``φPnt`` de la sección (§22.4.2 y §22.4.3), kN."""
    po = 0.85 * mat.fc * (seccion.Ag - seccion.Ast) + mat.fy * seccion.Ast
    phi_c, alfa = (0.75, 0.85) if zunchada else (0.65, 0.80)
    pnt = mat.fy * seccion.Ast
    return ResistenciaAxial(po / 1e3, phi_c * alfa * po / 1e3, pnt / 1e3, 0.90 * pnt / 1e3)


# --- Integración de la sección (núcleo en Rust) -------------------------------------
#
# El cálculo está en ``nervi_core::diseno::columna`` (crate ``nervi-core``): recorte
# exacto del bloque comprimido, profundidad del eje neutro por bisección
# logarítmica, búsqueda de la inclinación y razones demanda/capacidad. Estas
# funciones solo arman los arreglos y devuelven los resultados con la forma de
# la entrada.


def _f64(x) -> np.ndarray:
    return np.asarray(x, dtype=np.float64)


def _contiguos(*arreglos) -> tuple[np.ndarray, ...]:
    return tuple(np.ascontiguousarray(a, dtype=np.float64) for a in arreglos)


def _geo(seccion: SeccionColumna) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """``(contorno, barras (n, 2), áreas (n,))`` de la sección."""
    return seccion.contorno, seccion.barras[:, :2], seccion.areas


def _seccion_en(geo, mat: Materiales, theta, c, zunchada: bool):
    """Resultantes nominales para el eje neutro de inclinación ``theta`` y profundidad ``c``.

    ``u = (cos θ, sin θ)`` apunta hacia la fibra más comprimida. Devuelve ``Pn`` (N,
    compresión > 0), ``Mz`` y ``My`` (N·mm, convención del módulo), ``εt`` y ``φ``,
    con la forma de ``theta`` y ``c``.
    """
    v, pb, ab = geo
    theta, c = np.broadcast_arrays(_f64(theta), _f64(c))
    r = _core.columna_seccion_en(
        _core.VERSION_CONTRATO_DISENO, *_contiguos(v, pb, ab),
        mat.fc, mat.fy, zunchada, *_contiguos(theta.ravel(), c.ravel()),
    )  # fmt: skip
    return tuple(r[k].reshape(theta.shape) for k in ("pn", "mz", "my", "eps_t", "phi"))


def _capacidad_en_direccion(geo, mat, p_obj, alfa, zunchada):
    """Resistencia de diseño con ``φPn = p_obj`` (N) en la dirección ``alfa`` del
    plano ``(Mz, My)``. Devuelve ``φMn`` (N·mm), ``θ``, ``c`` y ``ok``.

    Primero recorre 48 inclinaciones del eje neutro hasta encontrar dos vecinas
    cuyo momento resistente queda a cada lado de ``alfa``; después ajusta la
    inclinación por bisección.
    """
    v, pb, ab = geo
    p_obj, alfa = np.broadcast_arrays(_f64(p_obj), _f64(alfa))
    cap, tf, cf, ok = _core.columna_capacidad(
        _core.VERSION_CONTRATO_DISENO, *_contiguos(v, pb, ab),
        mat.fc, mat.fy, zunchada, *_contiguos(p_obj.ravel(), alfa.ravel()),
    )  # fmt: skip
    forma = p_obj.shape
    return cap.reshape(forma), tf.reshape(forma), cf.reshape(forma), ok.reshape(forma)


def _razones(geo, mat, pu, mz, my, zunchada, phi_pn_max, phi_pnt):
    """``(φMn, razón de momento, razón axial, razón)`` en kN·m y adimensionales.

    Sin momento manda la razón axial; con momento y una carga fuera de la
    superficie de interacción, la razón de momento es infinita.
    """
    v, pb, ab = geo
    pu, mz, my = np.broadcast_arrays(_f64(pu), _f64(mz), _f64(my))
    sol = np.ascontiguousarray(np.stack([pu.ravel(), mz.ravel(), my.ravel()], axis=1))
    salida = _core.columna_razones(
        _core.VERSION_CONTRATO_DISENO, *_contiguos(v, pb, ab),
        mat.fc, mat.fy, zunchada, sol, float(phi_pn_max), float(phi_pnt),
    )  # fmt: skip
    return tuple(x.reshape(pu.shape) for x in salida)


# --- Verificación de solicitaciones ------------------------------------------------


@dataclass(frozen=True)
class VerificacionColumna:
    """Resultado de :func:`verificar_columna` (kN y kN·m). Los campos son arreglos
    si las solicitaciones lo son."""

    Pu: np.ndarray
    Mz: np.ndarray
    My: np.ndarray
    #: Resistencia de diseño a flexión con ``Pu`` fijo, en la dirección de ``Mu``.
    phiMn: np.ndarray
    #: ``|Mu| / φMn``; infinito si ``Pu`` queda fuera de la superficie de interacción.
    razon_momento: np.ndarray
    #: ``Pu/φPn,max`` en compresión o ``|Pu|/φPnt`` en tracción.
    razon_axial: np.ndarray
    #: La mayor de las dos: la sección resiste si es ``≤ 1``.
    razon: np.ndarray
    axial: ResistenciaAxial

    @property
    def cumple(self) -> bool:
        return bool(np.all(self.razon <= 1.0))


def verificar_columna(
    seccion: SeccionColumna,
    mat: Materiales,
    Pu,
    Mz=0.0,
    My=0.0,
    *,
    zunchada: bool = False,
) -> VerificacionColumna:
    """Verifica la sección para ``(Pu, Mz, My)`` en kN y kN·m (``Pu`` > 0 en compresión).

    Acepta escalares o arreglos del mismo largo. Ver el método en el docstring del
    módulo.
    """
    avisar()
    pu, mz, my = (np.atleast_1d(np.asarray(x, dtype=np.float64)) for x in (Pu, Mz, My))
    pu, mz, my = np.broadcast_arrays(pu, mz, my)
    ax = resistencia_axial(seccion, mat, zunchada)
    cap, r_m, r_a, r = _razones(_geo(seccion), mat, pu, mz, my, zunchada, ax.phiPn_max, ax.phiPnt)
    return VerificacionColumna(pu, mz, my, cap, r_m, r_a, r, ax)


def diagrama_interaccion(
    seccion: SeccionColumna,
    mat: Materiales,
    angulo: float = 0.0,
    n: int = 40,
    *,
    zunchada: bool = False,
) -> dict[str, np.ndarray]:
    """Curva de interacción de diseño en la dirección ``angulo`` (rad) del plano
    ``(Mz, My)``: ``angulo=0`` es ``+Mz`` y ``π/2`` es ``+My``.

    Devuelve ``phiPn`` (kN) y ``phiMn`` (kN·m) desde la tracción pura hasta la
    compresión máxima sin el tope de §22.4.2.1, y ``phiPn_max``, que es ese tope
    (la curva de diseño es ``min(phiPn, phiPn_max)``). También ``Pn``, ``Mn`` y
    ``phi`` nominales en los mismos puntos.
    """
    avisar()
    ax = resistencia_axial(seccion, mat, zunchada)
    p_top = 0.75 * ax.Po if zunchada else 0.65 * ax.Po
    niveles = np.linspace(-ax.phiPnt, p_top, n + 2)[1:-1] * 1e3
    geo = _geo(seccion)
    cap, tf, cf, ok = _capacidad_en_direccion(geo, mat, niveles, angulo, zunchada)
    pn, mz, my, _, phi = _seccion_en(geo, mat, tf, cf, zunchada)
    mn = mz * math.cos(angulo) + my * math.sin(angulo)
    phi_pn = np.concatenate([[-ax.phiPnt], niveles[ok] / 1e3, [p_top]])
    phi_mn = np.concatenate([[0.0], cap[ok] / 1e6, [0.0]])
    return {
        "phiPn": phi_pn,
        "phiMn": phi_mn,
        "Pn": np.concatenate([[-ax.Pnt], pn[ok] / 1e3, [ax.Po]]),
        "Mn": np.concatenate([[0.0], mn[ok] / 1e6, [0.0]]),
        "phi": np.concatenate([[0.9], phi[ok], [0.75 if zunchada else 0.65]]),
        "phiPn_max": np.array(ax.phiPn_max),
    }


# --- Esbeltez (§6.6.4) -------------------------------------------------------------


def modulo_hormigon(mat: Materiales) -> float:
    """``Ec = 4700 √f'c`` en MPa, hormigón de peso normal (§19.2.2.1b)."""
    return 4700.0 * math.sqrt(mat.fc)


def limite_esbeltez(m1_m2: float, desplazable: bool = False) -> float:
    """Límite de ``k·lu/r`` para despreciar la esbeltez (§6.2.5.1).

    ``m1_m2`` es ``M1/M2`` con el signo de la norma: negativo en curvatura simple.
    """
    if desplazable:
        return 22.0
    return min(34.0 + 12.0 * m1_m2, 40.0)


def coeficiente_cm(m1_m2: float, cargas_transversales: bool = False) -> float:
    """``Cm`` de §6.6.4.5.3: ``0.6 − 0.4·M1/M2`` (negativo en curvatura simple) o 1.0."""
    return 1.0 if cargas_transversales else 0.6 - 0.4 * m1_m2


def rigidez_efectiva(mat: Materiales, Ig: float, beta_dns: float) -> float:
    """``(EI)eff = 0.4 Ec Ig / (1 + βdns)`` en N·mm² (§6.6.4.4.4a)."""
    if not 0.0 <= beta_dns <= 1.0:
        raise ValueError("βdns tiene que estar entre 0 y 1")
    return 0.4 * modulo_hormigon(mat) * Ig / (1.0 + beta_dns)


def carga_critica(EI: float, k: float, lu: float) -> float:
    """``Pc = π² (EI)eff / (k lu)²`` (§6.6.4.4.2). ``EI`` en N·mm², ``lu`` en mm → kN."""
    return math.pi**2 * EI / (k * lu) ** 2 / 1e3


def factor_magnificacion(Pu: float, Pc: float, Cm: float) -> float:
    """``δ = Cm / (1 − Pu/(0.75 Pc)) ≥ 1`` (§6.6.4.5.2); infinito si ``Pu ≥ 0.75 Pc``."""
    if Pu >= 0.75 * Pc:
        return math.inf
    return max(1.0, Cm / (1.0 - Pu / (0.75 * Pc)))


@dataclass(frozen=True)
class MagnificacionEje:
    """Esbeltez de la columna en un eje para una combinación (kN, kN·m, mm)."""

    #: ``"z"`` (flexión con ``Mz``) o ``"y"`` (con ``My``).
    eje: str
    k: float
    lu: float
    r: float
    esbeltez: float
    limite: float
    esbelta: bool
    #: ``M1/M2`` con el signo de la norma (negativo en curvatura simple).
    m1_m2: float
    #: Momentos de extremo de primer orden: el menor y el mayor en valor absoluto.
    M1: float
    M2: float
    #: Lo siguiente vale solo si la columna es esbelta (si no, ``δ = 1``).
    Cm: float = 1.0
    beta_dns: float = 0.0
    Pc: float = math.inf
    delta: float = 1.0
    #: Momento de diseño del eje: ``δ·max(|M2|, M2,min)`` con el signo de ``M2``.
    Mc: float = 0.0
    usa_m2_min: bool = False
    #: Momento magnificado sin el mínimo de §6.6.4.5.4 (``δ·|M2|`` con ``Cm`` propio),
    #: que se combina con el del otro eje: el mínimo se aplica a un eje por vez.
    Mc_sin_minimo: float = 0.0


@dataclass(frozen=True)
class DemandaColumna:
    """Solicitación verificada (kN, kN·m) y su razón demanda/capacidad."""

    combinacion: str
    #: Posición en la barra (m), o ``None`` para el punto con momentos magnificados.
    x: float | None
    Pu: float
    Mz: float
    My: float
    phiMn: float
    razon: float


@dataclass(frozen=True)
class DisenoColumna:
    """Resultado de :func:`disenar_columna`."""

    barra: int
    seccion: SeccionColumna
    zunchada: bool
    axial: ResistenciaAxial
    #: Solicitación que manda.
    critica: DemandaColumna
    #: Todas las verificadas, en el orden de las combinaciones.
    demandas: list[DemandaColumna]
    #: Esbeltez por combinación y eje: ``esbeltez[comb]["z"]``.
    esbeltez: dict[str, dict[str, MagnificacionEje]]
    avisos: list[str] = field(default_factory=list)

    @property
    def razon(self) -> float:
        return self.critica.razon

    @property
    def cumple(self) -> bool:
        return self.razon <= 1.0


def _por_eje(valor, nombre: str) -> tuple[float | None, float | None]:
    if valor is None:
        return None, None
    if isinstance(valor, (int, float)):
        return float(valor), float(valor)
    if len(valor) != 2:
        raise ValueError(f"'{nombre}' es un número o un par (para Mz, para My)")
    return (None if valor[0] is None else float(valor[0]),
            None if valor[1] is None else float(valor[1]))  # fmt: skip


def _diagramas(res, barra: int, combinaciones):
    """``[(nombre, diagrama, casos)]`` con ``x, N, Mz, My`` por combinación.

    ``casos`` es una función ``nombre_caso -> diagrama`` para separar las cargas
    sostenidas. Acepta resultados del pórtico espacial o del plano.
    """
    if combinaciones is None:
        raise ValueError("pasá las combinaciones (lista de Combinacion o diccionario)")
    if isinstance(combinaciones, dict):
        pares = [(k, dict(v)) for k, v in combinaciones.items()]
    else:
        pares = []
        for c in combinaciones:
            if isinstance(c, str):
                if not hasattr(res, "factores"):
                    raise ValueError("en el pórtico espacial las combinaciones llevan sus factores")
                pares.append((c, res.factores(c)))
            else:
                pares.append((c.nombre, dict(c.factores)))
    if not pares:
        raise ValueError("no hay combinaciones para diseñar")
    plano = not hasattr(res, "ejes")
    resueltas = set(getattr(res, "combinaciones", None) or ())
    salida = []
    for nombre, factores in pares:
        if nombre in resueltas and res.factores(nombre) == factores:
            # Resuelta junto con el modelo: diagramas exactos y sin recombinar.
            d0 = res[nombre].diagrama(barra)
        else:
            d0 = res.combinar(nombre, factores).diagrama(barra)
        if plano:
            d = {"x": d0["x"], "N": d0["N"], "Mz": d0["M"], "My": np.zeros_like(d0["M"])}
        else:
            d = {k: d0[k] for k in ("x", "N", "Mz", "My")}
        salida.append((nombre, factores, d))
    return salida, plano


def _axil_caso(res, nombre: str, barra: int, x: np.ndarray) -> np.ndarray:
    d = res[nombre].diagrama(barra)
    return np.interp(x, d["x"], d["N"])


def _magnificar(
    eje: str,
    mom: np.ndarray,
    pu: float,
    seccion: SeccionColumna,
    mat: Materiales,
    k: float,
    lu: float,
    beta_dns: float,
    desplazable: bool,
    delta_s: float | None,
) -> MagnificacionEje:
    m_i, m_j = float(mom[0]), float(mom[-1])
    if abs(m_i) >= abs(m_j):
        m2, m1 = m_i, m_j
    else:
        m2, m1 = m_j, m_i
    escala = max(float(np.max(np.abs(mom))), 1e-12)
    if abs(m2) <= 1e-9 * max(escala, pu * 1e-3, 1.0):
        m1_m2 = -1.0  # sin momentos de extremo: se toma curvatura simple (del lado seguro)
    else:
        m1_m2 = -m1 / m2  # la norma usa signo negativo en curvatura simple
    r = seccion.radio_giro(eje)
    esb = k * lu / r
    lim = limite_esbeltez(m1_m2, desplazable)
    base = MagnificacionEje(eje, k, lu, r, esb, lim, esb > lim, m1_m2, m1, m2)
    if esb <= lim or pu <= 0.0:
        return base
    if desplazable:
        if delta_s is None:
            raise ValueError(
                f"la columna es esbelta en el eje {eje} (k·lu/r = {esb:.1f} > 22) y el pórtico "
                "es desplazable: Nervi todavía no calcula δs (§6.6.4.6) ni hace análisis P-Δ; "
                "pasá delta_s"
            )
        if delta_s < 1.0:
            raise ValueError("δs no puede ser menor que 1")
        mc = delta_s * float(mom[np.argmax(np.abs(mom))])
        return MagnificacionEje(
            eje, k, lu, r, esb, lim, True, m1_m2, m1, m2, 1.0, beta_dns, math.inf, delta_s, mc,
            Mc_sin_minimo=mc,
        )  # fmt: skip
    # Cargas transversales entre apoyos: el diagrama no es lineal entre los extremos.
    lineal = m_i + (m_j - m_i) * np.linspace(0.0, 1.0, mom.size)
    transversales = bool(np.max(np.abs(mom - lineal)) > 1e-6 * escala)
    cm_real = coeficiente_cm(m1_m2, transversales)
    m2_min = pu * (15.0 + 0.03 * seccion.altura(eje)) / 1e3  # kN·m (§6.6.4.5.4)
    usa_min = abs(m2) < m2_min
    pc = carga_critica(rigidez_efectiva(mat, seccion.inercia(eje), beta_dns), k, lu)
    delta_real = factor_magnificacion(pu, pc, cm_real)
    # Con el momento mínimo se toma Cm = 1 (la otra opción de §6.6.4.5.4 es usar M1/M2).
    cm = 1.0 if usa_min else cm_real
    delta = factor_magnificacion(pu, pc, cm)
    signo = -1.0 if m2 < 0 else 1.0
    m_max = float(np.max(np.abs(mom)))
    mc = signo * max(delta * max(abs(m2), m2_min), m_max)
    mc_real = signo * max(delta_real * abs(m2), m_max)
    return MagnificacionEje(
        eje, k, lu, r, esb, lim, True, m1_m2, m1, m2, cm, beta_dns, pc, delta, mc, usa_min,
        mc_real,
    )  # fmt: skip


def solicitaciones_columna(
    res,
    barra: int,
    seccion: SeccionColumna,
    mat: Materiales,
    combinaciones,
    *,
    permanentes: Sequence[str] | None = None,
    k=1.0,
    lu=None,
    desplazable: bool = False,
    delta_s=None,
) -> tuple[list[tuple[str, float | None, float, float, float]], dict, list[str]]:
    """Solicitaciones a verificar en la columna, con la esbeltez ya aplicada.

    Devuelve ``(puntos, esbeltez, avisos)``: ``puntos`` es una lista de
    ``(combinación, x, Pu, Mz, My)``. Solo depende de la geometría de la sección,
    no de su armadura. Ver :func:`disenar_columna` para los argumentos.
    """
    diags, plano = _diagramas(res, barra, combinaciones)
    kz, ky = _por_eje(k, "k")
    luz, luy = _por_eje(lu, "lu")
    dsz, dsy = _por_eje(delta_s, "delta_s")
    largo = float(diags[0][2]["x"][-1]) * 1e3
    luz = largo if luz is None else luz * 1e3
    luy = largo if luy is None else luy * 1e3
    ejes = [("z", "Mz", kz, luz, dsz)] + ([] if plano else [("y", "My", ky, luy, dsy)])
    puntos: list[tuple[str, float | None, float, float, float]] = []
    esbeltez: dict[str, dict[str, MagnificacionEje]] = {}
    avisos: list[str] = []
    for nombre, factores, d in diags:
        x = d["x"]
        pu_x = -d["N"]
        mom = {"Mz": d["Mz"].copy(), "My": d["My"].copy()}
        pu = float(pu_x.max())
        if permanentes is None:
            beta = 1.0
        elif pu > 0:
            sost = sum(
                f * _axil_caso(res, caso, barra, x)
                for caso, f in factores.items()
                if caso in permanentes
            )
            sost = -np.asarray(sost, dtype=np.float64) * np.ones_like(x)
            beta = float(np.clip(sost.max() / pu, 0.0, 1.0))
        else:
            beta = 0.0
        esbeltez[nombre] = {}
        magnificados = {}
        for eje, comp, k_e, lu_e, ds in ejes:
            mag = _magnificar(eje, mom[comp], pu, seccion, mat, k_e, lu_e, beta, desplazable, ds)
            esbeltez[nombre][eje] = mag
            if mag.esbelta and pu > 0:
                if desplazable:
                    mom[comp] = mom[comp] * mag.delta
                else:
                    magnificados[comp] = mag.Mc
                if permanentes is None and not desplazable:
                    aviso = "sin 'permanentes' se tomó βdns = 1 (del lado seguro)"
                    if aviso not in avisos:
                        avisos.append(aviso)
                if math.isinf(mag.delta):
                    avisos.append(
                        f"{nombre}: Pu ≥ 0.75·Pc en el eje {eje}; la columna es inestable"
                    )
                elif not desplazable and abs(mag.Mc_sin_minimo) > 1.4 * max(abs(mag.M2), 1e-12):
                    avisos.append(
                        f"{nombre}: el momento de segundo orden en el eje {eje} supera 1.4 veces "
                        "el de primer orden (§6.2.5.3); revisá la sección o el sistema"
                    )
        for k_x in range(x.size):
            puntos.append((nombre, float(x[k_x]), float(pu_x[k_x]),
                           float(mom["Mz"][k_x]), float(mom["My"][k_x])))  # fmt: skip
        # Un punto por eje esbelto: ese eje con Mc (incluido el mínimo) y el otro con
        # su momento magnificado sin mínimo, o su máximo de primer orden si no es esbelto.
        for comp in magnificados:
            par = {}
            for otro, eje in (("Mz", "z"), ("My", "y")):
                mag = esbeltez[nombre].get(eje)
                if otro == comp:
                    par[otro] = magnificados[comp]
                elif otro in magnificados and mag is not None:
                    par[otro] = mag.Mc_sin_minimo
                else:
                    par[otro] = float(mom[otro][np.argmax(np.abs(mom[otro]))])
            puntos.append((nombre, None, pu, par["Mz"], par["My"]))
    return puntos, esbeltez, avisos


def _verificar_puntos(seccion, mat, puntos, zunchada):
    if not puntos:
        raise ValueError("no hay solicitaciones")
    pu = np.array([p[2] for p in puntos])
    mz = np.array([p[3] for p in puntos])
    my = np.array([p[4] for p in puntos])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        v = verificar_columna(seccion, mat, pu, mz, my, zunchada=zunchada)
    return v


def _avisos_seccion(seccion: SeccionColumna, zunchada: bool) -> list[str]:
    avisos = []
    rho = seccion.cuantia
    if rho < CUANTIA_MIN - 1e-12:
        avisos.append(f"ρ = {100 * rho:.2f} % < 1 % (§10.6.1.1)")
    if rho > CUANTIA_MAX + 1e-12:
        avisos.append(f"ρ = {100 * rho:.2f} % > 8 % (§10.6.1.1)")
    n = seccion.barras.shape[0]
    if n < (6 if zunchada else 4):
        avisos.append(f"{n} barras: el mínimo es {6 if zunchada else 4} (§10.7.3.1)")
    s_min = separacion_libre_minima_columna(float(seccion.barras[:, 2].max()), seccion.d_agregado)
    s = seccion.separacion_libre()
    if s < s_min - 1e-9:
        avisos.append(f"separación libre {s:.0f} mm < {s_min:.0f} mm (§25.2.3)")
    return avisos


def _candidatas(seccion: SeccionColumna, diametros, zunchada):
    """Armaduras posibles de la sección, ordenadas por área de acero."""
    salida = []
    n_min = 6 if zunchada else 4
    for d in diametros:
        s_min = separacion_libre_minima_columna(d, seccion.d_agregado)
        e = seccion.recubrimiento + seccion.d_estribo + d / 2.0
        if seccion.forma == "rectangular":
            hy, hz = seccion.dimensiones["hy"], seccion.dimensiones["hz"]
            ly, lz = hy - 2 * e, hz - 2 * e
            if ly <= 0 or lz <= 0:
                continue
            ny_max = int(ly // (s_min + d)) + 1
            nz_max = int(lz // (s_min + d)) + 1
            for n_y in range(2, ny_max + 1):
                for n_z in range(2, nz_max + 1):
                    n = 2 * n_y + 2 * n_z - 4
                    if n >= n_min:
                        salida.append((n * area_barra(d), n, (n_y, n_z), d))
        elif seccion.forma == "circular":
            rb = seccion.dimensiones["D"] / 2.0 - e
            if rb <= 0:
                continue
            n_max = int(math.pi / math.asin(min(1.0, (s_min + d) / (2 * rb))))
            for n in range(n_min, n_max + 1):
                salida.append((n * area_barra(d), n, n, d))
        else:
            raise ValueError("la búsqueda de armadura es para secciones rectangulares o circulares")
    ag = seccion.Ag
    salida = [c for c in salida if CUANTIA_MIN * ag - 1e-9 <= c[0] <= CUANTIA_MAX * ag + 1e-9]
    # A igual área, menos barras y después la disposición más pareja entre caras.
    salida.sort(key=lambda c: (round(c[0], 6), c[1], np.ptp(np.atleast_1d(c[2]))))
    return salida


def elegir_armadura_columna(
    seccion: SeccionColumna,
    mat: Materiales,
    puntos: list[tuple[str, float | None, float, float, float]],
    *,
    zunchada: bool = False,
    diametros: tuple[int, ...] = DIAMETROS_COLUMNA,
) -> SeccionColumna:
    """La armadura de menor área que resiste todas las solicitaciones ``puntos``
    (kN, kN·m) con ``1 % ≤ ρ ≤ 8 %`` (§10.6.1.1), la cantidad mínima de barras
    (§10.7.3.1) y la separación libre de §25.2.3. Barras iguales en el perímetro.

    Lanza ``ValueError`` si ninguna alcanza: hay que agrandar la sección.
    """
    avisar()
    candidatas = _candidatas(seccion, diametros, zunchada)
    if not candidatas:
        raise ValueError("ninguna armadura entra en la sección con 1 % ≤ ρ ≤ 8 %")
    secciones = [seccion.con_barras(cant, d) for _, _, cant, d in candidatas]
    n_max = max(s.barras.shape[0] for s in secciones)
    # Todas las armaduras juntas, completadas con barras de área nula.
    pb = np.zeros((len(secciones), n_max, 2))
    ab = np.zeros((len(secciones), n_max))
    for k, s in enumerate(secciones):
        pb[k, : s.barras.shape[0]] = s.barras[:, :2]
        ab[k, : s.barras.shape[0]] = s.areas
    ax = [resistencia_axial(s, mat, zunchada) for s in secciones]
    todos = _f64([p[2:] for p in puntos]).reshape(-1, 3)
    if todos.size == 0:
        raise ValueError("no hay solicitaciones")
    # Rust descarta armaduras contra un grupo chico de solicitaciones que crece con
    # la que hace fallar a la mejor candidata; la que queda se verifica con todas.
    k = _core.columna_elegir_armadura(
        _core.VERSION_CONTRATO_DISENO, *_contiguos(seccion.contorno, pb, ab),
        *_contiguos([a.phiPn_max for a in ax], [a.phiPnt for a in ax]),
        mat.fc, mat.fy, zunchada, todos,
    )  # fmt: skip
    if k is not None:
        return secciones[k]
    raise ValueError(
        "ninguna armadura con ρ ≤ 8 % resiste las solicitaciones: agrandá la sección "
        "o mejorá los materiales"
    )


def disenar_columna(
    res,
    barra: int,
    seccion: SeccionColumna,
    mat: Materiales,
    combinaciones,
    *,
    permanentes: Sequence[str] | None = None,
    k=1.0,
    lu=None,
    desplazable: bool = False,
    delta_s=None,
    zunchada: bool = False,
    buscar_armadura: bool = False,
    diametros: tuple[int, ...] = DIAMETROS_COLUMNA,
) -> DisenoColumna:
    """Verifica (o arma) la barra ``barra`` como columna con todas las combinaciones.

    - ``res``: :class:`nervi.Modelo3D` resuelto (``Resultados3D``) o un pórtico
      plano (``Resultados``); en el plano solo hay flexión con ``Mz`` (``M``) y la
      esbeltez fuera del plano no se revisa. Modelo en kN y m.
    - ``combinaciones``: lista de :class:`~nervi.design.Combinacion` (por ejemplo
      de :func:`nervi.design.generar`) o diccionario ``{nombre: {caso: factor}}``.
      En el pórtico plano también valen los nombres de combinaciones resueltas.
    - ``permanentes``: casos de carga sostenida (los de tipo ``D``) para ``βdns``;
      sin ellos se toma ``βdns = 1``, del lado seguro.
    - ``k`` y ``lu`` (m, por defecto el largo de la barra): un número o un par
      ``(para Mz, para My)``. ``lu`` es la longitud libre entre apoyos laterales.
    - ``desplazable``: pórtico con desplazamiento lateral; si la columna es esbelta
      hay que dar ``delta_s`` (un número o un par), porque Nervi no lo calcula.
    - ``zunchada``: armadura transversal en espiral (cambia ``φ`` y ``Pn,max``).
    - ``buscar_armadura``: con ``True`` se conserva la geometría de ``seccion`` y se
      elige la armadura de menor área que cumple (:func:`elegir_armadura_columna`).

    En cada combinación se verifican todas las estaciones del diagrama y, si la
    columna es esbelta en algún eje (no desplazable), un punto más con ``Pu``
    máximo y los momentos magnificados ``Mc`` (el otro eje con su máximo, del lado
    seguro).
    """
    avisar()
    puntos, esbeltez, avisos = solicitaciones_columna(
        res,
        barra,
        seccion,
        mat,
        combinaciones,
        permanentes=permanentes,
        k=k,
        lu=lu,
        desplazable=desplazable,
        delta_s=delta_s,
    )
    if buscar_armadura:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            seccion = elegir_armadura_columna(
                seccion, mat, puntos, zunchada=zunchada, diametros=diametros
            )
    v = _verificar_puntos(seccion, mat, puntos, zunchada)
    demandas = [
        DemandaColumna(p[0], p[1], p[2], p[3], p[4], float(v.phiMn[i]), float(v.razon[i]))
        for i, p in enumerate(puntos)
    ]
    critica = demandas[int(np.argmax(v.razon))]
    return DisenoColumna(
        barra=barra,
        seccion=seccion,
        zunchada=zunchada,
        axial=v.axial,
        critica=critica,
        demandas=demandas,
        esbeltez=esbeltez,
        avisos=avisos + _avisos_seccion(seccion, zunchada),
    )
