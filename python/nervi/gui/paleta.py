# SPDX-License-Identifier: GPL-3.0-or-later
"""Buscador de comandos y elementos (Ctrl+K)."""

from __future__ import annotations

import unicodedata
from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout, QWidget


@dataclass
class Entrada:
    texto: str
    grupo: str
    detalle: str
    ejecutar: Callable[[], None]


def _normal(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFD", texto)
    return "".join(c for c in sin_tildes if unicodedata.category(c) != "Mn").lower()


def filtrar(entradas: list[Entrada], consulta: str) -> list[Entrada]:
    """Entradas cuyo texto contiene todas las palabras de la consulta (sin tildes)."""
    palabras = _normal(consulta).split()
    return [e for e in entradas if all(p in _normal(f"{e.texto} {e.grupo}") for p in palabras)]


class Paleta(QDialog):
    def __init__(self, entradas: list[Entrada], parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint)
        self.setObjectName("paleta")
        self.entradas = entradas
        self.campo = QLineEdit()
        self.campo.setPlaceholderText("Buscar comando o elemento")
        self.lista = QListWidget()
        capa = QVBoxLayout(self)
        capa.setContentsMargins(8, 8, 8, 8)
        capa.addWidget(self.campo)
        capa.addWidget(self.lista)
        self.resize(560, 380)
        self.campo.textChanged.connect(self._actualizar)
        self.campo.returnPressed.connect(self._ejecutar_actual)
        self.lista.itemActivated.connect(lambda _i: self._ejecutar_actual())
        self._actualizar("")

    def _actualizar(self, consulta: str) -> None:
        self.lista.clear()
        for e in filtrar(self.entradas, consulta)[:50]:
            item = QListWidgetItem(
                f"{e.texto}    ·  {e.grupo}{'  ·  ' + e.detalle if e.detalle else ''}"
            )
            item.setData(Qt.UserRole, e)
            self.lista.addItem(item)
        if self.lista.count():
            self.lista.setCurrentRow(0)

    def keyPressEvent(self, evento) -> None:
        if evento.key() in (Qt.Key_Down, Qt.Key_Up):
            fila = self.lista.currentRow() + (1 if evento.key() == Qt.Key_Down else -1)
            self.lista.setCurrentRow(max(0, min(self.lista.count() - 1, fila)))
            return
        super().keyPressEvent(evento)

    def _ejecutar_actual(self) -> None:
        item = self.lista.currentItem()
        if item is None:
            return
        entrada: Entrada = item.data(Qt.UserRole)
        self.accept()
        entrada.ejecutar()
