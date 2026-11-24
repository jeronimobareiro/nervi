# SPDX-License-Identifier: GPL-3.0-or-later
"""Importar la geometría de un pórtico desde un dibujo DXF.

Lee las líneas y polilíneas de un DXF en texto (ASCII), por capa, y arma nudos y
barras: une los extremos que están a menos de una tolerancia, corta las barras donde
otra llega o las cruza, y descarta las repetidas. No usa ninguna IA ni biblioteca
externa: el mismo dibujo con las mismas opciones da siempre el mismo modelo.

Lo que no es línea (textos, cotas, arcos, bloques, sombreados) se cuenta y se
informa, sin importarlo. El dibujo se interpreta como una elevación: la X del dibujo
es la X del pórtico y la Y del dibujo es la vertical.

>>> d = leer_texto(_EJEMPLO)
>>> sorted(d.capas), d.unidad
(['COLUMNAS', 'VIGAS'], 'mm')
>>> r = importar(d, unidad="mm")
>>> len(r.modelo["nudos"]), len(r.modelo["barras"])
(4, 3)
"""

from __future__ import annotations

import copy
import itertools
import math
import os
from collections import Counter
from dataclasses import dataclass, field

from ..formato import modelo as _modelo

#: Metros por unidad de dibujo, por código ``$INSUNITS`` del DXF.
_INSUNITS = {1: "in", 2: "ft", 4: "mm", 5: "cm", 6: "m"}
METROS = {"mm": 1e-3, "cm": 1e-2, "m": 1.0, "in": 0.0254, "ft": 0.3048}
_KN = {"N": 1e-3, "kN": 1.0, "kgf": 0.00980665, "tf": 9.80665}
#: Sección de las barras nuevas si el modelo no tiene ninguna: hormigón H-25,
#: 30 x 30 cm (E en kN/m², A en m², I en m⁴).
SECCION_POR_OMISION = {"E": 2.5e7, "A": 0.09, "I": 0.3**4 / 12}
#: Entidades que se leen como barras.
LINEAS = ("LINE", "LWPOLYLINE", "POLYLINE")


class DXFError(ValueError):
    """El archivo no se puede leer como DXF."""


@dataclass
class Dibujo:
    """Lo que se leyó del DXF: segmentos por capa (en unidades del dibujo), la
    unidad declarada (``None`` si no dice) y lo que no se importa, por tipo."""

    capas: dict[str, list[tuple[float, float, float, float]]] = field(default_factory=dict)
    unidad: str | None = None
    ignorados: Counter = field(default_factory=Counter)
    arcos_en_polilineas: int = 0

    @property
    def segmentos(self) -> int:
        return sum(len(s) for s in self.capas.values())


@dataclass
class Importacion:
    """Modelo resultante y resumen de lo que se hizo."""

    modelo: dict
    nudos_nuevos: int
    barras_nuevas: int
    avisos: list[str]


# --- Lectura -------------------------------------------------------------------------
def leer(ruta: str | os.PathLike) -> Dibujo:
    """Lee un archivo DXF. Lanza :class:`DXFError` si no es un DXF en texto."""
    with open(ruta, "rb") as f:
        crudo = f.read()
    if crudo.startswith(b"AutoCAD Binary DXF"):
        raise DXFError(
            "Es un DXF binario. Guardalo como DXF de texto (ASCII) desde el programa de dibujo."
        )
    for codificacion in ("utf-8", "cp1252"):
        try:
            return leer_texto(crudo.decode(codificacion))
        except UnicodeDecodeError:
            continue
    raise DXFError("No se pudo leer el texto del archivo.")


def _pares(texto: str):
    lineas = texto.splitlines()
    if len(lineas) % 2:
        lineas = lineas[:-1]
    for k in range(0, len(lineas), 2):
        try:
            codigo = int(lineas[k].strip())
        except ValueError:
            raise DXFError(
                f"No parece un DXF: en la línea {k + 1} se esperaba un código de grupo."
            ) from None
        yield codigo, lineas[k + 1].strip()


