# SPDX-License-Identifier: GPL-3.0-or-later
"""Modelo físico del edificio en la interfaz (issue #73).

Con *Edificio* elegido en la barra contextual, la ventana muestra el modelo físico
(``nervi.fisico.ModeloFisico``) en vez del analítico:

* :class:`PlantaEdificio`: la planta de un piso con ejes, columnas, vigas, losas,
  muros y cotas; un clic elige un elemento;
* :func:`filas_arbol`: las filas del panel *Estructura* (pisos, ejes, columnas,
  vigas, losas, muros y materiales);
* :class:`PropiedadesEdificio`: los datos del elemento elegido, editables;
* :class:`TablasEdificio`: una tabla editable por lista;
* :class:`GestorPlantas`: agregar, editar, quitar y copiar plantas.

Todo cambio pasa por :meth:`EstadoEdificio.aplicar`, que valida el modelo físico
entero y lo guarda en la sesión con deshacer y rehacer. Las muestras aprobadas
están en ``docs/diseno-interfaz.md`` §Modelo físico.
"""

from __future__ import annotations

import copy
import math
from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QObject, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QStyledItemDelegate,
    QTableView,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..fisico import ModeloFisico
from ..formato import fisico as formato_fisico
from ..formato.errores import FormatoError
from ..reparto import CASOS, RepartoCargas
from . import arbol, estilo
from .dibujo import DibujoEdificio
from .navegacion import (
    METROS,
    Navegable,
    Transformacion,
    Vista,
    dibujar_coordenadas,
    dibujar_grilla,
)
from .sesion import Sesion

#: Casos de carga que se pueden ver en la planta, con su nombre.
CASOS_VISTA = {
    "total": "Total de servicio",
    "peso_propio": "Peso propio",
    "permanente": "Permanente",
    "sobrecarga": "Sobrecarga",
}
#: Abreviatura de cada caso en los rótulos de la planta.
ABREV = {"peso_propio": "PP", "permanente": "D", "sobrecarga": "L"}

#: Listas que se dibujan en la planta de un piso.
ELEMENTOS = ("columnas", "vigas", "losas", "muros")
#: Nombre singular de cada lista, para títulos y mensajes.
SINGULAR = {
    "pisos": "Piso",
    "ejes": "Eje",
    "materiales": "Material",
    "secciones": "Sección",
    "columnas": "Columna",
    "vigas": "Viga",
    "losas": "Losa",
    "muros": "Muro",
}
TITULOS = {
    "pisos": "Pisos",
    "ejes": "Ejes",
    "columnas": "Columnas",
    "vigas": "Vigas",
    "losas": "Losas",
    "muros": "Muros",
    "materiales": "Materiales",
    "secciones": "Secciones",
}


def _n(v: float, decimales: int = 2) -> str:
    return f"{v:.{decimales}f}"


def _nivel(v: float) -> str:
    return "±0.00" if v == 0 else f"{v:+.2f}"


def _medida(mm: float) -> str:
    """Medida en cm sin ceros de más: 25, 22.5."""
    return f"{mm / 10:.1f}".rstrip("0").rstrip(".")


def _kn(v: float, decimales: int = 1) -> str:
    return f"{v:.{decimales}f}".replace(".", ",")


def resultante(reparto: RepartoCargas, apoyo: tuple[str, int], caso: str) -> float:
    """Fuerza que recibe el apoyo en ``caso`` (``"total"`` suma los tres)."""
    casos = CASOS if caso == "total" else (caso,)
    return sum(reparto.resultante(apoyo, c) for c in casos)


def diagrama(reparto: RepartoCargas, apoyo: tuple[str, int], caso: str) -> list[tuple]:
    """Puntos ``(abscisa, carga)`` de la carga lineal sobre el apoyo, sumando las losas
    que lo cargan, de un extremo al otro (para dibujarla)."""
    casos = CASOS if caso == "total" else (caso,)
    tramos = reparto.de(apoyo)
    cortes = sorted({t.a for t in tramos} | {t.b for t in tramos})

    def carga(x: float, lado: int) -> float:
        total = 0.0
        for t in tramos:
            dentro = t.a <= x < t.b if lado > 0 else t.a < x <= t.b
            if dentro:
                for c in casos:
                    q1, q2 = t.cargas[c]
                    total += q1 + (q2 - q1) * (x - t.a) / (t.b - t.a)
        return total

    puntos = []
    for x in cortes:
        puntos += [(x, carga(x, -1)), (x, carga(x, 1))]
    return puntos


def nombre_elemento(lista: str, el: dict) -> str:
    """Código que se muestra de un elemento: su nombre o, si no tiene, letra e id."""
    return el.get("nombre") or f"{SINGULAR[lista][0]}{el['id']}"


class EstadoEdificio(QObject):
    """Piso que se ve y elemento elegido, y la puerta de entrada de los cambios."""

    #: Cambió el piso, el elemento elegido o el modelo físico (también al deshacer).
    cambiado = Signal()
    mensaje = Signal(str)  # un cambio no se pudo hacer: el motivo

    def __init__(self, sesion: Sesion) -> None:
        super().__init__()
        self.sesion = sesion
        self.piso: int | None = None
        self.eleccion: tuple[str, int] | None = None
        #: Si la planta muestra las cargas de las losas y su reparto (#78).
        self.cargas_visibles = False
        #: Caso que se muestra: uno de ``nervi.reparto.CASOS`` o ``"total"``.
        self.caso = "total"
        self._reparto: RepartoCargas | None = None
        sesion.fisico_cambiado.connect(self._revisar)
        self._revisar()

    # -- datos ------------------------------------------------------------------
    def modelo(self) -> ModeloFisico:
        """Una copia del modelo físico de la sesión (vacío si no tiene)."""
        datos = self.sesion.fisico
        return ModeloFisico.desde_json(datos) if datos is not None else ModeloFisico()

    def aplicar(self, cambio: Callable[[ModeloFisico], object], descripcion: str) -> bool:
        """Aplica ``cambio`` a una copia del modelo y, si queda válido, lo guarda en la
        sesión (se deshace con Ctrl+Z). Si no, emite :attr:`mensaje` y no cambia nada."""
        mf = self.modelo()
        try:
            cambio(mf)
        except (FormatoError, KeyError, ValueError) as e:
            self.mensaje.emit(str(e).strip("'\""))
            return False
        self.sesion.editar_fisico(mf.a_json(), descripcion)
        return True

    def reparto(self) -> RepartoCargas:
        """El reparto de las losas a vigas y muros del modelo actual (se calcula una vez
        por cambio del modelo)."""
        if self._reparto is None:
            self._reparto = self.modelo().repartir_cargas()
        return self._reparto

    def mostrar_cargas(self, visibles: bool, caso: str | None = None) -> None:
        if caso is not None and caso not in CASOS_VISTA:
            raise ValueError(f"caso {caso!r}; válidos {tuple(CASOS_VISTA)}")
        self.cargas_visibles = visibles
        self.caso = caso or self.caso
        self.cambiado.emit()

    def _revisar(self) -> None:
        """Después de un cambio, el piso y el elemento elegidos tienen que seguir existiendo."""
        self._reparto = None
        mf = self.modelo()
        pisos = [p["id"] for p in mf.pisos_ordenados()]
        if self.piso not in pisos:
            # El primero con algo para ver, o el más bajo.
            con_algo = [p for p in pisos if mf.elementos_en_piso(p)]
            self.piso = (con_algo or pisos or [None])[0]
        if self.eleccion is not None:
            lista, id = self.eleccion
            if id not in {e["id"] for e in mf.lista(lista)}:
                self.eleccion = None
        self.cambiado.emit()

    # -- navegación ---------------------------------------------------------------
    def ir_a_piso(self, piso: int | None) -> None:
        if piso != self.piso:
            self.piso = piso
            if self.eleccion and self.eleccion[0] in ELEMENTOS:
                self.eleccion = None
            self.cambiado.emit()

    def subir(self, pasos: int = 1) -> None:
        """Sube (o baja, con ``pasos`` negativo) de planta."""
        orden = [p["id"] for p in self.modelo().pisos_ordenados()]
        if not orden:
            return
        k = orden.index(self.piso) if self.piso in orden else 0
        self.ir_a_piso(orden[max(0, min(len(orden) - 1, k + pasos))])

    def puede(self, pasos: int) -> bool:
        orden = [p["id"] for p in self.modelo().pisos_ordenados()]
        if self.piso not in orden:
            return False
        return 0 <= orden.index(self.piso) + pasos < len(orden)

    def elegir(self, lista: str | None, id: int | None = None) -> None:
        nueva = (lista, id) if lista is not None and id is not None else None
        if lista == "pisos" and id is not None:
            self.piso = id
            nueva = None
        if nueva != self.eleccion or lista == "pisos":
            self.eleccion = nueva
            self.cambiado.emit()


# --- Árbol ------------------------------------------------------------------------------


