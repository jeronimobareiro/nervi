# SPDX-License-Identifier: GPL-3.0-or-later
"""Consola Python dentro de la ventana, con el proyecto abierto a mano.

Variables disponibles: ``nervi``, ``np``, ``sesion``, ``doc`` (el documento),
``res`` (resultados del último cálculo) y ``r`` (resultado activo).
"""

from __future__ import annotations

import code
import contextlib
import io
import traceback

import numpy as np
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QVBoxLayout, QWidget

from .sesion import Sesion


class Consola(QWidget):
    def __init__(self, sesion: Sesion) -> None:
        super().__init__()
        import nervi

        self.sesion = sesion
        self.espacio: dict = {"nervi": nervi, "np": np, "sesion": sesion}
        self.salida = QPlainTextEdit(readOnly=True)
        mono = QFontDatabase.systemFont(QFontDatabase.FixedFont)
        mono.setPointSizeF(9)
        self.salida.setFont(mono)
        self.salida.setPlainText(
            "Consola de Python. Variables: nervi, np, doc, "
            "res (resultados), r (resultado activo).\n"
        )
        self.entrada = QLineEdit()
        self.entrada.setFont(mono)
        self.entrada.setPlaceholderText(
            "Escribí código Python, por ejemplo: r.diagrama(1)['M'].max()"
        )
        self.entrada.returnPressed.connect(self.ejecutar_linea)
        fila = QHBoxLayout()
        etiqueta = QLabel("Python ›")
        etiqueta.setObjectName("tenue")
        etiqueta.setFont(QFont(mono))
        fila.addWidget(etiqueta)
        fila.addWidget(self.entrada)
        capa = QVBoxLayout(self)
        capa.setContentsMargins(10, 6, 10, 6)
        capa.addWidget(self.salida)
        capa.addLayout(fila)

    def ejecutar(self, fuente: str) -> str:
        self.espacio.update(
            doc=self.sesion.doc, res=self.sesion.resultados, r=self.sesion.resultado()
        )
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
            try:
                compilado = code.compile_command(fuente, "<consola>", "single")
                if compilado is not None:
                    exec(compilado, self.espacio)
            except SystemExit:
                buffer.write("La consola no puede cerrar la aplicación.\n")
            except BaseException as e:  # se muestra al usuario, no se propaga
                buffer.write("".join(traceback.format_exception_only(type(e), e)))
        return buffer.getvalue()

    def ejecutar_linea(self) -> None:
        fuente = self.entrada.text()
        if not fuente.strip():
            return
        self.entrada.clear()
        self.salida.appendPlainText(f">>> {fuente}")
        texto = self.ejecutar(fuente).rstrip("\n")
        if texto:
            self.salida.appendPlainText(texto)
