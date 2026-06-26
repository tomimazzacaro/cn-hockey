# pages/02_carga_fisica.py
import streamlit as st
import pandas as pd
import plotly.express as px
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from settings import PROCESSED
from src.utils.auth import require_login
from src.metrics.physical import calcular_acwr, calcular_intensidad_relativa

st.set_page_config(page_title="Carga Física", page_icon="📊", layout="wide")

require_login()
st.title("📊 Carga Física")
st.caption("GPS Catapult — Métricas de carga externa e intensidad relativa")
st.divider()

# ── Cargar datos ───────────────────────────────────────────────────────────
@st.cache_data
def cargar_datos():
    df = pd.read_parquet(PROCESSED / "gps_procesado.parquet")
    df = calcular_intensidad_relativa(df)
    df = calcular_acwr(df, col_carga="player_load")
    return df

df = cargar_datos()

# ── Filtros ────────────────────────────────────────────────────────────────
fechas      = sorted(df["fecha"].unique(), reverse=True)
fecha_sel   = st.selectbox("Sesión", fechas,
                            format_func=lambda x: x.strftime("%d/%m/%Y")
                            if hasattr(x, "strftime") else str(x))
df_ses      = df[df["fecha"] == fecha_sel]

st.divider()

# ── KPIs del equipo ────────────────────────────────────────────────────────
st.subheader("Equipo — Resumen de sesión")

st.markdown("""
<style>
.kpi-grid {
    display: flex;
    justify-content: center;
    gap: 16px;
    flex-wrap: wrap;
    margin-bottom: 8px;
}
.kpi-card {
    background: linear-gradient(135deg, #0f2b5b 0%, #1a3a6b 60%, #1e4d8c 100%);
    border-radius: 14px;
    padding: 20px 28px;
    text-align: center;
    min-width: 140px;
    box-shadow: 0 4px 15px rgba(0,0,0,0.25);
}
.kpi-card .kpi-label {
    font-size: 0.78rem;
    color: #93c5fd;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 6px;
}
.kpi-card .kpi-value {
    font-size: 1.6rem;
    font-weight: 700;
    color: #ffffff;
}
</style>
""", unsafe_allow_html=True)

kpis = [
    ("Jugadoras",        f"{len(df_ses)}"),
    ("Distancia media",  f"{df_ses['distancia_total'].mean():,.0f} m"),
    ("HSR media",        f"{df_ses['hsr'].mean():,.0f} m"),
    ("Player Load medio",f"{df_ses['player_load'].mean():,.1f}"),
    ("Vel. Máx media",   f"{df_ses['vel_max_kmh'].mean():,.1f} km/h"),
]

cards_html = '<div class="kpi-grid">' + "".join(
    f'<div class="kpi-card"><div class="kpi-label">{label}</div><div class="kpi-value">{value}</div></div>'
    for label, value in kpis
) + '</div>'

st.markdown(cards_html, unsafe_allow_html=True)

st.divider()

# ── Config gráficos ────────────────────────────────────────────────────────
BG       = "#0d1b3e"
GRID_COL = "#1a2f5a"
FONT_COL = "#e2e8f0"

METRICAS = {
    "Distancia total (m)":  ("distancia_total", "%{text:,.0f} m", ["#1e3a8a", "#60a5fa", "#bfdbfe"]),
    "Player Load":          ("player_load",     "%{text:.1f}",    ["#064e3b", "#34d399", "#a7f3d0"]),
    "HSR Distance (m)":     ("hsr",             "%{text:.0f} m",  ["#78350f", "#fbbf24", "#fef3c7"]),
    "Sprints":              ("sprints",         "%{text:.0f}",    ["#7f1d1d", "#f87171", "#fee2e2"]),
    "Vel. Máx (km/h)":      ("vel_max_kmh",     "%{text:.1f}",    ["#4c1d95", "#a78bfa", "#ede9fe"]),
    "Dist/min (m/min)":     ("dist_min",        "%{text:.1f}",    ["#0c4a6e", "#38bdf8", "#e0f2fe"]),
    "Player Load/min":      ("pl_min",          "%{text:.2f}",    ["#052e16", "#4ade80", "#dcfce7"]),
    "ACC >3 (m/s²)":        ("acc_3",           "%{text:.0f}",    ["#431407", "#fb923c", "#ffedd5"]),
    "DECC >3 (m/s²)":       ("decc_3",          "%{text:.0f}",    ["#422006", "#fcd34d", "#fef9c3"]),
}

def _dark_layout(height):
    return dict(
        height=height,
        showlegend=False,
        coloraxis_showscale=False,
        plot_bgcolor=BG,
        paper_bgcolor=BG,
        font=dict(color=FONT_COL),
        xaxis=dict(showgrid=True, gridcolor=GRID_COL, color=FONT_COL, zerolinecolor=GRID_COL),
        yaxis=dict(color=FONT_COL),
        margin=dict(l=10, r=60, t=10, b=10),
    )

def _bar_chart(data, col, label, fmt, scale, height):
    fig = px.bar(
        data.sort_values(col, ascending=True),
        x=col, y="nombre",
        orientation="h",
        color=col,
        color_continuous_scale=scale,
        labels={col: label, "nombre": ""},
        text=col,
    )
    fig.update_traces(texttemplate=fmt, textposition="outside",
                      textfont=dict(color=FONT_COL))
    fig.update_layout(**_dark_layout(height))
    return fig

# ── Gráfico principal ──────────────────────────────────────────────────────
sel_principal = st.selectbox("Métrica", list(METRICAS.keys()), key="sel_principal")
col_p, fmt_p, scale_p = METRICAS[sel_principal]
st.subheader(sel_principal)
st.plotly_chart(_bar_chart(df_ses, col_p, sel_principal, fmt_p, scale_p, 420),
                use_container_width=True)

# ── Dos columnas con selector independiente ────────────────────────────────
col_izq, col_der = st.columns(2)

with col_izq:
    sel_izq = st.selectbox("Métrica", list(METRICAS.keys()), index=1, key="sel_izq")
    col_i, fmt_i, scale_i = METRICAS[sel_izq]
    st.subheader(sel_izq)
    st.plotly_chart(_bar_chart(df_ses, col_i, sel_izq, fmt_i, scale_i, 360),
                    use_container_width=True)

with col_der:
    sel_der = st.selectbox("Métrica", list(METRICAS.keys()), index=2, key="sel_der")
    col_d, fmt_d, scale_d = METRICAS[sel_der]
    st.subheader(sel_der)
    st.plotly_chart(_bar_chart(df_ses, col_d, sel_der, fmt_d, scale_d, 360),
                    use_container_width=True)

st.divider()

# ── Tabla detallada ────────────────────────────────────────────────────────
st.subheader("Tabla completa de la sesión")
cols_tabla = ["nombre", "duracion_min", "distancia_total",
              "dist_min", "hsr", "hsr_pct", "sprints",
              "acc_3", "decc_3", "player_load", "pl_min", "vel_max_kmh"]
st.dataframe(
    df_ses[cols_tabla].sort_values("distancia_total", ascending=False)
                      .reset_index(drop=True),
    use_container_width=True,
    hide_index=True,
)