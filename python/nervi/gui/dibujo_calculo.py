# SPDX-License-Identifier: GPL-3.0-or-later
"""Dibujo con el mouse del modelo de cálculo en la vista 2D (#31).

Herramientas: *Nudo*, *Barra*, *Apoyo*, *Puntual* y *Repartida*, con el mismo
enganche, Orto (F8) y entrada de largo y ángulo que la planta del edificio
(:class:`nervi.gui.dibujo.Dibujo`). Las ediciones son de :mod:`nervi.edicion`:

- **Nudo**: un clic. Si cae sobre una barra, la parte.
- **Barra**: tramos encadenados. Usa los nudos que hay o los crea, y se parte en cada
  nudo por el que pasa.
- **Apoyo**: clic en un nudo (o en una barra, que se parte) pone el apoyo elegido; otro
  clic con el mismo tipo lo saca.
- **Puntual**: en un nudo, una carga nodal; en una barra, una carga puntual a esa
  distancia.
- **Repartida**: clic en una barra, una carga uniforme en todo su largo.

Cada clic es un Ctrl+Z. Mientras se usa una herramienta de cargas se ven las cargas del
caso elegido.
"""

from __future__ import annotations

import copy
import math
from collections import Counter

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QDoubleValidator, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QComboBox, QFormLayout, QLabel, QLineEdit, QVBoxLayout, QWidget

from .. import edicion
from ..enganche import GeometriaPlanta, IndiceEnganche
from ..formato import modelo as formato_modelo
from ..formato.errores import FormatoError
from . import estilo
from .dibujo import Dibujo, OpcionesDibujo

#: Herramientas de la vista 2D, con su ícono del catálogo y su nombre.
HERRAMIENTAS_CALCULO = {
    "seleccionar": ("seleccionar", "Seleccionar"),
    "nudo": ("nudos", "Nudo"),
    "barra": ("barras", "Barra"),
    "apoyo": ("apoyos", "Apoyo"),
    "puntual": ("carga_puntual", "Puntual"),
    "repartida": ("carga_repartida", "Repartida"),
}
#: Enganches de la vista 2D (``extremos`` engancha a los nudos).
ENGANCHES_CALCULO = {
    "grilla": "Grilla",
    "extremos": "Nudos",
    "medio": "Medio",
    "cruces": "Cruces",
    "orto": "Orto F8",
}
#: Herramientas de cargas: con ellas se ven las cargas del caso elegido.
CARGAS = ("puntual", "repartida")