def filas_arbol(mf: ModeloFisico, piso: int | None) -> list[arbol.Fila]:
    """Filas del panel *Estructura* con el modelo físico; los elementos, del ``piso``."""
    F = arbol.Fila
    salida: list[F] = []
    pisos = list(reversed(mf.pisos_ordenados()))
    salida.append(F("pisos", "Pisos", grupo=True, cantidad=len(pisos)))
    for p in pisos:
        salida.append(
            F("pisos", p["nombre"], dato=f"{_nivel(p['nivel'])} {mf.longitud}", ref=p["id"])
        )
    ejes = mf.lista("ejes")
    salida.append(F("ejes", "Ejes", grupo=True, cantidad=len(ejes)))
    for e in ejes:
        salida.append(F("ejes", e["nombre"], ref=e["id"]))
    secciones = {s["id"]: s for s in mf.lista("secciones")}
    materiales = {m["id"]: m for m in mf.lista("materiales")}
    nombres_piso = {p["id"]: p["nombre"] for p in pisos}
    en = mf.en_piso(piso) if piso is not None else {k: [] for k in ELEMENTOS}
    for lista in ELEMENTOS:
        salida.append(F(lista, TITULOS[lista], grupo=True, cantidad=len(en[lista])))
        for el in en[lista]:
            if lista in ("columnas", "vigas"):
                s = secciones[el["seccion"]]
                detalle = s["nombre"]
            else:
                detalle = f"{'Maciza ' if lista == 'losas' else ''}{_medida(el['espesor'])} cm"
            if lista == "losas":
                dato = f"{mf.area_losa(el['id']):.1f} {mf.longitud}²"
            elif lista == "vigas":
                dato = f"{mf.largo_viga(el['id']):.2f} {mf.longitud}"
            else:
                dato = f"{nombres_piso[el['desde']]} → {nombres_piso[el['hasta']]}"
            salida.append(F(lista, nombre_elemento(lista, el), detalle, dato, ref=el["id"]))
    salida.append(
        F(
            "materiales",
            "Materiales y secciones",
            grupo=True,
            cantidad=len(materiales) + len(secciones),
        )
    )
    for m in materiales.values():
        detalle = f"f'c {m['fc']:g} MPa" if m["tipo"] == "hormigon" else f"fy {m['fy']:g} MPa"
        salida.append(
            F(
                "materiales",
                m["nombre"],
                detalle,
                "Hormigón" if m["tipo"] == "hormigon" else "Acero",
                ref=m["id"],
            )
        )
    return salida


# --- Planta -----------------------------------------------------------------------------


_Transformacion = Transformacion


def _metros(mm: float, longitud: str) -> float:
    """Pasa mm a la unidad de longitud de las coordenadas."""
    return mm / {"mm": 1.0, "cm": 10.0, "m": 1000.0}[longitud]


def _dist_segmento(p, a, b) -> float:
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    t = max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(p[0] - ax - t * dx, p[1] - ay - t * dy)


def _dentro(p, poligono) -> bool:
    """Punto dentro de un polígono (regla par-impar)."""
    x, y = p
    dentro = False
    n = len(poligono)
    for k in range(n):
        (x1, y1), (x2, y2) = poligono[k], poligono[(k + 1) % n]
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            dentro = not dentro
    return dentro


