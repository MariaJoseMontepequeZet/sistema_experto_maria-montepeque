"""
Informe de diagnóstico en PDF, con la marca del taller.

Igual que la API, solo presenta: el diagnóstico, la evidencia y el razonamiento los calcula el motor.
Requiere `reportlab` (pip install -r requirements-api.txt); el motor y la consola no lo necesitan.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import date
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    Flowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .modelo import BaseDeConocimiento, Valor, porcentaje
from .motor import Diagnostico, Inferencia

MARGEN = 18 * mm
ANCHO_UTIL = A4[0] - 2 * MARGEN
GRIS = colors.HexColor("#5b6470")
GRIS_CLARO = colors.HexColor("#eef0f3")
AMBAR = colors.HexColor("#fff4d6")
AMBAR_BORDE = colors.HexColor("#e0a800")
ALTO_LOGO = 14 * mm


@dataclass(frozen=True)
class Marca:
    """Identidad del taller que aparece en el encabezado del informe."""
    nombre: str = "Informe de diagnóstico"
    color: str = "#1f4e79"
    contacto: str = ""
    logo: bytes | None = None      # PNG o JPG

    def __post_init__(self) -> None:
        colors.HexColor(self.color)              # ValueError si no es un color válido
        if self.logo is not None:
            ImageReader(io.BytesIO(self.logo)).getSize()   # lanza si no es una imagen legible


@dataclass(frozen=True)
class DatosServicio:
    """Datos del servicio que el taller escribe a mano."""
    cliente: str = ""
    equipo: str = ""
    tecnico: str = ""
    observaciones: str = ""


def limpiar(valor: object) -> str:
    """Reemplaza lo que la tipografía estándar del PDF no puede dibujar (para texto directo en el lienzo)."""
    limpio = str(valor).replace("≥", ">=").replace("≤", "<=")
    return limpio.encode("cp1252", "replace").decode("cp1252")


def texto(valor: object) -> str:
    """Igual que `limpiar`, y además escapa el marcado que interpretan los párrafos de reportlab."""
    return escape(limpiar(valor))


class _Barra(Flowable):
    """Barra horizontal de certeza."""

    def __init__(self, certeza: float, ancho: float, color: colors.Color) -> None:
        super().__init__()
        self.certeza, self.ancho, self.color = max(0.0, min(1.0, certeza)), ancho, color
        self.width, self.height = ancho, 4 * mm

    def draw(self) -> None:
        self.canv.setFillColor(GRIS_CLARO)
        self.canv.roundRect(0, 0, self.ancho, self.height, 1.5 * mm, stroke=0, fill=1)
        if self.certeza > 0:
            self.canv.setFillColor(self.color)
            self.canv.roundRect(0, 0, self.ancho * self.certeza, self.height, 1.5 * mm, stroke=0, fill=1)


class _LienzoNumerado(canvas.Canvas):
    """Pone 'Página x de y' y el aviso legal al pie (el total solo se conoce al final)."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._paginas: list[dict] = []

    def showPage(self) -> None:
        self._paginas.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        total = len(self._paginas)
        for estado in self._paginas:
            self.__dict__.update(estado)
            self._pie(total)
            super().showPage()
        super().save()

    def _pie(self, total: int) -> None:
        self.setStrokeColor(GRIS_CLARO)
        self.line(MARGEN, 17 * mm, A4[0] - MARGEN, 17 * mm)
        self.setFillColor(GRIS)
        self.setFont("Helvetica", 7)
        self.drawString(MARGEN, 12 * mm, limpiar("Este informe orienta, no reemplaza a un técnico. "
                                               "Apaga y desconecta el equipo antes de abrirlo."))
        self.drawRightString(A4[0] - MARGEN, 12 * mm, f"Página {self._pageNumber} de {total}")


