# SPDX-License-Identifier: GPL-3.0-or-later
"""Panel del asistente de IA, junto a la barra lateral (``docs/diseno-interfaz.md``).

La persona conversa con su IA en su propia app (Claude Desktop u otra con MCP); este
panel no tiene chat. Muestra si la IA está conectada (:class:`CanalVentana`), las
propuestas de cambio pendientes para aplicar o descartar, y las consultas que hizo el
agente, para que se vea qué leyó.
"""

from __future__ import annotations

import copy
import dataclasses
import time

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .canal import CanalVentana
from .sesion import Propuesta, Sesion

URL_AYUDA = "https://github.com/jeronimobareiro/nervi/blob/main/docs/agentes-ia.md"
#: Consultas del agente que se muestran (las más recientes).
MAX_CONSULTAS = 40


def _etiqueta(texto: str, nombre: str | None = None, ajustar: bool = False) -> QLabel:
    lbl = QLabel(texto)
    if nombre:
        lbl.setObjectName(nombre)
    lbl.setWordWrap(ajustar)
    return lbl


def _hace(segundos: float) -> str:
    minutos = int(segundos // 60)
    if minutos < 1:
        return "recién"
    if minutos < 60:
        return f"hace {minutos} min"
    return f"hace {minutos // 60} h"


def _origen(origen: str) -> str:
    """``"ia: Claude Desktop"`` → ``"Claude Desktop"``."""
    return origen.split(":", 1)[1].strip() if ":" in origen else origen


class PanelAsistente(QWidget):
    """Panel del asistente. ``pendientes_cambiadas`` avisa cuántas propuestas hay
    pendientes, para la insignia de la barra lateral."""

    pendientes_cambiadas = Signal(int)

    def __init__(self, sesion: Sesion, canal: CanalVentana, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("panel")
        self.setAttribute(Qt.WA_StyledBackground)
        self.sesion = sesion
        self.canal = canal
        self.consultas: list[tuple[str, str, bool]] = []  # hora, herramienta, ok
        self._vistas: dict[int, float] = {}  # id de propuesta → cuándo llegó
        self.setMinimumWidth(340)

        capa = QVBoxLayout(self)
        capa.setContentsMargins(14, 12, 14, 12)
        capa.setSpacing(8)
        fila = QHBoxLayout()
        titulo = _etiqueta("Asistente de IA", "titulo")
        titulo.setStyleSheet("font-size: 12pt;")
        self.lbl_conexion = _etiqueta("", "conexion")
        fila.addWidget(titulo)
        fila.addStretch()
        fila.addWidget(self.lbl_conexion)
        capa.addLayout(fila)
        self.lbl_explicacion = _etiqueta("", "tenue", True)
        capa.addWidget(self.lbl_explicacion)
        self.b_conectar = QPushButton("Conectar con mi IA", objectName="primario")
        self.b_conectar.clicked.connect(lambda: self._conectar(True))
        capa.addWidget(self.b_conectar, 0, Qt.AlignLeft)

        contenido = QWidget()
        self.capa_contenido = QVBoxLayout(contenido)
        self.capa_contenido.setContentsMargins(0, 0, 0, 0)
        self.capa_contenido.setSpacing(8)
        self.lbl_propuestas = _etiqueta("", "seccion")
        self.capa_propuestas = QVBoxLayout()
        self.capa_propuestas.setSpacing(8)
        self.lbl_deshacer = _etiqueta(
            "Aplicar se puede deshacer con Ctrl+Z y queda anotado en el historial del proyecto.",
            "tenue",
            True,
        )
        self.lbl_consultas = _etiqueta("CONSULTAS DEL AGENTE", "seccion")
        self.capa_consultas = QVBoxLayout()
        self.capa_consultas.setSpacing(4)
        for w in (self.lbl_propuestas,):
            self.capa_contenido.addWidget(w)
        self.capa_contenido.addLayout(self.capa_propuestas)
        self.capa_contenido.addWidget(self.lbl_deshacer)
        self.capa_contenido.addSpacing(6)
        self.capa_contenido.addWidget(self.lbl_consultas)
        self.capa_contenido.addLayout(self.capa_consultas)
        self.capa_contenido.addStretch()
        desplazable = QScrollArea()
        desplazable.setWidget(contenido)
        desplazable.setWidgetResizable(True)
        desplazable.setFrameShape(QFrame.NoFrame)
        desplazable.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        contenido.setObjectName("panel")
        contenido.setAttribute(Qt.WA_StyledBackground)
        capa.addSpacing(6)
        capa.addWidget(desplazable, 1)

        pie = QHBoxLayout()
        self.b_desconectar = QPushButton("Desconectar")
        self.b_desconectar.clicked.connect(lambda: self._conectar(False))
        ayuda = QPushButton("Cómo conectar mi app", objectName="fantasma")
        ayuda.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(URL_AYUDA)))
        pie.addWidget(self.b_desconectar)
        pie.addWidget(ayuda)
        pie.addStretch()
        capa.addLayout(pie)
        capa.addWidget(
            _etiqueta(
                "El agente consulta a Nervi y propone; no calcula ni cambia nada por su "
                "cuenta. Lo que lee viaja a tu proveedor de IA.",
                "tenue",
                True,
            )
        )

        canal.estado_cambiado.connect(lambda _activo: self._actualizar_conexion())
        canal.consulta.connect(self._anotar_consulta)
        sesion.historial_cambiado.connect(self.actualizar_propuestas)
        sesion.archivo_cambiado.connect(self.actualizar_propuestas)
        self._actualizar_conexion()
        self.actualizar_propuestas()
        self._actualizar_consultas()

    # --- Conexión ----------------------------------------------------------------------
    def _conectar(self, conectar: bool) -> None:
        try:
            self.canal.abrir() if conectar else self.canal.cerrar()
        except OSError as e:
            QMessageBox.warning(self, "Conectar con mi IA", str(e))

    def _actualizar_conexion(self) -> None:
        activo = self.canal.activo
        self.lbl_conexion.setText("●  Conectado" if activo else "Sin conectar")
        self.lbl_conexion.setProperty("conectado", activo)
        self.lbl_conexion.style().unpolish(self.lbl_conexion)
        self.lbl_conexion.style().polish(self.lbl_conexion)
        self.lbl_explicacion.setText(
            "Tu app de IA ya puede usar nervi-mcp con este proyecto. Conversá allá; acá "
            "decidís qué se aplica."
            if activo
            else "Conectá tu app de IA (Claude Desktop, Claude Code u otra con MCP) para "
            "que consulte este proyecto y te proponga cambios. No hace falta clave de API."
        )
        self.b_conectar.setVisible(not activo)
        self.b_desconectar.setVisible(activo)

    # --- Propuestas --------------------------------------------------------------------
    def actualizar_propuestas(self) -> None:
        _vaciar(self.capa_propuestas)
        propuestas = list(self.sesion.propuestas)
        ahora = time.monotonic()
        for p in propuestas:
            self._vistas.setdefault(p.id, ahora)
        self._vistas = {k: v for k, v in self._vistas.items() if k in {p.id for p in propuestas}}
        self.lbl_propuestas.setText(f"PROPUESTAS PENDIENTES · {len(propuestas)}")
        if not propuestas:
            self.capa_propuestas.addWidget(
                _etiqueta(
                    "No hay propuestas. Cuando tu IA proponga un cambio, aparece acá para "
                    "que lo apliques o lo descartes.",
                    "tenue",
                    True,
                )
            )
        for p in propuestas:
            self.capa_propuestas.addWidget(self._tarjeta(p, ahora))
        self.lbl_deshacer.setVisible(bool(propuestas))
        self.pendientes_cambiadas.emit(len(propuestas))

    def _tarjeta(self, p: Propuesta, ahora: float) -> QFrame:
        tarjeta = QFrame(objectName="tarjeta")
        tarjeta.setProperty("pendiente", True)
        capa = QVBoxLayout(tarjeta)
        capa.setContentsMargins(12, 10, 12, 10)
        capa.setSpacing(4)
        capa.addWidget(_etiqueta(p.descripcion or "Cambio del modelo", "titulo", True))
        capa.addWidget(
            _etiqueta(f"de {_origen(p.origen)} · {_hace(ahora - self._vistas[p.id])}", "tenue")
        )
        for linea in p.resumen or ["Sin cambios en el modelo"]:
            capa.addWidget(_etiqueta("•  " + linea, ajustar=True))
        botones = QHBoxLayout()
        botones.setSpacing(6)
        aplicar = QPushButton("Aplicar", objectName="primario")
        aplicar.clicked.connect(lambda: self.aplicar(p.id))
        previa = QPushButton("Vista previa")
        previa.clicked.connect(lambda: self.vista_previa(p.id))
        descartar = QPushButton("Descartar", objectName="fantasma")
        descartar.clicked.connect(lambda: self.descartar(p.id))
        for b in (aplicar, previa, descartar):
            botones.addWidget(b)
        botones.addStretch()
        capa.addSpacing(4)
        capa.addLayout(botones)
        return tarjeta

    def aplicar(self, id: int) -> bool:
        """Aplica la propuesta; si el modelo cambió desde entonces, avisa y no aplica."""
        try:
            self.sesion.aplicar(id)
        except (ValueError, KeyError) as e:
            QMessageBox.warning(
                self,
                "No se aplicó la propuesta",
                str(e).strip("'") + " Pedile a tu IA que la rehaga.",
            )
            return False
        return True

    def descartar(self, id: int) -> None:
        """Descarta la propuesta sin cambiar nada."""
        if any(x.id == id for x in self.sesion.propuestas):
            self.sesion.descartar(id)

    def vista_previa(self, id: int) -> QDialog | None:
        """Muestra el modelo propuesto en una ventana aparte, sin aplicarlo."""
        from .vista2d import Vista2D

        p = next((x for x in self.sesion.propuestas if x.id == id), None)
        if p is None:
            return None
        doc = dataclasses.replace(
            copy.deepcopy(self.sesion.doc), modelo=copy.deepcopy(p.modelo), historial=None
        )
        previa = Sesion(doc)
        dialogo = QDialog(self)
        dialogo.setWindowTitle(f"Vista previa · {p.descripcion or 'propuesta'}")
        dialogo.resize(900, 620)
        capa = QVBoxLayout(dialogo)
        capa.addWidget(_etiqueta("; ".join(p.resumen) or "Sin cambios en el modelo", "tenue", True))
        vista = Vista2D(previa, dialogo)
        capa.addWidget(vista, 1)
        botones = QHBoxLayout()
        botones.addStretch()
        cerrar = QPushButton("Cerrar", objectName="fantasma")
        cerrar.clicked.connect(dialogo.reject)
        aplicar = QPushButton("Aplicar", objectName="primario")
        aplicar.clicked.connect(lambda: self.aplicar(id) and dialogo.accept())
        botones.addWidget(cerrar)
        botones.addWidget(aplicar)
        capa.addLayout(botones)
        dialogo._sesion = previa  # que viva lo mismo que el diálogo
        dialogo.setAttribute(Qt.WA_DeleteOnClose)
        dialogo.show()
        return dialogo

    # --- Consultas ---------------------------------------------------------------------
    def _anotar_consulta(self, herramienta: str, ok: bool) -> None:
        self.consultas.append((time.strftime("%H:%M"), herramienta, ok))
        del self.consultas[:-MAX_CONSULTAS]
        self._actualizar_consultas()

    def _actualizar_consultas(self) -> None:
        _vaciar(self.capa_consultas)
        if not self.consultas:
            self.capa_consultas.addWidget(_etiqueta("Todavía no hubo consultas.", "tenue", True))
        for hora, herramienta, ok in reversed(self.consultas[-12:]):
            fila = QHBoxLayout()
            fila.setSpacing(8)
            fila.addWidget(_etiqueta(hora, "tenue"))
            fila.addWidget(_etiqueta(herramienta, "codigo"))
            fila.addStretch()
            marca = _etiqueta("✓" if ok else "✕", "bien" if ok else "mal")
            marca.setToolTip("Respondió" if ok else "No se pudo responder")
            fila.addWidget(marca)
            self.capa_consultas.addLayout(fila)


def _vaciar(capa) -> None:
    while capa.count():
        item = capa.takeAt(0)
        w = item.widget()
        if w is not None:
            w.hide()  # se borra al volver al bucle de eventos
            w.deleteLater()
        elif item.layout() is not None:
            _vaciar(item.layout())
            item.layout().deleteLater()