class PlantaEdificio(Navegable, QWidget):
    """Planta del piso elegido. Los colores salen de :mod:`estilo` al dibujar.

    Se navega con la rueda (zoom hacia el cursor), el botón del medio (paneo) y
    ``F`` (encuadrar); ver :mod:`nervi.gui.navegacion`.
    """

    def __init__(self, estado: EstadoEdificio) -> None:
        super().__init__()
        self.estado = estado
        self.setMinimumSize(320, 240)
        self.iniciar_navegacion()
        self.dibujo = DibujoEdificio(self, estado)
        estado.cambiado.connect(self.update)

    def _puntos(self, mf: ModeloFisico) -> list[tuple[float, float]]:
        pts: list[tuple[float, float]] = []
        for e in mf.lista("ejes"):
            pts += [tuple(e["p1"]), tuple(e["p2"])]
        for c in mf.lista("columnas"):
            pts.append(tuple(c["punto"]))
        for lista in ("vigas", "muros"):
            for el in mf.lista(lista):
                pts += [tuple(el["p1"]), tuple(el["p2"])]
        for losa in mf.lista("losas"):
            pts += [tuple(p) for p in losa["contorno"]]
        return pts

    def centro_lienzo(self) -> QPointF:
        return QPointF(self.width() / 2, (self.height() - 30) / 2)

    def ajuste(self) -> Vista | None:
        """Encuadre automático de todo el edificio (todas las plantas a la misma escala)."""
        mf = self.estado.modelo()
        pts = self._puntos(mf)
        if not pts:
            if self.estado.piso is None:
                return None
            # Planta vacía: 40 px por metro alrededor de (5, 4) m, para empezar a dibujar.
            m = METROS.get(mf.longitud, 1.0)
            return Vista(40.0 * m, 5.0 / m, 4.0 / m)
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        ancho, alto = max(xs) - min(xs), max(ys) - min(ys)
        margen = 70
        w, h = max(self.width() - 2 * margen, 50), max(self.height() - 2 * margen - 30, 50)
        escala = min(w / ancho if ancho else math.inf, h / alto if alto else math.inf)
        if not math.isfinite(escala):
            escala = 40.0
        return Vista(escala, (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)

    # -- dibujo ---------------------------------------------------------------------
    def paintEvent(self, _evento) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(estilo.PANEL))
        mf = self.estado.modelo()
        v = self.vista_actual()
        if v is not None:
            dibujar_grilla(p, QRectF(self.rect()), v, self.centro_lienzo())
        t = self.transformacion()
        piso = self.estado.piso
        if t is None or piso is None:
            p.setPen(QColor(estilo.TEXTO_3))
            p.drawText(
                self.rect(),
                Qt.AlignCenter,
                "Agregá un piso en el gestor de plantas o en la tabla Pisos",
            )
            return
        if not self._puntos(mf) and not self.dibujo.activo:
            p.setPen(QColor(estilo.TEXTO_3))
            p.drawText(
                self.rect(),
                Qt.AlignCenter,
                "Dibujá ejes, columnas, vigas, losas o muros con las herramientas de Dibujar",
            )
        p.setFont(QFont(self.font().family(), 8))
        self._ejes(p, t, mf)
        en = mf.en_piso(piso)
        elegido = self.estado.eleccion
        reparto = self.estado.reparto() if self.estado.cargas_visibles else None
        if reparto is not None:
            self._zonas(p, t, en["losas"], elegido, reparto)
        self._losas(p, t, mf, en["losas"], elegido, reparto)
        self._vigas(p, t, mf, en["vigas"], elegido, reparto)
        self._muros(p, t, mf, en["muros"], elegido)
        self._columnas(p, t, mf, en["columnas"], elegido)
        self._leyenda(p, mf, piso, en)
        self.dibujo.pintar(p, t)
        dibujar_coordenadas(p, self, v, self.centro_lienzo(), self.cursor_lienzo, mf.longitud)

    def _ejes(self, p: QPainter, t: _Transformacion, mf: ModeloFisico) -> None:
        for e in mf.lista("ejes"):
            a, b = t.a_pantalla(*e["p1"]), t.a_pantalla(*e["p2"])
            p.setPen(QPen(QColor(estilo.TEXTO_3), 1, Qt.DashDotLine))
            p.drawLine(a, b)
            # Burbuja en el extremo p2 (el de arriba o el de la derecha según se dibujó).
            largo = math.hypot(b.x() - a.x(), b.y() - a.y()) or 1.0
            c = b + QPointF((b.x() - a.x()) / largo * 13, (b.y() - a.y()) / largo * 13)
            p.setPen(QPen(QColor(estilo.TEXTO_2), 1))
            p.setBrush(QColor(estilo.PANEL))
            p.drawEllipse(c, 11, 11)
            p.drawText(QRectF(c.x() - 11, c.y() - 11, 22, 22), Qt.AlignCenter, e["nombre"][:3])

    def _color(self, lista: str, el: dict, elegido) -> QColor:
        return QColor(estilo.ACENTO if elegido == (lista, el["id"]) else estilo.ESTRUCTURA)

    def _losas(self, p, t, mf, losas, elegido, reparto=None) -> None:
        for losa in losas:
            poli = QPolygonF([t.a_pantalla(*q) for q in losa["contorno"]])
            sel = elegido == ("losas", losa["id"])
            relleno = QColor(estilo.ACENTO if sel else estilo.ESTRUCTURA)
            relleno.setAlphaF(0.12 if sel else 0.05)
            p.setPen(QPen(QColor(estilo.ACENTO), 2) if sel else Qt.NoPen)
            p.setBrush(relleno)
            p.drawPolygon(poli)
            centro = poli.boundingRect().center()
            f = QFont(self.font().family(), 8)
            f.setWeight(QFont.DemiBold)
            p.setFont(f)
            if reparto is not None:
                nombre = nombre_elemento("losas", losa)
                caja = QRectF(0, 0, p.fontMetrics().horizontalAdvance(nombre) + 12, 16)
                caja.moveCenter(QPointF(centro.x(), centro.y() - 10))
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(estilo.PANEL))
                p.drawRoundedRect(caja, 3, 3)
            p.setPen(QColor(estilo.ACENTO if sel else estilo.TEXTO_2))
            p.drawText(
                QRectF(centro.x() - 80, centro.y() - 18, 160, 16),
                Qt.AlignCenter,
                nombre_elemento("losas", losa),
            )
            p.setFont(QFont(self.font().family(), 8))
            p.setPen(QColor(estilo.TEXTO_3))
            area = mf.area_losa(losa["id"])
            texto = f"Maciza · e = {_medida(losa['espesor'])} cm · {area:.1f} {mf.longitud}²"
            if reparto is not None:
                q = reparto.cargas_losa[losa["id"]]
                texto = " · ".join(f"{ABREV[c]} {_kn(q[c], 2)}" for c in CASOS) + " kN/m²"
                if losa["id"] not in reparto.repartidas:
                    poli_borde = QPen(QColor(estilo.NEGATIVO), 1.5, Qt.DashLine)
                    p.setPen(poli_borde)
                    p.setBrush(Qt.NoBrush)
                    p.drawPolygon(poli)
                    p.setPen(QColor(estilo.NEGATIVO))
                    p.drawText(
                        QRectF(centro.x() - 110, centro.y() + 16, 220, 16),
                        Qt.AlignCenter,
                        "Sin repartir",
                    )
                    p.setPen(QColor(estilo.TEXTO_3))
            if reparto is not None:
                caja = QRectF(0, 0, p.fontMetrics().horizontalAdvance(texto) + 12, 16)
                caja.moveCenter(QPointF(centro.x(), centro.y() + 8))
                p.save()
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(estilo.PANEL))
                p.drawRoundedRect(caja, 3, 3)
                p.restore()
            p.drawText(QRectF(centro.x() - 130, centro.y(), 260, 16), Qt.AlignCenter, texto)

    def _zonas(self, p, t, losas, elegido, reparto: RepartoCargas) -> None:
        """Zonas tributarias de las losas del piso: líneas de quiebre a trazos y, si hay
        una viga o un muro elegido, su zona resaltada."""
        del_piso = {losa["id"] for losa in losas}
        for z in reparto.zonas:
            if z.losa not in del_piso:
                continue
            poli = QPolygonF([t.a_pantalla(*q) for q in z.contorno])
            if elegido in z.apoyos:
                relleno = QColor(estilo.ACENTO)
                relleno.setAlphaF(0.22)
                p.setBrush(relleno)
            else:
                p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor(estilo.TEXTO_3), 1, Qt.DashLine))
            p.drawPolygon(poli)

    def _franja(self, t, el: dict, ancho_mm: float, longitud: str) -> QPolygonF:
        (x1, y1), (x2, y2) = el["p1"], el["p2"]
        largo = math.hypot(x2 - x1, y2 - y1)
        nx, ny = -(y2 - y1) / largo, (x2 - x1) / largo
        m = _metros(ancho_mm, longitud) / 2
        return QPolygonF(
            [
                t.a_pantalla(x1 + nx * m, y1 + ny * m),
                t.a_pantalla(x2 + nx * m, y2 + ny * m),
                t.a_pantalla(x2 - nx * m, y2 - ny * m),
                t.a_pantalla(x1 - nx * m, y1 - ny * m),
            ]
        )

    def _vigas(self, p, t, mf, vigas, elegido, reparto=None) -> None:
        secciones = {s["id"]: s for s in mf.lista("secciones")}
        for v in vigas:
            s = secciones[v["seccion"]]
            ancho = s.get("b", s.get("d", 200.0))
            color = self._color("vigas", v, elegido)
            p.setPen(QPen(color, 2 if color.name() == QColor(estilo.ACENTO).name() else 1.2))
            p.setBrush(
                QColor(estilo.ACENTO_SUAVE)
                if elegido == ("vigas", v["id"])
                else QColor(estilo.PANEL)
            )
            franja = self._franja(t, v, ancho, mf.longitud)
            p.drawPolygon(franja)
            a, b = t.a_pantalla(*v["p1"]), t.a_pantalla(*v["p2"])
            angulo = math.degrees(math.atan2(-(b.y() - a.y()), b.x() - a.x()))
            if angulo > 90 or angulo <= -90:
                angulo += 180
            medio = (a + b) / 2
            p.save()
            p.translate(medio)
            p.rotate(-angulo)
            p.setPen(QColor(estilo.ACENTO if elegido == ("vigas", v["id"]) else estilo.TEXTO_3))
            alto = t.escala * _metros(ancho, mf.longitud) / 2
            texto = f"{nombre_elemento('vigas', v)} · {s['nombre']}"
            if reparto is not None:
                r = resultante(reparto, ("vigas", v["id"]), self.estado.caso)
                texto = f"{nombre_elemento('vigas', v)} · {_kn(r)} kN"
            p.drawText(QRectF(-90, -alto - 16, 180, 14), Qt.AlignCenter, texto)
            p.restore()

    def _muros(self, p, t, mf, muros, elegido) -> None:
        for m in muros:
            color = self._color("muros", m, elegido)
            relleno = QColor(color)
            relleno.setAlphaF(0.5)
            p.setPen(QPen(color, 1.2))
            p.setBrush(relleno)
            p.drawPolygon(self._franja(t, m, m["espesor"], mf.longitud))

    def _columnas(self, p, t, mf, columnas, elegido) -> None:
        secciones = {s["id"]: s for s in mf.lista("secciones")}
        for c in columnas:
            s = secciones[c["seccion"]]
            centro = t.a_pantalla(*c["punto"])
            p.setPen(Qt.NoPen)
            p.setBrush(self._color("columnas", c, elegido))
            if s["forma"] == "circular":
                r = t.escala * _metros(s["d"], mf.longitud) / 2
                p.drawEllipse(centro, r, r)
                continue
            bx = t.escala * _metros(s["b"], mf.longitud)
            hy = t.escala * _metros(s["h"], mf.longitud)
            p.save()
            p.translate(centro)
            p.rotate(-c.get("angulo", 0.0))
            p.drawRect(QRectF(-bx / 2, -hy / 2, bx, hy))
            p.restore()

    def _leyenda(self, p, mf, piso, en) -> None:
        pisos = {q["id"]: q for q in mf.lista("pisos")}
        n = sum(len(v) for v in en.values())
        q = pisos[piso]
        texto = f"{q['nombre']} · nivel {_nivel(q['nivel'])} {mf.longitud} · {n} elementos"
        r = QRectF(14, self.height() - 36, p.fontMetrics().horizontalAdvance(texto) + 24, 24)
        p.setPen(QPen(QColor(estilo.BORDE), 1))
        p.setBrush(QColor(estilo.PANEL))
        p.drawRoundedRect(r, 4, 4)
        p.setPen(QColor(estilo.TEXTO_2))
        p.drawText(r, Qt.AlignCenter, texto)

    # -- elección -------------------------------------------------------------------
    def elemento_en(self, punto: QPointF) -> tuple[str, int] | None:
        """El elemento de la planta bajo ``punto`` (en píxeles), o ``None``."""
        t = self.transformacion()
        piso = self.estado.piso
        if t is None or piso is None:
            return None
        mf = self.estado.modelo()
        en = mf.en_piso(piso)
        q = t.a_modelo(punto)
        tol = 6 / t.escala
        secciones = {s["id"]: s for s in mf.lista("secciones")}
        for c in en["columnas"]:
            s = secciones[c["seccion"]]
            medio = _metros(max(s.get("b", 0), s.get("h", 0), s.get("d", 0)), mf.longitud) / 2
            if (
                abs(q[0] - c["punto"][0]) <= medio + tol
                and abs(q[1] - c["punto"][1]) <= medio + tol
            ):
                return ("columnas", c["id"])
        for lista, ancho in (("muros", "espesor"), ("vigas", None)):
            for el in en[lista]:
                mm = el[ancho] if ancho else secciones[el["seccion"]].get("b", 200.0)
                if _dist_segmento(q, el["p1"], el["p2"]) <= _metros(mm, mf.longitud) / 2 + tol:
                    return (lista, el["id"])
        for losa in en["losas"]:
            if _dentro(q, losa["contorno"]):
                return ("losas", losa["id"])
        return None

    def mousePressEvent(self, evento) -> None:
        if self.navegacion_presionar(evento):
            return
        if evento.button() == Qt.RightButton and self.dibujo.activo:
            # Clic derecho: termina el trazo (como Esc).
            self.dibujo.cancelar()
            return
        if evento.button() != Qt.LeftButton:
            return
        self.setFocus()
        if self.dibujo.activo:
            self.dibujo.presionar(evento.position())
            return
        elegido = self.elemento_en(evento.position())
        self.estado.elegir(*(elegido or (None, None)))

    def mouseMoveEvent(self, evento) -> None:
        if not self.navegacion_mover(evento):
            self.dibujo.mover(evento.position())
        self.update()

    def mouseReleaseEvent(self, evento) -> None:
        if not self.navegacion_soltar(evento) and evento.button() == Qt.LeftButton:
            self.dibujo.soltar(evento.position())

    def keyPressEvent(self, evento) -> None:
        if self.dibujo.tecla(evento):
            evento.accept()
            return
        if evento.key() == Qt.Key_Delete and self.estado.eleccion is not None:
            self.borrar_eleccion()
            evento.accept()
            return
        super().keyPressEvent(evento)

    def leaveEvent(self, evento) -> None:
        self.dibujo.salir()
        super().leaveEvent(evento)

    def borrar_eleccion(self) -> bool:
        """Borra el elemento elegido (Supr). Se deshace con Ctrl+Z."""
        lista, id = self.estado.eleccion
        if lista not in ELEMENTOS and lista != "ejes":
            return False
        return self.estado.aplicar(lambda mf: mf.quitar(lista, id), "Borrar elemento")


