# pages/05_perfil_jugadora.py
import streamlit as st
import pandas as pd
import plotly.express as px
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from settings import PROCESSED, WELLNESS_SHEET_ID, WELLNESS_SHEET_GID, ROSTER_SHEET_GID
from src.utils.auth import require_login
from src.loaders.wellness_loader import cargar_desde_sheets
from src.loaders.roster_loader import cargar_posiciones_desde_sheets
from src.metrics.wellness import calcular_readiness, calcular_tendencia_tqr, generar_alertas
from src.metrics.physical import calcular_acwr, calcular_intensidad_relativa, calcular_srpe
from src.ui.theme import inject_dashboard_css, plotly_line_layout, LINE_PALETTE, ZONE_CFG, home_button

st.set_page_config(page_title="Perfil de Jugadora", page_icon="🎯", layout="wide")

require_login()
inject_dashboard_css()
home_button()
st.markdown('<h1 style="text-align:center">🎯 Perfil de Jugadora</h1>', unsafe_allow_html=True)
st.markdown(
    '<p style="text-align:center; color:gray">'
    'Evolución individual — ACWR, wellness y sRPE en el tiempo</p>',
    unsafe_allow_html=True,
)
st.divider()

# ── Cargar datos ───────────────────────────────────────────────────────────
@st.cache_data
def cargar_gps():
    try:
        df = pd.read_parquet(PROCESSED / "gps_procesado.parquet")
        df = calcular_intensidad_relativa(df)
        return calcular_acwr(df, col_carga="player_load")
    except FileNotFoundError:
        return None

@st.cache_data(ttl=300)
def cargar_wellness():
    try:
        df = cargar_desde_sheets(WELLNESS_SHEET_ID, WELLNESS_SHEET_GID)
        df = calcular_readiness(df)
        df = calcular_tendencia_tqr(df)
        df = generar_alertas(df)
        return calcular_acwr(df, col_carga="rpe")
    except Exception:
        return None

@st.cache_data(ttl=3600)
def cargar_posiciones():
    try:
        return cargar_posiciones_desde_sheets(WELLNESS_SHEET_ID, ROSTER_SHEET_GID)
    except Exception:
        return None

df_gps  = cargar_gps()
df_well = cargar_wellness()
df_pos  = cargar_posiciones()

if df_gps is None and df_well is None:
    st.info("Sin datos de GPS ni de wellness disponibles todavía.")
    st.stop()

if df_gps is not None and df_well is not None:
    # Carga diaria (sumada) antes de cruzar con wellness — un partido tiene
    # 4 filas (Q1-Q4) el mismo día, y cruzar sin agregar duplicaría cada
    # registro de wellness de ese día una vez por cuarto.
    df_gps_diario = df_gps.groupby(["player_id", "fecha"], as_index=False)["duracion_min"].sum()
    df_well = calcular_srpe(df_well, df_gps_diario)

# ── Selector de jugadora ───────────────────────────────────────────────────
# El nombre se filtra por player_id, no por el texto "nombre": el export de
# Catapult guarda los nombres en mayúsculas ("AGUSTINA RODRIGUEZ") mientras
# que el roster y wellness usan formato normal — son strings distintos para
# la misma jugadora, pero normalizar_nombre() ya los hace coincidir en
# player_id, que es la clave real de cruce en todo el proyecto.
id_a_nombre = {}
for fuente in (df_pos, df_well, df_gps):
    if fuente is not None:
        id_a_nombre.update(
            fuente.drop_duplicates("player_id").set_index("player_id")["nombre"].to_dict()
        )

ids_gps   = set(df_gps["player_id"].unique())  if df_gps  is not None else set()
ids_well  = set(df_well["player_id"].unique()) if df_well is not None else set()
todos_ids = set(id_a_nombre) | ids_gps | ids_well

if not todos_ids:
    st.info("No hay jugadoras con datos cargados todavía.")
    st.stop()

player_ids = sorted(todos_ids, key=lambda pid: id_a_nombre.get(pid, pid))
jugadora_id = st.selectbox("Jugadora", player_ids,
                           format_func=lambda pid: id_a_nombre.get(pid, pid))

