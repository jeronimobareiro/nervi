# SPDX-License-Identifier: GPL-3.0-or-later
"""Canal local entre la ventana de Nervi abierta y ``nervi-mcp``.

La persona toca "Conectar con mi IA" en la ventana: Nervi escucha en
``127.0.0.1`` (un puerto libre que elige el sistema) y deja en
:func:`ruta_descubrimiento` un archivo, legible solo por su usuario, con el puerto
y un secreto de un solo uso. ``nervi-mcp`` sin argumentos (lo lanza la app de IA)
lee ese archivo y le pasa cada consulta a la ventana. Al desconectar o cerrar, el
archivo se borra y el secreto deja de valer.

El protocolo es una línea JSON por pedido y una por respuesta::

    → {"version": 1, "secreto": "…", "herramienta": "leer_nudo", "argumentos": {"nudo": "N2"}}
    ← {"ok": true, "resultado": {…}}   o   {"ok": false, "error": "No existe el nudo N9…"}

Este módulo no depende de Qt: la ventana usa :func:`atender` y el puente usa
:func:`consultar`.
"""

from __future__ import annotations

import hmac
import json
import os
import socket
import sys
from pathlib import Path

from .herramientas import ErrorConsulta

VERSION = 1
#: Tamaño máximo de un pedido o una respuesta (un modelo grande ocupa unos MB).
LIMITE = 64 * 1024 * 1024
_HOST = "127.0.0.1"


class SinVentana(ErrorConsulta):
    """Nervi no está abierto o la persona no conectó su IA."""


_SIN_VENTANA = (
    "Nervi no está abierto o no está conectado con la IA. Pedile a la persona que abra "
    "Nervi y toque «Conectar con mi IA»."
)


def ruta_descubrimiento() -> Path:
    """Archivo con el puerto y el secreto del canal. ``NERVI_CANAL`` lo cambia."""
    if os.environ.get("NERVI_CANAL"):
        return Path(os.environ["NERVI_CANAL"])
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / "Nervi"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "nervi"
    return base / "canal.json"


def publicar(puerto: int, secreto: str, proyecto: str = "") -> Path:
    """Escribe el archivo de descubrimiento, legible solo por el usuario."""
    ruta = ruta_descubrimiento()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_suffix(".tmp")
    datos = {
        "version": VERSION,
        "puerto": int(puerto),
        "secreto": secreto,
        "pid": os.getpid(),
        "proyecto": proyecto,
    }
    descriptor = os.open(temporal, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as f:
        json.dump(datos, f)
    os.replace(temporal, ruta)
    return ruta


def retirar(secreto: str) -> None:
    """Borra el archivo de descubrimiento si es el de este canal (otra ventana pudo
    haberlo reemplazado)."""
    ruta = ruta_descubrimiento()
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    if isinstance(datos, dict) and hmac.compare_digest(str(datos.get("secreto", "")), secreto):
        try:
            ruta.unlink()
        except OSError:
            pass


def _linea(datos: dict) -> bytes:
    return json.dumps(datos, ensure_ascii=False, allow_nan=False).encode("utf-8") + b"\n"


def atender(herramientas, secreto: str, linea: bytes) -> tuple[bytes, str | None, bool]:
    """Lado de la ventana: atiende un pedido. Devuelve la línea de respuesta, la
    herramienta pedida (``None`` si el pedido no trae el secreto) y si salió bien."""
    try:
        pedido = json.loads(linea)
    except ValueError:
        return _linea({"ok": False, "error": "pedido que no es JSON"}), None, False
    if not isinstance(pedido, dict) or not hmac.compare_digest(
        str(pedido.get("secreto", "")), secreto
    ):
        return (
            _linea({"ok": False, "error": "secreto incorrecto: volvé a conectar la IA"}),
            None,
            False,
        )
    nombre = str(pedido.get("herramienta"))
    if pedido.get("version") != VERSION:
        error = f"versión de canal no soportada (esta ventana usa la {VERSION})"
        return _linea({"ok": False, "error": error}), nombre, False
    try:
        resultado = herramientas.ejecutar(pedido.get("herramienta"), pedido.get("argumentos"))
        return _linea({"ok": True, "resultado": resultado}), nombre, True
    except ErrorConsulta as e:
        return _linea({"ok": False, "error": str(e)}), nombre, False
    except Exception as e:  # el agente tiene que recibir una respuesta
        error = f"Error interno de Nervi: {type(e).__name__}: {e}"
        return _linea({"ok": False, "error": error}), nombre, False


def responder(herramientas, secreto: str, linea: bytes) -> bytes:
    """Como :func:`atender`, solo la línea de respuesta."""
    return atender(herramientas, secreto, linea)[0]


def consultar(herramienta: str, argumentos: dict | None = None, espera: float = 120.0):
    """Lado del puente: manda la consulta a la ventana abierta y devuelve el
    resultado. Lanza :class:`SinVentana` si no hay ventana conectada y
    :class:`ErrorConsulta` con el motivo si la ventana no pudo responder."""
    try:
        datos = json.loads(ruta_descubrimiento().read_text(encoding="utf-8"))
        puerto, secreto = int(datos["puerto"]), str(datos["secreto"])
    except (OSError, ValueError, KeyError, TypeError):
        raise SinVentana(_SIN_VENTANA) from None
    pedido = {
        "version": VERSION,
        "secreto": secreto,
        "herramienta": herramienta,
        "argumentos": argumentos or {},
    }
    try:
        with socket.create_connection((_HOST, puerto), timeout=espera) as s:
            s.sendall(_linea(pedido))
            recibido = bytearray()
            while not recibido.endswith(b"\n"):
                parte = s.recv(1 << 16)
                if not parte:
                    break
                recibido += parte
                if len(recibido) > LIMITE:
                    raise ErrorConsulta("La respuesta de Nervi es demasiado grande.")
    except OSError:
        raise SinVentana(_SIN_VENTANA) from None
    try:
        respuesta = json.loads(recibido)
    except ValueError:
        raise SinVentana(_SIN_VENTANA) from None
    if not respuesta.get("ok"):
        raise ErrorConsulta(str(respuesta.get("error", "error desconocido")))
    return respuesta.get("resultado")
