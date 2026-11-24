# SPDX-License-Identifier: GPL-3.0-or-later
"""Consultas de solo lectura sobre un proyecto, para agentes de IA.

Son funciones comunes de Python sobre :class:`nervi.proyecto.Proyecto`: el servidor
MCP (:mod:`nervi.ia.servidor`) las publica tal cual, y se pueden usar y probar sin
MCP. Todo lo que devuelven es JSON (diccionarios, listas, textos y números) y cada
número es el ``float64`` del motor, sin redondear.

Nudos y barras se nombran con los ``id`` de ``modelo.json`` (``N3``, ``B2``); las
herramientas aceptan el número solo (``3``) o con su letra (``"N3"``).

Las de consulta no cambian nada: con un archivo, lo leen; con la ventana abierta,
trabajan sobre una copia del proyecto, así que calcular, diseñar o analizar para
responder no toca lo que ve la persona. Las de la ventana (:data:`NOMBRES_VENTANA`)
leen la selección y dejan propuestas que la persona aplica o descarta.

>>> from nervi.proyecto import Proyecto, documento_ejemplo
>>> h = Herramientas(FuenteProyecto(Proyecto(documento_ejemplo())))
>>> h.resumen_proyecto()["cantidades"]
{'nudos': 4, 'barras': 3, 'apoyos': 2, 'casos': 3, 'combinaciones': 3}
"""

from __future__ import annotations

import copy
import os
import warnings
from pathlib import Path

import numpy as np

from .. import MecanismoError, formato
from ..proyecto import Proyecto

#: Orden de las componentes que devuelven las herramientas.
COMPONENTES_NUDO = ("ux", "uy", "rz")
COMPONENTES_REACCION = ("Rx", "Ry", "Mz")
COMPONENTES_EXTREMO = ("N_i", "V_i", "M_i", "N_j", "V_j", "M_j")
ESFUERZOS = ("N", "V", "M")

#: Origen de las propuestas que llegan por MCP (``Proyecto.proponer``).
ORIGEN = "ia: agente MCP"


class ErrorConsulta(ValueError):
    """La consulta no se puede responder (un id que no existe, falta calcular algo)."""


class FuenteProyecto:
    """Un proyecto abierto (el de la ventana). Las consultas usan una copia, que se
    renueva cuando cambian el modelo, el diseño o la dinámica; ``vivo`` es el
    proyecto mismo, para leer la selección y dejar propuestas."""

    def __init__(self, proyecto: Proyecto) -> None:
        self.vivo = proyecto
        self._copia: tuple | None = None

    @property
    def descripcion(self) -> str:
        return self.vivo.titulo

    def proyecto(self) -> Proyecto:
        from ..resultados import huella

        doc = self.vivo.doc
        clave = tuple(
            huella(x) if x is not None else None for x in (doc.modelo, doc.diseno, doc.dinamica)
        )
        if self._copia is None or self._copia[0] != clave:
            self._copia = (clave, Proyecto(copy.deepcopy(doc)))
        return self._copia[1]


class FuenteArchivo:
    """Un ``.nrv`` en disco, de solo lectura. Si la persona lo vuelve a guardar, la
    siguiente consulta lo abre de nuevo, así el agente ve siempre lo guardado."""

    def __init__(self, ruta: str | os.PathLike) -> None:
        self.ruta = Path(ruta)
        self._proyecto: Proyecto | None = None
        self._marca: tuple[int, int] | None = None

    @property
    def descripcion(self) -> str:
        return str(self.ruta)

    def proyecto(self) -> Proyecto:
        try:
            st = self.ruta.stat()
        except OSError as e:
            raise ErrorConsulta(f"No se puede leer {self.ruta}: {e.strerror}.") from None
        marca = (st.st_mtime_ns, st.st_size)
        if self._proyecto is None or marca != self._marca:
            p = Proyecto()
            try:
                p.abrir(self.ruta)
            except formato.FormatoError as e:
                raise ErrorConsulta(f"No se pudo abrir {self.ruta.name}: {e}") from None
            self._proyecto, self._marca = p, marca
        return self._proyecto


