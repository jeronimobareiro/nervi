# SPDX-License-Identifier: GPL-3.0-or-later
"""Ejecutor de la biblioteca de casos de verificación de ``verification/``.

Cada archivo ``*.toml`` es un caso: un modelo, los resultados esperados con su
tolerancia y la fuente citada. El formato está descrito en
``verification/README.md``. Esta prueba resuelve cada caso con la API Python y
compara cada valor esperado.
"""

from __future__ import annotations

import ast
import math
import operator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pytest

import nervi

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

DIRECTORIO = Path(__file__).resolve().parent.parent / "verification"
CASOS = sorted(DIRECTORIO.rglob("*.toml"))

TOL_REL = 1e-9
TOL_ABS = 1e-12

_COMPONENTES_NUDO = {"ux": 0, "uy": 1, "rz": 2, "Rx": 0, "Ry": 1, "Mz": 2}
_COMPONENTES_SECCION = ("N", "V", "M", "u", "v")


# --- Expresiones ---------------------------------------------------------------
_BINARIOS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
}
_UNARIOS = {ast.USub: operator.neg, ast.UAdd: operator.pos}
_FUNCIONES = {
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "radianes": math.radians,
    "abs": abs,
}
_CONSTANTES = {"pi": math.pi}


def evaluar(valor: Any, parametros: dict[str, float]) -> float:
    """Convierte un número o una expresión aritmética (texto) en ``float``.

    Las expresiones admiten ``+ - * / **``, paréntesis, los parámetros del caso,
    ``pi`` y las funciones ``sqrt, sin, cos, tan, radianes, abs``. No se usa
    ``eval``: se recorre el árbol sintáctico y se rechaza cualquier otra cosa.
    """
    if isinstance(valor, bool):
        raise ValueError(f"se esperaba un número y se encontró {valor!r}")
    if isinstance(valor, (int, float)):
        return float(valor)
    if not isinstance(valor, str):
        raise ValueError(f"se esperaba un número o una expresión y se encontró {valor!r}")

    def nodo(n: ast.AST) -> float:
        if isinstance(n, ast.Expression):
            return nodo(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return float(n.value)
        if isinstance(n, ast.Name):
            if n.id in parametros:
                return parametros[n.id]
            if n.id in _CONSTANTES:
                return _CONSTANTES[n.id]
            raise ValueError(f"parámetro desconocido {n.id!r} en {valor!r}")
        if isinstance(n, ast.BinOp) and type(n.op) in _BINARIOS:
            return _BINARIOS[type(n.op)](nodo(n.left), nodo(n.right))
        if isinstance(n, ast.UnaryOp) and type(n.op) in _UNARIOS:
            return _UNARIOS[type(n.op)](nodo(n.operand))
        if (
            isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id in _FUNCIONES
            and not n.keywords
        ):
            return float(_FUNCIONES[n.func.id](*(nodo(a) for a in n.args)))
        raise ValueError(f"expresión no permitida en {valor!r}")

    return nodo(ast.parse(valor, mode="eval"))


# --- Casos ---------------------------------------------------------------------
def leer_caso(ruta: Path) -> dict:
    with open(ruta, "rb") as f:
        caso = tomllib.load(f)
    for clave in ("titulo", "fuente", "modelo", "esperado"):
        if clave not in caso:
            raise ValueError(f"{ruta.name}: falta la clave {clave!r}")
    return caso


def parametros_de(caso: dict) -> dict[str, float]:
    """Parámetros en orden: cada uno puede usar los anteriores."""
    salida: dict[str, float] = {}
    for nombre, valor in caso.get("parametros", {}).items():
        salida[nombre] = evaluar(valor, salida)
    return salida


def construir(caso: dict, p: dict[str, float]) -> nervi.Modelo:
    def num(v: Any) -> float:
        return evaluar(v, p)

    mod = caso["modelo"]
    m = nervi.Modelo()
    for x, y in mod["nudos"]:
        m.agregar_nudo(num(x), num(y))
    for b in mod["barras"]:
        m.agregar_barra(
            b["i"],
            b["j"],
            num(b["E"]),
            num(b["A"]),
            num(b["I"]),
            articulada_i=b.get("articulada_i", False),
            articulada_j=b.get("articulada_j", False),
        )
    for a in mod.get("apoyos", []):
        m.apoyar(a["nudo"], a.get("ux", False), a.get("uy", False), a.get("rz", False))
    for r in mod.get("resortes", []):
        m.resorte(r["nudo"], num(r.get("kx", 0)), num(r.get("ky", 0)), num(r.get("krz", 0)))
    for c in caso.get("cargas", []):
        tipo, nombre = c["tipo"], c["caso"]
        ejes = c.get("ejes", "local")
        g = {k: num(v) for k, v in c.items() if k not in ("tipo", "caso", "ejes", "nudo", "barra")}
        if tipo == "nodal":
            m.carga_nodal(nombre, c["nudo"], g.get("fx", 0.0), g.get("fy", 0.0), g.get("mz", 0.0))
        elif tipo == "uniforme":
            m.carga_uniforme(nombre, c["barra"], g.get("qx", 0.0), g.get("qy", 0.0), ejes=ejes)
        elif tipo == "puntual":
            m.carga_puntual(
                nombre, c["barra"], g["a"], g.get("px", 0.0), g.get("py", 0.0), ejes=ejes
            )
        elif tipo == "trapezoidal":
            m.carga_trapezoidal(
                nombre,
                c["barra"],
                g.get("qy1", 0.0),
                g.get("qy2", 0.0),
                g.get("a", 0.0),
                g.get("b"),
                g.get("qx1", 0.0),
                g.get("qx2", 0.0),
                ejes=ejes,
            )
        elif tipo == "momento":
            m.carga_momento(nombre, c["barra"], g["a"], g.get("mz", 0.0))
        elif tipo == "termica":
            m.carga_termica(
                nombre,
                c["barra"],
                g["alfa"],
                g.get("dt", 0.0),
                g.get("gradiente", 0.0),
                g.get("h"),
            )
        elif tipo == "desplazamiento_impuesto":
            m.desplazamiento_impuesto(
                nombre, c["nudo"], g.get("ux", 0.0), g.get("uy", 0.0), g.get("rz", 0.0)
            )
        else:
            raise ValueError(f"tipo de carga desconocido {tipo!r}")
    return m


@dataclass
class Comparacion:
    descripcion: str
    calculado: float
    esperado: float
    tolerancia: float

    @property
    def ok(self) -> bool:
        return abs(self.calculado - self.esperado) <= self.tolerancia


def valor_calculado(e: dict, res: nervi.Resultados, p: dict[str, float]) -> float:
    r = res[e["caso"]]
    que, comp = e["que"], e["componente"]
    if que == "reaccion":
        return float(r.reacciones[e["nudo"], _COMPONENTES_NUDO[comp]])
    if que == "desplazamiento":
        return float(r.desplazamientos[e["nudo"], _COMPONENTES_NUDO[comp]])
    if que == "seccion":
        if comp not in _COMPONENTES_SECCION:
            raise ValueError(f"componente de sección desconocida {comp!r}")
        d = r.diagrama(e["barra"])
        valores = d[comp]
        if "extremo" in e:
            return float(valores.max() if e["extremo"] == "max" else valores.min())
        x = evaluar(e["x"], p)
        cerca = np.flatnonzero(np.isclose(d["x"], x, rtol=0.0, atol=1e-9 * max(1.0, abs(x))))
        if cerca.size == 0:
            raise ValueError(
                f"x = {x} no es una estación del diagrama de la barra {e['barra']}; "
                "ajustá 'estaciones' del caso para que lo sea"
            )
        # En un salto hay dos estaciones: 'izquierda' toma la primera, 'derecha' la última.
        k = cerca[-1] if e.get("lado", "izquierda") == "derecha" else cerca[0]
        return float(valores[k])
    raise ValueError(f"'que' desconocido {que!r} (reaccion, desplazamiento o seccion)")


def comparar(caso: dict) -> list[Comparacion]:
    p = parametros_de(caso)
    res = construir(caso, p).resolver(n_estaciones=caso.get("estaciones", 11))
    tol_rel = caso.get("tolerancia", TOL_REL)
    tol_abs = caso.get("tolerancia_abs", TOL_ABS)
    salida = []
    for e in caso["esperado"]:
        esperado = evaluar(e["valor"], p)
        calculado = valor_calculado(e, res, p)
        rel = e.get("tolerancia", tol_rel)
        absoluta = e.get("tolerancia_abs", tol_abs)
        donde = f"nudo {e['nudo']}" if "nudo" in e else f"barra {e.get('barra')}"
        if "x" in e:
            donde += f", x = {e['x']}"
        if "extremo" in e:
            donde += f", {e['extremo']}"
        desc = e.get("descripcion", f"{e['que']} {e['componente']} ({donde})")
        salida.append(Comparacion(desc, calculado, esperado, rel * abs(esperado) + absoluta))
    return salida


# --- Ejemplos de libros ----------------------------------------------------------
LIBROS = DIRECTORIO / "libros"
CASOS_LIBROS = sorted(LIBROS.rglob("*.toml"))


def errores_de_referencia(caso: dict) -> list[str]:
    """Revisa la tabla ``[referencia]`` de un ejemplo de libro (``verification/README.md``).

    ``datos = "libro"``: el ejemplo está tomado del libro y lleva ``pagina`` y
    ``ejemplo``. ``datos = "propios"``: los datos los eligió quien aportó el caso, se
    resolvió con el método de la sección citada y lleva ``derivacion``, la función de
    ``verification/libros/derivaciones.py`` que lo resuelve a mano.
    """
    ref = caso.get("referencia")
    if not isinstance(ref, dict):
        return ["falta la tabla [referencia]"]
    errores = [f"falta {c!r}" for c in ("libro", "edicion", "seccion", "datos") if c not in ref]
    datos = ref.get("datos")
    if datos == "libro":
        errores += [f"falta {c!r}" for c in ("pagina", "ejemplo") if c not in ref]
    elif datos == "propios":
        if "derivacion" not in ref:
            errores.append("falta 'derivacion'")
        else:
            funcion = ref["derivacion"].split(",")[-1].strip().removesuffix("()")
            if funcion not in _funciones_de_derivaciones():
                errores.append(f"derivaciones.py no define {funcion}()")
    elif datos is not None:
        errores.append(f'\'datos\' tiene que ser "libro" o "propios", no {datos!r}')
    return errores


def _funciones_de_derivaciones() -> set[str]:
    ruta = LIBROS / "derivaciones.py"
    if not ruta.exists():
        return set()
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    return {n.name for n in arbol.body if isinstance(n, ast.FunctionDef)}


# --- Pruebas -------------------------------------------------------------------
def test_hay_casos():
    assert len(CASOS) >= 5


def test_hay_ejemplos_de_libros():
    assert len(CASOS_LIBROS) >= 5


@pytest.mark.parametrize("ruta", CASOS_LIBROS, ids=lambda r: r.stem)
def test_referencia_de_libro(ruta: Path):
    errores = errores_de_referencia(leer_caso(ruta))
    assert not errores, f"{ruta.name}: " + "; ".join(errores)


def test_referencia_incompleta_falla():
    base = {"libro": "Autor, Título", "edicion": "3.ª", "seccion": "cap. 4"}
    assert errores_de_referencia({}) == ["falta la tabla [referencia]"]
    assert errores_de_referencia({"referencia": {**base, "datos": "libro"}}) == [
        "falta 'pagina'",
        "falta 'ejemplo'",
    ]
    assert (
        errores_de_referencia(
            {"referencia": {**base, "datos": "libro", "pagina": 120, "ejemplo": "4.2"}}
        )
        == []
    )
    propios = {**base, "datos": "propios", "derivacion": "derivaciones.py, no_existe()"}
    assert errores_de_referencia({"referencia": propios}) == [
        "derivaciones.py no define no_existe()"
    ]
    assert errores_de_referencia({"referencia": {**base, "datos": "otro"}})


@pytest.mark.parametrize("ruta", CASOS, ids=lambda r: str(r.relative_to(DIRECTORIO)))
def test_caso(ruta: Path):
    fallas = [c for c in comparar(leer_caso(ruta)) if not c.ok]
    assert not fallas, "\n".join(
        f"{c.descripcion}: calculado {c.calculado:.12g}, esperado {c.esperado:.12g}" for c in fallas
    )


@pytest.mark.parametrize("ruta", CASOS[:3], ids=lambda r: r.stem)
def test_un_valor_alterado_falla(ruta: Path):
    # Control del propio ejecutor: si se altera un valor esperado, el caso falla.
    # La alteración supera la tolerancia del caso, para que también valga en los
    # ejemplos de libros con tolerancia de 1e-3.
    caso = leer_caso(ruta)
    for e in caso["esperado"]:
        factor = 1 + 10 * max(1e-4, e.get("tolerancia", caso.get("tolerancia", TOL_REL)))
        e["valor"] = f"({e['valor']}) * {factor} + 1e-6"
    assert not any(c.ok for c in comparar(caso))


def test_expresiones():
    p = {"L": 6.0, "q": 10.0}
    assert evaluar("q*L**2/8", p) == pytest.approx(45.0)
    assert evaluar("sqrt(2)*cos(radianes(45))", p) == pytest.approx(1.0)
    for malo in ("__import__('os')", "L.real", "[1]", "x"):
        with pytest.raises(ValueError):
            evaluar(malo, p)
