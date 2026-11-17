# SPDX-License-Identifier: GPL-3.0-or-later
"""Etapa *Diseño*: materiales, criterios y armadura de cada barra (experimental).

El panel no guarda datos propios: lee y escribe ``diseno.json`` a través de la
sesión (``Sesion.diseno`` y ``Sesion.editar_diseno``) y muestra lo que devuelve
``nervi.design.proyecto.disenar``.
"""

from __future__ import annotations

import copy

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .. import formato
from ..design.proyecto import AVISO_EXPERIMENTAL
from . import estilo
from .sesion import Seleccion, Sesion

COLUMNAS = (
    "Barra",
    "Tipo",
    "b (mm)",
    "h (mm)",
    "Inferior",
    "Superior",
    "Estribos",
    "Estado",
)
COLUMNAS_VERIF = ("Verificación", "Solicitación / resistencia", "Relación", "ACI 318-19")
#: Texto del selector de tipo -> valor en diseno.json.
TIPOS = {"Automático": "auto", "Viga": "viga", "Columna": "columna", "No diseñar": "ninguno"}
ESTADOS = {
    "cumple": ("✓ Cumple", estilo.OK),
    "no cumple": ("✕ No cumple", estilo.NEGATIVO),
    "error": ("✕ Error", estilo.NEGATIVO),
    "pendiente": ("Pendiente", estilo.TEXTO_3),
}


def color_estado(estado: str) -> str:
    return ESTADOS.get(estado, ("", estilo.TEXTO_3))[1]


def _spin(minimo: float, maximo: float, sufijo: str, decimales: int = 0) -> QDoubleSpinBox:
    s = QDoubleSpinBox()
    s.setRange(minimo, maximo)
    s.setDecimals(decimales)
    s.setSuffix(f" {sufijo}")
    s.setKeyboardTracking(False)
    s.setMinimumWidth(90)
    return s


