# SPDX-License-Identifier: GPL-3.0-or-later
"""Módulo ``diseno`` del formato ``.nrv`` (``diseno.json``, versión 2).

Guarda los datos que el usuario elige para diseñar: norma, materiales, criterios
y, por barra, el tipo de elemento y la sección de hormigón. **No** guarda
resultados: se recalculan desde el modelo (``docs/formato-nrv.md`` §4b).

Unidades fijas, independientes de las del modelo: MPa para tensiones y mm para
medidas de la sección.

La versión 2 agrega ``criterios.diametros_columna``: los diámetros entre los que
el programa busca la armadura de las columnas (por omisión, todos).

>>> d = nuevo()
>>> d["norma"], d["hormigon"]["fc"], d["acero"]["fy"]
('ACI 318-19', 25.0, 420.0)
>>> validar(d)
"""

from __future__ import annotations

import copy
import hashlib
import math

from .errores import FormatoError

MIEMBRO = "diseno.json"
NORMAS = ("ACI 318-19",)
#: Tipos de elemento: ``auto`` decide por la orientación de la barra.
TIPOS = ("auto", "viga", "columna", "ninguno")
DIAMETROS_ESTRIBO = (6, 8, 10, 12)
#: Diámetros de barra para columnas, en mm. Los mismos que
#: ``nervi.design.aci318.columna.DIAMETROS_COLUMNA``.
DIAMETROS_COLUMNA = (12, 16, 20, 25, 32)

_DEFECTO = {
    "norma": "ACI 318-19",
    "hormigon": {"fc": 25.0},
    "acero": {"fy": 420.0, "fyt": 420.0},
    "criterios": {
        "recubrimiento": 40.0,
        "d_estribo": 10.0,
        "d_agregado": 19.0,
        "seccion_critica_a_d": True,
        "diametros_columna": list(DIAMETROS_COLUMNA),
    },
    "elementos": [],
}


def nuevo() -> dict:
    """Datos de diseño por defecto: H-25 (``f'c`` = 25 MPa) y acero de 420 MPa."""
    return copy.deepcopy(_DEFECTO)


def huella(datos: bytes) -> str:
    """SHA-256 de los bytes de ``modelo.json`` (``docs/formato-nrv.md`` §3.1)."""
    return hashlib.sha256(datos).hexdigest()


def _err(motivo: str, ruta: str) -> FormatoError:
    return FormatoError(motivo, MIEMBRO, ruta)


def _numero(v, ruta: str, minimo: float = 0.0, estricto: bool = True) -> None:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise _err("tiene que ser un número", ruta)
    if v < minimo or (estricto and v == minimo):
        raise _err(f"= {v}: tiene que ser {'>' if estricto else '≥'} {minimo:g}", ruta)


def _objeto(d, ruta: str, claves: dict[str, bool]) -> dict:
    """Valida que ``d`` sea un objeto con esas claves (``True``: obligatoria)."""
    if not isinstance(d, dict):
        raise _err("tiene que ser un objeto", ruta)
    for clave in d:
        if clave not in claves:
            raise _err("clave desconocida", f"{ruta}.{clave}" if ruta else clave)
    for clave, obligatoria in claves.items():
        if obligatoria and clave not in d:
            raise _err("falta esta clave", f"{ruta}.{clave}" if ruta else clave)
    return d


def validar(d: dict) -> None:
    """Valida ``diseno.json``. Lanza :class:`FormatoError` con la ruta del error.

    Las barras de ``elementos`` no se comparan con el modelo: si una ya no existe,
    quien diseña la ignora (el modelo puede cambiar después de guardar el diseño).
    """
    _objeto(
        d,
        "",
        {
            "norma": True,
            "modelo_sha256": False,
            "hormigon": True,
            "acero": True,
            "criterios": True,
            "elementos": True,
            "extensiones": False,
        },
    )
    if d["norma"] not in NORMAS:
        raise _err(f"= {d['norma']!r}: normas válidas {NORMAS}", "norma")
    sha = d.get("modelo_sha256")
    if sha is not None and (
        not isinstance(sha, str) or len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha)
    ):
        raise _err("tiene que ser un SHA-256 en hexadecimal", "modelo_sha256")
    _objeto(d["hormigon"], "hormigon", {"fc": True})
    _numero(d["hormigon"]["fc"], "hormigon.fc")
    _objeto(d["acero"], "acero", {"fy": True, "fyt": False})
    _numero(d["acero"]["fy"], "acero.fy")
    if "fyt" in d["acero"]:
        _numero(d["acero"]["fyt"], "acero.fyt")
    c = _objeto(
        d["criterios"],
        "criterios",
        {
            "recubrimiento": True,
            "d_estribo": True,
            "d_agregado": True,
            "seccion_critica_a_d": True,
            "diametros_columna": True,
        },
    )
    _numero(c["recubrimiento"], "criterios.recubrimiento", estricto=False)
    _numero(c["d_estribo"], "criterios.d_estribo")
    if c["d_estribo"] not in DIAMETROS_ESTRIBO:
        raise _err(
            f"= {c['d_estribo']}: diámetros válidos {DIAMETROS_ESTRIBO}", "criterios.d_estribo"
        )
    _numero(c["d_agregado"], "criterios.d_agregado")
    if not isinstance(c["seccion_critica_a_d"], bool):
        raise _err("tiene que ser true o false", "criterios.seccion_critica_a_d")
    diametros = c["diametros_columna"]
    ruta_d = "criterios.diametros_columna"
    if not isinstance(diametros, list) or not diametros:
        raise _err("tiene que ser una lista con al menos un diámetro", ruta_d)
    for k, d_b in enumerate(diametros):
        if isinstance(d_b, bool) or d_b not in DIAMETROS_COLUMNA:
            raise _err(f"= {d_b!r}: diámetros válidos {DIAMETROS_COLUMNA}", f"{ruta_d}[{k}]")
    if len(set(diametros)) != len(diametros):
        raise _err("tiene diámetros repetidos", ruta_d)
    if not isinstance(d["elementos"], list):
        raise _err("tiene que ser una lista", "elementos")
    vistas = set()
    for k, e in enumerate(d["elementos"]):
        ruta = f"elementos[{k}]"
        _objeto(e, ruta, {"barra": True, "tipo": False, "b": False, "h": False})
        b = e["barra"]
        if isinstance(b, bool) or not isinstance(b, int) or b < 1:
            raise _err("tiene que ser un id de barra (entero ≥ 1)", f"{ruta}.barra")
        if b in vistas:
            raise _err(f"la barra {b} aparece dos veces", f"{ruta}.barra")
        vistas.add(b)
        if "tipo" in e and e["tipo"] not in TIPOS:
            raise _err(f"= {e['tipo']!r}: tipos válidos {TIPOS}", f"{ruta}.tipo")
        for clave in ("b", "h"):
            if clave in e:
                _numero(e[clave], f"{ruta}.{clave}")
    if "extensiones" in d and not isinstance(d["extensiones"], dict):
        raise _err("tiene que ser un objeto", "extensiones")
