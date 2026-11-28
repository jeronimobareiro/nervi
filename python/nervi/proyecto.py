# SPDX-License-Identifier: GPL-3.0-or-later
"""Proyecto abierto, sin interfaz gráfica: documento, cálculo, diseño, dinámica y memoria.

Todo cambio pasa por el diccionario de ``modelo.json`` del documento
(``nervi.formato``), y el cálculo se hace con ``nervi.formato.construir_modelo`` +
``Modelo.resolver``. La interfaz de escritorio (``nervi.gui.sesion.Sesion``) hereda
:class:`Proyecto` y solo le agrega las señales de Qt, así que lo que se hace desde
acá da los mismos resultados que en la interfaz.

No confundir con ``nervi.design.proyecto``, que diseña los elementos de un proyecto.
"""

from __future__ import annotations

import copy
import itertools
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from . import MecanismoError, formato
from .modelo import ResultadoCaso, Resultados


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
    from .modelo import Modelo

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


#: Origen de los cambios que hace la persona a mano.
PERSONA = "persona"
#: Cambios que se pueden deshacer, como máximo (los más viejos se descartan).
LIMITE_DESHACER = 100


@dataclass(frozen=True)
class Cambio:
    """Un cambio que se puede deshacer: una parte del proyecto antes y después."""

    parte: str  # "modelo", "diseno" o "dinamica"
    antes: dict | None
    despues: dict | None
    origen: str
    descripcion: str


@dataclass
class Propuesta:
    """Cambio del modelo que propone alguien que no es la persona (un agente de IA,
    un importador, un complemento). No cambia nada hasta que la persona lo aplica.

    ``base`` es la huella del modelo sobre el que se hizo: si el modelo cambió
    después, la propuesta ya no se puede aplicar."""

    id: int
    origen: str
    descripcion: str
    modelo: dict
    base: str
    resumen: list[str] = field(default_factory=list)


def _por_clave(lista: list, clave: str) -> dict:
    return {x[clave]: x for x in lista if isinstance(x, dict) and clave in x}


def resumir_cambios(antes: dict, despues: dict) -> list[str]:
    """Qué cambia entre dos ``modelo.json``, en frases cortas con los ``id`` del
    usuario: ``"Agrega N5"``, ``"Cambia B2 (I)"``, ``"Cargas en barras: 2 → 3"``."""
    lineas: list[str] = []
    if antes.get("unidades") != despues.get("unidades"):
        lineas.append("Cambia las unidades")
    for lista, clave, letra in (
        ("nudos", "id", "N"),
        ("barras", "id", "B"),
        ("apoyos", "nudo", "apoyo en N"),
        ("resortes", "nudo", "resorte en N"),
        ("casos", "id", "caso "),
        ("combinaciones", "nombre", "combinación "),
    ):
        a = _por_clave(antes.get(lista, []), clave)
        d = _por_clave(despues.get(lista, []), clave)

        def nombre(k, x, letra=letra, lista=lista) -> str:
            return f"{letra}{x.get('nombre', k)}" if lista == "casos" else f"{letra}{k}"

        for k in d.keys() - a.keys():
            lineas.append(f"Agrega {nombre(k, d[k])}")
        for k in a.keys() - d.keys():
            lineas.append(f"Quita {nombre(k, a[k])}")
        for k in a.keys() & d.keys():
            if a[k] != d[k]:
                campos = sorted(c for c in a[k].keys() | d[k].keys() if a[k].get(c) != d[k].get(c))
                lineas.append(f"Cambia {nombre(k, d[k])} ({', '.join(campos)})")
    for lista, titulo in (
        ("cargas_nodales", "Cargas en nudos"),
        ("cargas_barra", "Cargas en barras"),
        ("desplazamientos_impuestos", "Desplazamientos impuestos"),
    ):
        a, d = antes.get(lista, []), despues.get(lista, [])
        if a != d:
            lineas.append(
                f"{titulo}: {len(a)} → {len(d)}" if len(a) != len(d) else f"Cambia {titulo.lower()}"
            )
    return sorted(lineas, key=lambda t: (not t.startswith("Cambia las"), t))


