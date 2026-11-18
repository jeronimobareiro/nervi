# SPDX-License-Identifier: GPL-3.0-or-later
"""Detalle de armaduras según ACI 318-19: anclajes, empalmes y ganchos (experimental).

Unidades: MPa y mm.

Método (ACI 318-19; se implementa el método y se cita el artículo):

- Longitud de desarrollo de barras rectas traccionadas (§25.4.2): expresión
  general ``ld = fy ψt ψe ψs ψg / (1.1 λ √f'c (cb + Ktr)/db) · db`` (§25.4.2.4),
  con ``(cb + Ktr)/db ≤ 2.5``, ``Ktr = 40 Atr / (s n)``, factores ψ de §25.4.2.5
  (``ψt ψe ≤ 1.7``) y mínimo de 300 mm (§25.4.2.1); y la expresión simplificada
  de §25.4.2.3 según separación y recubrimiento.
- ``√f'c ≤ 8.3 MPa`` en todas las longitudes de desarrollo (§25.4.1.4).
- Reducción por armadura en exceso ``As,req/As,prov`` (§25.4.10), opcional.
- Ganchos normales traccionados (§25.4.3.1):
  ``ldh = fy ψe ψr ψo ψc / (23 λ √f'c) · db^1.5 ≥ max(8 db, 150 mm)``, y la
  geometría del gancho normal (§25.3.1): prolongación y diámetro de doblado.
- Barras comprimidas (§25.4.9.2): ``ldc = max(0.24 fy ψr/(λ√f'c), 0.043 fy ψr)·db``
  con mínimo de 200 mm.
- Empalmes por yuxtaposición traccionados clase A (``1.0 ld``) o B (``1.3 ld``),
  mínimo 300 mm (§25.5.2.1); comprimidos según §25.5.5.1.
- Corte de barras: prolongación ``max(d, 12 db)`` más allá del punto en que dejan
  de hacer falta (§9.7.3.3); parte de la armadura positiva que llega al apoyo
  (§9.7.3.8.1) y de la negativa que pasa el punto de inflexión (§9.7.3.8.4).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .flexion import separacion_libre_minima
from .materiales import Materiales, SeccionRectangular, area_barra, avisar
from .servicio import separacion_libre_capa

#: Límite de ``√f'c`` para longitudes de desarrollo, MPa (§25.4.1.4).
RAIZ_FC_MAX = 8.3
#: Límite de ``(cb + Ktr)/db`` (§25.4.2.4).
CONFINAMIENTO_MAX = 2.5
#: Mínimos absolutos, mm.
LD_MIN = 300.0  # §25.4.2.1
LDH_MIN = 150.0  # §25.4.3.1
LDC_MIN = 200.0  # §25.4.9.1
EMPALME_MIN = 300.0  # §25.5.2.1 y §25.5.5.1


def _raiz_fc(mat: Materiales) -> float:
    return min(math.sqrt(mat.fc), RAIZ_FC_MAX)


def psi_g(fy: float) -> float:
    """Factor por grado de la armadura ``ψg`` (§25.4.2.5)."""
    if fy <= 420.0:
        return 1.0
    if fy <= 550.0:
        return 1.15
    return 1.3


def psi_e(epoxi: bool, recubrimiento: float, s_libre: float, db: float) -> float:
    """Factor por recubrimiento epoxi ``ψe`` (§25.4.2.5)."""
    if not epoxi:
        return 1.0
    return 1.5 if recubrimiento < 3.0 * db or s_libre < 6.0 * db else 1.2


def psi_s(db: float) -> float:
    """Factor por tamaño ``ψs``: 0.8 para barras de 20 mm o menos (No. 19 y menores),
    1.0 para mayores (§25.4.2.5)."""
    return 0.8 if db <= 20.0 else 1.0


def indice_ktr(Atr: float, s: float, n: int) -> float:
    """Índice de armadura transversal ``Ktr = 40 Atr / (s n)``, mm (§25.4.2.4)."""
    if s <= 0 or n <= 0:
        raise ValueError("s y n tienen que ser positivos")
    return 40.0 * Atr / (s * n)


@dataclass(frozen=True)
class Desarrollo:
    """Longitud de desarrollo de una barra traccionada (mm) y sus factores."""

    db: float
    ld: float
    psi_t: float
    psi_e: float
    psi_s: float
    psi_g: float
    #: ``(cb + Ktr)/db`` usado (ya limitado a 2.5); ``None`` en la expresión simplificada.
    confinamiento: float | None
    #: Factor ``As,req/As,prov`` aplicado (§25.4.10).
    exceso: float


def longitud_desarrollo(
    db: float,
    mat: Materiales,
    *,
    cb: float,
    Ktr: float = 0.0,
    superior: bool = False,
    epoxi: bool = False,
    recubrimiento: float | None = None,
    s_libre: float | None = None,
    As_req_prov: float = 1.0,
) -> Desarrollo:
    """``ld`` de una barra recta traccionada con la expresión general (§25.4.2.4).

    ``cb`` es la menor distancia del centro de la barra a la superficie de hormigón
    más cercana o la mitad de la separación entre centros (mm). ``superior=True``
    aplica ``ψt = 1.3`` (más de 300 mm de hormigón fresco debajo). ``Ktr = 0`` es
    del lado seguro. ``As_req_prov < 1`` reduce ``ld`` por armadura en exceso
    (§25.4.10; no aplica en zonas sísmicas ni en algunos casos de la norma).
    """
    if db <= 0 or cb <= 0 or Ktr < 0:
        raise ValueError("db y cb tienen que ser positivos y Ktr no negativo")
    if not 0 < As_req_prov <= 1.0:
        raise ValueError("As,req/As,prov tiene que estar entre 0 y 1")
    pt = 1.3 if superior else 1.0
    rec = cb if recubrimiento is None else recubrimiento
    sl = math.inf if s_libre is None else s_libre
    pe = psi_e(epoxi, rec, sl, db)
    prod = min(pt * pe, 1.7)
    ps, pg = psi_s(db), psi_g(mat.fy)
    conf = min((cb + Ktr) / db, CONFINAMIENTO_MAX)
    ld = mat.fy * prod * ps * pg / (1.1 * mat.lam * _raiz_fc(mat) * conf) * db
    ld = max(ld * As_req_prov, LD_MIN)
    return Desarrollo(db, ld, pt, pe, ps, pg, conf, As_req_prov)


def longitud_desarrollo_simplificada(
    db: float,
    mat: Materiales,
    *,
    condiciones_favorables: bool,
    superior: bool = False,
    epoxi: bool = False,
) -> Desarrollo:
    """``ld`` con la expresión simplificada de §25.4.2.3.

    ``condiciones_favorables`` es ``True`` cuando la separación libre es al menos
    ``db``, el recubrimiento libre al menos ``db`` y hay estribos mínimos a lo
    largo de ``ld``, o cuando la separación libre es al menos ``2 db`` y el
    recubrimiento al menos ``db``. El divisor es ``2.1`` / ``1.7`` (barras de 20 mm o
    menos / mayores) en ese caso y ``1.4`` / ``1.1`` en los demás.
    """
    if db <= 0:
        raise ValueError("db tiene que ser positivo")
    pt = 1.3 if superior else 1.0
    pe = 1.5 if epoxi else 1.0  # sin datos de recubrimiento, el valor mayor
    prod = min(pt * pe, 1.7)
    pg = psi_g(mat.fy)
    chica = db <= 20.0
    if condiciones_favorables:
        divisor = 2.1 if chica else 1.7
    else:
        divisor = 1.4 if chica else 1.1
    ld = max(mat.fy * prod * pg / (divisor * mat.lam * _raiz_fc(mat)) * db, LD_MIN)
    return Desarrollo(db, ld, pt, pe, 1.0, pg, None, 1.0)


# --- Ganchos -----------------------------------------------------------------


def psi_c(fc: float) -> float:
    """Factor por resistencia del hormigón ``ψc`` para ganchos (§25.4.3.2)."""
    return fc / 105.0 + 0.6 if fc < 40.0 else 1.0


@dataclass(frozen=True)
class Gancho:
    """Gancho normal traccionado. Medidas en mm."""

    db: float
    angulo: int
    #: Longitud de desarrollo con gancho, medida hasta el exterior del gancho.
    ldh: float
    #: Prolongación recta después del doblado y diámetro interior de doblado.
    prolongacion: float
    diametro_doblado: float
    psi_e: float
    psi_r: float
    psi_o: float
    psi_c: float


def diametro_doblado(db: float) -> float:
    """Diámetro interior mínimo de doblado de ganchos normales, mm (§25.3.1):
    6 db hasta 25 mm, 8 db hasta 36 mm y 10 db para barras mayores."""
    if db <= 25.0:
        return 6.0 * db
    if db <= 36.0:
        return 8.0 * db
    return 10.0 * db


def gancho_normal(
    db: float,
    mat: Materiales,
    *,
    angulo: int = 90,
    epoxi: bool = False,
    confinado: bool = False,
    dentro_del_nucleo: bool = False,
) -> Gancho:
    """Gancho normal traccionado (§25.3.1 y §25.4.3.1).

    ``confinado=True`` usa ``ψr = 1.0`` (hay la armadura de confinamiento que pide la
    tabla de factores de §25.4.3.2);
    si no, ``ψr = 1.6``. ``dentro_del_nucleo=True`` usa ``ψo = 1.0`` (gancho que
    termina dentro del núcleo de una columna con recubrimiento lateral de al menos
    65 mm, o con recubrimiento lateral de al menos 6 db); si no, ``ψo = 1.25``.
    """
    if angulo not in (90, 180):
        raise ValueError("el gancho normal es de 90 o 180 grados")
    if db <= 0:
        raise ValueError("db tiene que ser positivo")
    pe = 1.2 if epoxi else 1.0
    pr = 1.0 if confinado else 1.6
    po = 1.0 if dentro_del_nucleo else 1.25
    pc = psi_c(mat.fc)
    ldh = mat.fy * pe * pr * po * pc / (23.0 * mat.lam * _raiz_fc(mat)) * db**1.5
    ldh = max(ldh, 8.0 * db, LDH_MIN)
    prolongacion = 12.0 * db if angulo == 90 else max(4.0 * db, 65.0)
    return Gancho(db, angulo, ldh, prolongacion, diametro_doblado(db), pe, pr, po, pc)


# --- Compresión y empalmes ----------------------------------------------------


def longitud_desarrollo_compresion(db: float, mat: Materiales, *, confinada: bool = False) -> float:
    """``ldc`` de barras comprimidas, mm (§25.4.9.2); ``confinada`` usa ``ψr = 0.75``."""
    pr = 0.75 if confinada else 1.0
    ldc = max(0.24 * mat.fy * pr / (mat.lam * _raiz_fc(mat)), 0.043 * mat.fy * pr) * db
    return max(ldc, LDC_MIN)


def empalme_traccion(ld: float, clase: str = "B") -> float:
    """Longitud de empalme por yuxtaposición traccionado, mm (§25.5.2.1).

    ``ld`` es la longitud de desarrollo **sin** la reducción por armadura en exceso.
    Clase A (``1.0 ld``) solo si ``As,prov/As,req ≥ 2`` en todo el empalme y se
    empalma como mucho la mitad de las barras; si no, clase B (``1.3 ld``).
    """
    if clase not in ("A", "B"):
        raise ValueError("la clase de empalme es 'A' o 'B'")
    return max((1.0 if clase == "A" else 1.3) * ld, EMPALME_MIN)


def empalme_compresion(db: float, mat: Materiales) -> float:
    """Longitud de empalme por yuxtaposición comprimido, mm (§25.5.5.1).

    ``0.071 fy db`` si ``fy ≤ 420`` MPa y ``(0.13 fy - 24) db`` si es mayor, con
    mínimo de 300 mm; un tercio más si ``f'c < 21`` MPa.
    """
    if mat.fy <= 420.0:
        ls = 0.071 * mat.fy * db
    else:
        ls = (0.13 * mat.fy - 24.0) * db
    ls = max(ls, EMPALME_MIN)
    return ls * 4.0 / 3.0 if mat.fc < 21.0 else ls


# --- Detalle de una viga diseñada --------------------------------------------


@dataclass(frozen=True)
class DetalleArmadura:
    """Detalle de una de las armaduras longitudinales de la viga (mm)."""

    #: ``"inferior"`` o ``"superior"``.
    posicion: str
    descripcion: str
    #: Diámetro mayor de la capa más traccionada (el que manda).
    db: float
    n_barras: int
    desarrollo: Desarrollo
    gancho: Gancho
    empalme_clase_b: float
    #: Prolongación más allá del punto donde la barra deja de hacer falta (§9.7.3.3).
    prolongacion_corte: float
    #: Barras que tienen que llegar al apoyo (inferior, §9.7.3.8.1) o pasar el punto
    #: de inflexión (superior, §9.7.3.8.4), y cuánto.
    barras_continuas: int
    longitud_continua: float
    articulo_continuas: str
    #: Separación libre provista y mínima (§25.2.1).
    s_libre: float
    s_libre_min: float

    @property
    def cumple(self) -> bool:
        return self.s_libre >= self.s_libre_min - 1e-9


@dataclass(frozen=True)
class DetalleViga:
    """Resultado de :func:`detallar_viga`."""

    barra: int
    inferior: DetalleArmadura | None
    superior: DetalleArmadura | None
    avisos: tuple[str, ...]

    @property
    def cumple(self) -> bool:
        return all(a is None or a.cumple for a in (self.inferior, self.superior))

    def filas_memoria(self, elemento: str | None = None) -> list[tuple]:
        """Filas para :func:`nervi.memoria.tabla_verificaciones`.

        La separación libre se verifica como "mínima / provista" para que la
        relación quede en la forma solicitación/resistencia.
        """
        nombre = f"Barra {self.barra}" if elemento is None else elemento
        return [
            (
                nombre,
                f"Separación libre mínima armadura {a.posicion}",
                a.s_libre_min,
                a.s_libre,
                "ACI 318-19 §25.2.1",
            )
            for a in (self.inferior, self.superior)
            if a is not None
        ]

    def tabla_memoria(self) -> list[list[str]]:
        """Filas de texto con las longitudes de anclaje y empalme, para una tabla."""
        filas = []
        for a in (self.inferior, self.superior):
            if a is None:
                continue
            filas.append(
                [
                    a.posicion,
                    a.descripcion,
                    f"{a.desarrollo.ld:.0f}",
                    f"{a.gancho.ldh:.0f}",
                    f"{a.empalme_clase_b:.0f}",
                    f"{a.prolongacion_corte:.0f}",
                    f"{a.barras_continuas} barras, {a.longitud_continua:.0f} mm",
                ]
            )
        return filas


def _detalle(
    posicion: str, disp, seccion: SeccionRectangular, mat: Materiales, estribos, *, extra
) -> DetalleArmadura:
    capa = disp.capas[0]
    db = float(max(capa))
    n = len(capa)
    s_libre = separacion_libre_capa(capa, seccion)
    s_centros = s_libre + db
    rec_centro = seccion.recubrimiento + seccion.d_estribo + db / 2.0
    cb = min(rec_centro, s_centros / 2.0)
    ktr = 0.0
    if estribos is not None:
        ktr = indice_ktr(estribos.ramas * area_barra(estribos.diametro), estribos.s, n)
    # Barras superiores: más de 300 mm de hormigón fresco debajo (§25.4.2.5).
    superior = posicion == "superior" and disp.d > 300.0
    des = longitud_desarrollo(
        db,
        mat,
        cb=cb,
        Ktr=ktr,
        superior=superior,
        recubrimiento=seccion.recubrimiento + seccion.d_estribo,
        s_libre=s_libre,
    )
    return DetalleArmadura(
        posicion=posicion,
        descripcion=disp.descripcion,
        db=db,
        n_barras=sum(len(c) for c in disp.capas),
        desarrollo=des,
        gancho=gancho_normal(db, mat),
        empalme_clase_b=empalme_traccion(des.ld, "B"),
        prolongacion_corte=max(disp.d, 12.0 * db),
        barras_continuas=extra[0],
        longitud_continua=extra[1],
        articulo_continuas=extra[2],
        s_libre=s_libre,
        s_libre_min=separacion_libre_minima(db, seccion.d_agregado),
    )


def detallar_viga(
    diseno,
    seccion: SeccionRectangular,
    mat: Materiales,
    *,
    continua: bool = True,
    luz_libre: float | None = None,
) -> DetalleViga:
    """Anclajes, empalmes, ganchos y corte de barras de una viga ya diseñada.

    ``diseno`` es el resultado de :func:`disenar_viga`. ``continua`` dice si la viga
    es continua (un cuarto de la armadura positiva llega al apoyo) o simplemente
    apoyada (un tercio) según §9.7.3.8.1. ``luz_libre`` (mm) se usa para
    ``ln/16`` en la armadura negativa (§9.7.3.8.4); sin ella se omite ese término.
    Las longitudes usan ``Ktr`` de los estribos diseñados y la geometría de la capa
    más traccionada; no reducen por armadura en exceso.
    """
    avisar()
    avisos = []
    inf = sup = None
    if diseno.inferior is not None:
        n = sum(len(c) for c in diseno.inferior.capas)
        frac = 0.25 if continua else 1.0 / 3.0
        cont = max(math.ceil(frac * n), 2)
        art = "ACI 318-19 §9.7.3.8.1"
        inf = _detalle(
            "inferior", diseno.inferior, seccion, mat, diseno.estribos, extra=(cont, 150.0, art)
        )
    if diseno.superior is not None:
        n = sum(len(c) for c in diseno.superior.capas)
        db = float(max(diseno.superior.capas[0]))
        largo = max(diseno.superior.d, 12.0 * db, (luz_libre or 0.0) / 16.0)
        if luz_libre is None:
            avisos.append("sin luz libre: la prolongación de la armadura negativa no incluye ln/16")
        cont = max(math.ceil(n / 3.0), 1)
        art = "ACI 318-19 §9.7.3.8.4"
        sup = _detalle(
            "superior", diseno.superior, seccion, mat, diseno.estribos, extra=(cont, largo, art)
        )
    return DetalleViga(diseno.barra, inf, sup, tuple(avisos))