def _id(valor: int | str, letra: str) -> int:
    """``3``, ``"3"`` o ``"N3"`` → ``3``."""
    if isinstance(valor, bool):
        raise ErrorConsulta(f"{valor!r} no es un id de {'nudo' if letra == 'N' else 'barra'}")
    if isinstance(valor, int):
        return valor
    texto = str(valor).strip().upper()
    if texto.startswith(letra):
        texto = texto[1:]
    try:
        return int(texto)
    except ValueError:
        raise ErrorConsulta(
            f"{valor!r} no es un id de {'nudo' if letra == 'N' else 'barra'} "
            f"(se escribe {letra}3 o 3)"
        ) from None


def _lista(a) -> list:
    return np.asarray(a, dtype=np.float64).tolist()


def _por_componente(valores, nombres) -> dict[str, float]:
    return {n: float(v) for n, v in zip(nombres, valores, strict=True)}


class Herramientas:
    """Consultas de solo lectura sobre el proyecto que da ``fuente``."""

    def __init__(self, fuente: FuenteProyecto | FuenteArchivo, origen: str = ORIGEN) -> None:
        self.fuente = fuente
        self.origen = origen
        self._cache: tuple | None = None

    @property
    def nombres(self) -> tuple[str, ...]:
        """Herramientas disponibles con esta fuente."""
        if isinstance(self.fuente, FuenteProyecto):
            return NOMBRES + NOMBRES_VENTANA
        return NOMBRES

    def ejecutar(self, nombre: str, argumentos: dict | None = None):
        """Llama a la herramienta ``nombre`` con ``argumentos`` (lo que llega por el
        canal de la ventana). Lanza :class:`ErrorConsulta` si no existe o si los
        argumentos no corresponden."""
        if nombre not in self.nombres:
            raise ErrorConsulta(f"No hay una herramienta {nombre!r}.")
        if argumentos is None:
            argumentos = {}
        if not isinstance(argumentos, dict):
            raise ErrorConsulta("Los argumentos tienen que ser un objeto.")
        try:
            return getattr(self, nombre)(**argumentos)
        except TypeError as e:
            raise ErrorConsulta(f"Argumentos que no corresponden a {nombre}: {e}") from None

    # --- Acceso al proyecto y a sus resultados ---------------------------------------
    def _proyecto(self) -> Proyecto:
        return self.fuente.proyecto()

    def _resuelto(self):
        """``(proyecto, Resultados con combinaciones, Indices)``, calculado si hace falta."""
        from ..resultados import huella

        p = self._proyecto()
        clave = (id(p), huella(p.modelo))
        if self._cache is not None and self._cache[0] == clave:
            return p, *self._cache[1:]
        try:
            _modelo, res, indices = p._resolver_con_combinaciones()
        except MecanismoError as e:
            try:
                p.calcular()
            except MecanismoError:
                pass
            texto = p.inestabilidad.texto() if p.inestabilidad else str(e)
            raise ErrorConsulta(f"El modelo no se puede calcular. {texto}") from None
        except (formato.FormatoError, ValueError) as e:
            raise ErrorConsulta(f"El modelo tiene un error: {e}") from None
        self._cache = (clave, res, indices)
        return p, res, indices

    def _resultado(self, res, nombre: str):
        if nombre not in res.casos and nombre not in res.combinaciones:
            raise ErrorConsulta(
                f"No hay un caso ni una combinación {nombre!r}. Hay: "
                + ", ".join([*res.combinaciones, *res.casos])
                + "."
            )
        return res[nombre]

    def _indice_nudo(self, indices, nudo) -> tuple[int, int]:
        n = _id(nudo, "N")
        if n not in indices.nudos:
            raise ErrorConsulta(
                f"No existe el nudo N{n}. Nudos: " + ", ".join(f"N{k}" for k in indices.nudos)
            )
        return n, indices.nudos[n]

    def _indice_barra(self, indices, barra) -> tuple[int, int]:
        b = _id(barra, "B")
        if b not in indices.barras:
            raise ErrorConsulta(
                f"No existe la barra B{b}. Barras: " + ", ".join(f"B{k}" for k in indices.barras)
            )
        return b, indices.barras[b]

    # --- Herramientas ------------------------------------------------------------------
    def resumen_proyecto(self) -> dict:
        """Qué hay en el proyecto: unidades, cantidades, casos, combinaciones, apoyos,
        si tiene datos de diseño y de dinámica, y la revisión del modelo."""
        from ..resultados import huella

        p = self._proyecto()
        m = p.modelo
        return {
            "proyecto": self.fuente.descripcion,
            "unidades": dict(m["unidades"]),
            "cantidades": {
                "nudos": len(m["nudos"]),
                "barras": len(m["barras"]),
                "apoyos": len(m.get("apoyos", [])),
                "casos": len(m["casos"]),
                "combinaciones": len(m.get("combinaciones", [])),
            },
            "casos": [c["nombre"] for c in m["casos"]],
            "combinaciones": {c["nombre"]: c["factores"] for c in m.get("combinaciones", [])},
            "apoyos": [
                {"nudo": f"N{a['nudo']}", **{g: bool(a.get(g, False)) for g in COMPONENTES_NUDO}}
                for a in m.get("apoyos", [])
            ],
            "tiene_datos_de_diseno": p.doc.diseno is not None,
            "tiene_datos_de_dinamica": p.doc.dinamica is not None,
            "revision": [{"nivel": a.nivel, "texto": a.texto} for a in p.revisar()],
            "huella_modelo": huella(m),
        }

    def leer_modelo(self) -> dict:
        """El ``modelo.json`` completo (nudos, barras, apoyos, cargas, casos y
        combinaciones). Formato en ``docs/formato-nrv.md`` §4."""
        return self._proyecto().copia_modelo()

    def revisar_modelo(self) -> list[dict]:
        """Avisos de la revisión del modelo, los mismos del panel de la interfaz."""
        return [{"nivel": a.nivel, "texto": a.texto} for a in self._proyecto().revisar()]

    def listar_resultados(self) -> dict:
        """Nombres de los casos de carga y de las combinaciones calculadas."""
        _p, res, _i = self._resuelto()
        return {"casos": res.casos, "combinaciones": res.combinaciones}

    def leer_nudo(self, nudo: int | str, resultado: str | None = None) -> dict:
        """Desplazamientos ``[ux, uy, rz]`` del nudo y, si tiene apoyo, reacciones
        ``[Rx, Ry, Mz]`` (ejes globales). Sin ``resultado``, para todos los casos y
        combinaciones."""
        p, res, indices = self._resuelto()
        n, k = self._indice_nudo(indices, nudo)
        apoyado = any(a["nudo"] == n for a in p.modelo.get("apoyos", []))
        nombres = [resultado] if resultado else [*res.combinaciones, *res.casos]
        salida = {}
        for nombre in nombres:
            r = self._resultado(res, nombre)
            fila = {"desplazamientos": _por_componente(r.desplazamientos[k], COMPONENTES_NUDO)}
            if apoyado:
                fila["reacciones"] = _por_componente(r.reacciones[k], COMPONENTES_REACCION)
            salida[nombre] = fila
        return {"nudo": f"N{n}", "unidades": dict(p.modelo["unidades"]), "resultados": salida}

    def leer_barra(self, barra: int | str, resultado: str) -> dict:
        """Fuerzas de extremo (ejes locales) y diagramas N, V, M y deformada local de la
        barra en un caso o combinación, por estación, con el máximo y el mínimo de N, V
        y M y dónde ocurren. Las estaciones incluyen los puntos de carga y los de
        cortante nulo, así que el extremo de M está entre ellas."""
        p, res, indices = self._resuelto()
        b, k = self._indice_barra(indices, barra)
        r = self._resultado(res, resultado)
        diagrama = r.diagrama(k)
        x = diagrama["x"]
        extremos = {}
        for c in ESFUERZOS:
            v = diagrama[c]
            imax, imin = int(np.argmax(v)), int(np.argmin(v))
            extremos[c] = {
                "max": float(v[imax]),
                "x_max": float(x[imax]),
                "min": float(v[imin]),
                "x_min": float(x[imin]),
            }
        return {
            "barra": f"B{b}",
            "resultado": resultado,
            "longitud": float(x[-1]),
            "unidades": dict(p.modelo["unidades"]),
            "fuerzas_extremo": _por_componente(r.fuerzas_extremo[k], COMPONENTES_EXTREMO),
            "extremos": extremos,
            "diagrama": {c: _lista(v) for c, v in diagrama.items()},
        }

    def envolvente_barra(self, barra: int | str) -> dict:
        """Máximo y mínimo de N, V y M de la barra sobre todas las combinaciones, con la
        combinación y la posición de cada uno."""
        from ..design.envolvente import envolvente

        p, res, indices = self._resuelto()
        b, k = self._indice_barra(indices, barra)
        if not res.combinaciones:
            raise ErrorConsulta("El proyecto no tiene combinaciones de carga.")
        env = envolvente(res, k)
        x = env["x"]
        salida = {}
        for c in ESFUERZOS:
            vmax, vmin = env[f"{c}_max"], env[f"{c}_min"]
            imax, imin = int(np.argmax(vmax)), int(np.argmin(vmin))
            salida[c] = {
                "max": float(vmax[imax]),
                "x_max": float(x[imax]),
                "combinacion_max": str(env[f"{c}_max_comb"][imax]),
                "min": float(vmin[imin]),
                "x_min": float(x[imin]),
                "combinacion_min": str(env[f"{c}_min_comb"][imin]),
            }
        return {"barra": f"B{b}", "unidades": dict(p.modelo["unidades"]), "envolvente": salida}

    def leer_reacciones(self, resultado: str | None = None) -> dict:
        """Reacciones ``[Rx, Ry, Mz]`` de cada apoyo en un caso o combinación; sin
        ``resultado``, la envolvente (máximo y mínimo con su combinación)."""
        from ..design.envolvente import envolvente_reacciones

        p, res, indices = self._resuelto()
        apoyos = [a["nudo"] for a in p.modelo.get("apoyos", [])]
        if resultado:
            r = self._resultado(res, resultado)
            datos = {
                f"N{n}": _por_componente(r.reacciones[indices.nudos[n]], COMPONENTES_REACCION)
                for n in apoyos
            }
            return {"resultado": resultado, "unidades": dict(p.modelo["unidades"]), "apoyos": datos}
        if not res.combinaciones:
            raise ErrorConsulta("Sin combinaciones no hay envolvente: indicá un caso.")
        env = envolvente_reacciones(res)
        datos = {}
        for n in apoyos:
            k = indices.nudos[n]
            datos[f"N{n}"] = {
                g: {
                    "max": float(env["max"][k, j]),
                    "combinacion_max": str(env["max_comb"][k, j]),
                    "min": float(env["min"][k, j]),
                    "combinacion_min": str(env["min_comb"][k, j]),
                }
                for j, g in enumerate(COMPONENTES_REACCION)
            }
        return {"resultado": "envolvente", "unidades": dict(p.modelo["unidades"]), "apoyos": datos}

    def leer_verificaciones(self, barra: int | str | None = None) -> dict:
        """Diseño de hormigón armado (ACI 318-19, experimental): estado, armadura y cada
        verificación con solicitación, resistencia, relación y artículo. Solo si el
        proyecto tiene datos de diseño; se calcula sobre una copia, sin tocar el
        proyecto."""
        from ..design import proyecto as diseno_proyecto
        from ..resultados import _diseno

        p, _res, indices = self._resuelto()
        if p.doc.diseno is None:
            raise ErrorConsulta(
                "El proyecto no tiene datos de diseño (materiales y secciones). La persona "
                "tiene que cargarlos en la etapa Diseño de la interfaz."
            )
        if not p.diseno_al_dia:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                p.disenar()
        elementos = _diseno(p.resultados_diseno)
        if barra is not None:
            b, _k = self._indice_barra(indices, barra)
            elementos = [e for e in elementos if e["barra"] == f"B{b}"]
        return {
            "aviso": diseno_proyecto.AVISO_EXPERIMENTAL,
            "norma": diseno_proyecto.NORMA,
            "elementos": elementos,
        }

    def leer_modos(self) -> dict:
        """Análisis modal del pórtico: periodo, frecuencia y fracción de masa
        participante en X e Y de cada modo. Solo si el proyecto tiene datos de dinámica
        con masa; se calcula sobre una copia, sin tocar el proyecto."""
        p, _res, _i = self._resuelto()
        if p.doc.dinamica is None or not any(p.dinamica["masas"]["casos"].values()):
            raise ErrorConsulta(
                "El proyecto no tiene datos de dinámica con masa. La persona los carga en "
                "la pestaña Dinámica de la interfaz."
            )
        if not p.dinamica_al_dia:
            try:
                p.analizar_dinamica()
            except ValueError as e:
                raise ErrorConsulta(str(e)) from None
        modal = p.resultados_dinamica.modal
        return {
            "gravedad": p.resultados_dinamica.gravedad,
            "masa_total": _por_componente(modal.masa_total, ("X", "Y")),
            "modos": [
                {
                    "modo": k + 1,
                    "periodo_s": float(modal.periodos[k]),
                    "frecuencia_hz": float(modal.frecuencias[k]),
                    "masa_participante": _por_componente(modal.masa_participante[k], ("X", "Y")),
                }
                for k in range(modal.n_modos)
            ],
        }

    def resultados_completos(self) -> dict:
        """Todos los resultados sin redondear (formato ``nervi-resultados``)."""
        return self._proyecto().resultados_completos()

    # --- Herramientas con la ventana abierta -------------------------------------------
    def _vivo(self) -> Proyecto:
        if not isinstance(self.fuente, FuenteProyecto):
            raise ErrorConsulta(
                "Esta herramienta necesita la ventana de Nervi abierta y conectada; con un "
                "archivo solo se puede consultar."
            )
        return self.fuente.vivo

    def leer_seleccion(self) -> dict:
        """Lo que la persona tiene seleccionado en la ventana (un nudo o una barra) y la
        combinación que está mirando. Sirve para "esta barra" o "este nudo"."""
        p = self._vivo()
        sel = p.seleccion
        return {
            "seleccion": None
            if sel is None
            else {"tipo": sel.tipo, "id": f"{'N' if sel.tipo == 'nudo' else 'B'}{sel.id}"},
            "combinacion": p.combinacion or None,
        }

    def proponer_modelo(self, modelo: dict, descripcion: str) -> dict:
        """Propone reemplazar ``modelo.json`` por ``modelo`` (leelo antes con
        leer_modelo y cambiá solo lo pedido). No cambia nada: la persona ve el resumen
        en la ventana y la aplica o la descarta. ``descripcion`` dice en pocas
        palabras qué hace (por ejemplo "Agrega la carga de viento en B1")."""
        p = self._vivo()
        if not isinstance(modelo, dict):
            raise ErrorConsulta("El modelo tiene que ser un objeto, como el de leer_modelo.")
        if not isinstance(descripcion, str) or not descripcion.strip():
            raise ErrorConsulta("Falta la descripción de la propuesta.")
        try:
            propuesta = p.proponer(modelo, self.origen, descripcion.strip())
        except formato.FormatoError as e:
            raise ErrorConsulta(f"El modelo propuesto no es válido: {e}") from None
        except ValueError as e:
            raise ErrorConsulta(str(e)) from None
        return {
            "propuesta": propuesta.id,
            "resumen": propuesta.resumen,
            "estado": "pendiente: la persona la aplica o la descarta en la ventana de Nervi",
        }

    def listar_propuestas(self) -> list[dict]:
        """Propuestas que siguen pendientes, con su resumen. Una que ya no aparece fue
        aplicada o descartada por la persona."""
        return [
            {
                "propuesta": x.id,
                "origen": x.origen,
                "descripcion": x.descripcion,
                "resumen": x.resumen,
            }
            for x in self._vivo().propuestas
        ]


#: Herramientas de consulta, en orden.
NOMBRES = (
    "resumen_proyecto",
    "leer_modelo",
    "revisar_modelo",
    "listar_resultados",
    "leer_nudo",
    "leer_barra",
    "envolvente_barra",
    "leer_reacciones",
    "leer_verificaciones",
    "leer_modos",
)
#: Herramientas que necesitan la ventana abierta.
NOMBRES_VENTANA = ("leer_seleccion", "proponer_modelo", "listar_propuestas")
