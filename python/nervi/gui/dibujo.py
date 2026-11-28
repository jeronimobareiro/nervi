# SPDX-License-Identifier: GPL-3.0-or-later
"""Dibujo con el mouse en la planta del edificio (#73 segunda parte, #31).

Herramientas: *Eje*, *Columna*, *Viga*, *Losa* y *Muro*, con enganche a puntos,
extremos, medios, cruces, ejes, líneas polares y grilla (``nervi.enganche``, en
Rust), Orto (F8), entrada de largo y ángulo junto al cursor y un Ctrl+Z por tramo.

- **Eje**: dos clics. Los ejes más verticales que horizontales se nombran con
  letras (A, B…) y los otros con números (1, 2…).
- **Columna**: un clic pone una columna del piso de abajo a este; arrastrar una
  ventana pone una en cada cruce de ejes de adentro que no tenga.
- **Viga** y **Muro**: tramos encadenados; Esc o Enter terminan. La viga se parte en
  cada columna por la que pasa.
- **Losa**: un clic dentro de un paño cerrado por vigas y muros crea la losa con su
  contorno (``nervi.enganche.pano_en``). Fuera de un paño, los clics dibujan el
  contorno a mano; un clic en el primer punto o Enter lo cierran.

La geometría (enganche, paños, cruces y cortes) va en Rust; este módulo es la
interfaz: lee el mouse y el teclado, dibuja la vista previa y aplica los cambios con
:meth:`EstadoEdificio.aplicar`.
"""

from __future__ import annotations

import math
import string
from collections import Counter
from dataclasses import dataclass
from itertools import pairwise

from PySide6.QtCore import QObject, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QDoubleValidator, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from ..enganche import TIPOS, Enganche, GeometriaPlanta, cruces, geometria_planta, pano_en, partir
from ..fisico import ModeloFisico
from . import ajustes, estilo
from .navegacion import METROS

#: Herramientas de la planta, con su ícono del catálogo y su nombre.
HERRAMIENTAS = {
    "seleccionar": ("seleccionar", "Seleccionar"),
    "ejes": ("ejes", "Eje"),
    "columnas": ("columnas", "Columna"),
    "vigas": ("vigas", "Viga"),
    "losas": ("losas", "Losa"),
    "muros": ("muros", "Muro"),
}
#: Enganches que se prenden y apagan desde la barra, con su nombre.
ENGANCHES = {
    "grilla": "Grilla",
    "ejes": "Ejes",
    "extremos": "Extremos",
    "medio": "Medio",
    "cruces": "Cruces",
    "orto": "Orto F8",
}
#: Tolerancia de captura en píxeles.
RADIO_PX = 10.0
#: Paso de la grilla de enganche en metros.
PASO_GRILLA_M = 0.5
#: Píxeles que hay que arrastrar con la herramienta Columna para que sea una ventana.
ARRASTRE_PX = 6.0
#: Secciones, material y espesores que se crean si el modelo no tiene.
SECCION_VIGA = ("V 20x50", 200.0, 500.0)
SECCION_COLUMNA = ("C 30x30", 300.0, 300.0)
MATERIAL = ("H-25", 25.0)
ESPESOR_LOSA = 120.0
ESPESOR_MURO = 200.0

Punto = tuple[float, float]


def _num(v: float) -> str:
    return f"{v:.2f}".replace("-", "−")


@dataclass
class OpcionesDibujo:
    """Lo que el usuario elige para dibujar; se recuerda entre sesiones."""

    enganches: dict[str, bool]
    #: Sección y material elegidos para cada lista (``None``: la de por omisión).
    seccion: dict[str, int | None]
    material: int | None = None
    espesor_losa: float = ESPESOR_LOSA
    espesor_muro: float = ESPESOR_MURO
    encadenar: bool = True
    partir_en_columnas: bool = True

    @classmethod
    def leer(cls) -> OpcionesDibujo:
        cfg = ajustes.configuracion()
        enganches = {}
        for clave in ENGANCHES:
            v = cfg.value(f"dibujo/{clave}", clave != "orto")
            enganches[clave] = v if isinstance(v, bool) else str(v).lower() == "true"
        return cls(enganches, {"vigas": None, "columnas": None})

    def guardar(self) -> None:
        cfg = ajustes.configuracion()
        for clave, v in self.enganches.items():
            cfg.setValue(f"dibujo/{clave}", v)


