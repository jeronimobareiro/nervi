# SPDX-License-Identifier: GPL-3.0-or-later
"""Paleta y hoja de estilos: interfaz clara, plana y sobria, un solo color de acento."""

from __future__ import annotations

FONDO = "#F3F4F6"
PANEL = "#FFFFFF"
BORDE = "#E2E5EA"
BORDE_SUAVE = "#EEF0F3"
HOVER = "#F1F3F6"
TEXTO = "#16181D"
TEXTO_2 = "#4B5563"
TEXTO_3 = "#6B7280"
ACENTO = "#1D4ED8"
ACENTO_SUAVE = "#E8EEFC"
POSITIVO = "#1D4ED8"
NEGATIVO = "#C2410C"
OK = "#15803D"
ESTRUCTURA = "#2B3038"

QSS = f"""
QMainWindow, QWidget#raiz {{ background: {FONDO}; }}
QWidget {{ color: {TEXTO}; font-size: 9.5pt; }}
QWidget#barra, QWidget#contexto, QWidget#panel, QStatusBar {{ background: {PANEL}; }}
QWidget#barra {{ border-bottom: 1px solid {BORDE}; }}
QWidget#contexto {{ border-bottom: 1px solid {BORDE}; }}
QLabel#titulo {{ font-weight: 600; }}
QLabel#tenue, QLabel#seccion {{ color: {TEXTO_3}; }}
QLabel#seccion {{ font-size: 8pt; font-weight: 600; letter-spacing: 0.5px; }}
QPushButton {{
    background: {PANEL}; border: 1px solid {BORDE}; border-radius: 5px;
    padding: 4px 10px; color: {TEXTO_2};
}}
QPushButton:hover {{ background: {HOVER}; color: {TEXTO}; }}
QPushButton:disabled {{ color: #A7AEBA; border-color: {BORDE_SUAVE}; }}
QPushButton#primario {{ background: {TEXTO}; color: white; border: 0; font-weight: 600; padding: 5px 14px; }}
QPushButton#primario:hover {{ background: #2B3038; }}
QPushButton#etapa {{ border: 0; border-radius: 5px; padding: 5px 10px; background: transparent; }}
QPushButton#etapa:checked {{ background: {HOVER}; color: {TEXTO}; font-weight: 600;
    border-bottom: 2px solid {ACENTO}; border-bottom-left-radius: 0; border-bottom-right-radius: 0; }}
QPushButton#segmento {{ border: 0; border-radius: 4px; padding: 4px 10px; background: transparent; }}
QPushButton#segmento:checked {{ background: {PANEL}; color: {TEXTO}; border: 1px solid #D5D9E0; }}
QWidget#grupo {{ background: {HOVER}; border-radius: 6px; }}
QPushButton#buscar {{ text-align: left; color: {TEXTO_3}; background: #F8F9FA; min-width: 210px; }}
QToolButton {{ border: 0; border-radius: 5px; padding: 4px; }}
QToolButton:hover {{ background: {HOVER}; }}
QToolButton::menu-indicator {{ image: none; }}
QComboBox, QLineEdit, QDoubleSpinBox, QSpinBox {{
    background: {PANEL}; border: 1px solid {BORDE}; border-radius: 4px; padding: 3px 6px;
    selection-background-color: {ACENTO_SUAVE}; selection-color: {TEXTO};
}}
QComboBox:focus, QLineEdit:focus {{ border-color: #93A9E8; }}
QTreeWidget, QListWidget, QTableView, QPlainTextEdit {{
    background: {PANEL}; border: 0; outline: 0;
    selection-background-color: {ACENTO_SUAVE}; selection-color: {ACENTO};
}}
QTreeWidget::item, QListWidget::item {{ padding: 3px 2px; }}
QTreeWidget::item:hover, QListWidget::item:hover {{ background: {HOVER}; }}
QHeaderView::section {{
    background: {PANEL}; color: {TEXTO_3}; border: 0; border-bottom: 1px solid {BORDE};
    padding: 4px 8px; font-weight: 600;
}}
QTableView {{ gridline-color: {BORDE_SUAVE}; }}
QTabWidget::pane {{ border: 0; border-top: 1px solid {BORDE_SUAVE}; background: {PANEL}; }}
QTabBar::tab {{
    background: transparent; color: {TEXTO_2}; padding: 7px 4px; margin-right: 16px;
    border: 0; border-bottom: 2px solid transparent;
}}
QTabBar::tab:selected {{ color: {TEXTO}; border-bottom-color: {ACENTO}; }}
QTabBar::tab:hover {{ color: {TEXTO}; }}
QSplitter::handle {{ background: {BORDE}; }}
QStatusBar {{ border-top: 1px solid {BORDE}; color: {TEXTO_2}; }}
QStatusBar QLabel {{ color: {TEXTO_2}; padding: 0 6px; }}
QLabel#etiqueta {{ border: 1px solid {BORDE}; border-radius: 3px; padding: 0 6px; }}
QScrollBar:vertical {{ background: transparent; width: 10px; }}
QScrollBar::handle:vertical {{ background: #D5D9E0; border-radius: 4px; min-height: 24px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; }}
QScrollBar::handle:horizontal {{ background: #D5D9E0; border-radius: 4px; min-width: 24px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QMenu {{ background: {PANEL}; border: 1px solid {BORDE}; padding: 4px; }}
QMenu::item {{ padding: 5px 24px 5px 12px; border-radius: 4px; }}
QMenu::item:selected {{ background: {ACENTO_SUAVE}; color: {TEXTO}; }}
QDialog#paleta {{ background: {PANEL}; border: 1px solid {BORDE}; border-radius: 8px; }}
"""