# --- Tablas ------------------------------------------------------------------------------


@dataclass(frozen=True)
class Col:
    titulo: str
    clave: str
    tipo: str = "num"  # num, texto, opcion, piso, seccion, material, x, y, contorno, mm, id
    indice: int = 0  # para x e y: 0 = x, 1 = y
    opcional: bool = False


COLUMNAS: dict[str, tuple[Col, ...]] = {
    "pisos": (
        Col("Id", "id", "id"),
        Col("Nombre", "nombre", "texto"),
        Col("Nivel", "nivel"),
        Col("Permanente [kN/m²]", "permanente", opcional=True),
        Col("Sobrecarga [kN/m²]", "sobrecarga", opcional=True),
    ),
    "ejes": (
        Col("Id", "id", "id"),
        Col("Nombre", "nombre", "texto"),
        Col("x₁", "p1", "x"),
        Col("y₁", "p1", "y", 1),
        Col("x₂", "p2", "x"),
        Col("y₂", "p2", "y", 1),
    ),
    "materiales": (
        Col("Id", "id", "id"),
        Col("Nombre", "nombre", "texto"),
        Col("Tipo", "tipo", "opcion"),
        Col("f'c [MPa]", "fc", opcional=True),
        Col("fy [MPa]", "fy", opcional=True),
        Col("fu [MPa]", "fu", opcional=True),
        Col("E [MPa]", "E", opcional=True),
        Col("Peso [kN/m³]", "peso", opcional=True),
    ),
    "secciones": (
        Col("Id", "id", "id"),
        Col("Nombre", "nombre", "texto"),
        Col("Forma", "forma", "opcion"),
        Col("b [mm]", "b", opcional=True),
        Col("h [mm]", "h", opcional=True),
        Col("d [mm]", "d", opcional=True),
    ),
    "columnas": (
        Col("Id", "id", "id"),
        Col("Nombre", "nombre", "texto", opcional=True),
        Col("x", "punto", "x"),
        Col("y", "punto", "y", 1),
        Col("Desde", "desde", "piso"),
        Col("Hasta", "hasta", "piso"),
        Col("Sección", "seccion", "seccion"),
        Col("Material", "material", "material"),
        Col("Giro [°]", "angulo", opcional=True),
    ),
    "vigas": (
        Col("Id", "id", "id"),
        Col("Nombre", "nombre", "texto", opcional=True),
        Col("x₁", "p1", "x"),
        Col("y₁", "p1", "y", 1),
        Col("x₂", "p2", "x"),
        Col("y₂", "p2", "y", 1),
        Col("Sección", "seccion", "seccion"),
        Col("Material", "material", "material"),
    ),
    "losas": (
        Col("Id", "id", "id"),
        Col("Nombre", "nombre", "texto", opcional=True),
        Col("Contorno (x, y; …)", "contorno", "contorno"),
        Col("Espesor [mm]", "espesor"),
        Col("Material", "material", "material"),
        Col("Permanente [kN/m²]", "permanente", opcional=True),
        Col("Sobrecarga [kN/m²]", "sobrecarga", opcional=True),
    ),
    "muros": (
        Col("Id", "id", "id"),
        Col("Nombre", "nombre", "texto", opcional=True),
        Col("x₁", "p1", "x"),
        Col("y₁", "p1", "y", 1),
        Col("x₂", "p2", "x"),
        Col("y₂", "p2", "y", 1),
        Col("Desde", "desde", "piso"),
        Col("Hasta", "hasta", "piso"),
        Col("Espesor [mm]", "espesor"),
        Col("Material", "material", "material"),
    ),
}

OPCIONES = {"tipo": formato_fisico.TIPOS_MATERIAL, "forma": formato_fisico.FORMAS_SECCION}
_REF = {"piso": "pisos", "seccion": "secciones", "material": "materiales"}


def _numero(texto) -> float:
    return float(str(texto).strip().replace(",", ".").replace("−", "-").replace("±", ""))


def texto_contorno(contorno: list) -> str:
    return "; ".join(f"{x:g}, {y:g}" for x, y in contorno)


def leer_contorno(texto: str) -> list[list[float]]:
    puntos = []
    for parte in str(texto).split(";"):
        if not parte.strip():
            continue
        x, y = parte.split(",")
        puntos.append([_numero(x), _numero(y)])
    return puntos


class TablaFisico(QAbstractTableModel):
    """Una lista del modelo físico como tabla editable. Los elementos de planta
    (columnas, vigas, losas y muros) muestran solo los del piso elegido."""

    def __init__(self, estado: EstadoEdificio, lista: str) -> None:
        super().__init__()
        self.estado = estado
        self.lista = lista
        self.columnas = COLUMNAS[lista]
        self._filas: list[dict] = []
        self._mf = ModeloFisico()
        estado.cambiado.connect(self.recargar)
        self.recargar()

    def recargar(self) -> None:
        self.beginResetModel()
        self._mf = self.estado.modelo()
        if self.lista in ELEMENTOS:
            piso = self.estado.piso
            self._filas = self._mf.en_piso(piso)[self.lista] if piso is not None else []
        else:
            self._filas = self._mf.lista(self.lista)
            if self.lista == "pisos":
                self._filas.sort(key=lambda p: -p["nivel"])
        self.endResetModel()

    def id_de_fila(self, fila: int) -> int:
        return self._filas[fila]["id"]

    def fila_de_id(self, id: int) -> int | None:
        return next((k for k, el in enumerate(self._filas) if el["id"] == id), None)

    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._filas)

    def columnCount(self, parent=QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self.columnas)

    def headerData(self, seccion, orientacion, rol=Qt.DisplayRole):
        if rol == Qt.DisplayRole and orientacion == Qt.Horizontal:
            return self.columnas[seccion].titulo
        return None

    def opciones(self, col: Col) -> list[str]:
        if col.tipo == "opcion":
            return list(OPCIONES[col.clave])
        if col.tipo in _REF:
            return [e["nombre"] for e in self._mf.lista(_REF[col.tipo])]
        return []

    def _texto(self, el: dict, col: Col) -> str:
        if col.clave not in el:
            return ""
        v = el[col.clave]
        if col.tipo in ("x", "y"):
            return f"{v[col.indice]:g}"
        if col.tipo in _REF:
            return next((e["nombre"] for e in self._mf.lista(_REF[col.tipo]) if e["id"] == v), "")
        if col.tipo == "contorno":
            return texto_contorno(v)
        if col.tipo in ("num",):
            return f"{v:g}"
        return str(v)

    def data(self, indice: QModelIndex, rol=Qt.DisplayRole):
        if not indice.isValid():
            return None
        el, col = self._filas[indice.row()], self.columnas[indice.column()]
        if rol == Qt.EditRole or (rol == Qt.DisplayRole and self._heredada(el, col) is None):
            return self._texto(el, col)
        if rol == Qt.TextAlignmentRole and col.tipo in ("num", "x", "y", "id"):
            return int(Qt.AlignRight | Qt.AlignVCenter)
        if rol == Qt.ForegroundRole and col.tipo == "id":
            return QColor(estilo.TEXTO_3)
        heredada = self._heredada(el, col)
        if heredada is not None:
            if rol == Qt.DisplayRole:
                return f"{heredada:g}"
            if rol == Qt.ForegroundRole:
                return QColor(estilo.TEXTO_3)
            if rol == Qt.ToolTipRole:
                return "Toma la del piso. Escribí un valor para que la losa tenga la suya."
        return None

    def _heredada(self, el: dict, col: Col) -> float | None:
        """En las losas sin carga propia, la carga del piso que toman (para mostrarla)."""
        if self.lista != "losas" or col.clave not in ("permanente", "sobrecarga"):
            return None
        if col.clave in el:
            return None
        piso = next((q for q in self._mf.lista("pisos") if q["id"] == el["piso"]), {})
        return piso.get(col.clave, 0.0)

    def flags(self, indice: QModelIndex):
        base = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        if self.columnas[indice.column()].tipo == "id":
            return base
        return base | Qt.ItemIsEditable

    def valor(self, col: Col, el: dict, texto):
        """Convierte lo escrito en el valor de ``fisico.json`` (``None`` = quitar)."""
        texto = str(texto if texto is not None else "").strip()
        if not texto:
            if col.opcional:
                return None
            raise ValueError(f"{col.titulo}: no puede quedar vacío")
        if col.tipo in ("x", "y"):
            punto = list(el[col.clave])
            punto[col.indice] = _numero(texto)
            return punto
        if col.tipo in _REF:
            for e in self._mf.lista(_REF[col.tipo]):
                if e["nombre"] == texto or str(e["id"]) == texto:
                    return e["id"]
            raise ValueError(f"no hay {SINGULAR[_REF[col.tipo]].lower()} {texto!r}")
        if col.tipo == "contorno":
            return leer_contorno(texto)
        if col.tipo == "num":
            return _numero(texto)
        return texto

    def setData(self, indice: QModelIndex, valor, rol=Qt.EditRole) -> bool:
        if not indice.isValid() or rol != Qt.EditRole:
            return False
        el, col = self._filas[indice.row()], self.columnas[indice.column()]
        try:
            nuevo = self.valor(col, el, valor)
        except ValueError as e:
            self.estado.mensaje.emit(str(e))
            return False
        if nuevo == el.get(col.clave):
            return False
        return self.estado.aplicar(
            lambda mf: mf.editar(self.lista, el["id"], **{col.clave: nuevo}),
            f"Cambiar {col.titulo.lower()} de {nombre_elemento(self.lista, el)}",
        )


