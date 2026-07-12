# pages/03_wellness.py
import streamlit as st
import pandas as pd
import plotly.express as px
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from settings import WELLNESS_SHEET_ID, WELLNESS_SHEET_GID, ROSTER_SHEET_GID
from src.utils.auth import require_login
from src.loaders.wellness_loader import cargar_desde_sheets
from src.loaders.roster_loader import cargar_posiciones_desde_sheets
from src.metrics.wellness import (
    calcular_readiness,
    calcular_tendencia_tqr,
    generar_alertas,
    resumen_alertas_equipo
)
from src.metrics.physical import calcular_acwr

st.set_page_config(page_title="Wellness", page_icon="💚", layout="wide")

require_login()
st.markdown('<h1 style="text-align:center">Wellness & Readiness</h1>', unsafe_allow_html=True)
st.markdown('<p style="text-align:center; color:gray">Carga interna · Recuperación · Alertas diarias</p>', unsafe_allow_html=True)
st.divider()

# ── Cargar datos ───────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def cargar_datos():
    try:
        df = cargar_desde_sheets(WELLNESS_SHEET_ID, WELLNESS_SHEET_GID)
        df = calcular_readiness(df)
        df = calcular_tendencia_tqr(df)
        df = generar_alertas(df)
        df = calcular_acwr(df, col_carga="rpe")
        return df
    except Exception as e:
        return None

@st.cache_data(ttl=3600)
def cargar_posiciones():
    try:
        return cargar_posiciones_desde_sheets(WELLNESS_SHEET_ID, ROSTER_SHEET_GID)
    except Exception:
        return None

df     = cargar_datos()
df_pos = cargar_posiciones()

if df is None:
    st.error("No se pudieron cargar los datos de wellness. Verificá que el Google Sheet esté compartido como público (Lector).")
    st.stop()

if df_pos is not None:
    df = df.merge(df_pos[["player_id", "posicion"]], on="player_id", how="left")

# ── Selectores: fechas + posición ──────────────────────────────────────────
col_fecha, col_pos = st.columns([2, 1])

with col_fecha:
    fechas_disponibles = sorted(df["fecha"].unique(), reverse=True)
    fmt_fecha = lambda x: x.strftime("%d/%m/%Y") if hasattr(x, "strftime") else str(x)
    st.markdown(
        '<p style="font-size:0.875rem; color:inherit; margin-bottom:0.25rem">Fechas</p>',
        unsafe_allow_html=True,
    )
    with st.popover("Fechas", use_container_width=True):
        fechas_sel = st.multiselect(
            "Fechas",
            options=fechas_disponibles,
            default=[fechas_disponibles[0]],
            format_func=fmt_fecha,
            label_visibility="collapsed",
        )

with col_pos:
    if df_pos is not None:
        posiciones = sorted(df_pos["posicion"].dropna().unique())
        st.markdown(
            '<p style="font-size:0.875rem; color:inherit; margin-bottom:0.25rem">Posición</p>',
            unsafe_allow_html=True,
        )
        with st.popover("Posición", use_container_width=True):
            pos_sel = st.multiselect(
                "Posición", posiciones, default=posiciones, label_visibility="collapsed"
            )
    else:
        pos_sel = None

if not fechas_sel:
    st.warning("Seleccioná al menos una fecha.")
    st.stop()

df_filtrado = df[df["fecha"].isin(fechas_sel)]
if pos_sel is not None:
    df_filtrado = df_filtrado[df_filtrado["posicion"].isin(pos_sel)]

# Último registro por jugadora dentro de las fechas seleccionadas
df_hoy = (df_filtrado.sort_values("fecha")
                     .groupby("player_id")
                     .last()
                     .reset_index())

# ── KPIs ───────────────────────────────────────────────────────────────────
totalmente_apta = (df_hoy["readiness_zona"] == "Totalmente Apta").sum()
apta_moderado   = (df_hoy["readiness_zona"] == "Apta Moderado").sum()
precaucion      = (df_hoy["readiness_zona"] == "Precaución").sum()
no_aptas        = (df_hoy["readiness_zona"] == "No Apta").sum()
con_molest      = df_hoy["molestia_flag"].sum()

if len(fechas_sel) == 1:
    fecha_label = fechas_sel[0].strftime("%d/%m/%Y") if hasattr(fechas_sel[0], "strftime") else str(fechas_sel[0])
else:
    fecha_label = f"{len(fechas_sel)} fechas"

st.markdown("""
<style>
.well-kpi-grid {
    display: flex;
    justify-content: center;
    gap: 16px;
    flex-wrap: wrap;
    margin-bottom: 8px;
}
.well-kpi-card {
    background: linear-gradient(135deg, #0f2b5b 0%, #1a3a6b 60%, #1e4d8c 100%);
    border-radius: 14px;
    padding: 20px 32px;
    text-align: center;
    min-width: 140px;
    box-shadow: 0 4px 15px rgba(0,0,0,0.25);
}
.well-kpi-card .kpi-label {
    font-size: 0.78rem;
    color: #93c5fd;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 6px;
}
.well-kpi-card .kpi-value {
    font-size: 1.6rem;
    font-weight: 700;
    color: #ffffff;
}
</style>
""", unsafe_allow_html=True)