class EntradaNumerica(QFrame):
    """Largo y ángulo junto al cursor: se escribe y Enter fija el punto."""

    aceptada = Signal(float, object)  # largo, ángulo en grados o None
    cancelada = Signal()

    def __init__(self, padre: QWidget) -> None:
        super().__init__(padre, objectName="entrada_numerica")
        capa = QGridLayout(self)
        capa.setContentsMargins(8, 6, 8, 6)
        capa.setHorizontalSpacing(8)
        capa.setVerticalSpacing(4)
        self.largo = QLineEdit()
        self.angulo = QLineEdit()
        for fila, (texto, campo) in enumerate((("Largo", self.largo), ("Ángulo", self.angulo))):
            capa.addWidget(QLabel(texto, objectName="tenue"), fila, 0)
            campo.setValidator(QDoubleValidator())
            campo.setAlignment(Qt.AlignRight)
            campo.setFixedWidth(92)
            campo.installEventFilter(self)
            capa.addWidget(campo, fila, 1)
        QWidget.setTabOrder(self.largo, self.angulo)
        QWidget.setTabOrder(self.angulo, self.largo)
        self.hide()

    def mostrar(self, largo: float, angulo: float, unidad: str) -> None:
        """Muestra los valores de la vista previa como sugerencia."""
        self.largo.setPlaceholderText(f"{_num(largo)} {unidad}")
        self.angulo.setPlaceholderText(f"{_num(angulo)}°")

    def empezar(self, texto: str) -> None:
        self.largo.setText(texto)
        self.angulo.clear()
        self.show()
        self.raise_()
        self.largo.setFocus()

    def editando(self) -> bool:
        return self.isVisible() and (self.largo.hasFocus() or self.angulo.hasFocus())

    @staticmethod
    def _valor(campo: QLineEdit) -> float | None:
        try:
            return float(campo.text().replace(",", "."))
        except ValueError:
            return None

    def _aceptar(self) -> None:
        largo = self._valor(self.largo)
        if largo is None or largo <= 0:
            self.largo.setFocus()
            return
        self.aceptada.emit(largo, self._valor(self.angulo))
        self.terminar()

    def terminar(self) -> None:
        self.largo.clear()
        self.angulo.clear()
        self.hide()
        self.parentWidget().setFocus()

    def eventFilter(self, objeto, evento) -> bool:
        if evento.type() == evento.Type.KeyPress:
            if evento.key() == Qt.Key_Escape:
                self.terminar()
                self.cancelada.emit()
                return True
            # Enter se usa acá: QLineEdit lo deja pasar a la planta, que terminaría el trazo.
            if evento.key() in (Qt.Key_Return, Qt.Key_Enter):
                self._aceptar()
                return True
        return super().eventFilter(objeto, evento)


def _mas_usado(valores, por_omision=None):
    c = Counter(valores)
    return c.most_common(1)[0][0] if c else por_omision