class _DelegadoOpciones(QStyledItemDelegate):
    """Desplegable para las columnas de opciones y referencias (piso, sección, material)."""

    def createEditor(self, padre, opcion, indice):
        modelo: TablaFisico = indice.model()
        col = modelo.columnas[indice.column()]
        opciones = modelo.opciones(col)
        if not opciones:
            return super().createEditor(padre, opcion, indice)
        combo = QComboBox(padre)
        combo.addItems(opciones)
        return combo

    def setEditorData(self, editor, indice):
        if isinstance(editor, QComboBox):
            editor.setCurrentText(indice.data(Qt.EditRole))
        else:
            super().setEditorData(editor, indice)

    def setModelData(self, editor, modelo, indice):
        if isinstance(editor, QComboBox):
            modelo.setData(indice, editor.currentText(), Qt.EditRole)
        else:
            super().setModelData(editor, modelo, indice)


class EditorFisico(QWidget):
    """Tabla de una lista con *Agregar* y *Eliminar*."""

    def __init__(self, estado: EstadoEdificio, lista: str) -> None:
        super().__init__()
        self.estado = estado
        self.lista = lista
        self.modelo = TablaFisico(estado, lista)
        self.tabla = QTableView()
        self.tabla.setModel(self.modelo)
        self.tabla.setItemDelegate(_DelegadoOpciones(self.tabla))
        self.tabla.verticalHeader().hide()
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tabla.setSelectionBehavior(QTableView.SelectRows)
        self.tabla.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tabla.clicked.connect(self._fila_elegida)
        agregar, eliminar = QPushButton("Agregar"), QPushButton("Eliminar")
        agregar.clicked.connect(self.agregar)
        eliminar.clicked.connect(self.eliminar)
        self.lbl_info = QLabel(objectName="tenue")
        botones = QHBoxLayout()
        botones.setContentsMargins(0, 0, 0, 0)
        botones.addWidget(agregar)
        botones.addWidget(eliminar)
        botones.addStretch()
        botones.addWidget(self.lbl_info)
        capa = QVBoxLayout(self)
        capa.setContentsMargins(10, 6, 10, 6)
        capa.setSpacing(6)
        capa.addLayout(botones)
        capa.addWidget(self.tabla)
        estado.cambiado.connect(self._actualizar)
        self._actualizar()

    def _actualizar(self) -> None:
        n = self.modelo.rowCount()
        if self.lista in ELEMENTOS:
            mf = self.estado.modelo()
            piso = self.estado.piso
            nombre = next((p["nombre"] for p in mf.lista("pisos") if p["id"] == piso), "Sin pisos")
            self.lbl_info.setText(f"{nombre} · {n} {TITULOS[self.lista].lower()}")
        else:
            self.lbl_info.setText(f"{n} {TITULOS[self.lista].lower()}")
        el = self.estado.eleccion
        if el and el[0] == self.lista:
            fila = self.modelo.fila_de_id(el[1])
            if fila is not None:
                self.tabla.selectRow(fila)

    def _fila_elegida(self, indice: QModelIndex) -> None:
        self.estado.elegir(self.lista, self.modelo.id_de_fila(indice.row()))

    def agregar(self) -> None:
        estado = self.estado

        def cambio(mf: ModeloFisico) -> None:
            nuevo_elemento(mf, self.lista, estado.piso)

        if estado.aplicar(cambio, f"Agregar {SINGULAR[self.lista].lower()}"):
            self.tabla.scrollToBottom()

    def eliminar(self) -> None:
        filas = {i.row() for i in self.tabla.selectionModel().selectedRows()}
        if not filas:
            return
        ids = [self.modelo.id_de_fila(f) for f in filas]

        def cambio(mf: ModeloFisico) -> None:
            for id in ids:
                if self.lista == "pisos":
                    mf.quitar_piso(id)
                else:
                    mf.quitar(self.lista, id)

        self.estado.aplicar(cambio, f"Eliminar {SINGULAR[self.lista].lower()}")


def _nombre_libre(mf: ModeloFisico, lista: str, base: str) -> str:
    """El primer nombre ``base k`` libre: con Piso 1 a Piso 3, Piso 4."""
    usados = {e["nombre"] for e in mf.lista(lista)}
    k = 1
    while f"{base} {k}" in usados:
        k += 1
    return f"{base} {k}"


def _hormigon(mf: ModeloFisico) -> int:
    for m in mf.lista("materiales"):
        if m["tipo"] == "hormigon":
            return m["id"]
    return mf.agregar_material(_nombre_libre(mf, "materiales", "H-25"), "hormigon", fc=25.0)


def _seccion(mf: ModeloFisico, b: float, h: float) -> int:
    for s in mf.lista("secciones"):
        if s["forma"] == "rectangular" and (s["b"], s["h"]) == (b, h):
            return s["id"]
    nombre = f"{_medida(b)}x{_medida(h)}"
    usados = {s["nombre"] for s in mf.lista("secciones")}
    return mf.agregar_seccion(
        nombre if nombre not in usados else _nombre_libre(mf, "secciones", nombre),
        "rectangular",
        b=b,
        h=h,
    )


def nuevo_elemento(mf: ModeloFisico, lista: str, piso: int | None) -> int:
    """Agrega un elemento con valores por omisión para empezar a editarlo en la tabla.

    Si faltan el material o la sección, se crean (hormigón H-25 y una sección
    rectangular habitual); los elementos de planta necesitan un piso elegido y, las
    columnas y los muros, un piso debajo."""
    if lista == "pisos":
        pisos = mf.pisos_ordenados()
        nivel = pisos[-1]["nivel"] + 3.0 if pisos else 0.0
        nombre = "Planta baja" if not pisos else _nombre_libre(mf, "pisos", "Piso")
        return mf.agregar_piso(nombre, nivel)
    if lista == "ejes":
        k = len(mf.lista("ejes"))
        return mf.agregar_eje(_nombre_libre(mf, "ejes", "Eje"), (float(k), 0.0), (float(k), 5.0))
    if lista == "materiales":
        return mf.agregar_material(_nombre_libre(mf, "materiales", "H-25"), "hormigon", fc=25.0)
    if lista == "secciones":
        return mf.agregar_seccion(
            _nombre_libre(mf, "secciones", "Sección"), "rectangular", b=300.0, h=300.0
        )
    if piso is None:
        raise ValueError("Primero agregá un piso")
    abajo = mf.piso_de_abajo(piso)
    if lista in ("columnas", "muros") and abajo is None:
        raise ValueError(
            "Las columnas y los muros llegan a un piso desde el de abajo: elegí un piso más alto"
        )
    h25 = _hormigon(mf)
    if lista == "columnas":
        return mf.agregar_columna((0.0, 0.0), abajo, piso, _seccion(mf, 300.0, 300.0), h25)
    if lista == "vigas":
        return mf.agregar_viga(piso, (0.0, 0.0), (5.0, 0.0), _seccion(mf, 200.0, 400.0), h25)
    if lista == "losas":
        return mf.agregar_losa(piso, [(0.0, 0.0), (5.0, 0.0), (5.0, 4.0), (0.0, 4.0)], 120.0, h25)
    return mf.agregar_muro((0.0, 0.0), (5.0, 0.0), abajo, piso, 200.0, h25)


class TablasEdificio(QTabWidget):
    """Una pestaña por lista del modelo físico."""

    ORDEN = ("pisos", "ejes", "columnas", "vigas", "losas", "muros", "materiales", "secciones")

    def __init__(self, estado: EstadoEdificio) -> None:
        super().__init__()
        self.editores = {lista: EditorFisico(estado, lista) for lista in self.ORDEN}
        for lista in self.ORDEN:
            self.addTab(self.editores[lista], TITULOS[lista])

    def mostrar(self, lista: str) -> None:
        self.setCurrentWidget(self.editores[lista])


