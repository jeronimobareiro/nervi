# SPDX-License-Identifier: GPL-3.0-or-later
"""Contenido de la memoria para el análisis de pórticos planos (Fase 1).

:func:`memoria_de_calculo` arma la :class:`~nervi.memoria.documento.Memoria` con
el modelo, los materiales y secciones, los casos de carga, las combinaciones y
los resultados (tablas y diagramas). Los módulos de diseño agregan después sus
propios capítulos con ``Memoria.agregar`` (ver ``documento.py``).
"""

from __future__ import annotations

import datetime as _dt
from collections.abc import Callable, Mapping
from importlib import metadata
from pathlib import Path

import numpy as np

from ..modelo import Modelo, ResultadoCaso, Resultados
from .dibujo import Geometria, figura_deformada, figura_diagrama, figura_geometria
from .documento import Capitulo, Memoria, Tabla, formatear, formatear_factor
from .plantilla import Plantilla

_TIPOS_CARGA = {0: "Uniforme", 1: "Puntual", 2: "Trapezoidal", 3: "Térmica", 4: "Momento"}
_EJES = {0: "local", 1: "global"}
_GDL = ("u<sub>x</sub>", "u<sub>y</sub>", "r<sub>z</sub>")

#: Títulos de los capítulos, para insertar capítulos con ``Memoria.agregar(antes_de=...)``.
CAPITULOS = {
    "alcance": "Alcance y método",
    "geometria": "Geometría",
    "materiales": "Materiales y secciones",
    "cargas": "Casos de carga",
    "combinaciones": "Combinaciones de carga",
    "resultados": "Resultados",
    "envolvente": "Envolventes",
}


def _version() -> str:
    try:
        return metadata.version("nervi")
    except metadata.PackageNotFoundError:  # pragma: no cover - sin instalar
        return "(versión de desarrollo)"


def _nombrador(
    nombres: Mapping[int, str] | Callable[[int], str] | None, prefijo: str
) -> Callable[[int], str]:
    if nombres is None:
        return lambda k: f"{prefijo}{k + 1}"
    if callable(nombres):
        return nombres
    return lambda k: str(nombres.get(k, f"{prefijo}{k + 1}"))


