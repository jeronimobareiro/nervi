# SPDX-License-Identifier: GPL-3.0-or-later
"""Modelo de pórtico plano y resultados.

Convenciones (ver ``docs/convenciones.md``):

* Ejes globales X horizontal, Y vertical hacia arriba; giros antihorarios positivos.
* 3 GDL por nudo: ``ux, uy, rz``.
* Ejes locales de barra: ``x`` del nudo i al nudo j, ``y`` a 90° antihorario.
* Axil positivo en tracción; momento positivo si tracciona la fibra del lado ``-y`` local.
* Unidades consistentes a elección del usuario (por ejemplo kN y m).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from . import _core

_EJES = {"local": 0, "global": 1}


@dataclass
class _Caso:
    nombre: str
    nodales: dict[int, np.ndarray] = field(default_factory=dict)
    impuestos: dict[int, np.ndarray] = field(default_factory=dict)


class Modelo:
    """Pórtico plano lineal elástico."""

    def __init__(self) -> None:
        self._nudos: list[tuple[float, float]] = []
        self._barras: list[tuple[int, int, float, float, float, tuple[bool, ...]]] = []
        self._restricciones: dict[int, list[bool]] = {}
        self._resortes: dict[int, tuple[float, float, float]] = {}
        self._casos: list[_Caso] = []
        self._cargas_barra: list[tuple[float, ...]] = []

    # --- Geometría -------------------------------------------------------------
    def agregar_nudo(self, x: float, y: float) -> int:
        self._nudos.append((float(x), float(y)))
        return len(self._nudos) - 1

    def agregar_barra(
        self,
        nudo_i: int,
        nudo_j: int,
        E: float,
        A: float,
        I: float,
        articulada_i: bool = False,
        articulada_j: bool = False,
        liberaciones: tuple[bool, bool, bool, bool, bool, bool] | None = None,
    ) -> int:
        """Agrega una barra. ``articulada_i/j`` liberan el momento en ese extremo;
        ``liberaciones`` permite indicar las seis fuerzas de extremo locales
        ``(N_i, V_i, M_i, N_j, V_j, M_j)`` explícitamente."""
        if liberaciones is None:
            liberaciones = (False, False, articulada_i, False, False, articulada_j)
        if len(liberaciones) != 6:
            raise ValueError("'liberaciones' debe tener 6 valores")
        self._barras.append(
            (int(nudo_i), int(nudo_j), float(E), float(A), float(I), tuple(map(bool, liberaciones)))
        )
        return len(self._barras) - 1

    # --- Apoyos ----------------------------------------------------------------
    def apoyar(self, nudo: int, ux: bool = True, uy: bool = True, rz: bool = True) -> None:
        """Restringe GDL del nudo. Por defecto, empotramiento."""
        r = self._restricciones.setdefault(int(nudo), [False, False, False])
        r[0] |= ux
        r[1] |= uy
        r[2] |= rz

    def resorte(self, nudo: int, kx: float = 0.0, ky: float = 0.0, krz: float = 0.0) -> None:
        self._resortes[int(nudo)] = (float(kx), float(ky), float(krz))

    # --- Cargas ----------------------------------------------------------------
    def caso(self, nombre: str) -> int:
        """Crea un caso de carga (o devuelve el existente con ese nombre)."""
        for k, c in enumerate(self._casos):
            if c.nombre == nombre:
                return k
        self._casos.append(_Caso(nombre))
        return len(self._casos) - 1

    def _indice_caso(self, caso: str | int) -> int:
        return self.caso(caso) if isinstance(caso, str) else int(caso)

    def carga_nodal(
        self, caso: str | int, nudo: int, fx: float = 0.0, fy: float = 0.0, mz: float = 0.0
    ) -> None:
        c = self._casos[self._indice_caso(caso)]
        c.nodales.setdefault(int(nudo), np.zeros(3))
        c.nodales[int(nudo)] += (fx, fy, mz)

    def carga_uniforme(
        self, caso: str | int, barra: int, qx: float = 0.0, qy: float = 0.0, ejes: str = "local"
    ) -> None:
        """Carga uniforme en toda la luz. En ejes globales se entiende por unidad
        de longitud de barra (no proyectada)."""
        self._cargas_barra.append((self._indice_caso(caso), barra, 0, _EJES[ejes], 0.0, qx, qy))

    def carga_puntual(
        self,
        caso: str | int,
        barra: int,
        a: float,
        px: float = 0.0,
        py: float = 0.0,
        ejes: str = "local",
    ) -> None:
        """Carga puntual a la distancia ``a`` del nudo i."""
        self._cargas_barra.append((self._indice_caso(caso), barra, 1, _EJES[ejes], a, px, py))

    def desplazamiento_impuesto(
        self, caso: str | int, nudo: int, ux: float = 0.0, uy: float = 0.0, rz: float = 0.0
    ) -> None:
        """Asentamiento de apoyo. Solo actúa en los GDL restringidos del nudo."""
        c = self._casos[self._indice_caso(caso)]
        c.impuestos[int(nudo)] = np.array([ux, uy, rz], dtype=np.float64)

    # --- Análisis --------------------------------------------------------------
    def arreglos(self) -> dict[str, np.ndarray]:
        """Arreglos del contrato de datos v1 (ver ``docs/contrato-datos.md``)."""
        n, m, nc = len(self._nudos), len(self._barras), len(self._casos)
        coords = np.array(self._nudos, dtype=np.float64).reshape(n, 2)
        conect = np.array([b[:2] for b in self._barras], dtype=np.int64).reshape(m, 2)
        props = np.array([b[2:5] for b in self._barras], dtype=np.float64).reshape(m, 3)
        lib = np.array([b[5] for b in self._barras], dtype=np.uint8).reshape(m, 6)
        restr = np.zeros((n, 3), dtype=np.uint8)
        for k, r in self._restricciones.items():
            restr[k] = r
        resortes = np.zeros((n, 3), dtype=np.float64)
        for k, r in self._resortes.items():
            resortes[k] = r
        nodales = np.zeros((nc, n, 3), dtype=np.float64)
        impuestos = np.zeros((nc, n, 3), dtype=np.float64)
        for c, caso in enumerate(self._casos):
            for k, f in caso.nodales.items():
                nodales[c, k] = f
            for k, u in caso.impuestos.items():
                impuestos[c, k] = u
        cargas_barra = np.array(self._cargas_barra, dtype=np.float64).reshape(-1, 7)
        return {
            "coords": coords,
            "conectividad": conect,
            "props": props,
            "liberaciones": lib,
            "restricciones": restr,
            "resortes": resortes,
            "cargas_nodales": nodales,
            "cargas_barra": cargas_barra,
            "despl_impuestos": impuestos,
        }

    def resolver(self, n_estaciones: int = 11) -> Resultados:
        """Resuelve todos los casos de carga. Lanza ``ValueError`` si el modelo es
        inválido y ``MecanismoError`` si la estructura es inestable."""
        if not self._casos:
            raise ValueError("el modelo no tiene casos de carga")
        crudo = _core.resolver_portico_2d(
            _core.VERSION_CONTRATO, **self.arreglos(), n_estaciones=n_estaciones
        )
        return Resultados([c.nombre for c in self._casos], crudo)


class ResultadoCaso:
    """Resultados de un caso de carga o de una combinación."""

    def __init__(
        self,
        nombre: str,
        desplazamientos: np.ndarray,
        reacciones: np.ndarray,
        fuerzas_extremo: np.ndarray,
        diagramas: dict[str, np.ndarray],
    ) -> None:
        self.nombre = nombre
        #: (n_nudos, 3) ``[ux, uy, rz]`` en ejes globales.
        self.desplazamientos = desplazamientos
        #: (n_nudos, 3) ``[Rx, Ry, Mz]`` en ejes globales.
        self.reacciones = reacciones
        #: (n_barras, 6) fuerzas de extremo en ejes locales, actuando sobre la barra.
        self.fuerzas_extremo = fuerzas_extremo
        self._diagramas = diagramas

    def diagrama(self, barra: int) -> dict[str, np.ndarray]:
        """Arreglos ``x, N, V, M, u, v`` de la barra (``u, v`` en ejes locales)."""
        sel = self._diagramas["barra"] == barra
        return {k: v[sel] for k, v in self._diagramas.items() if k != "barra"}

    def __repr__(self) -> str:
        return f"ResultadoCaso({self.nombre!r})"


class Resultados:
    """Resultados de todos los casos de carga."""

    def __init__(self, nombres: list[str], crudo: dict) -> None:
        self.gdl_sin_rigidez: list[tuple[int, str]] = list(crudo["gdl_sin_rigidez"])
        self._casos = {
            nombre: ResultadoCaso(
                nombre,
                crudo["desplazamientos"][c],
                crudo["reacciones"][c],
                crudo["fuerzas_extremo"][c],
                crudo["diagramas"][c],
            )
            for c, nombre in enumerate(nombres)
        }

    @property
    def casos(self) -> list[str]:
        return list(self._casos)

    def __getitem__(self, nombre: str) -> ResultadoCaso:
        return self._casos[nombre]

    def combinar(self, nombre: str, factores: dict[str, float]) -> ResultadoCaso:
        """Combinación lineal de casos, p. ej. ``{"D": 1.2, "L": 1.6}``.

        Válida por superposición (análisis lineal). Desplazamientos, reacciones y
        fuerzas de extremo son exactos. Los diagramas son exactos si todos los
        casos tienen las mismas estaciones; si no (por ejemplo, cargas puntuales
        en posiciones distintas), se interpolan linealmente en la unión de
        estaciones, lo que es aproximado cerca de los saltos.
        """
        if not factores:
            raise ValueError("la combinación no tiene casos")
        casos = [(self._casos[k], float(f)) for k, f in factores.items()]
        base = casos[0][0]
        despl = sum(f * c.desplazamientos for c, f in casos)
        reac = sum(f * c.reacciones for c, f in casos)
        fext = sum(f * c.fuerzas_extremo for c, f in casos)
        mismas = all(
            np.array_equal(c._diagramas["barra"], base._diagramas["barra"])
            and np.array_equal(c._diagramas["x"], base._diagramas["x"])
            for c, _ in casos
        )
        if mismas:
            diag = {"barra": base._diagramas["barra"], "x": base._diagramas["x"]}
            for k in ("N", "V", "M", "u", "v"):
                diag[k] = sum(f * c._diagramas[k] for c, f in casos)
        else:
            diag = _combinar_diagramas_distintos(casos)
        return ResultadoCaso(nombre, despl, reac, fext, diag)


def _combinar_diagramas_distintos(casos: list[tuple[ResultadoCaso, float]]) -> dict:
    barras = np.unique(np.concatenate([c._diagramas["barra"] for c, _ in casos]))
    salida: dict[str, list] = {k: [] for k in ("barra", "x", "N", "V", "M", "u", "v")}
    for b in barras:
        xs = np.unique(np.concatenate([c.diagrama(b)["x"] for c, _ in casos]))
        salida["barra"].append(np.full(xs.size, b))
        salida["x"].append(xs)
        for k in ("N", "V", "M", "u", "v"):
            total = np.zeros(xs.size)
            for c, f in casos:
                d = c.diagrama(b)
                total += f * np.interp(xs, d["x"], d[k])
            salida[k].append(total)
    return {k: np.concatenate(v) for k, v in salida.items()}
