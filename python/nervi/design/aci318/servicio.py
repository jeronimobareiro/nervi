# SPDX-License-Identifier: GPL-3.0-or-later
"""Servicio de vigas de hormigón armado según ACI 318-19: flechas y fisuración (experimental).

Unidades: MPa y mm en secciones y materiales; kN·m en momentos; mm en flechas.

Método (ACI 318-19; se implementa el método y se cita el artículo, no se
transcriben tablas ni texto):

- Módulo del hormigón ``Ec = 4700 √f'c`` para hormigón de peso normal
  (§19.2.2.1b) y módulo de rotura ``fr = 0.62 λ √f'c`` (§19.2.3.1).
- Momento de fisuración ``Mcr = fr Ig / yt`` (§24.2.3.5), con la sección bruta de
  hormigón (se desprecia la armadura en ``Ig``, como permite la norma).
- Inercia fisurada ``Icr`` de la sección transformada (``n = Es/Ec``), con la
  armadura comprimida transformada como ``(n - 1) As'``.
- Inercia efectiva ``Ie`` según §24.2.3.5 (forma de ACI 318-19, que reemplazó a
  la de Branson): ``Ie = Ig`` si ``Ma ≤ (2/3) Mcr``; si no,
  ``Ie = Icr / (1 - ((2/3) Mcr / Ma)² (1 - Icr/Ig))``.
- En tramos continuos, ``Ie`` promedio de las secciones críticas de momento
  positivo y negativo (§24.2.3.6).
- Flecha diferida: multiplicador ``λΔ = ξ / (1 + 50 rho')`` (§24.2.4.1.1), con ``ξ``
  según la duración de la carga sostenida (§24.2.4.1.3).
- Límites de flecha según el tipo de elemento y lo que soporta (§24.2.2).
- Control de fisuración por separación de la armadura traccionada más cercana a
  la cara traccionada (§24.3.2), con ``fs = (2/3) fy`` permitido por §24.3.2.1 o
  la tensión calculada con la sección fisurada.
- Armadura de piel cuando ``h > 900 mm`` (§9.7.2.3): solo se avisa.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .flexion import DisposicionBarras
from .materiales import ES, Materiales, SeccionRectangular, avisar

#: Duración de la carga sostenida (meses) y factor ξ (§24.2.4.1.3).
_XI = ((3.0, 1.0), (6.0, 1.2), (12.0, 1.4), (60.0, 2.0))

#: Límites de flecha (§24.2.2): divisor de la luz y qué flecha se compara.
#: ``"inmediata_L"`` es la flecha inmediata por sobrecarga; ``"diferida_mas_L"``,
#: la parte de la flecha que ocurre después de colocar los elementos no
#: estructurales (se toma, del lado seguro, toda la diferida más la inmediata por
#: sobrecarga).
LIMITES_FLECHA: dict[str, tuple[float, str]] = {
    "cubierta": (180.0, "inmediata_L"),
    "piso": (360.0, "inmediata_L"),
    "sensibles": (480.0, "diferida_mas_L"),
    "no_sensibles": (240.0, "diferida_mas_L"),
}

#: Altura a partir de la cual hace falta armadura de piel, mm (§9.7.2.3).
H_ARMADURA_PIEL = 900.0


# --- Propiedades de la sección ------------------------------------------------


def modulo_elasticidad(mat: Materiales) -> float:
    """``Ec = 4700 √f'c`` (MPa), hormigón de peso normal (§19.2.2.1b)."""
    return 4700.0 * math.sqrt(mat.fc)


def modulo_rotura(mat: Materiales) -> float:
    """``fr = 0.62 λ √f'c`` (MPa) (§19.2.3.1)."""
    return 0.62 * mat.lam * math.sqrt(mat.fc)


def inercia_bruta(seccion: SeccionRectangular) -> float:
    """``Ig = b h³ / 12`` (mm⁴), sin la armadura."""
    return seccion.b * seccion.h**3 / 12.0


