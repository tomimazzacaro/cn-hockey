# src/reports/pdf_builder.py
"""
Generador de informes PDF — CN Hockey Performance Hub.

Arma un documento PDF propio (fondo blanco, pensado para papel), en vez de
"imprimir" la página de Streamlit tal cual se ve: Streamlit no está pensado
para paginación de impresión y corta gráficos y tablas a la mitad entre
hojas. Cada gráfico se exporta a PNG estático (Plotly + kaleido) y cada
sección (gráfico o tabla) va envuelta en KeepTogether junto a su título —
así reportlab nunca la parte entre dos páginas: si no entra en el resto de
la hoja actual, la manda entera a la siguiente.

Los gráficos del dashboard usan fondo oscuro (pensado para pantalla) y texto
de leyenda casi blanco — eso quedaría invisible sobre una página blanca, así
que se recolorean (clon del Figure, no se toca el original en pantalla)
antes de exportarlos.
"""
import io
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

NAVY       = colors.HexColor("#0f2b5b")
TEXTO_GRIS = colors.HexColor("#4b5563")
GRILLA     = colors.HexColor("#e5e7eb")
FILA_PAR   = colors.HexColor("#f3f4f6")

# Colores hex (no reportlab.Color) para recolorear los gráficos de Plotly.
_FIG_FONDO  = "white"
_FIG_TEXTO  = "#1f2937"
_FIG_GRILLA = "#e5e7eb"
_FIG_TITULO = "#0f2b5b"

ANCHO_UTIL_CM = 17.0  # A4 (21cm) menos 2cm de margen a cada lado

_hoja_estilos = getSampleStyleSheet()

ESTILO_TITULO = ParagraphStyle(
    "TituloInforme", parent=_hoja_estilos["Title"],
    textColor=NAVY, fontSize=20, spaceAfter=2,
)
ESTILO_SUBTITULO = ParagraphStyle(
    "SubtituloInforme", parent=_hoja_estilos["Normal"],
    textColor=TEXTO_GRIS, fontName="Helvetica-Oblique", fontSize=10, spaceAfter=4,
)
ESTILO_FECHA = ParagraphStyle(
    "FechaInforme", parent=_hoja_estilos["Normal"],
    textColor=TEXTO_GRIS, fontSize=8, spaceAfter=14,
)
ESTILO_SECCION = ParagraphStyle(
    "SeccionInforme", parent=_hoja_estilos["Heading2"],
    textColor=NAVY, fontSize=13, spaceBefore=4, spaceAfter=8,
)


@dataclass
class SeccionFigura:
    """Una sección del informe con un gráfico de Plotly."""
    titulo: str
    figura: go.Figure
    alto_cm: float = 8.5


@dataclass
class SeccionTabla:
    """
    Una sección del informe con una tabla.

    `df` debe venir ya formateado para mostrar (valores como strings listos
    para leer, columnas ya renombradas a su encabezado final) — el builder
    no adivina formato numérico ni de fecha, solo dibuja lo que recibe.
    """
    titulo: str
    df: pd.DataFrame


@dataclass
class SeccionFotos:
    """
    Una fila de una o más fotos de jugadora, cada una con su nombre debajo
    (mismo uso que compare_card_html/foto_jugadora_path en pantalla — una
    sola foto para el perfil individual, dos para una comparativa A/B).

    `fotos` es una lista de (nombre, ruta_o_None) — None o una ruta que no
    existe cae en un placeholder de texto, nunca revienta el informe.
    """
    titulo: str
    fotos: list[tuple[str, Path | str | None]]
    lado_cm: float = 5.0


def _eje_x_es_fecha(fig: go.Figure) -> bool:
    """
    Detecta si el eje X de algún trace trae valores de fecha/datetime.

    calcular_acwr() deja "fecha" como datetime.date plano (no Timestamp ni
    datetime64) — isinstance(x, date) alcanza para los tres casos, porque
    tanto datetime.datetime como pd.Timestamp son subclases de date.
    """
    for trace in fig.data:
        x = getattr(trace, "x", None)
        if x is None or len(x) == 0:
            continue
        if isinstance(x[0], date):
            return True
        if pd.api.types.is_datetime64_any_dtype(pd.Series(x)):
            return True
    return False


