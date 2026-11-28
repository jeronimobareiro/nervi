# SPDX-License-Identifier: GPL-3.0-or-later
"""Zoom, paneo y grilla en unidades del modelo para las vistas planas.

Lo comparten la planta del edificio (:class:`~nervi.gui.edificio.PlantaEdificio`) y la
vista 2D del pórtico (:class:`~nervi.gui.vista2d.Vista2D`):

- rueda del mouse: acerca o aleja hacia el cursor;
- botón del medio, o espacio + botón izquierdo, arrastrado: desplaza la vista;
- doble clic con el botón del medio, ``F`` o ``Inicio``: encuadra el modelo;
- ``+`` y ``-``: acercan y alejan hacia el centro.

Mientras no se toca nada, la vista encuadra el modelo sola. Al acercar, alejar o
desplazar queda fija (``Camara.activa``) hasta que se encuadra de nuevo.

Solo cambia cómo se mira el modelo: no lo modifica ni hace cálculos sobre sus
elementos, por eso queda en Python (regla de rendimiento de ``AGENTS.md``).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QToolButton, QWidget

from . import estilo, iconos

#: Factor de zoom de un paso de la rueda (120 unidades de ``angleDelta``).
FACTOR_RUEDA = 1.2
#: Límites del zoom respecto del encuadre automático.
ZOOM_MIN, ZOOM_MAX = 1 / 200, 2000.0
#: Separación mínima en píxeles entre líneas finas de la grilla.
SEPARACION_GRILLA = 14
#: Metros por unidad de longitud del modelo.
METROS = {"mm": 0.001, "cm": 0.01, "m": 1.0}


@dataclass
class Vista:
    """Escala (px por unidad del modelo) y punto del modelo en el centro del lienzo."""

    escala: float
    cx: float
    cy: float


@dataclass(frozen=True)
class Transformacion:
    """Paso de coordenadas del modelo a la pantalla y al revés (y hacia arriba)."""

    escala: float
    ox: float
    oy: float

    @classmethod
    def de(cls, v: Vista, centro: QPointF) -> Transformacion:
        return cls(v.escala, centro.x() - v.cx * v.escala, centro.y() + v.cy * v.escala)

    def a_pantalla(self, x: float, y: float) -> QPointF:
        return QPointF(self.ox + x * self.escala, self.oy - y * self.escala)

    def a_modelo(self, p: QPointF) -> tuple[float, float]:
        return ((p.x() - self.ox) / self.escala, (self.oy - p.y()) / self.escala)


class Camara:
    """Zoom y paneo de una vista plana. Sin tocar, sigue al encuadre automático."""

    def __init__(self) -> None:
        self.vista: Vista | None = None

    @property
    def activa(self) -> bool:
        return self.vista is not None

    def resolver(self, ajuste: Vista) -> Vista:
        """La vista a usar: la propia si se navegó, o el encuadre automático."""
        return self.vista if self.vista is not None else ajuste

    def encuadrar(self) -> None:
        self.vista = None

    def acercar(self, factor: float, cursor: QPointF, centro: QPointF, ajuste: Vista) -> None:
        """Multiplica la escala por ``factor`` dejando fijo el punto bajo ``cursor``.

        ``centro`` es el centro del lienzo en píxeles, donde cae ``(cx, cy)``.
        """
        v = self.resolver(ajuste)
        escala = min(max(v.escala * factor, ajuste.escala * ZOOM_MIN), ajuste.escala * ZOOM_MAX)
        # Punto del modelo bajo el cursor antes y después: tiene que ser el mismo.
        x = v.cx + (cursor.x() - centro.x()) / v.escala
        y = v.cy - (cursor.y() - centro.y()) / v.escala
        self.vista = Vista(
            escala,
            x - (cursor.x() - centro.x()) / escala,
            y + (cursor.y() - centro.y()) / escala,
        )

    def desplazar(self, dx: float, dy: float, ajuste: Vista) -> None:
        """Mueve la vista ``dx``, ``dy`` píxeles (el modelo sigue al mouse)."""
        v = self.resolver(ajuste)
        self.vista = Vista(v.escala, v.cx - dx / v.escala, v.cy + dy / v.escala)


def paso_grilla(escala: float, minimo: float = SEPARACION_GRILLA) -> tuple[float, float]:
    """Paso fino y grueso de la grilla (en unidades del modelo) para una escala en px.

    El paso fino es el menor de la serie 1-2-5 que deja ``minimo`` píxeles entre
    líneas; el grueso es 5 veces el fino si empieza en 1, si no 10 veces la década.
    """
    crudo = minimo / escala
    decada = 10.0 ** math.floor(math.log10(crudo))
    for m in (1, 2, 5, 10):
        if m * decada >= crudo * (1 - 1e-12):
            break
    fino = m * decada
    if m == 10:
        m, decada = 1, decada * 10
    grueso = {1: 5, 2: 10, 5: 10}[m] * decada
    return fino, grueso


def dibujar_grilla(p: QPainter, rect: QRectF, v: Vista, centro: QPointF) -> None:
    """Grilla fina y gruesa en unidades del modelo, alineada con su origen."""
    fino, grueso = paso_grilla(v.escala)
    x0 = v.cx + (rect.left() - centro.x()) / v.escala
    x1 = v.cx + (rect.right() - centro.x()) / v.escala
    y0 = v.cy - (rect.bottom() - centro.y()) / v.escala
    y1 = v.cy - (rect.top() - centro.y()) / v.escala
    lapices = (QPen(QColor(estilo.HOVER), 1), QPen(QColor(estilo.BORDE), 1))
    razon = round(grueso / fino)
    for k in range(math.floor(x0 / fino), math.ceil(x1 / fino) + 1):
        px = centro.x() + (k * fino - v.cx) * v.escala
        p.setPen(lapices[k % razon == 0])
        p.drawLine(QPointF(px, rect.top()), QPointF(px, rect.bottom()))
    for k in range(math.floor(y0 / fino), math.ceil(y1 / fino) + 1):
        py = centro.y() - (k * fino - v.cy) * v.escala
        p.setPen(lapices[k % razon == 0])
        p.drawLine(QPointF(rect.left(), py), QPointF(rect.right(), py))


def escala_papel(v: Vista, unidad: str, dpi: float) -> int | None:
    """Denominador ``N`` de la escala 1:N en pantalla, o ``None`` si no se sabe."""
    if unidad not in METROS or dpi <= 0:
        return None
    px_por_metro = v.escala / METROS[unidad]
    n = (dpi / 0.0254) / px_por_metro
    if n >= 10:
        return int(round(n, -math.floor(math.log10(n)) + 1))
    return max(1, round(n))


def _num(valor: float) -> str:
    return f"{valor:.2f}".replace("-", "−")


def dibujar_coordenadas(
    p: QPainter, lienzo: QWidget, v: Vista, centro: QPointF, cursor: QPointF | None, unidad: str
) -> None:
    """Cuadro abajo a la derecha con las coordenadas del cursor y la escala."""
    partes = []
    if cursor is not None:
        x = v.cx + (cursor.x() - centro.x()) / v.escala
        y = v.cy - (cursor.y() - centro.y()) / v.escala
        partes.append(f"x {_num(x)}   y {_num(y)} {unidad}")
    n = escala_papel(v, unidad, lienzo.logicalDpiX())
    if n is not None:
        partes.append(f"1:{n}")
    if not partes:
        return
    texto = "   ·   ".join(partes)
    p.setFont(QFont(lienzo.font().family(), 8))
    ancho = p.fontMetrics().horizontalAdvance(texto) + 24
    caja = QRectF(lienzo.width() - ancho - 12, lienzo.height() - 36, ancho, 24)
    p.setPen(QPen(QColor(estilo.BORDE), 1))
    p.setBrush(QColor(estilo.PANEL))
    p.drawRoundedRect(caja, 4, 4)
    p.setPen(QColor(estilo.TEXTO_2))
    p.drawText(caja, Qt.AlignCenter, texto)


class BotonesNavegacion(QWidget):
    """Acercar, alejar y encuadrar, arriba a la derecha del lienzo."""

    #: Íconos del catálogo que usan los botones.
    CLAVES = ("acercar", "alejar", "encuadrar")

    def __init__(self, lienzo: Navegable) -> None:
        super().__init__(lienzo)
        self.lienzo = lienzo
        capa = QHBoxLayout(self)
        capa.setContentsMargins(0, 0, 0, 0)
        grupo = QWidget(objectName="grupo")
        g = QHBoxLayout(grupo)
        g.setContentsMargins(2, 2, 2, 2)
        g.setSpacing(2)
        self.botones: dict[str, QToolButton] = {}
        for clave, ayuda, funcion in (
            ("acercar", "Acercar (rueda del mouse o +)", lambda: lienzo.zoom(FACTOR_RUEDA)),
            ("alejar", "Alejar (rueda del mouse o -)", lambda: lienzo.zoom(1 / FACTOR_RUEDA)),
            ("encuadrar", "Encuadrar el modelo (F)", lienzo.encuadrar),
        ):
            b = QToolButton(objectName="segmento")
            b.setToolTip(ayuda)
            b.setAccessibleName(ayuda.split(" (")[0])
            b.setIconSize(QSize(16, 16))
            b.setFocusPolicy(Qt.NoFocus)
            b.clicked.connect(funcion)
            g.addWidget(b)
            self.botones[clave] = b
        capa.addWidget(grupo)
        self.actualizar_iconos()

    def actualizar_iconos(self) -> None:
        for clave, b in self.botones.items():
            b.setIcon(iconos.qicon(clave, estilo.actual, 16, self.devicePixelRatioF()))

    def acomodar(self) -> None:
        self.adjustSize()
        self.move(self.lienzo.width() - self.width() - 12, 12)


class Navegable:
    """Mezcla para un ``QWidget`` que dibuja el modelo en planta.

    La clase que la usa implementa :meth:`ajuste` (el encuadre automático, o ``None``
    si no hay nada que mostrar) y :meth:`centro_lienzo`, y llama a
    :meth:`iniciar_navegacion` en su ``__init__``. Los eventos del mouse que no son de
    navegación los maneja la clase con ``evento_navegacion`` primero.
    """

    def iniciar_navegacion(self) -> None:
        self.camara = Camara()
        self._arrastre: QPointF | None = None
        self._espacio = False
        self.cursor_lienzo: QPointF | None = None
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.ClickFocus)
        self.botones_navegacion = BotonesNavegacion(self)

    # -- a implementar ------------------------------------------------------------
    def ajuste(self) -> Vista | None:  # pragma: no cover - lo implementa la clase
        raise NotImplementedError

    def centro_lienzo(self) -> QPointF:
        return QPointF(self.width() / 2, self.height() / 2)

    # -- vista ----------------------------------------------------------------------
    def vista_actual(self) -> Vista | None:
        ajuste = self.ajuste()
        return None if ajuste is None else self.camara.resolver(ajuste)

    def transformacion(self) -> Transformacion | None:
        """La transformación de la vista actual, o ``None`` si no hay nada que ver."""
        v = self.vista_actual()
        return None if v is None else Transformacion.de(v, self.centro_lienzo())

    def zoom(self, factor: float, cursor: QPointF | None = None) -> None:
        ajuste = self.ajuste()
        if ajuste is None:
            return
        centro = self.centro_lienzo()
        self.camara.acercar(factor, centro if cursor is None else cursor, centro, ajuste)
        self.update()

    def encuadrar(self) -> None:
        self.camara.encuadrar()
        self.update()

    # -- eventos (la clase los llama desde los suyos) ---------------------------------
    def resizeEvent(self, evento) -> None:
        self.botones_navegacion.acomodar()
        super().resizeEvent(evento)

    def wheelEvent(self, evento) -> None:
        pasos = evento.angleDelta().y() / 120
        if pasos:
            self.zoom(FACTOR_RUEDA**pasos, evento.position())
        evento.accept()

    def keyPressEvent(self, evento) -> None:
        tecla = evento.key()
        if tecla in (Qt.Key_F, Qt.Key_Home) and not evento.modifiers():
            self.encuadrar()
        elif tecla in (Qt.Key_Plus, Qt.Key_Equal):
            self.zoom(FACTOR_RUEDA)
        elif tecla == Qt.Key_Minus:
            self.zoom(1 / FACTOR_RUEDA)
        elif tecla == Qt.Key_Space and not evento.isAutoRepeat():
            self._espacio = True
            self.setCursor(Qt.OpenHandCursor)
        else:
            super().keyPressEvent(evento)
            return
        evento.accept()

    def keyReleaseEvent(self, evento) -> None:
        if evento.key() == Qt.Key_Space and not evento.isAutoRepeat():
            self._espacio = False
            self._arrastre = None
            self.unsetCursor()
            evento.accept()
            return
        super().keyReleaseEvent(evento)

    def navegacion_presionar(self, evento) -> bool:
        """Empieza un paneo si corresponde. Devuelve ``True`` si se usó el evento."""
        boton = evento.button()
        if boton == Qt.MiddleButton or (boton == Qt.LeftButton and self._espacio):
            self._arrastre = evento.position()
            self.setCursor(Qt.ClosedHandCursor)
            return True
        return False

    def navegacion_mover(self, evento) -> bool:
        self.cursor_lienzo = evento.position()
        if self._arrastre is None:
            return False
        ajuste = self.ajuste()
        if ajuste is not None:
            d = evento.position() - self._arrastre
            self.camara.desplazar(d.x(), d.y(), ajuste)
        self._arrastre = evento.position()
        self.update()
        return True

    def navegacion_soltar(self, evento) -> bool:
        if self._arrastre is None:
            return False
        self._arrastre = None
        if self._espacio:
            self.setCursor(Qt.OpenHandCursor)
        else:
            self.unsetCursor()
        return True

    def mouseDoubleClickEvent(self, evento) -> None:
        if evento.button() == Qt.MiddleButton:
            self.encuadrar()
            evento.accept()
            return
        super().mouseDoubleClickEvent(evento)

    def leaveEvent(self, evento) -> None:
        self.cursor_lienzo = None
        self.update()
        super().leaveEvent(evento)