class Proyecto:
    """Proyecto abierto y su estado, sin interfaz gráfica.

    Es la capa que comparten la interfaz de escritorio (``nervi.gui.Sesion`` la
    hereda y traduce los eventos a señales de Qt), los scripts y las integraciones
    que vengan (servidor MCP para agentes de IA, complementos). Guarda el documento
    (``nervi.formato``), los resultados del último cálculo, de diseño y de
    dinámica, la combinación activa y la selección.

    Cada cambio se avisa con un evento a quien se haya suscripto con
    :meth:`suscribir`: ``"archivo"``, ``"modelo"``, ``"resultados"``,
    ``"seleccion"``, ``"diseno"`` o ``"dinamica"``.

    >>> from nervi.proyecto import Proyecto, documento_ejemplo
    >>> p = Proyecto(documento_ejemplo())
    >>> p.calcular()
    >>> p.combinacion
    '1.4D'
    """

    #: Eventos que puede avisar un proyecto, en el orden de :meth:`_reiniciar`.
    #: ``"historial"`` avisa que cambió lo que se puede deshacer o rehacer, o las
    #: propuestas pendientes.
    EVENTOS = (
        "archivo",
        "modelo",
        "resultados",
        "seleccion",
        "diseno",
        "dinamica",
        "historial",
        "fisico",
    )

    def __init__(self, doc: formato.Documento | None = None, **kwargs) -> None:
        # Cooperativo: ``Sesion`` hereda de ``Proyecto`` y de ``QObject``.
        super().__init__(**kwargs)
        self._oyentes: list[Callable[[str], None]] = []
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
        #: Edificio (#74): el último análisis del modelo de cálculo generado.
        self.resultados_edificio = None
        self.edificio_al_dia = False
        self._calculo_edificio = None
        self._combinadas: dict = {}
        self._deshacer: list[Cambio] = []
        self._rehacer: list[Cambio] = []
        # Última copia guardada de cada parte: si la parte no cambió desde entonces,
        # el cambio siguiente la reusa como "antes" en vez de copiarla otra vez.
        self._ultimo: dict[str, dict | None] = {}
        self.propuestas: list[Propuesta] = []
        self._ids_propuesta = itertools.count(1)
        self.revisar()

    # --- Eventos -------------------------------------------------------------------
    def suscribir(self, oyente: Callable[[str], None]) -> Callable[[], None]:
        """Llama a ``oyente(evento)`` en cada cambio. Devuelve la función que
        cancela la suscripción."""
        self._oyentes.append(oyente)
        return lambda: self._oyentes.remove(oyente)

    def _avisar(self, evento: str) -> None:
        for oyente in list(self._oyentes):
            oyente(evento)

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
        self._avisar("archivo")

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
        self.resultados_edificio = None
        self.edificio_al_dia = False
        self._calculo_edificio = None
        self._combinadas.clear()
        self._deshacer.clear()
        self._rehacer.clear()
        self._ultimo.clear()
        self.propuestas.clear()
        self.revisar()
        self._avisar("archivo")
        self._avisar("modelo")
        self._avisar("resultados")
        self._avisar("seleccion")
        self._avisar("diseno")
        self._avisar("dinamica")
        self._avisar("historial")
        self._avisar("fisico")

    # --- Edición -----------------------------------------------------------------
    @property
    def modelo(self) -> dict:
        return self.doc.modelo

    def editar(
        self, nuevo_modelo: dict, origen: str = PERSONA, descripcion: str = "Editar el modelo"
    ) -> None:
        """Reemplaza ``modelo.json`` por una versión editada. Los resultados quedan
        desactualizados hasta volver a calcular. Se puede deshacer."""
        self._registrar("modelo", self.doc.modelo, nuevo_modelo, origen, descripcion)
        self._poner_modelo(nuevo_modelo)
        self._avisar("historial")

    def _poner_modelo(self, nuevo_modelo: dict) -> None:
        self.doc.modelo = nuevo_modelo
        self.modificado = True
        self.al_dia = False
        self.inestabilidad = None
        self.diseno_al_dia = False
        self.dinamica_al_dia = False
        self.revisar()
        self._avisar("archivo")
        self._avisar("modelo")
        self._avisar("resultados")
        self._avisar("diseno")
        self._avisar("dinamica")

    def copia_modelo(self) -> dict:
        return copy.deepcopy(self.doc.modelo)

    def seleccionar(self, sel: Seleccion | None) -> None:
        if sel != self.seleccion:
            self.seleccion = sel
            self._avisar("seleccion")

    # --- Revisión y cálculo ------------------------------------------------------
    def revisar(self) -> list[Aviso]:
        """Revisión del modelo (lo que muestra el panel "Revisión del modelo"). En un
        edificio, la del modelo de cálculo que se genera desde él."""
        if self.es_edificio:
            return self._revisar_edificio()
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
        """Casos y combinaciones disponibles para mostrar (en un edificio, los del
        modelo de cálculo generado)."""
        if self.es_edificio:
            from .idealizacion import CASOS, COMBINACIONES

            return [*COMBINACIONES, *CASOS]
        m = self.modelo
        nombres = [c["nombre"] for c in m.get("combinaciones", [])]
        nombres += [c["nombre"] for c in m["casos"]]
        if self.dinamica_al_dia and self.resultados_dinamica is not None:
            nombres += [n for n in self.resultados_dinamica.nombres if n not in nombres]
        return nombres

    def calcular(self) -> None:
        """Resuelve el modelo. Lanza ``FormatoError``, ``ValueError`` o ``MecanismoError``.
        En un edificio resuelve el modelo de cálculo generado desde él
        (:meth:`calcular_edificio`)."""
        if self.es_edificio:
            self.calcular_edificio()
            return
        try:
            modelo, indices = formato.construir_modelo(self.modelo)
            resultados = modelo.resolver()
        except MecanismoError as e:
            self.inestabilidad = _inestabilidad(e, indices)
            self.avisos = [Aviso("error", self.inestabilidad.texto())]
            self._avisar("resultados")
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
        self._avisar("resultados")

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

    def editar_dinamica(
        self, nuevo: dict, origen: str = PERSONA, descripcion: str = "Editar la dinámica"
    ) -> None:
        """Reemplaza los datos de dinámica. Lanza ``FormatoError`` si no son válidos.
        Se puede deshacer."""
        formato.dinamica.validar(nuevo)
        self._registrar("dinamica", self.doc.dinamica, nuevo, origen, descripcion)
        self._poner_dinamica(nuevo)
        self._avisar("historial")

    def _poner_dinamica(self, nuevo: dict | None) -> None:
        self.doc.dinamica = nuevo
        self.modificado = True
        self.dinamica_al_dia = False
        self._avisar("archivo")
        self._avisar("dinamica")
        self._avisar("resultados")

    def gravedad(self) -> float:
        """g en las unidades de longitud del modelo (por s²)."""
        from .dinamica_plana import GRAVEDAD

        return GRAVEDAD[self.modelo["unidades"]["longitud"]]

    def analizar_dinamica(self) -> ResultadosDinamica:
        """Análisis modal y por espectro con los datos de :attr:`dinamica`.

        Calcula el modelo si hace falta. Lanza ``ValueError`` si no hay masa o
        un caso de masa no existe, y lo mismo que :meth:`calcular`."""
        from . import dinamica_plana

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
            self._avisar("archivo")
        self.resultados_dinamica = ResultadosDinamica(modal, modos, espectros, g)
        self.dinamica_al_dia = True
        self._avisar("dinamica")
        self._avisar("resultados")
        return self.resultados_dinamica

    # --- Datos del proyecto -----------------------------------------------------------
    @property
    def proyecto(self) -> dict:
        """Datos de ``proyecto.json`` (vacíos si el proyecto no tiene)."""
        return self.doc.proyecto if self.doc.proyecto is not None else formato.proyecto.nuevo()

    def editar_proyecto(self, nuevo: dict) -> None:
        """Reemplaza los datos del proyecto. Lanza ``FormatoError`` si no son válidos.
        Sin ningún dato el módulo deja de guardarse."""
        formato.proyecto.validar(nuevo)
        vacio = not nuevo["datos"] and not nuevo.get("extensiones")
        self.doc.proyecto = None if vacio else nuevo
        self.modificado = True
        self._avisar("archivo")

    # --- Modelo físico ------------------------------------------------------------------
    @property
    def fisico(self) -> dict | None:
        """Datos de ``fisico.json`` (``None`` si el proyecto no tiene modelo físico).
        Para leerlos o armarlos, ``nervi.fisico.ModeloFisico.desde_json``."""
        return self.doc.fisico

    def editar_fisico(
        self, nuevo: dict | None, descripcion: str = "Editar el modelo físico"
    ) -> None:
        """Reemplaza el modelo físico (``None`` lo quita). Lanza ``FormatoError`` si no
        es válido. Se puede deshacer. Por ahora solo lo edita la persona: las
        propuestas de agentes e importadores son del modelo analítico."""
        if nuevo is not None:
            formato.fisico.validar(nuevo)
        self._registrar("fisico", self.doc.fisico, nuevo, PERSONA, descripcion)
        self._poner_fisico(nuevo)
        self._avisar("historial")

    def _poner_fisico(self, nuevo: dict | None) -> None:
        self.doc.fisico = nuevo
        self.modificado = True
        self._calculo_edificio = None
        self._combinadas.clear()
        self.edificio_al_dia = False
        self.revisar()
        self._avisar("archivo")
        self._avisar("fisico")
        self._avisar("resultados")

    # --- Edificio: modelo de cálculo generado (#74) -----------------------------------
    @property
    def es_edificio(self) -> bool:
        """El proyecto tiene modelo físico: manda el edificio y el modelo de cálculo
        se genera desde él (``docs/diseno-interfaz.md`` §Un solo modelo). Sin modelo
        físico, el proyecto es un pórtico plano armado a mano."""
        return self.doc.fisico is not None

    def modelo_calculo(self):
        """El modelo de cálculo generado desde el edificio
        (:class:`nervi.idealizacion.ModeloCalculo`), guardado hasta que el edificio
        cambie. Lanza ``ValueError`` si el proyecto no tiene edificio."""
        if not self.es_edificio:
            raise ValueError("el proyecto no tiene modelo físico")
        if self._calculo_edificio is None:
            from .fisico import ModeloFisico

            self._calculo_edificio = ModeloFisico.desde_json(self.doc.fisico).modelo_calculo()
        return self._calculo_edificio

    def _revisar_edificio(self) -> list[Aviso]:
        avisos: list[Aviso] = []
        try:
            mc = self.modelo_calculo()
        except (ValueError, KeyError) as e:
            avisos.append(Aviso("error", f"No se pudo generar el modelo de cálculo: {e}"))
            self.avisos = avisos
            return avisos
        if mc.n_barras == 0:
            avisos.append(Aviso("info", "El edificio todavía no tiene columnas, vigas ni muros."))
        else:
            avisos.append(
                Aviso(
                    "ok",
                    f"Modelo de cálculo generado del edificio: {len(mc.nudos)} nudos, "
                    f"{mc.n_barras} barras y {len(mc.maestros)} diafragmas.",
                )
            )
            if not mc.apoyos:
                avisos.append(
                    Aviso("error", "No hay apoyos: ninguna columna ni muro llega a la base.")
                )
        from .fisico import ModeloFisico

        mf = None
        for a in mc.avisos:
            mf = mf or ModeloFisico.desde_json(self.doc.fisico)
            avisos.append(Aviso("info", a.texto(mf)))
        self.avisos = avisos
        return avisos

    def calcular_edificio(self) -> None:
        """Genera el modelo de cálculo del edificio y lo resuelve con sus casos ``D`` y
        ``L``; las combinaciones son las de :data:`nervi.idealizacion.COMBINACIONES`.
        Lanza ``ValueError`` o ``MecanismoError``."""
        mc = self.modelo_calculo()
        self.resultados_edificio = mc.modelo.resolver()
        self._combinadas.clear()
        self.edificio_al_dia = True
        nombres = self.nombres_resultado()
        if self.combinacion not in nombres:
            self.combinacion = nombres[0]
        self.revisar()
        self.avisos.append(Aviso("ok", "Estructura estable: el sistema de ecuaciones se resolvió."))
        self._avisar("resultados")

    def resultado_edificio(self):
        """Resultado del edificio (``ResultadoCaso3D``) en el caso o la combinación
        activa, si está al día."""
        from .idealizacion import COMBINACIONES

        res = self.resultados_edificio
        if not self.edificio_al_dia or res is None or not self.combinacion:
            return None
        nombre = self.combinacion
        if nombre in COMBINACIONES:
            if nombre not in self._combinadas:
                self._combinadas[nombre] = res.combinar(nombre, COMBINACIONES[nombre])
            return self._combinadas[nombre]
        return res[nombre] if nombre in res.casos else None

    # --- Diseño --------------------------------------------------------------------
    @property
    def diseno(self) -> dict:
        """Datos de ``diseno.json`` (los de por defecto si el proyecto no tiene)."""
        return self.doc.diseno if self.doc.diseno is not None else formato.diseno.nuevo()

    def editar_diseno(
        self, nuevo: dict, origen: str = PERSONA, descripcion: str = "Editar el diseño"
    ) -> None:
        """Reemplaza los datos de diseño. Lanza ``FormatoError`` si no son válidos.
        Se puede deshacer."""
        formato.diseno.validar(nuevo)
        self._registrar("diseno", self.doc.diseno, nuevo, origen, descripcion)
        self._poner_diseno(nuevo)
        self._avisar("historial")

    def _poner_diseno(self, nuevo: dict | None) -> None:
        self.doc.diseno = nuevo
        self.modificado = True
        self.diseno_al_dia = False
        self._avisar("archivo")
        self._avisar("diseno")

    def _resolver_con_combinaciones(self):
        m = self.modelo
        modelo, indices = formato.construir_modelo(m)
        combinaciones = {c["nombre"]: c["factores"] for c in m.get("combinaciones", [])}
        return modelo, modelo.resolver(combinaciones=combinaciones or None), indices

    def disenar(self) -> list:
        """Diseña todas las barras (``nervi.design.proyecto``). Calcula si hace falta.

        Lanza ``ValueError`` si no hay combinaciones, y lo mismo que :meth:`calcular`."""
        from .design import proyecto as diseno_proyecto

        if not self.al_dia:
            self.calcular()
        _modelo, res, indices = self._resolver_con_combinaciones()
        resultados = diseno_proyecto.disenar(self.modelo, self.diseno, res, indices)
        if self.doc.diseno is None:
            # Desde que se diseña, los datos de diseño son parte del proyecto.
            self.doc.diseno = self.diseno
            self.modificado = True
            self._avisar("archivo")
        self.resultados_diseno = resultados
        self.diseno_al_dia = True
        self._avisar("diseno")
        return resultados

    def resultado_diseno(self, barra: int):
        """Resultado de diseño de la barra ``barra`` (id), si está al día."""
        if not self.diseno_al_dia or not self.resultados_diseno:
            return None
        return next((r for r in self.resultados_diseno if r.elemento.barra == barra), None)

    def memoria(self, datos_proyecto: dict[str, str] | None = None):
        """Memoria de cálculo (``nervi.memoria.Memoria``) del proyecto abierto, con
        los ``id`` de nudos y barras que ve el usuario. Calcula si hace falta."""
        from .memoria import memoria_de_calculo

        if not self.al_dia or self.resultados is None or self.indices is None:
            self.calcular()
        m = self.modelo
        modelo, res, indices = self._resolver_con_combinaciones()
        datos = {"Proyecto": self.ruta.stem if self.ruta else "Sin título"}
        datos.update(formato.proyecto.para_caratula(self.doc.proyecto))
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
            from .design import proyecto as diseno_proyecto

            diseno = self.resultados_diseno if self.diseno_al_dia else self.disenar()
            doc.agregar(diseno_proyecto.capitulo_memoria(diseno, self.diseno))
            doc.avisos.append(diseno_proyecto.AVISO_EXPERIMENTAL)
            doc.normas.append(diseno_proyecto.NORMA)
        # Si el proyecto tiene datos de dinámica con masa, suma el análisis dinámico.
        if self.doc.dinamica is not None and any(self.dinamica["masas"]["casos"].values()):
            from .memoria.dinamica import capitulo_dinamica

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

    # --- Deshacer, rehacer y propuestas ------------------------------------------------
    def _registrar(
        self, parte: str, antes: dict | None, despues: dict | None, origen: str, descripcion: str
    ) -> None:
        if not isinstance(origen, str) or not origen.strip():
            raise ValueError("el origen de un cambio tiene que ser un texto no vacío")
        # Las copias guardadas no se tocan nunca: al restaurar se copian de nuevo.
        if parte in self._ultimo and self._ultimo[parte] == antes:
            antes = self._ultimo[parte]
        else:
            antes = copy.deepcopy(antes)
        despues = copy.deepcopy(despues)
        self._ultimo[parte] = despues
        cambio = Cambio(parte, antes, despues, origen, descripcion)
        self._deshacer.append(cambio)
        del self._deshacer[:-LIMITE_DESHACER]
        self._rehacer.clear()
        if origen != PERSONA:
            self._anotar("aplicar", cambio)

    @property
    def puede_deshacer(self) -> bool:
        return bool(self._deshacer)

    @property
    def puede_rehacer(self) -> bool:
        return bool(self._rehacer)

    @property
    def que_deshacer(self) -> str | None:
        """Descripción del cambio que desharía :meth:`deshacer` (``None`` si no hay)."""
        return self._deshacer[-1].descripcion if self._deshacer else None

    @property
    def que_rehacer(self) -> str | None:
        return self._rehacer[-1].descripcion if self._rehacer else None

    def deshacer(self) -> Cambio | None:
        """Vuelve la parte que tocó el último cambio a como estaba. Devuelve el
        cambio deshecho (``None`` si no había nada)."""
        if not self._deshacer:
            return None
        cambio = self._deshacer.pop()
        self._rehacer.append(cambio)
        self._restaurar(cambio.parte, cambio.antes)
        if cambio.origen != PERSONA:
            self._anotar("deshacer", cambio)
        self._avisar("historial")
        return cambio

    def rehacer(self) -> Cambio | None:
        """Vuelve a aplicar el último cambio deshecho."""
        if not self._rehacer:
            return None
        cambio = self._rehacer.pop()
        self._deshacer.append(cambio)
        self._restaurar(cambio.parte, cambio.despues)
        if cambio.origen != PERSONA:
            self._anotar("rehacer", cambio)
        self._avisar("historial")
        return cambio

    def _restaurar(self, parte: str, valor: dict | None) -> None:
        self._ultimo[parte] = valor
        valor = copy.deepcopy(valor)
        if parte == "modelo":
            self._poner_modelo(valor)
        elif parte == "diseno":
            self._poner_diseno(valor)
        elif parte == "fisico":
            self._poner_fisico(valor)
        else:
            self._poner_dinamica(valor)

    def _anotar(self, accion: str, cambio: Cambio) -> None:
        """Agrega el cambio al módulo ``historial`` del ``.nrv``."""
        from .resultados import huella

        if self.doc.historial is None:
            self.doc.historial = formato.historial.nuevo()
        antes, despues = (
            (cambio.antes, cambio.despues)
            if accion != "deshacer"
            else (cambio.despues, cambio.antes)
        )
        resumen = (
            resumir_cambios(antes, despues)
            if cambio.parte == "modelo"
            else [f"Cambia los datos de {cambio.parte}"]
        )
        cambios = self.doc.historial["cambios"]
        cambios.append(
            {
                "fecha": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "accion": accion,
                "parte": cambio.parte,
                "origen": cambio.origen,
                "descripcion": cambio.descripcion,
                "resumen": resumen,
                "huella_antes": huella(antes if antes is not None else {}),
                "huella_despues": huella(despues if despues is not None else {}),
            }
        )
        del cambios[: -formato.historial.MAX_CAMBIOS]
        self.modificado = True

    def proponer(self, nuevo_modelo: dict, origen: str, descripcion: str = "") -> Propuesta:
        """Deja pendiente un cambio del modelo para que la persona lo revise.

        No cambia el proyecto. Lanza ``FormatoError`` si el modelo propuesto no es
        válido y ``ValueError`` si ``origen`` está vacío o es la persona."""
        from .resultados import huella

        if not isinstance(origen, str) or not origen.strip() or origen == PERSONA:
            raise ValueError("una propuesta tiene que decir de dónde viene (no de la persona)")
        formato.validar(nuevo_modelo)
        propuesta = Propuesta(
            next(self._ids_propuesta),
            origen,
            descripcion,
            copy.deepcopy(nuevo_modelo),
            huella(self.modelo),
            resumir_cambios(self.modelo, nuevo_modelo),
        )
        self.propuestas.append(propuesta)
        self._avisar("historial")
        return propuesta

    def _propuesta(self, id: int) -> Propuesta:
        for p in self.propuestas:
            if p.id == id:
                return p
        raise KeyError(f"no hay una propuesta pendiente con id {id}")

    def aplicar(self, id: int) -> None:
        """Aplica la propuesta pendiente ``id``: es la persona la que decide.

        Lanza ``ValueError`` si el modelo cambió desde que se hizo la propuesta
        (habría que pedirla de nuevo) y ``KeyError`` si no existe."""
        from .resultados import huella

        p = self._propuesta(id)
        if huella(self.modelo) != p.base:
            raise ValueError(
                "El modelo cambió desde que se hizo esta propuesta; hay que pedirla de nuevo."
            )
        self.propuestas.remove(p)
        self.editar(copy.deepcopy(p.modelo), origen=p.origen, descripcion=p.descripcion)

    def descartar(self, id: int) -> None:
        """Descarta la propuesta pendiente ``id`` sin cambiar nada."""
        self.propuestas.remove(self._propuesta(id))
        self._avisar("historial")

    def resultados_completos(self) -> dict:
        """Todos los resultados a precisión completa, sin redondear
        (``nervi.resultados.exportar``). Calcula si hace falta."""
        from . import resultados

        return resultados.exportar(self)

    def exportar_resultados(self, ruta: str | Path) -> Path:
        """Escribe :meth:`resultados_completos` en un JSON (``nervi-resultados``)."""
        from . import resultados

        ruta = Path(ruta)
        resultados.guardar(resultados.exportar(self), ruta)
        return ruta

    def elegir_combinacion(self, nombre: str) -> None:
        if nombre != self.combinacion:
            self.combinacion = nombre
            self._avisar("resultados")


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