class DibujoCalculo(Dibujo):
    """Herramientas de dibujo de la vista 2D. La vista le pasa el mouse, el teclado y
    el pintor; esta clase edita el modelo de la sesión."""

    HERRAMIENTAS = HERRAMIENTAS_CALCULO
    #: Un cambio no se pudo hacer: el motivo, para la barra de estado.
    mensaje = Signal(str)

    def __init__(self, vista, sesion) -> None:
        super().__init__(vista, OpcionesDibujo.leer("dibujo_calculo", ENGANCHES_CALCULO))
        self.vista = vista
        self.sesion = sesion
        #: ``E``, ``A`` e ``I`` de las barras nuevas (``None``: las más usadas).
        self.propiedades: dict[str, float] | None = None
        self.apoyo = "empotrado"
        self.caso = "D"
        #: Valores de la carga: nodal o puntual (fx, fy, mz) y repartida (qx, qy).
        self.carga = {"fx": 0.0, "fy": -10.0, "mz": 0.0, "qx": 0.0, "qy": -10.0}
        self.ejes = "global"
        sesion.modelo_cambiado.connect(self._invalidar)

    # -- lo que pide Dibujo ----------------------------------------------------------
    def _al_elegir(self, herramienta: str) -> None:
        if herramienta != "seleccionar":
            self.sesion.seleccionar(None)

    def _armar_geometria(self) -> GeometriaPlanta:
        m = self.sesion.modelo
        xy = {n["id"]: (n["x"], n["y"]) for n in m["nudos"]}
        barras = [b for b in m["barras"] if b["i"] in xy and b["j"] in xy]
        indice = IndiceEnganche(list(xy.values()), [(xy[b["i"]], xy[b["j"]]) for b in barras])
        return GeometriaPlanta(
            indice, [("nudos", k) for k in xy], [("barras", b["id"]) for b in barras]
        )

    def _unidad(self) -> str:
        return self.sesion.modelo["unidades"]["longitud"]

    def _nombre_origen(self, lista: str, id: int) -> str:
        return ("N" if lista == "nudos" else "B") + str(id)

    # -- ediciones -------------------------------------------------------------------
    def aplicar(self, cambio, descripcion: str) -> bool:
        """Aplica ``cambio`` (que edita un ``dict``) a una copia del modelo y, si queda
        válido, lo guarda en la sesión (un Ctrl+Z). Si no, emite :attr:`mensaje`."""
        m = copy.deepcopy(self.sesion.modelo)
        try:
            cambio(m)
            formato_modelo.validar(m)
        except (FormatoError, KeyError, ValueError) as e:
            self.mensaje.emit(str(e).strip("'\""))
            return False
        self.sesion.editar(m, descripcion=descripcion)
        return True

    def propiedades_barra(self) -> dict[str, float]:
        """Las de :attr:`propiedades`, o las más usadas, o las de una barra de 30 x 30."""
        if self.propiedades is not None:
            return dict(self.propiedades)
        m = self.sesion.modelo
        usadas = Counter((b["E"], b["A"], b["I"]) for b in m["barras"])
        if usadas:
            e, a, i = usadas.most_common(1)[0][0]
            return {"E": e, "A": a, "I": i}
        return edicion.propiedades_por_omision(m["unidades"])

    def _tol(self) -> float:
        return edicion.tolerancia(self.sesion.modelo["unidades"])

    def fijar(self, p) -> None:
        h = self.herramienta
        if h == "nudo":
            if edicion.nudo_en(self.sesion.modelo, p) is not None:
                self.mensaje.emit("Ya hay un nudo ahí")
            else:
                self.aplicar(lambda m: edicion.agregar_nudo(m, p), "Dibujar nudo")
        elif h == "barra":
            if not self.puntos:
                self.puntos.append(p)
            elif math.dist(p, self.puntos[-1]) > self._tol():
                a, props = self.puntos[-1], self.propiedades_barra()
                if self.aplicar(lambda m: edicion.agregar_barra(m, a, p, props), "Dibujar barra"):
                    self.puntos = [p]
        elif h == "apoyo":
            self._poner_apoyo(p)
        elif h == "puntual":
            self._carga_puntual(p)
        elif h == "repartida":
            self._carga_repartida(p)
        self.lienzo.update()

    def _poner_apoyo(self, p) -> None:
        tipo = self.apoyo

        def cambio(m: dict) -> None:
            n = edicion.agregar_nudo(m, p)
            hay = next((a for a in m.get("apoyos", []) if a["nudo"] == n), None)
            edicion.poner_apoyo(m, n, None if edicion.tipo_apoyo(hay) == tipo else tipo)

        self.aplicar(cambio, "Poner apoyo")

    def _barra_en(self, p) -> tuple[int, float] | None:
        """La barra sobre la que está ``p`` y la distancia desde su nudo ``i``."""
        m = self.sesion.modelo
        xy = {n["id"]: (n["x"], n["y"]) for n in m["nudos"]}
        t = self.lienzo.transformacion()
        tol = max(self._tol(), 0.5 / t.escala if t else 0.0)
        mejor = None
        for b in m["barras"]:
            a, c = xy[b["i"]], xy[b["j"]]
            dx, dy = c[0] - a[0], c[1] - a[1]
            largo = math.hypot(dx, dy)
            if largo == 0:
                continue
            s = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / largo
            if not -tol <= s <= largo + tol:
                continue
            d = abs((p[0] - a[0]) * dy - (p[1] - a[1]) * dx) / largo
            if d <= tol and (mejor is None or d < mejor[0]):
                mejor = (d, b["id"], min(max(s, 0.0), largo))
        return None if mejor is None else mejor[1:]

    def _carga_puntual(self, p) -> None:
        c, caso = self.carga, self.caso
        nudo = edicion.nudo_en(self.sesion.modelo, p)
        if nudo is not None:
            self.aplicar(
                lambda m: edicion.agregar_carga_nodal(
                    m, edicion.caso(m, caso), nudo, c["fx"], c["fy"], c["mz"]
                ),
                f"Carga en el nudo N{nudo}",
            )
            return
        en = self._barra_en(p)
        if en is None:
            self.mensaje.emit("Clic en un nudo o en una barra")
            return
        barra, a = en
        carga = {"tipo": "puntual", "ejes": self.ejes, "a": a, "px": c["fx"], "py": c["fy"]}
        self.aplicar(
            lambda m: edicion.agregar_carga_barra(m, edicion.caso(m, caso), barra, carga),
            f"Carga puntual en la barra B{barra}",
        )

    def _carga_repartida(self, p) -> None:
        en = self._barra_en(p)
        if en is None:
            self.mensaje.emit("Clic en una barra")
            return
        barra, caso = en[0], self.caso
        carga = {"tipo": "uniforme", "ejes": self.ejes, "qx": self.carga["qx"]}
        carga["qy"] = self.carga["qy"]
        self.aplicar(
            lambda m: edicion.agregar_carga_barra(m, edicion.caso(m, caso), barra, carga),
            f"Carga repartida en la barra B{barra}",
        )

    def borrar(self, sel) -> bool:
        """Quita el nudo o la barra elegida (con lo que depende de ellos)."""
        if sel is None or sel.tipo not in ("nudo", "barra"):
            return False
        quitar = edicion.quitar_nudo if sel.tipo == "nudo" else edicion.quitar_barra
        letra = "N" if sel.tipo == "nudo" else "B"
        ok = self.aplicar(lambda m: quitar(m, sel.id), f"Borrar {letra}{sel.id}")
        if ok:
            self.sesion.seleccionar(None)
        return ok

    # -- dibujo ----------------------------------------------------------------------
    def _pintar_debajo(self, p: QPainter, t) -> None:
        if self.herramienta in CARGAS:
            pintar_cargas(p, t, self.sesion.modelo, self.caso)


