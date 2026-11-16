# SPDX-License-Identifier: GPL-3.0-or-later
"""Renderizador PDF de la memoria con ReportLab.

ReportLab (https://www.reportlab.com/opensource/) es software libre con licencia
BSD, compatible con GPL-3.0. Se usan solo las fuentes estándar de PDF
(Helvetica y Symbol), que no se incrustan, así que no se distribuye ninguna
fuente con el programa.
"""

from __future__ import annotations

import re
from pathlib import Path

try:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        BaseDocTemplate,
        CondPageBreak,
        Flowable,
        Frame,
        KeepTogether,
        NextPageTemplate,
        PageBreak,
        PageTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
    )
    from reportlab.platypus.tableofcontents import TableOfContents
except ImportError as e:  # pragma: no cover - depende del entorno
    raise ImportError("La memoria en PDF necesita ReportLab: pip install 'nervi[memoria]'") from e

from .documento import Capitulo, Figura, Memoria, Parrafo, Tabla

# --- Texto -------------------------------------------------------------------------
# Helvetica usa la codificación WinAnsi. Lo que falta (letras griegas, flechas,
# signos matemáticos) se escribe con la fuente Symbol, que también es estándar.
_SIMBOLOS = "αβγδεκλμνπρστφωΔΣΦ→≤≥≈∞"  # ReportLab los traduce a la codificación de Symbol
_REEMPLAZOS = {"−": "-", " ": " ", " ": " "}
_PATRON_SIMBOLOS = re.compile(f"[{_SIMBOLOS}]+")


def _texto(s: str) -> str:
    """Prepara texto con marcas para ``Paragraph``: ``<sub>``/``<sup>`` y símbolos."""
    for a, b in _REEMPLAZOS.items():
        s = s.replace(a, b)
    s = re.sub(r"&(?![a-zA-Z]+;|#\d+;)", "&amp;", s)
    return _PATRON_SIMBOLOS.sub(lambda m: f'<font name="Symbol">{m.group(0)}</font>', s)


def _plano(s: str) -> str:
    """Texto sin marcas para dibujar con ``drawString`` (rótulos de figuras)."""
    s = re.sub(r"<[^>]+>", "", s)
    for a, b in _REEMPLAZOS.items():
        s = s.replace(a, b)
    return s


# --- Estilos -----------------------------------------------------------------------
TINTA = colors.HexColor("#1d2330")
TENUE = colors.HexColor("#9aa3b2")
ACENTO = colors.HexColor("#1f5fa8")
POSITIVO = colors.HexColor("#1f5fa8")
NEGATIVO = colors.HexColor("#c0392b")
DEFORMADA = colors.HexColor("#d9822b")
FONDO_ENCABEZADO = colors.HexColor("#e8edf5")
FONDO_AVISO = colors.HexColor("#fff6e0")
BORDE_AVISO = colors.HexColor("#d9a62b")

_BASE = ParagraphStyle("base", fontName="Helvetica", fontSize=9.5, leading=13, textColor=TINTA)
ESTILOS = {
    "normal": ParagraphStyle("normal", parent=_BASE, spaceAfter=6),
    "nota": ParagraphStyle("nota", parent=_BASE, fontSize=8, leading=10, textColor=TENUE),
    "aviso": ParagraphStyle(
        "aviso",
        parent=_BASE,
        backColor=FONDO_AVISO,
        borderColor=BORDE_AVISO,
        borderWidth=0.6,
        borderPadding=6,
        spaceBefore=8,
        spaceAfter=12,
    ),
    "h1": ParagraphStyle(
        "h1",
        parent=_BASE,
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=19,
        spaceBefore=6,
        spaceAfter=10,
        textColor=ACENTO,
    ),
    "h2": ParagraphStyle(
        "h2",
        parent=_BASE,
        fontName="Helvetica-Bold",
        fontSize=11.5,
        leading=15,
        spaceBefore=10,
        spaceAfter=6,
    ),
    "h3": ParagraphStyle(
        "h3",
        parent=_BASE,
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=13,
        spaceBefore=8,
        spaceAfter=4,
    ),
    "titulo_tabla": ParagraphStyle(
        "titulo_tabla",
        parent=_BASE,
        fontName="Helvetica-Bold",
        fontSize=8.5,
        spaceBefore=6,
        spaceAfter=3,
    ),
    "celda": ParagraphStyle("celda", parent=_BASE, fontSize=8, leading=10),
    "celda_enc": ParagraphStyle(
        "celda_enc", parent=_BASE, fontName="Helvetica-Bold", fontSize=8, leading=10
    ),
    "portada_titulo": ParagraphStyle(
        "portada_titulo",
        parent=_BASE,
        fontName="Helvetica-Bold",
        fontSize=24,
        leading=30,
        textColor=ACENTO,
        spaceAfter=24,
    ),
    "indice1": ParagraphStyle(
        "indice1", parent=_BASE, fontName="Helvetica-Bold", leftIndent=0, spaceBefore=4
    ),
    "indice2": ParagraphStyle("indice2", parent=_BASE, fontSize=9, leftIndent=14),
}
_ALINEACION = {"izq": TA_LEFT, "centro": TA_CENTER, "der": TA_RIGHT}