def momento_fisuracion(seccion: SeccionRectangular, mat: Materiales) -> float:
    """``Mcr = fr Ig / yt`` (kN·m), con ``yt = h/2`` (§24.2.3.5)."""
    return modulo_rotura(mat) * inercia_bruta(seccion) / (seccion.h / 2.0) / 1e6


@dataclass(frozen=True)
class SeccionFisurada:
    """Sección transformada fisurada. Medidas en mm, inercia en mm⁴."""

    #: Relación modular ``Es/Ec``.
    n: float
    #: Profundidad del eje neutro desde la fibra comprimida.
    x: float
    Icr: float


def seccion_fisurada(
    b: float,
    d: float,
    As: float,
    mat: Materiales,
    *,
    As_comp: float = 0.0,
    d_comp: float = 0.0,
    Ec: float | None = None,
) -> SeccionFisurada:
    """Inercia fisurada de una sección rectangular (comportamiento elástico).

    Equilibrio de momentos estáticos de la sección transformada respecto del eje
    neutro: ``b x²/2 + (n-1) As' (x - d') = n As (d - x)``, y
    ``Icr = b x³/3 + (n-1) As' (x - d')² + n As (d - x)²``.
    """
    if b <= 0 or d <= 0 or As <= 0 or As_comp < 0:
        raise ValueError("b, d y As tienen que ser positivos y As' no negativa")
    if As_comp > 0 and not 0 < d_comp < d:
        raise ValueError("d_comp tiene que estar entre 0 y d")
    ec = modulo_elasticidad(mat) if Ec is None else Ec
    n = ES / ec
    nc = (n - 1.0) * As_comp
    # (b/2) x² + (n As + nc) x - (n As d + nc d') = 0
    p, q = n * As + nc, n * As * d + nc * d_comp
    x = (-p + math.sqrt(p * p + 2.0 * b * q)) / b
    icr = b * x**3 / 3.0 + nc * (x - d_comp) ** 2 + n * As * (d - x) ** 2
    return SeccionFisurada(n, x, icr)


def inercia_efectiva(Ma: float, Mcr: float, Ig: float, Icr: float) -> float:
    """``Ie`` de ACI 318-19 §24.2.3.5 (mm⁴). ``Ma`` y ``Mcr`` en las mismas unidades.

    ``Ie = Ig`` si ``|Ma| ≤ (2/3) Mcr``; si no,
    ``Ie = Icr / (1 - ((2/3) Mcr / Ma)² (1 - Icr / Ig))``, que tiende a ``Icr``
    cuando ``Ma`` crece.
    """
    ma = abs(Ma)
    if Icr <= 0 or Ig <= 0 or Icr > Ig:
        raise ValueError("hace falta 0 < Icr ≤ Ig")
    if ma <= 2.0 / 3.0 * Mcr:
        return Ig
    return Icr / (1.0 - (2.0 / 3.0 * Mcr / ma) ** 2 * (1.0 - Icr / Ig))


# --- Flechas diferidas y límites ---------------------------------------------


def factor_xi(meses: float) -> float:
    """Factor ``ξ`` según la duración de la carga sostenida (§24.2.4.1.3).

    Toma los valores de la norma para 3, 6, 12 y 60 meses o más; entre ellos
    interpola linealmente (aproximación de la curva del comentario R24.2.4.1.3).
    """
    if meses < _XI[0][0]:
        raise ValueError("la duración de la carga sostenida tiene que ser de al menos 3 meses")
    if meses >= _XI[-1][0]:
        return _XI[-1][1]
    return float(np.interp(meses, [m for m, _ in _XI], [x for _, x in _XI]))


def factor_diferido(meses: float, rho_comp: float = 0.0) -> float:
    """Multiplicador de flecha diferida ``λΔ = ξ / (1 + 50 rho')`` (§24.2.4.1.1).

    ``rho_comp`` es ``rho' = As'/(b d)`` en el centro del tramo (en el apoyo para
    voladizos).
    """
    if rho_comp < 0:
        raise ValueError("rho' no puede ser negativa")
    return factor_xi(meses) / (1.0 + 50.0 * rho_comp)