class _Constructor:
    """Arma los capítulos a partir del modelo, los resultados y la plantilla."""

    def __init__(
        self,
        modelo: Modelo,
        resultados: Resultados,
        plantilla: Plantilla,
        fuerza: str,
        longitud: str,
        nombre_nudo: Callable[[int], str],
        nombre_barra: Callable[[int], str],
    ) -> None:
        self.arr = modelo.arreglos()
        self.res = resultados
        self.pl = plantilla
        self.F, self.L = fuerza, longitud
        self.nudo, self.barra = nombre_nudo, nombre_barra
        self.geo = Geometria(self.arr)
        self.casos = resultados.casos

    # --- Formato ---------------------------------------------------------------
    def num(self, v: float) -> str:
        return formatear(v, self.pl.cifras, self.pl.decimal)

    def dato(self, v: float) -> str:
        """Datos de entrada: más cifras, para que se puedan reproducir."""
        return formatear(v, 6, self.pl.decimal)

    def u(self, clave: str) -> str:
        F, L = self.F, self.L
        return {
            "F": F,
            "L": L,
            "M": f"{F}·{L}",
            "q": f"{F}/{L}",
            "E": f"{F}/{L}²",
            "A": f"{L}²",
            "I": f"{L}<sup>4</sup>",
            "k": f"{F}/{L}",
            "kr": f"{F}·{L}/rad",
        }[clave]

    # --- Capítulos ---------------------------------------------------------------
    def alcance(self) -> Capitulo:
        s = Capitulo(CAPITULOS["alcance"])
        for clave in ("alcance", "metodo", "convenciones", "unidades", "numeracion"):
            s.parrafo(self.pl.texto(clave))
        return s

    def geometria(self) -> Capitulo:
        s = Capitulo(CAPITULOS["geometria"], pagina_nueva=True)
        s.parrafo(self.pl.texto("geometria"))
        s.figura(figura_geometria(self.geo, self.nudo, self.barra))
        filas = []
        for k, (x, y) in enumerate(self.arr["coords"]):
            r = self.arr["restricciones"][k].astype(bool)
            restr = ", ".join(g for g, si in zip(("ux", "uy", "rz"), r, strict=True) if si)
            kx, ky, kr = self.arr["resortes"][k]
            resortes = "; ".join(
                f"{n} = {self.dato(v)}"
                for n, v in (("k<sub>x</sub>", kx), ("k<sub>y</sub>", ky), ("k<sub>rz</sub>", kr))
                if v
            )
            filas.append([self.nudo(k), self.dato(x), self.dato(y), restr or "—", resortes or "—"])
        s.tabla(
            Tabla(
                ["Nudo", f"x ({self.L})", f"y ({self.L})", "Restricciones", "Resortes"],
                filas,
                titulo="Nudos y apoyos",
                anchos=[0.8, 1, 1, 1.3, 2.4],
                alineacion=["izq", "der", "der", "centro", "izq"],
                nota=(
                    f"Resortes: k<sub>x</sub>, k<sub>y</sub> en {self.u('k')}; "
                    f"k<sub>rz</sub> en {self.u('kr')}."
                    if self.arr["resortes"].any()
                    else ""
                ),
            )
        )
        filas = []
        for b, (i, j) in enumerate(self.arr["conectividad"]):
            lib = self.arr["liberaciones"][b].astype(bool)
            nombres = ("N<sub>i</sub>", "V<sub>i</sub>", "M<sub>i</sub>")
            nombres += ("N<sub>j</sub>", "V<sub>j</sub>", "M<sub>j</sub>")
            texto = ", ".join(n for n, si in zip(nombres, lib, strict=True) if si)
            filas.append(
                [
                    self.barra(b),
                    self.nudo(int(i)),
                    self.nudo(int(j)),
                    self.dato(self.geo.longitudes[b]),
                    self.tipo_seccion[b],
                    texto or "—",
                ]
            )
        s.tabla(
            Tabla(
                ["Barra", "Nudo i", "Nudo j", f"L ({self.L})", "Sección", "Liberaciones"],
                filas,
                titulo="Barras",
                alineacion=["izq", "centro", "centro", "der", "centro", "izq"],
            )
        )
        return s

    @property
    def tipo_seccion(self) -> list[str]:
        if not hasattr(self, "_tipos"):
            props = self.arr["props"]
            unicos: list[tuple[float, ...]] = []
            self._tipos = []
            for fila in props:
                clave = tuple(float(v) for v in fila)
                if clave not in unicos:
                    unicos.append(clave)
                self._tipos.append(f"S{unicos.index(clave) + 1}")
            self._unicos = unicos
        return self._tipos

    def materiales(self) -> Capitulo:
        s = Capitulo(CAPITULOS["materiales"])
        s.parrafo(self.pl.texto("materiales"))
        _ = self.tipo_seccion
        filas = []
        for k, (E, A, I) in enumerate(self._unicos):
            barras = [self.barra(b) for b, t in enumerate(self._tipos) if t == f"S{k + 1}"]
            filas.append([f"S{k + 1}", self.dato(E), self.dato(A), self.dato(I), ", ".join(barras)])
        s.tabla(
            Tabla(
                [
                    "Sección",
                    f"E ({self.u('E')})",
                    f"A ({self.u('A')})",
                    f"I ({self.u('I')})",
                    "Barras",
                ],
                filas,
                titulo="Tipos de sección",
                anchos=[0.8, 1.2, 1.1, 1.1, 2.2],
                alineacion=["izq", "der", "der", "der", "izq"],
            )
        )
        return s

    def cargas(self) -> Capitulo:
        s = Capitulo(CAPITULOS["cargas"], pagina_nueva=True)
        s.parrafo(self.pl.texto("cargas"))
        for c, nombre in enumerate(self.casos):
            sub = s.subcapitulo(f"Caso {nombre}")
            hubo = False
            nodales = self.arr["cargas_nodales"][c]
            filas = [
                [self.nudo(k), *(self.dato(v) for v in f)]
                for k, f in enumerate(nodales)
                if np.any(f)
            ]
            if filas:
                hubo = True
                sub.tabla(
                    Tabla(
                        [
                            "Nudo",
                            f"F<sub>x</sub> ({self.F})",
                            f"F<sub>y</sub> ({self.F})",
                            f"M<sub>z</sub> ({self.u('M')})",
                        ],
                        filas,
                        titulo="Cargas nodales (ejes globales)",
                    )
                )
            filas = [self._fila_carga_barra(f) for f in self.arr["cargas_barra"] if int(f[0]) == c]
            if filas:
                hubo = True
                sub.tabla(
                    Tabla(
                        ["Barra", "Tipo", "Ejes", "Posición", "Valores"],
                        filas,
                        titulo="Cargas en barras",
                        anchos=[0.7, 1.0, 0.7, 1.4, 3.6],
                        alineacion=["izq", "izq", "centro", "izq", "izq"],
                    )
                )
            imp = self.arr["despl_impuestos"][c]
            filas = [
                [self.nudo(k), self.dato(f[0]), self.dato(f[1]), self.dato(f[2])]
                for k, f in enumerate(imp)
                if np.any(f)
            ]
            if filas:
                hubo = True
                sub.tabla(
                    Tabla(
                        [
                            "Nudo",
                            f"u<sub>x</sub> ({self.L})",
                            f"u<sub>y</sub> ({self.L})",
                            "r<sub>z</sub> (rad)",
                        ],
                        filas,
                        titulo="Desplazamientos impuestos (asentamientos)",
                    )
                )
            if not hubo:
                sub.parrafo("El caso no tiene cargas.", "nota")
        return s

    def _fila_carga_barra(self, f: np.ndarray) -> list[str]:
        tipo, ejes = int(f[2]), int(f[3])
        b = int(f[1])
        L, q, M = self.L, self.u("q"), self.u("M")
        d = self.dato
        if tipo == 0:
            pos = "toda la barra"
            val = f"q<sub>x</sub> = {d(f[5])}; q<sub>y</sub> = {d(f[6])} {q}"
        elif tipo == 1:
            pos = f"a = {d(f[4])} {L}"
            val = f"P<sub>x</sub> = {d(f[5])}; P<sub>y</sub> = {d(f[6])} {self.F}"
        elif tipo == 2:
            pos = f"de {d(f[4])} a {d(f[7])} {L}"
            val = f"q<sub>x</sub>: {d(f[5])} → {d(f[8])}; q<sub>y</sub>: {d(f[6])} → {d(f[9])} {q}"
        elif tipo == 3:
            pos = "toda la barra"
            val = f"α = {d(f[4])}; ΔT = {d(f[5])}; ΔT<sub>g</sub> = {d(f[6])}"
            if f[7]:
                val += f"; h = {d(f[7])} {L}"
        else:
            pos = f"a = {d(f[4])} {L}"
            val = f"M<sub>z</sub> = {d(f[5])} {M}"
        return [self.barra(b), _TIPOS_CARGA.get(tipo, "?"), _EJES.get(ejes, "?"), pos, val]

    def combinaciones(self, combs: dict[str, dict[str, float]]) -> Capitulo:
        s = Capitulo(CAPITULOS["combinaciones"])
        s.parrafo(self.pl.texto("combinaciones"))
        filas = []
        for nombre, factores in combs.items():
            texto = " + ".join(
                f"{formatear_factor(f, self.pl.decimal)}·{c}" for c, f in factores.items()
            )
            filas.append([nombre, texto.replace("+ -", "- ")])
        s.tabla(
            Tabla(
                ["Combinación", "Casos y factores"],
                filas,
                anchos=[1.5, 3],
                alineacion=["izq", "izq"],
            )
        )
        return s

    def resultados(self, items: list[tuple[str, ResultadoCaso]]) -> Capitulo:
        s = Capitulo(CAPITULOS["resultados"], pagina_nueva=True)
        s.parrafo(self.pl.texto("resultados"))
        for k, (etiqueta, r) in enumerate(items):
            self._resultado(s.subcapitulo(etiqueta, pagina_nueva=k > 0), r)
        return s

    def _resultado(self, s: Capitulo, r: ResultadoCaso) -> None:
        F, L, M = self.F, self.L, self.u("M")
        grupo = f"diag-{r.nombre}"
        s.figura(figura_diagrama(self.geo, r, "M", f"Momento flector M ({M})", self.num, grupo))
        s.figura(figura_diagrama(self.geo, r, "V", f"Cortante V ({F})", self.num, grupo))
        s.figura(figura_diagrama(self.geo, r, "N", f"Axil N ({F})", self.num, grupo))
        s.figura(figura_deformada(self.geo, r, "Deformada", self.num, grupo))

        s.tabla(
            Tabla(
                ["Nudo", f"u<sub>x</sub> ({L})", f"u<sub>y</sub> ({L})", "r<sub>z</sub> (rad)"],
                [
                    [self.nudo(k), *(self.num(v) for v in fila)]
                    for k, fila in enumerate(r.desplazamientos)
                ],
                titulo="Desplazamientos de los nudos (ejes globales)",
            )
        )
        apoyados = [
            k
            for k in range(len(self.arr["coords"]))
            if self.arr["restricciones"][k].any() or self.arr["resortes"][k].any()
        ]
        s.tabla(
            Tabla(
                ["Nudo", f"R<sub>x</sub> ({F})", f"R<sub>y</sub> ({F})", f"M<sub>z</sub> ({M})"],
                [[self.nudo(k), *(self.num(v) for v in r.reacciones[k])] for k in apoyados],
                titulo="Reacciones de apoyo (ejes globales)",
            )
        )
        filas_ext, filas_max = [], []
        for b in range(len(self.arr["conectividad"])):
            d = r.diagrama(b)
            if not d["x"].size:
                continue
            filas_ext.append(
                [
                    self.barra(b),
                    *(self.num(d[c][0]) for c in ("N", "V", "M")),
                    *(self.num(d[c][-1]) for c in ("N", "V", "M")),
                ]
            )
            imax, imin = int(np.argmax(d["M"])), int(np.argmin(d["M"]))
            filas_max.append(
                [
                    self.barra(b),
                    self.num(d["N"].min()),
                    self.num(d["N"].max()),
                    self.num(np.abs(d["V"]).max()),
                    self.num(d["M"][imin]),
                    self.num(d["x"][imin]),
                    self.num(d["M"][imax]),
                    self.num(d["x"][imax]),
                ]
            )
        s.tabla(
            Tabla(
                [
                    "Barra",
                    f"N<sub>i</sub> ({F})",
                    f"V<sub>i</sub> ({F})",
                    f"M<sub>i</sub> ({M})",
                    f"N<sub>j</sub> ({F})",
                    f"V<sub>j</sub> ({F})",
                    f"M<sub>j</sub> ({M})",
                ],
                filas_ext,
                titulo="Esfuerzos en los extremos de las barras",
                nota="Con la convención de signos de los diagramas (ver Alcance y método).",
            )
        )
        s.tabla(
            Tabla(
                [
                    "Barra",
                    f"N mín ({F})",
                    f"N máx ({F})",
                    f"|V| máx ({F})",
                    f"M mín ({M})",
                    f"x ({L})",
                    f"M máx ({M})",
                    f"x ({L})",
                ],
                filas_max,
                titulo="Valores extremos por barra",
                nota="x: distancia desde el nudo i de la barra.",
            )
        )

    def envolvente(self, items: list[tuple[str, ResultadoCaso]]) -> Capitulo:
        """Extremos de cada esfuerzo por barra y de cada reacción sobre ``items``."""
        s = Capitulo(CAPITULOS["envolvente"], pagina_nueva=True)
        s.parrafo(self.pl.texto("envolvente"))
        F, M = self.F, self.u("M")
        filas = []
        for b in range(len(self.arr["conectividad"])):
            for c, unidad in (("N", F), ("V", F), ("M", M)):
                maximos = [(float(r.diagrama(b)[c].max()), n) for n, r in items]
                minimos = [(float(r.diagrama(b)[c].min()), n) for n, r in items]
                vmax, nmax = max(maximos, key=lambda t: t[0])
                vmin, nmin = min(minimos, key=lambda t: t[0])
                filas.append(
                    [self.barra(b), f"{c} ({unidad})", self.num(vmax), nmax, self.num(vmin), nmin]
                )
        s.tabla(
            Tabla(
                ["Barra", "Esfuerzo", "Máximo", "Combinación", "Mínimo", "Combinación"],
                filas,
                titulo="Envolvente de esfuerzos",
                anchos=[0.7, 1.0, 0.9, 1.8, 0.9, 1.8],
                alineacion=["izq", "izq", "der", "izq", "der", "izq"],
            )
        )
        filas = []
        for k in range(len(self.arr["coords"])):
            if not (self.arr["restricciones"][k].any() or self.arr["resortes"][k].any()):
                continue
            for g, (comp, unidad) in enumerate(
                ((("R<sub>x</sub>", F)), ("R<sub>y</sub>", F), ("M<sub>z</sub>", M))
            ):
                valores = [(float(r.reacciones[k, g]), n) for n, r in items]
                vmax, nmax = max(valores, key=lambda t: t[0])
                vmin, nmin = min(valores, key=lambda t: t[0])
                if vmax == vmin == 0.0:
                    continue
                filas.append(
                    [self.nudo(k), f"{comp} ({unidad})", self.num(vmax), nmax, self.num(vmin), nmin]
                )
        s.tabla(
            Tabla(
                ["Nudo", "Reacción", "Máximo", "Combinación", "Mínimo", "Combinación"],
                filas,
                titulo="Envolvente de reacciones",
                anchos=[0.7, 1.0, 0.9, 1.8, 0.9, 1.8],
                alineacion=["izq", "izq", "der", "izq", "der", "izq"],
            )
        )
        return s