def _recolorear_para_impresion(fig: go.Figure) -> go.Figure:
    """Clona el Figure y lo recolorea para fondo blanco antes de exportar."""
    fig = go.Figure(fig)
    fig.update_layout(
        plot_bgcolor=_FIG_FONDO, paper_bgcolor=_FIG_FONDO,
        font=dict(color=_FIG_TEXTO),
        legend=dict(font=dict(color=_FIG_TEXTO), bgcolor="rgba(0,0,0,0)"),
        # Piso mínimo de margen — algunas páginas usan layouts con margin
        # casi cero (pensados para un contenedor responsive en pantalla, no
        # para una imagen de ancho fijo). automargin abajo lo expande más
        # si hace falta (títulos de eje, nombres largos de jugadoras, texto
        # "outside" de las barras) — un margen fijo único rompía siempre
        # alguno de los dos casos (o pisaba el título del eje Y en gráficos
        # de línea, o cortaba los nombres/valores en gráficos de barra).
        margin=dict(l=40, r=40, t=40, b=40),
    )
    if fig.layout.title and fig.layout.title.text:
        fig.update_layout(title=dict(font=dict(color=_FIG_TITULO, size=14)))
    fig.update_xaxes(gridcolor=_FIG_GRILLA, zerolinecolor=_FIG_GRILLA,
                      color=_FIG_TEXTO, linecolor="#9ca3af", automargin=True)
    fig.update_yaxes(gridcolor=_FIG_GRILLA, zerolinecolor=_FIG_GRILLA,
                      color=_FIG_TEXTO, linecolor="#9ca3af", automargin=True)
    # Las etiquetas de valor "outside" de las barras (ej. "7.027 m" al final
    # de cada barra) fijan su propio textfont color en el código de cada
    # página (CHART_FONT, casi blanco — pensado para fondo oscuro). Ese
    # color por-trace no lo pisa el font.color global de arriba, así que
    # sin esto quedaban casi invisibles sobre una página blanca.
    fig.update_traces(textfont=dict(color=_FIG_TEXTO))
    # Los gráficos de radar (Scatterpolar) no tienen xaxis/yaxis cartesianos
    # — su fondo y grilla viven en layout.polar, que el update_xaxes/yaxes de
    # arriba no toca. Sin esto, el área del radar quedaba oscura sobre una
    # página blanca. Es inofensivo pisarlo en gráficos sin polar (no hay
    # nada que recolorear ahí).
    fig.update_layout(polar=dict(
        bgcolor=_FIG_FONDO,
        radialaxis=dict(gridcolor=_FIG_GRILLA, color=_FIG_TEXTO),
        angularaxis=dict(gridcolor=_FIG_GRILLA, color=_FIG_TEXTO),
    ))
    if _eje_x_es_fecha(fig):
        # Con una sola fecha seleccionada, el rango del eje queda "de ancho
        # cero" y el auto-formato de fecha de Plotly se rompe, mostrando
        # horas con nanosegundos en vez de la fecha — forzar el formato
        # evita ese caso degenerado sin importar cuántas fechas únicas haya.
        fig.update_xaxes(tickformat="%d/%m/%Y")
    return fig


def _figura_a_imagen(fig: go.Figure, alto_cm: float) -> Image:
    """Exporta el Figure a PNG estático (kaleido) y lo devuelve como Image
    de reportlab, ya escalado al ancho útil de la página."""
    fig_clara = _recolorear_para_impresion(fig)
    ancho_px = 1400
    alto_px = int(ancho_px * (alto_cm / ANCHO_UTIL_CM))
    png_bytes = fig_clara.to_image(format="png", width=ancho_px, height=alto_px, scale=2)
    return Image(io.BytesIO(png_bytes), width=ANCHO_UTIL_CM * cm, height=alto_cm * cm)


def _tabla_kpis(kpis: list[tuple[str, str]]) -> Table:
    """KPIs en una fila: label chico arriba, valor grande en negrita abajo —
    imitando las tarjetas de KPI de la app (kpi_row en src/ui/components.py)."""
    # Con más columnas cada una tiene menos ancho — bajar el tamaño evita
    # que un valor como "16/07/2026" se corte a la mitad en dos líneas.
    tam_valor = 14 if len(kpis) <= 4 else 11 if len(kpis) <= 6 else 9
    labels = [
        Paragraph(f'<font size=7 color="#6b7280">{label.upper()}</font>', _hoja_estilos["Normal"])
        for label, _ in kpis
    ]
    valores = [
        Paragraph(f'<font size={tam_valor} color="#0f2b5b"><b>{valor}</b></font>', _hoja_estilos["Normal"])
        for _, valor in kpis
    ]
    ancho_col = ANCHO_UTIL_CM * cm / len(kpis)
    tabla = Table([labels, valores], colWidths=[ancho_col] * len(kpis))
    tabla.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND", (0, 0), (-1, -1), FILA_PAR),
        ("BOX", (0, 0), (-1, -1), 0.5, GRILLA),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, GRILLA),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return tabla


_ESTILO_CELDA_ENCABEZADO = ParagraphStyle(
    "CeldaEncabezado", parent=_hoja_estilos["Normal"],
    fontSize=8, leading=10, alignment=1, textColor=colors.white, fontName="Helvetica-Bold",
)
_ESTILO_CELDA_CUERPO = ParagraphStyle(
    "CeldaCuerpo", parent=_hoja_estilos["Normal"], fontSize=8, leading=10, alignment=1,
)