def pintar_cargas(p: QPainter, t, m: dict, nombre_caso: str) -> None:
    """Flechas de las cargas del caso ``nombre_caso``: nodales, puntuales y uniformes,
    a tamaño fijo en pantalla (no a escala)."""
    caso = next((c["id"] for c in m.get("casos", []) if c["nombre"] == nombre_caso), None)
    if caso is None:
        return
    color = QColor(estilo.ACENTO)
    p.save()
    p.setPen(QPen(color, 1.4))
    p.setBrush(Qt.NoBrush)
    xy = {n["id"]: t.a_pantalla(n["x"], n["y"]) for n in m["nudos"]}
    for c in m.get("cargas_nodales", []):
        if c["caso"] == caso and c["nudo"] in xy:
            _flecha_fuerza(p, xy[c["nudo"]], c.get("fx", 0.0), c.get("fy", 0.0))
            if c.get("mz"):
                _momento(p, xy[c["nudo"]], c["mz"])
    barras = {b["id"]: b for b in m["barras"]}
    for c in m.get("cargas_barra", []):
        b = barras.get(c["barra"])
        if c["caso"] != caso or b is None:
            continue
        pi, pj = xy[b["i"]], xy[b["j"]]
        d = pj - pi
        largo_p = math.hypot(d.x(), d.y())
        if largo_p == 0:
            continue
        ex = d / largo_p

        def a_global(vx: float, vy: float, ex=ex, local=c["ejes"] == "local") -> tuple:
            # Dirección de la barra en el modelo (en pantalla y va hacia abajo); el eje
            # local y es la dirección girada 90° antihorario.
            if not local:
                return vx, vy
            ux, uy = ex.x(), -ex.y()
            return vx * ux - vy * uy, vx * uy + vy * ux

        if c["tipo"] == "puntual":
            largo = _largo_modelo(m, b)
            fx, fy = a_global(c.get("px", 0.0), c.get("py", 0.0))
            _flecha_fuerza(p, pi + d * (c["a"] / largo), fx, fy)
        elif c["tipo"] == "uniforme":
            qx, qy = a_global(c.get("qx", 0.0), c.get("qy", 0.0))
            n = max(2, min(12, int(largo_p / 28)))
            for k in range(n + 1):
                _flecha_fuerza(p, pi + d * (k / n), qx, qy, 26.0)
            q = math.hypot(qx, qy)
            if q:
                off = QPointF(qx / q, -qy / q) * -26.0
                p.drawLine(pi + off, pj + off)
    p.restore()


