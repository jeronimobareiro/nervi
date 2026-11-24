# SPDX-License-Identifier: GPL-3.0-or-later
"""Resultados del proyecto a precisión completa (memoria bruta), en JSON.

La memoria en PDF redondea a 4 cifras para que se lea; este archivo no redondea
nada. Cada número es el ``float64`` que dio el motor y vuelve a leerse igual,
bit a bit (JSON escribe la representación más corta que identifica al número).
Sirve para revisar, comparar versiones, llevar los resultados a otros programas
y como fuente de datos para integraciones (servidor MCP, complementos).

Formato ``nervi-resultados`` versión 1; el detalle está en
``docs/formato-resultados.md``. Se identifican nudos y barras con los ``id`` de
``modelo.json`` (``"N3"``, ``"B2"``), nunca con los índices del motor, y la
``huella_modelo`` dice a qué ``modelo.json`` corresponden.

>>> from nervi.proyecto import Proyecto, documento_ejemplo
>>> from nervi import resultados
>>> datos = resultados.exportar(Proyecto(documento_ejemplo()))
>>> datos["formato"], datos["version"], sorted(datos["combinaciones"])[0]
('nervi-resultados', 1, '1.2D+1.0L+1.0W')
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from .modelo import ResultadoCaso
    from .proyecto import Proyecto

FORMATO = "nervi-resultados"
VERSION = 1
#: Componentes de cada arreglo, en orden.
COMPONENTES = {
    "desplazamientos": ["ux", "uy", "rz"],
    "reacciones": ["Rx", "Ry", "Mz"],
    "fuerzas_extremo": ["N_i", "V_i", "M_i", "N_j", "V_j", "M_j"],
    "diagramas": ["x", "N", "V", "M", "u", "v"],
}


class ResultadosError(ValueError):
    """Archivo de resultados que no es de este formato o de una versión desconocida."""


def huella(modelo: dict) -> str:
    """SHA-256 de ``modelo.json`` en forma canónica (claves ordenadas, sin espacios)."""
    texto = json.dumps(modelo, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _lista(a) -> list:
    """Arreglo de NumPy a listas de ``float`` de Python, sin redondear."""
    return np.asarray(a, dtype=np.float64).tolist()


def _version_programa() -> str:
    try:
        from importlib.metadata import version

        return version("nervi")
    except Exception:
        return "desconocida"


def _contratos() -> dict[str, int]:
    from . import _core

    return {
        "plano": int(_core.VERSION_CONTRATO),
        "espacial": int(_core.VERSION_CONTRATO_3D),
        "dinamica": int(_core.VERSION_CONTRATO_DINAMICA),
        "diseno": int(_core.VERSION_CONTRATO_DISENO),
    }


def _resultado(r: ResultadoCaso, modelo: dict, indices) -> dict:
    apoyados = sorted({a["nudo"] for a in modelo.get("apoyos", [])})
    return {
        "desplazamientos": {
            f"N{n}": _lista(r.desplazamientos[k]) for n, k in indices.nudos.items()
        },
        "reacciones": {f"N{n}": _lista(r.reacciones[indices.nudos[n]]) for n in apoyados},
        "fuerzas_extremo": {
            f"B{b}": _lista(r.fuerzas_extremo[k]) for b, k in indices.barras.items()
        },
        "diagramas": {
            f"B{b}": {c: _lista(v) for c, v in r.diagrama(k).items()}
            for b, k in indices.barras.items()
        },
    }


def _diseno(resultados: list) -> list[dict]:
    salida = []
    for r in resultados:
        e = r.elemento
        salida.append(
            {
                "barra": f"B{e.barra}",
                "tipo": e.tipo,
                "seccion_mm": [e.b, e.h],
                "estado": r.estado,
                "relacion": r.relacion,
                "armadura": dict(r.armadura),
                "verificaciones": [
                    {
                        "nombre": v.nombre,
                        "solicitacion": v.solicitacion,
                        "resistencia": v.resistencia,
                        "relacion": v.relacion,
                        "unidad": v.unidad,
                        "articulo": v.articulo,
                    }
                    for v in r.verificaciones
                ],
                "mensajes": list(r.mensajes),
            }
        )
    return salida


def _dinamica(din, modelo: dict, indices) -> dict:
    modal = din.modal
    return {
        "gravedad": din.gravedad,
        "modos": [
            {
                "modo": k + 1,
                "periodo": float(modal.periodos[k]),
                "frecuencia": float(modal.frecuencias[k]),
                "masa_participante": _lista(modal.masa_participante[k]),
                "factor_participacion": _lista(modal.factores_participacion[k]),
            }
            for k in range(modal.n_modos)
        ],
        "masa_total": _lista(modal.masa_total),
        "espectros": {
            nombre: {"direccion": getattr(r, "direccion", None), **_resultado(r, modelo, indices)}
            for nombre, r in din.espectros.items()
        },
    }


def exportar(proyecto: Proyecto) -> dict:
    """Todos los resultados del proyecto, sin redondear, como diccionario JSON.

    Resuelve el modelo con sus combinaciones (diagramas exactos, los mismos que usa
    la memoria). Suma el diseño y la dinámica solo si están al día: exportar no
    diseña ni analiza por su cuenta, porque eso cambia el proyecto. Lanza lo mismo
    que :meth:`nervi.proyecto.Proyecto.calcular`."""
    if not proyecto.al_dia:
        proyecto.calcular()
    m = proyecto.modelo
    _modelo, res, indices = proyecto._resolver_con_combinaciones()
    datos = {
        "formato": FORMATO,
        "version": VERSION,
        "programa": {"nombre": "Nervi", "version": _version_programa()},
        "contratos": _contratos(),
        "fecha": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "huella_modelo": huella(m),
        "unidades": dict(m["unidades"]),
        "componentes": COMPONENTES,
        "casos": {c: _resultado(res[c], m, indices) for c in res.casos},
        "combinaciones": {
            c: {"factores": res.factores(c), **_resultado(res[c], m, indices)}
            for c in res.combinaciones
        },
    }
    if proyecto.diseno_al_dia and proyecto.resultados_diseno is not None:
        datos["diseno"] = _diseno(proyecto.resultados_diseno)
    if proyecto.dinamica_al_dia and proyecto.resultados_dinamica is not None:
        datos["dinamica"] = _dinamica(proyecto.resultados_dinamica, m, indices)
    return datos


def _sin_no_finitos(valor, ruta: str = "") -> None:
    if isinstance(valor, float) and not math.isfinite(valor):
        raise ValueError(f"valor no finito en {ruta or 'la raíz'}: {valor}")
    if isinstance(valor, dict):
        for k, v in valor.items():
            _sin_no_finitos(v, f"{ruta}.{k}" if ruta else str(k))
    elif isinstance(valor, list):
        for i, v in enumerate(valor):
            _sin_no_finitos(v, f"{ruta}[{i}]")


def guardar(datos: dict, ruta: str | os.PathLike) -> None:
    """Escribe los resultados en JSON (UTF-8). Rechaza valores no finitos, que JSON
    no admite, en vez de escribirlos mal."""
    _sin_no_finitos(datos)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, allow_nan=False, indent=1)
        f.write("\n")


def leer(ruta: str | os.PathLike) -> dict:
    """Lee un archivo de resultados. Lanza :class:`ResultadosError` si no es de este
    formato o si es de una versión más nueva."""
    with open(ruta, encoding="utf-8") as f:
        datos = json.load(f)
    if not isinstance(datos, dict) or datos.get("formato") != FORMATO:
        raise ResultadosError("no es un archivo de resultados de Nervi")
    if not isinstance(datos.get("version"), int) or datos["version"] > VERSION:
        raise ResultadosError(
            f"versión {datos.get('version')!r} de resultados no soportada "
            f"(esta versión de Nervi lee hasta la {VERSION})"
        )
    return datos
