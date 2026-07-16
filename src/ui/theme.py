# src/ui/theme.py
"""
Design system centralizado — CN Hockey Performance Hub.

Fuente única de colores, CSS y layouts de Plotly. Antes de este módulo,
cada página bajo pages/ reimplementaba su propia paleta y sus propios
bloques <style>; esto unifica esos valores (sin cambiar ningún tono) para
que un cambio de color se haga en un solo lugar.
"""
import pandas as pd
import streamlit as st

# ── Paleta base ─────────────────────────────────────────────────────────────
CARD_GRADIENT = "linear-gradient(135deg, #0f2b5b 0%, #1a3a6b 60%, #1e4d8c 100%)"

CHART_BG   = "#0d1b3e"
CHART_GRID = "#1a2f5a"
CHART_FONT = "#e2e8f0"

LINE_PALETTE = ["#60a5fa", "#34d399", "#f472b6", "#fbbf24",
                "#a78bfa", "#38bdf8", "#fb923c", "#4ade80"]

COMPARE_COLOR_A = "#3987e5"   # azul — misma familia que el resto del dashboard
COMPARE_COLOR_B = "#199e70"   # verde azulado — validado contra el fondo oscuro (CVD ΔE 69.8)

# Paleta categórica para gráficos de barras agrupadas por identidad (ej: un
# color por partido). Validada con scripts/validate_palette.js del skill de
# dataviz contra el fondo real del dashboard (#0d1b3e, modo oscuro): banda de
# luminosidad OK, piso de croma OK, contraste OK, CVD ΔE mínimo 10.3 (banda
# 8–12 — por eso siempre va con leyenda + tooltip, nunca solo color).
BAR_CATEGORICAL_PALETTE = [
    "#3987e5",  # azul
    "#199e70",  # verde azulado
    "#c98500",  # mostaza
    "#008300",  # verde
    "#9085e9",  # violeta
    "#e66767",  # rojo
    "#d55181",  # magenta
    "#d95926",  # naranja
]

# ── Zonas ACWR (semáforo de riesgo) ─────────────────────────────────────────
ZONE_CFG = {
    "Óptimo":      {"color": "#34A853", "bg": "#0a2e14"},
    "Precaución":  {"color": "#FBBC04", "bg": "#2e2200"},
    "Riesgo Alto": {"color": "#EA4335", "bg": "#2e0a08"},
    "Subcarga":    {"color": "#38bdf8", "bg": "#0c2a3a"},
    "Sin datos":   {"color": "#6b7280", "bg": "#1f2937"},
}

# ── Zonas Readiness ─────────────────────────────────────────────────────────
READINESS_CFG = {
    "Totalmente Apta": {"color": "#34A853", "bg": "#0a2e14", "icon": "✅"},
    "Apta Moderado":   {"color": "#8BC34A", "bg": "#1c2e0a", "icon": "🙂"},
    "Precaución":      {"color": "#FBBC04", "bg": "#2e2200", "icon": "⚠️"},
    "No Apta":         {"color": "#EA4335", "bg": "#2e0a08", "icon": "🚨"},
    "Sin datos":       {"color": "#6b7280", "bg": "#1f2937", "icon": "—"},
}


# ── CSS compartido ───────────────────────────────────────────────────────────

