# SPDX-License-Identifier: GPL-3.0-or-later
"""Análisis modal y espectro de respuesta del pórtico espacial (Fase 2b).

Issues #16 (masas), #17 (modal) y #18 (espectro). Las masas se cargan en
:class:`nervi.Modelo3D` con ``masa_nodal``, ``masa_lineal`` y
``masa_desde_casos``; ``Modelo3D.modal`` devuelve :class:`ResultadosModal3D` y
su método :meth:`ResultadosModal3D.espectro` hace el análisis por espectro de
respuesta en una dirección.

Unidades: las del modelo. Con fuerzas en kN y longitudes en m, la masa va en t
(kN·s²/m), la gravedad en m/s² y la aceleración espectral en m/s².

Convenciones (ver ``docs/convenciones.md``, «Dinámica»):

* Modos normalizados a masa (``φᵀ M φ = 1``) y con la traslación de mayor valor
  absoluto positiva.
* ``Γ = φᵀ M r`` con ``r`` la dirección de la excitación; masa efectiva ``Γ²``.
* La respuesta espectral de cada modo es la estática con ``u = Γ Sa(T)/ω² φ``;
  las magnitudes se combinan con SRSS o CQC y son **valores absolutos**: no se
  suman a otros casos con signo.

>>> import nervi
>>> m = nervi.Modelo3D()
>>> a, b = m.agregar_nudo(0, 0, 0), m.agregar_nudo(0, 0, 3)
>>> _ = m.agregar_barra(a, b, E=2.5e7, G=1e7, A=0.16, Iy=3e-3, Iz=2e-3, J=3e-3)
>>> m.apoyar(a)
>>> m.masa_nodal(b, 10.0)
>>> modal = m.modal(n_modos=2)
>>> float(round(modal.periodos[0], 4))
0.2666
>>> r = modal.espectro([(0.0, 5.0), (1.0, 5.0)], direccion="X")
>>> float(round(r.cortante_basal[0], 6))
50.0
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from . import _core
from .modelo3d import ResultadoCaso3D, _pisos, derivas_de_piso

_DIRECCIONES = {"X": (1.0, 0.0, 0.0), "Y": (0.0, 1.0, 0.0), "Z": (0.0, 0.0, 1.0)}
_COMBINACIONES = {"SRSS": 0, "CQC": 1}


def _direccion(direccion: str | Sequence[float]) -> np.ndarray:
    if isinstance(direccion, str):
        clave = direccion.upper()
        if clave not in _DIRECCIONES:
            raise ValueError(f"dirección {direccion!r} desconocida ('X', 'Y', 'Z' o un vector)")
        return np.array(_DIRECCIONES[clave])
    v = np.asarray(direccion, dtype=np.float64)
    if v.shape != (3,):
        raise ValueError("la dirección debe ser 'X', 'Y', 'Z' o un vector de 3 componentes")
    return v


def _espectro(espectro) -> tuple[np.ndarray, np.ndarray]:
    puntos = np.asarray(espectro, dtype=np.float64)
    if puntos.ndim != 2 or puntos.shape[1] != 2 or puntos.shape[0] == 0:
        raise ValueError("el espectro es una lista de pares (T, Sa)")
    return np.ascontiguousarray(puntos[:, 0]), np.ascontiguousarray(puntos[:, 1])


class ResultadosModal3D:
    """Resultados del análisis modal (``Modelo3D.modal``)."""

    def __init__(self, modelo: dict[str, np.ndarray], crudo: dict) -> None:
        self._modelo = modelo
        #: Frecuencias circulares ω (rad/s), de menor a mayor.
        self.omegas: np.ndarray = crudo["omegas"]
        #: Periodos T = 2π/ω.
        self.periodos: np.ndarray = crudo["periodos"]
        #: Frecuencias f = 1/T.
        self.frecuencias: np.ndarray = crudo["frecuencias"]
        #: (n_modos, n_nudos, 6) formas modales normalizadas a masa, en globales.
        self.modos: np.ndarray = crudo["modos"]
        #: (n_modos, n_nudos, 6) fuerzas de inercia unitarias ``M φ``.
        self.inercias: np.ndarray = crudo["inercias"]
        #: (n_modos, 3) factores de participación Γ en X, Y y Z.
        self.factores_participacion: np.ndarray = crudo["factores_participacion"]
        #: (n_modos, 3) masas modales efectivas Γ² en X, Y y Z.
        self.masas_efectivas: np.ndarray = crudo["masas_efectivas"]
        #: (3,) masa que puede participar en X, Y y Z (la de los GDL libres).
        self.masa_total: np.ndarray = crudo["masa_total"]
        #: Cantidad de GDL libres con masa (cota de la cantidad de modos).
        self.n_gdl_masa: int = crudo["n_gdl_masa"]
        #: ``"denso"`` o ``"lanczos"``.
        self.metodo: str = crudo["metodo"]
        self.gdl_sin_rigidez: list[tuple[int, str]] = list(crudo["gdl_sin_rigidez"])
        #: Masa de cada diafragma rígido, concentrada en su maestro: diccionarios
        #: con ``maestro``, ``masa`` ``[mx, my]``, ``centro_masa`` ``[x, y]`` e
        #: ``inercia`` (alrededor del eje vertical por el centro de masa).
        self.diafragmas: list[dict] = [
            {
                "maestro": int(d["maestro"]),
                "masa": np.asarray(d["masa"]),
                "centro_masa": np.asarray(d["centro_masa"]),
                "inercia": float(d["inercia"]),
            }
            for d in crudo.get("diafragmas", [])
        ]

    @property
    def n_modos(self) -> int:
        return int(self.omegas.size)

    @property
    def masa_participante(self) -> np.ndarray:
        """(n_modos, 3) fracción de la masa total que moviliza cada modo."""
        total = np.where(self.masa_total > 0, self.masa_total, np.inf)
        return self.masas_efectivas / total

    @property
    def masa_participante_acumulada(self) -> np.ndarray:
        """(n_modos, 3) suma acumulada de :attr:`masa_participante`. Las normas
        sísmicas suelen pedir al menos 90 % en cada dirección horizontal."""
        return np.cumsum(self.masa_participante, axis=0)

    def tabla(self) -> str:
        """Tabla de texto con periodo, frecuencia y masa participante."""
        filas = [
            "modo   T [s]    f [Hz]   %Mx    %My    %Mz    ΣMx    ΣMy    ΣMz",
        ]
        p = 100 * self.masa_participante
        a = 100 * self.masa_participante_acumulada
        for k in range(self.n_modos):
            filas.append(
                f"{k + 1:4d} {self.periodos[k]:8.4f} {self.frecuencias[k]:8.3f} "
                + " ".join(f"{v:6.1f}" for v in (*p[k], *a[k]))
            )
        return "\n".join(filas)

    def espectro(
        self,
        espectro: Sequence[tuple[float, float]] | np.ndarray,
        direccion: str | Sequence[float] = "X",
        amortiguamiento: float = 0.05,
        combinacion: str = "CQC",
        n_estaciones: int = 11,
        nombre: str | None = None,
    ) -> ResultadoEspectro3D:
        """Análisis por espectro de respuesta.

        ``espectro`` es una lista de pares ``(T, Sa)`` con periodos crecientes;
        entre puntos se interpola linealmente y fuera del rango se toma el
        extremo más cercano. ``direccion`` es ``"X"``, ``"Y"``, ``"Z"`` o un
        vector en globales (se usa tal cual). ``combinacion`` es ``"CQC"`` o
        ``"SRSS"``; ``amortiguamiento`` es la fracción del crítico de todos los
        modos (solo interviene en CQC). El espectro de la norma lo arma quien
        diseña: Nervi todavía no trae espectros normativos.
        """
        clave = combinacion.upper()
        if clave not in _COMBINACIONES:
            raise ValueError(f"combinación {combinacion!r} desconocida ('CQC' o 'SRSS')")
        periodos, aceleraciones = _espectro(espectro)
        d = _direccion(direccion)
        crudo = _core.espectro_3d(
            _core.VERSION_CONTRATO_DINAMICA,
            self._modelo,
            self.omegas,
            self.modos,
            self.inercias,
            periodos,
            aceleraciones,
            d,
            float(amortiguamiento),
            _COMBINACIONES[clave],
            n_estaciones=n_estaciones,
        )
        if nombre is None:
            nombre = f"Espectro {direccion}" if isinstance(direccion, str) else "Espectro"
        res = ResultadoEspectro3D(nombre, clave, crudo)
        escala = res.factores * res.aceleraciones / self.omegas**2
        res._pisos = _pisos(self._modelo)
        res._u_modal = self.modos * escala[:, None, None]
        return res

    def __repr__(self) -> str:
        return f"ResultadosModal3D({self.n_modos} modos, T1 = {self.periodos[0]:.4g})"


class ResultadoEspectro3D(ResultadoCaso3D):
    """Respuesta combinada por espectro (valores absolutos).

    Tiene la misma forma que un caso de carga (``desplazamientos``,
    ``reacciones``, ``fuerzas_extremo`` y ``diagrama``), pero cada magnitud es
    la combinación modal de su valor absoluto: no se puede sumar con signo a
    otros casos ni usar en ``Resultados3D.combinar``.
    """

    def __init__(self, nombre: str, combinacion: str, crudo: dict) -> None:
        super().__init__(
            nombre,
            crudo["desplazamientos"],
            crudo["reacciones"],
            crudo["fuerzas_extremo"],
            crudo["diagramas"],
        )
        self.combinacion = combinacion
        #: (3,) cortante basal combinado ``[Vx, Vy, Vz]``.
        self.cortante_basal: np.ndarray = crudo["cortante_basal"]
        #: (n_modos, 3) cortante basal de cada modo, con signo.
        self.cortante_basal_modal: np.ndarray = crudo["cortante_basal_modal"]
        #: Aceleración espectral Sa(T) de cada modo.
        self.aceleraciones: np.ndarray = crudo["aceleraciones"]
        #: Factor de participación de cada modo en la dirección de excitación.
        self.factores: np.ndarray = crudo["factores"]
        #: (n_modos, n_modos) coeficientes de correlación (identidad en SRSS).
        self.correlacion: np.ndarray = crudo["correlacion"]
        self._pisos: dict | None = None
        self._u_modal: np.ndarray | None = None

    def derivas(self) -> dict[str, np.ndarray]:
        """Desplazamientos y derivas de piso combinados (valores absolutos):
        la deriva de cada modo se calcula con signo y después se combina, como
        corresponde (no es la diferencia de los desplazamientos combinados)."""
        return derivas_de_piso(self._pisos, self._u_modal, self.correlacion)

    def __repr__(self) -> str:
        return f"ResultadoEspectro3D({self.nombre!r}, {self.combinacion})"
