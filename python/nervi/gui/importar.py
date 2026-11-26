# SPDX-License-Identifier: GPL-3.0-or-later
"""Diálogo *Archivo › Importar DXF*: elegir capas y opciones mirando el resultado.

La lectura y el armado son de :mod:`nervi.importar.dxf` (sin Qt y sin IA). Acá solo
se eligen las opciones, se ve el modelo que quedaría y, al tocar *Importar*, se
aplica como una edición más: se deshace con Ctrl+Z y queda en el historial.
"""

from __future__ import annotations

import copy
import dataclasses
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..importar import dxf
from . import estilo
from .sesion import Sesion

#: Origen con el que queda anotada la importación en el historial del ``.nrv``.
ORIGEN = "importador: DXF"
UNIDADES = {"mm": "milímetros", "cm": "centímetros", "m": "metros", "in": "pulgadas", "ft": "pies"}


def _etiqueta(texto: str, nombre: str | None = None, ajustar: bool = False) -> QLabel:
    lbl = QLabel(texto)
    if nombre:
        lbl.setObjectName(nombre)
    lbl.setWordWrap(ajustar)
    return lbl


def _caja(titulo: str, capa: QVBoxLayout) -> QFormLayout:
    capa.addWidget(_etiqueta(titulo.upper(), "seccion"))
    caja = QWidget(objectName="caja_ajustes")
    caja.setAttribute(Qt.WA_StyledBackground)
    form = QFormLayout(caja)
    form.setContentsMargins(14, 10, 14, 10)
    form.setHorizontalSpacing(16)
    form.setVerticalSpacing(8)
    capa.addWidget(caja)
    return form


