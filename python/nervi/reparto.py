# SPDX-License-Identifier: GPL-3.0-or-later
"""Cargas por planta: reparto de las losas a sus vigas y muros (issue #78).

Cada losa del modelo físico carga a los bordes apoyados de su contorno por áreas
tributarias: cada punto de la losa va al borde apoyado más cercano, lo que en una
losa rectangular apoyada en los cuatro lados da los triángulos y trapecios a 45°
del método clásico. Un borde está apoyado si lo cubren entero vigas del mismo piso o
muros que llegan a ese piso o lo atraviesan, sobre la misma recta. El cálculo
geométrico va en Rust (``nervi_core::losas``, método y fuentes en su documentación);
acá se arman los datos y se presentan los resultados.

Cargas de cada losa, en kN/m² (``docs/formato-nrv.md`` §4f):

- ``peso_propio``: espesor por el peso específico del material (``peso`` en kN/m³,
  :data:`PESO_HORMIGON` si no se indica).
- ``permanente``: la que se suma al peso propio (pisos, contrapiso, cielorraso,
  tabiques repartidos). La de la losa, si la tiene, si no la de su piso.
- ``sobrecarga``: la de uso, con la misma regla.

Las cargas lineales salen en kN/m y las abscisas en la unidad de longitud del modelo
físico, medidas desde ``p1`` de la viga o del muro.

>>> from nervi.fisico import ModeloFisico
>>> mf = ModeloFisico()
>>> p0 = mf.agregar_piso("PB", 0.0)
>>> p1 = mf.agregar_piso("P1", 3.0, permanente=1.5, sobrecarga=2.0)
>>> h = mf.agregar_material("H-25", "hormigon", fc=25.0)
>>> v = mf.agregar_seccion("V 20x50", "rectangular", b=200.0, h=500.0)
>>> esquinas = [(0, 0), (6, 0), (6, 4), (0, 4)]
>>> for k in range(4):
...     _ = mf.agregar_viga(p1, esquinas[k], esquinas[(k + 1) % 4], v, h)
>>> _ = mf.agregar_losa(p1, esquinas, 120.0, h)
>>> r = mf.repartir_cargas()
>>> round(r.total("sobrecarga"), 9), round(r.total_losas("sobrecarga"), 9)
(48.0, 48.0)
>>> round(r.resultante(("vigas", 1), "sobrecarga"), 9)  # trapecio de 8 m² · 2 kN/m²
16.0
"""

from __future__ import annotations

import functools
import math
from dataclasses import dataclass, field

import numpy as np

from . import _core

#: Casos de carga del reparto, en este orden.
CASOS = ("peso_propio", "permanente", "sobrecarga")
#: Peso específico del hormigón armado cuando el material no da el suyo (kN/m³).
#: Valor usual de los reglamentos (por ejemplo CIRSOC 101-2005, tabla 1; ASCE 7-22,
#: tabla C3.1-2 da 23,6 para el hormigón simple sin armadura).
PESO_HORMIGON = 25.0
#: Factor de la unidad de longitud del modelo físico a metros.
A_METROS = {"mm": 1e-3, "cm": 1e-2, "m": 1.0}
#: Tolerancia geométrica relativa al tamaño del modelo (para decidir si una viga está
#: sobre un borde). No cambia la exactitud del reparto, que es cerrada.
TOL_RELATIVA = 1e-6

_TEXTO_MOTIVO = {
    "no_convexa": "no es convexa: todavía no se reparte (dividila en losas convexas)",
    "sin_apoyos": "no tiene ningún borde sobre una viga o un muro",
    "borde_parcial": "tiene un borde apoyado solo en parte: se toma como libre",
    "fuera_del_borde": (
        "tiene un borde libre que no se puede repartir por áreas tributarias "
        "(voladizo o borde oblicuo)"
    ),
}

Apoyo = tuple[str, int]  # ("vigas", id) o ("muros", id)


@dataclass(frozen=True)
class TramoCarga:
    """Carga trapezoidal de una losa sobre una viga o un muro, de ``a`` a ``b``."""

    losa: int
    apoyo: Apoyo
    piso: int
    a: float
    b: float
    #: Ancho tributario en ``a`` y en ``b``, en la unidad de longitud del modelo.
    ancho: tuple[float, float]
    #: Caso -> carga lineal en ``a`` y en ``b`` (kN/m).
    cargas: dict[str, tuple[float, float]]

    def resultante(self, caso: str) -> float:
        """Fuerza total del tramo en ``caso`` (kN)."""
        q1, q2 = self.cargas[caso]
        return 0.5 * (q1 + q2) * (self.b - self.a) * self._m

    _m: float = field(default=1.0, repr=False, compare=False)


@dataclass(frozen=True)
class ZonaTributaria:
    """Parte de la losa que carga a un borde, con los apoyos que lo cubren."""

    losa: int
    apoyos: tuple[Apoyo, ...]
    contorno: tuple[tuple[float, float], ...]


