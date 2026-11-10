# SPDX-License-Identifier: GPL-3.0-or-later
"""``modelo.json`` del esquema 1: validación y conversión a ``nervi.Modelo``.

La validación sigue ``docs/esquemas/nrv-modelo-v1.schema.json`` y las reglas
extra de ``docs/formato-nrv.md`` §4.1 (referencias, nudos distintos, rangos).
Se implementa a mano para no sumar una dependencia obligatoria.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..modelo import Modelo
from .errores import FormatoError

MIEMBRO = "modelo.json"

_UNIDADES = {"fuerza": ("N", "kN", "kgf", "tf"), "longitud": ("mm", "cm", "m")}

# lista -> (claves obligatorias, claves opcionales numéricas, claves opcionales booleanas)
_LISTAS: dict[str, tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]] = {
    "nudos": (("id", "x", "y"), (), ()),
    "barras": (("id", "i", "j", "E", "A", "I"), (), ()),
    "apoyos": (("nudo",), (), ("ux", "uy", "rz")),
    "resortes": (("nudo",), ("kx", "ky", "krz"), ()),
    "casos": (("id", "nombre"), (), ()),
    "cargas_nodales": (("caso", "nudo"), ("fx", "fy", "mz"), ()),
    "cargas_barra": (
        ("caso", "barra", "tipo", "ejes"),
        ("a", "b", "qx", "qy", "px", "py", "qx1", "qy1", "qx2", "qy2"),
        (),
    ),
    "desplazamientos_impuestos": (("caso", "nudo"), ("ux", "uy", "rz"), ()),
    "combinaciones": (("nombre", "factores"), (), ()),
}
_EXTRA = {"barras": ("liberaciones",)}
_IDS = ("id", "i", "j", "nudo", "barra", "caso")
_TEXTO = ("nombre", "tipo", "ejes")


#: tipo de carga en barra -> claves numéricas que admite
_CLAVES_CARGA: dict[str, tuple[str, ...]] = {
    "uniforme": ("qx", "qy"),
    "puntual": ("a", "px", "py"),
    "trapezoidal": ("a", "b", "qx1", "qy1", "qx2", "qy2"),
}
_TIPOS_CARGA = ("uniforme", "puntual", "trapezoidal")  # índice = tipo del contrato v2
_CLAVES_CARGA_TODAS = ("a", "b", "qx", "qy", "px", "py", "qx1", "qy1", "qx2", "qy2")


def _lista(claves) -> str:
    claves = [f"'{k}'" for k in claves]
    return ", ".join(claves[:-1]) + " y " + claves[-1] if len(claves) > 1 else claves[0]


def nuevo() -> dict:
    """``modelo.json`` vacío en kN y m."""
    return {
        "tipo": "portico_2d",
        "unidades": {"fuerza": "kN", "longitud": "m"},
        "nudos": [],
        "barras": [],
        "apoyos": [],
        "resortes": [],
        "casos": [],
        "cargas_nodales": [],
        "cargas_barra": [],
        "desplazamientos_impuestos": [],
        "combinaciones": [],
        "extensiones": {},
    }


def _err(motivo: str, ruta: str = "") -> FormatoError:
    return FormatoError(motivo, MIEMBRO, ruta)


def _es_numero(v: object) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _es_id(v: object) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and v >= 1


def _validar_item(lista: str, k: int, item: object) -> None:
    ruta = f"{lista}[{k}]"
    if not isinstance(item, dict):
        raise _err("tiene que ser un objeto", ruta)
    obligatorias, numeros, booleanos = _LISTAS[lista]
    permitidas = set(obligatorias) | set(numeros) | set(booleanos) | set(_EXTRA.get(lista, ()))
    for clave in obligatorias:
        if clave not in item:
            raise _err(f"falta la clave obligatoria '{clave}'", ruta)
    for clave, valor in item.items():
        sub = f"{ruta}.{clave}"
        if clave not in permitidas:
            raise _err("clave desconocida", sub)
        if clave in _IDS:
            if not _es_id(valor):
                raise _err(f"= {valor!r}: tiene que ser un entero ≥ 1", sub)
        elif clave in _TEXTO:
            if not isinstance(valor, str) or not valor:
                raise _err("tiene que ser un texto no vacío", sub)
        elif clave in booleanos:
            if not isinstance(valor, bool):
                raise _err("tiene que ser true o false", sub)
        elif clave == "liberaciones":
            if (
                not isinstance(valor, list)
                or len(valor) != 6
                or not all(isinstance(b, bool) for b in valor)
            ):
                raise _err("tiene que ser una lista de 6 valores true/false", sub)
        elif clave == "factores":
            if not isinstance(valor, dict) or not valor:
                raise _err("tiene que ser un objeto con al menos un caso", sub)
            for nombre, f in valor.items():
                if not _es_numero(f):
                    raise _err("el factor tiene que ser un número finito", f"{sub}.{nombre}")
        elif not _es_numero(valor):
            raise _err(f"= {valor!r}: tiene que ser un número finito", sub)


def validar(modelo: object) -> None:
    """Valida un ``modelo.json`` del esquema 1. Lanza :class:`FormatoError` con la
    ruta JSON del primer problema encontrado."""
    if not isinstance(modelo, dict):
        raise _err("tiene que ser un objeto JSON")
    for clave in ("tipo", "unidades", "nudos", "barras", "casos"):
        if clave not in modelo:
            raise _err(f"falta la clave obligatoria '{clave}'")
    for clave in modelo:
        if clave not in (*_LISTAS, "tipo", "unidades", "extensiones"):
            raise _err("clave desconocida", clave)
    if modelo["tipo"] != "portico_2d":
        raise _err(f"= {modelo['tipo']!r}: el esquema 1 solo admite 'portico_2d'", "tipo")
    unidades = modelo["unidades"]
    if not isinstance(unidades, dict) or set(unidades) != set(_UNIDADES):
        raise _err("tiene que tener exactamente 'fuerza' y 'longitud'", "unidades")
    for clave, validos in _UNIDADES.items():
        if unidades[clave] not in validos:
            raise _err(f"= {unidades[clave]!r}: valores válidos {validos}", f"unidades.{clave}")
    if not isinstance(modelo.get("extensiones", {}), dict):
        raise _err("tiene que ser un objeto", "extensiones")

    for lista in _LISTAS:
        items = modelo.get(lista, [])
        if not isinstance(items, list):
            raise _err("tiene que ser una lista", lista)
        for k, item in enumerate(items):
            _validar_item(lista, k, item)

    nudos = _ids_unicos(modelo, "nudos")
    barras = _ids_unicos(modelo, "barras")
    casos = _ids_unicos(modelo, "casos")
    nombres: set[str] = set()
    for k, c in enumerate(modelo["casos"]):
        if c["nombre"] in nombres:
            raise _err(f"nombre de caso repetido: {c['nombre']!r}", f"casos[{k}].nombre")
        nombres.add(c["nombre"])

    coords = {n["id"]: (n["x"], n["y"]) for n in modelo["nudos"]}
    longitudes = {}
    for k, b in enumerate(modelo["barras"]):
        for extremo in ("i", "j"):
            if b[extremo] not in nudos:
                raise _err(
                    f"= {b[extremo]}: no existe el nudo {b[extremo]}", f"barras[{k}].{extremo}"
                )
        if b["i"] == b["j"]:
            raise _err("los nudos i y j tienen que ser distintos", f"barras[{k}]")
        for prop in ("E", "A", "I"):
            if b[prop] <= 0:
                raise _err(f"= {b[prop]}: tiene que ser mayor que cero", f"barras[{k}].{prop}")
        (xi, yi), (xj, yj) = coords[b["i"]], coords[b["j"]]
        longitudes[b["id"]] = math.hypot(xj - xi, yj - yi)
        if longitudes[b["id"]] == 0:
            raise _err("la barra tiene longitud cero", f"barras[{k}]")

    _referencias(modelo, "apoyos", {"nudo": nudos})
    _referencias(modelo, "resortes", {"nudo": nudos})
    _referencias(modelo, "cargas_nodales", {"nudo": nudos, "caso": casos})
    _referencias(modelo, "desplazamientos_impuestos", {"nudo": nudos, "caso": casos})
    _referencias(modelo, "cargas_barra", {"barra": barras, "caso": casos})
    for lista in ("resortes",):
        for k, r in enumerate(modelo.get(lista, [])):
            for clave in ("kx", "ky", "krz"):
                if r.get(clave, 0.0) < 0:
                    raise _err("no puede ser negativa", f"{lista}[{k}].{clave}")
    for k, c in enumerate(modelo.get("cargas_barra", [])):
        ruta = f"cargas_barra[{k}]"
        if c["tipo"] not in _CLAVES_CARGA:
            raise _err(
                f"= {c['tipo']!r}: tiene que ser 'uniforme', 'puntual' o 'trapezoidal'",
                f"{ruta}.tipo",
            )
        if c["ejes"] not in ("local", "global"):
            raise _err(f"= {c['ejes']!r}: tiene que ser 'local' o 'global'", f"{ruta}.ejes")
        permitidas = _CLAVES_CARGA[c["tipo"]]
        sobran = [k2 for k2 in _CLAVES_CARGA_TODAS if k2 in c and k2 not in permitidas]
        if sobran:
            raise _err(f"una carga {c['tipo']} usa {_lista(permitidas)}, no {_lista(sobran)}", ruta)
        largo = longitudes[c["barra"]]
        if c["tipo"] == "puntual":
            if "a" not in c:
                raise _err("una carga puntual necesita 'a'", ruta)
            if not 0 <= c["a"] <= largo:
                raise _err(
                    f"= {c['a']}: tiene que estar entre 0 y la longitud de la barra ({largo:g})",
                    f"{ruta}.a",
                )
        elif c["tipo"] == "trapezoidal":
            a, b = c.get("a", 0.0), c.get("b", largo)
            if not 0 <= a < largo:
                raise _err(
                    f"= {a}: tiene que estar entre 0 y la longitud de la barra ({largo:g})",
                    f"{ruta}.a",
                )
            if not a < b <= largo:
                raise _err(
                    f"= {b}: tiene que ser mayor que a ({a:g}) y no pasar la longitud "
                    f"de la barra ({largo:g})",
                    f"{ruta}.b",
                )
    for k, comb in enumerate(modelo.get("combinaciones", [])):
        for nombre in comb["factores"]:
            if nombre not in nombres:
                raise _err(f"no existe el caso {nombre!r}", f"combinaciones[{k}].factores.{nombre}")


def _ids_unicos(modelo: dict, lista: str) -> set[int]:
    vistos: set[int] = set()
    for k, item in enumerate(modelo.get(lista, [])):
        if item["id"] in vistos:
            raise _err(f"= {item['id']}: id repetido", f"{lista}[{k}].id")
        vistos.add(item["id"])
    return vistos


def _referencias(modelo: dict, lista: str, claves: dict[str, set[int]]) -> None:
    nombre = {"nudo": "el nudo", "barra": "la barra", "caso": "el caso"}
    for k, item in enumerate(modelo.get(lista, [])):
        for clave, existentes in claves.items():
            if item[clave] not in existentes:
                raise _err(
                    f"= {item[clave]}: no existe {nombre[clave]} {item[clave]}",
                    f"{lista}[{k}].{clave}",
                )


@dataclass
class Indices:
    """Tablas ``id -> índice`` de ``nervi.Modelo`` y sus inversas."""

    nudos: dict[int, int] = field(default_factory=dict)
    barras: dict[int, int] = field(default_factory=dict)
    casos: dict[int, int] = field(default_factory=dict)

    def id_nudo(self, indice: int) -> int:
        return next(i for i, k in self.nudos.items() if k == indice)

    def id_barra(self, indice: int) -> int:
        return next(i for i, k in self.barras.items() if k == indice)


def construir_modelo(modelo: dict) -> tuple[Modelo, Indices]:
    """Arma un ``nervi.Modelo`` desde un ``modelo.json`` ya validado."""
    validar(modelo)
    m = Modelo()
    ind = Indices()
    for n in modelo["nudos"]:
        ind.nudos[n["id"]] = m.agregar_nudo(n["x"], n["y"])
    for b in modelo["barras"]:
        ind.barras[b["id"]] = m.agregar_barra(
            ind.nudos[b["i"]],
            ind.nudos[b["j"]],
            E=b["E"],
            A=b["A"],
            I=b["I"],
            liberaciones=tuple(b.get("liberaciones", [False] * 6)),
        )
    for a in modelo.get("apoyos", []):
        m.apoyar(ind.nudos[a["nudo"]], a.get("ux", False), a.get("uy", False), a.get("rz", False))
    for r in modelo.get("resortes", []):
        m.resorte(ind.nudos[r["nudo"]], r.get("kx", 0.0), r.get("ky", 0.0), r.get("krz", 0.0))
    for c in modelo["casos"]:
        ind.casos[c["id"]] = m.caso(c["nombre"])
    for c in modelo.get("cargas_nodales", []):
        m.carga_nodal(
            ind.casos[c["caso"]],
            ind.nudos[c["nudo"]],
            c.get("fx", 0.0),
            c.get("fy", 0.0),
            c.get("mz", 0.0),
        )
    for c in modelo.get("cargas_barra", []):
        caso, barra = ind.casos[c["caso"]], ind.barras[c["barra"]]
        if c["tipo"] == "uniforme":
            m.carga_uniforme(caso, barra, c.get("qx", 0.0), c.get("qy", 0.0), ejes=c["ejes"])
        elif c["tipo"] == "trapezoidal":
            m.carga_trapezoidal(
                caso,
                barra,
                qy1=c.get("qy1", 0.0),
                qy2=c.get("qy2", 0.0),
                a=c.get("a", 0.0),
                b=c.get("b"),
                qx1=c.get("qx1", 0.0),
                qx2=c.get("qx2", 0.0),
                ejes=c["ejes"],
            )
        else:
            m.carga_puntual(caso, barra, c["a"], c.get("px", 0.0), c.get("py", 0.0), ejes=c["ejes"])
    for d in modelo.get("desplazamientos_impuestos", []):
        m.desplazamiento_impuesto(
            ind.casos[d["caso"]],
            ind.nudos[d["nudo"]],
            d.get("ux", 0.0),
            d.get("uy", 0.0),
            d.get("rz", 0.0),
        )
    return m, ind


def desde_modelo(
    m: Modelo,
    combinaciones: dict[str, dict[str, float]] | None = None,
    fuerza: str = "kN",
    longitud: str = "m",
) -> dict:
    """Convierte un ``nervi.Modelo`` en ``modelo.json``. Los id son el índice + 1."""
    d = nuevo()
    d["unidades"] = {"fuerza": fuerza, "longitud": longitud}
    d["nudos"] = [{"id": k + 1, "x": x, "y": y} for k, (x, y) in enumerate(m._nudos)]
    for k, (i, j, E, A, I, lib) in enumerate(m._barras):
        barra = {"id": k + 1, "i": i + 1, "j": j + 1, "E": E, "A": A, "I": I}
        if any(lib):
            barra["liberaciones"] = list(lib)
        d["barras"].append(barra)
    for n, (ux, uy, rz) in sorted(m._restricciones.items()):
        d["apoyos"].append({"nudo": n + 1, "ux": ux, "uy": uy, "rz": rz})
    for n, (kx, ky, krz) in sorted(m._resortes.items()):
        d["resortes"].append({"nudo": n + 1, "kx": kx, "ky": ky, "krz": krz})
    for c, caso in enumerate(m._casos):
        d["casos"].append({"id": c + 1, "nombre": caso.nombre})
        for n, f in sorted(caso.nodales.items()):
            fx, fy, mz = (float(v) for v in f)
            d["cargas_nodales"].append({"caso": c + 1, "nudo": n + 1, "fx": fx, "fy": fy, "mz": mz})
        for n, u in sorted(caso.impuestos.items()):
            ux, uy, rz = (float(v) for v in u)
            d["desplazamientos_impuestos"].append(
                {"caso": c + 1, "nudo": n + 1, "ux": ux, "uy": uy, "rz": rz}
            )
    for caso, barra, tipo, ejes, a, vx, vy, b, vx2, vy2 in m._cargas_barra:
        if not 0 <= int(tipo) < len(_TIPOS_CARGA):
            raise _err(
                f"el tipo de carga en barra {int(tipo)} del contrato de datos todavía no "
                "tiene representación en el esquema 1",
                "cargas_barra",
            )
        carga = {
            "caso": int(caso) + 1,
            "barra": int(barra) + 1,
            "tipo": _TIPOS_CARGA[int(tipo)],
            "ejes": "global" if ejes else "local",
        }
        if tipo == 0:
            carga.update(qx=float(vx), qy=float(vy))
        elif tipo == 1:
            carga.update(a=float(a), px=float(vx), py=float(vy))
        else:
            carga.update(a=float(a), qx1=float(vx), qy1=float(vy), qx2=float(vx2), qy2=float(vy2))
            if not math.isnan(b):
                carga["b"] = float(b)  # sin "b": hasta el nudo j
        d["cargas_barra"].append(carga)
    for nombre, factores in (combinaciones or {}).items():
        d["combinaciones"].append({"nombre": nombre, "factores": dict(factores)})
    validar(d)
    return d
