# pages/03_wellness.py
import streamlit as st
import pandas as pd
import plotly.express as px
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from settings import WELLNESS_SHEET_ID, WELLNESS_SHEET_GID, ROSTER_SHEET_GID, LOGO_PATH
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
from src.ui.theme import (
    inject_dashboard_css, render_kpi_row, acwr_table_html, home_button,
    plotly_line_layout, LINE_PALETTE, READINESS_CFG,
)

st.set_page_config(page_title="Wellness", page_icon=str(LOGO_PATH), layout="wide")

require_login()
inject_dashboard_css()
home_button()
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

kpis_well = [
    ("📅 Fecha",           fecha_label),
    ("✅ Totalmente Apta", totalmente_apta),
    ("🙂 Apta Moderado",   apta_moderado),
    ("⚠️ Precaución",      precaucion),
    ("🚨 No Aptas",        no_aptas),
    ("🤕 Con molestias",   con_molest),
]
render_kpi_row(kpis_well)

st.divider()

# ── Semáforo de readiness ──────────────────────────────────────────────────
st.subheader("Readiness individual — Último registro")

df_read_sorted = df_hoy.sort_values("readiness_index", ascending=False)

cards = []
for _, row in df_read_sorted.iterrows():
    zona  = row.get("readiness_zona", "Sin datos")
    cfg   = READINESS_CFG.get(zona, READINESS_CFG["Sin datos"])
    score = f"{row['readiness_index']:.2f}" if pd.notna(row["readiness_index"]) else "—"
    cards.append(
        f'<div class="cn-readiness-card" style="background:{cfg["bg"]}">'
        f'<div class="rc-icon">{cfg["icon"]}</div>'
        f'<div class="rc-name">{row["nombre"]}</div>'
        f'<div class="rc-score" style="color:{cfg["color"]}">{score}</div>'
        f'<div class="rc-zona" style="color:{cfg["color"]}; '
        f'background:rgba(255,255,255,0.07)">{zona}</div>'
        f'</div>'
    )

st.markdown('<div class="cn-readiness-grid">' + "".join(cards) + '</div>',
            unsafe_allow_html=True)

st.divider()

# ── ACWR Interno — Esfuerzo Percibido (RPE) ───────────────────────────────
st.subheader("ACWR Interno — Esfuerzo Percibido (RPE)")

n_registros = df["fecha"].nunique()
acwr_table_html(df_hoy, n_registros)

st.divider()

# ── Evolución TQR y RPE ────────────────────────────────────────────────────
st.subheader("Evolución TQR y RPE — Todas las jugadoras")
jugadoras  = sorted(df_filtrado["nombre"].unique())
sel_jug    = st.multiselect("Seleccioná jugadoras",
                             jugadoras, default=jugadoras[:4])
df_evol    = df_filtrado[df_filtrado["nombre"].isin(sel_jug)]

col_tqr, col_rpe = st.columns(2)

with col_tqr:
    fig_tqr = px.line(
        df_evol, x="fecha", y="tqr", color="nombre",
        markers=True,
        labels={"tqr": "TQR (1–10)", "fecha": ""},
        color_discrete_sequence=LINE_PALETTE,
    )
    fig_tqr.update_traces(line=dict(width=2.5), marker=dict(size=8))
    fig_tqr.add_hline(y=5, line_dash="dash", line_color="#FBBC04",
                      annotation_text="Umbral mínimo",
                      annotation_font_color="#FBBC04")
    fig_tqr.update_layout(**plotly_line_layout(340, "Recuperación (TQR)"))
    st.plotly_chart(fig_tqr, use_container_width=True)

with col_rpe:
    fig_rpe = px.line(
        df_evol, x="fecha", y="rpe", color="nombre",
        markers=True,
        labels={"rpe": "RPE (1–10)", "fecha": ""},
        color_discrete_sequence=LINE_PALETTE,
    )
    fig_rpe.update_traces(line=dict(width=2.5), marker=dict(size=8))
    fig_rpe.add_hline(y=8, line_dash="dash", line_color="#f87171",
                      annotation_text="Alerta RPE alto",
                      annotation_font_color="#f87171")
    fig_rpe.update_layout(**plotly_line_layout(340, "Esfuerzo Percibido (RPE)"))
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