def limite_flecha(luz: float, caso: str) -> float:
    """Flecha admisible (mismas unidades que ``luz``) para un caso de §24.2.2.

    ``caso`` es una clave de :data:`LIMITES_FLECHA`: ``"cubierta"`` (l/180),
    ``"piso"`` (l/360), ``"sensibles"`` (l/480) o ``"no_sensibles"`` (l/240).
    """
    try:
        divisor, _ = LIMITES_FLECHA[caso]
    except KeyError:
        raise ValueError(f"caso {caso!r}; los válidos son {', '.join(LIMITES_FLECHA)}") from None
    return luz / divisor


# --- Fisuración --------------------------------------------------------------


def separacion_maxima_fisuracion(fs: float, cc: float) -> float:
    """Separación máxima entre barras traccionadas, mm (§24.3.2).

    ``s ≤ 380 (280/fs) - 2.5 cc`` y ``s ≤ 300 (280/fs)``, con ``fs`` en MPa y
    ``cc`` el recubrimiento libre de la armadura más cercana a la cara
    traccionada, en mm.
    """
    if fs <= 0:
        raise ValueError("fs tiene que ser positiva")
    return min(380.0 * 280.0 / fs - 2.5 * cc, 300.0 * 280.0 / fs)


def separacion_libre_capa(capa: tuple[int, ...], seccion: SeccionRectangular) -> float:
    """Separación libre entre las barras de una capa repartidas de forma pareja, mm."""
    if len(capa) < 2:
        return math.inf
    ancho = seccion.b - 2.0 * (seccion.recubrimiento + seccion.d_estribo)
    return (ancho - sum(capa)) / (len(capa) - 1)


def separacion_barras(disp: DisposicionBarras, seccion: SeccionRectangular) -> float:
    """Separación entre centros de las barras de la capa más traccionada, mm.

    Supone las barras repartidas de forma pareja en el ancho libre entre estribos
    (como las ubica :func:`~nervi.design.aci318.elegir_barras`); con diámetros
    mezclados toma la separación libre más el diámetro mayor (del lado seguro).
    """
    capa = disp.capas[0]
    return separacion_libre_capa(capa, seccion) + max(capa)


@dataclass(frozen=True)
class Fisuracion:
    """Resultado de :func:`verificar_fisuracion`. Medidas en mm, tensiones en MPa."""

    s: float
    s_max: float
    fs: float
    cc: float
    #: ``True`` si ``fs`` se calculó con la sección fisurada y el momento de servicio.
    fs_calculada: bool

    @property
    def cumple(self) -> bool:
        return self.s <= self.s_max + 1e-9


def verificar_fisuracion(
    disp: DisposicionBarras,
    seccion: SeccionRectangular,
    mat: Materiales,
    *,
    Ms: float | None = None,
    Ec: float | None = None,
) -> Fisuracion:
    """Control de fisuración de una disposición de barras (§24.3.2).

    Sin ``Ms`` usa ``fs = (2/3) fy`` (§24.3.2.1). Con el momento de servicio ``Ms``
    (kN·m) calcula ``fs = n Ms (d - x) / Icr`` en la capa más traccionada. ``cc``
    es el recubrimiento libre (hasta el estribo, que es la barra más cercana a la
    cara traccionada).
    """
    avisar()
    if Ms is None:
        fs, calculada = 2.0 / 3.0 * mat.fy, False
    else:
        sf = seccion_fisurada(seccion.b, disp.d, disp.As, mat, Ec=Ec)
        fs = sf.n * abs(Ms) * 1e6 * (disp.dt - sf.x) / sf.Icr
        calculada = True
        if fs <= 0:
            fs = 1e-9
    cc = seccion.recubrimiento
    return Fisuracion(
        s=separacion_barras(disp, seccion),
        s_max=separacion_maxima_fisuracion(fs, cc),
        fs=fs,
        cc=cc,
        fs_calculada=calculada,
    )