def memoria_de_calculo(
    modelo: Modelo,
    resultados: Resultados | None = None,
    *,
    combinaciones: Mapping[str, Mapping[str, float]] | None = None,
    datos_proyecto: Mapping[str, str] | None = None,
    plantilla: str | Path | dict | None = None,
    fuerza: str = "kN",
    longitud: str = "m",
    nombres_nudos: Mapping[int, str] | Callable[[int], str] | None = None,
    nombres_barras: Mapping[int, str] | Callable[[int], str] | None = None,
    incluir_casos: bool = True,
) -> Memoria:
    """Arma la memoria de cálculo de un pórtico plano.

    * ``resultados``: los de ``modelo.resolver(...)``; si falta, se resuelve acá
      con ``combinaciones``.
    * ``combinaciones``: ``{nombre: {caso: factor}}``. Las que ya se resolvieron
      con el modelo (``Modelo.resolver(combinaciones=...)``) se toman de
      ``resultados``; las demás se calculan con ``Resultados.combinar``.
    * ``datos_proyecto``: datos de la portada (``"Proyecto"``, ``"Autor"``…).
      ``"Fecha"`` es hoy si no se indica.
    * ``plantilla``: archivo TOML o diccionario con los textos a cambiar
      (ver ``plantilla.toml``).
    * ``fuerza`` y ``longitud``: nombres de las unidades del modelo, solo para
      rotular (el motor no convierte unidades).
    * ``nombres_nudos`` y ``nombres_barras``: rótulos propios (por defecto
      ``N1, N2…`` y ``B1, B2…``, numerados desde 1).
    * ``incluir_casos``: agregar los resultados de cada caso de carga, además
      de los de cada combinación.

    Devuelve una :class:`Memoria` a la que se le pueden agregar capítulos antes
    de guardarla con :meth:`Memoria.guardar_pdf`.
    """
    combinaciones = {k: dict(v) for k, v in (combinaciones or {}).items()}
    if resultados is None:
        resultados = modelo.resolver(combinaciones=combinaciones or None)
    combs: dict[str, dict[str, float]] = {
        n: resultados.factores(n) for n in resultados.combinaciones
    }
    items_comb: list[tuple[str, ResultadoCaso]] = [(n, resultados[n]) for n in combs]
    for nombre, factores in combinaciones.items():
        if nombre not in combs:
            combs[nombre] = factores
            items_comb.append((nombre, resultados.combinar(nombre, factores)))

    datos = dict(datos_proyecto or {})
    datos.setdefault("Fecha", _dt.date.today().strftime("%d/%m/%Y"))
    version = _version()
    variables = {
        "proyecto": datos.get("Proyecto", ""),
        "autor": datos.get("Autor", ""),
        "fecha": datos["Fecha"],
        "version": version,
        "fuerza": fuerza,
        "longitud": longitud,
    }
    pl = Plantilla.cargar(plantilla, variables)
    campos = pl.campos_portada
    orden = {c: datos[c] for c in campos if datos.get(c)}
    orden.update({k: v for k, v in datos.items() if k not in orden and v})

    memoria = Memoria(
        titulo=pl.texto("titulo"),
        datos=orden,
        pie=pl.texto("pie").strip(" ·"),
        avisos=[pl.texto("portada.aviso")],
    )
    c = _Constructor(
        modelo,
        resultados,
        pl,
        fuerza,
        longitud,
        _nombrador(nombres_nudos, "N"),
        _nombrador(nombres_barras, "B"),
    )
    memoria.agregar(c.alcance())
    memoria.agregar(c.geometria())
    memoria.agregar(c.materiales())
    memoria.agregar(c.cargas())
    if combs:
        memoria.agregar(c.combinaciones(combs))
    items: list[tuple[str, ResultadoCaso]] = []
    if incluir_casos or not items_comb:
        items += [(f"Caso {n}", resultados[n]) for n in resultados.casos]
    items += [(f"Combinación {n}", r) for n, r in items_comb]
    memoria.agregar(c.resultados(items))
    if len(items_comb) > 1:
        memoria.agregar(c.envolvente(items_comb))
    return memoria