_TRAZOS = {
    # estilo: (color de línea, grosor, color de relleno o None, guiones)
    "estructura": (TINTA, 1.3, None, None),
    "tenue": (TENUE, 0.8, None, None),
    "apoyo": (TINTA, 0.8, None, None),
    "positivo": (POSITIVO, 0.8, colors.Color(0.12, 0.37, 0.66, alpha=0.18), None),
    "negativo": (NEGATIVO, 0.8, colors.Color(0.75, 0.22, 0.17, alpha=0.18), None),
    "deformada": (DEFORMADA, 1.2, None, (3, 2)),
    "carga": (colors.HexColor("#2e8b57"), 0.9, None, None),
}


# --- Figuras -----------------------------------------------------------------------
class _FiguraPDF(Flowable):
    """Dibuja una :class:`Figura` escalada para entrar en ``ancho × alto``."""

    def __init__(self, figura: Figura, ancho: float, alto: float) -> None:
        super().__init__()
        self.figura = figura
        self.width, self.height = ancho, alto

    def wrap(self, *_):
        return self.width, self.height

    def draw(self) -> None:
        c = self.canv
        fig = self.figura
        c.setFont("Helvetica-Bold", 8.5)
        c.setFillColor(TINTA)
        c.drawCentredString(self.width / 2, self.height - 10, _plano(fig.titulo))
        xmin, ymin, xmax, ymax = fig.limites()
        margen = 16
        ancho, alto = self.width - 2 * margen, self.height - 2 * margen - 12
        dx, dy = max(xmax - xmin, 1e-9), max(ymax - ymin, 1e-9)
        escala = min(ancho / dx, alto / dy)
        ox = margen + (ancho - dx * escala) / 2 - xmin * escala
        oy = margen + (alto - dy * escala) / 2 - ymin * escala

        def a_papel(p):
            return ox + p[0] * escala, oy + p[1] * escala

        for t in fig.trazos:
            if len(t.puntos) < 2:
                continue
            linea, grosor, relleno, guiones = _TRAZOS.get(t.estilo, _TRAZOS["estructura"])
            c.setStrokeColor(linea)
            c.setLineWidth(grosor)
            c.setDash(*guiones) if guiones else c.setDash()
            camino = c.beginPath()
            camino.moveTo(*a_papel(t.puntos[0]))
            for p in t.puntos[1:]:
                camino.lineTo(*a_papel(p))
            if t.cerrado:
                camino.close()
            if t.relleno and relleno is not None:
                c.setFillColor(relleno)
                c.drawPath(camino, stroke=1, fill=1)
            else:
                c.drawPath(camino, stroke=1, fill=0)
        c.setDash()
        for r in fig.rotulos:
            x, y = a_papel((r.x, r.y))
            texto = _plano(r.texto)
            if r.estilo == "nudo":
                c.setFont("Helvetica-Bold", 7)
                c.setFillColor(ACENTO)
                c.drawString(x, y - 3, texto)
                continue
            fuente = ("Helvetica-Oblique", 7) if r.estilo == "barra" else ("Helvetica", 6.5)
            c.setFont(*fuente)
            ancho_t = c.stringWidth(texto, *fuente) + 3
            c.setFillColor(colors.white)
            c.setStrokeColor(colors.white)
            c.rect(x - ancho_t / 2, y - 4, ancho_t, 8.5, stroke=0, fill=1)
            c.setFillColor(TINTA if r.estilo == "barra" else _color_valor(texto))
            c.drawCentredString(x, y - 2, texto)


