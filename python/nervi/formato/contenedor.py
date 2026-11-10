# SPDX-License-Identifier: GPL-3.0-or-later
"""Contenedor ZIP de los proyectos ``.nrv`` (``docs/formato-nrv.md`` §2, §3 y §6)."""

from __future__ import annotations

import json
import os
import shutil
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from . import migraciones
from . import modelo as _modelo
from .errores import FormatoError

MIMETYPE = "application/vnd.nervi.proyecto+zip"
VERSION_ESQUEMA = 1
FORMATO = "nervi.proyecto"
MANIFIESTO = "nervi.json"

#: Límites del lector (§2.2).
MAX_BYTES_MIEMBRO = 200 * 1024 * 1024
MAX_MIEMBROS = 10_000

_PROPIOS = ("mimetype", MANIFIESTO, _modelo.MIEMBRO)


def _version_programa() -> str:
    try:
        from importlib.metadata import version

        return version("nervi")
    except Exception:
        return "desconocida"


def _ahora() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass
class Documento:
    """Un proyecto de Nervi en memoria.

    ``modelo`` es el diccionario de ``modelo.json``; ``otros`` guarda, sin
    interpretarlos, los miembros del ZIP que este programa no conoce
    (``vista.json``, ``adjuntos/…``) para escribirlos igual al guardar.
    ``migrado_desde`` indica la versión de esquema original si al abrir hubo
    que migrar el archivo."""

    modelo: dict
    manifiesto: dict = field(default_factory=dict)
    otros: dict[str, bytes] = field(default_factory=dict)
    migrado_desde: int | None = None

    @classmethod
    def nuevo(cls) -> Documento:
        return cls(_modelo.nuevo(), {"formato": FORMATO, "version_esquema": VERSION_ESQUEMA})

    @classmethod
    def desde_modelo(cls, m, combinaciones: dict[str, dict[str, float]] | None = None):
        doc = cls.nuevo()
        doc.modelo = _modelo.desde_modelo(m, combinaciones)
        return doc


def _nombre_seguro(nombre: str) -> bool:
    p = PurePosixPath(nombre)
    return (
        bool(nombre)
        and "\\" not in nombre
        and not p.is_absolute()
        and ".." not in p.parts
        and not (len(nombre) > 1 and nombre[1] == ":")
    )


def _leer_json(zf: zipfile.ZipFile, nombre: str) -> dict:
    try:
        datos = zf.read(nombre)
    except KeyError:
        raise FormatoError("falta este miembro obligatorio", nombre) from None
    try:
        valor = json.loads(datos.decode("utf-8"), parse_constant=_rechazar_constante)
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise FormatoError(f"JSON inválido ({e})", nombre) from None
    if not isinstance(valor, dict):
        raise FormatoError("tiene que ser un objeto JSON", nombre)
    return valor


def _rechazar_constante(nombre: str):
    raise json.JSONDecodeError(f"{nombre} no está permitido", nombre, 0)


def abrir(ruta: str | os.PathLike) -> Documento:
    """Abre un ``.nrv``, aplica las migraciones necesarias y valida el modelo."""
    try:
        zf = zipfile.ZipFile(ruta)
    except zipfile.BadZipFile:
        raise FormatoError("no es un proyecto de Nervi (no es un archivo ZIP)") from None
    with zf:
        infos = zf.infolist()
        if not infos or infos[0].filename != "mimetype":
            raise FormatoError("no es un proyecto de Nervi (falta 'mimetype' al comienzo)")
        if infos[0].compress_type != zipfile.ZIP_STORED:
            raise FormatoError("tiene que estar sin comprimir", "mimetype")
        if zf.read("mimetype") != MIMETYPE.encode("ascii"):
            raise FormatoError(f"no es un proyecto de Nervi (se esperaba {MIMETYPE})", "mimetype")
        if len(infos) > MAX_MIEMBROS:
            raise FormatoError(f"tiene más de {MAX_MIEMBROS} miembros")
        for info in infos:
            if not _nombre_seguro(info.filename):
                raise FormatoError("nombre de miembro no permitido", info.filename)
            if info.file_size > MAX_BYTES_MIEMBRO:
                raise FormatoError("supera los 200 MB descomprimidos", info.filename)

        manifiesto = _leer_json(zf, MANIFIESTO)
        if manifiesto.get("formato") != FORMATO:
            raise FormatoError(f"'formato' tiene que ser {FORMATO!r}", MANIFIESTO, "formato")
        version = manifiesto.get("version_esquema")
        if not isinstance(version, int) or isinstance(version, bool) or version < 1:
            raise FormatoError("tiene que ser un entero ≥ 1", MANIFIESTO, "version_esquema")
        if version > VERSION_ESQUEMA:
            raise FormatoError(
                f"Este archivo es del formato {version}; esta versión de Nervi lee hasta el "
                f"{VERSION_ESQUEMA}. Actualizá Nervi."
            )
        modelo = _leer_json(zf, _modelo.MIEMBRO)
        migrado = None
        if version < VERSION_ESQUEMA:
            manifiesto, modelo = migraciones.migrar(manifiesto, modelo, VERSION_ESQUEMA)
            migrado = version
        _modelo.validar(modelo)
        otros = {
            i.filename: zf.read(i.filename)
            for i in infos
            if i.filename not in _PROPIOS and not i.is_dir()
        }
    return Documento(modelo, manifiesto, otros, migrado)


def guardar(doc: Documento, ruta: str | os.PathLike, copia_bak: bool = False) -> None:
    """Guarda el documento con escritura segura: ``.tmp``, ``fsync`` y ``os.replace``.

    Con ``copia_bak=True`` deja el archivo anterior como ``<ruta>.bak``."""
    _modelo.validar(doc.modelo)
    ruta = Path(ruta)
    ahora = _ahora()
    manifiesto = {k: v for k, v in doc.manifiesto.items()}
    manifiesto.update(
        formato=FORMATO,
        version_esquema=VERSION_ESQUEMA,
        generador={"nombre": "Nervi", "version": _version_programa()},
        modificado=ahora,
    )
    manifiesto.setdefault("creado", ahora)

    tmp = ruta.with_name(ruta.name + ".tmp")
    with open(tmp, "wb") as f:
        with zipfile.ZipFile(f, "w") as zf:
            info = zipfile.ZipInfo("mimetype", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            zf.writestr(info, MIMETYPE.encode("ascii"))
            for nombre, valor in ((MANIFIESTO, manifiesto), (_modelo.MIEMBRO, doc.modelo)):
                texto = json.dumps(valor, ensure_ascii=False, indent=2, allow_nan=False)
                zf.writestr(nombre, (texto + "\n").encode("utf-8"), zipfile.ZIP_DEFLATED)
            for nombre, datos in doc.otros.items():
                zf.writestr(nombre, datos, zipfile.ZIP_DEFLATED)
        f.flush()
        os.fsync(f.fileno())
    if copia_bak and ruta.exists():
        shutil.copy2(ruta, ruta.with_name(ruta.name + ".bak"))
    os.replace(tmp, ruta)
    doc.manifiesto = manifiesto
