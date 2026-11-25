# SPDX-License-Identifier: GPL-3.0-or-later
"""Modelo físico del edificio (issue #73, Fase 7).

Representa la estructura como la dibuja quien proyecta: **pisos** con su nivel,
**ejes**, **materiales**, **secciones** y los elementos **columnas**, **vigas**,
**losas** y **muros**, cada uno con su sección o espesor, material y ubicación. No
reemplaza al modelo analítico (``nervi.Modelo``, ``nervi.Modelo3D``): el modelo de
cálculo se generará desde el físico (#74). Se guarda en el módulo ``fisico`` del
``.nrv`` (``docs/formato-nrv.md`` §4f).

Unidades: coordenadas y niveles en la unidad de longitud del modelo físico
(``m`` por omisión); dimensiones de secciones y espesores en mm; resistencias y
módulos de elasticidad en MPa.

>>> mf = ModeloFisico()
>>> pb = mf.agregar_piso("Planta baja", 0.0)
>>> p1 = mf.agregar_piso("Piso 1", 3.0)
>>> h25 = mf.agregar_material("H-25", "hormigon", fc=25.0)
>>> c30 = mf.agregar_seccion("C 30x30", "rectangular", b=300.0, h=300.0)
>>> mf.agregar_columna((0.0, 0.0), pb, p1, c30, h25, nombre="C1")
1
>>> mf.altura_columna(1)
3.0
"""

from __future__ import annotations

import copy
import math
from collections.abc import Iterable, Sequence

from .formato import fisico as _formato
from .formato.errores import FormatoError

Punto = Sequence[float]

#: Qué listas pueden referirse a cada lista, y con qué claves.
_REFERENCIAS: dict[str, tuple[tuple[str, tuple[str, ...]], ...]] = {
    "pisos": (
        ("columnas", ("desde", "hasta")),
        ("vigas", ("piso",)),
        ("losas", ("piso",)),
        ("muros", ("desde", "hasta")),
    ),
    "materiales": (
        ("columnas", ("material",)),
        ("vigas", ("material",)),
        ("losas", ("material",)),
        ("muros", ("material",)),
    ),
    "secciones": (("columnas", ("seccion",)), ("vigas", ("seccion",))),
}


def _punto(p: Punto) -> list[float]:
    return [float(p[0]), float(p[1])] if len(p) == 2 else [*p]