def leer_texto(texto: str) -> Dibujo:
    """Lee el contenido de un DXF en texto."""
    pares = list(_pares(texto))
    if not any(c == 0 and v == "SECTION" for c, v in pares):
        raise DXFError("No parece un DXF: no tiene secciones.")
    dibujo = Dibujo()
    seccion = None
    k = 0
    n = len(pares)
    while k < n:
        codigo, valor = pares[k]
        if codigo == 0 and valor == "SECTION" and k + 1 < n:
            seccion = pares[k + 1][1]
            k += 2
            continue
        if codigo == 0 and valor == "ENDSEC":
            seccion = None
        elif seccion == "HEADER" and codigo == 9 and valor == "$INSUNITS" and k + 1 < n:
            try:
                dibujo.unidad = _INSUNITS.get(int(pares[k + 1][1]))
            except ValueError:
                pass
        elif seccion == "ENTITIES" and codigo == 0:
            k = _entidad(pares, k, dibujo)
            continue
        k += 1
    return dibujo


def _entidad(pares, k: int, dibujo: Dibujo) -> int:
    """Lee la entidad que empieza en ``k`` y devuelve dónde empieza la siguiente."""
    tipo = pares[k][1]
    fin = k + 1
    while fin < len(pares) and pares[fin][0] != 0:
        fin += 1
    datos = pares[k + 1 : fin]
    capa = next((v for c, v in datos if c == 8), "0")
    if tipo == "LINE":
        v = {c: float(x) for c, x in datos if c in (10, 20, 11, 21)}
        _agregar(dibujo, capa, [(v.get(10, 0.0), v.get(20, 0.0)), (v.get(11, 0.0), v.get(21, 0.0))])
    elif tipo == "LWPOLYLINE":
        puntos, x = [], None
        cerrada = False
        for c, valor in datos:
            if c == 70:
                cerrada = bool(int(valor) & 1)
            elif c == 10:
                x = float(valor)
            elif c == 20 and x is not None:
                puntos.append((x, float(valor)))
                x = None
            elif c == 42 and float(valor) != 0:
                dibujo.arcos_en_polilineas += 1
        _agregar(dibujo, capa, puntos + puntos[:1] if cerrada else puntos)
    elif tipo == "POLYLINE":
        cerrada = any(c == 70 and int(v) & 1 for c, v in datos)
        puntos = []
        while fin < len(pares) and pares[fin][1] != "SEQEND":
            if pares[fin][0] == 0 and pares[fin][1] == "VERTEX":
                siguiente = fin + 1
                while siguiente < len(pares) and pares[siguiente][0] != 0:
                    siguiente += 1
                v = {c: float(x) for c, x in pares[fin + 1 : siguiente] if c in (10, 20)}
                puntos.append((v.get(10, 0.0), v.get(20, 0.0)))
                fin = siguiente
            else:
                fin += 1
        fin += 1  # SEQEND
        while fin < len(pares) and pares[fin][0] != 0:
            fin += 1
        _agregar(dibujo, capa, puntos + puntos[:1] if cerrada else puntos)
    else:
        dibujo.ignorados[tipo] += 1
    return fin


def _agregar(dibujo: Dibujo, capa: str, puntos: list[tuple[float, float]]) -> None:
    segmentos = dibujo.capas.setdefault(capa, [])
    for (xa, ya), (xb, yb) in itertools.pairwise(puntos):
        segmentos.append((xa, ya, xb, yb))


# --- Armado del modelo -----------------------------------------------------------------
def _seccion(base: dict) -> dict:
    """Sección para las barras nuevas: la de la última barra del modelo o, si no hay,
    la de :data:`SECCION_POR_OMISION` en las unidades del modelo."""
    if base["barras"]:
        ultima = base["barras"][-1]
        return {c: ultima[c] for c in ("E", "A", "I")}
    f = 1 / _KN[base["unidades"]["fuerza"]]
    largo = 1 / METROS[base["unidades"]["longitud"]]
    return {
        "E": SECCION_POR_OMISION["E"] * f / largo**2,
        "A": SECCION_POR_OMISION["A"] * largo**2,
        "I": SECCION_POR_OMISION["I"] * largo**4,
    }