class PanelDiseno(QWidget):
    """Pestaña "Diseño" del panel inferior."""

    disenado = Signal()

    def __init__(self, sesion: Sesion, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.sesion = sesion
        self._cargando = False
        capa = QVBoxLayout(self)
        capa.setContentsMargins(10, 8, 10, 6)
        capa.setSpacing(6)

        self.aviso = QLabel(f"⚠  {AVISO_EXPERIMENTAL}", objectName="aviso")
        self.aviso.setWordWrap(True)
        capa.addWidget(self.aviso)

        fila = QHBoxLayout()
        fila.setSpacing(6)
        fila.addWidget(QLabel("Norma", objectName="tenue"))
        fila.addWidget(QLabel("ACI 318-19", objectName="titulo"))
        fila.addSpacing(10)
        self.fc = _spin(17, 100, "MPa", 1)
        self.fy = _spin(240, 550, "MPa")
        self.fyt = _spin(240, 420, "MPa")
        self.recubrimiento = _spin(0, 100, "mm")
        self.agregado = _spin(5, 50, "mm")
        self.estribo = QComboBox()
        for d in formato.diseno.DIAMETROS_ESTRIBO:
            self.estribo.addItem(f"Ø{d}", d)
        self.a_d = QCheckBox("Cortante a d del apoyo")
        self.a_d.setToolTip("Sección crítica a d de la cara del apoyo (ACI 318-19 §9.4.3.2)")
        for texto, w, ayuda in (
            ("f'c", self.fc, "Resistencia especificada del hormigón"),
            ("fy", self.fy, "Fluencia de la armadura longitudinal"),
            ("fyt", self.fyt, "Fluencia de los estribos (§20.2.2.4: hasta 420 MPa)"),
            ("Recubrimiento", self.recubrimiento, "Recubrimiento libre hasta el estribo"),
            ("Estribo", self.estribo, "Diámetro de los estribos"),
            ("Agregado", self.agregado, "Tamaño máximo nominal del agregado"),
        ):
            lbl = QLabel(texto, objectName="tenue")
            lbl.setToolTip(ayuda)
            w.setToolTip(ayuda)
            fila.addWidget(lbl)
            fila.addWidget(w)
        fila.addWidget(self.a_d)
        fila.addStretch()
        self.b_disenar = QPushButton("Diseñar", objectName="primario")
        self.b_disenar.clicked.connect(self.disenar)
        fila.addWidget(self.b_disenar)
        capa.addLayout(fila)

        for s in (self.fc, self.fy, self.fyt, self.recubrimiento, self.agregado):
            s.valueChanged.connect(self._criterios_editados)
        self.estribo.currentIndexChanged.connect(self._criterios_editados)
        self.a_d.toggled.connect(self._criterios_editados)

        self.tabla = QTableWidget(0, len(COLUMNAS))
        self.tabla.setHorizontalHeaderLabels(COLUMNAS)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.verticalHeader().setDefaultSectionSize(28)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabla.setSelectionMode(QAbstractItemView.SingleSelection)
        cabecera = self.tabla.horizontalHeader()
        cabecera.setSectionResizeMode(QHeaderView.ResizeToContents)
        cabecera.setSectionResizeMode(4, QHeaderView.Interactive)
        cabecera.setSectionResizeMode(5, QHeaderView.Interactive)
        cabecera.setSectionResizeMode(6, QHeaderView.Interactive)
        cabecera.resizeSection(4, 120)
        cabecera.resizeSection(5, 120)
        cabecera.resizeSection(6, 195)
        cabecera.setStretchLastSection(True)
        self.tabla.itemChanged.connect(self._celda_editada)
        self.tabla.itemSelectionChanged.connect(self._fila_elegida)

        derecha = QWidget()
        cd = QVBoxLayout(derecha)
        cd.setContentsMargins(8, 0, 0, 0)
        cd.setSpacing(4)
        self.lbl_verif = QLabel("VERIFICACIONES", objectName="seccion")
        cd.addWidget(self.lbl_verif)
        self.verif = QTableWidget(0, len(COLUMNAS_VERIF))
        self.verif.setHorizontalHeaderLabels(COLUMNAS_VERIF)
        self.verif.verticalHeader().setVisible(False)
        self.verif.verticalHeader().setDefaultSectionSize(24)
        self.verif.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.verif.setSelectionMode(QAbstractItemView.NoSelection)
        cv = self.verif.horizontalHeader()
        cv.setSectionResizeMode(QHeaderView.ResizeToContents)
        cv.setStretchLastSection(True)
        cd.addWidget(self.verif, 1)
        self.lbl_notas = QLabel()
        self.lbl_notas.setWordWrap(True)
        cd.addWidget(self.lbl_notas)

        self.division = QSplitter(Qt.Horizontal)
        self.division.addWidget(self.tabla)
        self.division.addWidget(derecha)
        self.division.setStretchFactor(0, 3)
        self.division.setStretchFactor(1, 2)
        self._repartido = False
        capa.addWidget(self.division, 1)

        pie = QHBoxLayout()
        self.lbl_estado = QLabel(objectName="tenue")
        pie.addWidget(self.lbl_estado)
        pie.addSpacing(12)
        self.lbl_mensaje = QLabel(objectName="tenue")
        self.lbl_mensaje.setWordWrap(True)
        pie.addWidget(self.lbl_mensaje, 1)
        capa.addLayout(pie)

        sesion.modelo_cambiado.connect(self.actualizar)
        sesion.diseno_cambiado.connect(self.actualizar)
        sesion.resultados_cambiados.connect(self._actualizar_estado)
        sesion.seleccion_cambiada.connect(self._marcar_seleccion)
        self.actualizar()

    def showEvent(self, evento) -> None:
        super().showEvent(evento)
        if not self._repartido:
            # La primera vez, 60 % para los elementos y 40 % para las verificaciones.
            ancho = max(self.division.width(), 600)
            self.division.setSizes([int(0.6 * ancho), ancho - int(0.6 * ancho)])
            self._repartido = True

    # --- Datos ---------------------------------------------------------------------
    def _criterios_editados(self, *_args) -> None:
        if self._cargando:
            return
        d = copy.deepcopy(self.sesion.diseno)
        d["hormigon"]["fc"] = self.fc.value()
        d["acero"]["fy"] = self.fy.value()
        d["acero"]["fyt"] = self.fyt.value()
        c = d["criterios"]
        c["recubrimiento"] = self.recubrimiento.value()
        c["d_agregado"] = self.agregado.value()
        c["d_estribo"] = float(self.estribo.currentData())
        c["seccion_critica_a_d"] = self.a_d.isChecked()
        self.sesion.editar_diseno(d)

    def _editar_elemento(self, barra: int, **cambios) -> None:
        d = copy.deepcopy(self.sesion.diseno)
        lista = d["elementos"]
        e = next((x for x in lista if x["barra"] == barra), None)
        if e is None:
            e = {"barra": barra}
            lista.append(e)
        e.update(cambios)
        if e.get("tipo") == "auto":
            del e["tipo"]
        if set(e) == {"barra"}:
            lista.remove(e)
        lista.sort(key=lambda x: x["barra"])
        try:
            self.sesion.editar_diseno(d)
        except formato.FormatoError as err:
            self.lbl_mensaje.setText(f"Dato no válido: {err.motivo}")
            self.actualizar()

    def _celda_editada(self, item: QTableWidgetItem) -> None:
        if self._cargando or item.column() not in (2, 3):
            return
        barra = item.data(Qt.UserRole)
        clave = "b" if item.column() == 2 else "h"
        try:
            valor = float(item.text().replace(",", "."))
            if valor <= 0:
                raise ValueError
        except ValueError:
            self.lbl_mensaje.setText("La sección se da en mm y tiene que ser positiva.")
            self.actualizar()
            return
        # La tabla se vuelve a llenar al cambiar el diseño: se hace después de que Qt
        # termine de procesar la edición de esta celda.
        QTimer.singleShot(0, lambda: self._editar_elemento(barra, **{clave: valor}))

    def _tipo_elegido(self, barra: int, texto: str) -> None:
        if not self._cargando:
            self._editar_elemento(barra, tipo=TIPOS[texto])

    def disenar(self) -> bool:
        """Calcula si hace falta y diseña todas las barras."""
        # La búsqueda de armadura de cada columna tarda uno o dos segundos.
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self.sesion.disenar()
        except Exception as e:  # el error se muestra en el panel, no se pierde
            self.lbl_mensaje.setText(f"No se pudo diseñar: {e}")
            self.lbl_mensaje.setStyleSheet(f"color: {estilo.NEGATIVO};")
            return False
        finally:
            QApplication.restoreOverrideCursor()
        self.disenado.emit()
        return True

    # --- Vista -----------------------------------------------------------------------
    def actualizar(self) -> None:
        """Vuelve a llenar los controles y la tabla con la sesión."""
        from ..design import proyecto

        s = self.sesion
        d = s.diseno
        self._cargando = True
        try:
            self.fc.setValue(d["hormigon"]["fc"])
            self.fy.setValue(d["acero"]["fy"])
            self.fyt.setValue(d["acero"].get("fyt", d["acero"]["fy"]))
            c = d["criterios"]
            self.recubrimiento.setValue(c["recubrimiento"])
            self.agregado.setValue(c["d_agregado"])
            self.estribo.setCurrentIndex(max(self.estribo.findData(int(c["d_estribo"])), 0))
            self.a_d.setChecked(bool(c["seccion_critica_a_d"]))
            try:
                elementos = proyecto.elementos(s.modelo, d)
            except (KeyError, ValueError, ZeroDivisionError):
                elementos = []
            self.tabla.clearSpans()
            self.tabla.setRowCount(0)
            self.tabla.setRowCount(len(elementos))
            for fila, el in enumerate(elementos):
                self._llenar_fila(fila, el, s.resultado_diseno(el.barra))
        finally:
            self._cargando = False
        self._actualizar_estado()
        self._marcar_seleccion()

    def _llenar_fila(self, fila: int, el, res) -> None:
        def celda(col: int, texto: str, editable: bool = False, color: str | None = None):
            item = QTableWidgetItem(texto)
            item.setData(Qt.UserRole, el.barra)
            flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable
            if editable:
                flags |= Qt.ItemIsEditable
            item.setFlags(flags)
            if col >= 2:
                item.setTextAlignment(
                    (Qt.AlignRight if col in (2, 3) else Qt.AlignLeft) | Qt.AlignVCenter
                )
            if color:
                item.setForeground(QColor(color))
            self.tabla.setItem(fila, col, item)
            return item

        celda(0, f"B{el.barra}")
        tipo = QComboBox()
        for texto, valor in TIPOS.items():
            etiqueta = f"Auto ({el.tipo})" if valor == "auto" and not el.tipo_manual else texto
            tipo.addItem(etiqueta, texto)
        actual = el.tipo if el.tipo_manual else "auto"
        tipo.setCurrentIndex(list(TIPOS.values()).index(actual))
        tipo.currentIndexChanged.connect(
            lambda k, b=el.barra, w=tipo: self._tipo_elegido(b, w.itemData(k))
        )
        self.tabla.setCellWidget(fila, 1, tipo)
        tenue = None if el.seccion_manual else estilo.TEXTO_3
        celda(2, f"{el.b:g}", editable=True, color=tenue).setToolTip(
            "Ancho. Por defecto, el del rectángulo con el mismo A e I que la barra."
        )
        celda(3, f"{el.h:g}", editable=True, color=tenue).setToolTip(
            "Canto en el plano del pórtico."
        )
        if res is None:
            for col in range(4, 8):
                celda(col, "")
            return
        texto, color = ESTADOS[res.estado]
        rel = res.relacion
        if rel is not None:
            texto = f"{texto[0]} {rel:.2f}"
        estado = celda(7, texto, color=color)
        estado.setToolTip("Relación solicitación / resistencia de la verificación que gobierna")
        if "Longitudinal" in res.armadura:
            # Columnas: la armadura longitudinal ocupa las tres columnas de armadura.
            celda(4, f"Longitudinal: {res.armadura['Longitudinal']}")
            self.tabla.setSpan(fila, 4, 1, 3)
        elif res.armadura:
            a = res.armadura
            celda(4, a.get("Inferior", ""))
            celda(5, a.get("Superior", ""))
            celda(6, a.get("Estribos", ""))
        else:
            # Sin armadura (pendiente o sección que no alcanza): el motivo ocupa esas columnas.
            celda(4, " ".join(res.mensajes), color=color).setToolTip("\n".join(res.mensajes))
            self.tabla.setSpan(fila, 4, 1, 3)

    def _actualizar_estado(self) -> None:
        s = self.sesion
        if not s.modelo["barras"]:
            texto = "El modelo no tiene barras"
        elif s.diseno_al_dia:
            res = s.resultados_diseno or []
            mal = sum(r.estado in ("no cumple", "error") for r in res)
            pend = sum(r.estado == "pendiente" and r.elemento.tipo != "ninguno" for r in res)
            texto = f"● Diseño al día · {mal} no cumplen · {pend} pendientes"
        elif s.resultados_diseno is not None:
            texto = "● Diseño desactualizado: diseñá de nuevo"
        else:
            texto = "Sin diseñar"
        self.lbl_estado.setText(texto)
        color = (
            estilo.OK
            if s.diseno_al_dia
            else estilo.NEGATIVO
            if s.resultados_diseno is not None
            else estilo.TEXTO_2
        )
        self.lbl_estado.setStyleSheet(f"color: {color};")
        if s.diseno_al_dia:
            self.lbl_mensaje.setStyleSheet("")
            self.lbl_mensaje.setText(
                "Relación: solicitación / resistencia de la verificación que gobierna. "
                "Elegí una barra para ver cada verificación con su artículo."
            )

    def _fila_elegida(self) -> None:
        if self._cargando:
            return
        filas = self.tabla.selectionModel().selectedRows()
        if filas:
            item = self.tabla.item(filas[0].row(), 0)
            if item is not None:
                self.sesion.seleccionar(Seleccion("barra", item.data(Qt.UserRole)))

    def _mostrar_verificaciones(self) -> None:
        sel = self.sesion.seleccion
        res = (
            self.sesion.resultado_diseno(sel.id)
            if sel is not None and sel.tipo == "barra"
            else None
        )
        self.verif.setRowCount(0)
        self.lbl_notas.setText("")
        if res is None:
            self.lbl_verif.setText("VERIFICACIONES · elegí una barra diseñada")
            return
        self.lbl_verif.setText(f"VERIFICACIONES · B{res.elemento.barra}")
        filas = [
            (
                v.nombre,
                f"{abs(v.solicitacion):.4g} / {v.resistencia:.4g} {v.unidad}",
                f"{'✓' if v.cumple else '✕'} {v.relacion:.2f}",
                v.articulo.removeprefix("ACI 318-19 "),
                v.cumple,
            )
            for v in res.verificaciones
        ]
        if res.mensajes:
            color = estilo.NEGATIVO if res.estado in ("no cumple", "error") else estilo.TEXTO_2
            self.lbl_notas.setStyleSheet(f"color: {color};")
            self.lbl_notas.setText("\n".join(res.mensajes))
        self.verif.setRowCount(len(filas))
        for k, (*textos, cumple) in enumerate(filas):
            for col, texto in enumerate(textos):
                item = QTableWidgetItem(texto)
                if col in (1, 2):
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if col == 2 and cumple is not None:
                    item.setForeground(QColor(estilo.OK if cumple else estilo.NEGATIVO))
                self.verif.setItem(k, col, item)

    def _marcar_seleccion(self) -> None:
        self._mostrar_verificaciones()
        sel = self.sesion.seleccion
        if sel is None or sel.tipo != "barra":
            return
        for fila in range(self.tabla.rowCount()):
            item = self.tabla.item(fila, 0)
            if item is not None and item.data(Qt.UserRole) == sel.id:
                if self.tabla.currentRow() != fila:
                    self._cargando = True
                    self.tabla.selectRow(fila)
                    self._cargando = False
                return