def _color_valor(texto: str):
    return NEGATIVO if texto.startswith("-") else POSITIVO


# --- Documento ---------------------------------------------------------------------
class _Documento(BaseDocTemplate):
    def __init__(self, ruta: str, memoria: Memoria) -> None:
        super().__init__(
            ruta,
            pagesize=A4,
            leftMargin=2 * cm,
            rightMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
            title=memoria.titulo,
            author=memoria.datos.get("Autor", ""),
            subject=memoria.datos.get("Proyecto", ""),
            creator="Nervi",
        )
        self.memoria = memoria
        marco = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="normal")
        self.addPageTemplates(
            [
                PageTemplate(id="portada", frames=[marco]),
                PageTemplate(id="cuerpo", frames=[marco], onPage=self._pie),
            ]
        )

    def _pie(self, c, doc) -> None:
        c.saveState()
        c.setFont("Helvetica", 7.5)
        c.setFillColor(TENUE)
        c.setStrokeColor(TENUE)
        c.setLineWidth(0.4)
        y = 1.3 * cm
        c.line(self.leftMargin, y + 9, self.leftMargin + self.width, y + 9)
        c.drawString(self.leftMargin, y, _plano(self.memoria.pie))
        c.drawRightString(self.leftMargin + self.width, y, f"Página {doc.page}")
        c.restoreState()

    def afterFlowable(self, flowable) -> None:
        nivel = getattr(flowable, "_nivel_indice", None)
        if nivel is not None:
            texto = flowable.getPlainText()
            clave = f"s{id(flowable)}"
            self.canv.bookmarkPage(clave)
            self.canv.addOutlineEntry(texto, clave, level=nivel)
            self.notify("TOCEntry", (nivel, texto, self.page, clave))