@dataclass(frozen=True)
class AvisoReparto:
    losa: int
    #: Lado del contorno (del punto ``lado`` al siguiente), si el aviso es de un lado.
    lado: int | None
    motivo: str

    @property
    def texto(self) -> str:
        donde = f" (lado {self.lado + 1})" if self.lado is not None else ""
        return f"La losa {self.losa}{donde} {_TEXTO_MOTIVO[self.motivo]}."


class RepartoCargas:
    """Resultado de :meth:`nervi.fisico.ModeloFisico.repartir_cargas`.

    Guarda los tramos en arreglos tal como salen del motor; :attr:`tramos` y
    :attr:`zonas` arman los objetos de Python recién cuando se piden, y las sumas por
    apoyo y totales se hacen sobre los arreglos."""

    casos = CASOS

    def __init__(self, longitud, cargas_losa, areas, ids_losas, apoyos, pisos_apoyo, salida):
        self.longitud: str = longitud
        #: Losa -> caso -> carga de superficie (kN/m²).
        self.cargas_losa: dict[int, dict[str, float]] = cargas_losa
        #: Losa -> área en planta (en la unidad de longitud al cuadrado).
        self.areas: dict[int, float] = areas
        self._ids_losas = ids_losas
        self._apoyos = apoyos
        self._pisos_apoyo = pisos_apoyo
        self._piezas = salida["piezas"]
        self._lineales = salida["cargas"]
        self._regiones = salida["regiones"]
        self._a_m = A_METROS[longitud]
        self.avisos: list[AvisoReparto] = [
            AvisoReparto(ids_losas[il], lado, motivo) for il, lado, motivo in salida["avisos"]
        ]
        #: Losas que se repartieron enteras.
        self.repartidas: set[int] = {ids_losas[k] for k, ok in enumerate(salida["repartida"]) if ok}
        # Filas de las piezas de cada apoyo (un muro puede figurar en varios pisos).
        unicos = list(dict.fromkeys(apoyos))
        numero = {a: k for k, a in enumerate(unicos)}
        clave = np.array([numero[a] for a in apoyos], dtype=np.int64)
        col = clave[self._piezas[:, 1].astype(np.int64)] if len(self._piezas) else clave[:0]
        orden = np.argsort(col, kind="stable")
        cortes = np.searchsorted(col[orden], np.arange(len(unicos) + 1))
        self._filas = {
            a: orden[cortes[k] : cortes[k + 1]]
            for k, a in enumerate(unicos)
            if cortes[k + 1] > cortes[k]
        }
        largo = self._piezas[:, 3] - self._piezas[:, 2] if len(self._piezas) else np.zeros(0)
        #: Fuerza de cada pieza en cada caso (kN), K x C.
        self._fuerzas = 0.5 * self._lineales.sum(axis=2) * (largo * self._a_m)[:, None]
        self._areas_piezas = (
            0.5
            * (self._piezas[:, 4] + self._piezas[:, 5] if len(self._piezas) else np.zeros(0))
            * largo
        )

    @functools.cached_property
    def tramos(self) -> list[TramoCarga]:
        """Todos los tramos de carga, por losa y en el orden de su contorno."""
        ids, apoyos, pisos = self._ids_losas, self._apoyos, self._pisos_apoyo
        return [
            TramoCarga(
                losa=ids[int(il)],
                apoyo=apoyos[int(ia)],
                piso=pisos[int(ia)],
                a=a,
                b=b,
                ancho=(wa, wb),
                cargas={c: tuple(q) for c, q in zip(CASOS, lineal, strict=True)},
                _m=self._a_m,
            )
            for (il, ia, a, b, wa, wb), lineal in zip(
                self._piezas.tolist(), self._lineales.tolist(), strict=True
            )
        ]

    @functools.cached_property
    def zonas(self) -> list[ZonaTributaria]:
        """Zonas tributarias de cada borde apoyado."""
        return [
            ZonaTributaria(
                losa=self._ids_losas[il],
                apoyos=tuple(self._apoyos[i] for i in ias),
                contorno=tuple(map(tuple, poligono.tolist())),
            )
            for il, ias, poligono in self._regiones
        ]

    def de(self, apoyo: Apoyo) -> list[TramoCarga]:
        """Tramos de carga sobre una viga (``("vigas", id)``) o un muro."""
        tramos = self.tramos
        return [tramos[k] for k in self._filas.get(apoyo, ())]

    def de_viga(self, id: int) -> list[TramoCarga]:
        return self.de(("vigas", id))

    def de_muro(self, id: int) -> list[TramoCarga]:
        return self.de(("muros", id))

    def resultante(self, apoyo: Apoyo, caso: str) -> float:
        """Fuerza total que recibe un apoyo en ``caso`` (kN)."""
        filas = self._filas.get(apoyo, ())
        return math.fsum(self._fuerzas[filas, CASOS.index(caso)]) if len(filas) else 0.0

    def area_tributaria(self, apoyo: Apoyo) -> float:
        """Área de losa que carga al apoyo (en la unidad de longitud al cuadrado)."""
        filas = self._filas.get(apoyo, ())
        return math.fsum(self._areas_piezas[filas]) if len(filas) else 0.0

    def total(self, caso: str) -> float:
        """Suma de las cargas que reciben vigas y muros en ``caso`` (kN)."""
        return math.fsum(self._fuerzas[:, CASOS.index(caso)])

    def total_losas(self, caso: str) -> float:
        """Carga total de las losas repartidas en ``caso`` (kN): tiene que ser igual a
        :meth:`total` (equilibrio global)."""
        m2 = self._a_m**2
        return math.fsum(
            self.cargas_losa[k][caso] * self.areas[k] * m2 for k in sorted(self.repartidas)
        )


