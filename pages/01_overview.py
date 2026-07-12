# pages/01_overview.py
import streamlit as st
import pandas as pd
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from settings import PROCESSED, WELLNESS_SHEET_ID, WELLNESS_SHEET_GID, ROSTER_SHEET_GID
from src.utils.auth import require_login
from src.loaders.wellness_loader import cargar_desde_sheets
from src.loaders.roster_loader import cargar_posiciones_desde_sheets
from src.metrics.wellness import (
    calcular_readiness, calcular_tendencia_tqr, generar_alertas,
)
from src.metrics.physical import calcular_acwr, calcular_intensidad_relativa

st.set_page_config(page_title="Overview", page_icon="🏑", layout="wide")

require_login()

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

# ── Estilos compartidos ────────────────────────────────────────────────────
BG_CARD = "linear-gradient(135deg, #0f2b5b 0%, #1a3a6b 60%, #1e4d8c 100%)"

st.markdown("""
<style>
/* KPI cards */
.ov-kpi-grid { display:flex; justify-content:center; gap:14px; flex-wrap:wrap; margin-bottom:4px; }
.ov-kpi-card {
    background: linear-gradient(135deg, #0f2b5b 0%, #1a3a6b 60%, #1e4d8c 100%);
    border-radius:14px; padding:18px 28px; text-align:center;
    min-width:130px; box-shadow:0 4px 15px rgba(0,0,0,0.3);
}
.ov-kpi-card .lbl { font-size:0.72rem; color:#93c5fd; text-transform:uppercase;
                    letter-spacing:0.05em; margin-bottom:5px; }
.ov-kpi-card .val { font-size:1.7rem; font-weight:800; color:#fff; }

/* ACWR table */
.acwr-table { width:100%; border-collapse:collapse; }
.acwr-table th { font-size:0.72rem; color:#93c5fd; text-transform:uppercase;
                 letter-spacing:0.05em; padding:8px 12px; text-align:left;
                 border-bottom:1px solid #1a2f5a; }
.acwr-table td { padding:9px 12px; font-size:0.88rem; color:#e2e8f0;
                 border-bottom:1px solid #0f2040; }
.acwr-badge { border-radius:20px; padding:3px 12px; font-size:0.75rem;
              font-weight:700; display:inline-block; }

/* Alertas */
.alert-row {
    background:#1a0a0a; border-left:4px solid #EA4335;
    border-radius:8px; padding:10px 16px; margin-bottom:8px;
    display:flex; align-items:center; gap:14px;
}
.alert-row .ar-name { font-weight:700; color:#fca5a5; font-size:0.9rem; }
.alert-row .ar-detail { font-size:0.8rem; color:#fecaca; }
.alert-tag { background:#7f1d1d; color:#fca5a5; border-radius:20px;
             padding:2px 8px; font-size:0.72rem; font-weight:600; margin-right:4px; }

/* Molestias */
.molestia-row {
    background:#1a1000; border-left:4px solid #FBBC04;
    border-radius:8px; padding:10px 16px; margin-bottom:8px;
}
.molestia-row .mo-name   { font-weight:700; color:#fde68a; font-size:0.88rem; }
.molestia-row .mo-detail { font-size:0.8rem; color:#fef3c7; margin-top:2px; }
</style>
""", unsafe_allow_html=True)

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
    st.markdown(
        '<div class="ov-kpi-grid">' + "".join(
            f'<div class="ov-kpi-card"><div class="lbl">{l}</div>'
            f'<div class="val">{v}</div></div>'
            for l, v in kpis
        ) + '</div>',
        unsafe_allow_html=True,
    )
    st.divider()

# ── Cuerpo principal: ACWR Interno (RPE) + ACWR Externo (GPS) ─────────────
col_acwr_rpe, col_acwr_gps = st.columns([1.1, 0.9], gap="large")

ACWR_CFG = {
    "Óptimo":     {"color": "#34A853", "bg": "#0a2e14"},
    "Precaución": {"color": "#FBBC04", "bg": "#2e2200"},
    "Riesgo Alto":{"color": "#EA4335", "bg": "#2e0a08"},
    "Subcarga":   {"color": "#38bdf8", "bg": "#0c2a3a"},
    "Sin datos":  {"color": "#6b7280", "bg": "#1f2937"},
}

def _tabla_acwr(df_last, n_sesiones):
    if n_sesiones < 4:
        st.caption(f"⚠️ Solo {n_sesiones} registro/s — el ACWR gana precisión a partir de 4+.")

    rows_html = ""
    for _, row in df_last.sort_values("acwr", ascending=False).iterrows():
        zona = row.get("zona_acwr", "Sin datos")
        cfg  = ACWR_CFG.get(zona, ACWR_CFG["Sin datos"])
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

# ── ACWR Interno (RPE — esfuerzo percibido) ────────────────────────────────
with col_acwr_rpe:
    st.subheader("ACWR Interno — Esfuerzo Percibido (RPE)")
    if df_hoy is not None:
        _tabla_acwr(df_hoy, df_well["fecha"].nunique())
    else:
        st.info("Sin datos de wellness disponibles.")

# ── ACWR Externo (GPS — carga física) ──────────────────────────────────────
with col_acwr_gps:
    st.subheader("ACWR Externo — GPS (Player Load)")
    if df_gps_last is not None:
        _tabla_acwr(df_gps_last, df_gps["fecha"].nunique())
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
                f'<div class="molestia-row">'
                f'<div class="mo-name">⚠️ {row["nombre"]} <span style="font-weight:400;color:#93c5fd;font-size:0.75rem">({fecha_str})</span></div>'
                f'<div class="mo-detail">{row["molestia"]}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
    else:
        st.success("✅ Sin molestias reportadas")
else:
    st.info("Sin datos de wellness disponibles.")