def _cortar(segmentos, tol: float, puntos=()):
    """Corta cada segmento donde lo toca o lo cruza otro, y donde pasa por uno de los
    ``puntos`` (los nudos que ya tiene el modelo). Devuelve segmentos."""
    n = len(segmentos)
    cortes: list[list[float]] = [[0.0, 1.0] for _ in range(n)]
    for k, (xa, ya, xb, yb) in enumerate(segmentos):
        dx, dy = xb - xa, yb - ya
        largo2 = dx * dx + dy * dy
        for px, py in puntos:
            if not (min(xa, xb) - tol <= px <= max(xa, xb) + tol):
                continue
            if not (min(ya, yb) - tol <= py <= max(ya, yb) + tol):
                continue
            t = ((px - xa) * dx + (py - ya) * dy) / largo2
            if 0 < t < 1 and math.hypot(xa + t * dx - px, ya + t * dy - py) <= tol:
                cortes[k].append(t)
    cajas = [
        (min(xa, xb) - tol, max(xa, xb) + tol, min(ya, yb) - tol, max(ya, yb) + tol)
        for xa, ya, xb, yb in segmentos
    ]
    orden = sorted(range(n), key=lambda i: cajas[i][0])
    for p, i in enumerate(orden):
        xa, ya, xb, yb = segmentos[i]
        for j in orden[p + 1 :]:
            if cajas[j][0] > cajas[i][1]:
                break
            if cajas[j][3] < cajas[i][2] or cajas[j][2] > cajas[i][3]:
                continue
            xc, yc, xd, yd = segmentos[j]
            for t, u in _encuentros((xa, ya, xb, yb), (xc, yc, xd, yd), tol):
                cortes[i].append(t)
                cortes[j].append(u)
    salida = []
    for (xa, ya, xb, yb), ts in zip(segmentos, cortes, strict=True):
        ts = sorted(set(min(max(t, 0.0), 1.0) for t in ts))
        for t0, t1 in itertools.pairwise(ts):
            salida.append(
                (xa + t0 * (xb - xa), ya + t0 * (yb - ya), xa + t1 * (xb - xa), ya + t1 * (yb - ya))
            )
    return salida


def _encuentros(s1, s2, tol: float):
    """Parámetros (t en s1, u en s2) donde se tocan: cruce, o extremo de uno sobre el
    otro a menos de ``tol``."""
    xa, ya, xb, yb = s1
    xc, yc, xd, yd = s2
    rx, ry, sx, sy = xb - xa, yb - ya, xd - xc, yd - yc
    l1, l2 = math.hypot(rx, ry), math.hypot(sx, sy)
    if l1 == 0 or l2 == 0:
        return []
    salida = []
    cruz = rx * sy - ry * sx
    if abs(cruz) > 1e-12 * l1 * l2:
        t = ((xc - xa) * sy - (yc - ya) * sx) / cruz
        u = ((xc - xa) * ry - (yc - ya) * rx) / cruz
        if -tol / l1 <= t <= 1 + tol / l1 and -tol / l2 <= u <= 1 + tol / l2:
            salida.append((t, u))
    # Extremos de uno sobre el otro (también para segmentos paralelos que se solapan).
    for px, py, sobre, propio in (
        (xc, yc, s1, 0.0),
        (xd, yd, s1, 1.0),
        (xa, ya, s2, 0.0),
        (xb, yb, s2, 1.0),
    ):
        ex, ey, fx, fy = sobre
        dx, dy = fx - ex, fy - ey
        largo2 = dx * dx + dy * dy
        t = ((px - ex) * dx + (py - ey) * dy) / largo2
        if 0 <= t <= 1 and math.hypot(ex + t * dx - px, ey + t * dy - py) <= tol:
            salida.append((t, propio) if sobre is s1 else (propio, t))
    return salida


