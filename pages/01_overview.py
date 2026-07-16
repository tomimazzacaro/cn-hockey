# pages/01_overview.py
import streamlit as st
import pandas as pd
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from settings import PROCESSED, WELLNESS_SHEET_ID, WELLNESS_SHEET_GID, ROSTER_SHEET_GID, LOGO_PATH
from src.utils.auth import require_login
from src.loaders.wellness_loader import cargar_desde_sheets
from src.loaders.roster_loader import cargar_posiciones_desde_sheets
from src.metrics.wellness import (
    calcular_readiness, calcular_tendencia_tqr, generar_alertas,
)
from src.metrics.physical import calcular_acwr, calcular_intensidad_relativa
from src.ui.theme import inject_dashboard_css, render_kpi_row, acwr_table_html, home_button

st.set_page_config(page_title="Overview", page_icon=str(LOGO_PATH), layout="wide")

require_login()
inject_dashboard_css()
home_button()

# ── Cargar datos ───────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def cargar_wellness():
    try:
        df = cargar_desde_sheets(WELLNESS_SHEET_ID, WELLNESS_SHEET_GID)
        df = calcular_readiness(df)
        df = calcular_tendencia_tqr(df)
        df = generar_alertas(df)
        df = calcular_acwr(df, col_carga="rpe")
        return df
    except Exception:
        return None

@st.cache_data
def cargar_gps():
    try:
        df = pd.read_parquet(PROCESSED / "gps_procesado.parquet")
        df = calcular_intensidad_relativa(df)
        df = calcular_acwr(df, col_carga="player_load")
        return df
    except Exception:
        return None

@st.cache_data(ttl=3600)
def cargar_posiciones():
    try:
        return cargar_posiciones_desde_sheets(WELLNESS_SHEET_ID, ROSTER_SHEET_GID)
    except Exception:
        return None

df_well = cargar_wellness()
df_gps  = cargar_gps()
df_pos  = cargar_posiciones()

# Último registro por jugadora
df_hoy  = (df_well.sort_values("fecha").groupby("player_id").last().reset_index()
           if df_well is not None else None)
df_gps_last = (df_gps.sort_values("fecha").groupby("player_id").last().reset_index()
               if df_gps is not None else None)

if df_pos is not None:
    if df_hoy is not None:
        df_hoy = df_hoy.merge(df_pos[["player_id", "posicion"]], on="player_id", how="left")
    if df_gps_last is not None:
        df_gps_last = df_gps_last.merge(df_pos[["player_id", "posicion"]], on="player_id", how="left")

# ── Header ─────────────────────────────────────────────────────────────────
fecha_well = df_hoy["fecha"].max() if df_hoy is not None else "—"
fecha_gps  = df_gps_last["fecha"].max() if df_gps_last is not None else "—"
fmt = lambda f: f.strftime("%d/%m/%Y") if hasattr(f, "strftime") else str(f)

st.markdown('<h1 style="text-align:center">🏑 Vista General</h1>', unsafe_allow_html=True)
st.markdown(
    f'<p style="text-align:center; color:#93c5fd; font-size:0.85rem">'
    f'Wellness: {fmt(fecha_well)} &nbsp;·&nbsp; GPS: {fmt(fecha_gps)}</p>',
    unsafe_allow_html=True,
)
st.divider()

# ── Filtro por posición ────────────────────────────────────────────────────
if df_pos is not None:
    posiciones = sorted(df_pos["posicion"].dropna().unique())
    col_pos, _ = st.columns([1, 3])
    with col_pos:
        st.markdown(
            '<p style="font-size:0.875rem; color:inherit; margin-bottom:0.25rem">Posición</p>',
            unsafe_allow_html=True,
        )
        with st.popover("Posición", use_container_width=True):
            pos_sel = st.multiselect(
                "Posición", posiciones, default=posiciones, label_visibility="collapsed"
            )

    if df_hoy is not None:
        df_hoy = df_hoy[df_hoy["posicion"].isin(pos_sel)]
    if df_gps_last is not None:
        df_gps_last = df_gps_last[df_gps_last["posicion"].isin(pos_sel)]

    st.divider()

# ── KPIs globales ──────────────────────────────────────────────────────────
if df_hoy is not None:
    totalmente_apta = (df_hoy["readiness_zona"] == "Totalmente Apta").sum()
    apta_moderado   = (df_hoy["readiness_zona"] == "Apta Moderado").sum()
    precaucion      = (df_hoy["readiness_zona"] == "Precaución").sum()
    no_aptas        = (df_hoy["readiness_zona"] == "No Apta").sum()
    molest_n        = df_hoy["molestia_flag"].sum()

    kpis = [
        ("✅ Totalmente Apta", totalmente_apta),
        ("🙂 Apta Moderado",   apta_moderado),
        ("⚠️ Precaución",      precaucion),
        ("🚨 No Aptas",        no_aptas),
        ("🤕 Molestias",       molest_n),
    ]
    render_kpi_row(kpis)
    st.divider()

# ── Cuerpo principal: ACWR Interno (RPE) + ACWR Externo (GPS) ─────────────
col_acwr_rpe, col_acwr_gps = st.columns([1.1, 0.9], gap="large")

# ── ACWR Interno (RPE — esfuerzo percibido) ────────────────────────────────
with col_acwr_rpe:
    st.subheader("ACWR Interno — Esfuerzo Percibido (RPE)")
    if df_hoy is not None:
        acwr_table_html(df_hoy, df_well["fecha"].nunique())
    else:
        st.info("Sin datos de wellness disponibles.")

# ── ACWR Externo (GPS — carga física) ──────────────────────────────────────
with col_acwr_gps:
    st.subheader("ACWR Externo — GPS (Player Load)")
    if df_gps_last is not None:
        acwr_table_html(df_gps_last, df_gps["fecha"].nunique())
    else:
        st.info("Sin datos de GPS disponibles.")

st.divider()

# ── Molestias físicas ──────────────────────────────────────────────────────
st.subheader("🤕 Molestias reportadas")
if df_hoy is not None:
    molestias = df_hoy[df_hoy["molestia_flag"]][["nombre", "fecha", "molestia"]]
    if len(molestias) > 0:
        for _, row in molestias.iterrows():
            fecha_str = fmt(row["fecha"])
            st.markdown(
                f'<div class="cn-molestia-row">'
                f'<div class="mo-name">⚠️ {row["nombre"]} <span style="font-weight:400;color:#93c5fd;font-size:0.75rem">({fecha_str})</span></div>'
                f'<div class="mo-detail">{row["molestia"]}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
    else:
        st.success("✅ Sin molestias reportadas")
else:
    st.info("Sin datos de wellness disponibles.")