class ModeloFisico:
    """Pisos, ejes, materiales, secciones y elementos del edificio.

    Guarda los datos tal cual van en ``fisico.json``: :meth:`a_json` y
    :meth:`desde_json` dan una ida y vuelta exacta. Cada ``agregar_*`` valida el
    elemento contra lo que ya hay y devuelve su ``id``; si algo no es válido lanza
    :class:`nervi.formato.FormatoError` con la ruta y el motivo, y el modelo no cambia.
    """

    def __init__(self, longitud: str = "m") -> None:
        datos = _formato.nuevo(longitud)
        _formato.validar(datos)
        self._datos = datos
        self._ctx = _formato.contexto(datos)

    # --- Ida y vuelta con fisico.json ------------------------------------------------
    @classmethod
    def desde_json(cls, datos: dict) -> ModeloFisico:
        """Toma una copia de ``fisico.json`` (por ejemplo ``Documento.fisico``)."""
        datos = copy.deepcopy(datos)
        ctx = _formato.contexto(datos)
        for lista in _formato.LISTAS:
            datos.setdefault(lista, [])
        mf = cls.__new__(cls)
        mf._datos, mf._ctx = datos, ctx
        return mf

    def a_json(self) -> dict:
        """Una copia de los datos, lista para ``Documento.fisico``."""
        return copy.deepcopy(self._datos)

    # --- Consulta ----------------------------------------------------------------------
    @property
    def longitud(self) -> str:
        """Unidad de las coordenadas y los niveles."""
        return self._datos["unidades"]["longitud"]

    def lista(self, nombre: str) -> list[dict]:
        """Copia de una lista (``"pisos"``, ``"vigas"``…), en el orden en que se agregó."""
        if nombre not in _formato.LISTAS:
            raise KeyError(f"no hay una lista {nombre!r}; válidas {_formato.LISTAS}")
        return copy.deepcopy(self._datos[nombre])

    def elemento(self, lista: str, id: int) -> dict:
        """Copia del elemento ``id`` de ``lista``."""
        try:
            return copy.deepcopy(self._ctx.ids[lista][id])
        except KeyError:
            raise KeyError(f"no existe {id} en {lista}") from None

    def pisos_ordenados(self) -> list[dict]:
        """Los pisos de abajo hacia arriba."""
        return sorted(self.lista("pisos"), key=lambda p: p["nivel"])

    def nivel(self, piso: int) -> float:
        return self._ctx.ids["pisos"][piso]["nivel"]

    def en_piso(self, piso: int) -> dict[str, list[dict]]:
        """Vigas y losas de un piso, y columnas y muros que llegan a él desde abajo."""
        if piso not in self._ctx.ids["pisos"]:
            raise KeyError(f"no existe el piso {piso}")
        return {
            "columnas": [e for e in self.lista("columnas") if e["hasta"] == piso],
            "vigas": [e for e in self.lista("vigas") if e["piso"] == piso],
            "losas": [e for e in self.lista("losas") if e["piso"] == piso],
            "muros": [e for e in self.lista("muros") if e["hasta"] == piso],
        }

    def altura_columna(self, id: int) -> float:
        c = self._ctx.ids["columnas"][id]
        return self.nivel(c["hasta"]) - self.nivel(c["desde"])

    def largo_viga(self, id: int) -> float:
        v = self._ctx.ids["vigas"][id]
        return math.dist(v["p1"], v["p2"])

    def area_losa(self, id: int) -> float:
        """Área en planta del contorno de la losa (siempre positiva)."""
        contorno = self._ctx.ids["losas"][id]["contorno"]
        return abs(_formato.area_poligono([tuple(p) for p in contorno]))

    def __len__(self) -> int:
        """Cantidad de elementos estructurales (columnas, vigas, losas y muros)."""
        return sum(len(self._datos[k]) for k in ("columnas", "vigas", "losas", "muros"))

    # --- Edición ----------------------------------------------------------------------
    def _agregar(self, lista: str, el: dict) -> int:
        el = {k: v for k, v in el.items() if v is not None}
        el = {"id": max(self._ctx.ids[lista], default=0) + 1, **el}
        _formato.validar_elemento(lista, el, self._ctx, f"{lista}[{len(self._datos[lista])}]")
        self._datos[lista].append(el)
        return el["id"]

    def agregar_piso(self, nombre: str, nivel: float) -> int:
        """Piso con su ``nivel`` (cota de la cara superior de la losa)."""
        return self._agregar("pisos", {"nombre": nombre, "nivel": nivel})

    def agregar_eje(self, nombre: str, p1: Punto, p2: Punto) -> int:
        return self._agregar("ejes", {"nombre": nombre, "p1": _punto(p1), "p2": _punto(p2)})

    def agregar_material(
        self,
        nombre: str,
        tipo: str,
        *,
        fc: float | None = None,
        fy: float | None = None,
        fu: float | None = None,
        E: float | None = None,
    ) -> int:
        """``tipo="hormigon"`` con ``fc`` o ``tipo="acero"`` con ``fy`` (y ``fu``), en MPa.
        ``E`` es opcional; sin ``E`` lo dará la norma que se use."""
        return self._agregar(
            "materiales", {"nombre": nombre, "tipo": tipo, "fc": fc, "fy": fy, "fu": fu, "E": E}
        )

    def agregar_seccion(
        self,
        nombre: str,
        forma: str,
        *,
        b: float | None = None,
        h: float | None = None,
        d: float | None = None,
    ) -> int:
        """``forma="rectangular"`` con ``b`` y ``h`` o ``"circular"`` con ``d``, en mm."""
        return self._agregar(
            "secciones", {"nombre": nombre, "forma": forma, "b": b, "h": h, "d": d}
        )

    def agregar_columna(
        self,
        punto: Punto,
        desde: int,
        hasta: int,
        seccion: int,
        material: int,
        *,
        nombre: str | None = None,
        angulo: float | None = None,
    ) -> int:
        """Columna en ``punto`` (planta) entre los pisos ``desde`` y ``hasta``.
        ``angulo``: giro de la sección en planta, en grados, antihorario desde X."""
        return self._agregar(
            "columnas",
            {
                "nombre": nombre,
                "punto": _punto(punto),
                "desde": desde,
                "hasta": hasta,
                "seccion": seccion,
                "material": material,
                "angulo": angulo,
            },
        )

    def agregar_viga(
        self,
        piso: int,
        p1: Punto,
        p2: Punto,
        seccion: int,
        material: int,
        *,
        nombre: str | None = None,
    ) -> int:
        """Viga del ``piso`` entre ``p1`` y ``p2`` (planta), con la cara superior en
        el nivel del piso."""
        return self._agregar(
            "vigas",
            {
                "nombre": nombre,
                "piso": piso,
                "p1": _punto(p1),
                "p2": _punto(p2),
                "seccion": seccion,
                "material": material,
            },
        )

    def agregar_losa(
        self,
        piso: int,
        contorno: Iterable[Punto],
        espesor: float,
        material: int,
        *,
        nombre: str | None = None,
        tipo: str | None = None,
    ) -> int:
        """Losa del ``piso`` con su ``contorno`` en planta (polígono simple, sin repetir
        el primer punto) y ``espesor`` en mm. ``tipo`` por omisión ``"maciza"``."""
        return self._agregar(
            "losas",
            {
                "nombre": nombre,
                "piso": piso,
                "contorno": [_punto(p) for p in contorno],
                "espesor": espesor,
                "material": material,
                "tipo": tipo,
            },
        )

    def agregar_muro(
        self,
        p1: Punto,
        p2: Punto,
        desde: int,
        hasta: int,
        espesor: float,
        material: int,
        *,
        nombre: str | None = None,
    ) -> int:
        """Muro sobre el eje ``p1``-``p2`` (planta) entre los pisos ``desde`` y
        ``hasta``, de ``espesor`` en mm."""
        return self._agregar(
            "muros",
            {
                "nombre": nombre,
                "p1": _punto(p1),
                "p2": _punto(p2),
                "desde": desde,
                "hasta": hasta,
                "espesor": espesor,
                "material": material,
            },
        )

    def quitar(self, lista: str, id: int) -> None:
        """Quita un elemento. Un piso, material o sección que algo usa no se quita."""
        if id not in self._ctx.ids.get(lista, {}):
            raise KeyError(f"no existe {id} en {lista}")
        for otra, claves in _REFERENCIAS.get(lista, ()):
            for el in self._datos[otra]:
                if any(el[c] == id for c in claves):
                    raise FormatoError(
                        f"no se puede quitar: lo usa {otra} {el['id']}",
                        _formato.MIEMBRO,
                        f"{lista}[id={id}]",
                    )
        self._datos[lista] = [e for e in self._datos[lista] if e["id"] != id]
        self._ctx = _formato.contexto(self._datos)
