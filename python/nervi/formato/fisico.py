# SPDX-License-Identifier: GPL-3.0-or-later
"""Módulo ``fisico`` del formato ``.nrv`` (``fisico.json``, versión 2).

El modelo físico describe el edificio como lo dibuja quien proyecta: pisos con su
nivel, ejes, y vigas, columnas, losas y muros con su sección, material y
contorno (issue #73, Fase 7). La versión 2 suma las cargas de superficie de pisos
y losas y el peso específico de los materiales (issue #78). Es independiente de
``modelo.json``, el modelo analítico de barras: el modelo de cálculo se generará
desde el físico (#74). Reglas en ``docs/formato-nrv.md`` §4f.

>>> d = nuevo()
>>> d["unidades"]
{'longitud': 'm'}
>>> validar(d)
"""

from __future__ import annotations

import copy
import math

from .errores import FormatoError

MIEMBRO = "fisico.json"

#: Unidades de longitud de coordenadas y niveles. Secciones y espesores van en mm.
UNIDADES_LONGITUD = ("mm", "cm", "m")
TIPOS_MATERIAL = ("hormigon", "acero")
FORMAS_SECCION = ("rectangular", "circular")
#: Tipos de losa de la versión 1. Los que siguen (nervadas, mixtas con steel deck y
#: pretensadas, decisión del 25/11/2026) suben la versión del módulo al entrar.
TIPOS_LOSA = ("maciza",)
MAX_NOMBRE = 100

#: Listas del módulo, en el orden en que se validan (las referencias van hacia atrás).
LISTAS = ("pisos", "ejes", "materiales", "secciones", "columnas", "vigas", "losas", "muros")

# lista -> (claves obligatorias, claves opcionales)
_CLAVES: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "pisos": (("id", "nombre", "nivel"), ("permanente", "sobrecarga")),
    "ejes": (("id", "nombre", "p1", "p2"), ()),
    "materiales": (("id", "nombre", "tipo"), ("fc", "fy", "fu", "E", "peso")),
    "secciones": (("id", "nombre", "forma"), ("b", "h", "d")),
    "columnas": (("id", "punto", "desde", "hasta", "seccion", "material"), ("nombre", "angulo")),
    "vigas": (("id", "piso", "p1", "p2", "seccion", "material"), ("nombre",)),
    "losas": (
        ("id", "piso", "contorno", "espesor", "material"),
        ("nombre", "tipo", "permanente", "sobrecarga"),
    ),
    "muros": (("id", "p1", "p2", "desde", "hasta", "espesor", "material"), ("nombre",)),
}
# Listas cuyos nombres no se pueden repetir (los usan las demás para referirse a ellos
# en los planos). Los elementos sí pueden repetir nombre: la columna C1 de cada piso.
_NOMBRES_UNICOS = ("pisos", "ejes", "materiales", "secciones")

_DEFECTO: dict = {"unidades": {"longitud": "m"}, **{lista: [] for lista in LISTAS}}


def nuevo(longitud: str = "m") -> dict:
    """Un modelo físico vacío, con coordenadas y niveles en ``longitud``."""
    d = copy.deepcopy(_DEFECTO)
    d["unidades"]["longitud"] = longitud
    return d


def _err(motivo: str, ruta: str) -> FormatoError:
    return FormatoError(motivo, MIEMBRO, ruta)


