# SPDX-License-Identifier: GPL-3.0-or-later
"""Genera los íconos de los instaladores a partir del isotipo SVG.

Uso: python packaging/generar_iconos.py <carpeta_destino>
Escribe nervi.ico (Windows, varios tamaños), nervi.png (256 px, Linux) y
nervi-proyecto.png (ícono de los archivos .nrv).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

RAIZ = Path(__file__).resolve().parents[1]
SVG = RAIZ / "python" / "nervi" / "gui" / "recursos" / "nervi.svg"


def renderizar(tam: int) -> QImage:
    img = QImage(tam, tam, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    svg = QSvgRenderer(str(SVG))
    caja = svg.viewBoxF()
    escala = 0.9 * tam / max(caja.width(), caja.height())
    w, h = caja.width() * escala, caja.height() * escala
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    svg.render(p, QRectF((tam - w) / 2, (tam - h) / 2, w, h))
    p.end()
    return img


def main(destino: str) -> None:
    QGuiApplication.instance() or QGuiApplication([])
    carpeta = Path(destino)
    carpeta.mkdir(parents=True, exist_ok=True)
    if not renderizar(256).save(str(carpeta / "nervi.png")):
        raise SystemExit("no se pudo escribir nervi.png")
    renderizar(256).save(str(carpeta / "nervi-proyecto.png"))
    # El formato ICO de Qt guarda un tamaño por archivo: se arma a mano con PNG embebidos.
    imagenes = []
    for tam in (16, 24, 32, 48, 64, 128, 256):
        ruta = carpeta / f"nervi-{tam}.png"
        renderizar(tam).save(str(ruta))
        imagenes.append((tam, ruta.read_bytes()))
    (carpeta / "nervi.ico").write_bytes(_ico(imagenes))


def _ico(imagenes: list[tuple[int, bytes]]) -> bytes:
    cabecera = (0).to_bytes(2, "little") + (1).to_bytes(2, "little")
    cabecera += len(imagenes).to_bytes(2, "little")
    directorio, datos = b"", b""
    desplazamiento = 6 + 16 * len(imagenes)
    for tam, png in imagenes:
        lado = 0 if tam >= 256 else tam
        directorio += bytes([lado, lado, 0, 0]) + (1).to_bytes(2, "little")
        directorio += (32).to_bytes(2, "little") + len(png).to_bytes(4, "little")
        directorio += (desplazamiento + len(datos)).to_bytes(4, "little")
        datos += png
    return cabecera + directorio + datos


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "build/iconos")
