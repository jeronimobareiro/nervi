# SPDX-License-Identifier: GPL-3.0-or-later
"""Pestaña *Dinámica*: masas, análisis modal y espectros de respuesta.

El panel no guarda datos propios: lee y escribe ``dinamica.json`` a través de la
sesión (``Sesion.dinamica`` y ``Sesion.editar_dinamica``) y muestra lo que
devuelve ``Sesion.analizar_dinamica`` (``nervi.dinamica_plana``). Cada modo y
cada espectro aparece como un resultado más en el selector de la ventana, así
que las vistas 2D y 3D los dibujan como cualquier caso.
"""

from __future__ import annotations

import copy
import math

import numpy as np
from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .. import MecanismoError, formato
from . import estilo
from .sesion import Sesion

COLUMNAS_MODOS = ("Modo", "T (s)", "f (Hz)", "Mx %", "My %", "ΣMx %", "ΣMy %")


def _tabla(columnas, editable: bool = False) -> QTableWidget:
    t = QTableWidget(0, len(columnas))
    t.setHorizontalHeaderLabels(list(columnas))
    t.verticalHeader().setVisible(False)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    if not editable:
        t.setEditTriggers(QAbstractItemView.NoEditTriggers)
        t.setSelectionMode(QAbstractItemView.SingleSelection)
    return t


def _celda(texto: str, editable: bool = False, derecha: bool = True) -> QTableWidgetItem:
    item = QTableWidgetItem(texto)
    if not editable:
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
    if derecha:
        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
    return item


def _numero(texto: str) -> float:
    return float(texto.strip().replace(",", "."))