kpis_well = [
    ("📅 Fecha",           fecha_label),
    ("✅ Totalmente Apta", totalmente_apta),
    ("🙂 Apta Moderado",   apta_moderado),
    ("⚠️ Precaución",      precaucion),
    ("🚨 No Aptas",        no_aptas),
    ("🤕 Con molestias",   con_molest),
]

st.markdown(
    '<div class="well-kpi-grid">' + "".join(
        f'<div class="well-kpi-card">'
        f'<div class="kpi-label">{label}</div>'
        f'<div class="kpi-value">{value}</div>'
        f'</div>'
        for label, value in kpis_well
    ) + '</div>',
    unsafe_allow_html=True,
)

st.divider()

# ── Semáforo de readiness ──────────────────────────────────────────────────
st.subheader("Readiness individual — Último registro")

_ZONA_CFG = {
    "Totalmente Apta": {"color": "#34A853", "bg": "#0a2e14", "icon": "✅"},
    "Apta Moderado":   {"color": "#8BC34A", "bg": "#1c2e0a", "icon": "🙂"},
    "Precaución":      {"color": "#FBBC04", "bg": "#2e2200", "icon": "⚠️"},
    "No Apta":         {"color": "#EA4335", "bg": "#2e0a08", "icon": "🚨"},
    "Sin datos":  {"color": "#6b7280", "bg": "#1f2937", "icon": "—"},
}

st.markdown("""
<style>
.readiness-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 14px;
    justify-content: center;
    margin: 8px 0 16px;
}
.readiness-card {
    border-radius: 14px;
    padding: 18px 22px;
    text-align: center;
    min-width: 148px;
    max-width: 172px;
    flex: 1 1 148px;
    box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    border: 1px solid rgba(255,255,255,0.08);
}
.readiness-card .rc-icon  { font-size: 1.5rem; margin-bottom: 4px; }
.readiness-card .rc-name  { font-size: 0.78rem; color: #cbd5e1;
                             text-transform: uppercase; letter-spacing: 0.04em;
                             margin-bottom: 10px; }
.readiness-card .rc-score { font-size: 2rem; font-weight: 800; margin-bottom: 4px; }
.readiness-card .rc-zona  { font-size: 0.8rem; font-weight: 600;
                             border-radius: 20px; padding: 2px 12px;
                             display: inline-block; }
</style>
""", unsafe_allow_html=True)

df_read_sorted = df_hoy.sort_values("readiness_index", ascending=False)

cards = []
for _, row in df_read_sorted.iterrows():
    zona  = row.get("readiness_zona", "Sin datos")
    cfg   = _ZONA_CFG.get(zona, _ZONA_CFG["Sin datos"])
    score = f"{row['readiness_index']:.2f}" if pd.notna(row["readiness_index"]) else "—"
    cards.append(
        f'<div class="readiness-card" style="background:{cfg["bg"]}">'
        f'<div class="rc-icon">{cfg["icon"]}</div>'
        f'<div class="rc-name">{row["nombre"]}</div>'
        f'<div class="rc-score" style="color:{cfg["color"]}">{score}</div>'
        f'<div class="rc-zona" style="color:{cfg["color"]}; '
        f'background:rgba(255,255,255,0.07)">{zona}</div>'
        f'</div>'
    )

st.markdown('<div class="readiness-grid">' + "".join(cards) + '</div>',
            unsafe_allow_html=True)

st.divider()

# ── ACWR Interno — Esfuerzo Percibido (RPE) ───────────────────────────────
st.subheader("ACWR Interno — Esfuerzo Percibido (RPE)")

st.markdown("""
<style>
.acwr-table { width:100%; border-collapse:collapse; }
.acwr-table th { font-size:0.72rem; color:#93c5fd; text-transform:uppercase;
                 letter-spacing:0.05em; padding:8px 12px; text-align:left;
                 border-bottom:1px solid #1a2f5a; }
.acwr-table td { padding:9px 12px; font-size:0.88rem; color:#e2e8f0;
                 border-bottom:1px solid #0f2040; }
.acwr-badge { border-radius:20px; padding:3px 12px; font-size:0.75rem;
              font-weight:700; display:inline-block; }
</style>
""", unsafe_allow_html=True)

_ACWR_CFG = {
    "Óptimo":     {"color": "#34A853", "bg": "#0a2e14"},
    "Precaución": {"color": "#FBBC04", "bg": "#2e2200"},
    "Riesgo Alto":{"color": "#EA4335", "bg": "#2e0a08"},
    "Subcarga":   {"color": "#38bdf8", "bg": "#0c2a3a"},
    "Sin datos":  {"color": "#6b7280", "bg": "#1f2937"},
}

n_registros = df["fecha"].nunique()
if n_registros < 4:
    st.caption(f"⚠️ Solo {n_registros} registro/s — el ACWR gana precisión a partir de 4+.")