# --- Flechas de una barra del modelo ------------------------------------------


@dataclass(frozen=True)
class FlechasViga:
    """Resultado de :func:`verificar_servicio_viga`. Flechas en mm, momentos en kN·m."""

    barra: int
    #: Luz de cálculo (la longitud de la barra), mm.
    luz: float
    #: Posición de la flecha máxima, mm desde el nudo i.
    x: float
    Ec: float
    Ig: float
    Mcr: float
    #: Momentos de servicio (permanentes y permanentes + sobrecarga) en el centro y
    #: en los extremos (``Ma_extremos`` vale 0 si el extremo no tiene momento negativo).
    Ma_D: float
    Ma_DL: float
    Ma_extremos_DL: tuple[float, float]
    #: Inercias fisuradas (centro y apoyos) y efectivas usadas, mm⁴.
    Icr_centro: float
    Icr_apoyo: float | None
    Ie_D: float
    Ie_DL: float
    #: Flechas inmediatas (permanentes, total y sobrecarga) y sostenida.
    delta_D: float
    delta_DL: float
    delta_L: float
    delta_sostenida: float
    #: Multiplicador diferido y flecha diferida adicional.
    lambda_delta: float
    delta_diferida: float
    #: Verificaciones ``(nombre, flecha, admisible, artículo)``.
    limites: tuple[tuple[str, float, float, str], ...]
    fisuracion_inferior: Fisuracion | None
    fisuracion_superior: Fisuracion | None
    avisos: tuple[str, ...] = field(default=())

    @property
    def cumple(self) -> bool:
        ok = all(f <= adm + 1e-9 for _, f, adm, _ in self.limites)
        for fis in (self.fisuracion_inferior, self.fisuracion_superior):
            ok = ok and (fis is None or fis.cumple)
        return ok

    def filas_memoria(self, elemento: str | None = None) -> list[tuple]:
        """Filas para :func:`nervi.memoria.tabla_verificaciones` (flechas en mm)."""
        nombre = f"Barra {self.barra}" if elemento is None else elemento
        filas: list[tuple] = [
            (nombre, f"Flecha {texto}", f, adm, art) for texto, f, adm, art in self.limites
        ]
        for lado, fis in (
            ("inferior", self.fisuracion_inferior),
            ("superior", self.fisuracion_superior),
        ):
            if fis is not None:
                filas.append(
                    (nombre, f"Separación armadura {lado}", fis.s, fis.s_max, "ACI 318-19 §24.3.2")
                )
        return filas


_A_KN = {"N": 1e-3, "kN": 1.0, "kgf": 9.80665e-3, "tf": 9.80665}
_A_M = {"mm": 1e-3, "cm": 1e-2, "m": 1.0}


def _estaciones(res, barra: int, casos) -> np.ndarray:
    """Unión de las estaciones de la barra en todos los casos."""
    return np.unique(np.concatenate([res[c].diagrama(barra)["x"] for c in casos]))


def _suma(res, barra: int, cargas: dict[str, float], comp: str, x: np.ndarray) -> np.ndarray:
    """Suma ``Σ f · comp`` interpolada en ``x`` (los casos pueden tener estaciones
    distintas, por ejemplo con cargas puntuales; cerca de un salto es aproximado)."""
    total = np.zeros(x.size)
    for caso, f in cargas.items():
        d = res[caso].diagrama(barra)
        total += f * np.interp(x, d["x"], d[comp])
    return total


def _como_factores(cargas) -> dict[str, float]:
    if isinstance(cargas, dict):
        return {str(k): float(v) for k, v in cargas.items()}
    return {str(k): 1.0 for k in cargas}