class DibujoEdificio(QObject):
    """Herramientas de dibujo de la planta del edificio. La planta le pasa el mouse,
    el teclado y el pintor; esta clase decide qué crear."""

    #: Cambió la herramienta o las opciones (la barra y el panel se actualizan).
    cambiado = Signal()

    def __init__(self, planta, estado) -> None:
        super().__init__(planta)
        self.planta = planta
        self.estado = estado
        self.herramienta = "seleccionar"
        self.opciones = OpcionesDibujo.leer()
        #: Puntos fijados del trazo en curso (modelo).
        self.puntos: list[Punto] = []
        #: Enganche bajo el cursor y su posición en pantalla.
        self.enganche: Enganche | None = None
        self.cursor: QPointF | None = None
        self._recientes: list[int] = []
        self._geometria: GeometriaPlanta | None = None
        self._ventana: QPointF | None = None  # inicio de la ventana de columnas
        self._pano: list[Punto] | None = None  # paño bajo el cursor (herramienta Losa)
        self.entrada = EntradaNumerica(planta)
        self.entrada.aceptada.connect(self._numerico)
        self.entrada.cancelada.connect(planta.update)
        estado.cambiado.connect(self._invalidar)

    # -- estado -------------------------------------------------------------------
    @property
    def activo(self) -> bool:
        return self.herramienta != "seleccionar"

    def elegir(self, herramienta: str) -> None:
        if herramienta not in HERRAMIENTAS:
            raise ValueError(f"herramienta {herramienta!r}; válidas {tuple(HERRAMIENTAS)}")
        self.herramienta = herramienta
        self.cancelar()
        if herramienta != "seleccionar":
            self.estado.elegir(None)
        self.planta.setCursor(Qt.ArrowCursor if herramienta == "seleccionar" else Qt.CrossCursor)
        self.cambiado.emit()
        self.planta.update()

    def poner_enganche(self, clave: str, valor: bool) -> None:
        self.opciones.enganches[clave] = valor
        self.opciones.guardar()
        self._geometria = None
        self.cambiado.emit()
        self.planta.update()

    def cancelar(self) -> None:
        self.puntos.clear()
        self._ventana = None
        self.entrada.terminar() if self.entrada.isVisible() else None
        self.planta.update()

    def _invalidar(self) -> None:
        self._geometria = None
        self._recientes.clear()
        self._pano = None

    def geometria(self) -> GeometriaPlanta:
        if self._geometria is None:
            self._geometria = geometria_planta(
                self.estado.modelo(), self.estado.piso, ejes=self.opciones.enganches["ejes"]
            )
        return self._geometria

    def _unidad(self) -> str:
        return self.estado.modelo().longitud

    # -- enganche -------------------------------------------------------------------
    def enganchar(self, pos: QPointF) -> Enganche | None:
        t = self.planta.transformacion()
        if t is None:
            return None
        x, y = t.a_modelo(pos)
        o = self.opciones.enganches
        g = self.geometria()
        paso = PASO_GRILLA_M / METROS.get(self._unidad(), 1.0) if o["grilla"] else 0.0
        e = g.indice.enganchar(
            x,
            y,
            RADIO_PX / t.escala,
            anterior=self.puntos[-1] if self.puntos else None,
            puntos=o["extremos"],
            extremos=o["extremos"],
            perpendicular=o["extremos"],
            medios=o["medio"],
            cruces=o["cruces"],
            orto=o["orto"],
            recientes=self._recientes,
            paso_grilla=paso,
        )
        # Los segmentos que pasa el mouse sirven de guía de prolongación (FreeCAD).
        if e.tipo in ("extremo", "cerca", "medio") and e.elemento is not None:
            if e.elemento in self._recientes:
                self._recientes.remove(e.elemento)
            self._recientes.insert(0, e.elemento)
            del self._recientes[4:]
        return e

    # -- eventos que pasa la planta ---------------------------------------------------
    def mover(self, pos: QPointF) -> None:
        if not self.activo:
            return
        self.cursor = pos
        self.enganche = self.enganchar(pos)
        self._pano = None
        if self.herramienta == "losas" and not self.puntos and self.enganche is not None:
            self._pano = self._pano_en(self.enganche.punto)
        if self.puntos and self.enganche is not None:
            largo, angulo = self._largo_angulo(self.puntos[-1], self.enganche.punto)
            self.entrada.mostrar(largo, angulo, self._unidad())
        self._ubicar_entrada()
        self.planta.update()

    def salir(self) -> None:
        self.cursor = None
        self.enganche = None
        self._pano = None
        self.planta.update()

    def presionar(self, pos: QPointF) -> None:
        self.mover(pos)
        if self.herramienta == "columnas":
            self._ventana = pos
            return
        if self.enganche is not None:
            self.fijar(self.enganche.punto)

    def soltar(self, pos: QPointF) -> None:
        if self.herramienta != "columnas" or self._ventana is None:
            return
        inicio, self._ventana = self._ventana, None
        if math.hypot(pos.x() - inicio.x(), pos.y() - inicio.y()) >= ARRASTRE_PX:
            t = self.planta.transformacion()
            if t is not None:
                self.columnas_en_ventana(t.a_modelo(inicio), t.a_modelo(pos))
            return
        e = self.enganchar(pos)
        if e is not None:
            self.fijar(e.punto)

    def tecla(self, evento) -> bool:
        """Teclas de las herramientas. Devuelve ``True`` si se usó la tecla."""
        if not self.activo:
            return False
        k = evento.key()
        if k == Qt.Key_Escape:
            if self.puntos:
                self.cancelar()
            else:
                self.elegir("seleccionar")
            return True
        if k in (Qt.Key_Return, Qt.Key_Enter):
            if self.herramienta == "losas" and len(self.puntos) >= 3:
                self._crear_losa(list(self.puntos))
            self.cancelar()
            return True
        if k == Qt.Key_Backspace and self.puntos:
            self.puntos.pop()
            self.planta.update()
            return True
        if k == Qt.Key_F8:
            self.poner_enganche("orto", not self.opciones.enganches["orto"])
            return True
        texto = evento.text()
        if self.puntos and texto and texto in string.digits + ".,-":
            self.entrada.empezar(texto)
            self._ubicar_entrada()
            return True
        return False

    def _ubicar_entrada(self) -> None:
        if self.cursor is None:
            return
        self.entrada.adjustSize()
        x = min(self.cursor.x() + 18, self.planta.width() - self.entrada.width() - 8)
        y = min(self.cursor.y() + 24, self.planta.height() - self.entrada.height() - 44)
        self.entrada.move(int(max(8, x)), int(max(8, y)))

    # -- geometría -------------------------------------------------------------------
    @staticmethod
    def _largo_angulo(a: Punto, b: Punto) -> tuple[float, float]:
        dx, dy = b[0] - a[0], b[1] - a[1]
        return math.hypot(dx, dy), math.degrees(math.atan2(dy, dx))

    def _numerico(self, largo: float, angulo: float | None) -> None:
        if not self.puntos:
            return
        a = self.puntos[-1]
        if angulo is None:
            if self.enganche is None:
                return
            _, angulo = self._largo_angulo(a, self.enganche.punto)
        r = math.radians(angulo)
        # Los múltiplos de 90° van exactos.
        c, s = math.cos(r), math.sin(r)
        if abs(angulo % 90.0) < 1e-12 or abs(angulo % 90.0 - 90.0) < 1e-12:
            c, s = round(c), round(s)
        self.fijar((a[0] + largo * c, a[1] + largo * s))

    def _apoyos(self, mf: ModeloFisico) -> list[tuple[Punto, Punto]]:
        en = mf.en_piso(self.estado.piso)
        return [(tuple(e["p1"]), tuple(e["p2"])) for lista in ("vigas", "muros") for e in en[lista]]

    def _pano_en(self, p: Punto) -> list[Punto] | None:
        mf = self.estado.modelo()
        if self.estado.piso is None:
            return None
        return pano_en(self._apoyos(mf), p, self._tol(mf))

    @staticmethod
    def _tol(mf: ModeloFisico) -> float:
        return 1e-6 / METROS.get(mf.longitud, 1.0)

    # -- crear ----------------------------------------------------------------------
    def fijar(self, p: Punto) -> None:
        """Fija un punto del trazo con la herramienta activa."""
        h = self.herramienta
        if self.estado.piso is None:
            self.estado.mensaje.emit("Agregá un piso antes de dibujar")
            return
        if h == "columnas":
            self._crear_columnas([p])
        elif h == "losas":
            if not self.puntos:
                pano = self._pano_en(p)
                if pano is not None:
                    self._crear_losa(pano)
                    return
            elif len(self.puntos) >= 3 and self._cerca_en_pantalla(p, self.puntos[0]):
                self._crear_losa(list(self.puntos))
                self.cancelar()
                return
            self.puntos.append(p)
        elif h in ("ejes", "vigas", "muros"):
            if not self.puntos:
                self.puntos.append(p)
            elif not _cerca(p, self.puntos[-1]):
                a = self.puntos[-1]
                ok = {
                    "ejes": self._crear_eje,
                    "vigas": self._crear_viga,
                    "muros": self._crear_muro,
                }[h](a, p)
                if ok and (h == "ejes" or not self.opciones.encadenar):
                    self.puntos.clear()
                elif ok:
                    self.puntos = [p]
        self.planta.update()

    def _cerca_en_pantalla(self, a: Punto, b: Punto) -> bool:
        t = self.planta.transformacion()
        if t is None:
            return _cerca(a, b)
        return math.hypot(a[0] - b[0], a[1] - b[1]) * t.escala <= RADIO_PX

    def _piso_abajo(self, mf: ModeloFisico) -> int | None:
        orden = [q["id"] for q in mf.pisos_ordenados()]
        k = orden.index(self.estado.piso)
        return orden[k - 1] if k > 0 else None

    def _material(self, mf: ModeloFisico) -> int:
        if self.opciones.material in {m["id"] for m in mf.lista("materiales")}:
            return self.opciones.material
        usados = [
            e["material"]
            for lista in ("vigas", "columnas", "losas", "muros")
            for e in mf.lista(lista)
        ]
        hormigones = [m["id"] for m in mf.lista("materiales") if m["tipo"] == "hormigon"]
        m = _mas_usado(usados) or (hormigones[0] if hormigones else None)
        if m is None:
            nombre, fc = MATERIAL
            m = mf.agregar_material(nombre, "hormigon", fc=fc)
        return m

    def _seccion(self, mf: ModeloFisico, lista: str) -> int:
        ids = {s["id"] for s in mf.lista("secciones")}
        elegida = self.opciones.seccion.get(lista)
        if elegida in ids:
            return elegida
        s = _mas_usado(e["seccion"] for e in mf.lista(lista))
        if s is not None:
            return s
        nombre, b, h = SECCION_VIGA if lista == "vigas" else SECCION_COLUMNA
        for sec in mf.lista("secciones"):
            if sec["nombre"] == nombre:
                return sec["id"]
        return mf.agregar_seccion(nombre, "rectangular", b=b, h=h)

    def _crear_eje(self, a: Punto, b: Punto) -> bool:
        def cambio(mf: ModeloFisico) -> None:
            vertical = abs(b[0] - a[0]) < abs(b[1] - a[1])
            usados = {e["nombre"] for e in mf.lista("ejes")}
            if vertical:
                nombres = _letras()
            else:
                nombres = (str(k) for k in range(1, 10_000))
            nombre = next(n for n in nombres if n not in usados)
            # Los verticales de abajo hacia arriba y los horizontales de izquierda a
            # derecha: la burbuja va en p2, arriba o a la derecha.
            p1, p2 = (a, b) if (b[1] - a[1] if vertical else b[0] - a[0]) >= 0 else (b, a)
            mf.agregar_eje(nombre, p1, p2)

        return self.estado.aplicar(cambio, "Dibujar eje")

    def _crear_viga(self, a: Punto, b: Punto) -> bool:
        piso = self.estado.piso

        def cambio(mf: ModeloFisico) -> None:
            s, m = self._seccion(mf, "vigas"), self._material(mf)
            ts = [0.0, 1.0]
            if self.opciones.partir_en_columnas:
                cols = [c["punto"] for c in mf.en_piso(piso)["columnas"]]
                ts = [0.0, *partir((a, b), cols, self._tol(mf)), 1.0]
            for t0, t1 in pairwise(ts):
                mf.agregar_viga(piso, _en(a, b, t0), _en(a, b, t1), s, m)

        return self.estado.aplicar(cambio, "Dibujar viga")

    def _crear_muro(self, a: Punto, b: Punto) -> bool:
        piso = self.estado.piso

        def cambio(mf: ModeloFisico) -> None:
            abajo = self._piso_abajo(mf)
            if abajo is None:
                raise ValueError("Los muros van del piso de abajo a este: subí una planta")
            mf.agregar_muro(a, b, abajo, piso, self.opciones.espesor_muro, self._material(mf))

        return self.estado.aplicar(cambio, "Dibujar muro")

    def _crear_columnas(self, puntos: list[Punto]) -> bool:
        piso = self.estado.piso

        def cambio(mf: ModeloFisico) -> None:
            abajo = self._piso_abajo(mf)
            if abajo is None:
                raise ValueError("Las columnas van del piso de abajo a este: subí una planta")
            hay = [tuple(c["punto"]) for c in mf.en_piso(piso)["columnas"]]
            nuevos = [p for p in puntos if not any(_cerca(p, q) for q in hay)]
            if not nuevos:
                raise ValueError("Ya hay una columna ahí")
            s, m = self._seccion(mf, "columnas"), self._material(mf)
            for p in nuevos:
                mf.agregar_columna(p, abajo, piso, s, m)

        texto = "Dibujar columna" if len(puntos) == 1 else "Columnas en los cruces de ejes"
        return self.estado.aplicar(cambio, texto)

    def columnas_en_ventana(self, a: Punto, b: Punto) -> bool:
        """Una columna en cada cruce de ejes dentro del rectángulo ``a``-``b``."""
        mf = self.estado.modelo()
        ejes = [(tuple(e["p1"]), tuple(e["p2"])) for e in mf.lista("ejes")]
        x0, x1 = sorted((a[0], b[0]))
        y0, y1 = sorted((a[1], b[1]))
        dentro = [p for p in cruces(ejes, self._tol(mf)) if x0 <= p[0] <= x1 and y0 <= p[1] <= y1]
        if not dentro:
            self.estado.mensaje.emit("No hay cruces de ejes dentro de la ventana")
            return False
        return self._crear_columnas(sorted(dentro, key=lambda p: (p[1], p[0])))

    def _crear_losa(self, contorno: list[Punto]) -> bool:
        piso = self.estado.piso

        def cambio(mf: ModeloFisico) -> None:
            mf.agregar_losa(piso, contorno, self.opciones.espesor_losa, self._material(mf))

        return self.estado.aplicar(cambio, "Dibujar losa")

    # -- dibujo -----------------------------------------------------------------------
    def pintar(self, p: QPainter, t) -> None:
        if not self.activo or t is None:
            return
        acento = QColor(estilo.ACENTO)
        p.save()
        p.setFont(QFont(self.planta.font().family(), 8))
        if self._pano is not None:
            relleno = QColor(estilo.ACENTO)
            relleno.setAlphaF(0.12)
            p.setPen(QPen(acento, 1.5, Qt.DashLine))
            p.setBrush(relleno)
            p.drawPolygon(QPolygonF([t.a_pantalla(*q) for q in self._pano]))
        e = self.enganche
        if self.puntos:
            p.setPen(QPen(acento, 1.6, Qt.DashLine))
            p.setBrush(Qt.NoBrush)
            pts = [t.a_pantalla(*q) for q in self.puntos]
            for q0, q1 in pairwise(pts):
                p.drawLine(q0, q1)
            if e is not None:
                fin = t.a_pantalla(*e.punto)
                p.drawLine(pts[-1], fin)
                if self.herramienta == "losas" and len(pts) >= 2:
                    p.setPen(QPen(acento, 1, Qt.DotLine))
                    p.drawLine(fin, pts[0])
                self._cota(p, pts[-1], fin)
        if self._ventana is not None and self.cursor is not None:
            p.setPen(QPen(acento, 1, Qt.DashLine))
            relleno = QColor(estilo.ACENTO)
            relleno.setAlphaF(0.08)
            p.setBrush(relleno)
            p.drawRect(QRectF(self._ventana, self.cursor).normalized())
        if e is not None and e.guia is not None:
            a, b = t.a_pantalla(*e.guia[0]), t.a_pantalla(*e.guia[1])
            p.setPen(QPen(acento, 1, Qt.DotLine))
            p.drawLine(a, b)
        if e is not None:
            self._marca(p, t.a_pantalla(*e.punto), e)
        p.restore()

    def _marca(self, p: QPainter, q: QPointF, e: Enganche) -> None:
        acento = QColor(estilo.ACENTO)
        p.setPen(QPen(acento, 1.4))
        p.setBrush(Qt.NoBrush)
        # Cruz del cursor.
        p.drawLine(q + QPointF(-14, 0), q + QPointF(14, 0))
        p.drawLine(q + QPointF(0, -14), q + QPointF(0, 14))
        p.setPen(QPen(acento, 2))
        r = 6.0
        if e.tipo in ("punto", "extremo"):
            p.drawRect(QRectF(q.x() - r, q.y() - r, 2 * r, 2 * r))
        elif e.tipo == "medio":
            p.drawPolygon(
                QPolygonF([q + QPointF(0, -r - 1), q + QPointF(r + 1, r), q + QPointF(-r - 1, r)])
            )
        elif e.tipo in ("cruce", "cruce_guias"):
            p.drawLine(q + QPointF(-r, -r), q + QPointF(r, r))
            p.drawLine(q + QPointF(-r, r), q + QPointF(r, -r))
        elif e.tipo == "perpendicular":
            p.drawLine(q + QPointF(-r, r), q + QPointF(r, r))
            p.drawLine(q + QPointF(0, r), q + QPointF(0, -r))
        elif e.tipo == "cerca":
            p.drawPolygon(
                QPolygonF(
                    [q + QPointF(0, -r), q + QPointF(r, 0), q + QPointF(0, r), q + QPointF(-r, 0)]
                )
            )
        elif e.tipo in ("grilla", "polar", "prolongacion"):
            p.drawRect(QRectF(q.x() - 3.5, q.y() - 3.5, 7, 7))
        nombre = TIPOS.get(e.tipo, "")
        origen = self.geometria().origen(e)
        if origen is not None:
            nombre += " · " + _nombre(self.estado.modelo(), *origen)
        if nombre:
            _etiqueta(p, q + QPointF(12, -28), nombre)

    def _cota(self, p: QPainter, a: QPointF, b: QPointF) -> None:
        largo, angulo = self._largo_angulo(
            self.puntos[-1], self.enganche.punto if self.enganche else self.puntos[-1]
        )
        if largo <= 0:
            return
        _etiqueta(
            p, (a + b) / 2 + QPointF(10, 10), f"{_num(largo)} {self._unidad()} · {angulo:.0f}°"
        )


