# SPDX-License-Identifier: GPL-3.0-or-later
"""Pruebas del catálogo de íconos (``nervi.gui.iconos``)."""

import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
pytest.importorskip("pytestqt")

from PySide6.QtGui import QIcon

from nervi.gui import arbol, dibujo, dibujo_calculo, estilo, iconos, ventana
from nervi.gui.navegacion import BotonesNavegacion

RAIZ = Path(__file__).resolve().parent.parent
FORMAS = {"path", "circle", "rect", "ellipse"}


def test_claves_y_grupos():
    assert len(iconos.CATALOGO) == len(iconos._LISTA), "claves repetidas"
    for clave, ic in iconos.CATALOGO.items():
        assert re.fullmatch(r"[a-z0-9_]+", clave), clave
        assert ic.grupo in iconos.GRUPOS, clave
        assert ic.nombre and ic.uso, clave
        assert ic.rejilla in (16, 24), clave
    assert all(iconos.por_grupo()[g] for g in iconos.GRUPOS)


def test_solo_trazos_propios_sin_relleno_ni_color():
    # El color y el trazo los pone svg(); el cuerpo solo trae formas.
    for clave, ic in iconos.CATALOGO.items():
        raiz = ET.fromstring(f'<g xmlns="http://www.w3.org/2000/svg">{ic.cuerpo}</g>')
        for nodo in raiz:
            assert nodo.tag.split("}")[1] in FORMAS, clave
            assert not {"fill", "stroke", "stroke-width", "style"} & set(nodo.attrib), clave
        ET.fromstring(iconos.svg(clave, "#000000"))


def test_los_iconos_en_uso_son_los_de_la_aplicacion():
    en_uso = {c for c, ic in iconos.CATALOGO.items() if ic.en_uso}
    assert set(estilo.ICONOS_MENU) | set(arbol.ICONOS_ARBOL) | {
        "plantas",
        "subir",
        "bajar",
        "cargas_planta",
        *BotonesNavegacion.CLAVES,
        *(icono for icono, _ in dibujo.HERRAMIENTAS.values()),
        *(icono for icono, _ in dibujo_calculo.HERRAMIENTAS_CALCULO.values()),
        "cerrar",
        "desacoplar",
        "vista_alzado",
        "vista_3d",
    } == (en_uso)


@pytest.mark.parametrize("lado, px", [(16, 1.4), (18, 1.275), (20, 1.4167), (24, 1.7)])
def test_trazo_en_pixeles(lado, px):
    for clave in ("nudos", "archivo"):
        texto = iconos.svg(clave, "#000", lado)
        caja = float(re.search(r'viewBox="0 0 (\d+)', texto).group(1))
        ancho = float(re.search(r'stroke-width="([\d.]+)"', texto).group(1))
        assert ancho * lado / caja == pytest.approx(px, abs=1e-3)


def test_el_catalogo_dibuja_igual_que_antes(qapp):
    # Pasar los íconos al catálogo no cambia ni un píxel (árbol, barra lateral, modo Edificio).
    for escala in (1.0, 1.5, 2.0):
        for clave, cuerpo in arbol.ICONOS_ARBOL.items():
            antes = arbol._icono(cuerpo, "#4A5260", escala).toImage()
            assert iconos.pixmap(clave, "#4A5260", 16, escala).toImage() == antes, clave
        for clave, lado in (("plantas", 20), ("subir", 18), ("bajar", 18), ("ver", 24)):
            antes = ventana.icono_trazo(iconos.CATALOGO[clave].cuerpo, "#4A5260", lado, escala)
            assert iconos.pixmap(clave, "#4A5260", lado, escala).toImage() == antes.toImage()


def test_pixmap_y_qicon(qapp):
    pix = iconos.pixmap("vista_3d", "#2563EB", 20, 2.0)
    assert pix.width() == 40 and pix.devicePixelRatio() == 2.0
    imagen = pix.toImage()
    assert any(imagen.pixelColor(x, y).alpha() for x in range(40) for y in range(40))
    icono = iconos.qicon("vista_3d", estilo.OSCURO, 20)
    for modo, estado in (
        (QIcon.Normal, QIcon.Off),
        (QIcon.Normal, QIcon.On),
        (QIcon.Disabled, QIcon.Off),
    ):
        assert not icono.pixmap(20, 20, modo, estado).isNull()


def test_la_guia_lista_todo_el_catalogo():
    guia = (RAIZ / "docs" / "iconos.md").read_text(encoding="utf-8")
    for clave in iconos.CATALOGO:
        assert f"`{clave}`" in guia, clave
