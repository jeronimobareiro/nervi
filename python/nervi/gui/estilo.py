# SPDX-License-Identifier: GPL-3.0-or-later
"""Sistema de diseño de la interfaz: tokens de color y medida, hoja de estilos e íconos.

Un :class:`Tema` reúne los tokens (colores, radio de esquinas, alto de los controles).
:func:`qss` arma con ellos la hoja de estilos completa de Qt, y :func:`aplicar` la
instala en la aplicación entera, para que también los diálogos sueltos y los
desplegables abiertos tengan el mismo aspecto.

Hay que estilar **todas** las partes de los controles compuestos (la flecha del
desplegable, los botones del campo numérico, las casillas): si la hoja de estilos
define solo el borde y el fondo, Qt dibuja esas partes con el relieve biselado de
los estilos viejos. Las flechas y marcas son SVG que se generan con los colores
del tema.

Las constantes de módulo (``PANEL``, ``ACENTO``…) son las del tema claro y las usan
los dibujos propios (vista 2D, visor 3D, tablas).
"""

from __future__ import annotations

import hashlib
import tempfile
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QAbstractSpinBox, QApplication, QComboBox, QStyledItemDelegate


@dataclass(frozen=True)
class Tema:
    """Tokens de diseño. Los nombres describen el uso, no el color."""

    nombre: str
    fondo: str  # fondo de la ventana, detrás de los paneles
    panel: str  # paneles, tablas, menús
    campo: str  # fondo de los campos de texto, numéricos y desplegables
    borde: str
    borde_fuerte: str  # borde al pasar el mouse, casillas, barras de desplazamiento
    hover: str
    presionado: str
    texto: str
    texto_2: str  # texto secundario
    texto_3: str  # etiquetas tenues, encabezados de tabla
    deshabilitado: str
    acento: str  # selección, casillas marcadas, pestaña activa
    sobre_acento: str
    acento_suave: str  # fondo de filas y opciones elegidas
    foco: str  # borde del campo con el foco
    primario: str  # botón de la acción principal
    primario_hover: str
    sobre_primario: str
    ok: str
    negativo: str
    negativo_suave: str
    aviso_fondo: str
    aviso_borde: str
    aviso_texto: str
    # Dibujos propios (vista 2D, visor 3D)
    estructura: str = "#2B3038"
    positivo: str = "#1D4ED8"
    borde_suave: str = "#EEF0F3"
    oscuro: bool = False
    radio: int = 6
    alto: int = 28  # alto de campos y botones, en píxeles
    tamano: float = 9.5  # tamaño de letra, en puntos


CLARO = Tema(
    nombre="Claro",
    fondo="#F4F5F7",
    panel="#FFFFFF",
    campo="#FFFFFF",
    borde="#DFE3E8",
    borde_fuerte="#C5CBD3",
    hover="#F1F3F6",
    presionado="#E6E9EE",
    texto="#14171C",
    texto_2="#4A5260",
    texto_3="#6B7280",
    deshabilitado="#A9B0BB",
    acento="#2563EB",
    sobre_acento="#FFFFFF",
    acento_suave="#E7EEFD",
    foco="#2563EB",
    primario="#14171C",
    primario_hover="#2B3038",
    sobre_primario="#FFFFFF",
    ok="#15803D",
    negativo="#C2410C",
    negativo_suave="#FFF1EA",
    aviso_fondo="#FFF7ED",
    aviso_borde="#FED7AA",
    aviso_texto="#9A3412",
)

# Modo oscuro con los colores de la marca: azul marino de fondo y cian para el foco.
OSCURO = Tema(
    nombre="Oscuro",
    fondo="#0B132B",
    panel="#0F172A",
    campo="#131E36",
    borde="#1F2C47",
    borde_fuerte="#2A3A5C",
    hover="#16213A",
    presionado="#1B2945",
    texto="#DCE6F5",
    texto_2="#A9B8D0",
    texto_3="#7184A3",
    deshabilitado="#46597A",
    acento="#3B82F6",
    sobre_acento="#FFFFFF",
    acento_suave="#16305E",
    foco="#00E5FF",
    primario="#3B82F6",
    primario_hover="#60A5FA",
    sobre_primario="#FFFFFF",
    ok="#22C55E",
    negativo="#F97316",
    negativo_suave="#3A1E12",
    aviso_fondo="#2B2110",
    aviso_borde="#5C4314",
    aviso_texto="#FBBF24",
    estructura="#C9D6EA",
    positivo="#60A5FA",
    borde_suave="#141F38",
    oscuro=True,
)

