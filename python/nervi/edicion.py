# SPDX-License-Identifier: GPL-3.0-or-later
"""Ediciones geométricas del modelo de cálculo (``modelo.json`` del pórtico plano).

Lo que hacen las herramientas de dibujo de la vista 2D, sin Qt: agregar nudos y
barras uniendo y partiendo lo que ya hay, poner apoyos y cargas, y quitar nudos y
barras con lo que depende de ellos. Cada función cambia el ``dict`` que recibe; quien
la llama trabaja sobre una copia y la aplica con :meth:`nervi.proyecto.Proyecto.editar`.

>>> m = {"unidades": {"fuerza": "kN", "longitud": "m"}, "nudos": [], "barras": [],
...      "casos": [], "cargas_barra": []}
>>> agregar_barra(m, (0, 0), (6, 0), propiedades_por_omision(m["unidades"]))
[1]
>>> agregar_nudo(m, (2, 0))  # cae sobre la barra 1: la parte
3
>>> [(b["id"], b["i"], b["j"]) for b in m["barras"]]
[(1, 1, 3), (2, 3, 2)]
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from itertools import pairwise

from .enganche import partir

__all__ = [
    "APOYOS",
    "agregar_barra",
    "agregar_carga_barra",
    "agregar_carga_nodal",
    "agregar_nudo",
    "caso",
    "nudo_en",
    "partir_barra",
    "poner_apoyo",
    "propiedades_por_omision",
    "quitar_barra",
    "quitar_nudo",
    "tipo_apoyo",
    "tolerancia",
]

Punto = tuple[float, float]

#: Tipos de apoyo: nombre y GDL restringidos (``ux``, ``uy``, ``rz``).
APOYOS = {
    "empotrado": ("Empotramiento", (True, True, True)),
    "articulado": ("Articulación", (True, True, False)),
    "movil_x": ("Móvil (se desliza en x)", (False, True, False)),
    "movil_y": ("Móvil (se desliza en y)", (True, False, False)),
}

#: Metros de cada unidad de longitud y kN de cada unidad de fuerza.
_METROS = {"mm": 1e-3, "cm": 1e-2, "m": 1.0}
_KN = {"N": 1e-3, "kN": 1.0, "kgf": 9.80665e-3, "tf": 9.80665}


def tolerancia(unidades: dict) -> float:
    """Distancia (en la unidad del modelo) por debajo de la cual dos puntos son el mismo:
    una micra."""
    return 1e-6 / _METROS[unidades["longitud"]]


def propiedades_por_omision(unidades: dict) -> dict[str, float]:
    """``E``, ``A`` e ``I`` de una barra de hormigón de 30 x 30 cm (E = 25 GPa) en las
    unidades del modelo, para dibujar sin cargar antes las secciones."""
    m, kn = _METROS[unidades["longitud"]], _KN[unidades["fuerza"]]
    return {
        "E": 2.5e7 * m**2 / kn,
        "A": 0.09 / m**2,
        "I": 0.3**4 / 12 / m**4,
    }


def _nuevo_id(lista: list[dict]) -> int:
    return max((x["id"] for x in lista), default=0) + 1


def _xy(modelo: dict) -> dict[int, Punto]:
    return {n["id"]: (n["x"], n["y"]) for n in modelo["nudos"]}


def _largo(a: Punto, b: Punto) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def nudo_en(modelo: dict, p: Sequence[float], tol: float | None = None) -> int | None:
    """El nudo que está en ``p`` (a menos de ``tol``), o ``None``."""
    tol = tolerancia(modelo["unidades"]) if tol is None else tol
    for n in modelo["nudos"]:
        if math.hypot(n["x"] - p[0], n["y"] - p[1]) <= tol:
            return n["id"]
    return None


def agregar_nudo(modelo: dict, p: Sequence[float], tol: float | None = None) -> int:
    """Agrega un nudo en ``p`` y devuelve su id. Si ya hay uno ahí, devuelve ese. Si cae
    en el medio de una barra, la parte en dos."""
    tol = tolerancia(modelo["unidades"]) if tol is None else tol
    hay = nudo_en(modelo, p, tol)
    if hay is not None:
        return hay
    nid = _nuevo_id(modelo["nudos"])
    modelo["nudos"].append({"id": nid, "x": float(p[0]), "y": float(p[1])})
    xy = _xy(modelo)
    for b in list(modelo["barras"]):
        if partir((xy[b["i"]], xy[b["j"]]), [p], tol):
            partir_barra(modelo, b["id"], nid)
    return nid


def partir_barra(modelo: dict, barra: int, nudo: int) -> tuple[int, int]:
    """Parte la barra ``barra`` en el nudo ``nudo`` (que tiene que estar sobre ella).

    La barra conserva el tramo del lado ``i`` y la nueva el del lado ``j``, con las
    mismas propiedades; cada una lleva las liberaciones de su extremo original. Las
    cargas se reparten: las uniformes y térmicas van a las dos, las puntuales y los
    momentos al tramo que las tiene (con ``a`` medido desde su nudo ``i``) y las
    trapezoidales se cortan con los valores interpolados. Devuelve los dos ids."""
    xy = _xy(modelo)
    b = next(x for x in modelo["barras"] if x["id"] == barra)
    pi, pj, pn = xy[b["i"]], xy[b["j"]], xy[nudo]
    largo, corte = _largo(pi, pj), _largo(pi, pn)
    nueva = {**b, "id": _nuevo_id(modelo["barras"]), "i": nudo}
    b["j"] = nudo
    if "liberaciones" in b:
        lib = list(b["liberaciones"])
        b["liberaciones"] = lib[:3] + [False] * 3
        nueva["liberaciones"] = [False] * 3 + lib[3:]
    modelo["barras"].insert(modelo["barras"].index(b) + 1, nueva)
    cargas = []
    for c in modelo.get("cargas_barra", []):
        if c["barra"] != barra:
            cargas.append(c)
            continue
        for bid, s0, s1 in ((barra, 0.0, corte), (nueva["id"], corte, largo)):
            parte = _cortar_carga(c, s0, s1, largo)
            if parte is not None:
                cargas.append({**parte, "barra": bid})
    if "cargas_barra" in modelo:
        modelo["cargas_barra"] = cargas
    return barra, nueva["id"]


def _cortar_carga(c: dict, s0: float, s1: float, largo: float) -> dict | None:
    """La parte de la carga ``c`` (de una barra de ``largo``) que cae en ``[s0, s1]``,
    con las posiciones medidas desde ``s0``; ``None`` si no le toca nada."""
    tipo = c["tipo"]
    if tipo in ("uniforme", "termica"):
        return dict(c)
    if tipo in ("puntual", "momento"):
        a = c["a"]
        # Una carga justo en el corte va al primer tramo.
        if s0 <= a <= s1 and not (a == s0 and s0 > 0.0):
            return {**c, "a": a - s0}
        return None
    if tipo == "trapezoidal":
        a, b = c.get("a", 0.0), c.get("b", largo)
        lo, hi = max(a, s0), min(b, s1)
        if hi - lo <= 1e-12 * max(largo, 1.0):
            return None

        def valor(clave1: str, clave2: str, s: float) -> float:
            q1, q2 = c.get(clave1, 0.0), c.get(clave2, 0.0)
            return q1 + (q2 - q1) * (s - a) / (b - a)

        nueva = {k: v for k, v in c.items() if k not in ("a", "b", "qx1", "qy1", "qx2", "qy2")}
        nueva.update(
            a=lo - s0,
            b=hi - s0,
            qx1=valor("qx1", "qx2", lo),
            qy1=valor("qy1", "qy2", lo),
            qx2=valor("qx1", "qx2", hi),
            qy2=valor("qy1", "qy2", hi),
        )
        return nueva
    raise ValueError(f"tipo de carga {tipo!r}")


def agregar_barra(
    modelo: dict,
    a: Sequence[float],
    b: Sequence[float],
    propiedades: dict[str, float],
    tol: float | None = None,
) -> list[int]:
    """Agrega una barra de ``a`` a ``b`` con ``propiedades`` (``E``, ``A``, ``I``).

    Usa los nudos que ya hay en los extremos o los crea (partiendo las barras sobre las
    que caen) y se parte en cada nudo por el que pasa. Un tramo que ya existe entre los
    mismos nudos no se repite. Devuelve los ids de las barras nuevas."""
    tol = tolerancia(modelo["unidades"]) if tol is None else tol
    if _largo(a, b) <= tol:
        raise ValueError("La barra tiene que tener largo")
    ni, nj = agregar_nudo(modelo, a, tol), agregar_nudo(modelo, b, tol)
    xy = _xy(modelo)
    pa, pb = xy[ni], xy[nj]
    otros = [(nid, q) for nid, q in xy.items() if nid not in (ni, nj)]
    ts = partir((pa, pb), [q for _, q in otros], tol)
    en_medio = []
    for t in ts:
        q = (pa[0] + t * (pb[0] - pa[0]), pa[1] + t * (pb[1] - pa[1]))
        en_medio.append(min(otros, key=lambda o, q=q: _largo(o[1], q))[0])
    cadena = [ni, *en_medio, nj]
    hay = {frozenset((x["i"], x["j"])) for x in modelo["barras"]}
    nuevas = []
    for i, j in pairwise(cadena):
        if frozenset((i, j)) in hay:
            continue
        bid = _nuevo_id(modelo["barras"])
        modelo["barras"].append({"id": bid, "i": i, "j": j, **propiedades})
        nuevas.append(bid)
    if not nuevas:
        raise ValueError("Esa barra ya está")
    return nuevas


def poner_apoyo(modelo: dict, nudo: int, tipo: str | None) -> None:
    """Pone en ``nudo`` un apoyo del ``tipo`` de :data:`APOYOS`, o lo saca con ``None``."""
    apoyos = [a for a in modelo.setdefault("apoyos", []) if a["nudo"] != nudo]
    if tipo is not None:
        ux, uy, rz = APOYOS[tipo][1]
        apoyos.append({"nudo": nudo, "ux": ux, "uy": uy, "rz": rz})
        apoyos.sort(key=lambda a: a["nudo"])
    modelo["apoyos"] = apoyos


def tipo_apoyo(apoyo: dict | None) -> str | None:
    """La clave de :data:`APOYOS` de un apoyo, o ``None`` si no es uno de esos."""
    if apoyo is None:
        return None
    gdl = (bool(apoyo.get("ux")), bool(apoyo.get("uy")), bool(apoyo.get("rz")))
    return next((k for k, (_, g) in APOYOS.items() if g == gdl), None)


def caso(modelo: dict, nombre: str) -> int:
    """El id del caso ``nombre``; lo crea si no existe."""
    for c in modelo.setdefault("casos", []):
        if c["nombre"] == nombre:
            return c["id"]
    cid = _nuevo_id(modelo["casos"])
    modelo["casos"].append({"id": cid, "nombre": nombre})
    return cid


def agregar_carga_nodal(
    modelo: dict, caso_id: int, nudo: int, fx: float = 0.0, fy: float = 0.0, mz: float = 0.0
) -> None:
    """Agrega una carga en el nudo ``nudo`` del caso ``caso_id``."""
    if not (fx or fy or mz):
        raise ValueError("La carga es nula: poné Fx, Fy o Mz")
    modelo.setdefault("cargas_nodales", []).append(
        {"caso": caso_id, "nudo": nudo, "fx": fx, "fy": fy, "mz": mz}
    )


def agregar_carga_barra(modelo: dict, caso_id: int, barra: int, carga: dict) -> None:
    """Agrega a ``barra`` una carga del caso ``caso_id`` (``carga`` con ``tipo``,
    ``ejes`` y sus valores, como en ``modelo.json``)."""
    valores = [v for k, v in carga.items() if k not in ("tipo", "ejes", "a", "b")]
    if not any(valores):
        raise ValueError("La carga es nula")
    modelo.setdefault("cargas_barra", []).append({"caso": caso_id, "barra": barra, **carga})


def quitar_barra(modelo: dict, barra: int) -> None:
    """Quita la barra y sus cargas (los nudos quedan)."""
    modelo["barras"] = [b for b in modelo["barras"] if b["id"] != barra]
    if "cargas_barra" in modelo:
        modelo["cargas_barra"] = [c for c in modelo["cargas_barra"] if c["barra"] != barra]


def quitar_nudo(modelo: dict, nudo: int) -> None:
    """Quita el nudo con sus barras, su apoyo, sus resortes, sus cargas y sus
    desplazamientos impuestos."""
    for b in [b for b in modelo["barras"] if nudo in (b["i"], b["j"])]:
        quitar_barra(modelo, b["id"])
    modelo["nudos"] = [n for n in modelo["nudos"] if n["id"] != nudo]
    for lista in ("apoyos", "resortes", "cargas_nodales", "desplazamientos_impuestos"):
        if lista in modelo:
            modelo[lista] = [x for x in modelo[lista] if x["nudo"] != nudo]