# --- Propiedades -------------------------------------------------------------------------


class PropiedadesEdificio(QWidget):
    """Datos del elemento elegido, editables; sin elección, los del piso que se ve."""

    def __init__(self, estado: EstadoEdificio) -> None:
        super().__init__(objectName="panel")
        self.estado = estado
        capa = QVBoxLayout(self)
        capa.setContentsMargins(14, 12, 14, 12)
        capa.setSpacing(8)
        self.lbl_tipo = QLabel(objectName="seccion")
        self.lbl_nombre = QLabel(objectName="titulo")
        self.lbl_nombre.setStyleSheet("font-size: 12pt;")
        self.form = QFormLayout()
        self.form.setHorizontalSpacing(12)
        self.form.setVerticalSpacing(6)
        self.lbl_nota = QLabel(objectName="tenue")
        self.lbl_nota.setWordWrap(True)
        self.lbl_error = QLabel(objectName="aviso")
        self.lbl_error.setWordWrap(True)
        self.lbl_error.hide()
        for w in (self.lbl_tipo, self.lbl_nombre):
            capa.addWidget(w)
        capa.addLayout(self.form)
        capa.addWidget(self.lbl_nota)
        capa.addWidget(self.lbl_error)
        capa.addStretch()
        self.setMinimumWidth(240)
        estado.cambiado.connect(self.actualizar)
        estado.mensaje.connect(self.mostrar_error)
        self.actualizar()

    def mostrar_error(self, texto: str) -> None:
        self.lbl_error.setText(texto)
        self.lbl_error.setVisible(bool(texto))

    def _limpiar(self) -> None:
        # takeRow y deleteLater: el campo que se está editando puede ser el que avisó
        # del cambio, y no se borra mientras emite su señal.
        while self.form.rowCount():
            fila = self.form.takeRow(0)
            for item in (fila.labelItem, fila.fieldItem):
                if item is not None and item.widget() is not None:
                    item.widget().hide()
                    item.widget().deleteLater()
        self.lbl_nota.setText("")

    def actualizar(self) -> None:
        self._limpiar()
        self.lbl_error.hide()
        mf = self.estado.modelo()
        el = self.estado.eleccion
        if el is None:
            self._piso(mf)
            return
        lista, id = el
        datos = mf.elemento(lista, id)
        self.lbl_tipo.setText(SINGULAR[lista].upper())
        self.lbl_nombre.setText(nombre_elemento(lista, datos))
        for col in COLUMNAS[lista]:
            if col.tipo == "id":
                continue
            self.form.addRow(col.titulo, self._control(mf, lista, datos, col))
        if lista == "vigas":
            self.form.addRow("Largo", QLabel(f"{mf.largo_viga(id):.3f} {mf.longitud}"))
        elif lista == "losas":
            self.form.addRow("Área", QLabel(f"{mf.area_losa(id):.2f} {mf.longitud}²"))
            self._cargas_losa(mf, datos)
        elif lista == "columnas":
            self.form.addRow("Altura", QLabel(f"{mf.altura_columna(id):.3f} {mf.longitud}"))
        if lista in ("vigas", "muros"):
            self._cargas_apoyo(mf, (lista, id))
        self.lbl_nota.setText("Los cambios se deshacen con Ctrl+Z.")

    def _titulo_seccion(self, texto: str) -> None:
        etiqueta = QLabel(texto.upper(), objectName="seccion")
        etiqueta.setContentsMargins(0, 8, 0, 0)
        self.form.addRow(etiqueta)

    def _cargas_losa(self, mf: ModeloFisico, losa: dict) -> None:
        """Peso propio que resulta y, en los campos vacíos, las cargas que toma del piso."""
        q = mf.cargas_losa(losa["id"])
        piso = mf.elemento("pisos", losa["piso"])
        for k in range(self.form.rowCount()):
            campo = self.form.itemAt(k, QFormLayout.FieldRole)
            w = campo.widget() if campo is not None else None
            clave = w.property("clave") if w is not None else None
            if isinstance(w, QLineEdit) and clave in ("permanente", "sobrecarga"):
                w.setPlaceholderText(f"del piso: {_kn(piso.get(clave, 0.0), 2)}")
        self.form.addRow("Peso propio", QLabel(f"{_kn(q['peso_propio'], 2)} kN/m²"))
        r = self.estado.reparto()
        if losa["id"] not in r.repartidas:
            aviso = next((a for a in r.avisos if a.losa == losa["id"]), None)
            texto = QLabel(aviso.texto if aviso else "Sin repartir", objectName="aviso")
            texto.setWordWrap(True)
            self.form.addRow(texto)

    def _cargas_apoyo(self, mf: ModeloFisico, apoyo: tuple[str, int]) -> None:
        """Lo que recibe de las losas: diagrama del caso que se ve y, por caso, la
        resultante y la carga máxima."""
        r = self.estado.reparto()
        self._titulo_seccion("Cargas de losas")
        if not r.de(apoyo):
            self.form.addRow(QLabel("No recibe cargas de losas.", objectName="tenue"))
            return
        el = mf.elemento(*apoyo)
        largo = math.dist(el["p1"], el["p2"])
        caso = self.estado.caso
        self.form.addRow(DiagramaCarga(diagrama(r, apoyo, caso), largo, mf.longitud))
        tabla = QWidget()
        g = QGridLayout(tabla)
        g.setContentsMargins(0, 0, 0, 0)
        g.setHorizontalSpacing(10)
        g.setVerticalSpacing(3)
        for k, titulo in enumerate(("", "kN", "máx kN/m")):
            g.addWidget(QLabel(titulo, objectName="tenue"), 0, k, Qt.AlignRight)
        for fila, c in enumerate((*CASOS, "total"), start=1):
            qmax = max(q for _, q in diagrama(r, apoyo, c))
            celdas = (
                CASOS_VISTA[c] if c != "total" else "Total",
                _kn(resultante(r, apoyo, c)),
                _kn(qmax, 2),
            )
            for k, texto in enumerate(celdas):
                etiqueta = QLabel(texto)
                if c == caso:
                    etiqueta.setStyleSheet(f"color: {estilo.ACENTO}; font-weight: 600;")
                g.addWidget(etiqueta, fila, k, Qt.AlignLeft if k == 0 else Qt.AlignRight)
        self.form.addRow(tabla)
        area = r.area_tributaria(apoyo)
        self.form.addRow("Área tributaria", QLabel(f"{area:.2f} {mf.longitud}²"))

    def _piso(self, mf: ModeloFisico) -> None:
        piso = self.estado.piso
        self.lbl_tipo.setText("PLANTA")
        if piso is None:
            self.lbl_nombre.setText("Sin pisos")
            self.lbl_nota.setText(
                "Agregá el primer piso en el gestor de plantas o en la tabla Pisos."
            )
            return
        p = mf.elemento("pisos", piso)
        self.lbl_nombre.setText(p["nombre"])
        self.form.addRow("Nivel", QLabel(f"{_nivel(p['nivel'])} {mf.longitud}"))
        abajo = mf.piso_de_abajo(piso)
        if abajo is not None:
            h = p["nivel"] - mf.nivel(abajo)
            self.form.addRow("Entrepiso", QLabel(f"{h:.2f} {mf.longitud}"))
        for lista, v in mf.en_piso(piso).items():
            self.form.addRow(TITULOS[lista], QLabel(str(len(v))))
        self._titulo_seccion("Cargas de las losas")
        for col in COLUMNAS["pisos"]:
            if col.clave in ("permanente", "sobrecarga"):
                campo = self._control(mf, "pisos", p, col)
                campo.setPlaceholderText("0,00")
                self.form.addRow(col.titulo.replace(" [kN/m²]", ""), campo)
        nota = QLabel("En kN/m², además del peso propio de cada losa.", objectName="tenue")
        nota.setWordWrap(True)
        self.form.addRow(nota)
        self.lbl_nota.setText("Hacé clic en un elemento de la planta para ver y cambiar sus datos.")

    def _control(self, mf: ModeloFisico, lista: str, datos: dict, col: Col) -> QWidget:
        modelo = _TablaSuelta(self.estado, lista, mf)
        texto = modelo._texto(datos, col)

        def aplicar(valor) -> None:
            try:
                nuevo = modelo.valor(col, datos, valor)
            except ValueError as e:
                self.mostrar_error(str(e))
                return
            if nuevo != datos.get(col.clave):
                self.estado.aplicar(
                    lambda m: m.editar(lista, datos["id"], **{col.clave: nuevo}),
                    f"Cambiar {col.titulo.lower()} de {nombre_elemento(lista, datos)}",
                )

        opciones = modelo.opciones(col)
        if opciones:
            combo = QComboBox()
            combo.addItems(opciones)
            combo.setCurrentText(texto)
            combo.activated.connect(lambda _k: aplicar(combo.currentText()))
            return combo
        campo = QLineEdit(texto)
        campo.setProperty("clave", col.clave)
        if col.tipo in ("num", "x", "y"):
            campo.setAlignment(Qt.AlignRight)
        campo.editingFinished.connect(lambda: aplicar(campo.text()))
        return campo


