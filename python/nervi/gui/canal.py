# SPDX-License-Identifier: GPL-3.0-or-later
"""Lado de la ventana del canal local con ``nervi-mcp`` (:mod:`nervi.ia.canal`).

Escucha solo en ``127.0.0.1`` y atiende cada pedido en el hilo de la interfaz, así
las herramientas leen el proyecto sin carreras con la persona que lo edita. Solo
está abierto mientras la persona lo tiene conectado.
"""

from __future__ import annotations

import secrets

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QHostAddress, QTcpServer, QTcpSocket

from ..ia import canal
from ..ia.herramientas import FuenteProyecto, Herramientas


class CanalVentana(QObject):
    """Canal de la ventana. ``consulta`` avisa cada pedido atendido (herramienta y si
    salió bien) y ``estado_cambiado`` cuando se conecta o desconecta."""

    consulta = Signal(str, bool)
    estado_cambiado = Signal(bool)

    def __init__(self, sesion, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.sesion = sesion
        self.herramientas = Herramientas(FuenteProyecto(sesion))
        self._servidor: QTcpServer | None = None
        self._secreto = ""
        self._buffers: dict[QTcpSocket, bytearray] = {}

    @property
    def activo(self) -> bool:
        return self._servidor is not None

    @property
    def puerto(self) -> int:
        return self._servidor.serverPort() if self._servidor else 0

    def abrir(self) -> None:
        """Empieza a escuchar y publica el archivo de descubrimiento."""
        if self.activo:
            return
        servidor = QTcpServer(self)
        if not servidor.listen(QHostAddress(QHostAddress.LocalHost), 0):
            raise OSError(f"No se pudo abrir el canal local: {servidor.errorString()}")
        servidor.newConnection.connect(self._nueva_conexion)
        self._servidor = servidor
        self._secreto = secrets.token_urlsafe(32)
        canal.publicar(servidor.serverPort(), self._secreto, self.sesion.titulo)
        self.estado_cambiado.emit(True)

    def cerrar(self) -> None:
        """Deja de escuchar, corta las conexiones y borra el archivo."""
        if not self.activo:
            return
        canal.retirar(self._secreto)
        for socket in list(self._buffers):
            socket.abort()
        self._buffers.clear()
        self._servidor.close()
        self._servidor.deleteLater()
        self._servidor = None
        self._secreto = ""
        self.estado_cambiado.emit(False)

    def _nueva_conexion(self) -> None:
        while self._servidor and self._servidor.hasPendingConnections():
            socket = self._servidor.nextPendingConnection()
            self._buffers[socket] = bytearray()
            socket.readyRead.connect(lambda s=socket: self._leer(s))
            socket.disconnected.connect(lambda s=socket: self._olvidar(s))

    def _olvidar(self, socket: QTcpSocket) -> None:
        self._buffers.pop(socket, None)
        socket.deleteLater()

    def _leer(self, socket: QTcpSocket) -> None:
        buffer = self._buffers.get(socket)
        if buffer is None:
            return
        buffer += bytes(socket.readAll().data())
        if len(buffer) > canal.LIMITE:
            socket.abort()
            return
        while b"\n" in buffer:
            linea, _, resto = bytes(buffer).partition(b"\n")
            buffer[:] = resto
            respuesta, herramienta, ok = canal.atender(self.herramientas, self._secreto, linea)
            socket.write(respuesta)
            socket.flush()
            if herramienta is not None:
                self.consulta.emit(herramienta, ok)
