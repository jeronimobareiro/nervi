# SPDX-License-Identifier: GPL-3.0-or-later
"""Vista 2D del pórtico con diagramas N, V, M y deformada.

Convenciones de dibujo (``docs/convenciones.md``): el momento positivo tracciona
la fibra ``-y`` local, así que se dibuja del lado ``-y`` (del lado traccionado);
N y V positivos se dibujan del lado ``+y`` local.
"""

from __future__ import annotations

import math

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QMouseEvent, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QWidget

from . import estilo
from .brujula import Brujula
from .dibujo_calculo import DibujoCalculo
from .navegacion import METROS, Navegable, Vista, dibujar_coordenadas, dibujar_grilla
from .sesion import Seleccion, Sesion

DIAGRAMAS = {"M": "Momento", "V": "Cortante", "N": "Axil", "D": "Deformada"}
UNIDAD = {"M": "{f}·{l}", "V": "{f}", "N": "{f}"}


def _fmt(v: float) -> str:
    return f"{v:.2f}".replace("-", "−")


class Vista2D(Navegable, QWidget):
    """Lienzo del pórtico. Clic selecciona; al pasar el cursor sobre una barra
    muestra los esfuerzos en ese punto. Se navega con la rueda, el botón del medio y
    ``F`` (ver :mod:`nervi.gui.navegacion`) y se dibuja con las herramientas de
    :attr:`dibujo` (:mod:`nervi.gui.dibujo_calculo`)."""

    diagrama_cambiado = Signal(str)
    #: Arrastre con el botón derecho: pasar a la vista 3D y girar desde este punto
    #: del lienzo, alrededor de este punto del modelo (``x``, ``y``).
    giro_pedido = Signal(QPointF, float, float)
    #: El giro sigue (píxeles arrastrados desde el último aviso) o terminó.
    giro_arrastre = Signal(float, float)
    giro_terminado = Signal()
    #: Píxeles que hay que mover con el botón derecho para que sea un giro y no un clic.
    UMBRAL_GIRO = 4

    def __init__(self, sesion: Sesion, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.sesion = sesion
        self.diagrama = "M"
        self.mostrar_valores = True
        #: Factor de la deformada dibujada (la animación de un modo lo hace oscilar).
        self.fase = 1.0
        #: Color de cada barra (id -> color), por ejemplo el estado de su diseño.
        self.colores_barra: dict[int, str] = {}
        self._cursor: QPointF | None = None
        self.setMinimumSize(320, 240)
        self.iniciar_navegacion()
        self.setAutoFillBackground(False)
        self.dibujo = DibujoCalculo(self, sesion)
        #: Botón derecho apretado: (punto inicial, último punto, ya es un giro).
        self._derecho: tuple[QPointF, QPointF, bool] | None = None
        #: Brújula de vistas: la muestra la ventana, que sabe pasar a la vista 3D.
        self.brujula = Brujula(self)
        self.brujula.hide()
        for senal in (
            sesion.modelo_cambiado,
            sesion.resultados_cambiados,
            sesion.seleccion_cambiada,
        ):
            senal.connect(self.update)

    def elegir_diagrama(self, clave: str) -> None:
        if clave in DIAGRAMAS and clave != self.diagrama:
            self.diagrama = clave
            self.diagrama_cambiado.emit(clave)
            self.update()

    # --- Geometría ---------------------------------------------------------------
    def _nudos(self) -> dict[int, tuple[float, float]]:
        return {n["id"]: (n["x"], n["y"]) for n in self.sesion.modelo["nudos"]}

    def _caja(self):
        nudos = self._nudos()
        if not nudos:
            return None
        xs = [p[0] for p in nudos.values()]
        ys = [p[1] for p in nudos.values()]
        return min(xs), max(xs), min(ys), max(ys)

    def ajuste(self) -> Vista | None:
        """Encuadre automático del pórtico."""
        caja = self._caja()
        if caja is None:
            # Modelo vacío: 40 px por metro alrededor de (5, 3) m, para empezar a dibujar.
            m = METROS.get(self.sesion.modelo["unidades"]["longitud"], 1.0)
            return Vista(40.0 * m, 5.0 / m, 3.0 / m)
        x0, x1, y0, y1 = caja
        ancho, alto = max(x1 - x0, 1e-9), max(y1 - y0, 1e-9)
        tam = max(ancho, alto)
        margen = 90
        w, h = max(self.width() - 2 * margen, 50), max(self.height() - 2 * margen, 50)
        escala = min(w / max(ancho, tam * 0.3), h / max(alto, tam * 0.3))
        return Vista(escala, (x0 + x1) / 2, (y0 + y1) / 2)

    def _transformacion(self):
        v = self.vista_actual()
        if v is None:
            return None
        caja = self._caja()
        tam = 1.0 if caja is None else max(caja[1] - caja[0], caja[3] - caja[2], 1e-9)
        escala, cx, cy = v.escala, v.cx, v.cy
        ox, oy = self.width() / 2, self.height() / 2

        def a_pantalla(x: float, y: float) -> QPointF:
            return QPointF(ox + (x - cx) * escala, oy - (y - cy) * escala)

        return a_pantalla, escala, tam

    def _barras(self):
        """(id, índice, p_i, p_j) de cada barra en pantalla."""
        t = self._transformacion()
        if t is None:
            return []
        a_pantalla, _, _ = t
        nudos = self._nudos()
        salida = []
        for k, b in enumerate(self.sesion.modelo["barras"]):
            if b["i"] in nudos and b["j"] in nudos:
                salida.append((b["id"], k, a_pantalla(*nudos[b["i"]]), a_pantalla(*nudos[b["j"]])))
        return salida

    # --- Dibujo ---------------------------------------------------------------------
    def paintEvent(self, _evento) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(estilo.PANEL))
        self._grilla(p)
        t = self._transformacion()
        if t is None:
            return
        if not self.sesion.modelo["nudos"] and not self.dibujo.activo:
            p.setPen(QColor(estilo.TEXTO_3))
            p.drawText(
                self.rect(),
                Qt.AlignCenter,
                "Dibujá nudos, barras, apoyos y cargas con las herramientas de Dibujar,\n"
                "o cargalos en la tabla de Geometría",
            )
        res = self.sesion.resultado()
        if res is not None:
            self._diagrama(p, res, t)
        self._estructura(p, t)
        if res is not None:
            self._lectura(p, res)
        self._leyenda(p, res)
        self.dibujo.pintar(p, self.transformacion())
        v = self.vista_actual()
        dibujar_coordenadas(
            p, self, v, self.centro_lienzo(), self.cursor_lienzo, self._unidades()["l"]
        )

    def _grilla(self, p: QPainter) -> None:
        v = self.vista_actual()
        if v is not None:
            dibujar_grilla(p, QRectF(self.rect()), v, self.centro_lienzo())

    def _estructura(self, p: QPainter, t) -> None:
        a_pantalla, _, _ = t
        sel = self.sesion.seleccion
        for bid, _k, pi, pj in self._barras():
            elegida = sel == Seleccion("barra", bid)
            color = estilo.ACENTO if elegida else self.colores_barra.get(bid, estilo.ESTRUCTURA)
            p.setPen(QPen(QColor(color), 3 if elegida or bid in self.colores_barra else 2.5))
            p.drawLine(pi, pj)
        p.setFont(QFont(self.font().family(), 8))
        nudos = self._nudos()
        apoyos = {a["nudo"]: a for a in self.sesion.modelo.get("apoyos", [])}
        self._inestabilidad(p, a_pantalla, nudos)
        for nid, (x, y) in nudos.items():
            q = a_pantalla(x, y)
            if nid in apoyos:
                self._apoyo(p, q, apoyos[nid])
            elegido = sel == Seleccion("nudo", nid)
            p.setPen(QPen(QColor(estilo.ACENTO if elegido else estilo.ESTRUCTURA), 1.5))
            p.setBrush(QColor(estilo.ACENTO_SUAVE if elegido else estilo.PANEL))
            p.drawRect(QRectF(q.x() - 3.5, q.y() - 3.5, 7, 7))
            p.setPen(QColor(estilo.TEXTO_3))
            p.drawText(q + QPointF(8, -8), f"N{nid}")
        p.setBrush(Qt.NoBrush)

    def _inestabilidad(self, p: QPainter, a_pantalla, nudos: dict) -> None:
        """Marca en rojo los nudos del mecanismo y, con un aro y una etiqueta, el
        nudo y el GDL que se mueven sin rigidez."""
        ines = self.sesion.inestabilidad
        if ines is None:
            return
        color = QColor(estilo.NEGATIVO)
        p.setBrush(Qt.NoBrush)
        for nid in ines.nudos:
            if nid in nudos and nid != ines.nudo:
                q = a_pantalla(*nudos[nid])
                p.setPen(QPen(color, 1.5, Qt.DashLine))
                p.drawEllipse(q, 9.0, 9.0)
        if ines.nudo in nudos:
            q = a_pantalla(*nudos[ines.nudo])
            p.setPen(QPen(color, 2.5))
            p.drawEllipse(q, 13.0, 13.0)
            p.drawText(q + QPointF(16, 18), f"inestable en {ines.gdl}")

    def _apoyo(self, p: QPainter, q: QPointF, apoyo: dict) -> None:
        p.setPen(QPen(QColor(estilo.TEXTO_2), 1.5))
        if apoyo.get("ux") and apoyo.get("uy") and apoyo.get("rz"):
            p.drawLine(q + QPointF(-20, 0), q + QPointF(20, 0))
            p.setPen(QPen(QColor(estilo.TEXTO_3), 1))
            for dx in range(-18, 22, 9):
                p.drawLine(q + QPointF(dx, 0), q + QPointF(dx - 7, 9))
        else:
            tri = QPolygonF([q, q + QPointF(-10, 16), q + QPointF(10, 16)])
            p.drawPolygon(tri)
            if not (apoyo.get("ux") and apoyo.get("uy")):
                p.drawLine(q + QPointF(-14, 21), q + QPointF(14, 21))

    def _diagrama(self, p: QPainter, res, t) -> None:
        _a_pantalla, escala, tam = t
        barras = self._barras()
        if self.diagrama == "D":
            self._deformada(p, res, barras, escala, tam)
            return
        clave = self.diagrama
        maximo = max(
            (float(np.abs(res.diagrama(k)[clave]).max()) for _b, k, _i, _j in barras), default=0.0
        )
        if maximo <= 1e-12:
            return
        largo = 0.16 * tam * escala / maximo
        lado = -1.0 if clave == "M" else 1.0
        fuente = QFont(self.font().family(), 8)
        fuente.setBold(True)
        p.setFont(fuente)
        for _bid, k, pi, pj in barras:
            d = res.diagrama(k)
            ex = (pj - pi) / max(math.hypot((pj - pi).x(), (pj - pi).y()), 1e-9)
            # +y local en pantalla (la pantalla tiene y hacia abajo)
            ey = QPointF(ex.y(), -ex.x())
            longitud = math.hypot((pj - pi).x(), (pj - pi).y())
            xs = d["x"] / max(d["x"][-1], 1e-12) * longitud
            vals = d[clave]
            for signo, color in ((1, estilo.POSITIVO), (-1, estilo.NEGATIVO)):
                parte = np.where(signo * vals > 0, vals, 0.0)
                if not np.any(parte):
                    continue
                poli = QPolygonF([pi])
                for x, v in zip(xs, parte, strict=True):
                    poli.append(pi + ex * x + ey * (lado * v * largo))
                poli.append(pj)
                c = QColor(color)
                p.setPen(QPen(c, 1.25))
                c.setAlpha(28)
                p.setBrush(c)
                p.drawPolygon(poli)
            p.setBrush(Qt.NoBrush)
            if self.mostrar_valores:
                for idx in {int(np.argmax(vals)), int(np.argmin(vals)), 0, len(vals) - 1}:
                    v = float(vals[idx])
                    if abs(v) < 0.005 * maximo:
                        continue
                    punto = pi + ex * xs[idx] + ey * (lado * v * largo)
                    punto += ey * (lado * math.copysign(12, v))
                    texto = _fmt(v)
                    ancho = p.fontMetrics().horizontalAdvance(texto) + 8
                    caja = QRectF(punto.x() - ancho / 2, punto.y() - 8, ancho, 16)
                    p.setPen(Qt.NoPen)
                    fondo = QColor(estilo.PANEL)
                    fondo.setAlpha(220)
                    p.setBrush(fondo)
                    p.drawRoundedRect(caja, 3, 3)
                    p.setBrush(Qt.NoBrush)
                    p.setPen(QColor(estilo.POSITIVO if v > 0 else estilo.NEGATIVO))
                    p.drawText(caja, Qt.AlignCenter, texto)

    def _deformada(self, p: QPainter, res, barras, escala: float, tam: float) -> None:
        maximo = max(
            (
                float(np.hypot(res.diagrama(k)["u"], res.diagrama(k)["v"]).max())
                for _b, k, _i, _j in barras
            ),
            default=0.0,
        )
        if maximo <= 1e-15:
            return
        amplif = 0.1 * tam / maximo * self.fase
        p.setPen(QPen(QColor(estilo.ACENTO), 1.75, Qt.DashLine))
        for _bid, k, pi, pj in barras:
            d = res.diagrama(k)
            ex = (pj - pi) / max(math.hypot((pj - pi).x(), (pj - pi).y()), 1e-9)
            ey = QPointF(ex.y(), -ex.x())
            longitud = math.hypot((pj - pi).x(), (pj - pi).y())
            camino = QPainterPath()
            for n, (x, u, v) in enumerate(
                zip(d["x"] / max(d["x"][-1], 1e-12), d["u"], d["v"], strict=True)
            ):
                q = pi + ex * (x * longitud + u * amplif * escala) + ey * (v * amplif * escala)
                camino.moveTo(q) if n == 0 else camino.lineTo(q)
            p.drawPath(camino)
        self._amplificacion = amplif

    def _lectura(self, p: QPainter, res) -> None:
        """Esfuerzos en el punto de la barra más cercano al cursor."""
        if self._cursor is None or self.diagrama == "D":
            return
        cerca = self._barra_cercana(self._cursor)
        if cerca is None:
            return
        bid, k, pi, pj, s = cerca
        d = res.diagrama(k)
        x = s * float(d["x"][-1])
        valores = {c: float(np.interp(x, d["x"], d[c])) for c in ("M", "V", "N")}
        q = pi + (pj - pi) * s
        p.setPen(QPen(QColor(estilo.TEXTO), 1.25))
        p.setBrush(QColor(estilo.PANEL))
        p.drawEllipse(q, 3.5, 3.5)
        u = self._unidades()
        lineas = [f"B{bid} · x = {x:.2f} {u['l']}"] + [
            f"{c} = {_fmt(valores[c])} {UNIDAD[c].format(**u)}" for c in ("M", "V", "N")
        ]
        caja = QRectF(q.x() + 14, q.y() + 14, 170, 16 * len(lineas) + 12)
        if caja.right() > self.width() - 8:
            caja.moveRight(q.x() - 14)
        if caja.bottom() > self.height() - 8:
            caja.moveBottom(q.y() - 14)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(estilo.TEXTO))
        p.drawRoundedRect(caja, 6, 6)
        p.setFont(QFont(self.font().family(), 8))
        for n, texto in enumerate(lineas):
            p.setPen(QColor(estilo.DESHABILITADO if n == 0 else estilo.PANEL))
            p.drawText(caja.adjusted(10, 6 + 16 * n, -6, 0), Qt.AlignLeft | Qt.AlignTop, texto)
        p.setBrush(Qt.NoBrush)

    def _leyenda(self, p: QPainter, res) -> None:
        u = self._unidades()
        if res is None:
            texto = "Sin resultados: calculá con F5" if self.sesion.modelo["barras"] else ""
        elif self.diagrama == "D":
            texto = f"Deformada (amplificada) · {res.nombre}"
        else:
            texto = (
                f"{DIAGRAMAS[self.diagrama]} [{UNIDAD[self.diagrama].format(**u)}] · {res.nombre}"
            )
        if not texto:
            return
        p.setFont(QFont(self.font().family(), 8))
        ancho = p.fontMetrics().horizontalAdvance(texto) + 20
        caja = QRectF(10, self.height() - 34, ancho, 24)
        p.setPen(QPen(QColor(estilo.BORDE), 1))
        p.setBrush(QColor(estilo.PANEL))
        p.drawRoundedRect(caja, 5, 5)
        p.setPen(QColor(estilo.TEXTO))
        p.drawText(caja, Qt.AlignCenter, texto)

    def _unidades(self) -> dict[str, str]:
        u = self.sesion.modelo["unidades"]
        return {"f": u["fuerza"], "l": u["longitud"]}

    # --- Interacción ---------------------------------------------------------------
    def _barra_cercana(self, q: QPointF, tolerancia: float = 10.0):
        mejor = None
        for bid, k, pi, pj in self._barras():
            d = pj - pi
            largo2 = d.x() ** 2 + d.y() ** 2
            if largo2 == 0:
                continue
            s = max(0.0, min(1.0, ((q - pi).x() * d.x() + (q - pi).y() * d.y()) / largo2))
            r = pi + d * s - q
            dist = math.hypot(r.x(), r.y())
            if dist <= tolerancia and (mejor is None or dist < mejor[0]):
                mejor = (dist, bid, k, pi, pj, s)
        return mejor[1:] if mejor else None

    def _nudo_cercano(self, q: QPointF, tolerancia: float = 9.0) -> int | None:
        t = self._transformacion()
        if t is None:
            return None
        a_pantalla = t[0]
        for nid, (x, y) in self._nudos().items():
            r = a_pantalla(x, y) - q
            if math.hypot(r.x(), r.y()) <= tolerancia:
                return nid
        return None

    def resizeEvent(self, evento) -> None:
        super().resizeEvent(evento)
        self.brujula.acomodar()

    def mouseMoveEvent(self, evento: QMouseEvent) -> None:
        if self._derecho is not None:
            inicio, ultimo, girando = self._derecho
            pos = evento.position()
            if girando:
                d = pos - ultimo
                self.giro_arrastre.emit(d.x(), d.y())
                self._derecho = (inicio, pos, True)
            elif (pos - inicio).manhattanLength() > self.UMBRAL_GIRO:
                t = self.transformacion()
                x, y = t.a_modelo(inicio) if t is not None else (0.0, 0.0)
                self._derecho = (inicio, inicio, True)
                self.giro_pedido.emit(inicio, x, y)
                d = pos - inicio
                self.giro_arrastre.emit(d.x(), d.y())
                self._derecho = (inicio, pos, True)
            return
        if not self.navegacion_mover(evento):
            self.dibujo.mover(evento.position())
        self._cursor = evento.position()
        self.update()

    def leaveEvent(self, evento) -> None:
        self._cursor = None
        self.dibujo.salir()
        super().leaveEvent(evento)

    def mouseReleaseEvent(self, evento: QMouseEvent) -> None:
        if evento.button() == Qt.RightButton and self._derecho is not None:
            girando = self._derecho[2]
            self._derecho = None
            if girando:
                self.giro_terminado.emit()
            elif self.dibujo.activo:
                # Clic derecho sin arrastrar: termina el trazo (como Esc).
                self.dibujo.cancelar()
            return
        if not self.navegacion_soltar(evento) and evento.button() == Qt.LeftButton:
            self.dibujo.soltar(evento.position())

    def mousePressEvent(self, evento: QMouseEvent) -> None:
        if self.navegacion_presionar(evento):
            return
        if evento.button() == Qt.RightButton:
            # Clic: termina el trazo al soltar. Arrastre: gira en la vista 3D.
            self._derecho = (evento.position(), evento.position(), False)
            return
        if evento.button() != Qt.LeftButton:
            return
        self.setFocus()
        if self.dibujo.activo:
            self.dibujo.presionar(evento.position())
            return
        q = evento.position()
        nudo = self._nudo_cercano(q)
        if nudo is not None:
            self.sesion.seleccionar(Seleccion("nudo", nudo))
            return
        barra = self._barra_cercana(q)
        self.sesion.seleccionar(Seleccion("barra", barra[0]) if barra else None)

    def keyPressEvent(self, evento) -> None:
        if self.dibujo.tecla(evento):
            evento.accept()
            return
        if evento.key() == Qt.Key_Delete and self.dibujo.borrar(self.sesion.seleccion):
            evento.accept()
            return
        super().keyPressEvent(evento)
