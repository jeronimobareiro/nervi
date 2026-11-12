# SPDX-License-Identifier: GPL-3.0-or-later
"""Contenedor ZIP de los proyectos ``.nrv`` (``docs/formato-nrv.md`` §2, §3 y §6)."""

from __future__ import annotations

import json
import os
import re
import shutil
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from . import migraciones
from . import modelo as _modelo
from .errores import FormatoError

MIMETYPE = "application/vnd.nervi.proyecto+zip"
#: Versión del contenedor (ZIP + manifiesto). Cambia solo si cambia la estructura
#: del contenedor, no cuando un módulo agrega datos (§6).
VERSION_ESQUEMA = 1
FORMATO = "nervi.proyecto"
MANIFIESTO = "nervi.json"

#: Límites del lector (§2.2).
MAX_BYTES_MIEMBRO = 200 * 1024 * 1024
MAX_MIEMBROS = 10_000

_NOMBRE_MODULO = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*$")


@dataclass(frozen=True)
class Modulo:
    """Un módulo que este programa sabe leer y escribir (§3.1)."""

    nombre: str
    version: int
    miembros: tuple[str, ...]
    requerido: bool

    def entrada(self) -> dict:
        return {
            "version": self.version,
            "miembros": list(self.miembros),
            "requerido": self.requerido,
        }


#: Módulos que conoce esta versión de Nervi y la versión que escribe de cada uno.
MODULOS: dict[str, Modulo] = {
    "modelo": Modulo("modelo", 1, (_modelo.MIEMBRO,), requerido=True),
}


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
    (``vista.json``, ``adjuntos/…``, módulos de versiones más nuevas) para
    escribirlos igual al guardar. ``migrado_desde`` dice, por módulo, la versión
    original si al abrir hubo que migrarlo (``{"modelo": 1}``), y ``avisos``
    explica lo que se conservó sin leer."""

    modelo: dict
    manifiesto: dict = field(default_factory=dict)
    otros: dict[str, bytes] = field(default_factory=dict)
    migrado_desde: dict[str, int] | None = None
    avisos: list[str] = field(default_factory=list)

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


def _modulos_del_manifiesto(manifiesto: dict) -> dict[str, dict]:
    """Lee y valida ``modulos`` (§3.1). Un manifiesto sin ``modulos`` es de un
    archivo guardado antes de que existieran: tiene solo el módulo ``modelo``."""
    if "modulos" not in manifiesto:
        return {"modelo": MODULOS["modelo"].entrada() | {"version": 1}}
    modulos = manifiesto["modulos"]
    if not isinstance(modulos, dict):
        raise FormatoError("tiene que ser un objeto", MANIFIESTO, "modulos")
    for nombre, entrada in modulos.items():
        ruta = f"modulos.{nombre}"
        if not _NOMBRE_MODULO.match(nombre):
            raise FormatoError("nombre de módulo no permitido", MANIFIESTO, ruta)
        if not isinstance(entrada, dict):
            raise FormatoError("tiene que ser un objeto", MANIFIESTO, ruta)
        version = entrada.get("version")
        if not isinstance(version, int) or isinstance(version, bool) or version < 1:
            raise FormatoError("tiene que ser un entero ≥ 1", MANIFIESTO, f"{ruta}.version")
        miembros = entrada.get("miembros")
        if (
            not isinstance(miembros, list)
            or not miembros
            or not all(isinstance(m, str) and _nombre_seguro(m) for m in miembros)
        ):
            raise FormatoError(
                "tiene que ser una lista de nombres de miembros", MANIFIESTO, f"{ruta}.miembros"
            )
        if not isinstance(entrada.get("requerido", False), bool):
            raise FormatoError("tiene que ser true o false", MANIFIESTO, f"{ruta}.requerido")
    if "modelo" not in modulos:
        raise FormatoError("falta el módulo obligatorio 'modelo'", MANIFIESTO, "modulos")
    return modulos


def abrir(ruta: str | os.PathLike) -> Documento:
    """Abre un ``.nrv``, aplica las migraciones necesarias y valida el modelo.

    Un módulo que este programa no conoce, o de una versión más nueva, se
    conserva sin leer si no es ``requerido`` (queda un aviso en
    ``Documento.avisos``); si es ``requerido``, el archivo no se abre."""
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
        modulos = _modulos_del_manifiesto(manifiesto)

        avisos: list[str] = []
        migrado: dict[str, int] = {}
        leidos: dict[str, dict] = {}
        for nombre, entrada in modulos.items():
            conocido = MODULOS.get(nombre)
            requerido = entrada.get("requerido", False) or nombre == "modelo"
            v = entrada["version"]
            if conocido is None or v > conocido.version:
                motivo = (
                    f"usa el módulo {nombre!r}, que esta versión de Nervi no conoce"
                    if conocido is None
                    else f"usa el módulo {nombre!r} versión {v}; esta versión de Nervi "
                    f"lee hasta la {conocido.version}"
                )
                if requerido:
                    raise FormatoError(f"Este proyecto {motivo}. Actualizá Nervi.")
                avisos.append(
                    f"El proyecto {motivo}. Se conserva sin cambios al guardar, pero no se "
                    "muestra ni se actualiza."
                )
                continue
            datos = {m: _leer_json(zf, m) for m in entrada["miembros"]}
            if v < conocido.version:
                datos = migraciones.migrar(nombre, datos, v, conocido.version)
                migrado[nombre] = v
            leidos.update(datos)

        modelo = leidos[_modelo.MIEMBRO]
        _modelo.validar(modelo)
        propios = {"mimetype", MANIFIESTO, *leidos}
        otros = {
            i.filename: zf.read(i.filename)
            for i in infos
            if i.filename not in propios and not i.is_dir()
        }
    manifiesto["modulos"] = modulos
    return Documento(modelo, manifiesto, otros, migrado or None, avisos)


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
    # Módulos que no se pudieron leer: se conservan tal cual, igual que sus miembros.
    modulos = {
        nombre: entrada
        for nombre, entrada in manifiesto.get("modulos", {}).items()
        if nombre not in MODULOS or entrada["version"] > MODULOS[nombre].version
    }
    modulos.update({n: m.entrada() for n, m in MODULOS.items() if n not in modulos})
    manifiesto["modulos"] = modulos

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