rows_html = ""
for _, row in df_hoy.sort_values("acwr", ascending=False).iterrows():
    zona = row.get("zona_acwr", "Sin datos")
    cfg  = _ACWR_CFG.get(zona, _ACWR_CFG["Sin datos"])
    acwr_val = f"{row['acwr']:.2f}" if pd.notna(row.get("acwr")) else "—"
    rows_html += (
        f'<tr>'
        f'<td>{row["nombre"]}</td>'
        f'<td style="font-weight:700;color:{cfg["color"]}">{acwr_val}</td>'
        f'<td><span class="acwr-badge" style="background:{cfg["bg"]};'
        f'color:{cfg["color"]}">{zona}</span></td>'
        f'</tr>'
    )
st.markdown(
    f'<table class="acwr-table">'
    f'<thead><tr><th>Jugadora</th><th>ACWR</th><th>Zona</th></tr></thead>'
    f'<tbody>{rows_html}</tbody>'
    f'</table>',
    unsafe_allow_html=True,
)
st.markdown("""
<div style="margin-top:14px; font-size:0.75rem; color:#6b7280; line-height:1.6">
<span style="color:#38bdf8">●</span> Subcarga &lt;0.8 &nbsp;
<span style="color:#34A853">●</span> Óptimo 0.8–1.3 &nbsp;
<span style="color:#FBBC04">●</span> Precaución 1.3–1.5 &nbsp;
<span style="color:#EA4335">●</span> Riesgo &gt;1.5
</div>
""", unsafe_allow_html=True)

st.divider()

# ── Evolución TQR y RPE ────────────────────────────────────────────────────
st.subheader("Evolución TQR y RPE — Todas las jugadoras")
jugadoras  = sorted(df_filtrado["nombre"].unique())
sel_jug    = st.multiselect("Seleccioná jugadoras",
                             jugadoras, default=jugadoras[:4])
df_evol    = df_filtrado[df_filtrado["nombre"].isin(sel_jug)]

_BG        = "#0d1b3e"
_GRID      = "#1a2f5a"
_FONT      = "#e2e8f0"
_COLORES   = ["#60a5fa", "#34d399", "#f472b6", "#fbbf24",
              "#a78bfa", "#38bdf8", "#fb923c", "#4ade80"]

def _dark_line_layout(height, title):
    return dict(
        height=height,
        plot_bgcolor=_BG,
        paper_bgcolor=_BG,
        font=dict(color=_FONT),
        title=dict(text=title, font=dict(color=_FONT)),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=_FONT)),
        xaxis=dict(color=_FONT, gridcolor=_GRID, zerolinecolor=_GRID),
        yaxis=dict(color=_FONT, gridcolor=_GRID, zerolinecolor=_GRID),
        margin=dict(l=10, r=10, t=40, b=10),
    )

col_tqr, col_rpe = st.columns(2)

with col_tqr:
    fig_tqr = px.line(
        df_evol, x="fecha", y="tqr", color="nombre",
        markers=True,
        labels={"tqr": "TQR (1–10)", "fecha": ""},
        color_discrete_sequence=_COLORES,
    )
    fig_tqr.update_traces(line=dict(width=2.5), marker=dict(size=8))
    fig_tqr.add_hline(y=5, line_dash="dash", line_color="#FBBC04",
                      annotation_text="Umbral mínimo",
                      annotation_font_color="#FBBC04")
    fig_tqr.update_layout(**_dark_line_layout(340, "Recuperación (TQR)"))
    st.plotly_chart(fig_tqr, use_container_width=True)

with col_rpe:
    fig_rpe = px.line(
        df_evol, x="fecha", y="rpe", color="nombre",
        markers=True,
        labels={"rpe": "RPE (1–10)", "fecha": ""},
        color_discrete_sequence=_COLORES,
    )
    fig_rpe.update_traces(line=dict(width=2.5), marker=dict(size=8))
    fig_rpe.add_hline(y=8, line_dash="dash", line_color="#f87171",
                      annotation_text="Alerta RPE alto",
                      annotation_font_color="#f87171")
    fig_rpe.update_layout(**_dark_line_layout(340, "Esfuerzo Percibido (RPE)"))
    st.plotly_chart(fig_rpe, use_container_width=True)

st.divider()

# ── Alertas activas ────────────────────────────────────────────────────────
st.subheader("🚨 Alertas activas")
alertas = resumen_alertas_equipo(df_filtrado)
if len(alertas) > 0:
    st.dataframe(
        alertas[["nombre", "fecha", "tqr", "rpe",
                 "readiness_index", "readiness_zona",
                 "total_alertas"]].reset_index(drop=True),
        use_container_width=True,
        hide_index=True,
    )
else:
    st.success("✅ Sin alertas activas en el plantel")

# ── Molestias físicas ──────────────────────────────────────────────────────
st.divider()
st.subheader("🤕 Molestias físicas reportadas")
molestias = (df_filtrado[df_filtrado["molestia_flag"]][["nombre", "fecha", "molestia"]]
             .sort_values(["nombre", "fecha"])
             .reset_index(drop=True))
if len(molestias) > 0:
    st.dataframe(molestias, use_container_width=True, hide_index=True)
else:
    st.success("✅ Sin molestias reportadas")