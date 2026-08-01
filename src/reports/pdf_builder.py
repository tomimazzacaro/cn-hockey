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

from settings import ZSCORE_ALERTA

NAVY       = colors.HexColor("#0f2b5b")
TEXTO_GRIS = colors.HexColor("#4b5563")
GRILLA     = colors.HexColor("#e5e7eb")
FILA_PAR   = colors.HexColor("#f3f4f6")

# Versión clara (fondo blanco) del semáforo PARAMETRO_CFG de src/ui/theme.py —
# esa paleta está pensada para fondo oscuro de pantalla (bg casi negro, texto
# saturado), sobre papel blanco queda invisible o ilegible. Mismo hue por
# estado (celeste/verde/rojo) para que se reconozca como "el mismo semáforo"
# entre pantalla y PDF, solo que con el bg claro y el texto oscurecido para
# tener contraste sobre blanco — mismo criterio que _recolorear_para_impresion
# ya aplica a los gráficos de Plotly.
_ESTADO_PDF_CFG = {
    "Por debajo": {"texto": "#0369a1", "bg": colors.HexColor("#e0f2fe")},
    "En rango":   {"texto": "#15803d", "bg": colors.HexColor("#dcfce7")},
    "Por encima": {"texto": "#b91c1c", "bg": colors.HexColor("#fee2e2")},
    "Sin dato":   {"texto": "#6b7280", "bg": colors.HexColor("#f3f4f6")},
}

# Colores hex (no reportlab.Color) para recolorear los gráficos de Plotly.
_FIG_FONDO  = "white"
_FIG_TEXTO  = "#1f2937"
_FIG_GRILLA = "#e5e7eb"
_FIG_TITULO = "#0f2b5b"

# Tamaños de fuente para impresión — bastante más grandes que el default de
# Plotly (~12, el que usan los layouts de src/ui/charts.py pensados para
# pantalla). El "size" de Plotly son px CSS (96 por pulgada); _figura_a_imagen
# exporta siempre a un ancho fijo de 1400px representando los 17cm útiles de
# la página (ANCHO_UTIL_CM), o sea ~209 px/pulgada — más del doble de la
# densidad que Plotly asume al calcular tamaños de fuente. Un "size" pensado
# para pantalla queda chico en el PDF aunque se vea nítido (más resolución no
# es lo mismo que más tamaño) — por eso estos valores están escalados por
# ese mismo factor (~209/96 ≈ 2.18) contra un tamaño de pantalla razonable,
# no elegidos "a ojo".
_FIG_TICK_SIZE       = 26  # ticks de eje y texto general (leyenda, etc.) — ~9pt impreso
_FIG_TITULO_EJE_SIZE = 30  # título de cada eje (ej. "Distancia (m)") — ~10pt impreso
_FIG_VALOR_SIZE      = 26  # etiquetas de valor sobre cada barra (texttemplate) — ~9pt impreso

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


@dataclass
class SeccionAsistente:
    """
    Grilla de cumplimiento del Asistente de Parámetros (mismo dato largo que
    consume tabla_asistente_html() en pantalla: columnas [etiqueta, metrica,
    valor_real, estado]) — se pivotea y se pinta acá con el mismo semáforo de
    color que la tabla HTML, en vez del texto plano "valor (estado)" que se
    usaba antes.
    """
    titulo: str
    df_evaluacion: pd.DataFrame
    etiqueta_header: str = "Jugadora"