df_gps_jug  = (df_gps[df_gps["player_id"] == jugadora_id].sort_values("fecha")
               if df_gps is not None else None)
df_well_jug = (df_well[df_well["player_id"] == jugadora_id].sort_values("fecha")
               if df_well is not None else None)

sin_gps  = df_gps_jug is None or df_gps_jug.empty
sin_well = df_well_jug is None or df_well_jug.empty

if sin_gps and sin_well:
    st.info(f"{id_a_nombre.get(jugadora_id, jugadora_id)} todavía no tiene registros de GPS ni de wellness.")
    st.stop()

st.divider()

# ── ACWR en el tiempo ──────────────────────────────────────────────────────
st.subheader("ACWR — Externo (GPS) vs Interno (RPE)")

col_acwr_gps, col_acwr_rpe = st.columns(2)

with col_acwr_gps:
    if not sin_gps:
        fig = px.line(df_gps_jug, x="fecha", y="acwr", markers=True,
                      labels={"acwr": "ACWR (Player Load)", "fecha": ""})
        fig.update_traces(line=dict(width=2.5, color=LINE_PALETTE[0]), marker=dict(size=7))
        fig.add_hrect(y0=0.8, y1=1.3, fillcolor=ZONE_CFG["Óptimo"]["color"],
                      opacity=0.12, line_width=0)
        fig.update_layout(**plotly_line_layout(320, "ACWR Externo (GPS)"))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sin datos de GPS para esta jugadora.")

with col_acwr_rpe:
    if not sin_well:
        fig = px.line(df_well_jug, x="fecha", y="acwr", markers=True,
                      labels={"acwr": "ACWR (RPE)", "fecha": ""})
        fig.update_traces(line=dict(width=2.5, color=LINE_PALETTE[1]), marker=dict(size=7))
        fig.add_hrect(y0=0.8, y1=1.3, fillcolor=ZONE_CFG["Óptimo"]["color"],
                      opacity=0.12, line_width=0)
        fig.update_layout(**plotly_line_layout(320, "ACWR Interno (RPE)"))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sin datos de wellness para esta jugadora.")

st.caption("Banda sombreada: zona óptima 0.8–1.3 (Hulin et al., 2016).")

st.divider()

# ── TQR / RPE / sRPE en el tiempo ──────────────────────────────────────────
st.subheader("Recuperación, esfuerzo y sRPE")

if not sin_well:
    col_tqr_rpe, col_srpe = st.columns(2)

    with col_tqr_rpe:
        fig = px.line(df_well_jug, x="fecha", y=["tqr", "rpe"], markers=True,
                      labels={"value": "Escala 1–10", "fecha": "", "variable": ""},
                      color_discrete_sequence=[LINE_PALETTE[2], LINE_PALETTE[3]])
        fig.update_traces(line=dict(width=2.5), marker=dict(size=7))
        fig.update_layout(**plotly_line_layout(320, "TQR vs RPE"))
        st.plotly_chart(fig, use_container_width=True)

    with col_srpe:
        if df_well_jug["srpe"].notna().any():
            fig = px.line(df_well_jug, x="fecha", y="srpe", markers=True,
                          labels={"srpe": "sRPE (UA)", "fecha": ""})
            fig.update_traces(line=dict(width=2.5, color=LINE_PALETTE[4]), marker=dict(size=7))
            fig.update_layout(**plotly_line_layout(320, "sRPE (RPE × duración)"))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info(
                "sRPE requiere sesiones GPS con duración registrada en las "
                "mismas fechas que los registros de wellness de esta jugadora."
            )
else:
    st.info("Sin datos de wellness para esta jugadora.")

st.divider()

# ── Molestias reportadas ───────────────────────────────────────────────────
st.subheader("🤕 Molestias reportadas")

if not sin_well:
    molestias = df_well_jug[df_well_jug["molestia_flag"]][["fecha", "molestia"]]
    if len(molestias) > 0:
        st.dataframe(molestias.reset_index(drop=True), use_container_width=True, hide_index=True)
    else:
        st.success("✅ Sin molestias reportadas")
else:
    st.info("Sin datos de wellness para esta jugadora.")
