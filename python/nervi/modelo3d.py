# SPDX-License-Identifier: GPL-3.0-or-later
"""Modelo de pórtico espacial y resultados (Fase 2a, issues #11 y #12).

Convenciones (ver ``docs/convenciones.md``, «Pórtico espacial»):

* Ejes globales X, Y horizontales y Z vertical hacia arriba (terna derecha).
* 6 GDL por nudo: ``ux, uy, uz, rx, ry, rz``; giros por la regla de la mano derecha.
* Ejes locales de barra: ``x`` del nudo i al j; ``y`` en el plano que forman ``x``
  y el vector de referencia, del lado del vector; ``z = x ^ y`` (producto vectorial). Sin vector de
  referencia se usa ``+Z`` (en las vigas ``y`` apunta hacia arriba) y en las
  barras verticales ``z = -Y``.
* Esfuerzos: ``N`` positivo en tracción; ``Mz`` positivo si tracciona la fibra
  ``-y`` (como ``M`` del pórtico plano) y ``Vy = dMz/dx``; ``My`` positivo si
  tracciona la fibra ``+z`` y ``Vz = dMy/dx``; ``T`` por la regla de la mano
  derecha alrededor de ``+x``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

from . import _core

if TYPE_CHECKING:
    from .dinamica import ResultadosModal3D

_EJES = {"local": 0, "global": 1}
_DIAGRAMA = ("N", "Vy", "Vz", "T", "My", "Mz", "u", "v", "w", "rx")


@dataclass
class _Caso:
    nombre: str
    nodales: dict[int, np.ndarray] = field(default_factory=dict)
    impuestos: dict[int, np.ndarray] = field(default_factory=dict)


def _tres(v: Sequence[float], nombre: str) -> tuple[float, float, float]:
    if len(v) != 3:
        raise ValueError(f"'{nombre}' debe tener 3 componentes")
    return (float(v[0]), float(v[1]), float(v[2]))


class Modelo3D:
    """Pórtico espacial lineal elástico."""

    def __init__(self) -> None:
        self._nudos: list[tuple[float, float, float]] = []
        self._barras: list[dict] = []
        self._restricciones: dict[int, list[bool]] = {}
        self._resortes: dict[int, tuple[float, ...]] = {}
        self._casos: list[_Caso] = []
        self._cargas_barra: list[tuple[float, ...]] = []
        self._masas_nodales: dict[int, np.ndarray] = {}
        self._masas_lineales: dict[int, float] = {}
        self._masas_casos: dict[str, float] = {}
        self._gravedad = 9.80665

    # --- Geometría -------------------------------------------------------------
    def agregar_nudo(self, x: float, y: float, z: float) -> int:
        self._nudos.append((float(x), float(y), float(z)))
        return len(self._nudos) - 1

    def agregar_barra(
        self,
        nudo_i: int,
        nudo_j: int,
        E: float,
        G: float,
        A: float | None = None,
        Iy: float | None = None,
        Iz: float | None = None,
        J: float | None = None,
        *,
        seccion: dict[str, float] | None = None,
        referencia: Sequence[float] | None = None,
        articulada_i: bool = False,
        articulada_j: bool = False,
        liberaciones: Sequence[bool] | None = None,
    ) -> int:
        """Agrega una barra.

        Las propiedades ``A, Iy, Iz, J`` se dan sueltas o con ``seccion`` (ver
        :mod:`nervi.secciones`); las sueltas tienen prioridad. ``referencia`` es
        el vector (en globales) que fija el plano ``x-y`` local.
        ``articulada_i/j`` liberan ``My`` y ``Mz`` en ese extremo;
        ``liberaciones`` da las doce fuerzas de extremo locales
        ``(N, Vy, Vz, T, My, Mz)`` del extremo i y luego las del j.
        """
        props = dict(seccion or {})
        for nombre, v in (("A", A), ("Iy", Iy), ("Iz", Iz), ("J", J)):
            if v is not None:
                props[nombre] = v
            if nombre not in props:
                raise ValueError(f"falta la propiedad {nombre} (o una 'seccion')")
        if liberaciones is None:
            liberaciones = [False] * 12
            if articulada_i:
                liberaciones[4] = liberaciones[5] = True
            if articulada_j:
                liberaciones[10] = liberaciones[11] = True
        if len(liberaciones) != 12:
            raise ValueError("'liberaciones' debe tener 12 valores")
        ref = (0.0, 0.0, 0.0) if referencia is None else _tres(referencia, "referencia")
        if referencia is not None and ref == (0.0, 0.0, 0.0):
            raise ValueError("el vector de referencia no puede ser nulo")
        self._barras.append(
            {
                "nudos": (int(nudo_i), int(nudo_j)),
                "props": tuple(
                    float(x) for x in (E, G, props["A"], props["Iy"], props["Iz"], props["J"])
                ),
                "referencia": ref,
                "liberaciones": tuple(map(bool, liberaciones)),
            }
        )
        return len(self._barras) - 1

    def agregar_biela(self, nudo_i: int, nudo_j: int, E: float, A: float) -> int:
        """Barra de cercha espacial: solo transmite axil (momentos liberados en
        ambos extremos y torsión liberada en el j). Las inercias no intervienen."""
        lib = [False] * 12
        lib[4] = lib[5] = lib[9] = lib[10] = lib[11] = True
        # Las inercias y G se condensan por completo; valen cualquier positivo.
        return self.agregar_barra(nudo_i, nudo_j, E, E, A, A * A, A * A, A * A, liberaciones=lib)

    # --- Apoyos ----------------------------------------------------------------
    def apoyar(
        self,
        nudo: int,
        ux: bool = True,
        uy: bool = True,
        uz: bool = True,
        rx: bool = True,
        ry: bool = True,
        rz: bool = True,
    ) -> None:
        """Restringe GDL del nudo. Por defecto, empotramiento; un apoyo fijo
        articulado es ``apoyar(n, rx=False, ry=False, rz=False)``."""
        r = self._restricciones.setdefault(int(nudo), [False] * 6)
        for k, v in enumerate((ux, uy, uz, rx, ry, rz)):
            r[k] |= bool(v)

    def resorte(
        self,
        nudo: int,
        kx: float = 0.0,
        ky: float = 0.0,
        kz: float = 0.0,
        krx: float = 0.0,
        kry: float = 0.0,
        krz: float = 0.0,
    ) -> None:
        self._resortes[int(nudo)] = tuple(float(k) for k in (kx, ky, kz, krx, kry, krz))

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
        self,
        caso: str | int,
        nudo: int,
        fx: float = 0.0,
        fy: float = 0.0,
        fz: float = 0.0,
        mx: float = 0.0,
        my: float = 0.0,
        mz: float = 0.0,
    ) -> None:
        """Fuerzas y momentos en un nudo, en ejes globales."""
        c = self._casos[self._indice_caso(caso)]
        c.nodales.setdefault(int(nudo), np.zeros(6))
        c.nodales[int(nudo)] += (fx, fy, fz, mx, my, mz)

    def _carga(self, caso, barra, tipo, ejes, a, b, q1, q2) -> None:
        if ejes not in _EJES:
            raise ValueError(f"ejes {ejes!r} desconocidos ('local' o 'global')")
        self._cargas_barra.append(
            (self._indice_caso(caso), barra, tipo, _EJES[ejes], a, b, *q1, *q2)
        )

    def carga_uniforme(
        self,
        caso: str | int,
        barra: int,
        qx: float = 0.0,
        qy: float = 0.0,
        qz: float = 0.0,
        ejes: str = "local",
    ) -> None:
        """Carga uniforme en toda la luz. En ejes globales se entiende por unidad
        de longitud de barra (no proyectada); el peso propio es ``qz < 0`` global."""
        self._carga(caso, barra, 0, ejes, 0.0, 0.0, (qx, qy, qz), (0.0, 0.0, 0.0))

    def carga_puntual(
        self,
        caso: str | int,
        barra: int,
        a: float,
        px: float = 0.0,
        py: float = 0.0,
        pz: float = 0.0,
        ejes: str = "local",
    ) -> None:
        """Carga puntual a la distancia ``a`` del nudo i."""
        self._carga(caso, barra, 1, ejes, a, 0.0, (px, py, pz), (0.0, 0.0, 0.0))

    def carga_trapezoidal(
        self,
        caso: str | int,
        barra: int,
        q1: Sequence[float],
        q2: Sequence[float],
        a: float = 0.0,
        b: float | None = None,
        ejes: str = "local",
    ) -> None:
        """Carga que varía linealmente de ``q1 = (qx, qy, qz)`` en ``a`` a ``q2`` en
        ``b`` (distancias desde el nudo i, ``0 <= a < b <= L``; ``b=None`` es
        hasta el nudo j)."""
        fin = float("nan") if b is None else float(b)
        self._carga(caso, barra, 2, ejes, a, fin, _tres(q1, "q1"), _tres(q2, "q2"))

    def desplazamiento_impuesto(
        self,
        caso: str | int,
        nudo: int,
        ux: float = 0.0,
        uy: float = 0.0,
        uz: float = 0.0,
        rx: float = 0.0,
        ry: float = 0.0,
        rz: float = 0.0,
    ) -> None:
        """Asentamiento de apoyo. Solo actúa en los GDL restringidos del nudo."""
        c = self._casos[self._indice_caso(caso)]
        c.impuestos[int(nudo)] = np.array([ux, uy, uz, rx, ry, rz], dtype=np.float64)

    # --- Masas (Fase 2b) -------------------------------------------------------
    def masa_nodal(
        self,
        nudo: int,
        m: float = 0.0,
        *,
        mx: float | None = None,
        my: float | None = None,
        mz: float | None = None,
        Jx: float = 0.0,
        Jy: float = 0.0,
        Jz: float = 0.0,
    ) -> None:
        """Suma una masa en el nudo: ``m`` en las tres traslaciones (o ``mx, my,
        mz`` por separado) e inercias de rotación ``Jx, Jy, Jz`` (ejes globales
        por el nudo). Se acumula con las anteriores."""
        v = np.array(
            [
                m if mx is None else mx,
                m if my is None else my,
                m if mz is None else mz,
                Jx,
                Jy,
                Jz,
            ],
            dtype=np.float64,
        )
        self._masas_nodales.setdefault(int(nudo), np.zeros(6))
        self._masas_nodales[int(nudo)] += v

    def masa_lineal(self, barra: int, m: float) -> None:
        """Masa por unidad de longitud de la barra (densidad por área, ``rho * A``); se
        acumula. Se reparte según ``masa`` de :meth:`modal`."""
        self._masas_lineales[int(barra)] = self._masas_lineales.get(int(barra), 0.0) + float(m)

    def masa_desde_casos(self, factores: dict[str, float], gravedad: float = 9.80665) -> None:
        """Convierte en masa las cargas verticales de los casos, p. ej.
        ``{"D": 1.0, "L": 0.25}``: ``m = -Fz · factor / g`` en los nudos (las
        cargas en barras se reparten a sus nudos por estática). ``gravedad`` en
        las unidades del modelo (9.80665 para m/s², 980.665 para cm/s²).
        Reemplaza lo dado antes con este método."""
        self._masas_casos = {str(k): float(v) for k, v in factores.items()}
        self._gravedad = float(gravedad)

    # --- Análisis --------------------------------------------------------------
    def arreglos(self) -> dict[str, np.ndarray]:
        """Arreglos del contrato de datos 3D (ver ``docs/contrato-datos.md``)."""
        n, m, nc = len(self._nudos), len(self._barras), len(self._casos)
        coords = np.array(self._nudos, dtype=np.float64).reshape(n, 3)
        conect = np.array([b["nudos"] for b in self._barras], dtype=np.int64).reshape(m, 2)
        props = np.array([b["props"] for b in self._barras], dtype=np.float64).reshape(m, 6)
        refs = np.array([b["referencia"] for b in self._barras], dtype=np.float64).reshape(m, 3)
        lib = np.array([b["liberaciones"] for b in self._barras], dtype=np.uint8).reshape(m, 12)
        restr = np.zeros((n, 6), dtype=np.uint8)
        for k, r in self._restricciones.items():
            restr[k] = r
        resortes = np.zeros((n, 6), dtype=np.float64)
        for k, r in self._resortes.items():
            resortes[k] = r
        nodales = np.zeros((nc, n, 6), dtype=np.float64)
        impuestos = np.zeros((nc, n, 6), dtype=np.float64)
        for c, caso in enumerate(self._casos):
            for k, f in caso.nodales.items():
                nodales[c, k] = f
            for k, u in caso.impuestos.items():
                impuestos[c, k] = u
        cargas_barra = np.array(self._cargas_barra, dtype=np.float64).reshape(-1, 12)
        for fila in cargas_barra:
            if fila[2] == 2 and np.isnan(fila[5]):
                k = int(fila[1])
                if 0 <= k < m:
                    i, j = conect[k]
                    if 0 <= i < n and 0 <= j < n:
                        fila[5] = float(np.linalg.norm(coords[j] - coords[i]))
        return {
            "coords": coords,
            "conectividad": conect,
            "props": props,
            "referencias": refs,
            "liberaciones": lib,
            "restricciones": restr,
            "resortes": resortes,
            "cargas_nodales": nodales,
            "cargas_barra": cargas_barra,
            "despl_impuestos": impuestos,
        }

    def resolver(self, n_estaciones: int = 11) -> Resultados3D:
        """Resuelve todos los casos de carga. Lanza ``ValueError`` si el modelo es
        inválido y ``MecanismoError`` si la estructura es inestable."""
        if not self._casos:
            raise ValueError("el modelo no tiene casos de carga")
        crudo = _core.resolver_portico_3d(
            _core.VERSION_CONTRATO_3D, **self.arreglos(), n_estaciones=n_estaciones
        )
        return Resultados3D([c.nombre for c in self._casos], crudo)

    def modal(
        self,
        n_modos: int = 12,
        masa: str = "concentrada",
        metodo: str = "automatico",
    ) -> ResultadosModal3D:
        """Análisis modal: los ``n_modos`` modos de menor frecuencia.

        ``masa`` es ``"concentrada"`` (``m L/2`` en cada extremo, sin inercia
        rotacional) o ``"consistente"``; vale para las masas lineales (las
        nodales y las de los casos son siempre concentradas). ``metodo`` es
        ``"automatico"`` (denso exacto hasta 1500 GDL con masa, Lanczos por
        encima), ``"denso"`` o ``"lanczos"``. Devuelve
        :class:`nervi.dinamica.ResultadosModal3D`.
        """
        from .dinamica import ResultadosModal3D

        tipos = {"concentrada": 0, "consistente": 1}
        metodos = {"automatico": 0, "denso": 1, "lanczos": 2}
        if masa not in tipos:
            raise ValueError(f"masa {masa!r} desconocida ('concentrada' o 'consistente')")
        if metodo not in metodos:
            raise ValueError(f"método {metodo!r} desconocido ('automatico', 'denso' o 'lanczos')")
        if int(n_modos) < 1:
            raise ValueError("hay que pedir al menos un modo")
        n, m = len(self._nudos), len(self._barras)
        nodales = np.zeros((n, 6), dtype=np.float64)
        for k, v in self._masas_nodales.items():
            if not 0 <= k < n:
                raise ValueError(f"masa en el nudo inexistente {k}")
            nodales[k] = v
        lineales = np.zeros(m, dtype=np.float64)
        for k, v in self._masas_lineales.items():
            if not 0 <= k < m:
                raise ValueError(f"masa en la barra inexistente {k}")
            lineales[k] = v
        nombres = [c.nombre for c in self._casos]
        casos = np.zeros(len(nombres), dtype=np.float64)
        for nombre, f in self._masas_casos.items():
            if nombre not in nombres:
                raise ValueError(f"masa desde el caso inexistente {nombre!r}")
            casos[nombres.index(nombre)] = f
        arreglos = self.arreglos()
        crudo = _core.resolver_modal_3d(
            _core.VERSION_CONTRATO_DINAMICA,
            arreglos,
            nodales,
            lineales,
            casos,
            self._gravedad,
            tipos[masa],
            int(n_modos),
            metodos[metodo],
        )
        return ResultadosModal3D(arreglos, crudo)


class ResultadoCaso3D:
    """Resultados de un caso de carga (o de una combinación) del pórtico espacial."""

    def __init__(
        self,
        nombre: str,
        desplazamientos: np.ndarray,
        reacciones: np.ndarray,
        fuerzas_extremo: np.ndarray,
        diagramas: dict[str, np.ndarray],
    ) -> None:
        self.nombre = nombre
        #: (n_nudos, 6) ``[ux, uy, uz, rx, ry, rz]`` en ejes globales.
        self.desplazamientos = desplazamientos
        #: (n_nudos, 6) ``[Rx, Ry, Rz, Mx, My, Mz]`` en ejes globales.
        self.reacciones = reacciones
        #: (n_barras, 12) fuerzas de extremo en ejes locales, sobre la barra:
        #: ``[Fx, Fy, Fz, Mx, My, Mz]`` en i y luego en j.
        self.fuerzas_extremo = fuerzas_extremo
        self._diagramas = diagramas

    def diagrama(self, barra: int) -> dict[str, np.ndarray]:
        """Arreglos ``x, N, Vy, Vz, T, My, Mz, u, v, w, rx`` de la barra
        (desplazamientos en ejes locales)."""
        sel = self._diagramas["barra"] == barra
        return {k: v[sel] for k, v in self._diagramas.items() if k != "barra"}

    def __repr__(self) -> str:
        return f"ResultadoCaso3D({self.nombre!r})"


class Resultados3D:
    """Resultados de todos los casos de carga del pórtico espacial."""

    def __init__(self, nombres: list[str], crudo: dict) -> None:
        self.gdl_sin_rigidez: list[tuple[int, str]] = list(crudo["gdl_sin_rigidez"])
        #: (n_barras, 3, 3): filas ``x, y, z`` locales de cada barra en globales.
        self.ejes: np.ndarray = crudo["ejes"]
        self._casos = {
            nombre: ResultadoCaso3D(
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

    def __getitem__(self, nombre: str) -> ResultadoCaso3D:
        return self._casos[nombre]

    def combinar(self, nombre: str, factores: dict[str, float]) -> ResultadoCaso3D:
        """Combinación lineal de casos, p. ej. ``{"D": 1.2, "L": 1.6}``.

        Válida por superposición. Desplazamientos, reacciones y fuerzas de
        extremo son exactos; los diagramas también si todos los casos tienen
        las mismas estaciones, y si no se interpolan linealmente en la unión de
        estaciones (aproximado cerca de los saltos).
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
            for k in _DIAGRAMA:
                diag[k] = sum(f * c._diagramas[k] for c, f in casos)
        else:
            barras = np.unique(np.concatenate([c._diagramas["barra"] for c, _ in casos]))
            partes: dict[str, list] = {k: [] for k in ("barra", "x", *_DIAGRAMA)}
            for b in barras:
                xs = np.unique(np.concatenate([c.diagrama(b)["x"] for c, _ in casos]))
                partes["barra"].append(np.full(xs.size, b))
                partes["x"].append(xs)
                for k in _DIAGRAMA:
                    total = np.zeros(xs.size)
                    for c, f in casos:
                        d = c.diagrama(b)
                        total += f * np.interp(xs, d["x"], d[k])
                    partes[k].append(total)
            diag = {k: np.concatenate(v) for k, v in partes.items()}
        return ResultadoCaso3D(nombre, despl, reac, fext, diag)