class DiagramaCarga(QWidget):
    """Carga lineal sobre una viga o un muro, a lo largo de su eje (p1 a la izquierda)."""

    def __init__(self, puntos: list[tuple], largo: float, longitud: str) -> None:
        super().__init__()
        self.puntos, self.largo, self.longitud = puntos, largo, longitud
        self.setMinimumHeight(96)

    def paintEvent(self, _evento) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        f = QFont(self.font().family(), 8)
        p.setFont(f)
        izq, der, arriba, abajo = 4, self.width() - 4, 18, self.height() - 18
        qmax = max((q for _, q in self.puntos), default=0.0) or 1.0

        def a_px(s: float, q: float) -> QPointF:
            return QPointF(izq + (der - izq) * s / self.largo, abajo - (abajo - arriba) * q / qmax)

        relleno = QColor(estilo.ACENTO)
        relleno.setAlphaF(0.16)
        poli = [a_px(self.puntos[0][0], 0.0), *(a_px(s, q) for s, q in self.puntos)]
        poli.append(a_px(self.puntos[-1][0], 0.0))
        p.setPen(QPen(QColor(estilo.ACENTO), 1.5))
        p.setBrush(relleno)
        p.drawPolygon(QPolygonF(poli))
        # La viga y sus extremos.
        p.setPen(QPen(QColor(estilo.ESTRUCTURA), 2))
        p.drawLine(QPointF(izq, abajo), QPointF(der, abajo))
        p.setPen(QColor(estilo.TEXTO_3))
        p.drawText(QRectF(izq, abajo + 2, 60, 14), Qt.AlignLeft, "0")
        p.drawText(
            QRectF(der - 80, abajo + 2, 80, 14), Qt.AlignRight, f"{_n(self.largo)} {self.longitud}"
        )
        s_max, q_max = max(self.puntos, key=lambda x: x[1])
        cima = a_px(s_max, q_max)
        p.setPen(QColor(estilo.ACENTO))
        p.drawText(
            QRectF(cima.x() - 60, arriba - 17, 120, 14), Qt.AlignCenter, f"{_kn(q_max, 2)} kN/m"
        )


class _TablaSuelta(TablaFisico):
    """Las conversiones de :class:`TablaFisico` sin conectarse a la sesión."""

    def __init__(self, estado: EstadoEdificio, lista: str, mf: ModeloFisico) -> None:
        QAbstractTableModel.__init__(self)
        self.estado = estado
        self.lista = lista
        self.columnas = COLUMNAS[lista]
        self._filas = []
        self._mf = mf


# --- Gestor de plantas ------------------------------------------------------------------


def _caja(titulo: str, contenido) -> QWidget:
    w = QWidget()
    c = QVBoxLayout(w)
    c.setContentsMargins(0, 0, 0, 0)
    c.setSpacing(6)
    c.addWidget(QLabel(titulo.upper(), objectName="seccion"))
    caja = QWidget(objectName="caja_ajustes")
    caja.setAttribute(Qt.WA_StyledBackground)
    kc = QVBoxLayout(caja)
    kc.setContentsMargins(14, 12, 14, 12)
    kc.addLayout(contenido)
    c.addWidget(caja)
    return w


