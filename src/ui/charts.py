# src/ui/charts.py
"""
Layouts de Plotly y helpers de estilo de gráfico compartidos — fuente única
para que un cambio de fondo/grilla/fuente se haga en un solo lugar. Los
colores base (CHART_BG/GRID/FONT) viven en theme.py junto con el resto de
la paleta del dashboard.
"""
import pandas as pd

from src.ui.theme import CHART_BG, CHART_GRID, CHART_FONT


def plotly_bar_layout(height: int) -> dict:
    """Layout oscuro compartido para gráficos de barras horizontales."""
    return dict(
        height=height,
        showlegend=False,
        coloraxis_showscale=False,
        plot_bgcolor=CHART_BG,
        paper_bgcolor=CHART_BG,
        font=dict(color=CHART_FONT),
        xaxis=dict(showgrid=True, gridcolor=CHART_GRID, color=CHART_FONT,
                   zerolinecolor=CHART_GRID),
        yaxis=dict(color=CHART_FONT),
        margin=dict(l=10, r=60, t=10, b=10),
    )


def plotly_grouped_bar_layout(height: int) -> dict:
    """
    Layout oscuro para barras verticales agrupadas por categoría (ej: una
    barra por partido, dentro de cada cuarto). A diferencia de
    plotly_bar_layout (barras horizontales de una sola serie), acá sí hay
    leyenda — cada color es una identidad (partido), no un valor.
    bargap/bargroupgap dejan aire entre grupos y entre barras del mismo
    grupo, para que las barras no ocupen todo el espacio del eje.
    """
    return dict(
        height=height,
        plot_bgcolor=CHART_BG,
        paper_bgcolor=CHART_BG,
        font=dict(color=CHART_FONT),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=CHART_FONT)),
        xaxis=dict(color=CHART_FONT, gridcolor=CHART_GRID, zerolinecolor=CHART_GRID),
        yaxis=dict(color=CHART_FONT, gridcolor=CHART_GRID, zerolinecolor=CHART_GRID),
        bargap=0.25,
        bargroupgap=0.1,
        margin=dict(l=10, r=10, t=10, b=10),
    )


def plotly_line_layout(height: int, title: str | None = None) -> dict:
    """Layout oscuro compartido para gráficos de línea temporal."""
    layout = dict(
        height=height,
        plot_bgcolor=CHART_BG,
        paper_bgcolor=CHART_BG,
        font=dict(color=CHART_FONT),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=CHART_FONT)),
        xaxis=dict(color=CHART_FONT, gridcolor=CHART_GRID, zerolinecolor=CHART_GRID),
        yaxis=dict(color=CHART_FONT, gridcolor=CHART_GRID, zerolinecolor=CHART_GRID),
        margin=dict(l=10, r=10, t=40 if title else 10, b=10),
    )
    if title:
        layout["title"] = dict(text=title, font=dict(color=CHART_FONT))
    return layout


def _hex_a_rgba(hex_color: str, alpha: float) -> str:
    """Convierte un hex '#rrggbb' a 'rgba(r,g,b,alpha)' para fillgradient."""
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def apply_area_line_style(fig, top_opacity: float = 0.32, fill: bool = True) -> None:
    """
    Da a un gráfico de línea (px.line) el estilo "área con degradé":
    curva suavizada (spline), marcador con borde blanco, relleno bajo la
    línea con gradiente vertical del mismo color de cada traza (denso cerca
    de la línea, transparente hacia la base) y hover unificado prolijo.

    Toma el color que Plotly Express ya asignó a cada traza (vía
    color_discrete_sequence / LINE_PALETTE) en vez de recibirlo aparte, así
    que funciona igual con uno o varios gráficos superpuestos.

    fill=False deja la curva/marcador/hover pero sin área rellena — usar en
    gráficos de 2+ líneas que se cruzan (ej. TQR vs RPE): dos áreas
    "tozeroy" superpuestas generan una mezcla de color turbia justo en las
    zonas de cruce, así que ahí el relleno resta en vez de sumar.
    """
    for trace in fig.data:
        color = trace.line.color
        trace.update(
            mode="lines+markers",
            line=dict(shape="spline", smoothing=0.4, width=2.5, color=color),
            marker=dict(size=7, color=color, line=dict(width=1.5, color="#ffffff")),
        )
        if fill:
            trace.update(
                fill="tozeroy",
                fillgradient=dict(
                    type="vertical",
                    colorscale=[[0, _hex_a_rgba(color, 0)], [1, _hex_a_rgba(color, top_opacity)]],
                ),
            )
    fig.update_layout(
        hovermode="x unified",
        hoverlabel=dict(bgcolor=CHART_BG, bordercolor=CHART_GRID,
                         font=dict(color=CHART_FONT, size=12)),
    )


MD_HIGHLIGHT_COLOR = "#F9AB00"


def resaltar_md(label: str, match_day: str) -> str:
    """
    Envuelve `label` en negrita + color si `match_day` es exactamente "MD"
    (el día de partido en sí) — MD-5, MD-4, MD+1, etc. quedan sin resaltar.
    Usado en los ticks de eje X de todos los gráficos con Match Day, para que
    el ojo vaya directo al día de partido en vez de tener que leer cada tick.
    """
    if match_day == "MD":
        return f'<b><span style="color:{MD_HIGHLIGHT_COLOR}">{label}</span></b>'
    return label


def md_ordinal_axis(df: pd.DataFrame, col_fecha: str = "fecha",
                     col_md: str = "match_day", col_x: str = "_md_x"
                     ) -> tuple[pd.DataFrame, dict]:
    """
    Prepara un eje X de Match Day con espaciado parejo entre jornadas.

    Espaciar por fecha real (ver versión anterior de este helper) dejaba
    huecos desparejos cada vez que había una semana sin sesiones entre un MD
    y el siguiente. Acá cada fecha única pasa a ocupar una posición entera
    consecutiva (0, 1, 2...) en el mismo orden cronológico — los cuartos de
    un mismo partido comparten fecha y quedan en la misma posición, y dos
    MDs iguales de semanas distintas (ej. dos "MD-2") no colisionan porque
    la posición se arma por fecha, no por el texto del MD.

    Devuelve (df_copia_con_columna_x, dict_para_fig.update_xaxes).
    """
    fechas = sorted(df[col_fecha].unique())
    posicion = {fecha: i for i, fecha in enumerate(fechas)}
    df = df.copy()
    df[col_x] = df[col_fecha].map(posicion)
    md_por_fecha = df.drop_duplicates(col_fecha).set_index(col_fecha)[col_md]
    ticks = dict(
        tickmode="array", tickvals=list(posicion.values()),
        ticktext=[resaltar_md(md_por_fecha[f], md_por_fecha[f]) for f in fechas],
    )
    return df, ticks


def plotly_radar_layout(height: int, radial_range: tuple[float, float] = (0, 10)) -> dict:
    """Layout oscuro compartido para gráficos de radar (Scatterpolar)."""
    return dict(
        height=height,
        paper_bgcolor=CHART_BG,
        font=dict(color=CHART_FONT),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=CHART_FONT)),
        polar=dict(
            bgcolor=CHART_BG,
            radialaxis=dict(visible=True, range=list(radial_range),
                            color=CHART_FONT, gridcolor=CHART_GRID),
            angularaxis=dict(color=CHART_FONT, gridcolor=CHART_GRID),
        ),
        margin=dict(l=40, r=40, t=40, b=40),
    )