def generar_pdf(base: BaseDeConocimiento, respuestas: dict[str, Valor], inferencia: Inferencia,
                marca: Marca | None = None, servicio: DatosServicio | None = None,
                hoy: date | None = None, comprimir: bool = True) -> bytes:
    """Arma el informe PDF de una consulta terminada y lo devuelve como bytes."""
    marca = marca or Marca()
    servicio = servicio or DatosServicio()
    hoy = hoy or date.today()
    color = colors.HexColor(marca.color)

    estilos = getSampleStyleSheet()
    normal = ParagraphStyle("normal", parent=estilos["Normal"], fontSize=9.5, leading=13, alignment=TA_LEFT)
    pequeno = ParagraphStyle("pequeno", parent=normal, fontSize=8.5, leading=11, textColor=GRIS)
    titulo = ParagraphStyle("titulo", parent=normal, fontName="Helvetica-Bold", fontSize=12.5, leading=16,
                            textColor=color, spaceBefore=10, spaceAfter=4)
    principal_estilo = ParagraphStyle("principal", parent=normal, fontName="Helvetica-Bold", fontSize=15,
                                      leading=19)

    def encabezado(lienzo: canvas.Canvas, _doc) -> None:
        lienzo.saveState()
        lienzo.setFillColor(color)
        lienzo.rect(0, A4[1] - 28 * mm, A4[0], 28 * mm, stroke=0, fill=1)
        x = MARGEN
        if marca.logo:
            logo = ImageReader(io.BytesIO(marca.logo))
            ancho, alto = logo.getSize()
            lienzo.drawImage(logo, x, A4[1] - 21 * mm, width=ALTO_LOGO * ancho / alto, height=ALTO_LOGO,
                             mask="auto")
            x += ALTO_LOGO * ancho / alto + 4 * mm
        lienzo.setFillColor(colors.white)
        lienzo.setFont("Helvetica-Bold", 16)
        lienzo.drawString(x, A4[1] - 13 * mm, limpiar(marca.nombre))
        if marca.contacto:
            lienzo.setFont("Helvetica", 8.5)
            lienzo.drawString(x, A4[1] - 19 * mm, limpiar(marca.contacto))
        lienzo.setFont("Helvetica-Bold", 10)
        lienzo.drawRightString(A4[0] - MARGEN, A4[1] - 13 * mm, "Informe de diagnóstico")
        lienzo.setFont("Helvetica", 8.5)
        lienzo.drawRightString(A4[0] - MARGEN, A4[1] - 19 * mm, hoy.strftime("%d/%m/%Y"))
        lienzo.restoreState()

    historia: list = [Spacer(1, 4 * mm)]

    datos = [(etiqueta, valor) for etiqueta, valor in (
        ("Cliente", servicio.cliente), ("Equipo", servicio.equipo),
        ("Técnico", servicio.tecnico), ("Observaciones", servicio.observaciones)) if valor]
    if datos:
        tabla = Table([[Paragraph(f"<b>{texto(e)}</b>", pequeno), Paragraph(texto(v), normal)]
                       for e, v in datos], colWidths=[28 * mm, ANCHO_UTIL - 28 * mm])
        tabla.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                                   ("LINEBELOW", (0, 0), (-1, -1), 0.4, GRIS_CLARO),
                                   ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                                   ("TOPPADDING", (0, 0), (-1, -1), 3)]))
        historia += [Paragraph("Datos del servicio", titulo), tabla]

    diagnosticos = inferencia.diagnosticos
    historia.append(Paragraph("Diagnóstico", titulo))
    if not diagnosticos:
        historia.append(Paragraph(
            "No se llegó a ningún diagnóstico con suficiente certeza con las respuestas dadas. "
            "Se recomienda una revisión presencial.", normal))
    else:
        principal, *otros = diagnosticos
        historia += _bloque_principal(principal, principal_estilo, normal, color)

        if otros:
            historia.append(Paragraph("Otros diagnósticos posibles", titulo))
            filas = [[Paragraph(f"{texto(dg.descripcion)}", normal),
                      _Barra(dg.certeza, 45 * mm, GRIS),
                      Paragraph(porcentaje(dg.certeza), normal)] for dg in otros]
            tabla = Table(filas, colWidths=[ANCHO_UTIL - 62 * mm, 50 * mm, 12 * mm])
            tabla.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                       ("LINEBELOW", (0, 0), (-1, -1), 0.4, GRIS_CLARO)]))
            historia.append(tabla)

    if inferencia.descartados:
        historia.append(Paragraph("Descartados por evidencia en contra", titulo))
        for dg in inferencia.descartados:
            motivos = "; ".join(d.regla.descripcion for d in dg.en_contra)
            historia.append(Paragraph(f"• <b>{texto(dg.descripcion)}</b>: {texto(motivos)}.", normal))

    if respuestas:
        filas = [[Paragraph(texto(base.preguntas[h]), pequeno),
                  Paragraph(f"<b>{texto(base.formatear(h, v))}</b>", normal)] for h, v in respuestas.items()]
        tabla = Table(filas, colWidths=[ANCHO_UTIL * 0.68, ANCHO_UTIL * 0.32], repeatRows=0)
        tabla.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                                   ("LINEBELOW", (0, 0), (-1, -1), 0.4, GRIS_CLARO),
                                   ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                                   ("TOPPADDING", (0, 0), (-1, -1), 3)]))
        historia += [Paragraph("Lo que se comprobó en el equipo", titulo), tabla]

    if diagnosticos:
        pasos = inferencia.justificacion(diagnosticos[0].hecho)
        historia.append(Paragraph("Por qué el sistema llegó a este diagnóstico", titulo))
        for d in pasos:
            condiciones = " y ".join(f"{h} = {base.describir(h, c)}" for h, c in d.regla.condiciones.items())
            historia.append(Paragraph(
                f"<b>{texto(d.regla.id)} · {texto(d.regla.descripcion)}</b> ({d.certeza * 100:.0f} %)<br/>"
                f"<font color='#5b6470'>Si {texto(condiciones)}.</font>", normal))
            historia.append(Spacer(1, 1.5 * mm))

    memoria = io.BytesIO()
    SimpleDocTemplate(
        memoria, pagesize=A4, leftMargin=MARGEN, rightMargin=MARGEN, topMargin=32 * mm, bottomMargin=22 * mm,
        title=f"Informe de diagnóstico - {servicio.equipo or 'equipo'}", author=marca.nombre,
        pageCompression=1 if comprimir else 0,
    ).build(historia, onFirstPage=encabezado, onLaterPages=encabezado, canvasmaker=_LienzoNumerado)
    return memoria.getvalue()