def _df_a_tabla(df: pd.DataFrame) -> Table:
    """
    DataFrame (ya formateado) a Table de reportlab, con encabezado que se
    repite si la tabla ocupa más de una página (repeatRows=1).

    Cada celda va envuelta en un Paragraph (no un string plano): un string
    plano no hace word-wrap dentro de su columna y un valor largo (ej. el
    texto libre de una molestia reportada) se desborda visualmente encima
    de la columna de al lado en vez de bajar de línea.
    """
    encabezados = [Paragraph(str(c), _ESTILO_CELDA_ENCABEZADO) for c in df.columns]
    filas = [
        [Paragraph(str(v), _ESTILO_CELDA_CUERPO) for v in fila]
        for fila in df.astype(str).values.tolist()
    ]
    datos = [encabezados] + filas

    ancho_col = ANCHO_UTIL_CM * cm / len(df.columns)
    tabla = Table(datos, colWidths=[ancho_col] * len(df.columns), repeatRows=1)

    estilo = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.4, GRILLA),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    for i in range(1, len(datos)):
        if i % 2 == 0:
            estilo.append(("BACKGROUND", (0, i), (-1, i), FILA_PAR))
    tabla.setStyle(TableStyle(estilo))
    return tabla


def _foto_cuadrada_buffer(ruta: Path, tam_px: int = 400) -> io.BytesIO | None:
    """
    Recorta la foto a un cuadrado centrado y la devuelve como buffer JPEG
    en memoria — mismo criterio que .cn-cmp-avatar-foto en pantalla
    (object-fit: cover), para que una foto no cuadrada no salga estirada
    ni deforme el layout de la fila de fotos.
    """
    try:
        img = PILImage.open(ruta).convert("RGB")
    except Exception:
        return None
    ancho, alto = img.size
    lado = min(ancho, alto)
    izq, arriba = (ancho - lado) // 2, (alto - lado) // 2
    img = img.crop((izq, arriba, izq + lado, arriba + lado)).resize((tam_px, tam_px))
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=85)
    buffer.seek(0)
    return buffer


def _fotos_a_tabla(fotos: list[tuple[str, Path | str | None]], lado_cm: float) -> Table:
    """Fila de fotos cuadradas con el nombre debajo de cada una."""
    ancho_col = ANCHO_UTIL_CM * cm / len(fotos)
    lado_img = min(lado_cm * cm, ancho_col - 0.6 * cm)

    celdas_img, celdas_nombre = [], []
    for nombre, ruta in fotos:
        buffer = _foto_cuadrada_buffer(Path(ruta)) if ruta and Path(ruta).exists() else None
        if buffer:
            img = Image(buffer, width=lado_img, height=lado_img)
            img.hAlign = "CENTER"
            celdas_img.append(img)
        else:
            celdas_img.append(Paragraph("(sin foto)", _ESTILO_CELDA_CUERPO))
        celdas_nombre.append(Paragraph(f"<b>{nombre}</b>", _ESTILO_CELDA_CUERPO))

    tabla = Table([celdas_img, celdas_nombre], colWidths=[ancho_col] * len(fotos))
    tabla.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
    ]))
    return tabla


def _pie_pagina(canvas, doc) -> None:
    """Pie de página con marca y número de página, en todas las hojas."""
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(TEXTO_GRIS)
    canvas.drawString(2 * cm, 1 * cm, "Centro Naval Hockey — Performance Hub")
    canvas.drawRightString(A4[0] - 2 * cm, 1 * cm, f"Página {doc.page}")
    canvas.restoreState()


def generar_pdf_reporte(
    titulo: str,
    subtitulo: str,
    secciones: list[SeccionFigura | SeccionTabla | SeccionFotos],
    kpis: list[tuple[str, str]] | None = None,
) -> bytes:
    """
    Arma el informe PDF y devuelve sus bytes, listos para pasar directo a
    st.download_button(data=...).
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=1.8 * cm, bottomMargin=1.6 * cm,
        leftMargin=2 * cm, rightMargin=2 * cm,
    )

    story = [Paragraph(titulo, ESTILO_TITULO)]
    if subtitulo:
        story.append(Paragraph(subtitulo, ESTILO_SUBTITULO))
    story.append(Paragraph(datetime.now().strftime("Generado el %d/%m/%Y a las %H:%M"), ESTILO_FECHA))

    if kpis:
        story.append(_tabla_kpis(kpis))
        story.append(Spacer(1, 16))

    for seccion in secciones:
        bloque = [Paragraph(seccion.titulo, ESTILO_SECCION)]
        if isinstance(seccion, SeccionFigura):
            bloque.append(_figura_a_imagen(seccion.figura, seccion.alto_cm))
        elif isinstance(seccion, SeccionTabla):
            if seccion.df.empty:
                bloque.append(Paragraph("Sin datos para mostrar.", _hoja_estilos["Normal"]))
            else:
                bloque.append(_df_a_tabla(seccion.df))
        elif isinstance(seccion, SeccionFotos):
            bloque.append(_fotos_a_tabla(seccion.fotos, seccion.lado_cm))
        story.append(KeepTogether(bloque))
        story.append(Spacer(1, 14))

    doc.build(story, onFirstPage=_pie_pagina, onLaterPages=_pie_pagina)
    return buffer.getvalue()