class GraficoEspectro(QWidget):
    """Curva ``Sa/g`` del espectro elegido, con los periodos de los modos."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.puntos: list[list[float]] = []
        self.periodos: list[float] = []
        self.setMinimumSize(220, 130)

    def mostrar(self, puntos, periodos) -> None:
        self.puntos = [list(p) for p in puntos]
        self.periodos = [float(t) for t in periodos]
        self.update()

    def paintEvent(self, _evento) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(estilo.PANEL))
        if not self.puntos:
            p.setPen(QColor(estilo.TEXTO_3))
            p.drawText(self.rect(), Qt.AlignCenter, "Sin espectro")
            return
        pts = np.array(self.puntos, dtype=float)
        tmax = max(pts[:, 0].max(), max(self.periodos, default=0.0), 1e-6) * 1.05
        smax = max(pts[:, 1].max(), 1e-9) * 1.1
        izq, abajo, der, arriba = 34, self.height() - 22, self.width() - 10, 10

        def q(t: float, s: float) -> QPointF:
            return QPointF(izq + t / tmax * (der - izq), abajo - s / smax * (abajo - arriba))

        p.setFont(QFont(self.font().family(), 7))
        p.setPen(QPen(QColor(estilo.BORDE), 1))
        p.drawLine(q(0, 0), q(tmax, 0))
        p.drawLine(q(0, 0), q(0, smax))
        p.setPen(QColor(estilo.TEXTO_3))
        p.drawText(q(0, smax) + QPointF(4, 8), "Sa/g")
        p.drawText(q(tmax, 0) + QPointF(-26, 16), "T (s)")
        for v in (0.0, pts[:, 1].max()):
            p.drawText(QPointF(4, q(0, v).y() + 3), f"{v:.2g}")
        p.setPen(QPen(QColor(estilo.TEXTO_3), 1, Qt.DotLine))
        for t in self.periodos:
            sa = float(np.interp(t, pts[:, 0], pts[:, 1]))
            p.drawLine(q(t, 0), q(t, sa))
        camino = QPainterPath(q(*pts[0]))
        for t, s in pts[1:]:
            camino.lineTo(q(t, s))
        camino.lineTo(q(tmax, pts[-1, 1]))
        p.setPen(QPen(QColor(estilo.ACENTO), 1.75))
        p.drawPath(camino)


class PanelDinamica(QWidget):
    """Pestaña "Dinámica" del panel inferior."""

    #: Nombre del resultado (``"Modo 1"`` o un espectro) que se eligió en las tablas.
    resultado_elegido = Signal(str)
    #: Pedido de animar (o dejar de animar) el modo que se ve.
    animar = Signal(bool)

    def __init__(self, sesion: Sesion, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.sesion = sesion
        self._cargando = False
        capa = QHBoxLayout(self)
        capa.setContentsMargins(10, 8, 10, 6)
        partes = QSplitter(Qt.Horizontal)
        capa.addWidget(partes)
        partes.addWidget(self._datos())
        partes.addWidget(self._espectros())
        partes.addWidget(self._resultados())
        partes.setSizes([230, 360, 520])
        sesion.dinamica_cambiada.connect(self.actualizar)
        sesion.modelo_cambiado.connect(self.actualizar)
        self.actualizar()

    # --- Armado ------------------------------------------------------------------------
    def _datos(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 6, 0)
        v.addWidget(QLabel("MASA DESDE LOS CASOS", objectName="seccion"))
        self.t_masas = _tabla(("Caso", "Factor"), editable=True)
        self.t_masas.setToolTip(
            "m = −Fy · factor / g en cada nudo. Por ejemplo D con 1 y L con 0,25."
        )
        self.t_masas.itemChanged.connect(self._masas_editadas)
        v.addWidget(self.t_masas, 1)
        fila = QHBoxLayout()
        fila.addWidget(QLabel("Modos", objectName="tenue"))
        self.n_modos = QSpinBox()
        self.n_modos.setRange(1, formato.dinamica.MAX_MODOS)
        self.n_modos.setKeyboardTracking(False)
        self.n_modos.valueChanged.connect(self._n_modos)
        fila.addWidget(self.n_modos)
        fila.addStretch()
        v.addLayout(fila)
        self.b_analizar = QPushButton("Análisis modal y espectral", objectName="primario")
        self.b_analizar.clicked.connect(self.analizar)
        v.addWidget(self.b_analizar)
        self.lbl_estado = QLabel(objectName="tenue")
        self.lbl_estado.setWordWrap(True)
        v.addWidget(self.lbl_estado)
        return w

    def _espectros(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(6, 0, 6, 0)
        fila = QHBoxLayout()
        fila.addWidget(QLabel("ESPECTROS", objectName="seccion"))
        self.c_espectro = QComboBox()
        self.c_espectro.currentIndexChanged.connect(self._mostrar_espectro)
        fila.addWidget(self.c_espectro, 1)
        self.b_agregar = QPushButton("+")
        self.b_agregar.setToolTip("Agregar un espectro (con una forma de ejemplo para editar)")
        self.b_agregar.clicked.connect(self.agregar_espectro)
        self.b_quitar = QPushButton("−")
        self.b_quitar.setToolTip("Quitar el espectro elegido")
        self.b_quitar.clicked.connect(self.quitar_espectro)
        fila.addWidget(self.b_agregar)
        fila.addWidget(self.b_quitar)
        v.addLayout(fila)
        fila = QHBoxLayout()
        self.e_nombre = QLineEdit()
        self.e_nombre.setPlaceholderText("Nombre")
        self.e_nombre.editingFinished.connect(self._espectro_editado)
        self.c_direccion = QComboBox()
        self.c_direccion.addItems(formato.dinamica.DIRECCIONES)
        self.c_direccion.setToolTip("Dirección de la excitación (X horizontal, Y vertical)")
        self.c_combinacion = QComboBox()
        self.c_combinacion.addItems(formato.dinamica.COMBINACIONES)
        self.c_combinacion.setToolTip("Combinación de las respuestas modales")
        self.s_amort = QDoubleSpinBox()
        self.s_amort.setRange(0.0, 50.0)
        self.s_amort.setDecimals(1)
        self.s_amort.setSuffix(" %")
        self.s_amort.setKeyboardTracking(False)
        self.s_amort.setToolTip("Amortiguamiento, en % del crítico (interviene en CQC)")
        for c in (self.c_direccion, self.c_combinacion):
            c.currentIndexChanged.connect(self._espectro_editado)
        self.s_amort.valueChanged.connect(self._espectro_editado)
        for x in (self.e_nombre, self.c_direccion, self.c_combinacion, self.s_amort):
            fila.addWidget(x)
        v.addLayout(fila)
        abajo = QHBoxLayout()
        self.t_puntos = _tabla(("T (s)", "Sa / g"), editable=True)
        self.t_puntos.setToolTip(
            "Pares T, Sa/g con T creciente. Entre puntos se interpola linealmente y fuera del "
            "rango se toma el extremo. Los valores los da la norma que corresponda."
        )
        self.t_puntos.itemChanged.connect(self._puntos_editados)
        col = QVBoxLayout()
        col.addWidget(self.t_puntos, 1)
        botones = QHBoxLayout()
        b = QPushButton("Agregar punto")
        b.clicked.connect(self._agregar_punto)
        botones.addWidget(b)
        b = QPushButton("Quitar punto")
        b.clicked.connect(self._quitar_punto)
        botones.addWidget(b)
        col.addLayout(botones)
        abajo.addLayout(col, 1)
        self.grafico = GraficoEspectro()
        abajo.addWidget(self.grafico, 1)
        v.addLayout(abajo, 1)
        return w

    def _resultados(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(6, 0, 0, 0)
        fila = QHBoxLayout()
        fila.addWidget(QLabel("MODOS", objectName="seccion"))
        fila.addStretch()
        self.b_animar = QPushButton("Animar modo", checkable=True)
        self.b_animar.setToolTip("Hace oscilar la forma modal en la vista 2D")
        self.b_animar.toggled.connect(self.animar.emit)
        fila.addWidget(self.b_animar)
        v.addLayout(fila)
        self.t_modos = _tabla(COLUMNAS_MODOS)
        self.t_modos.itemSelectionChanged.connect(self._modo_elegido)
        v.addWidget(self.t_modos, 3)
        v.addWidget(QLabel("CORTANTE BASAL POR ESPECTRO", objectName="seccion"))
        self.t_basal = _tabla(("Espectro", "Dirección", "Combinación", "Vx", "Vy"))
        self.t_basal.itemSelectionChanged.connect(self._espectro_elegido)
        v.addWidget(self.t_basal, 1)
        nota = QLabel(
            "Los espectros dan valores absolutos combinados: no se suman a los casos. "
            "Las formas modales se dibujan con su mayor traslación igual a 1.",
            objectName="tenue",
        )
        nota.setWordWrap(True)
        v.addWidget(nota)
        return w

    # --- Lectura de la sesión -----------------------------------------------------------
    def actualizar(self) -> None:
        self._cargando = True
        try:
            d = self.sesion.dinamica
            casos = [c["nombre"] for c in self.sesion.modelo["casos"]]
            factores = d["masas"]["casos"]
            self.t_masas.setRowCount(len(casos))
            for k, nombre in enumerate(casos):
                self.t_masas.setItem(k, 0, _celda(nombre, derecha=False))
                f = factores.get(nombre, 0.0)
                self.t_masas.setItem(k, 1, _celda(f"{f:g}" if f else "", editable=True))
            self.n_modos.setValue(d["n_modos"])
            actual = self.c_espectro.currentIndex()
            self.c_espectro.clear()
            self.c_espectro.addItems([e["nombre"] for e in d["espectros"]])
            if d["espectros"]:
                self.c_espectro.setCurrentIndex(min(max(actual, 0), len(d["espectros"]) - 1))
        finally:
            self._cargando = False
        self._mostrar_espectro()
        self._mostrar_resultados()

    def _espectro_actual(self) -> dict | None:
        k = self.c_espectro.currentIndex()
        espectros = self.sesion.dinamica["espectros"]
        return espectros[k] if 0 <= k < len(espectros) else None

    def _mostrar_espectro(self) -> None:
        e = self._espectro_actual()
        self._cargando = True
        try:
            for w in (
                self.e_nombre,
                self.c_direccion,
                self.c_combinacion,
                self.s_amort,
                self.t_puntos,
                self.b_quitar,
            ):
                w.setEnabled(e is not None)
            if e is None:
                self.e_nombre.clear()
                self.t_puntos.setRowCount(0)
                self.grafico.mostrar([], [])
                return
            self.e_nombre.setText(e["nombre"])
            self.c_direccion.setCurrentText(e["direccion"])
            self.c_combinacion.setCurrentText(e["combinacion"])
            self.s_amort.setValue(100 * e["amortiguamiento"])
            self.t_puntos.setRowCount(len(e["puntos"]))
            for k, (t, sa) in enumerate(e["puntos"]):
                self.t_puntos.setItem(k, 0, _celda(f"{t:g}", editable=True))
                self.t_puntos.setItem(k, 1, _celda(f"{sa:g}", editable=True))
            din = self.sesion.resultados_dinamica if self.sesion.dinamica_al_dia else None
            self.grafico.mostrar(e["puntos"], din.modal.periodos if din else [])
        finally:
            self._cargando = False

    def _mostrar_resultados(self) -> None:
        s = self.sesion
        din = s.resultados_dinamica if s.dinamica_al_dia else None
        self.t_modos.blockSignals(True)
        self.t_basal.blockSignals(True)
        self.t_modos.setRowCount(0)
        self.t_basal.setRowCount(0)
        self.b_animar.setEnabled(din is not None)
        if din is None:
            hay = s.doc.dinamica is not None and s.resultados_dinamica is not None
            self.lbl_estado.setText(
                "Resultados desactualizados: analizá de nuevo." if hay else "Sin analizar."
            )
        else:
            modal = din.modal
            p = 100 * modal.masa_participante
            a = 100 * modal.masa_participante_acumulada
            self.t_modos.setRowCount(modal.n_modos)
            for k in range(modal.n_modos):
                valores = (
                    str(k + 1),
                    f"{modal.periodos[k]:.4g}",
                    f"{modal.frecuencias[k]:.4g}",
                    *(f"{v:.1f}" for v in (p[k, 0], p[k, 1], a[k, 0], a[k, 1])),
                )
                for c, texto in enumerate(valores):
                    self.t_modos.setItem(k, c, _celda(texto))
            for c, col in ((5, 0), (6, 1)):
                if modal.masa_total[col] > 0 and a[-1, col] < 90:
                    item = self.t_modos.item(modal.n_modos - 1, c)
                    item.setForeground(QColor(estilo.NEGATIVO))
                    item.setToolTip("No llega al 90 %: conviene pedir más modos")
            u = s.modelo["unidades"]
            self.t_basal.setRowCount(len(din.espectros))
            for k, (nombre, r) in enumerate(din.espectros.items()):
                v = np.where(
                    np.abs(r.cortante_basal) > 1e-9 * np.abs(r.cortante_basal).max(),
                    r.cortante_basal,
                    0.0,
                )
                valores = (
                    nombre,
                    r.direccion,
                    r.combinacion,
                    f"{v[0]:.4g} {u['fuerza']}",
                    f"{v[1]:.4g} {u['fuerza']}",
                )
                for c, texto in enumerate(valores):
                    self.t_basal.setItem(k, c, _celda(texto, derecha=c >= 3))
            texto = f"{modal.n_modos} modos · T1 = {modal.periodos[0]:.4g} s"
            if modal.n_modos < s.dinamica["n_modos"]:
                texto += " (no hay más GDL con masa)"
            self.lbl_estado.setText(texto)
            nombre = s.combinacion
            fila = next((k for k, n in enumerate(din.modos) if n == nombre), None)
            if fila is not None:
                self.t_modos.selectRow(fila)
        self.t_modos.blockSignals(False)
        self.t_basal.blockSignals(False)
        e = self._espectro_actual()
        if e is not None:
            self.grafico.mostrar(e["puntos"], din.modal.periodos if din else [])

    # --- Edición ------------------------------------------------------------------------
    def _editar(self, cambio) -> bool:
        d = copy.deepcopy(self.sesion.dinamica)
        cambio(d)
        try:
            self.sesion.editar_dinamica(d)
        except formato.FormatoError as e:
            self.lbl_estado.setText(f"✕ {e.motivo}")
            self.actualizar()
            return False
        return True

    def _masas_editadas(self, item: QTableWidgetItem) -> None:
        if self._cargando or item.column() != 1:
            return
        nombre = self.t_masas.item(item.row(), 0).text()
        texto = item.text().strip()
        try:
            f = _numero(texto) if texto else 0.0
        except ValueError:
            self.lbl_estado.setText(f"✕ Factor no válido: {texto}")
            self.actualizar()
            return

        def cambio(d):
            if f:
                d["masas"]["casos"][nombre] = f
            else:
                d["masas"]["casos"].pop(nombre, None)

        self._editar(cambio)

    def _n_modos(self, n: int) -> None:
        if not self._cargando and n != self.sesion.dinamica["n_modos"]:
            self._editar(lambda d: d.update(n_modos=int(n)))

    def _espectro_editado(self, *_args) -> None:
        if self._cargando:
            return
        k = self.c_espectro.currentIndex()
        nombre = self.e_nombre.text().strip()

        def cambio(d):
            e = d["espectros"][k]
            e["nombre"] = nombre or e["nombre"]
            e["direccion"] = self.c_direccion.currentText()
            e["combinacion"] = self.c_combinacion.currentText()
            e["amortiguamiento"] = round(self.s_amort.value() / 100, 6)

        if 0 <= k < len(self.sesion.dinamica["espectros"]):
            self._editar(cambio)

    def _puntos_editados(self, _item=None) -> None:
        if self._cargando:
            return
        k = self.c_espectro.currentIndex()
        puntos = []
        try:
            for fila in range(self.t_puntos.rowCount()):
                celdas = [self.t_puntos.item(fila, c) for c in (0, 1)]
                textos = [c.text().strip() if c else "" for c in celdas]
                if not all(textos):
                    return  # fila a medio completar
                puntos.append([_numero(t) for t in textos])
        except ValueError:
            self.lbl_estado.setText("✕ Los puntos del espectro tienen que ser números.")
            return
        puntos.sort(key=lambda p: p[0])
        self._editar(lambda d: d["espectros"][k].update(puntos=puntos))

    def _agregar_punto(self) -> None:
        e = self._espectro_actual()
        if e is None:
            return
        k = self.c_espectro.currentIndex()
        t, sa = e["puntos"][-1]
        nuevo = [round(t + max(0.5, 0.25 * t), 4), sa]
        self._editar(lambda d: d["espectros"][k]["puntos"].append(nuevo))

    def _quitar_punto(self) -> None:
        e = self._espectro_actual()
        fila = self.t_puntos.currentRow()
        if e is None or fila < 0 or len(e["puntos"]) <= 1:
            return
        k = self.c_espectro.currentIndex()
        self._editar(lambda d: d["espectros"][k]["puntos"].pop(fila))

    def agregar_espectro(self) -> None:
        existentes = {e["nombre"] for e in self.sesion.dinamica["espectros"]}
        direccion = "X"
        nombre = "Sismo X"
        n = 2
        while nombre in existentes:
            nombre = f"Sismo X{n}"
            n += 1
        nuevo = formato.dinamica.espectro_ejemplo(nombre, direccion)
        if self._editar(lambda d: d["espectros"].append(nuevo)):
            self.c_espectro.setCurrentIndex(self.c_espectro.count() - 1)

    def quitar_espectro(self) -> None:
        k = self.c_espectro.currentIndex()
        if k >= 0:
            self._editar(lambda d: d["espectros"].pop(k))

    # --- Análisis y selección -------------------------------------------------------------
    def analizar(self) -> bool:
        try:
            din = self.sesion.analizar_dinamica()
        except (ValueError, formato.FormatoError) as e:
            self.lbl_estado.setText(f"✕ {e}")
            return False
        except MecanismoError:
            ines = self.sesion.inestabilidad
            self.lbl_estado.setText(f"✕ {ines.texto() if ines else 'Estructura inestable.'}")
            return False
        self._mostrar_resultados()
        if din.modos:
            self.resultado_elegido.emit(next(iter(din.modos)))
        return True

    def _modo_elegido(self) -> None:
        filas = self.t_modos.selectionModel().selectedRows()
        if filas:
            self.resultado_elegido.emit(f"Modo {filas[0].row() + 1}")

    def _espectro_elegido(self) -> None:
        filas = self.t_basal.selectionModel().selectedRows()
        if filas:
            self.resultado_elegido.emit(self.t_basal.item(filas[0].row(), 0).text())


def fase(t: float, periodo_animacion: float = 1.6) -> float:
    """Factor de la forma modal en el instante ``t`` (s) de la animación."""
    return math.sin(2 * math.pi * t / periodo_animacion)