TEMAS = {"claro": CLARO, "oscuro": OSCURO}

actual: Tema = CLARO


def _colores_de_dibujo(t: Tema) -> None:
    """Pasa el tema a las constantes que leen los dibujos propios (vista 2D, visor 3D, tablas)."""
    global FONDO, PANEL, BORDE, BORDE_SUAVE, HOVER, TEXTO, TEXTO_2, TEXTO_3, ACENTO
    global ACENTO_SUAVE, POSITIVO, NEGATIVO, OK, AVISO_FONDO, AVISO_BORDE, AVISO_TEXTO
    global ESTRUCTURA, DESHABILITADO
    FONDO, PANEL, BORDE, BORDE_SUAVE, HOVER = t.fondo, t.panel, t.borde, t.borde_suave, t.hover
    TEXTO, TEXTO_2, TEXTO_3 = t.texto, t.texto_2, t.texto_3
    ACENTO, ACENTO_SUAVE, POSITIVO, NEGATIVO, OK = (
        t.acento,
        t.acento_suave,
        t.positivo,
        t.negativo,
        t.ok,
    )
    AVISO_FONDO, AVISO_BORDE, AVISO_TEXTO = t.aviso_fondo, t.aviso_borde, t.aviso_texto
    ESTRUCTURA, DESHABILITADO = t.estructura, t.deshabilitado


_colores_de_dibujo(CLARO)

_TRAZOS = {
    "abajo": '<path d="M3.5 6l4.5 4.5L12.5 6" fill="none" stroke="{c}" stroke-width="1.6" '
    'stroke-linecap="round" stroke-linejoin="round"/>',
    "arriba": '<path d="M3.5 10l4.5-4.5L12.5 10" fill="none" stroke="{c}" stroke-width="1.6" '
    'stroke-linecap="round" stroke-linejoin="round"/>',
    "check": '<path d="M3.5 8.3l3 3 6-6.6" fill="none" stroke="{c}" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round"/>',
    "guion": '<path d="M4 8h8" stroke="{c}" stroke-width="2" stroke-linecap="round"/>',
    "punto": '<circle cx="8" cy="8" r="3.2" fill="{c}"/>',
}


def svg(forma: str, color: str) -> str:
    """Ícono de 16×16 de las partes de los controles (flechas, marca de casilla, punto)."""
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">'
        + _TRAZOS[forma].format(c=color)
        + "</svg>"
    )


#: Íconos de la barra lateral de menús: trazos propios de 24 por 24 px con línea de 1,7 px,
#: el mismo estilo fino de las flechas de los controles.
ICONOS_MENU = {
    "archivo": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/>'
    '<path d="M14 3v5h5"/>',
    # Editar: flecha de deshacer.
    "editar": '<path d="M9 14L4 9l5-5"/><path d="M4 9h10.5a5.5 5.5 0 0 1 0 11H11"/>',
    "modelo": '<path d="M5 20V6h14v14"/><path d="M3 20h4M17 20h4"/><path d="M5 13h14"/>',
    "calcular": '<path d="M7 4l13 8-13 8z"/>',
    "ver": '<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
    "herramientas": '<path d="M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18l3 3 6.3-6.3a4 4 0 0 0 '
    '5.4-5.4l-2.5 2.5-2.4-.6-.6-2.4z"/>',
    "ayuda": '<circle cx="12" cy="12" r="9"/><path d="M9.5 9.2a2.6 2.6 0 1 1 3.6 2.4c-.7.3-1.1.9-1.1 1.6"/>'
    '<path d="M12 17h.01"/>',
    "preferencias": '<path d="M4 6h9M17 6h3M4 12h3M11 12h9M4 18h11M19 18h1"/>'
    '<circle cx="15" cy="6" r="2"/><circle cx="9" cy="12" r="2"/><circle cx="17" cy="18" r="2"/>',
    # Asistente de IA: una chispa grande y una chica.
    "ia": '<path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z"/>'
    '<path d="M18.5 15l.7 1.8 1.8.7-1.8.7-.7 1.8-.7-1.8-1.8-.7 1.8-.7z"/>',
}