def _etiqueta(p: QPainter, izq: QPointF, texto: str) -> None:
    fm = p.fontMetrics()
    r = QRectF(izq.x(), izq.y(), fm.horizontalAdvance(texto) + 14, 20)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(estilo.ACENTO))
    p.drawRoundedRect(r, 4, 4)
    p.setPen(QColor(estilo.actual.sobre_acento))
    p.drawText(r, Qt.AlignCenter, texto)


def _nombre(mf: ModeloFisico, lista: str, id: int) -> str:
    from .edificio import nombre_elemento

    try:
        el = mf.elemento(lista, id)
    except KeyError:
        return ""
    return el.get("nombre") or nombre_elemento(lista, el)


def _letras():
    """A, B, …, Z, AA, AB, …"""
    for n in range(1, 4):
        for k in range(26**n):
            s = ""
            for _ in range(n):
                k, r = divmod(k, 26)
                s = string.ascii_uppercase[r] + s
            yield s


def _en(a: Punto, b: Punto, t: float) -> Punto:
    if t == 0.0:
        return a
    if t == 1.0:
        return b
    return (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))


def _cerca(a: Punto, b: Punto, tol: float = 1e-9) -> bool:
    return abs(a[0] - b[0]) <= tol and abs(a[1] - b[1]) <= tol


