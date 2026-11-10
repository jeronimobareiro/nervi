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
from .sesion import Seleccion, Sesion

DIAGRAMAS = {"M": "Momento", "V": "Cortante", "N": "Axil", "D": "Deformada"}
UNIDAD = {"M": "{f}·{l}", "V": "{f}", "N": "{f}"}


def _fmt(v: float) -> str:
    return f"{v:.2f}".replace("-", "−")


class Vista2D(QWidget):
    """Lienzo del pórtico. Clic selecciona; al pasar el cursor sobre una barra
    muestra los esfuerzos en ese punto."""

    diagrama_cambiado = Signal(str)

    def __init__(self, sesion: Sesion, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.sesion = sesion
        self.diagrama = "M"
        self.mostrar_valores = True
        self._cursor: QPointF | None = None
        self.setMouseTracking(True)
        self.setMinimumSize(320, 240)
        self.setAutoFillBackground(False)
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

    def _transformacion(self):
        nudos = self._nudos()
        if not nudos:
            return None
        xs = [p[0] for p in nudos.values()]
        ys = [p[1] for p in nudos.values()]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        ancho, alto = max(x1 - x0, 1e-9), max(y1 - y0, 1e-9)
        tam = max(ancho, alto)
        margen = 90
        w, h = max(self.width() - 2 * margen, 50), max(self.height() - 2 * margen, 50)
        escala = min(w / max(ancho, tam * 0.3), h / max(alto, tam * 0.3))
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
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
            p.setPen(QColor(estilo.TEXTO_3))
            p.drawText(
                self.rect(), Qt.AlignCenter, "Agregá nudos y barras en la tabla de Geometría"
            )
            return
        res = self.sesion.resultado()
        if res is not None:
            self._diagrama(p, res, t)
        self._estructura(p, t)
        if res is not None:
            self._lectura(p, res)
        self._leyenda(p, res)

    def _grilla(self, p: QPainter) -> None:
        p.setPen(QPen(QColor(estilo.HOVER), 1))
        paso = 28
        for x in range(0, self.width(), paso):
            p.drawLine(x, 0, x, self.height())
        for y in range(0, self.height(), paso):
            p.drawLine(0, y, self.width(), y)

    def _estructura(self, p: QPainter, t) -> None:
        a_pantalla, _, _ = t
        sel = self.sesion.seleccion
        for bid, _k, pi, pj in self._barras():
            elegida = sel == Seleccion("barra", bid)
            p.setPen(
                QPen(QColor(estilo.ACENTO if elegida else estilo.ESTRUCTURA), 3 if elegida else 2.5)
            )
            p.drawLine(pi, pj)
        p.setFont(QFont(self.font().family(), 8))
        nudos = self._nudos()
        apoyos = {a["nudo"]: a for a in self.sesion.modelo.get("apoyos", [])}
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

    def _apoyo(self, p: QPainter, q: QPointF, apoyo: dict) -> None:
        p.setPen(QPen(QColor(estilo.TEXTO_2), 1.5))
        if apoyo.get("ux") and apoyo.get("uy") and apoyo.get("rz"):
            p.drawLine(q + QPointF(-20, 0), q + QPointF(20, 0))
            p.setPen(QPen(QColor("#9CA3AF"), 1))
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
                    p.setBrush(QColor(255, 255, 255, 220))
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
        amplif = 0.1 * tam / maximo
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
            p.setPen(QColor("#A7AEBA" if n == 0 else "#FFFFFF"))
            p.drawText(caja.adjusted(10, 6 + 16 * n, -6, 0), Qt.AlignLeft | Qt.AlignTop, texto)
        p.setBrush(Qt.NoBrush)

    def _leyenda(self, p: QPainter, res) -> None:
        u = self._unidades()
        if res is None:
            texto = "Sin resultados: calculá con F5" if self.sesion.modelo["barras"] else ""
        elif self.diagrama == "D":
            texto = "Deformada (amplificada)"
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

    def mouseMoveEvent(self, evento: QMouseEvent) -> None:
        self._cursor = evento.position()
        self.update()

    def leaveEvent(self, _evento) -> None:
        self._cursor = None
        self.update()

    def mousePressEvent(self, evento: QMouseEvent) -> None:
        q = evento.position()
        nudo = self._nudo_cercano(q)
        if nudo is not None:
            self.sesion.seleccionar(Seleccion("nudo", nudo))
            return
        barra = self._barra_cercana(q)
        self.sesion.seleccionar(Seleccion("barra", barra[0]) if barra else None)