@dataclass
class SeccionAnalisis:
    """
    Fortalezas/debilidades del Asistente — mismo dict que devuelve
    generar_analisis() (src/metrics/analisis.py) y consume
    analisis_asistente_html() en pantalla. Se dibuja como chips de fortaleza
    + tarjetas de debilidad con borde de color, en vez de la tabla plana
    "Jugadora/Estado/Detalle" que se usaba antes.
    """
    titulo: str
    analisis: dict


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
        font=dict(color=_FIG_TEXTO, size=_FIG_TICK_SIZE),
        legend=dict(font=dict(color=_FIG_TEXTO, size=_FIG_TICK_SIZE), bgcolor="rgba(0,0,0,0)"),
        # Piso mínimo de margen — algunas páginas usan layouts con margin
        # casi cero (pensados para un contenedor responsive en pantalla, no
        # para una imagen de ancho fijo). automargin abajo lo expande más
        # si hace falta (títulos de eje, nombres largos de jugadoras) — pero
        # NO cubre el texto "outside" de las barras (texttemplate/textposition
        # en el trace, no un elemento de eje): con los tamaños de fuente más
        # grandes de _FIG_*_SIZE ese texto queda más ancho, y un piso de 40
        # (pensado para el font default ~12) lo cortaba contra el borde
        # derecho — de ahí el r más generoso.
        margin=dict(l=110, r=140, t=60, b=90),
    )
    if fig.layout.title and fig.layout.title.text:
        fig.update_layout(title=dict(font=dict(color=_FIG_TITULO, size=14)))
    # standoff separa el título del eje de los ticks — sin esto, el título
    # del eje Y (rotado 90°) queda pegado o superpuesto contra las etiquetas
    # de tick más largas (ej. "Cami Diaz") apenas el título usa una fuente
    # más grande que la pensada para pantalla.
    fig.update_xaxes(gridcolor=_FIG_GRILLA, zerolinecolor=_FIG_GRILLA,
                      color=_FIG_TEXTO, linecolor="#9ca3af", automargin=True,
                      tickfont=dict(size=_FIG_TICK_SIZE),
                      title=dict(font=dict(size=_FIG_TITULO_EJE_SIZE), standoff=20))
    fig.update_yaxes(gridcolor=_FIG_GRILLA, zerolinecolor=_FIG_GRILLA,
                      color=_FIG_TEXTO, linecolor="#9ca3af", automargin=True,
                      tickfont=dict(size=_FIG_TICK_SIZE),
                      title=dict(font=dict(size=_FIG_TITULO_EJE_SIZE), standoff=20))
    # Las etiquetas de valor "outside" de las barras (ej. "7.027 m" al final
    # de cada barra) fijan su propio textfont color en el código de cada
    # página (CHART_FONT, casi blanco — pensado para fondo oscuro), sin
    # tamaño explícito (hereda el font.size global, chico en pantalla). Ese
    # color/tamaño por-trace no lo pisa el font global de arriba, así que
    # sin esto quedaban casi invisibles y chicos sobre una página blanca.
    fig.update_traces(textfont=dict(color=_FIG_TEXTO, size=_FIG_VALOR_SIZE))
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


def _tabla_semaforo(df_evaluacion: pd.DataFrame, etiqueta_header: str) -> Table:
    """
    Pivotea la evaluación larga (etiqueta, metrica, valor_real, estado) a una
    grilla etiqueta × métrica, con cada celda pintada según el semáforo de
    _ESTADO_PDF_CFG — la versión imprimible de tabla_asistente_html().
    """
    metricas = list(dict.fromkeys(df_evaluacion["metrica"]))
    encabezados = [Paragraph(etiqueta_header, _ESTILO_CELDA_ENCABEZADO)]
    encabezados += [Paragraph(str(m), _ESTILO_CELDA_ENCABEZADO) for m in metricas]
    datos = [encabezados]
    comandos_bg = []

    for fila_idx, (etiqueta, grupo) in enumerate(df_evaluacion.groupby("etiqueta", sort=False), start=1):
        fila_por_metrica = grupo.set_index("metrica")
        fila = [Paragraph(f"<b>{etiqueta}</b>", _ESTILO_CELDA_CUERPO)]
        for col_idx, m in enumerate(metricas, start=1):
            if m not in fila_por_metrica.index:
                fila.append(Paragraph("—", _ESTILO_CELDA_CUERPO))
                continue
            r = fila_por_metrica.loc[m]
            if isinstance(r, pd.DataFrame):
                # Misma colisión de etiqueta que tabla_asistente_html() ya
                # protege en pantalla — quedarse con la primera fila en vez
                # de romper el informe.
                r = r.iloc[0]
            cfg = _ESTADO_PDF_CFG.get(r["estado"], _ESTADO_PDF_CFG["Sin dato"])
            valor_str = f"{r['valor_real']:.0f}" if pd.notna(r["valor_real"]) else "—"
            fila.append(Paragraph(
                f'<font color="{cfg["texto"]}"><b>{valor_str}</b></font>', _ESTILO_CELDA_CUERPO,
            ))
            comandos_bg.append(("BACKGROUND", (col_idx, fila_idx), (col_idx, fila_idx), cfg["bg"]))
        datos.append(fila)

    ancho_col = ANCHO_UTIL_CM * cm / len(datos[0])
    tabla = Table(datos, colWidths=[ancho_col] * len(datos[0]), repeatRows=1)
    estilo = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.4, GRILLA),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ] + comandos_bg
    tabla.setStyle(TableStyle(estilo))
    return tabla


