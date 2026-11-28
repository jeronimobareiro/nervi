# SPDX-License-Identifier: GPL-3.0-or-later
"""Brújula de vistas del visor: los tres ejes del modelo vistos con la cámara actual.

Va abajo a la derecha del lienzo, en la vista de frente y en la 3D. Cada extremo de
eje es un botón: el positivo, un círculo lleno con su letra; el negativo, un círculo
hueco. Un clic pide mirar el modelo desde ese lado (``vista_pedida`` con ``"+Z"``,
``"-Y"``…; ver :data:`nervi.gui.camara3d.EXTREMOS`). Colores del tema: X en el color
negativo, Y en el de cumple y Z en el de acento. Es un dibujo propio de Nervi.
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QRegion
from PySide6.QtWidgets import QWidget

from . import estilo
from .camara3d import Camara3D

#: Lado del widget en píxeles y largo de cada semieje.
LADO = 96
RADIO = 30
#: Radio de los círculos de los extremos positivo y negativo.
R_POSITIVO, R_NEGATIVO = 8.0, 5.5
NOMBRES = {
    "+X": "Mirar desde +X",
    "-X": "Mirar desde −X",
    "+Y": "Mirar desde +Y (de atrás)",
    "-Y": "De frente (desde −Y)",
    "+Z": "En planta (desde arriba)",
    "-Z": "Desde abajo",
}


def _colores() -> dict[str, str]:
    return {"X": estilo.NEGATIVO, "Y": estilo.OK, "Z": estilo.ACENTO}


def extremos(camara: Camara3D, centro: QPointF, radio: float = RADIO) -> list[tuple]:
    """``(profundidad, clave, punto)`` de los seis extremos, del más lejano al más
    cercano a quien mira (el orden en que se dibujan)."""
    d, u, n = camara.ejes()
    salida = []
    for k, eje in enumerate("XYZ"):
        for signo in (1, -1):
            v = np.zeros(3)
            v[k] = signo
            q = QPointF(centro.x() + radio * float(v @ d), centro.y() - radio * float(v @ u))
            salida.append((float(v @ n), f"{'+' if signo > 0 else '-'}{eje}", q))
    salida.sort(key=lambda t: t[0])
    return salida


class Brujula(QWidget):
    """Brújula de vistas. ``camara`` se actualiza con :meth:`mostrar`."""

    vista_pedida = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.camara = Camara3D(0.0, 0.0, (0.0, 0.0, 0.0), 1.0)
        self._encima: str | None = None
        self.setFixedSize(LADO, LADO)
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Clic en un eje: mirar el modelo desde ese lado")
        # Solo el círculo recibe clics y tapa el lienzo (también sobre el visor de VTK).
        self.setMask(QRegion(0, 0, LADO, LADO, QRegion.Ellipse))

    def mostrar(self, camara: Camara3D) -> None:
        self.camara = camara
        self.update()

    def acomodar(self, margen_abajo: int = 48) -> None:
        """Abajo a la derecha del widget padre, sobre la barra de coordenadas."""
        p = self.parentWidget()
        if p is not None:
            self.move(p.width() - LADO - 10, p.height() - LADO - margen_abajo)

    def extremo_en(self, pos: QPointF) -> str | None:
        """Clave del extremo bajo ``pos`` (el más cercano a quien mira, si se tapan)."""
        centro = QPointF(LADO / 2, LADO / 2)
        for _prof, clave, q in reversed(extremos(self.camara, centro)):
            r = (R_POSITIVO if clave[0] == "+" else R_NEGATIVO) + 3
            if (q.x() - pos.x()) ** 2 + (q.y() - pos.y()) ** 2 <= r * r:
                return clave
        return None

    # --- Eventos ----------------------------------------------------------------------
    def mouseMoveEvent(self, evento) -> None:
        clave = self.extremo_en(evento.position())
        if clave != self._encima:
            self._encima = clave
            self.setToolTip(NOMBRES[clave] if clave else "Clic en un eje: mirar desde ese lado")
            self.update()

    def leaveEvent(self, evento) -> None:
        self._encima = None
        self.update()
        super().leaveEvent(evento)

    def mousePressEvent(self, evento) -> None:
        if evento.button() == Qt.LeftButton:
            clave = self.extremo_en(evento.position())
            if clave is not None:
                self.vista_pedida.emit(clave)
        evento.accept()

    def paintEvent(self, _evento) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor(estilo.BORDE), 1))
        p.setBrush(QColor(estilo.PANEL))
        p.drawEllipse(QRectF(0.5, 0.5, LADO - 1, LADO - 1))
        centro = QPointF(LADO / 2, LADO / 2)
        puntas = extremos(self.camara, centro)
        colores = _colores()
        for _prof, clave, q in puntas:
            if clave[0] == "+":
                p.setPen(QPen(QColor(colores[clave[1]]), 2))
                p.drawLine(centro, q)
        f = QFont(self.font().family(), 7)
        f.setBold(True)
        p.setFont(f)
        for _prof, clave, q in puntas:
            color = QColor(colores[clave[1]])
            if clave[0] == "+":
                r = R_POSITIVO
                p.setPen(Qt.NoPen)
                p.setBrush(color)
                p.drawEllipse(q, r, r)
                p.setPen(QColor(estilo.actual.sobre_acento))
                p.drawText(QRectF(q.x() - r, q.y() - r, 2 * r, 2 * r), Qt.AlignCenter, clave[1])
            else:
                r = R_NEGATIVO
                p.setPen(QPen(color, 1.4))
                p.setBrush(QColor(estilo.PANEL))
                p.drawEllipse(q, r, r)
            if clave == self._encima:
                p.setPen(QPen(QColor(estilo.ACENTO), 1.5))
                p.setBrush(Qt.NoBrush)
                p.drawEllipse(q, r + 3.5, r + 3.5)
        p.end()