def cargas_losa(mf, losa: dict) -> dict[str, float]:
    """Cargas de superficie de una losa (kN/m²) según las reglas del módulo."""
    ids = mf._ctx.ids  # solo lectura: sin copiar
    piso = ids["pisos"][losa["piso"]]
    material = ids["materiales"][losa["material"]]
    peso = material.get("peso", PESO_HORMIGON)
    return {
        "peso_propio": losa["espesor"] * 1e-3 * peso,
        "permanente": losa.get("permanente", piso.get("permanente", 0.0)),
        "sobrecarga": losa.get("sobrecarga", piso.get("sobrecarga", 0.0)),
    }


def _tolerancia(mf, vertices: np.ndarray, apoyos: np.ndarray) -> float:
    """``TOL_RELATIVA`` por la mayor coordenada del modelo (al menos 1 m)."""
    uno = 1.0 / A_METROS[mf.longitud]  # 1 m en la unidad del modelo
    mayor = max(float(np.abs(vertices).max(initial=0.0)), float(np.abs(apoyos).max(initial=0.0)))
    return TOL_RELATIVA * max(mayor, uno)


def repartir(mf, tol: float | None = None) -> RepartoCargas:
    """Reparte las losas de ``mf`` (:class:`nervi.fisico.ModeloFisico`) a sus apoyos."""
    # Se leen los datos sin copiarlos (el reparto no los cambia).
    datos = mf._datos
    a_m = A_METROS[mf.longitud]
    niveles = {p["id"]: p["nivel"] for p in datos["pisos"]}
    pisos = {i: k for k, i in enumerate(sorted(niveles, key=niveles.get))}

    apoyos: list[Apoyo] = []
    filas_apoyos: list = []
    grupos_apoyos: list[int] = []
    piso_apoyo: list[int] = []
    for v in datos["vigas"]:
        apoyos.append(("vigas", v["id"]))
        filas_apoyos.append([*v["p1"], *v["p2"]])
        grupos_apoyos.append(pisos[v["piso"]])
        piso_apoyo.append(v["piso"])
    for m in datos["muros"]:
        # El muro apoya las losas de los pisos que alcanza por encima de su base.
        for piso, nivel in niveles.items():
            if niveles[m["desde"]] < nivel <= niveles[m["hasta"]]:
                apoyos.append(("muros", m["id"]))
                filas_apoyos.append([*m["p1"], *m["p2"]])
                grupos_apoyos.append(pisos[piso])
                piso_apoyo.append(piso)

    losas = datos["losas"]
    vertices: list[list[float]] = []
    inicio = [0]
    for losa in losas:
        vertices += losa["contorno"]
        inicio.append(len(vertices))
    vertices = np.array(vertices, dtype=float).reshape(-1, 2)
    filas_apoyos = np.array(filas_apoyos, dtype=float).reshape(-1, 4)
    if tol is None:
        tol = _tolerancia(mf, vertices, filas_apoyos)
    q = {losa["id"]: cargas_losa(mf, losa) for losa in losas}
    # El motor multiplica la carga por el ancho (en la unidad del modelo): pasar kN/m²
    # por metro de esa unidad deja la carga lineal en kN/m.
    cargas = np.array(
        [[q[losa["id"]][c] * a_m for c in CASOS] for losa in losas], dtype=float
    ).reshape(len(losas), len(CASOS))
    salida = _core.repartir_losas(
        _core.VERSION_CONTRATO_LOSAS,
        vertices,
        np.array(inicio, dtype=np.int64),
        np.array([pisos[losa["piso"]] for losa in losas], dtype=np.int64),
        filas_apoyos,
        np.array(grupos_apoyos, dtype=np.int64),
        cargas,
        float(tol),
    )
    return RepartoCargas(
        mf.longitud,
        q,
        {losa["id"]: mf.area_losa(losa["id"]) for losa in losas},
        [losa["id"] for losa in losas],
        apoyos,
        piso_apoyo,
        salida,
    )