def _largo_modelo(m: dict, b: dict) -> float:
    xy = {n["id"]: (n["x"], n["y"]) for n in m["nudos"]}
    return max(math.dist(xy[b["i"]], xy[b["j"]]), 1e-12)


def _flecha_fuerza(p: QPainter, q: QPointF, fx: float, fy: float, largo: float = 44.0) -> None:
    """Flecha que llega a ``q`` en la dirección de la fuerza ``(fx, fy)`` del modelo. Las
    concentradas (las largas) van con trazo más grueso que las de una repartida."""
    f = math.hypot(fx, fy)
    if f == 0:
        return
    p.setPen(QPen(QColor(estilo.ACENTO), 2.0 if largo > 30 else 1.2))
    u = QPointF(fx / f, -fy / f)  # en pantalla
    cola = q - u * largo
    p.drawLine(cola, q)
    n = QPointF(-u.y(), u.x())
    p.drawPolygon(QPolygonF([q, q - u * 8 + n * 4, q - u * 8 - n * 4]))


def _momento(p: QPainter, q: QPointF, mz: float) -> None:
    r = 16.0
    p.drawArc(int(q.x() - r), int(q.y() - r), int(2 * r), int(2 * r), 30 * 16, 240 * 16)
    # Punta en el extremo del arco, antihoraria si mz > 0.
    ang = math.radians(270 if mz > 0 else 30)
    punta = q + QPointF(r * math.cos(ang), -r * math.sin(ang))
    sentido = 1 if mz > 0 else -1
    t = QPointF(-math.sin(ang), -math.cos(ang)) * sentido
    n = QPointF(-t.y(), t.x())
    p.drawPolygon(QPolygonF([punta + t * 6, punta - n * 4, punta + n * 4]))


TITULOS = {
    "nudo": "NUEVO NUDO",
    "barra": "NUEVA BARRA",
    "apoyo": "APOYO",
    "puntual": "CARGA PUNTUAL",
    "repartida": "CARGA REPARTIDA",
}
AYUDAS = {
    "nudo": "Clic donde va el nudo. Si cae sobre una barra, la parte en dos.",
    "barra": "Clic en cada punto; escribí el largo y Enter para fijarlo. Usa los nudos "
    "que hay o los crea, y se parte en cada nudo por el que pasa. Esc o clic derecho "
    "terminan.",
    "apoyo": "Clic en un nudo. Otro clic con el mismo tipo lo saca.",
    "puntual": "Clic en un nudo (carga nodal) o en una barra (carga puntual a esa "
    "distancia). Se ven las cargas del caso elegido.",
    "repartida": "Clic en una barra: carga uniforme en todo su largo.",
}