def _bloque_principal(dg: Diagnostico, estilo: ParagraphStyle, normal: ParagraphStyle,
                      color: colors.Color) -> list:
    contenido: list = [
        Paragraph(texto(dg.descripcion), estilo),
        Spacer(1, 2 * mm),
        Table([[_Barra(dg.certeza, 70 * mm, color),
                Paragraph(f"Certeza <b>{porcentaje(dg.certeza)}</b>", normal)]],
              colWidths=[75 * mm, 40 * mm], style=[("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                                   ("LEFTPADDING", (0, 0), (0, 0), 0)], hAlign="LEFT"),
    ]
    if dg.recomendaciones:
        contenido.append(Spacer(1, 2 * mm))
        contenido += [Paragraph(f"• {texto(rec)}", normal) for rec in dg.recomendaciones]
    bloque: list = [KeepTogether(contenido)]
    for adv in dg.advertencias:
        aviso = Table([[Paragraph(f"<b>Atención:</b> {texto(adv)}", normal)]], colWidths=[ANCHO_UTIL])
        aviso.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), AMBAR),
                                   ("LINEBEFORE", (0, 0), (0, -1), 2, AMBAR_BORDE),
                                   ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 5),
                                   ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
        bloque += [Spacer(1, 3 * mm), aviso]
    return bloque
