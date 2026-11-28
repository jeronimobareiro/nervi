# SPDX-License-Identifier: GPL-3.0-or-later
"""Paneles acoplables de la ventana y distribuciones guardadas.

Cada panel (Estructura, Propiedades, Tablas y resultados, Asistente de IA) es un
``QDockWidget``: se acopla a cualquier borde, se apila en pestañas con otro, se
desacopla a una ventana propia (que puede ir a otro monitor) y se cierra; *Ver ›
Paneles* los vuelve a abrir. La distribución se guarda al cerrar y se recupera al
abrir; además se pueden guardar distribuciones con nombre y volver a la de fábrica.

Todo con Qt (PySide6), sin bibliotecas de acople en C++.
"""

from __future__ import annotations

from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtWidgets import (
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QToolButton,
    QWidget,
)

from . import ajustes, estilo, iconos

#: Versión de la distribución guardada: si cambian los paneles, las viejas no se usan.
VERSION = 1
CLAVE_GEOMETRIA = "ventana/geometria"
CLAVE_ESTADO = "ventana/estado"
GRUPO_DISTRIBUCIONES = "distribuciones"


class TituloPanel(QWidget):
    """Barra de título de un panel: su nombre, *Desacoplar* y *Cerrar*. Se arrastra
    para moverlo y doble clic lo desacopla o lo vuelve a acoplar."""

    def __init__(self, dock: QDockWidget) -> None:
        super().__init__(dock, objectName="titulo_panel")
        self.setAttribute(Qt.WA_StyledBackground)
        self.dock = dock
        capa = QHBoxLayout(self)
        capa.setContentsMargins(12, 6, 6, 4)
        capa.setSpacing(2)
        self.etiqueta = QLabel(dock.windowTitle(), objectName="titulo_arbol")
        capa.addWidget(self.etiqueta, 1)
        self.b_flotar = QToolButton(objectName="boton_panel")
        self.b_cerrar = QToolButton(objectName="boton_panel")
        for b, ayuda in ((self.b_flotar, "Desacoplar"), (self.b_cerrar, "Cerrar")):
            b.setToolTip(ayuda)
            b.setAccessibleName(ayuda)
            b.setIconSize(QSize(14, 14))
            b.setFocusPolicy(Qt.NoFocus)
            capa.addWidget(b)
        self.b_flotar.clicked.connect(lambda: dock.setFloating(not dock.isFloating()))
        self.b_cerrar.clicked.connect(dock.close)
        dock.windowTitleChanged.connect(self.etiqueta.setText)
        dock.topLevelChanged.connect(self._flotando)
        self.actualizar_iconos()

    def _flotando(self, flotando: bool) -> None:
        texto = "Acoplar" if flotando else "Desacoplar"
        self.b_flotar.setToolTip(texto)
        self.b_flotar.setAccessibleName(texto)

    def actualizar_iconos(self) -> None:
        dpr = self.devicePixelRatioF()
        self.b_flotar.setIcon(iconos.qicon("desacoplar", estilo.actual, 14, dpr))
        self.b_cerrar.setIcon(iconos.qicon("cerrar", estilo.actual, 14, dpr))

    def mouseDoubleClickEvent(self, evento) -> None:
        if evento.button() == Qt.LeftButton:
            self.dock.setFloating(not self.dock.isFloating())
            evento.accept()
            return
        super().mouseDoubleClickEvent(evento)


def crear_panel(ventana: QMainWindow, clave: str, titulo: str, widget: QWidget) -> QDockWidget:
    """Un panel acoplable con ``widget`` adentro. ``clave`` es su nombre en la
    distribución guardada (no se cambia)."""
    dock = QDockWidget(titulo, ventana, objectName=f"panel_{clave}")
    dock.setWidget(widget)
    dock.setFeatures(
        QDockWidget.DockWidgetClosable
        | QDockWidget.DockWidgetMovable
        | QDockWidget.DockWidgetFloatable
    )
    dock.setTitleBarWidget(TituloPanel(dock))
    dock.toggleViewAction().setText(titulo)
    return dock


def _bytes(valor) -> QByteArray | None:
    if isinstance(valor, QByteArray) and not valor.isEmpty():
        return valor
    if isinstance(valor, bytes | bytearray) and valor:
        return QByteArray(bytes(valor))
    return None


def guardar_al_cerrar(ventana: QMainWindow) -> None:
    """Guarda el tamaño, la posición y la distribución de la ventana."""
    cfg = ajustes.configuracion()
    cfg.setValue(CLAVE_GEOMETRIA, ventana.saveGeometry())
    cfg.setValue(CLAVE_ESTADO, ventana.saveState(VERSION))


def recuperar(ventana: QMainWindow) -> bool:
    """Vuelve a la ventana y la distribución de la última vez. ``False`` si no había."""
    cfg = ajustes.configuracion()
    geometria = _bytes(cfg.value(CLAVE_GEOMETRIA))
    estado = _bytes(cfg.value(CLAVE_ESTADO))
    if geometria is not None:
        ventana.restoreGeometry(geometria)
    return estado is not None and ventana.restoreState(estado, VERSION)


def distribuciones() -> list[str]:
    """Nombres de las distribuciones guardadas, en orden alfabético."""
    cfg = ajustes.configuracion()
    cfg.beginGroup(GRUPO_DISTRIBUCIONES)
    nombres = sorted(cfg.childKeys(), key=str.casefold)
    cfg.endGroup()
    return nombres


def _clave(nombre: str) -> str:
    nombre = nombre.strip().replace("/", "-").replace("\\", "-")
    if not nombre:
        raise ValueError("La distribución necesita un nombre")
    return f"{GRUPO_DISTRIBUCIONES}/{nombre}"


def guardar_distribucion(ventana: QMainWindow, nombre: str) -> str:
    """Guarda la distribución actual con ``nombre`` (la reemplaza si ya existe)."""
    clave = _clave(nombre)
    ajustes.configuracion().setValue(clave, ventana.saveState(VERSION))
    return clave.split("/", 1)[1]


def aplicar_distribucion(ventana: QMainWindow, nombre: str) -> bool:
    estado = _bytes(ajustes.configuracion().value(_clave(nombre)))
    return estado is not None and ventana.restoreState(estado, VERSION)


def borrar_distribucion(nombre: str) -> None:
    ajustes.configuracion().remove(_clave(nombre))
