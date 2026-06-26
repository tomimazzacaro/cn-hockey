# pages/01_overview.py
import streamlit as st
import pandas as pd
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from settings import PROCESSED
from src.utils.auth import require_login
from src.metrics.wellness import (
    calcular_readiness, calcular_tendencia_tqr, generar_alertas,
)
from src.metrics.physical import calcular_acwr, calcular_intensidad_relativa

st.set_page_config(page_title="Overview", page_icon="🏑", layout="wide")

require_login()

# ── Cargar datos ───────────────────────────────────────────────────────────
@st.cache_data
def cargar_wellness():
    try:
        df = pd.read_parquet(PROCESSED / "wellness_procesado.parquet")
        df = calcular_readiness(df)
        df = calcular_tendencia_tqr(df)
        df = generar_alertas(df)
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

df_well = cargar_wellness()
df_gps  = cargar_gps()

# Último registro por jugadora
df_hoy  = (df_well.sort_values("fecha").groupby("player_id").last().reset_index()
           if df_well is not None else None)
df_gps_last = (df_gps.sort_values("fecha").groupby("player_id").last().reset_index()
               if df_gps is not None else None)

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

/* Readiness cards */
.rc-grid { display:flex; flex-wrap:wrap; gap:10px; justify-content:flex-start; }
.rc-card {
    border-radius:12px; padding:14px 16px; text-align:center;
    min-width:120px; flex:1 1 120px; max-width:150px;
    box-shadow:0 3px 10px rgba(0,0,0,0.3);
    border:1px solid rgba(255,255,255,0.07);
}
.rc-card .rc-icon  { font-size:1.2rem; margin-bottom:3px; }
.rc-card .rc-name  { font-size:0.68rem; color:#cbd5e1; text-transform:uppercase;
                     letter-spacing:0.04em; margin-bottom:7px; }
.rc-card .rc-score { font-size:1.6rem; font-weight:800; margin-bottom:3px; }
.rc-card .rc-zona  { font-size:0.7rem; font-weight:600; border-radius:20px;
                     padding:2px 10px; display:inline-block; }

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

# ── KPIs globales ──────────────────────────────────────────────────────────
if df_hoy is not None:
    aptas      = (df_hoy["readiness_zona"] == "Apta").sum()
    precaucion = (df_hoy["readiness_zona"] == "Precaución").sum()
    no_aptas   = (df_hoy["readiness_zona"] == "No Apta").sum()
    molest_n   = df_hoy["molestia_flag"].sum()

    kpis = [
        ("✅ Aptas",         aptas),
        ("⚠️ Precaución",    precaucion),
        ("🚨 No Aptas",      no_aptas),
        ("🤕 Molestias",     molest_n),
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

# ── Cuerpo principal: Readiness + ACWR ────────────────────────────────────
col_read, col_acwr = st.columns([1.1, 0.9], gap="large")

# ── Readiness semáforo ─────────────────────────────────────────────────────
ZONA_CFG = {
    "Apta":       {"color": "#34A853", "bg": "#0a2e14", "icon": "✅"},
    "Precaución": {"color": "#FBBC04", "bg": "#2e2200", "icon": "⚠️"},
    "No Apta":    {"color": "#EA4335", "bg": "#2e0a08", "icon": "🚨"},
    "Sin datos":  {"color": "#6b7280", "bg": "#1f2937", "icon": "—"},
}

with col_read:
    st.subheader("Readiness — Estado del plantel")
    if df_hoy is not None:
        cards = []
        for _, row in df_hoy.sort_values("readiness_index", ascending=False).iterrows():
            zona  = row.get("readiness_zona", "Sin datos")
            cfg   = ZONA_CFG.get(zona, ZONA_CFG["Sin datos"])
            score = f"{row['readiness_index']:.1f}" if pd.notna(row["readiness_index"]) else "—"
            cards.append(
                f'<div class="rc-card" style="background:{cfg["bg"]}">'
                f'<div class="rc-icon">{cfg["icon"]}</div>'
                f'<div class="rc-name">{row["nombre"]}</div>'
                f'<div class="rc-score" style="color:{cfg["color"]}">{score}</div>'
                f'<div class="rc-zona" style="color:{cfg["color"]};'
                f'background:rgba(255,255,255,0.07)">{zona}</div>'
                f'</div>'
            )
        st.markdown('<div class="rc-grid">' + "".join(cards) + '</div>',
                    unsafe_allow_html=True)
    else:
        st.info("Sin datos de wellness disponibles.")

# ── ACWR ──────────────────────────────────────────────────────────────────
ACWR_CFG = {
    "Óptimo":     {"color": "#34A853", "bg": "#0a2e14"},
    "Precaución": {"color": "#FBBC04", "bg": "#2e2200"},
    "Riesgo Alto":{"color": "#EA4335", "bg": "#2e0a08"},
    "Subcarga":   {"color": "#38bdf8", "bg": "#0c2a3a"},
    "Sin datos":  {"color": "#6b7280", "bg": "#1f2937"},
}

with col_acwr:
    st.subheader("ACWR — Ratio Carga Aguda:Crónica")
    if df_gps_last is not None:
        n_sesiones = df_gps["fecha"].nunique()
        if n_sesiones < 4:
            st.caption(f"⚠️ Solo {n_sesiones} sesión/es registrada/s — el ACWR gana precisión a partir de 4+ sesiones.")

        rows_html = ""
        for _, row in df_gps_last.sort_values("acwr", ascending=False).iterrows():
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