TITULOS_NUEVO = {
    "ejes": "NUEVO EJE",
    "columnas": "NUEVA COLUMNA",
    "vigas": "NUEVA VIGA",
    "losas": "NUEVA LOSA",
    "muros": "NUEVO MURO",
}
AYUDAS = {
    "ejes": "Clic en el primer punto y en el segundo. Los ejes verticales se nombran "
    "con letras y los horizontales con números.",
    "columnas": "Clic donde va la columna, o arrastrá una ventana para poner una en "
    "cada cruce de ejes. Van del piso de abajo a este.",
    "vigas": "Clic en cada punto; escribí el largo y Enter para fijarlo. Esc o clic "
    "derecho terminan. Cada tramo se deshace con Ctrl+Z.",
    "losas": "Clic dentro de un paño cerrado por vigas y muros. Fuera de un paño, "
    "clic en cada vértice y en el primero (o Enter) para cerrar.",
    "muros": "Clic en cada punto; van del piso de abajo a este. Esc o clic derecho terminan.",
}


class PanelHerramienta(QWidget):
    """Opciones de la herramienta de dibujo activa, en el lugar de Propiedades."""

    def __init__(self, dibujo: DibujoEdificio) -> None:
        super().__init__(objectName="panel")
        self.dibujo = dibujo
        capa = QVBoxLayout(self)
        capa.setContentsMargins(14, 12, 14, 12)
        capa.setSpacing(8)
        self.lbl_tipo = QLabel(objectName="seccion")
        capa.addWidget(self.lbl_tipo)
        self.form = QFormLayout()
        self.form.setHorizontalSpacing(12)
        self.form.setVerticalSpacing(6)
        capa.addLayout(self.form)
        self.seccion = QComboBox()
        self.material = QComboBox()
        self.espesor = QDoubleSpinBox(decimals=0, minimum=50, maximum=2000, singleStep=10)
        self.espesor.setSuffix(" mm")
        self.seccion.setToolTip("Automática: la más usada en el modelo, o una nueva si no hay")
        self.material.setToolTip("Automático: el más usado en el modelo, o H-25 si no hay")
        self.form.addRow("Sección", self.seccion)
        self.form.addRow("Material", self.material)
        self.form.addRow("Espesor", self.espesor)
        self.encadenar = QCheckBox("Encadenar tramos")
        self.partir = QCheckBox("Partir en cada columna")
        capa.addWidget(self.encadenar)
        capa.addWidget(self.partir)
        self.lbl_ayuda = QLabel(objectName="tenue")
        self.lbl_ayuda.setWordWrap(True)
        capa.addWidget(self.lbl_ayuda)
        capa.addStretch()
        self.setMinimumWidth(240)
        self.seccion.activated.connect(self._elegir_seccion)
        self.material.activated.connect(self._elegir_material)
        self.espesor.valueChanged.connect(self._elegir_espesor)
        self.encadenar.toggled.connect(lambda v: setattr(dibujo.opciones, "encadenar", v))
        self.partir.toggled.connect(lambda v: setattr(dibujo.opciones, "partir_en_columnas", v))
        dibujo.cambiado.connect(self.actualizar)
        dibujo.estado.cambiado.connect(self.actualizar)
        self.actualizar()

    def actualizar(self) -> None:
        h = self.dibujo.herramienta
        if h == "seleccionar":
            return
        o = self.dibujo.opciones
        mf = self.dibujo.estado.modelo()
        self.lbl_tipo.setText(TITULOS_NUEVO[h])
        self.lbl_ayuda.setText(AYUDAS[h])
        self.seccion.blockSignals(True)
        self.seccion.clear()
        self.seccion.addItem("Automática", None)
        for s in mf.lista("secciones"):
            self.seccion.addItem(s["nombre"], s["id"])
        self.seccion.setCurrentIndex(max(self.seccion.findData(o.seccion.get(h)), 0))
        self.seccion.blockSignals(False)
        self.material.blockSignals(True)
        self.material.clear()
        self.material.addItem("Automático", None)
        for m in mf.lista("materiales"):
            self.material.addItem(m["nombre"], m["id"])
        self.material.setCurrentIndex(max(self.material.findData(o.material), 0))
        self.material.blockSignals(False)
        self.espesor.blockSignals(True)
        self.espesor.setValue(o.espesor_losa if h == "losas" else o.espesor_muro)
        self.espesor.blockSignals(False)
        self.form.setRowVisible(self.seccion, h in ("vigas", "columnas"))
        self.form.setRowVisible(self.material, h != "ejes")
        self.form.setRowVisible(self.espesor, h in ("losas", "muros"))
        self.encadenar.setVisible(h in ("vigas", "muros"))
        self.encadenar.setChecked(o.encadenar)
        self.partir.setVisible(h == "vigas")
        self.partir.setChecked(o.partir_en_columnas)

    def _elegir_seccion(self, i: int) -> None:
        self.dibujo.opciones.seccion[self.dibujo.herramienta] = self.seccion.itemData(i)

    def _elegir_material(self, i: int) -> None:
        self.dibujo.opciones.material = self.material.itemData(i)

    def _elegir_espesor(self, v: float) -> None:
        if self.dibujo.herramienta == "losas":
            self.dibujo.opciones.espesor_losa = v
        else:
            self.dibujo.opciones.espesor_muro = v