def _es_numero(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _es_id(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and v >= 1


def _numero(el: dict, clave: str, ruta: str, positivo: bool = False) -> float:
    v = el[clave]
    if not _es_numero(v):
        raise _err("tiene que ser un número finito", f"{ruta}.{clave}")
    if positivo and v <= 0:
        raise _err("tiene que ser mayor que 0", f"{ruta}.{clave}")
    return float(v)


#: Cargas de superficie de pisos y losas (kN/m², versión 2): ``permanente`` es la
#: permanente que se suma al peso propio de la losa (pisos, contrapiso, cielorraso,
#: tabiques repartidos) y ``sobrecarga`` la de uso. La de la losa reemplaza a la del piso.
CARGAS_SUPERFICIE = ("permanente", "sobrecarga")


def _cargas(el: dict, ruta: str) -> None:
    for clave in CARGAS_SUPERFICIE:
        if clave in el:
            if _numero(el, clave, ruta) < 0:
                raise _err("no puede ser negativa", f"{ruta}.{clave}")


def _punto(v, ruta: str) -> tuple[float, float]:
    if not isinstance(v, list) or len(v) != 2 or not all(_es_numero(c) for c in v):
        raise _err("tiene que ser un punto [x, y] de números finitos", ruta)
    return (float(v[0]), float(v[1]))


def _referencia(el: dict, clave: str, ids: dict[int, dict], que: str, ruta: str) -> dict:
    v = el[clave]
    if not _es_id(v):
        raise _err("tiene que ser un id entero ≥ 1", f"{ruta}.{clave}")
    if v not in ids:
        raise _err(f"no existe {que} {v}", f"{ruta}.{clave}")
    return ids[v]


def _orientacion(a, b, c) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _en_segmento(a, b, p) -> bool:
    return min(a[0], b[0]) <= p[0] <= max(a[0], b[0]) and min(a[1], b[1]) <= p[1] <= max(a[1], b[1])


def _se_tocan(a, b, c, d) -> bool:
    """Si los segmentos ``ab`` y ``cd`` tienen algún punto en común (prueba exacta
    de orientaciones; Cormen et al., *Introduction to Algorithms*, §33.1)."""
    o1, o2 = _orientacion(c, d, a), _orientacion(c, d, b)
    o3, o4 = _orientacion(a, b, c), _orientacion(a, b, d)
    if ((o1 > 0 and o2 < 0) or (o1 < 0 and o2 > 0)) and (
        (o3 > 0 and o4 < 0) or (o3 < 0 and o4 > 0)
    ):
        return True
    return (
        (o1 == 0 and _en_segmento(c, d, a))
        or (o2 == 0 and _en_segmento(c, d, b))
        or (o3 == 0 and _en_segmento(a, b, c))
        or (o4 == 0 and _en_segmento(a, b, d))
    )


def area_poligono(puntos: list[tuple[float, float]]) -> float:
    """Área con signo de un polígono (fórmula del agrimensor o de Gauss):
    positiva si el contorno va en sentido antihorario."""
    n = len(puntos)
    return 0.5 * sum(
        puntos[k][0] * puntos[(k + 1) % n][1] - puntos[(k + 1) % n][0] * puntos[k][1]
        for k in range(n)
    )


def _contorno(v, ruta: str) -> list[tuple[float, float]]:
    if not isinstance(v, list) or len(v) < 3:
        raise _err("tiene que ser una lista de al menos 3 puntos", ruta)
    puntos = [_punto(p, f"{ruta}[{k}]") for k, p in enumerate(v)]
    n = len(puntos)
    if len(set(puntos)) != n:
        raise _err("tiene puntos repetidos (el contorno se cierra solo)", ruta)
    # Polígono simple: lados no consecutivos sin puntos en común.
    for k in range(n):
        a, b = puntos[k], puntos[(k + 1) % n]
        for m in range(k + 2, n):
            if k == 0 and m == n - 1:
                continue
            if _se_tocan(a, b, puntos[m], puntos[(m + 1) % n]):
                raise _err(f"el contorno se corta a sí mismo (lados {k} y {m})", ruta)
    if area_poligono(puntos) == 0:
        raise _err("el contorno no encierra área", ruta)
    return puntos


def _nombre(el: dict, ruta: str) -> None:
    if "nombre" not in el:
        return
    v = el["nombre"]
    if not isinstance(v, str) or not v.strip():
        raise _err("tiene que ser un texto no vacío", f"{ruta}.nombre")
    if len(v) > MAX_NOMBRE:
        raise _err(f"tiene más de {MAX_NOMBRE} caracteres", f"{ruta}.nombre")


class _Contexto:
    """Lo ya validado de cada lista, para resolver referencias."""

    def __init__(self) -> None:
        self.ids: dict[str, dict[int, dict]] = {lista: {} for lista in LISTAS}
        self.nombres: dict[str, set[str]] = {lista: set() for lista in _NOMBRES_UNICOS}


def _validar_material(el: dict, ruta: str) -> None:
    tipo = el["tipo"]
    if tipo not in TIPOS_MATERIAL:
        raise _err(f"tiene que ser uno de {TIPOS_MATERIAL}", f"{ruta}.tipo")
    propias = {"hormigon": ("fc", "E"), "acero": ("fy", "fu", "E")}[tipo]
    if "peso" in el:
        _numero(el, "peso", ruta, positivo=True)
    for clave in ("fc", "fy", "fu", "E"):
        if clave in el and clave not in propias:
            raise _err(f"no corresponde a un material de tipo {tipo!r}", f"{ruta}.{clave}")
    obligatoria = "fc" if tipo == "hormigon" else "fy"
    if obligatoria not in el:
        raise _err("falta esta clave", f"{ruta}.{obligatoria}")
    for clave in propias:
        if clave in el:
            _numero(el, clave, ruta, positivo=True)
    if "fu" in el and el["fu"] < el["fy"]:
        raise _err("tiene que ser mayor o igual que fy", f"{ruta}.fu")


def _validar_seccion(el: dict, ruta: str) -> None:
    forma = el["forma"]
    if forma not in FORMAS_SECCION:
        raise _err(f"tiene que ser una de {FORMAS_SECCION}", f"{ruta}.forma")
    propias = {"rectangular": ("b", "h"), "circular": ("d",)}[forma]
    for clave in ("b", "h", "d"):
        if clave in el and clave not in propias:
            raise _err(f"no corresponde a una sección {forma}", f"{ruta}.{clave}")
        if clave in propias:
            if clave not in el:
                raise _err("falta esta clave", f"{ruta}.{clave}")
            _numero(el, clave, ruta, positivo=True)


def _tramo_vertical(el: dict, ctx: _Contexto, ruta: str) -> None:
    desde = _referencia(el, "desde", ctx.ids["pisos"], "el piso", ruta)
    hasta = _referencia(el, "hasta", ctx.ids["pisos"], "el piso", ruta)
    if hasta["nivel"] <= desde["nivel"]:
        raise _err("el piso 'hasta' tiene que estar más arriba que 'desde'", f"{ruta}.hasta")


def _hormigon(el: dict, ctx: _Contexto, ruta: str) -> None:
    mat = _referencia(el, "material", ctx.ids["materiales"], "el material", ruta)
    if mat["tipo"] != "hormigon":
        raise _err("tiene que ser un material de hormigón", f"{ruta}.material")


def validar_elemento(lista: str, el, ctx: _Contexto, ruta: str) -> None:
    """Valida un elemento de ``lista`` contra lo ya validado en ``ctx`` y lo suma."""
    if not isinstance(el, dict):
        raise _err("tiene que ser un objeto", ruta)
    obligatorias, opcionales = _CLAVES[lista]
    for clave in el:
        if clave not in obligatorias and clave not in opcionales:
            raise _err("clave desconocida", f"{ruta}.{clave}")
    for clave in obligatorias:
        if clave not in el:
            raise _err("falta esta clave", f"{ruta}.{clave}")
    if not _es_id(el["id"]):
        raise _err("tiene que ser un entero ≥ 1", f"{ruta}.id")
    if el["id"] in ctx.ids[lista]:
        raise _err(f"id repetido en {lista}", f"{ruta}.id")
    _nombre(el, ruta)
    if lista in _NOMBRES_UNICOS:
        if el["nombre"] in ctx.nombres[lista]:
            raise _err(f"nombre repetido en {lista}", f"{ruta}.nombre")

    if lista == "pisos":
        nivel = _numero(el, "nivel", ruta)
        if any(p["nivel"] == nivel for p in ctx.ids["pisos"].values()):
            raise _err("ya hay un piso en este nivel", f"{ruta}.nivel")
        _cargas(el, ruta)
    elif lista == "ejes":
        if _punto(el["p1"], f"{ruta}.p1") == _punto(el["p2"], f"{ruta}.p2"):
            raise _err("tiene que ser distinto de p1", f"{ruta}.p2")
    elif lista == "materiales":
        _validar_material(el, ruta)
    elif lista == "secciones":
        _validar_seccion(el, ruta)
    elif lista == "columnas":
        _punto(el["punto"], f"{ruta}.punto")
        _tramo_vertical(el, ctx, ruta)
        _referencia(el, "seccion", ctx.ids["secciones"], "la sección", ruta)
        _referencia(el, "material", ctx.ids["materiales"], "el material", ruta)
        if "angulo" in el:
            _numero(el, "angulo", ruta)
    elif lista == "vigas":
        _referencia(el, "piso", ctx.ids["pisos"], "el piso", ruta)
        if _punto(el["p1"], f"{ruta}.p1") == _punto(el["p2"], f"{ruta}.p2"):
            raise _err("tiene que ser distinto de p1", f"{ruta}.p2")
        _referencia(el, "seccion", ctx.ids["secciones"], "la sección", ruta)
        _referencia(el, "material", ctx.ids["materiales"], "el material", ruta)
    elif lista == "losas":
        _referencia(el, "piso", ctx.ids["pisos"], "el piso", ruta)
        _contorno(el["contorno"], f"{ruta}.contorno")
        _numero(el, "espesor", ruta, positivo=True)
        _hormigon(el, ctx, ruta)
        if "tipo" in el and el["tipo"] not in TIPOS_LOSA:
            raise _err(f"tiene que ser uno de {TIPOS_LOSA}", f"{ruta}.tipo")
        _cargas(el, ruta)
    elif lista == "muros":
        if _punto(el["p1"], f"{ruta}.p1") == _punto(el["p2"], f"{ruta}.p2"):
            raise _err("tiene que ser distinto de p1", f"{ruta}.p2")
        _tramo_vertical(el, ctx, ruta)
        _numero(el, "espesor", ruta, positivo=True)
        _hormigon(el, ctx, ruta)

    ctx.ids[lista][el["id"]] = el
    if lista in _NOMBRES_UNICOS:
        ctx.nombres[lista].add(el["nombre"])


def contexto(d: dict) -> _Contexto:
    """Valida ``fisico.json`` y devuelve las tablas ``id → elemento`` de cada lista."""
    if not isinstance(d, dict):
        raise _err("tiene que ser un objeto", "")
    for clave in d:
        if clave not in ("unidades", *LISTAS, "extensiones"):
            raise _err("clave desconocida", clave)
    if "unidades" not in d:
        raise _err("falta esta clave", "unidades")
    unidades = d["unidades"]
    if not isinstance(unidades, dict) or set(unidades) != {"longitud"}:
        raise _err("tiene que ser un objeto con la clave 'longitud'", "unidades")
    if unidades["longitud"] not in UNIDADES_LONGITUD:
        raise _err(f"tiene que ser una de {UNIDADES_LONGITUD}", "unidades.longitud")
    ctx = _Contexto()
    for lista in LISTAS:
        elementos = d.get(lista, [])
        if not isinstance(elementos, list):
            raise _err("tiene que ser una lista", lista)
        for k, el in enumerate(elementos):
            validar_elemento(lista, el, ctx, f"{lista}[{k}]")
    if "extensiones" in d and not isinstance(d["extensiones"], dict):
        raise _err("tiene que ser un objeto", "extensiones")
    return ctx


def validar(d: dict) -> None:
    """Valida ``fisico.json``. Lanza :class:`FormatoError` con la ruta del error."""
    contexto(d)
