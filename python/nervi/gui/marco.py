# SPDX-License-Identifier: GPL-3.0-or-later
"""Barra de título propia de la ventana principal.

La barra de título que dibuja el sistema operativo (el gestor de ventanas de Windows,
o KWin, Mutter y los demás en Linux) no sigue los temas de :mod:`nervi.gui.estilo`.
Con la barra propia, la fila superior de Nervi (logo, nombre del archivo, etapas,
Buscar, Calcular) pasa a ser la barra de título y lleva al final *Minimizar*,
*Maximizar* y *Cerrar*. Se conserva lo que hace el sistema:

- arrastrar la ventana desde cualquier parte vacía de la fila y doble clic para
  maximizar o restaurar;
- redimensionar desde los bordes;
- en Windows, Snap (llevar la ventana a un borde, Win + flechas, el menú de
  distribuciones al pasar por *Maximizar* en Windows 11), la sombra y las esquinas
  redondeadas, porque la ventana sigue siendo una ventana con marco para el sistema:
  solo se le quita el área que dibujaba él (``WM_NCCALCSIZE``) y se le dice qué parte
  es la barra y qué parte los bordes (``WM_NCHITTEST``);
- en Linux (X11 y Wayland), el arrastre y el redimensionado los hace el propio gestor
  de ventanas con ``QWindow.startSystemMove`` y ``startSystemResize``.

La preferencia *Apariencia › Barra de título* vuelve a la del sistema, por si algún
escritorio se porta mal. Todo en Python con Qt y ``ctypes``, sin C++.
Ver ``docs/diseno-interfaz.md`` §Barra de título.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from PySide6.QtCore import QEvent, QObject, QPoint, QRect, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QToolButton, QWidget

from . import ajustes, estilo, iconos

if TYPE_CHECKING:
    from PySide6.QtWidgets import QMainWindow

CLAVE = "interfaz/barra_titulo"
#: Ancho y alto de cada botón de la ventana, en píxeles.
ANCHO_BOTON = 46
ALTO_BARRA = 40
#: Franja de los bordes desde la que se redimensiona, en píxeles.
BORDE = 5
#: Lado del dibujo de los botones de la ventana.
LADO_ICONO = 16

WINDOWS = sys.platform == "win32"


def usar_propia() -> bool:
    """True si la persona eligió la barra de título de Nervi (la de por defecto)."""
    return ajustes.leer(CLAVE) == "propia"


class BotonesVentana(QWidget):
    """*Minimizar*, *Maximizar* (o *Restaurar*) y *Cerrar*, con el estilo del tema."""

    def __init__(self, ventana: QMainWindow) -> None:
        super().__init__(objectName="botones_ventana")
        self.ventana = ventana
        capa = QHBoxLayout(self)
        capa.setContentsMargins(0, 0, 0, 0)
        capa.setSpacing(0)
        self.b_minimizar = self._boton("Minimizar", ventana.showMinimized)
        self.b_maximizar = self._boton("Maximizar", self.alternar_maximizada)
        self.b_cerrar = self._boton("Cerrar", ventana.close, "boton_cerrar_ventana")
        for b in (self.b_minimizar, self.b_maximizar, self.b_cerrar):
            capa.addWidget(b)
        ventana.installEventFilter(self)
        self.actualizar_iconos()

    def _boton(self, ayuda: str, funcion, nombre: str = "boton_ventana") -> QToolButton:
        b = QToolButton(objectName=nombre)
        b.setToolTip(ayuda)
        b.setAccessibleName(ayuda)
        b.setFixedSize(ANCHO_BOTON, ALTO_BARRA)
        b.setIconSize(QSize(LADO_ICONO, LADO_ICONO))
        b.setFocusPolicy(Qt.NoFocus)
        b.setAutoRaise(True)
        b.clicked.connect(funcion)
        return b

    def alternar_maximizada(self) -> None:
        v = self.ventana
        v.showNormal() if v.isMaximized() else v.showMaximized()

    def actualizar_iconos(self) -> None:
        t = estilo.actual
        escala = self.devicePixelRatioF()
        maximizada = self.ventana.isMaximized()
        self.b_minimizar.setIcon(iconos.qicon("minimizar", t, LADO_ICONO, escala))
        self.b_maximizar.setIcon(
            iconos.qicon("restaurar" if maximizada else "maximizar", t, LADO_ICONO, escala)
        )
        texto = "Restaurar" if maximizada else "Maximizar"
        self.b_maximizar.setToolTip(texto)
        self.b_maximizar.setAccessibleName(texto)
        # Cerrar: con el cursor encima va en blanco sobre el rojo de cerrar.
        cerrar = iconos.qicon("cerrar", t, LADO_ICONO, escala)
        blanco = iconos.pixmap("cerrar", t.sobre_cerrar_ventana, LADO_ICONO, escala)
        cerrar.addPixmap(blanco, QIcon.Active, QIcon.Off)
        self.b_cerrar.setIcon(cerrar)

    def marcar_encima(self, boton: QToolButton | None) -> None:
        """Marca el botón que tiene el cursor cuando Windows se queda con los eventos del
        mouse (el de *Maximizar*, para el menú de Snap de Windows 11)."""
        for b in (self.b_minimizar, self.b_maximizar, self.b_cerrar):
            valor = b is boton
            if b.property("encima") != valor:
                b.setProperty("encima", valor)
                b.style().unpolish(b)
                b.style().polish(b)

    def eventFilter(self, objeto: QObject, evento: QEvent) -> bool:
        if objeto is self.ventana and evento.type() == QEvent.WindowStateChange:
            self.actualizar_iconos()
        return False


def separador() -> QFrame:
    """Línea vertical que separa Calcular de los botones de la ventana."""
    linea = QFrame(objectName="separador_ventana")
    linea.setFixedSize(1, 20)
    return linea


class Marco(QObject):
    """Quita la barra del sistema y le da a ``barra`` el papel de barra de título."""

    def __init__(
        self, ventana: QMainWindow, barra: QWidget, botones: BotonesVentana, *arrastre: QWidget
    ) -> None:
        super().__init__(ventana)
        self.ventana = ventana
        self.barra = barra
        self.botones = botones
        #: Widgets que, en sus partes vacías, arrastran la ventana.
        self.arrastre = (barra, *arrastre)
        self._presion: QPoint | None = None
        ventana.setWindowFlag(Qt.FramelessWindowHint, True)
        for w in self.arrastre:
            w.installEventFilter(self)
        if WINDOWS:
            self._nativo = _Windows(self)
        else:
            self._nativo = None
            # En Linux la franja de los bordes es un margen de la propia ventana, para
            # que reciba el movimiento del mouse aunque los paneles lleguen al borde.
            ventana.setMouseTracking(True)
            ventana.installEventFilter(self)
            self._margenes()

    # --- Qué parte de la ventana es qué ---------------------------------------------
    def es_barra(self, global_: QPoint) -> bool:
        """True si en ``global_`` hay una parte vacía de la barra (arrastra la ventana)."""
        v = self.ventana
        w = QApplication.widgetAt(global_)
        if w is None or w.window() is not v:
            return False
        while w is not None and w is not v:
            if w in self.arrastre:
                return True
            # Las etiquetas (nombre del archivo, separadores de etapas) no usan el
            # mouse: también arrastran. Cualquier otro control se queda con el clic.
            if w.metaObject().className() not in ("QLabel", "QFrame"):
                return False
            w = w.parentWidget()
        return False

    def borde(self, local: QPoint) -> Qt.Edge:
        """Bordes de la ventana cerca de ``local`` (coordenadas de la ventana)."""
        v = self.ventana
        if v.isMaximized() or v.isFullScreen():
            return Qt.Edge(0)
        bordes = Qt.Edge(0)
        if local.x() < BORDE:
            bordes |= Qt.LeftEdge
        elif local.x() >= v.width() - BORDE:
            bordes |= Qt.RightEdge
        if local.y() < BORDE:
            bordes |= Qt.TopEdge
        elif local.y() >= v.height() - BORDE:
            bordes |= Qt.BottomEdge
        return bordes

    # --- Linux (y Windows para el doble clic) ------------------------------------------
    def _margenes(self) -> None:
        m = 0 if self.ventana.isMaximized() or self.ventana.isFullScreen() else BORDE
        self.ventana.setContentsMargins(m, m, m, m)

    def eventFilter(self, objeto: QObject, evento: QEvent) -> bool:
        tipo = evento.type()
        if objeto is self.ventana:
            if tipo == QEvent.WindowStateChange:
                self._margenes()
            elif tipo == QEvent.MouseMove and not evento.buttons():
                self.ventana.setCursor(_CURSORES.get(self._clave(evento), Qt.ArrowCursor))
            elif tipo == QEvent.MouseButtonPress and evento.button() == Qt.LeftButton:
                bordes = self.borde(evento.position().toPoint())
                if bordes and self.ventana.windowHandle().startSystemResize(bordes):
                    return True
            return False
        if objeto in self.arrastre:
            if tipo == QEvent.MouseButtonDblClick and evento.button() == Qt.LeftButton:
                self.botones.alternar_maximizada()
                return True
            if self._nativo is not None:
                # En Windows el arrastre lo hace el sistema (la barra es HTCAPTION).
                return False
            if tipo == QEvent.MouseButtonPress and evento.button() == Qt.LeftButton:
                self._presion = evento.globalPosition().toPoint()
                return True
            if tipo == QEvent.MouseMove and self._presion is not None:
                distancia = (evento.globalPosition().toPoint() - self._presion).manhattanLength()
                if distancia >= QApplication.startDragDistance():
                    self._presion = None
                    self.ventana.windowHandle().startSystemMove()
                return True
            if tipo == QEvent.MouseButtonRelease:
                self._presion = None
        return False

    def _clave(self, evento) -> int:
        b = self.borde(evento.position().toPoint())
        return int(b.value) if hasattr(b, "value") else int(b)

    def pintar_borde(self, ventana: QWidget) -> None:
        """Línea de 1 px alrededor de la ventana sin marco (en Windows la pone el
        sistema)."""
        if self._nativo is not None or ventana.isMaximized() or ventana.isFullScreen():
            return
        p = QPainter(ventana)
        p.setPen(QPen(QColor(estilo.actual.borde_fuerte), 1))
        p.drawRect(QRect(0, 0, ventana.width() - 1, ventana.height() - 1))
        p.end()

    def evento_nativo(self, tipo, mensaje) -> tuple[bool, int] | None:
        """Mensajes de Windows; ``None`` deja que Qt los atienda como siempre."""
        if self._nativo is None:
            return None
        return self._nativo.evento(tipo, mensaje)


def _cursores() -> dict[int, Qt.CursorShape]:
    def k(b) -> int:
        return int(b.value) if hasattr(b, "value") else int(b)

    L, R, T, B = Qt.LeftEdge, Qt.RightEdge, Qt.TopEdge, Qt.BottomEdge
    return {
        k(L): Qt.SizeHorCursor,
        k(R): Qt.SizeHorCursor,
        k(T): Qt.SizeVerCursor,
        k(B): Qt.SizeVerCursor,
        k(L | T): Qt.SizeFDiagCursor,
        k(R | B): Qt.SizeFDiagCursor,
        k(R | T): Qt.SizeBDiagCursor,
        k(L | B): Qt.SizeBDiagCursor,
    }


_CURSORES = _cursores()


# --- Windows --------------------------------------------------------------------------
WM_NCCALCSIZE = 0x0083
WM_NCHITTEST = 0x0084
WM_NCMOUSEMOVE = 0x00A0
WM_NCLBUTTONDOWN = 0x00A1
WM_NCLBUTTONUP = 0x00A2
WM_NCLBUTTONDBLCLK = 0x00A3
WM_NCMOUSELEAVE = 0x02A2
WM_MOUSEMOVE = 0x0200
HTCLIENT, HTCAPTION, HTMAXBUTTON = 1, 2, 9
HTLEFT, HTRIGHT, HTTOP, HTTOPLEFT, HTTOPRIGHT = 10, 11, 12, 13, 14
HTBOTTOM, HTBOTTOMLEFT, HTBOTTOMRIGHT = 15, 16, 17
GWL_STYLE = -16
WS_CAPTION, WS_THICKFRAME, WS_SYSMENU = 0x00C00000, 0x00040000, 0x00080000
WS_MINIMIZEBOX, WS_MAXIMIZEBOX = 0x00020000, 0x00010000
SWP_FRAMECHANGED, SWP_NOMOVE, SWP_NOSIZE, SWP_NOZORDER = 0x20, 0x2, 0x1, 0x4
SM_CXSIZEFRAME, SM_CYSIZEFRAME, SM_CXPADDEDBORDER = 32, 33, 92


class _Windows:
    """Barra propia en Windows conservando lo que hace el sistema con una ventana con
    marco: la ventana mantiene ``WS_CAPTION | WS_THICKFRAME``, pero su área de cliente
    ocupa toda la ventana y el sistema pregunta a Nervi qué es barra y qué es borde."""

    def __init__(self, marco: Marco) -> None:
        import ctypes
        from ctypes import wintypes

        self.ct = ctypes
        self.wt = wintypes
        self.marco = marco
        self.user32 = ctypes.windll.user32
        self.dwm = ctypes.windll.dwmapi
        self._hwnd = 0

    def _preparar(self) -> int:
        """Devuelve el HWND y, la primera vez, le devuelve a la ventana sin marco de Qt el
        estilo de una ventana con marco (Snap, animaciones, sombra)."""
        hwnd = int(self.marco.ventana.winId())
        if hwnd != self._hwnd:
            self._hwnd = hwnd
            u = self.user32
            u.GetWindowLongPtrW.restype = self.ct.c_ssize_t
            u.SetWindowLongPtrW.argtypes = [self.wt.HWND, self.ct.c_int, self.ct.c_ssize_t]
            estilo_ = u.GetWindowLongPtrW(self.wt.HWND(hwnd), GWL_STYLE)
            estilo_ |= WS_CAPTION | WS_THICKFRAME | WS_SYSMENU | WS_MINIMIZEBOX | WS_MAXIMIZEBOX
            u.SetWindowLongPtrW(self.wt.HWND(hwnd), GWL_STYLE, estilo_)

            ctypes = self.ct

            class MARGINS(ctypes.Structure):
                _fields_ = (
                    ("l", ctypes.c_int),
                    ("r", ctypes.c_int),
                    ("t", ctypes.c_int),
                    ("b", ctypes.c_int),
                )

            # Un píxel de marco "dentro" del cliente basta para que DWM dibuje la sombra.
            self.dwm.DwmExtendFrameIntoClientArea(
                self.wt.HWND(hwnd), self.ct.byref(MARGINS(0, 0, 1, 0))
            )
            u.SetWindowPos(
                self.wt.HWND(hwnd),
                None,
                0,
                0,
                0,
                0,
                SWP_FRAMECHANGED | SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER,
            )
        return hwnd

    def _marco_sistema(self, hwnd) -> int:
        """Ancho del marco que Windows deja fuera de la pantalla al maximizar."""
        u = self.user32
        try:
            dpi = u.GetDpiForWindow(self.wt.HWND(hwnd))
            f = u.GetSystemMetricsForDpi
            return f(SM_CXSIZEFRAME, dpi) + f(SM_CXPADDEDBORDER, dpi)
        except AttributeError:  # Windows anterior a 10 (1607)
            return u.GetSystemMetrics(SM_CXSIZEFRAME) + u.GetSystemMetrics(SM_CXPADDEDBORDER)

    def evento(self, tipo, mensaje) -> tuple[bool, int] | None:
        if bytes(tipo) != b"windows_generic_MSG":
            return None
        msg = self.wt.MSG.from_address(int(mensaje))
        m = msg.message
        if m == WM_NCCALCSIZE:
            hwnd = self._preparar()
            if msg.wParam and self.marco.ventana.isMaximized():
                # Maximizada, Windows deja el marco fuera de la pantalla: se lo recorta
                # para que no se pierdan la barra ni los bordes de los paneles.
                rect = self.wt.RECT.from_address(msg.lParam)
                f = self._marco_sistema(hwnd)
                rect.left += f
                rect.top += f
                rect.right -= f
                rect.bottom -= f
            return True, 0
        if m == WM_NCHITTEST:
            return True, self._zona(msg.lParam)
        if m in (WM_NCMOUSEMOVE, WM_NCLBUTTONDOWN, WM_NCLBUTTONUP, WM_NCLBUTTONDBLCLK):
            b = self.marco.botones
            if msg.wParam == HTMAXBUTTON:
                b.marcar_encima(b.b_maximizar)
                if m == WM_NCLBUTTONUP:
                    b.marcar_encima(None)
                    b.alternar_maximizada()
                if m != WM_NCMOUSEMOVE:
                    return True, 0
            else:
                b.marcar_encima(None)
        elif m in (WM_NCMOUSELEAVE, WM_MOUSEMOVE):
            self.marco.botones.marcar_encima(None)
        return None

    def _zona(self, lparam: int) -> int:
        """Qué hay bajo el cursor (``WM_NCHITTEST``); ``lparam`` trae coordenadas físicas."""
        punto = self.wt.POINT(
            self.ct.c_short(lparam & 0xFFFF).value, self.ct.c_short((lparam >> 16) & 0xFFFF).value
        )
        # A coordenadas del cliente (que ocupa toda la ventana) y de ahí a las lógicas
        # de Qt, sin depender de la escala de las otras pantallas.
        self.user32.ScreenToClient(self.wt.HWND(self._preparar()), self.ct.byref(punto))
        v = self.marco.ventana
        escala = v.devicePixelRatioF()
        local = QPoint(round(punto.x / escala), round(punto.y / escala))
        global_ = v.mapToGlobal(local)
        bordes = self.marco.borde(local)
        if bordes:
            return _ZONAS_BORDE[_k(bordes)]
        b = self.marco.botones
        maximizar = b.b_maximizar
        if maximizar.isVisible() and maximizar.rect().contains(maximizar.mapFromGlobal(global_)):
            return HTMAXBUTTON
        if self.marco.es_barra(global_):
            return HTCAPTION
        return HTCLIENT


def _k(b) -> int:
    return int(b.value) if hasattr(b, "value") else int(b)


_ZONAS_BORDE = {
    _k(Qt.LeftEdge): HTLEFT,
    _k(Qt.RightEdge): HTRIGHT,
    _k(Qt.TopEdge): HTTOP,
    _k(Qt.BottomEdge): HTBOTTOM,
    _k(Qt.LeftEdge | Qt.TopEdge): HTTOPLEFT,
    _k(Qt.RightEdge | Qt.TopEdge): HTTOPRIGHT,
    _k(Qt.LeftEdge | Qt.BottomEdge): HTBOTTOMLEFT,
    _k(Qt.RightEdge | Qt.BottomEdge): HTBOTTOMRIGHT,
}
