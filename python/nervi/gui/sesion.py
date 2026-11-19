# SPDX-License-Identifier: GPL-3.0-or-later
"""Estado de la sesión de trabajo: documento abierto, cálculo y selección.

La interfaz no guarda datos propios: todo cambio pasa por el diccionario de
``modelo.json`` del documento (``nervi.formato``), y el cálculo se hace con
``nervi.formato.construir_modelo`` + ``Modelo.resolver``.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from .. import MecanismoError, formato
from ..modelo import ResultadoCaso, Resultados


@dataclass(frozen=True)
class Seleccion:
    tipo: str  # "barra" o "nudo"
    id: int


@dataclass(frozen=True)
class Inestabilidad:
    """Dónde es inestable el modelo, con los ``id`` de ``modelo.json``.

    ``nudo`` y ``gdl`` son el nudo y el grado de libertad que se mueven sin
    rigidez (``None`` si el motor no pudo localizarlo) y ``nudos`` todos los
    nudos que se mueven en los modos de mecanismo (issue #9).
    """

    nudo: int | None
    gdl: str | None
    nudos: frozenset[int]

    def texto(self) -> str:
        if self.nudo is None:
            return "Estructura inestable (mecanismo): revisá apoyos y articulaciones."
        texto = (
            f"Estructura inestable: N{self.nudo} se puede mover en {self.gdl} "
            "sin que nada lo impida"
        )
        otros = sorted(self.nudos - {self.nudo})
        if otros:
            texto += " (también se mueven " + ", ".join(f"N{n}" for n in otros) + ")"
        return texto + "."


@dataclass
class ResultadosDinamica:
    """Análisis modal y espectral del proyecto (``nervi.dinamica_plana``).

    ``modos`` y ``espectros`` son resultados del pórtico plano que las vistas
    dibujan como cualquier caso: ``Modo 1``, ``Modo 2``… y un resultado por
    espectro, con su nombre."""

    modal: object  # nervi.dinamica_plana.ResultadosModalPlano
    modos: dict[str, ResultadoCaso]
    espectros: dict[str, ResultadoCaso]
    #: Gravedad usada (unidades de longitud del modelo por s²).
    gravedad: float

    def resultado(self, nombre: str) -> ResultadoCaso | None:
        return self.modos.get(nombre) or self.espectros.get(nombre)

    @property
    def nombres(self) -> list[str]:
        return [*self.modos, *self.espectros]


@dataclass
class Aviso:
    nivel: str  # "ok", "info", "error"
    texto: str


def documento_ejemplo() -> formato.Documento:
    """Pórtico de una crujía de ``examples/portico_simple.py`` (kN, m)."""
    from ..modelo import Modelo

    E = 2.5e7
    columna = dict(E=E, A=0.30 * 0.30, I=0.30 * 0.30**3 / 12)
    viga = dict(E=E, A=0.25 * 0.50, I=0.25 * 0.50**3 / 12)
    m = Modelo()
    a, b = m.agregar_nudo(0.0, 0.0), m.agregar_nudo(0.0, 3.0)
    c, d = m.agregar_nudo(6.0, 3.0), m.agregar_nudo(6.0, 0.0)
    m.agregar_barra(a, b, **columna)
    v = m.agregar_barra(b, c, **viga)
    m.agregar_barra(d, c, **columna)
    m.apoyar(a)
    m.apoyar(d)
    m.carga_uniforme("D", v, qy=-20.0)
    m.carga_uniforme("L", v, qy=-10.0)
    m.carga_nodal("W", b, fx=15.0)
    return formato.Documento.desde_modelo(
        m,
        {
            "1.4D": {"D": 1.4},
            "1.2D+1.6L": {"D": 1.2, "L": 1.6},
            "1.2D+1.0L+1.0W": {"D": 1.2, "L": 1.0, "W": 1.0},
        },
    )


class Sesion(QObject):
    """Documento abierto y su estado. Emite señales para que las vistas se actualicen."""

    modelo_cambiado = Signal()
    resultados_cambiados = Signal()
    seleccion_cambiada = Signal()
    archivo_cambiado = Signal()
    diseno_cambiado = Signal()
    dinamica_cambiada = Signal()

    def __init__(self, doc: formato.Documento | None = None) -> None:
        super().__init__()
        self.doc = doc or formato.Documento.nuevo()
        self.ruta: Path | None = None
        self.modificado = False
        self.resultados: Resultados | None = None
        self.indices: formato.modelo.Indices | None = None
        self.al_dia = False
        self.combinacion = ""
        self.seleccion: Seleccion | None = None
        self.avisos: list[Aviso] = []
        self.inestabilidad: Inestabilidad | None = None
        self.resultados_diseno: list | None = None
        self.diseno_al_dia = False
        self.resultados_dinamica: ResultadosDinamica | None = None
        self.dinamica_al_dia = False
        self.revisar()

    # --- Archivo ---------------------------------------------------------------
    @property
    def titulo(self) -> str:
        return self.ruta.name if self.ruta else "Sin título.nrv"

    def nuevo(self, doc: formato.Documento | None = None) -> None:
        self.doc = doc or formato.Documento.nuevo()
        self.ruta = None
        self._reiniciar()

    def abrir(self, ruta: str | Path) -> None:
        """Abre un ``.nrv``. Lanza ``formato.FormatoError`` si no es válido."""
        doc = formato.abrir(ruta)
        self.doc = doc
        self.ruta = Path(ruta)
        self._reiniciar()

    def guardar(self, ruta: str | Path | None = None) -> None:
        ruta = Path(ruta) if ruta else self.ruta
        if ruta is None:
            raise ValueError("falta la ruta del archivo")
        if ruta.suffix.lower() != ".nrv":
            ruta = ruta.with_suffix(".nrv")
        formato.guardar(self.doc, ruta, copia_bak=bool(self.doc.migrado_desde))
        self.doc.migrado_desde = None
        self.ruta = ruta
        self.modificado = False
        self.archivo_cambiado.emit()

    def _reiniciar(self) -> None:
        self.modificado = False
        self.resultados = None
        self.indices = None
        self.al_dia = False
        self.combinacion = ""
        self.seleccion = None
        self.inestabilidad = None
        self.resultados_diseno = None
        self.diseno_al_dia = False
        self.resultados_dinamica = None
        self.dinamica_al_dia = False
        self.revisar()
        self.archivo_cambiado.emit()
        self.modelo_cambiado.emit()
        self.resultados_cambiados.emit()
        self.seleccion_cambiada.emit()
        self.diseno_cambiado.emit()
        self.dinamica_cambiada.emit()

    # --- Edición -----------------------------------------------------------------
    @property
    def modelo(self) -> dict:
        return self.doc.modelo

    def editar(self, nuevo_modelo: dict) -> None:
        """Reemplaza ``modelo.json`` por una versión editada. Los resultados quedan
        desactualizados hasta volver a calcular."""
        self.doc.modelo = nuevo_modelo
        self.modificado = True
        self.al_dia = False
        self.inestabilidad = None
        self.diseno_al_dia = False
        self.dinamica_al_dia = False
        self.revisar()
        self.archivo_cambiado.emit()
        self.modelo_cambiado.emit()
        self.resultados_cambiados.emit()
        self.diseno_cambiado.emit()
        self.dinamica_cambiada.emit()

    def copia_modelo(self) -> dict:
        return copy.deepcopy(self.doc.modelo)

    def seleccionar(self, sel: Seleccion | None) -> None:
        if sel != self.seleccion:
            self.seleccion = sel
            self.seleccion_cambiada.emit()

    # --- Revisión y cálculo ------------------------------------------------------
    def revisar(self) -> list[Aviso]:
        """Revisión del modelo (lo que muestra el panel "Revisión del modelo")."""
        avisos: list[Aviso] = []
        m = self.modelo
        try:
            formato.validar(m)
        except formato.FormatoError as e:
            avisos.append(Aviso("error", f"{e.ruta or e.miembro}: {e.motivo}"))
            self.avisos = avisos
            return avisos
        if not m["nudos"] or not m["barras"]:
            avisos.append(Aviso("info", "El modelo todavía no tiene nudos y barras."))
        if not m.get("apoyos"):
            avisos.append(Aviso("error", "No hay apoyos: la estructura es un mecanismo."))
        if not m["casos"]:
            avisos.append(Aviso("info", "No hay casos de carga."))
        usados = {n for b in m["barras"] for n in (b["i"], b["j"])}
        sueltos = [n["id"] for n in m["nudos"] if n["id"] not in usados]
        if sueltos:
            lista = ", ".join(f"N{i}" for i in sueltos)
            avisos.append(Aviso("error", f"Nudos sin barras: {lista}."))
        pares = {}
        for b in m["barras"]:
            par = frozenset((b["i"], b["j"]))
            if par in pares:
                avisos.append(Aviso("error", f"B{b['id']} se superpone con B{pares[par]}."))
            pares[par] = b["id"]
        en_comb = {n for c in m.get("combinaciones", []) for n in c["factores"]}
        for c in m["casos"]:
            if m.get("combinaciones") and c["nombre"] not in en_comb:
                avisos.append(
                    Aviso("info", f"El caso {c['nombre']} no entra en ninguna combinación.")
                )
        if not any(a.nivel == "error" for a in avisos):
            avisos.insert(0, Aviso("ok", "Datos completos y referencias válidas."))
        self.avisos = avisos
        return avisos

    def nombres_resultado(self) -> list[str]:
        """Casos y combinaciones disponibles para mostrar."""
        m = self.modelo
        nombres = [c["nombre"] for c in m.get("combinaciones", [])]
        nombres += [c["nombre"] for c in m["casos"]]
        if self.dinamica_al_dia and self.resultados_dinamica is not None:
            nombres += [n for n in self.resultados_dinamica.nombres if n not in nombres]
        return nombres

    def calcular(self) -> None:
        """Resuelve el modelo. Lanza ``FormatoError``, ``ValueError`` o ``MecanismoError``."""
        try:
            modelo, indices = formato.construir_modelo(self.modelo)
            resultados = modelo.resolver()
        except MecanismoError as e:
            self.inestabilidad = _inestabilidad(e, indices)
            self.avisos = [Aviso("error", self.inestabilidad.texto())]
            self.resultados_cambiados.emit()
            if self.inestabilidad.nudo is not None:
                self.seleccionar(Seleccion("nudo", self.inestabilidad.nudo))
            raise
        self.inestabilidad = None
        self.resultados = resultados
        self.indices = indices
        self.al_dia = True
        nombres = self.nombres_resultado()
        if self.combinacion not in nombres:
            self.combinacion = nombres[0] if nombres else ""
        self.revisar()
        self.avisos.insert(
            1 if self.avisos and self.avisos[0].nivel == "ok" else 0,
            Aviso("ok", "Estructura estable: el sistema de ecuaciones se resolvió."),
        )
        self.resultados_cambiados.emit()

    def resultado(self) -> ResultadoCaso | None:
        """Resultado del caso o la combinación activa, si está al día."""
        if not self.al_dia or self.resultados is None or not self.combinacion:
            return None
        for c in self.modelo.get("combinaciones", []):
            if c["nombre"] == self.combinacion:
                return self.resultados.combinar(c["nombre"], c["factores"])
        if self.combinacion in self.resultados.casos:
            return self.resultados[self.combinacion]
        if self.dinamica_al_dia and self.resultados_dinamica is not None:
            return self.resultados_dinamica.resultado(self.combinacion)
        return None

    # --- Dinámica ------------------------------------------------------------------
    @property
    def dinamica(self) -> dict:
        """Datos de ``dinamica.json`` (los de por defecto si el proyecto no tiene)."""
        return self.doc.dinamica if self.doc.dinamica is not None else formato.dinamica.nuevo()

    def editar_dinamica(self, nuevo: dict) -> None:
        """Reemplaza los datos de dinámica. Lanza ``FormatoError`` si no son válidos."""
        formato.dinamica.validar(nuevo)
        self.doc.dinamica = nuevo
        self.modificado = True
        self.dinamica_al_dia = False
        self.archivo_cambiado.emit()
        self.dinamica_cambiada.emit()
        self.resultados_cambiados.emit()

    def gravedad(self) -> float:
        """g en las unidades de longitud del modelo (por s²)."""
        from ..dinamica_plana import GRAVEDAD

        return GRAVEDAD[self.modelo["unidades"]["longitud"]]

    def analizar_dinamica(self) -> ResultadosDinamica:
        """Análisis modal y por espectro con los datos de :attr:`dinamica`.

        Calcula el modelo si hace falta. Lanza ``ValueError`` si no hay masa o
        un caso de masa no existe, y lo mismo que :meth:`calcular`."""
        from .. import dinamica_plana

        if not self.al_dia:
            self.calcular()
        datos = self.dinamica
        casos = {c["nombre"] for c in self.modelo["casos"]}
        masas = {k: v for k, v in datos["masas"]["casos"].items() if v > 0}
        if not masas:
            raise ValueError(
                "Elegí de qué casos de carga sale la masa (por ejemplo D con factor 1)."
            )
        faltan = sorted(set(masas) - casos)
        if faltan:
            raise ValueError("La masa usa casos que no existen: " + ", ".join(faltan) + ".")
        g = self.gravedad()
        modelo, _indices = formato.construir_modelo(self.modelo)
        modal = dinamica_plana.modal(modelo, masas, g, n_modos=datos["n_modos"])
        modos = {r.nombre: r for r in modal.modos()}
        espectros = {}
        for e in datos["espectros"]:
            puntos = [(t, sa * g) for t, sa in e["puntos"]]
            espectros[e["nombre"]] = modal.espectro(
                puntos,
                e["direccion"],
                amortiguamiento=e["amortiguamiento"],
                combinacion=e["combinacion"],
                nombre=e["nombre"],
            )
        if self.doc.dinamica is None:
            # Desde que se analiza, los datos de dinámica son parte del proyecto.
            self.doc.dinamica = datos
            self.modificado = True
            self.archivo_cambiado.emit()
        self.resultados_dinamica = ResultadosDinamica(modal, modos, espectros, g)
        self.dinamica_al_dia = True
        self.dinamica_cambiada.emit()
        self.resultados_cambiados.emit()
        return self.resultados_dinamica

    # --- Diseño --------------------------------------------------------------------
    @property
    def diseno(self) -> dict:
        """Datos de ``diseno.json`` (los de por defecto si el proyecto no tiene)."""
        return self.doc.diseno if self.doc.diseno is not None else formato.diseno.nuevo()

    def editar_diseno(self, nuevo: dict) -> None:
        """Reemplaza los datos de diseño. Lanza ``FormatoError`` si no son válidos."""
        formato.diseno.validar(nuevo)
        self.doc.diseno = nuevo
        self.modificado = True
        self.diseno_al_dia = False
        self.archivo_cambiado.emit()
        self.diseno_cambiado.emit()

    def _resolver_con_combinaciones(self):
        m = self.modelo
        modelo, indices = formato.construir_modelo(m)
        combinaciones = {c["nombre"]: c["factores"] for c in m.get("combinaciones", [])}
        return modelo, modelo.resolver(combinaciones=combinaciones or None), indices

    def disenar(self) -> list:
        """Diseña todas las barras (``nervi.design.proyecto``). Calcula si hace falta.

        Lanza ``ValueError`` si no hay combinaciones, y lo mismo que :meth:`calcular`."""
        from ..design import proyecto

        if not self.al_dia:
            self.calcular()
        _modelo, res, indices = self._resolver_con_combinaciones()
        resultados = proyecto.disenar(self.modelo, self.diseno, res, indices)
        if self.doc.diseno is None:
            # Desde que se diseña, los datos de diseño son parte del proyecto.
            self.doc.diseno = self.diseno
            self.modificado = True
            self.archivo_cambiado.emit()
        self.resultados_diseno = resultados
        self.diseno_al_dia = True
        self.diseno_cambiado.emit()
        return resultados

    def resultado_diseno(self, barra: int):
        """Resultado de diseño de la barra ``barra`` (id), si está al día."""
        if not self.diseno_al_dia or not self.resultados_diseno:
            return None
        return next((r for r in self.resultados_diseno if r.elemento.barra == barra), None)

    def memoria(self, datos_proyecto: dict[str, str] | None = None):
        """Memoria de cálculo (``nervi.memoria.Memoria``) del proyecto abierto, con
        los ``id`` de nudos y barras que ve el usuario. Calcula si hace falta."""
        from ..memoria import memoria_de_calculo

        if not self.al_dia or self.resultados is None or self.indices is None:
            self.calcular()
        m = self.modelo
        modelo, res, indices = self._resolver_con_combinaciones()
        datos = {"Proyecto": self.ruta.stem if self.ruta else "Sin título"}
        datos.update(datos_proyecto or {})
        u = m["unidades"]
        doc = memoria_de_calculo(
            modelo,
            res,
            datos_proyecto=datos,
            fuerza=u["fuerza"],
            longitud=u["longitud"],
            nombres_nudos=lambda k: f"N{indices.id_nudo(k)}",
            nombres_barras=lambda k: f"B{indices.id_barra(k)}",
        )
        # Si el proyecto tiene datos de diseño, la memoria suma su capítulo.
        if self.doc.diseno is not None and res.combinaciones:
            from ..design import proyecto

            diseno = self.resultados_diseno if self.diseno_al_dia else self.disenar()
            doc.agregar(proyecto.capitulo_memoria(diseno, self.diseno))
            doc.avisos.append(proyecto.AVISO_EXPERIMENTAL)
        # Si el proyecto tiene datos de dinámica con masa, suma el análisis dinámico.
        if self.doc.dinamica is not None and any(self.dinamica["masas"]["casos"].values()):
            from ..memoria.dinamica import capitulo_dinamica

            din = self.resultados_dinamica if self.dinamica_al_dia else self.analizar_dinamica()
            capitulo = capitulo_dinamica(
                modelo,
                din.modal,
                self.dinamica,
                din.espectros,
                din.gravedad,
                fuerza=u["fuerza"],
                longitud=u["longitud"],
                nombre_nudo=lambda k: f"N{indices.id_nudo(k)}",
                nombre_barra=lambda k: f"B{indices.id_barra(k)}",
            )
            doc.agregar(capitulo, antes_de="Diseño")
        return doc

    def elegir_combinacion(self, nombre: str) -> None:
        if nombre != self.combinacion:
            self.combinacion = nombre
            self.resultados_cambiados.emit()


def _inestabilidad(e: MecanismoError, indices: formato.modelo.Indices) -> Inestabilidad:
    """Traduce los índices del motor que trae ``MecanismoError`` a ``id`` de nudos."""
    a_id = {k: i for i, k in indices.nudos.items()}
    nudo = getattr(e, "nudo", None)
    nudos = {
        a_id[n] for modo in (getattr(e, "modos", None) or []) for n, _g, _v in modo if n in a_id
    }
    if nudo is not None and nudo in a_id:
        nudo = a_id[nudo]
        nudos.add(nudo)
    else:
        nudo = None
    return Inestabilidad(
        nudo, getattr(e, "gdl", None) if nudo is not None else None, frozenset(nudos)
    )