def svg_menu(nombre: str, color: str) -> str:
    """Ícono de 24 por 24 px de la barra lateral de menús, en el color pedido."""
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" '
        f'fill="none" stroke="{color}" stroke-width="1.7" stroke-linecap="round" '
        f'stroke-linejoin="round">{ICONOS_MENU[nombre]}</svg>'
    )


def con_tamano(tema: Tema, tamano: float) -> Tema:
    """El mismo tema con otro tamaño de letra (preferencia *Tamaño de letra*)."""
    return tema if tema.tamano == tamano else replace(tema, tamano=tamano)


def _carpeta_tema(tema: Tema) -> Path:
    clave = hashlib.sha1(repr(asdict(tema)).encode()).hexdigest()[:12]
    return Path(tempfile.gettempdir()) / f"nervi-tema-{clave}"


def iconos_menu(tema: Tema, carpeta: Path | None = None) -> dict[str, str]:
    """Escribe los íconos de la barra lateral y devuelve sus rutas.

    Cada ícono va en dos colores: ``<nombre>`` (texto secundario) y
    ``<nombre>_activo`` (acento, mientras su menú está abierto)."""
    carpeta = carpeta if carpeta is not None else _carpeta_tema(tema)
    carpeta.mkdir(parents=True, exist_ok=True)
    rutas = {}
    for nombre in ICONOS_MENU:
        for sufijo, color in (("", tema.texto_2), ("_activo", tema.acento)):
            ruta = carpeta / f"menu-{nombre}{sufijo}.svg"
            contenido = svg_menu(nombre, color)
            if not ruta.is_file() or ruta.read_text(encoding="utf-8") != contenido:
                ruta.write_text(contenido, encoding="utf-8")
            rutas[nombre + sufijo] = ruta.as_posix()
    return rutas


def iconos(tema: Tema, carpeta: Path | None = None) -> dict[str, str]:
    """Escribe los íconos del tema y devuelve sus rutas, con ``/`` como pide Qt.

    Van a una carpeta temporal propia de cada tema: la hoja de estilos de Qt solo
    toma imágenes desde archivos o recursos compilados.
    """
    if carpeta is None:
        carpeta = _carpeta_tema(tema)
    carpeta.mkdir(parents=True, exist_ok=True)
    pedidos = {
        "abajo": ("abajo", tema.texto_2),
        "abajo_off": ("abajo", tema.deshabilitado),
        "arriba": ("arriba", tema.texto_2),
        "arriba_off": ("arriba", tema.deshabilitado),
        "check": ("check", tema.sobre_acento),
        "guion": ("guion", tema.sobre_acento),
        "punto": ("punto", tema.sobre_acento),
    }
    rutas = {}
    for nombre, (forma, color) in pedidos.items():
        ruta = carpeta / f"{nombre}.svg"
        contenido = svg(forma, color)
        if not ruta.is_file() or ruta.read_text(encoding="utf-8") != contenido:
            ruta.write_text(contenido, encoding="utf-8")
        rutas[nombre] = ruta.as_posix()
    return rutas