class GestorPlantas(QDialog):
    """Agregar, editar, quitar y copiar plantas sobre una copia del modelo físico.

    *Aceptar* aplica todo junto (un solo Ctrl+Z lo deshace); *Cancelar* lo descarta."""

    def __init__(self, estado: EstadoEdificio, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.estado = estado
        self.mf = estado.modelo()
        self.cambios = 0
        self.setWindowTitle("Plantas")
        self.resize(980, 600)
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        cabecera = QWidget(objectName="barra")
        cabecera.setAttribute(Qt.WA_StyledBackground)
        c = QHBoxLayout(cabecera)
        c.setContentsMargins(16, 10, 16, 10)
        c.addWidget(QLabel("Plantas", objectName="titulo"))
        c.addWidget(QLabel(estado.sesion.titulo, objectName="tenue"))
        c.addStretch()
        raiz.addWidget(cabecera)

        medio = QHBoxLayout()
        medio.setContentsMargins(16, 14, 16, 14)
        medio.setSpacing(18)
        izq = QVBoxLayout()
        izq.setSpacing(8)
        izq.addWidget(
            QLabel(
                "De arriba hacia abajo. El nivel es la cara superior de la losa.",
                objectName="tenue",
            )
        )
        self.tabla = QTableWidget(0, 4)
        self.tabla.setHorizontalHeaderLabels(
            [
                "Planta",
                f"Nivel [{self.mf.longitud}]",
                f"Entrepiso [{self.mf.longitud}]",
                "Elementos",
            ]
        )
        self.tabla.verticalHeader().hide()
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabla.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tabla.setEditTriggers(QAbstractItemView.NoEditTriggers)
        cab = self.tabla.horizontalHeader()
        cab.setSectionResizeMode(0, QHeaderView.Stretch)
        for j in (1, 2, 3):
            cab.setSectionResizeMode(j, QHeaderView.ResizeToContents)
        self.tabla.itemSelectionChanged.connect(self._elegida)
        izq.addWidget(self.tabla, 1)
        botones = QHBoxLayout()
        self.b_arriba = QPushButton("Agregar arriba")
        self.b_abajo = QPushButton("Agregar abajo")
        self.b_quitar = QPushButton("Quitar planta", objectName="peligro")
        self.b_arriba.clicked.connect(lambda: self.agregar(arriba=True))
        self.b_abajo.clicked.connect(lambda: self.agregar(arriba=False))
        self.b_quitar.clicked.connect(self.quitar)
        botones.addWidget(self.b_arriba)
        botones.addWidget(self.b_abajo)
        botones.addStretch()
        botones.addWidget(self.b_quitar)
        izq.addLayout(botones)
        medio.addLayout(izq, 3)

        der = QVBoxLayout()
        der.setSpacing(14)
        f = QFormLayout()
        f.setHorizontalSpacing(14)
        f.setVerticalSpacing(8)
        self.e_nombre = QLineEdit()
        self.e_nombre.editingFinished.connect(self._nombre)
        self.e_nivel = self._numero()
        self.e_nivel.editingFinished.connect(self._nivel)
        self.e_entrepiso = self._numero()
        self.e_entrepiso.setMinimum(0.01)
        self.e_entrepiso.editingFinished.connect(self._entrepiso)
        self.c_mover = QCheckBox("Mover las plantas de arriba con el nuevo entrepiso")
        self.c_mover.setChecked(True)
        f.addRow("Nombre", self.e_nombre)
        f.addRow("Nivel", self.e_nivel)
        f.addRow("Altura de entrepiso", self.e_entrepiso)
        f.addRow("", self.c_mover)
        der.addWidget(_caja("Planta elegida", f))

        g = QGridLayout()
        g.setHorizontalSpacing(14)
        g.setVerticalSpacing(8)
        g.addWidget(QLabel("Copiar de"), 0, 0)
        self.c_origen = QComboBox()
        self.c_origen.currentIndexChanged.connect(self._destinos)
        g.addWidget(self.c_origen, 0, 1, 1, 3)
        g.addWidget(QLabel("Qué"), 1, 0)
        self.c_que: dict[str, QCheckBox] = {}
        for k, lista in enumerate(ELEMENTOS):
            b = QCheckBox(TITULOS[lista])
            b.setChecked(lista != "muros")
            b.toggled.connect(self._boton_copiar)
            self.c_que[lista] = b
            g.addWidget(b, 1 + k // 2, 1 + k % 2)
        g.addWidget(QLabel("A las plantas"), 3, 0)
        self.caja_destinos = QGridLayout()
        self.caja_destinos.setHorizontalSpacing(14)
        g.addLayout(self.caja_destinos, 3, 1, 1, 3)
        self.c_destinos: dict[int, QCheckBox] = {}
        nota = QLabel(
            "Las columnas y los muros copiados van del piso de abajo al de destino. Lo que "
            "ya hay en el destino se conserva.",
            objectName="tenue",
        )
        nota.setWordWrap(True)
        g.addWidget(nota, 4, 0, 1, 4)
        fila = QHBoxLayout()
        self.lbl_copia = QLabel(objectName="tenue")
        fila.addWidget(self.lbl_copia)
        fila.addStretch()
        self.b_copiar = QPushButton("Copiar")
        self.b_copiar.clicked.connect(self.copiar)
        fila.addWidget(self.b_copiar)
        g.addLayout(fila, 5, 0, 1, 4)
        der.addWidget(_caja("Copiar elementos", g))
        self.lbl_error = QLabel(objectName="aviso")
        self.lbl_error.setWordWrap(True)
        self.lbl_error.hide()
        der.addWidget(self.lbl_error)
        der.addStretch()
        medio.addLayout(der, 2)
        raiz.addLayout(medio, 1)

        pie = QWidget(objectName="pie_ajustes")
        pie.setAttribute(Qt.WA_StyledBackground)
        p = QHBoxLayout(pie)
        p.setContentsMargins(16, 10, 16, 10)
        p.addWidget(
            QLabel(
                "Los cambios se aplican al aceptar y se deshacen con Ctrl+Z.", objectName="tenue"
            )
        )
        p.addStretch()
        cancelar = QPushButton("Cancelar", objectName="fantasma")
        aceptar = QPushButton("Aceptar", objectName="primario")
        cancelar.clicked.connect(self.reject)
        aceptar.clicked.connect(self.accept)
        p.addWidget(cancelar)
        p.addWidget(aceptar)
        raiz.addWidget(pie)
        self.elegida: int | None = estado.piso if estado.piso in self._ids() else None
        self._llenar()

    @staticmethod
    def _numero() -> QDoubleSpinBox:
        s = QDoubleSpinBox()
        s.setDecimals(2)
        s.setRange(-1000.0, 10000.0)
        return s

    def _ids(self) -> list[int]:
        return [p["id"] for p in reversed(self.mf.pisos_ordenados())]

    # -- contenido --------------------------------------------------------------------
    def _llenar(self) -> None:
        pisos = list(reversed(self.mf.pisos_ordenados()))
        if self.elegida not in [p["id"] for p in pisos]:
            self.elegida = pisos[0]["id"] if pisos else None
        self.tabla.blockSignals(True)
        self.tabla.setRowCount(len(pisos))
        for k, piso in enumerate(pisos):
            abajo = self.mf.piso_de_abajo(piso["id"])
            entrepiso = "—" if abajo is None else _n(piso["nivel"] - self.mf.nivel(abajo))
            valores = (
                piso["nombre"],
                _nivel(piso["nivel"]),
                entrepiso,
                str(self.mf.elementos_en_piso(piso["id"])),
            )
            for j, v in enumerate(valores):
                item = QTableWidgetItem(v)
                if j:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.tabla.setItem(k, j, item)
            if piso["id"] == self.elegida:
                self.tabla.selectRow(k)
        self.tabla.blockSignals(False)
        self.c_origen.blockSignals(True)
        origen = self.c_origen.currentData()
        self.c_origen.clear()
        for piso in pisos:
            self.c_origen.addItem(
                f"{piso['nombre']} · {_nivel(piso['nivel'])} {self.mf.longitud}", piso["id"]
            )
        k = self.c_origen.findData(origen if origen is not None else self.elegida)
        self.c_origen.setCurrentIndex(max(k, 0))
        self.c_origen.blockSignals(False)
        self._destinos()
        self._planta_elegida()

    def _planta_elegida(self) -> None:
        hay = self.elegida is not None
        for w in (self.e_nombre, self.e_nivel, self.e_entrepiso, self.c_mover, self.b_quitar):
            w.setEnabled(hay)
        if not hay:
            self.e_nombre.clear()
            return
        piso = self.mf.elemento("pisos", self.elegida)
        self.e_nombre.setText(piso["nombre"])
        self.e_nivel.setValue(piso["nivel"])
        abajo = self.mf.piso_de_abajo(self.elegida)
        self.e_entrepiso.setEnabled(abajo is not None)
        self.e_entrepiso.setValue(
            piso["nivel"] - self.mf.nivel(abajo) if abajo is not None else 0.01
        )

    def _destinos(self) -> None:
        while self.caja_destinos.count():
            w = self.caja_destinos.takeAt(0).widget()
            if w is not None:
                w.deleteLater()
        self.c_destinos.clear()
        origen = self.c_origen.currentData()
        otros = [p for p in reversed(self.mf.pisos_ordenados()) if p["id"] != origen]
        for k, piso in enumerate(reversed(otros)):
            b = QCheckBox(piso["nombre"])
            b.toggled.connect(self._boton_copiar)
            self.c_destinos[piso["id"]] = b
            self.caja_destinos.addWidget(b, k // 2, k % 2)
        self._boton_copiar()

    def _boton_copiar(self) -> None:
        n = sum(b.isChecked() for b in self.c_destinos.values())
        hay_que = any(b.isChecked() for b in self.c_que.values())
        self.b_copiar.setText(f"Copiar a {n} planta{'s' if n != 1 else ''}" if n else "Copiar")
        self.b_copiar.setEnabled(bool(n and hay_que))

    def _elegida(self) -> None:
        filas = self.tabla.selectionModel().selectedRows()
        if filas:
            self.elegida = self._ids()[filas[0].row()]
            self._planta_elegida()

    # -- cambios ----------------------------------------------------------------------
    def _probar(self, cambio: Callable[[ModeloFisico], object]) -> object:
        copia = ModeloFisico.desde_json(self.mf.a_json())
        try:
            resultado = cambio(copia)
        except (FormatoError, KeyError, ValueError) as e:
            self.lbl_error.setText(str(e).strip("'\""))
            self.lbl_error.show()
            self._planta_elegida()
            return None
        self.lbl_error.hide()
        self.mf = copia
        self.cambios += 1
        self._llenar()
        return resultado

    def agregar(self, arriba: bool) -> None:
        pisos = self.mf.pisos_ordenados()
        if not pisos:
            self.elegida = self._probar(lambda m: m.agregar_piso("Planta baja", 0.0)) or None
            self._llenar()
            return
        ref = self.elegida if self.elegida is not None else pisos[-1]["id"]
        nivel_ref = self.mf.nivel(ref)
        abajo = self.mf.piso_de_abajo(ref)
        altura = nivel_ref - self.mf.nivel(abajo) if abajo is not None else 3.0
        orden = [p["id"] for p in pisos]
        k = orden.index(ref)

        def cambio(m: ModeloFisico) -> int:
            nombre = _nombre_libre(m, "pisos", "Piso")
            if arriba:
                # Las plantas de arriba suben una altura de entrepiso para hacer lugar.
                for otro in reversed(orden[k + 1 :]):
                    m.editar("pisos", otro, nivel=m.nivel(otro) + altura)
                return m.agregar_piso(nombre, nivel_ref + altura)
            if k == 0:
                return m.agregar_piso(nombre, nivel_ref - altura)
            # Entre dos plantas: la elegida y las de arriba suben para hacer lugar.
            for otro in reversed(orden[k:]):
                m.editar("pisos", otro, nivel=m.nivel(otro) + altura)
            return m.agregar_piso(nombre, nivel_ref)

        nuevo = self._probar(cambio)
        if nuevo is not None:
            self.elegida = nuevo
            self._llenar()

    def quitar(self) -> None:
        if self.elegida is None:
            return
        n = self.mf.elementos_en_piso(self.elegida) + sum(
            1
            for lista in ("columnas", "muros")
            for el in self.mf.lista(lista)
            if el["desde"] == self.elegida
        )
        if n and not self.confirmar(n):
            return
        self._probar(lambda m: m.quitar_piso(self.elegida))

    def confirmar(self, n: int) -> bool:
        nombre = self.mf.elemento("pisos", self.elegida)["nombre"]
        r = QMessageBox.question(
            self,
            "Quitar planta",
            f"{nombre} tiene {n} elementos que la usan. Se quitan junto con la planta. ¿Seguir?",
        )
        return r == QMessageBox.Yes

    def _nombre(self) -> None:
        texto = self.e_nombre.text().strip()
        if (
            self.elegida is not None
            and texto
            and texto != self.mf.elemento("pisos", self.elegida)["nombre"]
        ):
            self._probar(lambda m: m.editar("pisos", self.elegida, nombre=texto))

    def _nivel(self) -> None:
        if self.elegida is None or self.e_nivel.value() == self.mf.nivel(self.elegida):
            return
        valor, mover = self.e_nivel.value(), self.c_mover.isChecked()
        self._probar(lambda m: m.cambiar_nivel(self.elegida, valor, mover_arriba=mover))

    def _entrepiso(self) -> None:
        if self.elegida is None:
            return
        abajo = self.mf.piso_de_abajo(self.elegida)
        if abajo is None:
            return
        nivel = self.mf.nivel(abajo) + self.e_entrepiso.value()
        if nivel == self.mf.nivel(self.elegida):
            return
        mover = self.c_mover.isChecked()
        self._probar(lambda m: m.cambiar_nivel(self.elegida, nivel, mover_arriba=mover))

    def copiar(self) -> None:
        origen = self.c_origen.currentData()
        destinos = [id for id, b in self.c_destinos.items() if b.isChecked()]
        listas = [lista for lista, b in self.c_que.items() if b.isChecked()]
        n = self._probar(lambda m: m.copiar_piso(origen, destinos, listas))
        if n is not None:
            self.lbl_copia.setText(f"Se copiaron {n} elementos")

    def accept(self) -> None:
        if self.cambios:
            datos = self.mf.a_json()
            self.estado.aplicar(lambda m: m._probar(copy.deepcopy(datos)), "Editar plantas")
        super().accept()