def _chips(nombres: list[str], texto_hex: str, bg: colors.Color, por_fila: int = 4) -> Table:
    """Fila(s) de chips de color parejo — usado para las fortalezas del
    Análisis (mismo lenguaje visual que .cn-acwr-badge en pantalla)."""
    filas = [nombres[i:i + por_fila] for i in range(0, len(nombres), por_fila)]
    ancho_col = ANCHO_UTIL_CM * cm / por_fila
    datos = []
    for fila in filas:
        celdas = [Paragraph(f'<font color="{texto_hex}"><b>{n}</b></font>', _ESTILO_CELDA_CUERPO)
                  for n in fila]
        celdas += [""] * (por_fila - len(fila))
        datos.append(celdas)

    tabla = Table(datos, colWidths=[ancho_col] * por_fila)
    estilo = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]
    for r, fila in enumerate(filas):
        for c in range(len(fila)):
            estilo.append(("BACKGROUND", (c, r), (c, r), bg))
    tabla.setStyle(TableStyle(estilo))
    return tabla


def _marca_atipica(m: dict) -> str:
    """Sufijo "(z=X.X)" cuando la métrica es atípica contra el propio
    historial de la jugadora — versión texto del ⚡ con tooltip que usa
    analisis_asistente_html() en pantalla (un PDF estático no tiene tooltip)."""
    z = m.get("z_score")
    if pd.isna(z):
        return ""
    return f" (z={z:.1f})" if abs(z) >= ZSCORE_ALERTA else ""


def _badges_metricas(metricas: list[dict], por_fila: int = 3) -> Table:
    """Grilla de badges "Métrica: valor" coloreados por estado — la versión
    imprimible de los .cn-acwr-badge de cada tarjeta de debilidad."""
    filas = [metricas[i:i + por_fila] for i in range(0, len(metricas), por_fila)]
    ancho_col = (ANCHO_UTIL_CM * cm - 1.6 * cm) / por_fila
    datos = []
    comandos_bg = []
    for r, fila in enumerate(filas):
        celdas = []
        for c, m in enumerate(fila):
            cfg = _ESTADO_PDF_CFG.get(m["estado"], _ESTADO_PDF_CFG["Sin dato"])
            valor = f"{m['valor_real']:.0f}" if pd.notna(m["valor_real"]) else "—"
            celdas.append(Paragraph(
                f'<font color="{cfg["texto"]}" size=7><b>{m["metrica"]}: {valor}</b>'
                f'{_marca_atipica(m)}</font>',
                _hoja_estilos["Normal"],
            ))
            comandos_bg.append(("BACKGROUND", (c, r), (c, r), cfg["bg"]))
        celdas += [""] * (por_fila - len(fila))
        datos.append(celdas)

    tabla = Table(datos, colWidths=[ancho_col] * por_fila)
    tabla.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ] + comandos_bg))
    return tabla


def _tarjeta_debilidad(d: dict) -> Table:
    """Una tarjeta de debilidad: borde izquierdo de color según peor_estado,
    nombre + posición, badges de métricas y recomendaciones — mismo
    contenido que .cn-analisis-card en pantalla, envuelta en una Table de
    una celda para poder dibujarle el borde de acento con LINEBEFORE."""
    accent = colors.HexColor(_ESTADO_PDF_CFG[d["peor_estado"]]["texto"])
    contenido = [
        Paragraph(f'<font color="#0f2b5b" size=11><b>{d["nombre"]}</b></font>', _hoja_estilos["Normal"]),
        Paragraph(f'<font color="#6b7280" size=8>{d["posicion"]}</font>', _hoja_estilos["Normal"]),
        Spacer(1, 5),
        _badges_metricas(d["metricas_fuera"] + d["metricas_en_rango"]),
    ]
    for reco in d["recomendaciones"]:
        contenido.append(Spacer(1, 4))
        contenido.append(Paragraph(f'<font size=8 color="#374151">{reco}</font>', _hoja_estilos["Normal"]))

    celda = Table([[contenido]], colWidths=[ANCHO_UTIL_CM * cm])
    celda.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, GRILLA),
        ("LINEBEFORE", (0, 0), (0, -1), 3, accent),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return celda


