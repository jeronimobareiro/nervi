# SPDX-License-Identifier: GPL-3.0-or-later
"""Árbol del modelo: panel *Estructura* con secciones plegables.

Cada categoría (Nudos, Barras, Apoyos, Secciones, Cargas y Combinaciones) es una
sección con su ícono, su contador y un chevrón a la derecha que la pliega. Las
secciones van separadas por una línea fina y sus filas cuelgan de una guía
vertical. Las filas dicen qué es cada cosa, no solo su número: la barra con su
tipo y sección (``B1  Columna 30×30``), el apoyo con su tipo (``N1  Empotrado``) y
el caso de carga con su nombre según ACI 318-19 §5.3 (``D  Permanente``).

El árbol no guarda datos propios: se arma desde el diccionario del modelo y los
datos de diseño cada vez que cambian. Recuerda qué secciones están abiertas.
Los colores salen de las constantes de :mod:`estilo` en el momento de dibujar,
así cambian con el tema.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QByteArray, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTreeWidget,
    QTreeWidgetItem,
)

from . import estilo, iconos

#: Íconos de las secciones (16 por 16 px con línea de 1,4 px). Salen del catálogo
#: :mod:`nervi.gui.iconos`, la fuente única de los íconos de la interfaz.
ICONOS_ARBOL = {
    clave: iconos.CATALOGO[clave].cuerpo
    for clave in (
        "nudos",
        "barras",
        "apoyos",
        "secciones",
        "cargas",
        "combinaciones",
        # Modelo físico del edificio (#73).
        "pisos",
        "ejes",
        "columnas",
        "vigas",
        "losas",
        "muros",
        "materiales",
    )
}

_CHEVRON = {
    "abierto": '<path d="M4.5 6.2l3.5 3.5 3.5-3.5"/>',
    "cerrado": '<path d="M6.2 4.5l3.5 3.5-3.5 3.5"/>',
}

#: Nombre de los casos de carga por su símbolo (ACI 318-19 §5.3.1; ASCE 7).
NOMBRES_CASO = {
    "D": "Permanente",
    "L": "Sobrecarga",
    "LR": "Sobrecarga de techo",
    "W": "Viento",
    "E": "Sismo",
    "S": "Nieve",
    "R": "Lluvia",
    "T": "Temperatura",
    "H": "Empuje de suelo",
    "F": "Fluidos",
}

#: Tabla del modelo que abre el título de cada sección.
TABLAS = {
    "nudos": "nudos",
    "barras": "barras",
    "apoyos": "apoyos",
    "secciones": "barras",
    "cargas": "casos",
    "combinaciones": "combinaciones",
}

#: Secciones del árbol del modelo físico; el título abre la tabla de la misma lista.
TABLAS_EDIFICIO = ("pisos", "ejes", "columnas", "vigas", "losas", "muros", "materiales")

#: Secciones abiertas al empezar (como en la muestra aprobada).
ABIERTAS = frozenset({"barras", "cargas", "combinaciones"})

_ALTO_GRUPO = 34
_ALTO_FILA = 26
_ANCHO_DATO = 300  # px desde los que entra el dato de la derecha
_ROL_FILA = Qt.UserRole + 1


@dataclass(frozen=True)
class Fila:
    """Una fila del árbol: grupo (sección) o elemento dentro de una sección."""

    clave: str  # sección a la que pertenece
    codigo: str  # "B1", "N1", "D", "Nudos"
    detalle: str = ""  # tipo y sección de la barra, tipo de apoyo, nombre del caso
    dato: str = ""  # texto tenue a la derecha: "N1 → N2", "2 barras"
    grupo: bool = False
    cantidad: int | None = None
    #: En el modelo físico, el ``id`` del elemento (o del piso) de la fila.
    ref: int | None = None


def _svg(cuerpo: str, color: str, ancho: float = 1.4) -> bytes:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16" '
        f'fill="none" stroke="{color}" stroke-width="{ancho}" stroke-linecap="round" '
        f'stroke-linejoin="round">{cuerpo}</svg>'
    ).encode()


_cache: dict[tuple[str, str, float], QPixmap] = {}


def _icono(cuerpo: str, color: str, escala: float, ancho: float = 1.4) -> QPixmap:
    clave = (cuerpo, color, escala)
    if clave not in _cache:
        lado = round(16 * escala)
        pix = QPixmap(lado, lado)
        pix.fill(Qt.transparent)
        p = QPainter(pix)
        QSvgRenderer(QByteArray(_svg(cuerpo, color, ancho))).render(p)
        p.end()
        pix.setDevicePixelRatio(escala)
        _cache[clave] = pix
    return _cache[clave]


def _numero(v: float) -> str:
    """Medida sin ceros de más: 30, 22.5."""
    return f"{v:.1f}".rstrip("0").rstrip(".")


def tipo_apoyo(apoyo: dict) -> str:
    """Nombre del apoyo según los GDL que restringe."""
    ux, uy, rz = (bool(apoyo.get(k, False)) for k in ("ux", "uy", "rz"))
    if ux and uy and rz:
        return "Empotrado"
    if ux and uy:
        return "Articulado"
    if rz and (ux or uy):
        return "Empotrado deslizante"
    if ux or uy:
        return "Deslizante"
    return "Giro impedido" if rz else "Libre"


def filas(modelo: dict, elementos: list | None = None) -> list[Fila]:
    """Filas del árbol para un modelo.

    ``elementos`` son los de :func:`nervi.design.proyecto.elementos` (tipo y
    sección de cada barra, en mm). Si faltan, las barras solo muestran sus nudos.
    """
    por_barra = {e.barra: e for e in elementos or []}
    salida: list[Fila] = []

    def grupo(clave: str, titulo: str, cantidad: int | None) -> None:
        salida.append(Fila(clave, titulo, grupo=True, cantidad=cantidad))

    nudos = modelo["nudos"]
    grupo("nudos", "Nudos", len(nudos))
    for n in nudos:
        salida.append(Fila("nudos", f"N{n['id']}", dato=f"({_numero(n['x'])}; {_numero(n['y'])})"))

    barras = modelo["barras"]
    grupo("barras", "Barras", len(barras))
    secciones: dict[tuple[float, float], list[int]] = {}
    for b in barras:
        el = por_barra.get(b["id"])
        detalle = ""
        if el is not None:
            seccion = f"{_numero(el.b / 10)}×{_numero(el.h / 10)}"
            secciones.setdefault((el.b, el.h), []).append(b["id"])
            tipo = {"viga": "Viga", "columna": "Columna"}.get(el.tipo, "Barra")
            detalle = f"{tipo} {seccion}"
        salida.append(Fila("barras", f"B{b['id']}", detalle, f"N{b['i']} → N{b['j']}"))

    apoyos = modelo.get("apoyos", [])
    grupo("apoyos", "Apoyos", len(apoyos))
    for a in apoyos:
        salida.append(Fila("apoyos", f"N{a['nudo']}", tipo_apoyo(a)))

    if elementos is not None:
        grupo("secciones", "Secciones", len(secciones))
        for (bb, hh), ids in sorted(secciones.items()):
            n = len(ids)
            salida.append(
                Fila(
                    "secciones",
                    f"{_numero(bb / 10)}×{_numero(hh / 10)}",
                    "Rectangular",
                    f"{n} barra" if n == 1 else f"{n} barras",
                )
            )

    casos = modelo["casos"]
    grupo("cargas", "Cargas", len(casos))
    for c in casos:
        nombre = c["nombre"]
        salida.append(Fila("cargas", nombre, NOMBRES_CASO.get(nombre.upper(), "")))

    combinaciones = modelo.get("combinaciones", [])
    grupo("combinaciones", "Combinaciones", len(combinaciones))
    for c in combinaciones:
        salida.append(Fila("combinaciones", c["nombre"]))
    return salida


class _Delegado(QStyledItemDelegate):
    """Dibuja los grupos y las filas con los tokens del tema."""

    def sizeHint(self, opcion: QStyleOptionViewItem, indice) -> QSize:
        fila: Fila = indice.data(_ROL_FILA)
        alto = _ALTO_GRUPO if fila is not None and fila.grupo else _ALTO_FILA
        return QSize(opcion.rect.width(), round(alto * estilo.actual.tamano / 9.5))

    def paint(self, p: QPainter, opcion: QStyleOptionViewItem, indice) -> None:
        fila: Fila = indice.data(_ROL_FILA)
        if fila is None:
            return
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        r = opcion.rect
        escala = p.device().devicePixelRatioF() if p.device() else 1.0
        hover = bool(opcion.state & QStyle.State_MouseOver)
        elegido = bool(opcion.state & QStyle.State_Selected)
        base = QFont(opcion.font)
        if fila.grupo:
            self._grupo(p, r, fila, indice, base, escala, hover)
        else:
            activo = (fila.clave, fila.codigo) == self.parent().activo
            self._fila(p, r, fila, base, hover, elegido, activo)
        p.restore()

    def _grupo(self, p, r: QRect, fila: Fila, indice, base: QFont, escala, hover) -> None:
        if indice.row() > 0:
            p.setPen(QPen(QColor(estilo.BORDE), 1))
            p.drawLine(r.left(), r.top(), r.right(), r.top())
        if hover:
            p.fillRect(r.adjusted(0, 1, 0, 0), QColor(estilo.HOVER))
        y = r.top() + (r.height() - 16) // 2
        p.drawPixmap(r.left() + 10, y, iconos.pixmap(fila.clave, estilo.TEXTO_2, 16, escala))
        f = QFont(base)
        f.setWeight(QFont.DemiBold)
        p.setFont(f)
        p.setPen(QColor(estilo.TEXTO))
        x = r.left() + 34
        caja = QRect(x, r.top(), r.width() - 64, r.height())
        p.drawText(caja, Qt.AlignVCenter | Qt.AlignLeft, fila.codigo)
        if fila.cantidad is not None:
            x += p.fontMetrics().horizontalAdvance(fila.codigo) + 6
            p.setFont(base)
            p.setPen(QColor(estilo.TEXTO_3))
            p.drawText(
                QRect(x, r.top(), 60, r.height()),
                Qt.AlignVCenter | Qt.AlignLeft,
                str(fila.cantidad),
            )
        abierto = indice.model().hasChildren(indice) and self.parent().isExpanded(indice)
        chevron = _CHEVRON["abierto" if abierto else "cerrado"]
        p.drawPixmap(r.right() - 24, y, _icono(chevron, estilo.TEXTO_3, escala, 1.6))

    def _fila(self, p, r: QRect, fila: Fila, base: QFont, hover, elegido, activo) -> None:
        # Guía vertical de la sección, a la altura del ícono del grupo.
        p.setPen(QPen(QColor(estilo.BORDE), 1))
        p.drawLine(r.left() + 18, r.top(), r.left() + 18, r.bottom())
        fondo = r.adjusted(28, 1, -8, -1)
        if elegido or hover:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(estilo.ACENTO_SUAVE if elegido else estilo.HOVER))
            p.drawRoundedRect(QRectF(fondo), 4, 4)
        x = fondo.left() + 8
        ancho = fondo.width() - 16
        f = QFont(base)
        f.setWeight(QFont.DemiBold if elegido or activo else QFont.Medium)
        p.setFont(f)
        p.setPen(QColor(estilo.ACENTO if elegido or activo else estilo.TEXTO))
        p.drawText(
            QRect(x, r.top(), ancho, r.height()), Qt.AlignVCenter | Qt.AlignLeft, fila.codigo
        )
        avance = p.fontMetrics().horizontalAdvance(fila.codigo)
        p.setFont(base)
        fm = p.fontMetrics()
        x2 = x + max(avance + 8, 30)
        derecha = 0
        dato = fila.dato
        if activo and not dato:
            dato = "●"
        if dato:
            derecha = fm.horizontalAdvance(dato) + 8
            # Con el panel angosto el detalle manda y el dato queda en la ayuda; se decide
            # por el ancho del panel, no por fila, para que todas las filas se vean iguales.
            if fila.detalle and r.width() < _ANCHO_DATO and not activo:
                derecha = 0
            else:
                p.setPen(QColor(estilo.ACENTO if activo or elegido else estilo.TEXTO_3))
                p.drawText(
                    QRect(x, r.top(), ancho, r.height()), Qt.AlignVCenter | Qt.AlignRight, dato
                )
        if fila.detalle:
            p.setPen(QColor(estilo.ACENTO if elegido else estilo.TEXTO_2))
            caja = QRect(x2, r.top(), x + ancho - derecha - x2, r.height())
            texto = fm.elidedText(fila.detalle, Qt.ElideRight, caja.width())
            p.drawText(caja, Qt.AlignVCenter | Qt.AlignLeft, texto)


class ArbolModelo(QTreeWidget):
    """Árbol del modelo con secciones plegables.

    Emite :attr:`elegido` con ``(tipo, valor)`` al hacer clic:
    ``("tabla", lista)`` en el título de una sección, ``("barra", id)``,
    ``("nudo", id)`` y ``("resultado", nombre)`` en las filas.
    """

    elegido = Signal(str, object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("arbol_modelo")
        self.setHeaderHidden(True)
        self.setRootIsDecorated(False)
        self.setIndentation(0)
        self.setItemsExpandable(False)
        self.setExpandsOnDoubleClick(False)
        self.setMouseTracking(True)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setFocusPolicy(Qt.NoFocus)
        self.setItemDelegate(_Delegado(self))
        self.abiertas: set[str] = set(ABIERTAS)
        self._items: dict[tuple[str, str], QTreeWidgetItem] = {}
        #: Caso o combinación que se está viendo: texto en acento y un punto.
        self.activo: tuple[str, str] | None = None
        self.itemClicked.connect(self._clic)

    # -- contenido --------------------------------------------------------------

    def mostrar(self, modelo: dict, elementos: list | None = None) -> None:
        """Arma el árbol del modelo analítico, sin perder qué secciones están abiertas."""
        self.mostrar_filas(filas(modelo, elementos))

    def mostrar_filas(self, lista_filas: list[Fila]) -> None:
        """Arma el árbol con estas filas, sin perder qué secciones están abiertas."""
        self.blockSignals(True)
        self.clear()
        self._items.clear()
        actual: QTreeWidgetItem | None = None
        for fila in lista_filas:
            if fila.grupo:
                actual = QTreeWidgetItem(self, [fila.codigo])
                actual.setFlags(Qt.ItemIsEnabled)
            else:
                item = QTreeWidgetItem(actual, [f"{fila.codigo} {fila.detalle}".strip()])
                self._items[(fila.clave, fila.codigo)] = item
            (actual if fila.grupo else item).setData(0, _ROL_FILA, fila)
            (actual if fila.grupo else item).setToolTip(0, self._ayuda(fila))
        for i in range(self.topLevelItemCount()):
            g = self.topLevelItem(i)
            g.setExpanded(g.data(0, _ROL_FILA).clave in self.abiertas)
        self.blockSignals(False)

    @staticmethod
    def _ayuda(fila: Fila) -> str:
        if fila.grupo:
            return f"{fila.codigo}: clic para desplegar y ver la tabla"
        return " · ".join(t for t in (fila.codigo, fila.detalle, fila.dato) if t)

    def marcar(self, clave: str | None, codigo: str | None) -> None:
        """Resalta la fila elegida (barra o nudo) sin emitir; ``None`` la quita."""
        self.blockSignals(True)
        self.clearSelection()
        item = self._items.get((clave, codigo)) if clave and codigo is not None else None
        if item is not None:
            item.setSelected(True)
            self.scrollToItem(item)
        self.blockSignals(False)
        self.viewport().update()

    def marcar_activo(self, clave: str | None, codigo: str | None) -> None:
        """Marca el caso o la combinación que muestran los diagramas."""
        self.activo = (clave, codigo) if clave and codigo else None
        self.viewport().update()

    # -- interacción ------------------------------------------------------------

    def alternar(self, clave: str) -> None:
        """Abre o pliega una sección."""
        for i in range(self.topLevelItemCount()):
            g = self.topLevelItem(i)
            if g.data(0, _ROL_FILA).clave == clave:
                abrir = not g.isExpanded()
                g.setExpanded(abrir)
                (self.abiertas.add if abrir else self.abiertas.discard)(clave)

    def mousePressEvent(self, evento) -> None:
        self._x_clic = evento.position().x()
        super().mousePressEvent(evento)

    def _clic(self, item: QTreeWidgetItem, _col: int = 0) -> None:
        fila: Fila = item.data(0, _ROL_FILA)
        if fila is None:
            return
        if fila.grupo:
            # El título pliega o despliega la sección y, al abrirla, muestra su tabla;
            # el chevrón solo pliega o despliega.
            en_chevron = getattr(self, "_x_clic", 0) >= self.viewport().width() - 34
            self.alternar(fila.clave)
            self._x_clic = 0
            if item.isExpanded() and not en_chevron and fila.clave in TABLAS:
                self.elegido.emit("tabla", TABLAS[fila.clave])
            elif item.isExpanded() and not en_chevron and fila.clave in TABLAS_EDIFICIO:
                self.elegido.emit("tabla_edificio", fila.clave)
            return
        if fila.ref is not None:
            self.elegido.emit("edificio", (fila.clave, fila.ref))
            return
        if fila.clave == "barras":
            self.elegido.emit("barra", int(fila.codigo[1:]))
        elif fila.clave in ("nudos", "apoyos"):
            self.elegido.emit("nudo", int(fila.codigo[1:]))
        elif fila.clave in ("cargas", "combinaciones"):
            self.elegido.emit("resultado", fila.codigo)
        elif fila.clave == "secciones":
            self.elegido.emit("tabla", "barras")