def inject_dashboard_css() -> None:
    """
    Inyecta el CSS compartido por todas las páginas: cards de navegación,
    grillas de KPI, tarjetas de comparación, tabla ACWR, tarjetas de
    readiness, filas de alerta/molestia. Llamar una vez por página.
    """
    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Oswald:wght@500;700&display=swap');

    /* Cards de navegación clickeables (home) — ver nav_card() más abajo */
    div[class*="st-key-cn-navcard-"] {{
        background: {CARD_GRADIENT};
        border-radius: 14px;
        padding: 26px 20px 16px;
        text-align: center;
        box-shadow: 0 4px 20px rgba(0,0,0,0.35);
        transition: box-shadow 0.2s ease, transform 0.2s ease;
        min-height: 190px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
    }}
    div[class*="st-key-cn-navcard-"]:hover {{
        box-shadow: 0 12px 28px rgba(0,0,0,0.45);
        transform: translateY(-3px);
    }}
    div[class*="st-key-cn-navcard-"] [data-testid="stPageLink"] {{
        width: 100%;
    }}
    div[class*="st-key-cn-navcard-"] [data-testid="stPageLink"] a {{
        justify-content: center;
        text-decoration: none !important;
        white-space: normal !important;
        height: auto !important;
    }}
    div[class*="st-key-cn-navcard-"] [data-testid="stPageLink"] p {{
        color: #ffffff !important;
        font-size: 1.05rem;
        white-space: normal !important;
        overflow-wrap: break-word;
        text-align: center;
    }}
    div[class*="st-key-cn-navcard-"] [data-testid="stCaptionContainer"] {{
        color: #93c5fd !important;
        text-align: center;
        margin-top: 2px;
    }}

    /* Grilla de KPIs */
    .cn-kpi-grid {{ display:flex; justify-content:center; gap:10px; flex-wrap:wrap; margin-bottom:4px; }}
    .cn-kpi-card {{
        background: {CARD_GRADIENT};
        border-radius:14px; padding:14px 12px 12px; text-align:center;
        width:150px; box-shadow:0 4px 15px rgba(0,0,0,0.3);
    }}
    .cn-kpi-card .lbl {{ font-size:0.72rem; color:#93c5fd; text-transform:uppercase;
                        letter-spacing:0.05em; margin-bottom:5px; overflow-wrap:break-word; }}
    .cn-kpi-card .val {{ font-size:1.55rem; font-weight:800; color:#fff; }}

    /* Tarjetas KPI de jugadora (perfil individual) — chip de ícono con
       tinte del color de acento, borde superior a juego */
    .cn-player-kpi-grid {{
        display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
        gap: 14px; margin: 28px 0 4px;
    }}
    .cn-player-kpi-card {{
        background: {CARD_GRADIENT};
        border-radius: 16px; padding: 18px 18px 16px;
        border-top: 3px solid var(--accent);
        border-left: 1px solid rgba(255,255,255,0.06);
        border-right: 1px solid rgba(255,255,255,0.06);
        border-bottom: 1px solid rgba(255,255,255,0.06);
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
        text-align: center;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }}
    .cn-player-kpi-card:hover {{
        transform: translateY(-2px);
        box-shadow: 0 10px 24px rgba(0,0,0,0.4);
    }}
    .cn-player-kpi-icon {{
        width: 38px; height: 38px; border-radius: 10px;
        display: flex; align-items: center; justify-content: center;
        background: color-mix(in srgb, var(--accent) 22%, transparent);
        font-size: 1.15rem; margin: 0 auto 12px;
    }}
    .cn-player-kpi-label {{
        font-size: 0.7rem; color: #93c5fd; text-transform: uppercase;
        letter-spacing: 0.05em; margin-bottom: 5px;
    }}
    .cn-player-kpi-value {{ font-size: 1.55rem; font-weight: 800; color: #fff; }}

    /* Tarjetas de comparación (jugadoras / tipos de sesión) */
    .cn-cmp-card {{
        border-radius: 14px;
        padding: 22px 12px;
        text-align: center;
        background: {CARD_GRADIENT};
        border-top: 4px solid var(--accent);
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    }}
    .cn-cmp-avatar {{ font-size: 2.4rem; margin-bottom: 8px; }}
    .cn-cmp-name   {{ font-size: 0.92rem; font-weight: 700; color: #fff;
                     text-transform: uppercase; letter-spacing: 0.02em; }}

    /* Filas de barras comparativas (jugadora A vs B, tipo A vs B) */
    .cn-cmp-row {{ display: flex; align-items: center; gap: 8px; margin-bottom: 14px; }}
    .cn-cmp-value {{ width: 72px; font-size: 0.82rem; font-weight: 700; color: {CHART_FONT}; }}
    .cn-cmp-value-a {{ text-align: right; }}
    .cn-cmp-value-b {{ text-align: left; }}
    .cn-cmp-label  {{
        width: 130px; flex-shrink: 0; text-align: center;
        font-size: 0.74rem; color: #93c5fd; text-transform: uppercase;
        letter-spacing: 0.04em;
    }}
    .cn-cmp-bar-a, .cn-cmp-bar-b {{
        flex: 1; display: flex; height: 12px;
        background: #16294f; border-radius: 6px;
    }}
    .cn-cmp-bar-a {{ justify-content: flex-end; }}
    .cn-cmp-bar-b {{ justify-content: flex-start; }}
    .cn-cmp-fill-a, .cn-cmp-fill-b {{ height: 100%; }}
    .cn-cmp-fill-a {{ background: var(--color-a); border-radius: 4px 0 0 4px; }}
    .cn-cmp-fill-b {{ background: var(--color-b); border-radius: 0 4px 4px 0; }}

    /* Tabla ACWR */
    .cn-acwr-table {{ width:100%; border-collapse:collapse; }}
    .cn-acwr-table th {{ font-size:0.72rem; color:#93c5fd; text-transform:uppercase;
                        letter-spacing:0.05em; padding:8px 12px; text-align:left;
                        border-bottom:1px solid {CHART_GRID}; }}
    .cn-acwr-table td {{ padding:9px 12px; font-size:0.88rem; color:{CHART_FONT};
                        border-bottom:1px solid #0f2040; }}
    .cn-acwr-badge {{ border-radius:20px; padding:3px 12px; font-size:0.75rem;
                     font-weight:700; display:inline-block; }}

    /* Encabezado de página compartido — ver page_header() más abajo. Ícono
       arriba del título, apilados en columna y centrados — así el ícono
       siempre queda justo encima del título sin importar cuánto mida. */
    .cn-page-header {{
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 10px;
        margin: 6px 0 4px;
    }}
    .cn-page-header-icon {{
        width: 56px; height: 56px; border-radius: 14px; flex-shrink: 0;
        display: flex; align-items: center; justify-content: center;
        font-size: 1.8rem;
        background: color-mix(in srgb, var(--accent) 22%, transparent);
        border: 1px solid color-mix(in srgb, var(--accent) 45%, transparent);
    }}
    .cn-page-header-text {{ text-align: center; }}
    .cn-page-header-title {{
        font-family: 'Oswald', sans-serif;
        font-size: 2.3rem; font-weight: 700; color: #fff; margin: 0; line-height: 1.15;
        text-transform: uppercase; letter-spacing: 0.04em;
    }}
    .cn-page-header-subtitle {{
        font-size: 0.85rem; color: #93c5fd; font-style: italic; margin: 4px 0 0;
    }}

    /* Tarjetas de readiness individual */
    .cn-readiness-grid {{
        display: flex; flex-wrap: wrap; gap: 14px;
        justify-content: center; margin: 8px 0 16px;
    }}
    .cn-readiness-card {{
        border-radius: 14px; padding: 18px 22px; text-align: center;
        min-width: 148px; max-width: 172px; flex: 1 1 148px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
        border: 1px solid rgba(255,255,255,0.08);
    }}
    .cn-readiness-card .rc-icon  {{ font-size: 1.5rem; margin-bottom: 4px; }}
    .cn-readiness-card .rc-name  {{ font-size: 0.78rem; color: #cbd5e1;
                                   text-transform: uppercase; letter-spacing: 0.04em;
                                   margin-bottom: 10px; }}
    .cn-readiness-card .rc-score {{ font-size: 2rem; font-weight: 800; margin-bottom: 4px; }}
    .cn-readiness-card .rc-zona  {{ font-size: 0.8rem; font-weight: 600;
                                   border-radius: 20px; padding: 2px 12px;
                                   display: inline-block; }}

    /* Alertas */
    .cn-alert-row {{
        background:#1a0a0a; border-left:4px solid #EA4335;
        border-radius:8px; padding:10px 16px; margin-bottom:8px;
        display:flex; align-items:center; gap:14px;
    }}
    .cn-alert-row .ar-name {{ font-weight:700; color:#fca5a5; font-size:0.9rem; }}
    .cn-alert-row .ar-detail {{ font-size:0.8rem; color:#fecaca; }}
    .cn-alert-tag {{ background:#7f1d1d; color:#fca5a5; border-radius:20px;
                    padding:2px 8px; font-size:0.72rem; font-weight:600; margin-right:4px; }}

    /* Molestias */
    .cn-molestia-row {{
        background:#1a1000; border-left:4px solid #FBBC04;
        border-radius:8px; padding:10px 16px; margin-bottom:8px;
    }}
    .cn-molestia-row .mo-name   {{ font-weight:700; color:#fde68a; font-size:0.88rem; }}
    .cn-molestia-row .mo-detail {{ font-size:0.8rem; color:#fef3c7; margin-top:2px; }}

    /* Link "Home" arriba a la derecha (ver home_button()) */
    div[class*="st-key-cn-home-link"] [data-testid="stPageLink"] a {{
        background: rgba(15,43,91,0.55);
        border: 1px solid rgba(147,197,253,0.25);
        border-radius: 20px;
        padding: 2px 12px;
        justify-content: center;
        text-decoration: none !important;
    }}
    div[class*="st-key-cn-home-link"] [data-testid="stPageLink"] a:hover {{
        background: rgba(26,58,107,0.85);
    }}
    div[class*="st-key-cn-home-link"] [data-testid="stPageLink"] p {{
        color: #93c5fd !important;
        font-size: 0.8rem;
        white-space: nowrap;
    }}
    </style>
    """, unsafe_allow_html=True)


def home_button() -> None:
    """
    Link "🏠 Home" alineado arriba a la derecha para volver a app.py.
    Llamar al principio de cada página (después de require_login(),
    antes del título) — no en app.py, que ya es la home.
    """
    _, col_home = st.columns([6, 1])
    with col_home:
        with st.container(key="cn-home-link"):
            st.page_link("app.py", label="Home", icon="🏠", use_container_width=True)


# ── Plotly layouts ────────────────────────────────────────────────────────

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
    ticks = dict(tickmode="array", tickvals=list(posicion.values()),
                 ticktext=[md_por_fecha[f] for f in fechas])
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


# ── Componentes HTML ─────────────────────────────────────────────────────

def page_header(title: str, subtitle: str | None = None,
                 icon: str | None = None, color: str | None = None) -> None:
    """
    Encabezado de página compartido: ícono en chip de color + título grande
    + subtítulo opcional debajo, reemplazando el st.title()/<h1> suelto que
    cada página armaba por su cuenta. `color` es el mismo acento que la
    tarjeta de esa sección en home (ver nav_card() en app.py). Ícono y texto
    quedan pegados como un solo grupo, centrado en la página — pasar
    icon=None (ej. Overview) omite el chip y solo centra el título.
    """
    icon_html = (
        f'<div class="cn-page-header-icon" style="--accent:{color}">{icon}</div>'
        if icon else ""
    )
    subtitle_html = f'<p class="cn-page-header-subtitle">{subtitle}</p>' if subtitle else ""
    st.markdown(
        f'<div class="cn-page-header">'
        f'{icon_html}'
        f'<div class="cn-page-header-text">'
        f'<h1 class="cn-page-header-title">{title}</h1>'
        f'{subtitle_html}'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def render_kpi_row(items: list[tuple[str, object]]) -> None:
    """Renderiza una fila de tarjetas KPI. items = [(label, value), ...]."""
    st.markdown(
        '<div class="cn-kpi-grid">' + "".join(
            f'<div class="cn-kpi-card"><div class="lbl">{label}</div>'
            f'<div class="val">{value}</div></div>'
            for label, value in items
        ) + '</div>',
        unsafe_allow_html=True,
    )


def player_kpi_row(items: list[tuple[str, str, str, str]]) -> None:
    """
    Renderiza una fila de tarjetas KPI de jugadora con ícono acentuado.
    items = [(icono, label, valor, color_acento), ...] — color_acento en hex,
    pensado para usarse con BAR_CATEGORICAL_PALETTE (ya validada contra el
    fondo oscuro del dashboard).
    """
    st.markdown(
        '<div class="cn-player-kpi-grid">' + "".join(
            f'<div class="cn-player-kpi-card" style="--accent:{color}">'
            f'<div class="cn-player-kpi-icon">{icon}</div>'
            f'<div class="cn-player-kpi-label">{label}</div>'
            f'<div class="cn-player-kpi-value">{value}</div>'
            f'</div>'
            for icon, label, value, color in items
        ) + '</div>',
        unsafe_allow_html=True,
    )


def nav_card(key: str, page: str, icon: str, title: str, subtitle: str, color: str) -> None:
    """
    Tarjeta de navegación clickeable para la home.

    Usa st.page_link (navegación real de Streamlit) en vez de un
    <div onclick="window.location.href=...">: ese onclick corre dentro del
    iframe aislado del componente de markdown y navega el iframe, no la app
    — por eso el click no llevaba a ningún lado. st.container(key=...)
    expone una clase CSS estable ("st-key-<key>") que sí podemos estilizar.
    """
    st.markdown(
        f'<style>.st-key-{key} {{ border-top: 4px solid {color}; }}</style>',
        unsafe_allow_html=True,
    )
    with st.container(key=key):
        st.page_link(page, label=f"{icon}  **{title}**", use_container_width=True)
        st.caption(subtitle)


def compare_card_html(icon: str, name: str, color: str) -> str:
    """Tarjeta de cabecera para un lado de una comparación A/B (jugadora o tipo de sesión)."""
    return (
        f'<div class="cn-cmp-card" style="--accent:{color}">'
        f'<div class="cn-cmp-avatar">{icon}</div>'
        f'<div class="cn-cmp-name">{name}</div>'
        f'</div>'
    )


def compare_rows_html(metrics: list[tuple[str, str, str]],
                       valores_a, valores_b,
                       color_a: str = COMPARE_COLOR_A,
                       color_b: str = COMPARE_COLOR_B) -> str:
    """
    Genera las filas de barras comparativas A/B.
    metrics: [(label, columna, formato), ...]
    valores_a/valores_b: objetos con .get(columna) -> valor numérico (Series o dict).
    """
    rows_html = ""
    for label, col, fmt in metrics:
        val_a = valores_a.get(col)
        val_b = valores_b.get(col)
        val_a = 0.0 if pd.isna(val_a) else float(val_a)
        val_b = 0.0 if pd.isna(val_b) else float(val_b)
        maximo = max(val_a, val_b, 1e-9)
        pct_a = (val_a / maximo) * 100
        pct_b = (val_b / maximo) * 100

        rows_html += (
            f'<div class="cn-cmp-row">'
            f'<div class="cn-cmp-value cn-cmp-value-a">{fmt.format(val_a)}</div>'
            f'<div class="cn-cmp-bar-a"><div class="cn-cmp-fill-a" '
            f'style="width:{pct_a:.1f}%; --color-a:{color_a}"></div></div>'
            f'<div class="cn-cmp-label">{label}</div>'
            f'<div class="cn-cmp-bar-b"><div class="cn-cmp-fill-b" '
            f'style="width:{pct_b:.1f}%; --color-b:{color_b}"></div></div>'
            f'<div class="cn-cmp-value cn-cmp-value-b">{fmt.format(val_b)}</div>'
            f'</div>'
        )
    return rows_html


def acwr_table_html(df: pd.DataFrame, n_registros: int | None = None) -> None:
    """
    Renderiza la tabla ACWR por jugadora con semáforo de zona de riesgo.
    Espera columnas [nombre, acwr, zona_acwr] en df (una fila por jugadora,
    ya reducida al último registro).
    """
    if n_registros is not None and n_registros < 4:
        st.caption(f"⚠️ Solo {n_registros} registro/s — el ACWR gana precisión a partir de 4+.")

    rows_html = ""
    for _, row in df.sort_values("acwr", ascending=False).iterrows():
        zona = row.get("zona_acwr", "Sin datos")
        cfg = ZONE_CFG.get(zona, ZONE_CFG["Sin datos"])
        acwr_val = f"{row['acwr']:.2f}" if pd.notna(row.get("acwr")) else "—"
        rows_html += (
            f'<tr>'
            f'<td>{row["nombre"]}</td>'
            f'<td style="font-weight:700;color:{cfg["color"]}">{acwr_val}</td>'
            f'<td><span class="cn-acwr-badge" style="background:{cfg["bg"]};'
            f'color:{cfg["color"]}">{zona}</span></td>'
            f'</tr>'
        )
    st.markdown(
        f'<table class="cn-acwr-table">'
        f'<thead><tr><th>Jugadora</th><th>ACWR</th><th>Zona</th></tr></thead>'
        f'<tbody>{rows_html}</tbody>'
        f'</table>',
        unsafe_allow_html=True,
    )
    st.markdown(f"""
    <div style="margin-top:14px; font-size:0.75rem; color:#6b7280; line-height:1.6">
    <span style="color:{ZONE_CFG['Subcarga']['color']}">●</span> Subcarga &lt;0.8 &nbsp;
    <span style="color:{ZONE_CFG['Óptimo']['color']}">●</span> Óptimo 0.8–1.3 &nbsp;
    <span style="color:{ZONE_CFG['Precaución']['color']}">●</span> Precaución 1.3–1.5 &nbsp;
    <span style="color:{ZONE_CFG['Riesgo Alto']['color']}">●</span> Riesgo &gt;1.5
    </div>
    """, unsafe_allow_html=True)