class DialogoImportarDXF(QDialog):
    """Capas, unidad y opciones a la izquierda; a la derecha, el modelo que quedaría
    (lo nuevo resaltado) con lo que se agrega y los avisos."""

    def __init__(self, sesion: Sesion, ruta: str | Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.sesion = sesion
        self.ruta = Path(ruta)
        self.dibujo = dxf.leer(self.ruta)  # DXFError u OSError: los atiende quien llama
        self.resultado: dxf.Importacion | None = None
        self.setWindowTitle("Importar DXF")
        self.resize(1000, 640)
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        cabecera = QWidget(objectName="barra")
        cabecera.setAttribute(Qt.WA_StyledBackground)
        c = QHBoxLayout(cabecera)
        c.setContentsMargins(16, 10, 16, 10)
        c.addWidget(_etiqueta("Importar DXF", "titulo"))
        c.addWidget(_etiqueta(self.ruta.name, "tenue"))
        c.addStretch()
        raiz.addWidget(cabecera)

        medio = QHBoxLayout()
        medio.setContentsMargins(16, 14, 16, 14)
        medio.setSpacing(16)
        raiz.addLayout(medio, 1)

        # --- Opciones -------------------------------------------------------------
        izquierda = QWidget(objectName="pagina_ajustes")
        izquierda.setAttribute(Qt.WA_StyledBackground)
        opciones = QVBoxLayout(izquierda)
        opciones.setContentsMargins(0, 0, 0, 0)
        opciones.setSpacing(8)
        desplazable = QScrollArea()
        desplazable.setWidgetResizable(True)
        desplazable.setFrameShape(QScrollArea.NoFrame)
        desplazable.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        desplazable.setWidget(izquierda)
        desplazable.setFixedWidth(330)
        medio.addWidget(desplazable)

        form = _caja("Capas", opciones)
        self.casillas: dict[str, QCheckBox] = {}
        for nombre in sorted(self.dibujo.capas, key=str.lower):
            n = len(self.dibujo.capas[nombre])
            casilla = QCheckBox(nombre)
            casilla.setChecked(True)
            casilla.toggled.connect(self.actualizar)
            fila = QHBoxLayout()
            fila.addWidget(casilla, 1)
            fila.addWidget(_etiqueta(f"{n} {'línea' if n == 1 else 'líneas'}", "tenue"))
            form.addRow(fila)
            self.casillas[nombre] = casilla
        if not self.casillas:
            form.addRow(_etiqueta("El dibujo no tiene líneas.", "tenue", True))

        form = _caja("Dibujo", opciones)
        self.unidad = QComboBox()
        if self.dibujo.unidad is None:
            self.unidad.addItem("Elegí la unidad", None)
        for clave, nombre in UNIDADES.items():
            self.unidad.addItem(nombre, clave)
        if self.dibujo.unidad is not None:
            self.unidad.setCurrentIndex(self.unidad.findData(self.dibujo.unidad))
        self.unidad.currentIndexChanged.connect(self.actualizar)
        form.addRow("Unidad", self.unidad)
        self.tolerancia = QDoubleSpinBox(suffix=" mm", decimals=1, minimum=0.1, maximum=1000)
        self.tolerancia.setValue(10)
        self.tolerancia.setToolTip("Los puntos más cerca que esto son el mismo nudo.")
        self.tolerancia.valueChanged.connect(self.actualizar)
        form.addRow("Tolerancia", self.tolerancia)

        form = _caja("Opciones", opciones)
        vacio = not sesion.modelo["nudos"]
        self.al_origen = QCheckBox("Llevar el dibujo al origen")
        self.al_origen.setChecked(vacio)
        self.al_origen.setEnabled(vacio)
        if not vacio:
            self.al_origen.setToolTip(
                "Con un modelo que ya tiene nudos, el dibujo va en sus coordenadas."
            )
        self.al_origen.toggled.connect(self.actualizar)
        form.addRow(self.al_origen)
        self.empotrar = QCheckBox("Empotrar los nudos más bajos")
        self.empotrar.setChecked(vacio)
        self.empotrar.toggled.connect(self.actualizar)
        form.addRow(self.empotrar)
        nota = _etiqueta(
            "La X del dibujo es la horizontal del pórtico y la Y, la vertical. "
            "Lo importado se suma al modelo y se deshace con Ctrl+Z.",
            "tenue",
            True,
        )
        opciones.addWidget(nota)
        opciones.addStretch()

        # --- Vista previa -----------------------------------------------------------
        from .vista2d import Vista2D

        class Previa(Vista2D):
            def _leyenda(self, *_args) -> None:  # sin resultados ni diagramas que explicar
                pass

        derecha = QVBoxLayout()
        derecha.setSpacing(8)
        self.lbl_resumen = _etiqueta("", "titulo", True)
        derecha.addWidget(self.lbl_resumen)
        self.previa = Sesion(dataclasses.replace(copy.deepcopy(sesion.doc), historial=None))
        self.vista = Previa(self.previa, self)
        derecha.addWidget(self.vista, 1)
        self.lbl_avisos = _etiqueta("", "tenue", True)
        self.lbl_avisos.setTextFormat(Qt.PlainText)
        derecha.addWidget(self.lbl_avisos)
        medio.addLayout(derecha, 1)

        pie = QWidget(objectName="pie_ajustes")
        pie.setAttribute(Qt.WA_StyledBackground)
        p = QHBoxLayout(pie)
        p.setContentsMargins(16, 10, 16, 10)
        p.addStretch()
        cancelar = QPushButton("Cancelar")
        cancelar.clicked.connect(self.reject)
        self.b_importar = QPushButton("Importar", objectName="primario")
        self.b_importar.setDefault(True)
        self.b_importar.clicked.connect(self.importar)
        p.addWidget(cancelar)
        p.addWidget(self.b_importar)
        raiz.addWidget(pie)
        self.actualizar()

    # --- Lógica -----------------------------------------------------------------------
    def capas(self) -> list[str]:
        return [n for n, c in self.casillas.items() if c.isChecked()]

    def actualizar(self, *_args) -> None:
        """Vuelve a armar el modelo con las opciones elegidas y lo muestra."""
        try:
            self.resultado = dxf.importar(
                self.dibujo,
                capas=self.capas(),
                unidad=self.unidad.currentData(),
                base=self.sesion.modelo,
                tolerancia=self.tolerancia.value() / 1000,
                al_origen=self.al_origen.isChecked(),
                empotrar_base=self.empotrar.isChecked(),
            )
        except dxf.DXFError as e:
            self.resultado = None
            self.lbl_resumen.setText(str(e))
            self.lbl_avisos.setText("")
            self._mostrar(self.sesion.modelo, set())
            self.b_importar.setEnabled(False)
            return
        r = self.resultado
        self.lbl_resumen.setText(
            f"Se agregan {r.nudos_nuevos} {'nudo' if r.nudos_nuevos == 1 else 'nudos'} y "
            f"{r.barras_nuevas} {'barra' if r.barras_nuevas == 1 else 'barras'}"
        )
        self.lbl_avisos.setText("\n".join(r.avisos))
        # Lo nuevo se resalta solo si hay algo de antes con qué distinguirlo.
        antes = {b["id"] for b in self.sesion.modelo["barras"]}
        nuevas = {b["id"] for b in r.modelo["barras"]} - antes if antes else set()
        self._mostrar(r.modelo, nuevas)
        self.b_importar.setEnabled(r.barras_nuevas > 0)

    def _mostrar(self, modelo: dict, nuevas: set[int]) -> None:
        self.previa.doc.modelo = modelo
        self.vista.colores_barra = dict.fromkeys(nuevas, estilo.ACENTO)
        self.previa.modelo_cambiado.emit()

    def importar(self) -> None:
        if self.resultado is None or not self.resultado.barras_nuevas:
            return
        r = self.resultado
        self.sesion.editar(
            r.modelo,
            origen=ORIGEN,
            descripcion=f"Importar {self.ruta.name} ({r.nudos_nuevos} nudos, "
            f"{r.barras_nuevas} barras)",
        )
        self.accept()