def importar(
    dibujo: Dibujo,
    capas: list[str] | None = None,
    unidad: str | None = None,
    base: dict | None = None,
    tolerancia: float = 0.01,
    al_origen: bool = True,
    empotrar_base: bool = False,
) -> Importacion:
    """Arma el modelo: el de ``base`` (o uno vacío) con los nudos y barras del dibujo.

    ``capas`` son las capas que se importan (todas si es ``None``); ``unidad`` la del
    dibujo (``"mm"``, ``"cm"``, ``"m"``, ``"in"``, ``"ft"``; la del DXF si es
    ``None``). ``tolerancia`` está en metros: puntos más cerca que eso son el mismo
    nudo. Con ``al_origen`` el punto de abajo a la izquierda del dibujo va al (0, 0)
    si el modelo está vacío. Con ``empotrar_base`` se empotran los nudos nuevos de la
    cota más baja. Los nudos que coinciden con los del modelo se reusan."""
    unidad = unidad or dibujo.unidad
    if unidad not in METROS:
        raise DXFError(
            "El dibujo no dice en qué unidad está: elegí milímetros, centímetros o metros."
        )
    modelo = copy.deepcopy(base) if base is not None else _modelo.nuevo()
    avisos: list[str] = []
    elegidas = list(dibujo.capas) if capas is None else [c for c in capas if c in dibujo.capas]
    crudos = [s for c in elegidas for s in dibujo.capas[c]]
    if not crudos:
        raise DXFError("Las capas elegidas no tienen líneas.")

    # Pasar a las unidades del modelo.
    escala = METROS[unidad] / METROS[modelo["unidades"]["longitud"]]
    tol = tolerancia / METROS[modelo["unidades"]["longitud"]]
    segmentos = [tuple(v * escala for v in s) for s in crudos]
    if al_origen and not modelo["nudos"]:
        x0 = min(min(s[0], s[2]) for s in segmentos)
        y0 = min(min(s[1], s[3]) for s in segmentos)
        segmentos = [(xa - x0, ya - y0, xb - x0, yb - y0) for xa, ya, xb, yb in segmentos]
    largos = [math.hypot(s[2] - s[0], s[3] - s[1]) for s in segmentos]
    cortos = sum(1 for lg in largos if lg <= tol)
    segmentos = [s for s, lg in zip(segmentos, largos, strict=True) if lg > tol]
    if cortos:
        avisos.append(f"Se descartaron {cortos} líneas más cortas que la tolerancia.")
    segmentos = _cortar(segmentos, tol, [(nd["x"], nd["y"]) for nd in modelo["nudos"]])

    # Nudos: se reusan los existentes y se unen los que están a menos de la tolerancia.
    nudos = modelo["nudos"]
    siguiente_nudo = max((n["id"] for n in nudos), default=0) + 1
    celdas: dict[tuple[int, int], list[dict]] = {}

    def celda(x, y):
        return (math.floor(x / tol), math.floor(y / tol))

    for nd in nudos:
        celdas.setdefault(celda(nd["x"], nd["y"]), []).append(nd)
    nuevos: list[dict] = []

    def nudo(x: float, y: float) -> int:
        nonlocal siguiente_nudo
        cx, cy = celda(x, y)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for nd in celdas.get((cx + dx, cy + dy), ()):
                    if math.hypot(nd["x"] - x, nd["y"] - y) <= tol:
                        return nd["id"]
        nd = {"id": siguiente_nudo, "x": _redondear(x), "y": _redondear(y)}
        siguiente_nudo += 1
        nudos.append(nd)
        nuevos.append(nd)
        celdas.setdefault((cx, cy), []).append(nd)
        return nd["id"]

    seccion = _seccion(modelo)
    if not modelo["barras"]:
        avisos.append(
            "Las barras nuevas tienen una sección de hormigón de 30 x 30 cm (H-25): "
            "cambiala en la tabla de barras."
        )
    else:
        avisos.append(
            f"Las barras nuevas tienen la sección de B{modelo['barras'][-1]['id']}: "
            "cambiala en la tabla de barras si hace falta."
        )
    existentes = {tuple(sorted((b["i"], b["j"]))) for b in modelo["barras"]}
    siguiente_barra = max((b["id"] for b in modelo["barras"]), default=0) + 1
    repetidas = 0
    barras_nuevas = 0
    for xa, ya, xb, yb in segmentos:
        i, j = nudo(xa, ya), nudo(xb, yb)
        par = tuple(sorted((i, j)))
        if i == j:
            continue
        if par in existentes:
            repetidas += 1
            continue
        existentes.add(par)
        modelo["barras"].append({"id": siguiente_barra, "i": i, "j": j, **seccion})
        siguiente_barra += 1
        barras_nuevas += 1
    if repetidas:
        avisos.append(f"Se descartaron {repetidas} líneas repetidas o superpuestas.")

    if empotrar_base and nuevos:
        cota = min(nd["y"] for nd in nuevos)
        apoyados = {a["nudo"] for a in modelo["apoyos"]}
        for nd in nuevos:
            if abs(nd["y"] - cota) <= tol and nd["id"] not in apoyados:
                modelo["apoyos"].append({"nudo": nd["id"], "ux": True, "uy": True, "rz": True})
    # Nudos sueltos (de líneas descartadas) no quedan en el modelo.
    usados = {b["i"] for b in modelo["barras"]} | {b["j"] for b in modelo["barras"]}
    usados |= {a["nudo"] for a in modelo["apoyos"]}
    sueltos = [nd for nd in nuevos if nd["id"] not in usados]
    if sueltos:
        ids = {nd["id"] for nd in sueltos}
        modelo["nudos"] = [nd for nd in modelo["nudos"] if nd["id"] not in ids]
        nuevos = [nd for nd in nuevos if nd["id"] not in ids]

    if dibujo.arcos_en_polilineas:
        avisos.append(
            f"{dibujo.arcos_en_polilineas} tramos curvos de polilíneas se tomaron rectos."
        )
    ignorados = {t: n for t, n in dibujo.ignorados.items() if t not in LINEAS}
    if ignorados:
        detalle = ", ".join(f"{n} {_NOMBRES.get(t, t)}" for t, n in sorted(ignorados.items()))
        avisos.append(f"No se importa lo que no es línea: {detalle}.")
    return Importacion(modelo, len(nuevos), barras_nuevas, avisos)


def _redondear(v: float) -> float:
    """Quita el ruido de coma flotante del dibujo (por debajo de una milésima de mm)."""
    return round(v, 9) + 0.0


_NOMBRES = {
    "TEXT": "textos",
    "MTEXT": "textos",
    "DIMENSION": "cotas",
    "ARC": "arcos",
    "CIRCLE": "círculos",
    "INSERT": "bloques",
    "HATCH": "sombreados",
    "POINT": "puntos",
    "SPLINE": "curvas",
    "ELLIPSE": "elipses",
    "SOLID": "rellenos",
    "LEADER": "flechas",
}

#: Un pórtico de una nave en milímetros: dos columnas y una viga, con un texto.
_EJEMPLO = """0
SECTION
2
HEADER
9
$INSUNITS
70
4
0
ENDSEC
0
SECTION
2
ENTITIES
0
LINE
8
COLUMNAS
10
0
20
0
11
0
21
3000
0
LINE
8
COLUMNAS
10
6000
20
0
11
6000
21
3000
0
LWPOLYLINE
8
VIGAS
90
2
70
0
10
0
20
3000
10
6000
20
3000
0
TEXT
8
COTAS
1
Pórtico
0
ENDSEC
0
EOF
"""