def verificar_servicio_viga(
    res,
    modelo,
    barra: int,
    diseno,
    seccion: SeccionRectangular,
    mat: Materiales,
    *,
    permanentes: list[str] | dict[str, float],
    sobrecargas: list[str] | dict[str, float] = (),
    fraccion_sostenida: float = 0.0,
    meses: float = 60.0,
    uso: str = "piso",
    elementos: str | None = "no_sensibles",
    As_comp_centro: float = 0.0,
    Ec: float | None = None,
    fs_calculada: bool = False,
    fuerza: str = "kN",
    longitud: str = "m",
) -> FlechasViga:
    """Flechas y fisuración de la barra ``barra`` ya diseñada con :func:`disenar_viga`.

    - ``permanentes`` y ``sobrecargas`` son los casos de carga (o ``{caso: factor}``)
      de servicio: cargas permanentes (D) y sobrecargas (L o de cubierta). Las
      sobrecargas se aplican todas juntas.
    - ``fraccion_sostenida`` es la parte de la sobrecarga que actúa en forma
      sostenida (por ejemplo 0.25 en depósitos); ``meses`` es la duración para ``ξ``.
    - ``uso`` es ``"piso"`` o ``"cubierta"`` (flecha inmediata por sobrecarga, l/360
      o l/180) y ``elementos`` dice si la barra soporta elementos no estructurales
      ``"sensibles"`` a flechas grandes (l/480), ``"no_sensibles"`` (l/240) o
      ninguno (``None``) (§24.2.2).
    - ``As_comp_centro`` es la armadura comprimida en el centro del tramo (mm²), para
      ``rho'`` del multiplicador diferido; por defecto 0, del lado seguro.

    La flecha elástica se toma del análisis (desplazamiento ``v`` de la barra
    respecto de la cuerda entre sus extremos) y se escala por ``EI`` del modelo /
    ``Ec Ie``. Vale para tramos entre apoyos, no para voladizos, y supone que la
    rigidez de la barra en el análisis es uniforme. ``fuerza`` y ``longitud`` son
    las unidades del modelo.
    """
    avisar()
    if uso not in ("piso", "cubierta"):
        raise ValueError("uso tiene que ser 'piso' o 'cubierta'")
    if elementos not in (None, "sensibles", "no_sensibles"):
        raise ValueError("elementos tiene que ser 'sensibles', 'no_sensibles' o None")
    if not 0.0 <= fraccion_sostenida <= 1.0:
        raise ValueError("fraccion_sostenida tiene que estar entre 0 y 1")
    if diseno.inferior is None:
        raise ValueError(
            f"la barra {barra} no tiene armadura inferior: no hay flecha que verificar"
        )
    try:
        ff, fl = _A_KN[fuerza], _A_M[longitud]
    except KeyError:
        raise ValueError(f"unidades no reconocidas: {fuerza}, {longitud}") from None

    cargas_d, cargas_l = _como_factores(permanentes), _como_factores(sobrecargas)
    if not cargas_d:
        raise ValueError("hace falta al menos un caso permanente")
    xm = _estaciones(res, barra, [*cargas_d, *cargas_l])  # unidades del modelo
    x = xm * fl * 1e3  # mm
    luz = float(x[-1])

    def cuerda(v: np.ndarray) -> np.ndarray:
        return v - (v[0] + (v[-1] - v[0]) * x / luz)

    v_d = cuerda(_suma(res, barra, cargas_d, "v", xm)) * fl * 1e3  # mm
    m_d = _suma(res, barra, cargas_d, "M", xm) * ff * fl  # kN·m
    if cargas_l:
        v_l = cuerda(_suma(res, barra, cargas_l, "v", xm)) * fl * 1e3
        m_l = _suma(res, barra, cargas_l, "M", xm) * ff * fl
    else:
        v_l, m_l = np.zeros_like(v_d), np.zeros_like(m_d)
    v_dl, m_dl = v_d + v_l, m_d + m_l

    k = int(np.argmax(np.abs(v_dl)))
    e, _, inercia = modelo.arreglos()["props"][barra]
    ei_modelo = e * inercia * ff * fl**2 * 1e9  # N·mm²

    ec = modulo_elasticidad(mat) if Ec is None else Ec
    ig = inercia_bruta(seccion)
    mcr = momento_fisuracion(seccion, mat)
    inf = diseno.inferior
    d_comp = seccion.recubrimiento + seccion.d_estribo + 8.0
    icr_c = seccion_fisurada(
        seccion.b,
        inf.d,
        inf.As,
        mat,
        As_comp=As_comp_centro,
        d_comp=d_comp if As_comp_centro > 0 else 0.0,
        Ec=ec,
    ).Icr
    sup = diseno.superior
    icr_a = seccion_fisurada(seccion.b, sup.d, sup.As, mat, Ec=ec).Icr if sup is not None else None

    def ie(m: np.ndarray) -> tuple[float, float, tuple[float, float]]:
        ma_pos = max(float(np.max(m)), 0.0)
        extremos = (max(-float(m[0]), 0.0), max(-float(m[-1]), 0.0))
        ie_c = inercia_efectiva(ma_pos, mcr, ig, icr_c) if ma_pos > 0 else ig
        negativos = [ma for ma in extremos if ma > 1e-9 * max(ma_pos, 1.0)]
        if negativos and icr_a is not None:
            ie_a = sum(inercia_efectiva(ma, mcr, ig, icr_a) for ma in negativos) / len(negativos)
            ie_c = 0.5 * (ie_c + ie_a)  # §24.2.3.6, promedio de secciones críticas
        return ie_c, ma_pos, extremos

    ie_d, ma_d, _ = ie(m_d)
    ie_dl, ma_dl, ext_dl = ie(m_dl)

    delta_d = abs(v_d[k]) * ei_modelo / (ec * ie_d)
    delta_dl = abs(v_dl[k]) * ei_modelo / (ec * ie_dl)
    delta_l = max(delta_dl - delta_d, 0.0)
    delta_sost = delta_d + fraccion_sostenida * delta_l

    rho_comp = As_comp_centro / (seccion.b * inf.d)
    lam = factor_diferido(meses, rho_comp)
    delta_dif = lam * delta_sost

    limites = []
    texto_uso = "inmediata por sobrecarga (" + ("cubierta" if uso == "cubierta" else "piso") + ")"
    limites.append((texto_uso, delta_l, limite_flecha(luz, uso), "ACI 318-19 §24.2.2"))
    if elementos is not None:
        texto = "diferida + sobrecarga (elementos " + elementos.replace("_", " ") + ")"
        limites.append(
            (texto, delta_dif + delta_l, limite_flecha(luz, elementos), "ACI 318-19 §24.2.2")
        )

    avisos = []
    if seccion.h > H_ARMADURA_PIEL:
        avisos.append(
            f"h = {seccion.h:g} mm > {H_ARMADURA_PIEL:g} mm: hace falta armadura de piel en las "
            "caras laterales (§9.7.2.3), que este módulo no dimensiona"
        )
    fis_inf = verificar_fisuracion(
        inf, seccion, mat, Ms=ma_dl if fs_calculada and ma_dl > 0 else None, Ec=ec
    )
    fis_sup = None
    if sup is not None:
        ms_sup = max(ext_dl) if fs_calculada and max(ext_dl) > 0 else None
        fis_sup = verificar_fisuracion(sup, seccion, mat, Ms=ms_sup, Ec=ec)

    return FlechasViga(
        barra=barra,
        luz=luz,
        x=float(x[k]),
        Ec=ec,
        Ig=ig,
        Mcr=mcr,
        Ma_D=ma_d,
        Ma_DL=ma_dl,
        Ma_extremos_DL=ext_dl,
        Icr_centro=icr_c,
        Icr_apoyo=icr_a,
        Ie_D=ie_d,
        Ie_DL=ie_dl,
        delta_D=delta_d,
        delta_DL=delta_dl,
        delta_L=delta_l,
        delta_sostenida=delta_sost,
        lambda_delta=lam,
        delta_diferida=delta_dif,
        limites=tuple(limites),
        fisuracion_inferior=fis_inf,
        fisuracion_superior=fis_sup,
        avisos=tuple(avisos),
    )