def _analisis_a_flowables(titulo: str, analisis: dict) -> list:
    """
    Arma fortalezas (chips) + debilidades (tarjetas con borde de color) — el
    layout imprimible de analisis_asistente_html() en pantalla.

    A diferencia de las demás secciones, NO se envuelve todo en un único
    KeepTogether: una lista larga de debilidades nunca entraría entera en
    una sola página. Cada tarjeta individual sí va en su propio
    KeepTogether (no se parte a la mitad entre hojas), pero distintas
    tarjetas pueden repartirse en páginas distintas.
    """
    flow = [Paragraph(titulo, ESTILO_SECCION)]
    if not analisis["fortalezas"] and not analisis["debilidades"]:
        flow.append(Paragraph("Sin fortalezas ni debilidades detectadas.", _hoja_estilos["Normal"]))
        flow.append(Spacer(1, 14))
        return flow

    if analisis["fortalezas"]:
        cfg_ok = _ESTADO_PDF_CFG["En rango"]
        # fortalezas_atipicas (ver generar_analisis en analisis.py) es
        # complementario: una jugadora en rango contra el Sheet puede igual
        # tener un pico atípico contra su propio historial — en pantalla se
        # marca con ⚡ + tooltip (analisis_asistente_html), acá no hay
        # tooltip así que el detalle va directo en el chip.
        atipicas_por_nombre = {
            f["nombre"]: f["metricas_atipicas"] for f in analisis.get("fortalezas_atipicas", [])
        }

        def _etiqueta_fortaleza(nombre: str) -> str:
            metricas = atipicas_por_nombre.get(nombre)
            if not metricas:
                return nombre
            detalle = ", ".join(f"{m['metrica']} z={m['z_score']:.1f}" for m in metricas)
            return f"{nombre} ({detalle})"

        flow.append(Paragraph(
            "<b>Fortalezas</b> — en rango en todas las métricas evaluadas:", _hoja_estilos["Normal"],
        ))
        flow.append(Spacer(1, 4))
        etiquetas = [_etiqueta_fortaleza(n) for n in analisis["fortalezas"]]
        flow.append(_chips(etiquetas, cfg_ok["texto"], cfg_ok["bg"]))
        flow.append(Spacer(1, 12))

    if analisis["debilidades"]:
        flow.append(Paragraph("<b>A vigilar</b>", _hoja_estilos["Normal"]))
        flow.append(Spacer(1, 6))
        for d in analisis["debilidades"]:
            flow.append(KeepTogether(_tarjeta_debilidad(d)))
            flow.append(Spacer(1, 8))

    flow.append(Spacer(1, 6))
    return flow


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
    secciones: list[SeccionFigura | SeccionTabla | SeccionFotos | SeccionAsistente | SeccionAnalisis],
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
        # SeccionAnalisis maneja sus propios saltos de página (cada tarjeta
        # de debilidad en su propio KeepTogether) — envolver TODO el bloque
        # en un único KeepTogether, como hacen las demás secciones, rompería
        # la paginación apenas hubiera más debilidades de las que entran en
        # una sola hoja.
        if isinstance(seccion, SeccionAnalisis):
            story.extend(_analisis_a_flowables(seccion.titulo, seccion.analisis))
            story.append(Spacer(1, 14))
            continue

        bloque = [Paragraph(seccion.titulo, ESTILO_SECCION)]
        if isinstance(seccion, SeccionFigura):
            bloque.append(_figura_a_imagen(seccion.figura, seccion.alto_cm))
        elif isinstance(seccion, SeccionAsistente):
            if seccion.df_evaluacion.empty:
                bloque.append(Paragraph("Sin datos para mostrar.", _hoja_estilos["Normal"]))
            else:
                bloque.append(_tabla_semaforo(seccion.df_evaluacion, seccion.etiqueta_header))
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
