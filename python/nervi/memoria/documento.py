# SPDX-License-Identifier: GPL-3.0-or-later
"""Estructura de una memoria de cálculo, independiente del formato de salida.

Una :class:`Memoria` es una lista de :class:`Capitulo`, y cada capítulo una lista
de bloques: :class:`Parrafo`, :class:`Tabla` y :class:`Figura`. El contenido se
arma con funciones que leen el modelo y los resultados (``analisis.py``) y se
dibuja con un renderizador (hoy solo PDF, ``pdf.py``).

Cualquier módulo puede sumar sus propios capítulos con :meth:`Memoria.agregar`.
Por ejemplo, un módulo de diseño de vigas de hormigón armado agrega un capítulo
con :func:`tabla_verificaciones`, sin tocar el renderizador ni el análisis.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np


@dataclass
class Parrafo:
    """Texto corrido. Admite ``<b>``, ``<i>``, ``<sub>`` y ``<sup>``."""

    texto: str
    #: ``"normal"``, ``"nota"`` (letra chica) o ``"aviso"`` (recuadro destacado).
    estilo: str = "normal"


@dataclass
class Tabla:
    """Tabla con encabezado. Las celdas ya vienen formateadas como texto."""

    columnas: list[str]
    filas: list[list[str]]
    titulo: str = ""
    #: Ancho relativo de cada columna (``None``: todas iguales).
    anchos: list[float] | None = None
    #: Alineación por columna: ``"izq"``, ``"centro"`` o ``"der"`` (por defecto,
    #: la primera a la izquierda y el resto a la derecha).
    alineacion: list[str] | None = None
    nota: str = ""


@dataclass
class Trazo:
    """Polilínea o polígono en coordenadas del modelo."""

    puntos: np.ndarray  # (n, 2)
    #: Rol del trazo, que el renderizador traduce a color y grosor:
    #: ``"estructura"``, ``"tenue"``, ``"positivo"``, ``"negativo"``,
    #: ``"deformada"``, ``"apoyo"``, ``"carga"``.
    estilo: str = "estructura"
    cerrado: bool = False
    relleno: bool = False


@dataclass
class Rotulo:
    """Texto ubicado en coordenadas del modelo."""

    x: float
    y: float
    texto: str
    estilo: str = "valor"  # "valor", "nudo", "barra"


@dataclass
class Figura:
    """Dibujo vectorial: trazos y rótulos en coordenadas del modelo."""

    titulo: str
    trazos: list[Trazo] = field(default_factory=list)
    rotulos: list[Rotulo] = field(default_factory=list)
    #: Las figuras con el mismo ``grupo`` consecutivas se ponen en una grilla.
    grupo: str = ""

    def limites(self) -> tuple[float, float, float, float]:
        """``(xmin, ymin, xmax, ymax)`` de todo lo dibujado."""
        pts = [t.puntos for t in self.trazos if len(t.puntos)]
        pts += [np.array([[r.x, r.y]]) for r in self.rotulos]
        if not pts:
            return (0.0, 0.0, 1.0, 1.0)
        todo = np.vstack(pts)
        return (*todo.min(axis=0), *todo.max(axis=0))


@dataclass
class Capitulo:
    """Sección numerada de la memoria. ``nivel`` 1 es un capítulo, 2 un apartado."""

    titulo: str
    #: Párrafos, tablas, figuras y subcapítulos, en orden.
    bloques: list[Parrafo | Tabla | Figura | Capitulo] = field(default_factory=list)
    nivel: int = 1
    #: Empezar en una página nueva.
    pagina_nueva: bool = False

    def parrafo(self, texto: str, estilo: str = "normal") -> Capitulo:
        if texto:
            self.bloques.append(Parrafo(texto, estilo))
        return self

    def tabla(self, tabla: Tabla) -> Capitulo:
        self.bloques.append(tabla)
        return self

    def figura(self, figura: Figura) -> Capitulo:
        self.bloques.append(figura)
        return self

    def subcapitulo(self, titulo: str, pagina_nueva: bool = False) -> Capitulo:
        """Agrega y devuelve un subcapítulo (un nivel más abajo)."""
        sub = Capitulo(titulo, nivel=self.nivel + 1, pagina_nueva=pagina_nueva)
        self.bloques.append(sub)
        return sub


@dataclass
class Memoria:
    """Documento completo: datos de portada y capítulos en orden."""

    titulo: str
    #: Datos de portada en orden, por ejemplo ``{"Proyecto": ..., "Autor": ...}``.
    datos: dict[str, str] = field(default_factory=dict)
    capitulos: list[Capitulo] = field(default_factory=list)
    #: Texto al pie de cada página.
    pie: str = ""
    #: Avisos que van en la portada (por ejemplo, módulos experimentales).
    avisos: list[str] = field(default_factory=list)
    #: Normas y documentos de referencia, en la hoja que sigue a la carátula. Los
    #: módulos de diseño suman la suya (por ejemplo ``"ACI 318-19 · …"``).
    normas: list[str] = field(default_factory=list)
    #: Versión de Nervi que generó la memoria (va al pie de la carátula).
    version: str = ""

    def agregar(self, capitulo: Capitulo, antes_de: str | None = None) -> Capitulo:
        """Agrega un capítulo al final o antes del primero cuyo título empiece
        con ``antes_de``."""
        if antes_de is not None:
            for k, s in enumerate(self.capitulos):
                if s.titulo.startswith(antes_de):
                    self.capitulos.insert(k, capitulo)
                    return capitulo
        self.capitulos.append(capitulo)
        return capitulo

    def guardar_pdf(self, ruta: str | Path) -> Path:
        """Escribe la memoria en PDF (necesita ``reportlab``: ``pip install nervi[memoria]``)."""
        from .pdf import escribir_pdf

        return escribir_pdf(self, Path(ruta))


def tabla_verificaciones(
    filas: Sequence[Sequence[object]],
    titulo: str = "Verificaciones",
    unidades: str = "",
    decimal: str = ",",
) -> Tabla:
    """Tabla estándar de verificaciones de diseño.

    Cada fila es ``(elemento, verificación, solicitación, resistencia, artículo)``:
    la relación ``solicitación / resistencia`` y si cumple se calculan acá, así
    que todos los módulos de diseño las muestran igual. ``artículo`` es la cita
    de la norma aplicada (por ejemplo ``"ACI 318-19 §22.5.1.1"``); la memoria cita
    el artículo, no transcribe su texto.
    """
    salida = []
    for elemento, verificacion, solicitacion, resistencia, articulo in filas:
        s, r = float(solicitacion), float(resistencia)
        relacion = abs(s) / r if r > 0 else float("inf")
        salida.append(
            [
                str(elemento),
                str(verificacion),
                formatear(s, decimal=decimal),
                formatear(r, decimal=decimal),
                f"{relacion:.2f}".replace(".", decimal),
                "Cumple" if relacion <= 1.0 else "NO CUMPLE",
                str(articulo),
            ]
        )
    sufijo = f" ({unidades})" if unidades else ""
    return Tabla(
        columnas=[
            "Elemento",
            "Verificación",
            f"Solicitación{sufijo}",
            f"Resistencia{sufijo}",
            "Relación",
            "Estado",
            "Artículo",
        ],
        filas=salida,
        titulo=titulo,
        anchos=[1.0, 2.0, 1.3, 1.3, 0.9, 1.1, 1.8],
        alineacion=["izq", "izq", "der", "der", "der", "centro", "izq"],
    )


def formatear(v: float, cifras: int = 4, decimal: str = ",") -> str:
    """Número con ``cifras`` significativas, sin notación científica en el rango
    habitual, con ``0`` en lugar de ``-0`` y ``decimal`` como separador decimal."""
    texto = _formatear(float(v), cifras)
    return texto.replace(".", decimal) if decimal != "." else texto


def _formatear(v: float, cifras: int) -> str:
    if not np.isfinite(v):
        return "—"
    if v == 0.0 or abs(v) < 1e-12:
        return "0"
    a = abs(v)
    if 1e-4 <= a < 1e7:
        decimales = max(0, cifras - 1 - int(np.floor(np.log10(a))))
        texto = f"{v:.{decimales}f}"
        if "." in texto:
            texto = texto.rstrip("0").rstrip(".")
        return "0" if texto in ("-0", "") else texto
    mantisa, exponente = f"{v:.{cifras - 1}e}".split("e")
    if "." in mantisa:
        mantisa = mantisa.rstrip("0").rstrip(".")
    return f"{mantisa}e{int(exponente)}"


def formatear_factor(f: float, decimal: str = ",") -> str:
    """Factor de combinación con al menos un decimal, como en las normas: ``1,0``,
    ``1,2``, ``0,75``."""
    texto = f"{float(f):.3f}".rstrip("0")
    if texto.endswith("."):
        texto += "0"
    return texto.replace(".", decimal)
