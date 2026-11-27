# SPDX-License-Identifier: GPL-3.0-or-later
"""Catálogo de íconos de la interfaz de Nervi.

Es la fuente única de los íconos de la aplicación: los que ya se usan (barra lateral,
árbol del modelo, modo Edificio) y los reservados para las fases de la hoja de ruta, para
que cada aporte tome su ícono de acá en vez de dibujar uno propio. La guía de uso y la
lámina con todos los íconos están en ``docs/iconos.md``.

Reglas de la familia (las mismas de la barra lateral, aprobadas el 19/11/2026):

- Dibujos propios sobre una grilla de 24 por 24 (``viewBox="0 0 24 24"``), con margen de
  2 unidades, solo trazo, sin relleno, puntas y uniones redondeadas. Los íconos del árbol
  del modelo conservan su grilla original de 16 (campo ``rejilla``).
- Trazo de 1,7 unidades de la grilla; a 16 px o menos se engrosa a 2,1 unidades para que
  la línea siga midiendo 1,4 px, como los íconos del árbol del modelo.
- El color lo pone quien lo usa, siempre desde el tema de :mod:`nervi.gui.estilo`: en
  reposo ``texto_2``, activo o elegido ``acento``, deshabilitado ``deshabilitado``.
- No se copian íconos de otros programas (``AGENTS.md`` §4).

Uso::

    from nervi.gui import estilo, iconos

    boton.setIcon(iconos.qicon("vista_3d", estilo.actual, 20, boton.devicePixelRatioF()))
    etiqueta.setPixmap(iconos.pixmap("aviso", estilo.AVISO_TEXTO, 16, 2.0))
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtGui import QIcon, QPixmap

    from .estilo import Tema


@dataclass(frozen=True)
class Icono:
    """Un ícono del catálogo."""

    clave: str
    nombre: str  # para la ayuda emergente y el nombre accesible
    grupo: str
    cuerpo: str  # trazos SVG sobre la grilla de 24
    uso: str  # dónde se usa o qué fase o issue lo necesita
    en_uso: bool = False  # True si la aplicación ya lo muestra
    #: Grilla del dibujo. Los íconos nuevos van en 24; los del árbol del modelo conservan
    #: su grilla original de 16 para que se vean exactamente igual que antes del catálogo.
    rejilla: int = 24


#: Grupos del catálogo, en el orden de la lámina.
GRUPOS = (
    "Menús",
    "Archivo y edición",
    "Vista y navegación",
    "Modelo de cálculo",
    "Modelo físico",
    "Cargas",
    "Análisis y resultados",
    "Diseño de hormigón",
    "Diseño de acero y mixtas",
    "Documentos e intercambio",
    "Estados",
)

_HOJA = (
    '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/>'
)
_BANDEJA = '<path d="M4 15v4a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-4"/>'
_LUPA = '<circle cx="10.5" cy="10.5" r="6.5"/><path d="M15.2 15.2L20.5 20.5"/>'
_OJO = '<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>'

_I = Icono
_LISTA = (
    # --- Menús de la barra lateral (en uso desde el 19/11/2026) ---
    _I("archivo", "Archivo", "Menús", _HOJA, "Barra lateral", True),
    _I(
        "editar",
        "Editar",
        "Menús",
        '<path d="M9 14L4 9l5-5"/><path d="M4 9h10.5a5.5 5.5 0 0 1 0 11H11"/>',
        "Barra lateral (flecha de deshacer)",
        True,
    ),
    _I(
        "modelo",
        "Modelo",
        "Menús",
        '<path d="M5 20V6h14v14"/><path d="M3 20h4M17 20h4"/><path d="M5 13h14"/>',
        "Barra lateral",
        True,
    ),
    _I("calcular", "Calcular", "Menús", '<path d="M7 4l13 8-13 8z"/>', "Barra lateral", True),
    _I("ver", "Ver", "Menús", _OJO, "Barra lateral", True),
    _I(
        "herramientas",
        "Herramientas",
        "Menús",
        '<path d="M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18l3 3 6.3-6.3a4 4 0 0 0 '
        '5.4-5.4l-2.5 2.5-2.4-.6-.6-2.4z"/>',
        "Barra lateral",
        True,
    ),
    _I(
        "ia",
        "Asistente de IA",
        "Menús",
        '<path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z"/>'
        '<path d="M18.5 15l.7 1.8 1.8.7-1.8.7-.7 1.8-.7-1.8-1.8-.7 1.8-.7z"/>',
        "Barra lateral",
        True,
    ),
    _I(
        "ayuda",
        "Ayuda",
        "Menús",
        '<circle cx="12" cy="12" r="9"/>'
        '<path d="M9.5 9.2a2.6 2.6 0 1 1 3.6 2.4c-.7.3-1.1.9-1.1 1.6"/>'
        '<path d="M12 17h.01"/>',
        "Barra lateral",
        True,
    ),
    _I(
        "preferencias",
        "Preferencias",
        "Menús",
        '<path d="M4 6h9M17 6h3M4 12h3M11 12h9M4 18h11M19 18h1"/>'
        '<circle cx="15" cy="6" r="2"/><circle cx="9" cy="12" r="2"/>'
        '<circle cx="17" cy="18" r="2"/>',
        "Barra lateral",
        True,
    ),
    # --- Archivo y edición ---
    _I(
        "nuevo", "Nuevo", "Archivo y edición", _HOJA + '<path d="M12 11v6M9 14h6"/>', "Menú Archivo"
    ),
    _I(
        "abrir",
        "Abrir",
        "Archivo y edición",
        '<path d="M3 19V6a1 1 0 0 1 1-1h5l2 2h7a1 1 0 0 1 1 1v3"/><path d="M3 19l3-8h15.5l-3 8z"/>',
        "Menú Archivo",
    ),
    _I(
        "guardar",
        "Guardar",
        "Archivo y edición",
        '<path d="M5 3h11l4 4v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a1 1 0 0 1 1-1z"/>'
        '<path d="M8 3v5h7V3"/><path d="M7.5 21v-6.5h9V21"/>',
        "Menú Archivo",
    ),
    _I(
        "importar",
        "Importar",
        "Archivo y edición",
        '<path d="M12 3v11"/><path d="M8 10l4 4 4-4"/>' + _BANDEJA,
        "Menú Archivo: DXF, IFC (#25, #75)",
    ),
    _I(
        "exportar",
        "Exportar",
        "Archivo y edición",
        '<path d="M12 14V3"/><path d="M8 7l4-4 4 4"/>' + _BANDEJA,
        "Menú Archivo: IFC, DXF, PDF (#29, #95, #98)",
    ),
    _I(
        "imprimir",
        "Imprimir",
        "Archivo y edición",
        '<path d="M7 9V3h10v6"/><path d="M7 17H4.5A1.5 1.5 0 0 1 3 15.5v-5A1.5 1.5 0 0 1 4.5 9h15'
        'a1.5 1.5 0 0 1 1.5 1.5v5a1.5 1.5 0 0 1-1.5 1.5H17"/><path d="M7 14h10v7H7z"/>',
        "Memoria y láminas (#28, #95)",
    ),
    _I(
        "deshacer",
        "Deshacer",
        "Archivo y edición",
        '<path d="M9 14L4 9l5-5"/><path d="M4 9h10.5a5.5 5.5 0 0 1 0 11H11"/>',
        "Edición gráfica (#31)",
    ),
    _I(
        "rehacer",
        "Rehacer",
        "Archivo y edición",
        '<path d="M15 14l5-5-5-5"/><path d="M20 9H9.5a5.5 5.5 0 0 0 0 11H13"/>',
        "Edición gráfica (#31)",
    ),
    _I(
        "copiar",
        "Copiar",
        "Archivo y edición",
        '<rect x="8.5" y="8.5" width="12" height="12" rx="1.5"/>'
        '<path d="M15.5 8.5V5A1.5 1.5 0 0 0 14 3.5H5A1.5 1.5 0 0 0 3.5 5v9'
        'A1.5 1.5 0 0 0 5 15.5h3.5"/>',
        "Edición gráfica, copiar plantas (#31, #73)",
    ),
    _I(
        "borrar",
        "Borrar",
        "Archivo y edición",
        '<path d="M4 6.5h16"/><path d="M9.5 6.5V4h5v2.5"/><path d="M6 6.5L7 20h10l1-13.5"/>'
        '<path d="M10 10.5v6M14 10.5v6"/>',
        "Tablas y edición gráfica (#31)",
    ),
    _I(
        "agregar", "Agregar", "Archivo y edición", '<path d="M12 5v14M5 12h14"/>', "Tablas y listas"
    ),
    _I("quitar", "Quitar", "Archivo y edición", '<path d="M5 12h14"/>', "Tablas y listas"),
    _I(
        "cerrar",
        "Cerrar",
        "Archivo y edición",
        '<path d="M6 6l12 12M18 6L6 18"/>',
        "Paneles y diálogos",
    ),
    _I("buscar", "Buscar", "Archivo y edición", _LUPA, "Paleta de comandos, tablas"),
    _I(
        "subir",
        "Subir",
        "Archivo y edición",
        '<path d="M6 15l6-6 6 6"/>',
        "Modo Edificio: subir una planta",
        True,
    ),
    _I(
        "bajar",
        "Bajar",
        "Archivo y edición",
        '<path d="M6 9l6 6 6-6"/>',
        "Modo Edificio: bajar una planta",
        True,
    ),
    # --- Vista y navegación ---
    _I(
        "seleccionar",
        "Seleccionar",
        "Vista y navegación",
        '<path d="M5.5 3.5l13 7-5.8 1.6-2.2 5.9z"/><path d="M12.8 12.2l5.2 6.3"/>',
        "Edición gráfica (#31)",
    ),
    _I(
        "desplazar",
        "Desplazar",
        "Vista y navegación",
        '<path d="M12 3v18M3 12h18"/><path d="M9.5 5.5L12 3l2.5 2.5M9.5 18.5L12 21l2.5-2.5'
        'M5.5 9.5L3 12l2.5 2.5M18.5 9.5L21 12l-2.5 2.5"/>',
        "Visor 3D y planta (#30)",
    ),
    _I(
        "orbitar",
        "Orbitar",
        "Vista y navegación",
        '<path d="M12 8a9 4 0 1 1-9 4"/><path d="M1.3 13.8L3 12l1.7 1.8"/>'
        '<circle cx="12" cy="12" r="1.6"/>',
        "Visor 3D (#30)",
    ),
    _I(
        "acercar",
        "Acercar",
        "Vista y navegación",
        _LUPA + '<path d="M10.5 8v5M8 10.5h5"/>',
        "Visor 3D y planta (#30)",
    ),
    _I(
        "alejar",
        "Alejar",
        "Vista y navegación",
        _LUPA + '<path d="M8 10.5h5"/>',
        "Visor 3D y planta (#30)",
    ),
    _I(
        "encuadrar",
        "Encuadrar todo",
        "Vista y navegación",
        '<path d="M4 9V4h5M15 4h5v5M20 15v5h-5M9 20H4v-5"/>'
        '<rect x="8.5" y="8.5" width="7" height="7" rx="0.6"/>',
        "Visor 3D y planta (#30)",
    ),
    _I(
        "vista_3d",
        "Vista 3D",
        "Vista y navegación",
        '<path d="M4 8.5h11v11.5H4z"/><path d="M4 8.5L8.5 4H20v11.5L15 20M15 8.5L20 4"/>',
        "Visor 3D (#30)",
    ),
    _I(
        "vista_planta",
        "Vista en planta",
        "Vista y navegación",
        '<rect x="3.5" y="3.5" width="17" height="17" rx="1"/>'
        '<path d="M6.5 6.5h2.5v2.5H6.5zM15 6.5h2.5v2.5H15z'
        'M6.5 15h2.5v2.5H6.5zM15 15h2.5v2.5H15z"/>',
        "Modo Edificio y visor (#30, #73)",
    ),
    _I(
        "vista_alzado",
        "Vista en alzado",
        "Vista y navegación",
        '<path d="M4 20V5h16v15M12 5v15M4 12.5h16"/><path d="M2.5 20h19"/>',
        "Modo Edificio y visor (#30, #73)",
    ),
    _I(
        "rejilla",
        "Rejilla",
        "Vista y navegación",
        '<rect x="3.5" y="3.5" width="17" height="17" rx="1"/>'
        '<path d="M3.5 9.2h17M3.5 14.8h17M9.2 3.5v17M14.8 3.5v17"/>',
        "Edición gráfica (#31)",
    ),
    _I(
        "capas",
        "Capas",
        "Vista y navegación",
        '<path d="M12 4l9 4.5-9 4.5-9-4.5z"/><path d="M3 12.5l9 4.5 9-4.5"/>'
        '<path d="M3 16.5l9 4.5 9-4.5"/>',
        "Capas del plano DXF (#75)",
    ),
    _I(
        "medir",
        "Medir",
        "Vista y navegación",
        '<path d="M3.5 16.5l13-13 4 4-13 13z"/><path d="M7.5 12.5l2 2M10.5 9.5l2 2M13.5 6.5l2 2"/>',
        "Edición gráfica (#31)",
    ),
    _I(
        "cotas",
        "Cotas",
        "Vista y navegación",
        '<path d="M4 6v12M20 6v12M4 12h16"/>'
        '<path d="M7 9.5L4.5 12 7 14.5M17 9.5l2.5 2.5-2.5 2.5"/>',
        "Planta y láminas (#95)",
    ),
    _I(
        "ocultar",
        "Ocultar",
        "Vista y navegación",
        _OJO + '<path d="M4 20L20 4"/>',
        "Árbol del modelo y capas",
    ),
    # --- Modelo de cálculo (árbol del modelo, en uso) ---
    _I(
        "nudos",
        "Nudos",
        "Modelo de cálculo",
        '<circle cx="8" cy="8" r="2.6"/><path d="M8 1.8v2.4M8 11.8v2.4M1.8 8h2.4M11.8 8h2.4"/>',
        "Árbol del modelo",
        True,
        16,
    ),
    _I(
        "barras",
        "Barras",
        "Modelo de cálculo",
        '<path d="M4.6 11.4l6.8-6.8"/><circle cx="3.4" cy="12.6" r="1.7"/>'
        '<circle cx="12.6" cy="3.4" r="1.7"/>',
        "Árbol del modelo",
        True,
        16,
    ),
    _I(
        "apoyos",
        "Apoyos",
        "Modelo de cálculo",
        '<path d="M8 3.2l4.2 6.3H3.8z"/><path d="M2.5 12.3h11"/>'
        '<path d="M4 14.6l1.5-2.3M7.2 14.6l1.5-2.3M10.4 14.6l1.5-2.3"/>',
        "Árbol del modelo",
        True,
        16,
    ),
    _I(
        "secciones",
        "Secciones",
        "Modelo de cálculo",
        '<path d="M3.5 2.8h9M3.5 13.2h9M8 2.8v10.4"/>'
        '<path d="M5.8 2.8v1.6M10.2 2.8v1.6M5.8 13.2v-1.6M10.2 13.2v-1.6"/>',
        "Árbol del modelo",
        True,
        16,
    ),
    _I(
        "empotramiento",
        "Empotramiento",
        "Modelo de cálculo",
        '<path d="M7 4v16"/><path d="M7 12h13"/><path d="M7 6.5l-3 3M7 11l-3 3M7 15.5l-3 3"/>',
        "Edición de apoyos (#31)",
    ),
    _I(
        "apoyo_movil",
        "Apoyo móvil",
        "Modelo de cálculo",
        '<path d="M12 4l5 7H7z"/><circle cx="9" cy="14.2" r="1.6"/>'
        '<circle cx="15" cy="14.2" r="1.6"/>'
        '<path d="M4 17.8h16"/>',
        "Edición de apoyos (#31)",
    ),
    _I(
        "resorte",
        "Apoyo elástico",
        "Modelo de cálculo",
        '<path d="M12 3v3l4 1.5-8 3 8 3-8 3 4 1.5v2"/><path d="M6 20h12"/>',
        "Apoyos elásticos y suelo (#88)",
    ),
    _I(
        "articulacion",
        "Articulación",
        "Modelo de cálculo",
        '<path d="M3 12h6.2M14.8 12H21"/><circle cx="12" cy="12" r="2.8"/>',
        "Liberaciones en extremos de barra (#31)",
    ),
    _I(
        "brazo_rigido",
        "Brazo rígido",
        "Modelo de cálculo",
        '<circle cx="4.8" cy="12" r="2"/><path d="M6.8 10.4h5.7v3.2H6.8"/><path d="M12.5 12H21"/>',
        "Brazos rígidos (#13)",
    ),
    _I(
        "diafragma",
        "Diafragma rígido",
        "Modelo de cálculo",
        '<path d="M3 16l4-4h14l-4 4z"/><path d="M7 7h9.5M14 4.5L16.5 7 14 9.5"/>',
        "Diafragma por piso (#14)",
    ),
    _I(
        "masa",
        "Masa",
        "Modelo de cálculo",
        '<path d="M7 9h10l3 11H4z"/><path d="M9.5 9a2.5 2.5 0 1 1 5 0"/>',
        "Masas para dinámica (#16)",
    ),
    _I(
        "combinaciones",
        "Combinaciones",
        "Modelo de cálculo",
        '<path d="M12.2 3H4l4.4 5L4 13h8.2"/>',
        "Árbol del modelo",
        True,
        16,
    ),
    _I(
        "materiales",
        "Materiales",
        "Modelo de cálculo",
        '<path d="M8 2.2l5.2 3v5.6L8 13.8l-5.2-3V5.2z"/>'
        '<path d="M8 8v5.8M8 8l5.2-2.8M8 8L2.8 5.2"/>',
        "Árbol del modelo físico",
        True,
        16,
    ),
    # --- Modelo físico del edificio (#73) ---
    _I(
        "plantas",
        "Plantas",
        "Modelo físico",
        '<path d="M5 20V4h14v16"/><path d="M3 20h18"/><path d="M5 9.3h14M5 14.6h14"/>',
        "Modo Edificio: gestor de plantas",
        True,
    ),
    _I(
        "pisos",
        "Pisos",
        "Modelo físico",
        '<path d="M2 5.5h12M2 10.5h12"/><path d="M3.5 5.5v5M12.5 5.5v5"/>',
        "Árbol del modelo físico",
        True,
        16,
    ),
    _I(
        "ejes",
        "Ejes",
        "Modelo físico",
        '<circle cx="8" cy="3.6" r="2"/><path d="M8 5.6v8.8" stroke-dasharray="2 1.6"/>',
        "Árbol del modelo físico",
        True,
        16,
    ),
    _I(
        "columnas",
        "Columnas",
        "Modelo físico",
        '<rect x="5" y="2.5" width="6" height="11" rx="0.6"/>',
        "Árbol del modelo físico",
        True,
        16,
    ),
    _I(
        "vigas",
        "Vigas",
        "Modelo físico",
        '<rect x="1.8" y="5.8" width="12.4" height="4.4" rx="0.6"/>',
        "Árbol del modelo físico",
        True,
        16,
    ),
    _I(
        "losas",
        "Losas",
        "Modelo físico",
        '<path d="M2.2 5.5l3-2.5h8.6l-3 2.5z"/><path d="M2.2 5.5v2.2h8.6V5.5M10.8 7.7l3-2.5V3"/>',
        "Árbol del modelo físico",
        True,
        16,
    ),
    _I(
        "muros",
        "Muros",
        "Modelo físico",
        '<rect x="2" y="3" width="12" height="10" rx="0.6"/><path d="M2 8h12M6 3v5M10 8v5"/>',
        "Árbol del modelo físico",
        True,
        16,
    ),
    _I(
        "cota_nivel",
        "Nivel",
        "Modelo físico",
        '<path d="M10 6h10M10 12h10M10 18h10"/><path d="M3 9.5h4L5 12z"/>',
        "Cotas de piso en alzado (#73)",
    ),
    _I(
        "abertura",
        "Abertura en losa",
        "Modelo físico",
        '<rect x="3" y="4.5" width="18" height="15" rx="1"/>'
        '<path d="M9 9h6v6H9z" stroke-dasharray="2.2 1.6"/>',
        "Huecos de losas y muros (#73, #86)",
    ),
    _I(
        "escalera",
        "Escalera",
        "Modelo físico",
        '<path d="M3 20h4v-4h4v-4h4V8h4V4h2"/>',
        "Escaleras (#89)",
    ),
    _I(
        "fundacion",
        "Fundación",
        "Modelo físico",
        '<path d="M10 3v9M14 3v9"/><path d="M4 12h16v4.5H4z"/>'
        '<path d="M2.5 20h19" stroke-dasharray="2 2"/>',
        "Fundaciones (#88)",
    ),
    _I(
        "pilote",
        "Pilotes",
        "Modelo físico",
        '<rect x="4" y="4" width="16" height="5" rx="0.6"/><path d="M8 9v11M16 9v11"/>'
        '<path d="M2.5 12.5h19" stroke-dasharray="2 2"/>',
        "Fundaciones profundas (#88)",
    ),
    _I(
        "tanque",
        "Tanque",
        "Modelo físico",
        '<ellipse cx="12" cy="6" rx="7" ry="2.5"/>'
        '<path d="M5 6v12c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5V6"/>',
        "Tanques (#89)",
    ),
    _I(
        "contencion",
        "Muro de contención",
        "Modelo físico",
        '<path d="M8 3h3v14h7v3H4v-3h4z"/><path d="M14 9l4-4M14 13.5l6.5-6.5M17.5 14l3-3"/>',
        "Muros de contención (#89)",
    ),
    # --- Cargas ---
    _I(
        "cargas",
        "Cargas",
        "Cargas",
        '<path d="M8 1.8v7.6"/><path d="M5 6.6l3 3 3-3"/><path d="M2.5 13h11"/>',
        "Árbol del modelo; carga puntual",
        True,
        16,
    ),
    _I(
        "carga_puntual",
        "Carga puntual",
        "Cargas",
        '<path d="M3 20h18"/><path d="M12 3v13"/><path d="M8 12l4 4 4-4"/>',
        "Cargas puntuales en barras y nudos (#31)",
    ),
    _I(
        "carga_repartida",
        "Carga repartida",
        "Cargas",
        '<path d="M3 20h18"/><path d="M4 5h16"/><path d="M7 5v10M12 5v10M17 5v10"/>'
        '<path d="M5 13l2 2 2-2M10 13l2 2 2-2M15 13l2 2 2-2"/>',
        "Cargas en barras (#31)",
    ),
    _I(
        "carga_trapezoidal",
        "Carga trapezoidal",
        "Cargas",
        '<path d="M3 11l18-7"/><path d="M5 10.2v4.3M12 7.5v7M19 4.8v9.7"/>'
        '<path d="M3 12.5l2 2 2-2M10 12.5l2 2 2-2M17 12.5l2 2 2-2"/><path d="M3 19.5h18"/>',
        "Cargas trapezoidales en barras (#2, #31)",
    ),
    _I(
        "cargas_planta",
        "Cargas de la planta",
        "Cargas",
        '<path d="M3 5h18v14H3z"/><path d="M3 5l6 7-6 7M21 5l-6 7 6 7M9 12h6"/>',
        "Modo Edificio: cargas de superficie de losas y su reparto (#78)",
    ),
    _I(
        "carga_lineal_losa",
        "Carga lineal en losa",
        "Cargas",
        '<path d="M3 5h18v14H3z"/><path d="M6 11h12M6 13h12"/>',
        "Tabiques y cargas lineales sobre losas (#78, #79)",
    ),
    _I(
        "momento",
        "Momento concentrado",
        "Cargas",
        '<path d="M3 18h18"/><path d="M6 14a6 6 0 0 1 12 0"/><path d="M14.5 12.5l3.5 1.5 1.5-3.5"/>',
        "Momentos puntuales (#3, #31)",
    ),
    _I(
        "temperatura",
        "Temperatura",
        "Cargas",
        '<path d="M10 14.5V5a2 2 0 0 1 4 0v9.5a4 4 0 1 1-4 0z"/><path d="M12 9v7.5"/>',
        "Cargas térmicas (#4)",
    ),
    _I(
        "uso",
        "Cargas por uso",
        "Cargas",
        '<circle cx="9" cy="7" r="2.8"/><path d="M4 20v-2.5a5 5 0 0 1 10 0V20"/>'
        '<circle cx="16.8" cy="8.2" r="2.2"/><path d="M16 12.8a4 4 0 0 1 4.5 4V20"/>',
        "Cargas por uso del local (#79)",
    ),
    _I(
        "viento",
        "Viento",
        "Cargas",
        '<path d="M3 8h10.5a2.8 2.8 0 1 0-2.8-2.8"/><path d="M3 12h15a3 3 0 1 1-3 3"/>'
        '<path d="M3 16h7"/>',
        "Viento según norma (#80)",
    ),
    _I(
        "sismo",
        "Sismo",
        "Cargas",
        '<path d="M2 12h3.5l2-5 3 11 3-14 3 12 2-4H22"/>',
        "Sismo estático y espectro normativo (#81)",
    ),
    _I(
        "nieve",
        "Nieve",
        "Cargas",
        '<path d="M12 3v18M4.2 7.5l15.6 9M4.2 16.5l15.6-9"/>'
        '<path d="M9.5 4.5L12 6.5l2.5-2M9.5 19.5L12 17.5l2.5 2"/>',
        "Caso de carga S (#79)",
    ),
    _I(
        "empuje_suelo",
        "Empuje de suelo",
        "Cargas",
        '<path d="M5 3v18"/><path d="M5 3l13 18H5"/><path d="M13.5 16H7"/>'
        '<path d="M9 14l-2 2 2 2"/>',
        "Caso H, muros de contención (#89)",
    ),
    _I(
        "envolvente",
        "Envolvente",
        "Cargas",
        '<path d="M3 12c4-8.5 14-8.5 18 0"/><path d="M3 12c4 8.5 14 8.5 18 0"/>'
        '<path d="M3 12h18" stroke-dasharray="2 2"/>',
        "Combinaciones y envolventes (#21)",
    ),
    # --- Análisis y resultados ---
    _I(
        "deformada",
        "Deformada",
        "Análisis y resultados",
        '<path d="M5 20V6h12v14" stroke-dasharray="2 2"/>'
        '<path d="M5 20c0-6 1-10 3.5-14h12c-2 4-3 8-3.5 14"/><path d="M3 20h18"/>',
        "Vista de resultados",
    ),
    _I(
        "momento_flector",
        "Momento flector",
        "Análisis y resultados",
        '<path d="M3 7h18"/><path d="M3 7c3 11 15 11 18 0"/><path d="M8 7v6.5M12 7v8M16 7v6.5"/>',
        "Diagramas de esfuerzos",
    ),
    _I(
        "cortante",
        "Cortante",
        "Análisis y resultados",
        '<path d="M3 12h18"/><path d="M3 12V5l18 14v-7"/><path d="M7.5 8.5V12M16.5 12v3.5"/>',
        "Diagramas de esfuerzos",
    ),
    _I(
        "axil",
        "Esfuerzo axil",
        "Análisis y resultados",
        '<path d="M3 15.5h18"/><path d="M3 15.5V8.5h18v7"/><path d="M8 8.5v7M13 8.5v7M18 8.5v7"/>',
        "Diagramas de esfuerzos",
    ),
    _I(
        "reacciones",
        "Reacciones",
        "Análisis y resultados",
        '<path d="M12 3.5l4.5 6h-9z"/><path d="M5 9.5h14"/><path d="M12 21v-8"/>'
        '<path d="M9 16l3-3 3 3"/>',
        "Resultados de apoyos",
    ),
    _I(
        "modal",
        "Modos de vibración",
        "Análisis y resultados",
        '<path d="M3 21h18"/><path d="M12 21V3" stroke-dasharray="2 2"/>'
        '<path d="M12 21c-6-3-6-7 0-9s6-6 0-9"/><circle cx="8" cy="15.5" r="1.3"/>'
        '<circle cx="16" cy="7" r="1.3"/>',
        "Análisis modal (#17)",
    ),
    _I(
        "espectro",
        "Espectro de respuesta",
        "Análisis y resultados",
        '<path d="M4 3.5V20h16.5"/><path d="M4 16l3-9h4.5c2 0 3.5 6 9 9"/>',
        "Espectro de respuesta (#18, #81)",
    ),
    _I(
        "p_delta",
        "P-Δ",
        "Análisis y resultados",
        '<path d="M4 21h10"/><path d="M8 21V7" stroke-dasharray="2 2"/>'
        '<path d="M8 21c0-6 2-10.5 6-14"/><path d="M14 2v4.5M12.2 4.8L14 6.6l1.8-1.8"/>',
        "Segundo orden P-Δ (#19)",
    ),
    _I(
        "tabla",
        "Tabla",
        "Análisis y resultados",
        '<rect x="3" y="4" width="18" height="16" rx="1.5"/><path d="M3 9h18M3 14.5h18M9 4v16"/>',
        "Tablas del modelo y resultados",
    ),
    _I(
        "grafico",
        "Gráfico",
        "Análisis y resultados",
        '<path d="M4 3.5V20h16.5"/><path d="M7 15l4-5 3 3 5.5-6.5"/>',
        "Curvas y gráficos de resultados",
    ),
    # --- Diseño de hormigón (Fase 3 y 10) ---
    _I(
        "hormigon",
        "Hormigón armado",
        "Diseño de hormigón",
        '<rect x="5" y="3" width="14" height="18" rx="0.8"/><circle cx="8.6" cy="6.6" r="1.1"/>'
        '<circle cx="15.4" cy="6.6" r="1.1"/><circle cx="8.6" cy="17.4" r="1.1"/>'
        '<circle cx="15.4" cy="17.4" r="1.1"/>',
        "Etapa Diseño: hormigón (#22, #24)",
    ),
    _I(
        "armadura",
        "Armadura",
        "Diseño de hormigón",
        '<path d="M3 15h13a3.5 3.5 0 0 0 0-7h-3"/><path d="M6 13.5v3M9.5 13.5v3M13 13.5v3"/>',
        "Modelo de armado (#93)",
    ),
    _I(
        "estribos",
        "Estribos",
        "Diseño de hormigón",
        '<path d="M10.5 3h6A1.5 1.5 0 0 1 18 4.5v15a1.5 1.5 0 0 1-1.5 1.5h-9'
        'A1.5 1.5 0 0 1 6 19.5v-15A1.5 1.5 0 0 1 7.5 3"/><path d="M7.5 3l3.6 3.6M6 4.5l3.6 3.6"/>',
        "Cortante y detalle de vigas (#23, #93)",
    ),
    _I(
        "interaccion",
        "Diagrama de interacción",
        "Diseño de hormigón",
        '<path d="M4 3v18M4 12h2"/><path d="M4 4.5C11 5 17 8.5 17 12.5S12 19 4 19.5"/>'
        '<circle cx="10.5" cy="12" r="1.3"/>',
        "Columnas: interacción biaxial (#24)",
    ),
    _I(
        "flecha",
        "Flecha",
        "Diseño de hormigón",
        '<path d="M3 7h18" stroke-dasharray="2 2"/><path d="M3 7q9 9 18 0"/>'
        '<path d="M12 7v4M10.3 9.6l1.7 1.7 1.7-1.7"/>',
        "Servicio: flechas (#90)",
    ),
    _I(
        "fisuracion",
        "Fisuración",
        "Diseño de hormigón",
        '<rect x="3" y="6" width="18" height="12" rx="0.8"/>'
        '<path d="M8.5 18l-.8-3 1.2-1.6-.6-2.4M15.5 18l.8-3-1.2-1.6.6-2.4"/>',
        "Servicio: fisuración (#90)",
    ),
    _I(
        "losa_nervada",
        "Losa nervada",
        "Diseño de hormigón",
        '<path d="M3 7h18v3.5H3z"/><path d="M5.5 10.5v6h3v-6M10.5 10.5v6h3v-6M15.5 10.5v6h3v-6"/>',
        "Losas nervadas (#101)",
    ),
    _I(
        "pretensado",
        "Pretensado",
        "Diseño de hormigón",
        '<rect x="3" y="7" width="18" height="10" rx="0.8"/><path d="M3 10q9 9 18 0"/>'
        '<path d="M1.5 10h1.5M21 10h1.5"/>',
        "Losas pretensadas (#102)",
    ),
    _I(
        "predimensionar",
        "Predimensionar",
        "Diseño de hormigón",
        '<rect x="9" y="4" width="8" height="14" rx="0.6"/>'
        '<path d="M5 4v14M3.8 6.2L5 4l1.2 2.2M3.8 15.8L5 18l1.2-2.2"/><path d="M9 21h8"/>',
        "Predimensionado (#82)",
    ),
    _I(
        "deriva",
        "Deriva de piso",
        "Diseño de hormigón",
        '<path d="M3 21h18M6 21v-8h10v8"/><path d="M6 13l2.5-8h10L16 13"/>'
        '<path d="M6 13V5" stroke-dasharray="2 2"/><path d="M6 3h2.5"/>',
        "Servicio: derivas (#90)",
    ),
    _I(
        "vibracion",
        "Vibración de entrepiso",
        "Diseño de hormigón",
        '<path d="M3 16h18"/>'
        '<path d="M3 10c1.5-2.5 3-2.5 4.5 0s3 2.5 4.5 0 3-2.5 4.5 0 3 2.5 4.5 0"/>',
        "Servicio: vibraciones (#90)",
    ),
    # --- Diseño de acero y mixtas (Fases 9 y 11) ---
    _I(
        "acero",
        "Perfil de acero",
        "Diseño de acero y mixtas",
        '<path d="M5 3.5h14v3.5h-5v10h5v3.5H5V17h5V7H5z"/>',
        "Catálogo de perfiles y barras de acero (#83, #84)",
    ),
    _I(
        "perfil_frio",
        "Perfil conformado en frío",
        "Diseño de acero y mixtas",
        '<path d="M18 7.5V4H7v16h11v-3.5"/>',
        "Perfiles conformados en frío (#100)",
    ),
    _I(
        "union_apernada",
        "Unión apernada",
        "Diseño de acero y mixtas",
        '<rect x="3" y="6" width="18" height="12" rx="1"/><path d="M12 6v12"/>'
        '<circle cx="7.5" cy="12" r="1.8"/><circle cx="16.5" cy="12" r="1.8"/>',
        "Uniones de acero (#85)",
    ),
    _I(
        "union_soldada",
        "Unión soldada",
        "Diseño de acero y mixtas",
        '<path d="M3 20h18M8 20V4"/><path d="M8 14l6 6"/><path d="M8 16.5l3.5 3.5M8 19l1 1"/>',
        "Uniones de acero, planos de taller (#85, #94)",
    ),
    _I(
        "placa_base",
        "Placa base",
        "Diseño de acero y mixtas",
        '<path d="M8 3h8M8 15h8M12 3v12"/><path d="M3 15h18v3H3z"/><path d="M6 18v3M18 18v3"/>',
        "Placas base (#85)",
    ),
    _I(
        "mixta",
        "Sección mixta",
        "Diseño de acero y mixtas",
        '<rect x="3.5" y="3.5" width="17" height="17" rx="0.8"/>'
        '<path d="M8 7.5h8M8 16.5h8M12 7.5v9"/>',
        "Vigas y columnas mixtas (#91)",
    ),
    _I(
        "losa_colaborante",
        "Losa colaborante",
        "Diseño de acero y mixtas",
        '<path d="M3 7h18"/><path d="M3 16.5h2.5l2-5h4l2 5h2.5l2-5H21"/>'
        '<path d="M3 7v9.5M21 7v4.5"/>',
        "Losa colaborante con chapa (#92)",
    ),
    # --- Documentos e intercambio (Fases 4, 7 y 12) ---
    _I(
        "memoria",
        "Memoria de cálculo",
        "Documentos e intercambio",
        _HOJA + '<path d="M8.5 12.5h7M8.5 16h7M8.5 9h2.5"/>',
        "Memoria PDF (#28)",
    ),
    _I(
        "plano_dxf",
        "Plano de arquitectura",
        "Documentos e intercambio",
        '<rect x="3" y="3" width="18" height="18" rx="1"/>'
        '<path d="M3 10h7v3M14 3v7h7M14 14.5V21"/>',
        "Importar DXF y reconocer el plano (#75)",
    ),
    _I(
        "reconocer",
        "Reconocer plano",
        "Documentos e intercambio",
        '<path d="M3 8V4.5A1.5 1.5 0 0 1 4.5 3H8M16 3h3.5A1.5 1.5 0 0 1 21 4.5V8'
        'M21 16v3.5a1.5 1.5 0 0 1-1.5 1.5H16M8 21H4.5A1.5 1.5 0 0 1 3 19.5V16"/>'
        '<path d="M7.5 7.5h3v3h-3zM13.5 7.5h3v3h-3z'
        'M7.5 13.5h3v3h-3zM13.5 13.5h3v3h-3z"/>',
        "Reconocer ejes, columnas, muros y losas (#75)",
    ),
    _I(
        "comparar",
        "Comparar revisiones",
        "Documentos e intercambio",
        '<rect x="3" y="4" width="7.5" height="16" rx="1"/>'
        '<rect x="13.5" y="4" width="7.5" height="16" rx="1"/>'
        '<path d="M5.5 9h2.5M5.5 13h2.5M16 9h2.5M16 13h2.5M16 16.5h2.5"/>',
        "Revisiones del plano (#76)",
    ),
    _I(
        "ifc",
        "Intercambio IFC",
        "Documentos e intercambio",
        '<path d="M4 8h13"/><path d="M14 5l3 3-3 3"/><path d="M20 16H7"/>'
        '<path d="M10 13l-3 3 3 3"/>',
        "Importar y exportar IFC (#25, #27, #98)",
    ),
    _I(
        "lamina",
        "Lámina",
        "Documentos e intercambio",
        '<rect x="2.5" y="4" width="19" height="16" rx="1"/><path d="M14 20v-5h7.5"/>'
        '<path d="M6 7.5h5v5H6z"/>',
        "Láminas con rótulo (#95)",
    ),
    _I(
        "planilla",
        "Planilla de armaduras",
        "Documentos e intercambio",
        '<rect x="3" y="3.5" width="18" height="17" rx="1.5"/><path d="M3 8.5h18M8.5 8.5v12"/>'
        '<path d="M11.5 16.5h5a2 2 0 0 0 0-4h-1"/>',
        "Planillas de armaduras y doblado (#29)",
    ),
    _I(
        "computo",
        "Cómputo y presupuesto",
        "Documentos e intercambio",
        '<rect x="5" y="3" width="14" height="18" rx="1.5"/><path d="M8 7h8"/>'
        '<path d="M8.5 11.5h.01M12 11.5h.01M15.5 11.5h.01M8.5 14.8h.01M12 14.8h.01M15.5 14.8h.01'
        'M8.5 18h.01M12 18h.01M15.5 18h.01"/>',
        "Cómputos métricos y presupuesto (#96)",
    ),
    _I(
        "versiones",
        "Versiones",
        "Documentos e intercambio",
        '<path d="M3.5 12a8.5 8.5 0 1 0 2.5-6"/><path d="M3.5 3.5V8H8"/><path d="M12 7.5V12l3 2"/>',
        "Control de versiones de la entrega (#97)",
    ),
    # --- Estados ---
    _I(
        "ok",
        "Cumple",
        "Estados",
        '<circle cx="12" cy="12" r="9"/><path d="M8 12.3l2.8 2.8 5.2-5.6"/>',
        "Verificaciones que cumplen",
    ),
    _I(
        "no_cumple",
        "No cumple",
        "Estados",
        '<circle cx="12" cy="12" r="9"/><path d="M9 9l6 6M15 9l-6 6"/>',
        "Verificaciones que no cumplen",
    ),
    _I(
        "aviso",
        "Aviso",
        "Estados",
        '<path d="M12 3.5L21.5 20h-19z"/><path d="M12 10v4.5M12 17.3h.01"/>',
        "Nudo inestable, avisos del cálculo",
    ),
    _I(
        "info",
        "Información",
        "Estados",
        '<circle cx="12" cy="12" r="9"/><path d="M12 11v5.5M12 7.8h.01"/>',
        "Notas y ayudas",
    ),
    _I(
        "preliminar",
        "Preliminar",
        "Estados",
        '<path d="M9 3h6M10 3v6.5L4.6 18.6A1.6 1.6 0 0 0 6 21h12a1.6 1.6 0 0 0 1.4-2.4L14 9.5V3"/>'
        '<path d="M7 15.5h10"/>',
        "Módulos experimentales sin revisión",
    ),
    _I(
        "bloqueado",
        "Bloqueado",
        "Estados",
        '<rect x="5" y="11" width="14" height="10" rx="1.5"/>'
        '<path d="M8 11V7.5a4 4 0 0 1 8 0V11"/>',
        "Elementos fijados, versiones cerradas (#97)",
    ),
)

#: Todos los íconos, por clave.
CATALOGO: dict[str, Icono] = {i.clave: i for i in _LISTA}

#: Trazo en unidades de la grilla de 24, según el lado en píxeles.
TRAZO = 1.7
TRAZO_CHICO = 2.1  # 1,4 px a 16 px


def trazo(lado: int) -> float:
    """Ancho de trazo, en unidades de la grilla, para un ícono de ``lado`` px."""
    return TRAZO_CHICO if lado <= 16 else TRAZO


def svg(clave: str, color: str, lado: int = 24) -> str:
    """El ícono ``clave`` como SVG de ``lado`` px, en ``color``.

    El trazo se da en unidades de la grilla del ícono, así mide lo mismo en píxeles
    sea cual sea su grilla (24 o 16)."""
    ic = CATALOGO[clave]
    r = ic.rejilla
    ancho = round(trazo(lado) * r / 24, 4)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{lado}" height="{lado}" '
        f'viewBox="0 0 {r} {r}" fill="none" stroke="{color}" stroke-width="{ancho:g}" '
        f'stroke-linecap="round" stroke-linejoin="round">{ic.cuerpo}</svg>'
    )


_cache: dict[tuple[str, str, int, float], QPixmap] = {}


def pixmap(clave: str, color: str, lado: int = 24, escala: float = 1.0) -> QPixmap:
    """El ícono como imagen de ``lado`` px lógicos para una pantalla de ``escala``."""
    from PySide6.QtCore import QByteArray, Qt
    from PySide6.QtGui import QPainter, QPixmap
    from PySide6.QtSvg import QSvgRenderer

    llave = (clave, color, lado, escala)
    if llave not in _cache:
        fisico = round(lado * escala)
        pix = QPixmap(fisico, fisico)
        pix.fill(Qt.transparent)
        p = QPainter(pix)
        QSvgRenderer(QByteArray(svg(clave, color, lado).encode())).render(p)
        p.end()
        pix.setDevicePixelRatio(escala)
        _cache[llave] = pix
    return _cache[llave]


def qicon(clave: str, tema: Tema, lado: int = 20, escala: float = 1.0) -> QIcon:
    """``QIcon`` con los colores del tema: reposo, activo (botón marcado) y deshabilitado."""
    from PySide6.QtGui import QIcon

    icono = QIcon()
    icono.addPixmap(pixmap(clave, tema.texto_2, lado, escala), QIcon.Normal, QIcon.Off)
    icono.addPixmap(pixmap(clave, tema.acento, lado, escala), QIcon.Normal, QIcon.On)
    icono.addPixmap(pixmap(clave, tema.deshabilitado, lado, escala), QIcon.Disabled, QIcon.Off)
    icono.addPixmap(pixmap(clave, tema.deshabilitado, lado, escala), QIcon.Disabled, QIcon.On)
    return icono


def por_grupo() -> dict[str, list[Icono]]:
    """Los íconos agrupados en el orden de :data:`GRUPOS`."""
    grupos: dict[str, list[Icono]] = {g: [] for g in GRUPOS}
    for i in _LISTA:
        grupos[i.grupo].append(i)
    return grupos