def qss(tema: Tema = CLARO, rutas: dict[str, str] | None = None) -> str:
    """Hoja de estilos completa para el tema."""
    t = tema
    i = rutas if rutas is not None else iconos(t)
    r = t.radio
    rc = max(r - 2, 2)  # radio de lo que va dentro de otro control
    pv = max((t.alto - 18) // 2 - 1, 2)  # relleno vertical de campos y botones
    alto_int = t.alto - 2 * pv - 2  # alto del contenido
    return f"""
* {{ font-size: {t.tamano}pt; }}
QMainWindow, QWidget#raiz, QDialog, QMessageBox {{ background: {t.fondo}; }}
QWidget {{ color: {t.texto}; }}
QWidget#barra, QWidget#contexto, QWidget#panel, QStatusBar {{ background: {t.panel}; }}
QWidget#barra, QWidget#contexto {{ border-bottom: 1px solid {t.borde}; }}
QLabel {{ background: transparent; }}
QLabel#titulo {{ font-weight: 600; }}
QLabel#tenue {{ color: {t.texto_3}; }}
QLabel#seccion {{ color: {t.texto_3}; font-size: {t.tamano - 1.5}pt; font-weight: 600; letter-spacing: 0.5px; }}

/* Botones */
QPushButton {{
    background: {t.panel}; border: 1px solid {t.borde}; border-radius: {r}px;
    padding: {pv}px 12px; min-height: {alto_int}px; color: {t.texto_2};
}}
QPushButton:hover {{ background: {t.hover}; border-color: {t.borde_fuerte}; color: {t.texto}; }}
QPushButton:pressed {{ background: {t.presionado}; }}
QPushButton:checked {{ background: {t.acento_suave}; border-color: {t.acento_suave}; color: {t.texto}; }}
QPushButton:focus {{ border-color: {t.foco}; }}
QPushButton:disabled {{ color: {t.deshabilitado}; background: {t.panel}; border-color: {t.borde}; }}
QPushButton#primario {{
    background: {t.primario}; color: {t.sobre_primario}; border: 1px solid {t.primario};
    font-weight: 600; padding-left: 16px; padding-right: 16px;
}}
QPushButton#primario:hover {{ background: {t.primario_hover}; border-color: {t.primario_hover}; }}
QPushButton#primario:disabled {{ background: {t.presionado}; border-color: {t.presionado}; color: {t.deshabilitado}; }}
QPushButton#fantasma {{ background: transparent; border-color: transparent; }}
QPushButton#fantasma:hover {{ background: {t.hover}; }}
QPushButton#peligro {{ color: {t.negativo}; }}
QPushButton#peligro:hover {{ background: {t.negativo_suave}; border-color: {t.negativo}; }}
QToolButton {{ background: transparent; border: 1px solid transparent; border-radius: {r}px; padding: 4px; }}
QToolButton:hover {{ background: {t.hover}; }}
QToolButton:pressed, QToolButton:checked {{ background: {t.presionado}; }}
QToolButton::menu-indicator {{ image: none; }}

/* Control segmentado, etapas y buscador */
QWidget#grupo {{ background: {t.hover}; border-radius: {r}px; }}
QPushButton#segmento {{
    background: transparent; border: 1px solid transparent; border-radius: {rc}px;
    padding: {max(pv - 2, 1)}px 10px; min-height: {alto_int - 2}px;
}}
QPushButton#segmento:hover {{ color: {t.texto}; }}
QPushButton#segmento:checked {{ background: {t.panel}; color: {t.texto}; border-color: {t.borde}; font-weight: 600; }}
QPushButton#etapa {{ border: 0; border-radius: {r}px; padding: 5px 10px; background: transparent; }}
QPushButton#etapa:hover {{ background: {t.hover}; color: {t.texto}; }}
QPushButton#etapa:checked {{
    background: {t.hover}; color: {t.texto}; font-weight: 600; border-bottom: 2px solid {t.acento};
    border-bottom-left-radius: 0; border-bottom-right-radius: 0;
}}
QPushButton#buscar {{ text-align: left; color: {t.texto_3}; background: {t.fondo}; min-width: 210px; }}

/* Campos de texto, numéricos y desplegables */
QLineEdit, QComboBox, QAbstractSpinBox {{
    background: {t.campo}; border: 1px solid {t.borde}; border-radius: {r}px;
    padding: {pv}px 8px; min-height: {alto_int}px; color: {t.texto};
    selection-background-color: {t.acento}; selection-color: {t.sobre_acento};
}}
QLineEdit:hover, QComboBox:hover, QAbstractSpinBox:hover {{ border-color: {t.borde_fuerte}; }}
QLineEdit:focus, QComboBox:focus, QComboBox:on, QAbstractSpinBox:focus {{ border-color: {t.foco}; }}
QLineEdit:disabled, QComboBox:disabled, QAbstractSpinBox:disabled {{ color: {t.deshabilitado}; background: {t.fondo}; }}
QLineEdit[error="true"], QAbstractSpinBox[error="true"] {{ border-color: {t.negativo}; }}

QComboBox::drop-down {{
    subcontrol-origin: padding; subcontrol-position: center right;
    width: 24px; border: 0; background: transparent;
}}
QComboBox::down-arrow {{ image: url({i["abajo"]}); width: 12px; height: 12px; }}
QComboBox::down-arrow:disabled {{ image: url({i["abajo_off"]}); }}
/* La lista abierta es una ventana aparte y siempre rectangular: con esquinas
   redondeadas asomarían sus esquinas. Va recta, con borde en los cuatro lados. */
QComboBoxPrivateContainer {{ background: {t.panel}; border: 1px solid {t.borde_fuerte}; border-radius: 0; padding: 0; }}
QComboBox QAbstractItemView {{
    background: {t.panel}; border: 0; padding: 4px; outline: 0;
    selection-background-color: {t.acento_suave}; selection-color: {t.texto};
}}
QComboBox QAbstractItemView::item {{ min-height: {t.alto - 4}px; padding: 0 8px; border-radius: {rc}px; color: {t.texto}; }}
QComboBox QAbstractItemView::item:hover, QComboBox QAbstractItemView::item:selected {{
    background: {t.acento_suave}; color: {t.texto};
}}

QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {{
    subcontrol-origin: border; width: 20px; border: 0; background: transparent; margin-right: 2px;
}}
QAbstractSpinBox::up-button {{ subcontrol-position: top right; margin-top: 2px; border-top-right-radius: {rc}px; }}
QAbstractSpinBox::down-button {{ subcontrol-position: bottom right; margin-bottom: 2px; border-bottom-right-radius: {rc}px; }}
QAbstractSpinBox::up-button:hover, QAbstractSpinBox::down-button:hover {{ background: {t.hover}; }}
QAbstractSpinBox::up-arrow {{ image: url({i["arriba"]}); width: 10px; height: 10px; }}
QAbstractSpinBox::down-arrow {{ image: url({i["abajo"]}); width: 10px; height: 10px; }}
QAbstractSpinBox::up-arrow:disabled, QAbstractSpinBox::up-arrow:off {{ image: url({i["arriba_off"]}); }}
QAbstractSpinBox::down-arrow:disabled, QAbstractSpinBox::down-arrow:off {{ image: url({i["abajo_off"]}); }}

/* Casillas, opciones y deslizador */
QCheckBox, QRadioButton {{ spacing: 8px; background: transparent; }}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 14px; height: 14px; border: 1px solid {t.borde_fuerte}; background: {t.campo};
}}
QCheckBox::indicator {{ border-radius: {min(rc, 4)}px; }}
QRadioButton::indicator {{ border-radius: 8px; }}
QCheckBox::indicator:hover, QRadioButton::indicator:hover {{ border-color: {t.acento}; }}
QCheckBox::indicator:checked {{ background: {t.acento}; border-color: {t.acento}; image: url({i["check"]}); }}
QCheckBox::indicator:indeterminate {{ background: {t.acento}; border-color: {t.acento}; image: url({i["guion"]}); }}
QRadioButton::indicator:checked {{ background: {t.acento}; border-color: {t.acento}; image: url({i["punto"]}); }}
QCheckBox::indicator:disabled, QRadioButton::indicator:disabled {{ background: {t.fondo}; border-color: {t.borde}; }}
QCheckBox:disabled, QRadioButton:disabled {{ color: {t.deshabilitado}; }}
QSlider:horizontal {{ min-height: 20px; background: transparent; }}
QSlider::groove:horizontal {{ height: 4px; background: {t.borde}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {t.acento}; border-radius: 2px; }}
QSlider::handle:horizontal {{
    width: 8px; margin: -7px 0; border-radius: 2px;
    background: {t.acento}; border: 1px solid {t.acento};
}}
QSlider::handle:horizontal:hover {{ background: {t.primario_hover if t.oscuro else t.acento}; border-color: {t.foco}; }}
QSlider::handle:horizontal:disabled {{ background: {t.deshabilitado}; border-color: {t.deshabilitado}; }}

/* Pestañas */
QTabWidget::pane {{ border: 0; border-top: 1px solid {t.borde}; background: {t.panel}; }}
QTabBar {{ qproperty-drawBase: 0; }}
QTabBar::tab {{
    background: transparent; color: {t.texto_2}; padding: 7px 4px; margin-right: 16px;
    border: 0; border-bottom: 2px solid transparent;
}}
QTabBar::tab:hover {{ color: {t.texto}; }}
QTabBar::tab:selected {{ color: {t.texto}; border-bottom-color: {t.acento}; font-weight: 600; }}

/* Tablas, listas y árboles */
QTreeView, QListView, QTableView, QPlainTextEdit {{
    background: {t.panel}; border: 0; outline: 0; alternate-background-color: {t.fondo};
    selection-background-color: {t.acento_suave}; selection-color: {t.texto};
}}
QTableView {{ gridline-color: {t.borde}; }}
QTableView::item:selected {{ background: {t.acento_suave}; color: {t.texto}; }}
QTreeView::item, QListView::item {{ padding: 3px 2px; }}
QTreeView::item:hover, QListView::item:hover {{ background: {t.hover}; }}
QTreeView::item:selected, QListView::item:selected {{ background: {t.acento_suave}; color: {t.acento}; }}
QHeaderView {{ background: {t.panel}; }}
QHeaderView::section {{
    background: {t.panel}; color: {t.texto_3}; border: 0; border-bottom: 1px solid {t.borde};
    padding: 4px 8px; font-weight: 600;
}}
QTableCornerButton::section {{ background: {t.panel}; border: 0; border-bottom: 1px solid {t.borde}; }}

/* Barras de desplazamiento */
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 1px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 1px; }}
QScrollBar::handle {{ background: {t.borde_fuerte}; border-radius: 4px; }}
QScrollBar::handle:vertical {{ min-height: 24px; }}
QScrollBar::handle:horizontal {{ min-width: 24px; }}
QScrollBar::handle:hover {{ background: {t.texto_3}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* Menús, ayudas, avisos y separadores */
QMenu {{ background: {t.panel}; border: 1px solid {t.borde}; border-radius: {r}px; padding: 4px; }}
QMenu::item {{ padding: 5px 24px 5px 12px; border-radius: {rc}px; color: {t.texto}; }}
QMenu::item:selected {{ background: {t.acento_suave}; }}
QMenu::item:disabled {{ color: {t.deshabilitado}; }}
QMenu::separator {{ height: 1px; background: {t.borde}; margin: 4px 6px; }}
QToolTip {{ background: {t.texto}; color: {t.panel}; border: 0; border-radius: {rc}px; padding: 4px 8px; }}
QLabel#aviso {{
    background: {t.aviso_fondo}; color: {t.aviso_texto}; border: 1px solid {t.aviso_borde};
    border-radius: {r}px; padding: 4px 8px;
}}
QLabel#etiqueta {{ border: 1px solid {t.borde}; border-radius: {rc}px; padding: 0 6px; }}
QSplitter::handle {{ background: {t.borde}; }}
QStatusBar {{ border-top: 1px solid {t.borde}; color: {t.texto_2}; }}
QStatusBar QLabel {{ color: {t.texto_2}; padding: 0 6px; }}
QProgressBar {{ background: {t.hover}; border: 0; border-radius: 3px; color: transparent; max-height: 6px; }}
QProgressBar::chunk {{ background: {t.acento}; border-radius: 3px; }}
QDialog#paleta {{ background: {t.panel}; border: 1px solid {t.borde}; border-radius: 8px; }}

/* Barra lateral de menús */
QWidget#riel {{ background: {t.panel}; border-right: 1px solid {t.borde}; }}
QToolButton#menu_riel {{ border-radius: {r}px; padding: 0; }}
QToolButton#menu_riel:hover {{ background: {t.hover}; }}
QToolButton#menu_riel:checked {{ background: {t.acento_suave}; }}
QLabel#insignia {{
    background: {t.acento}; color: {t.sobre_acento}; border-radius: 7px;
    font-size: {t.tamano - 2.5}pt; font-weight: 600;
}}

/* Panel del asistente de IA */
QFrame#tarjeta {{ background: {t.panel}; border: 1px solid {t.borde}; border-radius: {r}px; }}
QFrame#tarjeta[pendiente="true"] {{ background: {t.acento_suave}; border-color: {t.acento}; }}
QFrame#tarjeta QLabel {{ background: transparent; }}
QLabel#conexion {{ border: 1px solid {t.borde_fuerte}; color: {t.texto_3}; border-radius: {rc}px; padding: 1px 6px; }}
QLabel#conexion[conectado="true"] {{ border-color: {t.ok}; color: {t.ok}; }}
QLabel#codigo {{ font-family: "JetBrains Mono", "Cascadia Mono", Consolas, monospace; color: {t.texto_2}; }}
QLabel#bien {{ color: {t.ok}; }}
QLabel#mal {{ color: {t.negativo}; }}

/* Ventanas de ajustes (Preferencias, Configuración del proyecto) */
QListWidget#apartados {{ background: {t.panel}; border: 0; border-right: 1px solid {t.borde}; padding: 8px; }}
QListWidget#apartados::item {{ padding: 6px 10px; border-radius: {rc}px; }}
QWidget#pagina_ajustes {{ background: {t.fondo}; }}
QWidget#caja_ajustes {{ background: {t.panel}; border: 1px solid {t.borde}; border-radius: {r}px; }}
QWidget#pie_ajustes {{ background: {t.panel}; border-top: 1px solid {t.borde}; }}

/* Árbol del modelo (panel Estructura): el delegado de arbol.py dibuja las filas */
QLabel#titulo_arbol {{ font-weight: 600; font-size: {t.tamano + 1}pt; color: {t.texto}; }}
QTreeView#arbol_modelo {{ border-top: 1px solid {t.borde}; }}
QTreeView#arbol_modelo::item, QTreeView#arbol_modelo::item:hover,
QTreeView#arbol_modelo::item:selected {{ background: transparent; padding: 0; border: 0; }}
"""


MARGEN_TEXTO_NUMERICO = 5  # px entre el borde y el número


class _Pulidor(QObject):
    """Ajustes que la hoja de estilos sola no alcanza.

    - A cada desplegable le da un delegado que respeta la hoja de estilos: el de
      Fusion dibuja las opciones como un menú y no toma el alto, el relleno ni el
      color de selección de ``QAbstractItemView::item``.
    - A los campos numéricos les da margen izquierdo al texto: Qt no aplica a su
      campo interno el ``padding`` de ``QAbstractSpinBox``.
    """

    def eventFilter(self, objeto: QObject, evento: QEvent) -> bool:
        if evento.type() == QEvent.Polish and isinstance(objeto, QComboBox):
            if not isinstance(objeto.itemDelegate(), QStyledItemDelegate):
                objeto.setItemDelegate(QStyledItemDelegate(objeto))
        elif evento.type() == QEvent.Polish and isinstance(objeto, QAbstractSpinBox):
            objeto.lineEdit().setTextMargins(MARGEN_TEXTO_NUMERICO, 0, 0, 0)
        return False


_pulidor: _Pulidor | None = None


def aplicar(app: QApplication | None = None, tema: Tema = CLARO) -> None:
    """Instala el estilo Fusion, la hoja de estilos del tema y el ajuste de desplegables.

    Se puede llamar más de una vez: si la hoja ya está, no la vuelve a cargar.
    """
    global _pulidor, actual
    actual = tema
    _colores_de_dibujo(tema)
    app = app or QApplication.instance()
    if app is None:
        return
    if _pulidor is None or _pulidor.parent() is not app:
        app.setStyle("Fusion")
        _pulidor = _Pulidor(app)
        app.installEventFilter(_pulidor)
    hoja = qss(tema)
    if app.styleSheet() != hoja:
        app.setStyleSheet(hoja)
