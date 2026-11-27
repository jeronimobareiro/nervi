# SPDX-License-Identifier: GPL-3.0-or-later
"""Dibuja la lámina del catálogo de íconos (``docs/img/iconos-claro.png`` y ``-oscuro.png``).

Uso::

    python scripts/lamina_iconos.py            # escribe las dos láminas en docs/img/
    python scripts/lamina_iconos.py --carpeta /tmp/iconos

Cada celda muestra el ícono a 24 px y a 16 px, su nombre y su clave. Un punto azul marca
los íconos que la aplicación ya usa; el resto está reservado para la fase que figura en
``docs/iconos.md``.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from nervi.gui import estilo, iconos

COLUMNAS = 8
RAIZ = Path(__file__).resolve().parent.parent


def lamina(tema: estilo.Tema) -> QWidget:
    w = QWidget(objectName="raiz")
    w.setAttribute(Qt.WA_StyledBackground)
    w.setStyleSheet(f"#raiz {{ background: {tema.fondo}; }}")
    capa = QVBoxLayout(w)
    capa.setContentsMargins(28, 24, 28, 28)
    capa.setSpacing(10)
    titulo = QLabel("Catálogo de íconos de Nervi", objectName="titulo")
    titulo.setStyleSheet(f"font-size: 15pt; font-weight: 600; color: {tema.texto};")
    capa.addWidget(titulo)
    nota = QLabel(
        f"{len(iconos.CATALOGO)} íconos · grilla de 24 · trazo 1,7 · "
        "● en uso en la aplicación · el resto, reservados por fase"
    )
    nota.setStyleSheet(f"color: {tema.texto_3};")
    capa.addWidget(nota)
    escala = 2.0
    for grupo, lista in iconos.por_grupo().items():
        cab = QLabel(grupo.upper(), objectName="seccion")
        cab.setStyleSheet(
            f"color: {tema.texto_3}; font-weight: 600; letter-spacing: 1px; margin-top: 8px;"
        )
        capa.addWidget(cab)
        g = QGridLayout()
        g.setHorizontalSpacing(8)
        g.setVerticalSpacing(8)
        for k, ic in enumerate(lista):
            celda = QWidget(objectName="celda")
            celda.setAttribute(Qt.WA_StyledBackground)
            celda.setStyleSheet(
                f"#celda {{ background: {tema.panel}; border: 1px solid {tema.borde};"
                f" border-radius: {tema.radio}px; }}"
            )
            celda.setFixedSize(138, 92)
            c = QVBoxLayout(celda)
            c.setContentsMargins(10, 8, 10, 6)
            c.setSpacing(2)
            fila = QHBoxLayout()
            fila.setSpacing(10)
            grande = QLabel()
            grande.setPixmap(iconos.pixmap(ic.clave, tema.texto, 24, escala))
            chico = QLabel()
            chico.setPixmap(iconos.pixmap(ic.clave, tema.texto_2, 16, escala))
            fila.addWidget(grande, 0, Qt.AlignBottom)
            fila.addWidget(chico, 0, Qt.AlignBottom)
            fila.addStretch()
            if ic.en_uso:
                punto = QLabel("●")
                punto.setStyleSheet(f"color: {tema.acento}; font-size: 7pt;")
                fila.addWidget(punto, 0, Qt.AlignTop)
            c.addLayout(fila)
            c.addStretch()
            nombre = QLabel(ic.nombre)
            nombre.setStyleSheet(f"color: {tema.texto}; font-size: 8.5pt;")
            clave = QLabel(ic.clave)
            clave.setStyleSheet(f"color: {tema.texto_3}; font-size: 7.5pt; font-family: monospace;")
            c.addWidget(nombre)
            c.addWidget(clave)
            g.addWidget(celda, k // COLUMNAS, k % COLUMNAS)
        g.setColumnStretch(COLUMNAS, 1)
        capa.addLayout(g)
    capa.addStretch()
    return w


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--carpeta", type=Path, default=RAIZ / "docs" / "img")
    args = ap.parse_args(argv)
    app = QApplication.instance() or QApplication(["lamina"])
    args.carpeta.mkdir(parents=True, exist_ok=True)
    for nombre, tema in (("claro", estilo.CLARO), ("oscuro", estilo.OSCURO)):
        estilo.aplicar(app, tema)
        w = lamina(tema)
        w.adjustSize()
        w.resize(28 * 2 + COLUMNAS * 138 + (COLUMNAS - 1) * 8, w.sizeHint().height())
        w.show()
        for _ in range(5):
            app.processEvents()
        ruta = args.carpeta / f"iconos-{nombre}.png"
        w.grab().save(str(ruta))
        w.close()
        print(ruta)
    return 0


if __name__ == "__main__":
    sys.exit(main())