class PanelCalculo(QWidget):
    """Opciones de la herramienta de dibujo de la vista 2D, en el lugar de Propiedades."""

    def __init__(self, dibujo: DibujoCalculo) -> None:
        super().__init__(objectName="panel")
        self.dibujo = dibujo
        capa = QVBoxLayout(self)
        capa.setContentsMargins(14, 12, 14, 12)
        capa.setSpacing(8)
        self.lbl_tipo = QLabel(objectName="seccion")
        capa.addWidget(self.lbl_tipo)
        self.form = QFormLayout()
        self.form.setHorizontalSpacing(12)
        self.form.setVerticalSpacing(6)
        capa.addLayout(self.form)
        self.campos: dict[str, QLineEdit] = {}
        for clave in ("E", "A", "I", "fx", "fy", "mz", "qx", "qy"):
            campo = QLineEdit()
            campo.setValidator(QDoubleValidator())
            campo.setAlignment(Qt.AlignRight)
            campo.editingFinished.connect(lambda c=clave: self._editar(c))
            self.campos[clave] = campo
        self.apoyo = QComboBox()
        for clave, (nombre, _) in edicion.APOYOS.items():
            self.apoyo.addItem(nombre, clave)
        self.apoyo.activated.connect(lambda i: setattr(dibujo, "apoyo", self.apoyo.itemData(i)))
        self.caso = QComboBox(editable=True)
        self.caso.setToolTip("Caso de la carga; escribí un nombre para crear uno nuevo")
        self.caso.currentTextChanged.connect(self._elegir_caso)
        self.ejes = QComboBox()
        self.ejes.addItem("Globales", "global")
        self.ejes.addItem("Locales de la barra", "local")
        self.ejes.activated.connect(lambda i: setattr(dibujo, "ejes", self.ejes.itemData(i)))
        self.form.addRow("Tipo", self.apoyo)
        self.form.addRow("Caso", self.caso)
        for clave in ("E", "A", "I", "fx", "fy", "mz", "qx", "qy"):
            self.form.addRow(clave, self.campos[clave])
        self.form.addRow("Ejes", self.ejes)
        self.lbl_ayuda = QLabel(objectName="tenue")
        self.lbl_ayuda.setWordWrap(True)
        capa.addWidget(self.lbl_ayuda)
        capa.addStretch()
        self.setMinimumWidth(240)
        dibujo.cambiado.connect(self.actualizar)
        dibujo.sesion.modelo_cambiado.connect(self.actualizar)
        self.actualizar()

    def _etiquetas(self) -> dict[str, str]:
        u = self.dibujo.sesion.modelo["unidades"]
        f, ln = u["fuerza"], u["longitud"]
        return {
            "E": f"E [{f}/{ln}²]",
            "A": f"A [{ln}²]",
            "I": f"I [{ln}⁴]",
            "fx": f"Fx [{f}]",
            "fy": f"Fy [{f}]",
            "mz": f"Mz [{f}·{ln}]",
            "qx": f"qx [{f}/{ln}]",
            "qy": f"qy [{f}/{ln}]",
        }

    def actualizar(self) -> None:
        d = self.dibujo
        h = d.herramienta
        if h == "seleccionar":
            return
        self.lbl_tipo.setText(TITULOS[h])
        self.lbl_ayuda.setText(AYUDAS[h])
        valores = {**d.propiedades_barra(), **d.carga}
        for clave, texto in self._etiquetas().items():
            campo = self.campos[clave]
            etiqueta = self.form.labelForField(campo)
            if etiqueta is not None:
                etiqueta.setText(texto)
            if not campo.hasFocus():
                campo.setText(f"{valores[clave]:.6g}")
        self.caso.blockSignals(True)
        self.caso.clear()
        nombres = [c["nombre"] for c in d.sesion.modelo.get("casos", [])]
        self.caso.addItems(nombres if d.caso in nombres else [*nombres, d.caso])
        self.caso.setCurrentText(d.caso)
        self.caso.blockSignals(False)
        self.apoyo.setCurrentIndex(max(self.apoyo.findData(d.apoyo), 0))
        self.ejes.setCurrentIndex(max(self.ejes.findData(d.ejes), 0))
        visibles = {
            "barra": ("E", "A", "I"),
            "puntual": ("fx", "fy", "mz"),
            "repartida": ("qx", "qy"),
        }.get(h, ())
        for clave, campo in self.campos.items():
            self.form.setRowVisible(campo, clave in visibles)
        self.form.setRowVisible(self.apoyo, h == "apoyo")
        self.form.setRowVisible(self.caso, h in CARGAS)
        self.form.setRowVisible(self.ejes, h in CARGAS)

    def _editar(self, clave: str) -> None:
        try:
            v = float(self.campos[clave].text().replace(",", "."))
        except ValueError:
            return
        d = self.dibujo
        if clave in ("E", "A", "I"):
            if v <= 0:
                return
            d.propiedades = {**d.propiedades_barra(), clave: v}
        else:
            d.carga[clave] = v

    def _elegir_caso(self, texto: str) -> None:
        texto = texto.strip()
        if texto:
            self.dibujo.caso = texto
            self.dibujo.lienzo.update()