class _Armador:
    def __init__(self, ancho: float) -> None:
        self.ancho = ancho
        self.contador = [0, 0, 0]

    def encabezado(self, s: Capitulo) -> Paragraph:
        n = min(s.nivel, 3) - 1
        self.contador[n] += 1
        for k in range(n + 1, 3):
            self.contador[k] = 0
        numero = ".".join(str(v) for v in self.contador[: n + 1])
        p = Paragraph(f"{numero}. {_texto(s.titulo)}", ESTILOS[f"h{n + 1}"])
        if n < 2:
            p._nivel_indice = n  # entra en el índice
        return p

    def capitulo(self, s: Capitulo) -> list:
        salida: list = []
        if s.pagina_nueva:
            salida.append(PageBreak())
        else:
            salida.append(CondPageBreak(4 * cm))
        salida.append(self.encabezado(s))
        bloques = list(s.bloques)
        k = 0
        while k < len(bloques):
            b = bloques[k]
            if isinstance(b, Figura):
                grupo = [b]
                while (
                    b.grupo
                    and k + 1 < len(bloques)
                    and isinstance(bloques[k + 1], Figura)
                    and bloques[k + 1].grupo == b.grupo
                ):
                    k += 1
                    grupo.append(bloques[k])
                salida.append(self.figuras(grupo))
            elif isinstance(b, Capitulo):
                salida += self.capitulo(b)
            elif isinstance(b, Tabla):
                salida += self.tabla(b)
            elif isinstance(b, Parrafo):
                salida.append(Paragraph(_texto(b.texto), ESTILOS.get(b.estilo, ESTILOS["normal"])))
            k += 1
        return salida

    def figuras(self, figs: list[Figura]):
        if len(figs) == 1:
            return KeepTogether([_FiguraPDF(figs[0], self.ancho, 0.55 * self.ancho), Spacer(1, 6)])
        ancho = self.ancho / 2
        celdas = [_FiguraPDF(f, ancho - 4, 0.62 * ancho) for f in figs]
        if len(celdas) % 2:
            celdas.append(Spacer(1, 1))
        filas = [celdas[k : k + 2] for k in range(0, len(celdas), 2)]
        t = Table(filas, colWidths=[ancho, ancho])
        t.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.4, TENUE),
                    ("INNERGRID", (0, 0), (-1, -1), 0.4, TENUE),
                    ("LEFTPADDING", (0, 0), (-1, -1), 2),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ]
            )
        )
        return KeepTogether([t, Spacer(1, 8)])

    def tabla(self, t: Tabla) -> list:
        n = len(t.columnas)
        alin = t.alineacion or (["izq"] + ["der"] * (n - 1))
        estilos = []
        for a in alin:
            base, enc = ESTILOS["celda"], ESTILOS["celda_enc"]
            estilos.append(
                (
                    ParagraphStyle(f"c{a}", parent=base, alignment=_ALINEACION[a]),
                    ParagraphStyle(f"e{a}", parent=enc, alignment=_ALINEACION[a]),
                )
            )
        datos = [[Paragraph(_texto(c), estilos[k][1]) for k, c in enumerate(t.columnas)]]
        for fila in t.filas:
            datos.append([Paragraph(_texto(str(c)), estilos[k][0]) for k, c in enumerate(fila)])
        pesos = t.anchos or [1.0] * n
        anchos = [self.ancho * p / sum(pesos) for p in pesos]
        tabla = Table(datos, colWidths=anchos, repeatRows=1)
        tabla.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), FONDO_ENCABEZADO),
                    ("LINEBELOW", (0, 0), (-1, 0), 0.6, TINTA),
                    ("LINEBELOW", (0, 1), (-1, -1), 0.25, TENUE),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]
            )
        )
        salida: list = []
        if t.titulo:
            salida.append(Paragraph(_texto(t.titulo), ESTILOS["titulo_tabla"]))
        salida.append(tabla)
        if t.nota:
            salida.append(Paragraph(_texto(t.nota), ESTILOS["nota"]))
        salida.append(Spacer(1, 6))
        # Las tablas cortas no se parten entre páginas; las largas sí, repitiendo
        # el encabezado.
        return [KeepTogether(salida)] if len(t.filas) <= 25 else salida

    def portada(self, m: Memoria) -> list:
        salida: list = [Spacer(1, 3 * cm), Paragraph(_texto(m.titulo), ESTILOS["portada_titulo"])]
        if m.datos:
            filas = [
                [
                    Paragraph(f"<b>{_texto(k)}</b>", ESTILOS["normal"]),
                    Paragraph(_texto(str(v)), ESTILOS["normal"]),
                ]
                for k, v in m.datos.items()
            ]
            t = Table(filas, colWidths=[0.25 * self.ancho, 0.75 * self.ancho])
            t.setStyle(
                TableStyle(
                    [
                        ("LINEBELOW", (0, 0), (-1, -1), 0.3, TENUE),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ]
                )
            )
            salida += [t, Spacer(1, 1.2 * cm)]
        for aviso in m.avisos:
            if aviso:
                salida.append(Paragraph(_texto(aviso), ESTILOS["aviso"]))
        indice = TableOfContents()
        indice.levelStyles = [ESTILOS["indice1"], ESTILOS["indice2"]]
        salida += [
            Spacer(1, 1 * cm),
            Paragraph("Índice", ESTILOS["h2"]),
            indice,
        ]
        return salida


def escribir_pdf(memoria: Memoria, ruta: Path) -> Path:
    """Escribe ``memoria`` en ``ruta`` (formato A4) y devuelve la ruta."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    doc = _Documento(str(ruta), memoria)
    armador = _Armador(doc.width)
    historia: list = armador.portada(memoria)
    historia.append(NextPageTemplate("cuerpo"))
    for k, s in enumerate(memoria.capitulos):
        if k == 0:
            s = Capitulo(s.titulo, s.bloques, s.nivel, pagina_nueva=True)
        historia += armador.capitulo(s)
    doc.multiBuild(historia)
    return ruta
