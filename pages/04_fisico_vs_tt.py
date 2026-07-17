# pages/04_fisico_vs_tt.py
import streamlit as st
import pandas as pd
import plotly.express as px
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from settings import (
    PROCESSED, TIPOS_SESION, WELLNESS_SHEET_ID, ROSTER_SHEET_GID, SESIONES_SHEET_GID,
    LOGO_PATH,
)
from src.utils.auth import require_login
from src.loaders.roster_loader import cargar_posiciones_desde_sheets
from src.loaders.sesiones_loader import cargar_sesiones_desde_sheets, orden_match_day
from src.metrics.physical import calcular_intensidad_relativa, resumen_carga_equipo
from src.ui.theme import (
    inject_dashboard_css, compare_card_html, compare_rows_html, home_button, page_header,
    plotly_line_layout, COMPARE_COLOR_A, COMPARE_COLOR_B, init_persistent, save_persistent,
)

st.set_page_config(page_title="Físico vs Técnico-Táctico", page_icon=str(LOGO_PATH), layout="wide")

require_login()
inject_dashboard_css()
home_button()
page_header("Físico vs Técnico-Táctico", "Comparativa de demanda física entre tipos de sesión",
            icon="⚖️", color="#F9AB00")
st.divider()

# ── Cargar datos ───────────────────────────────────────────────────────────
@st.cache_data
def cargar_datos():
    df = pd.read_parquet(PROCESSED / "gps_procesado.parquet")
    if "tipo_sesion" not in df.columns:
        df["tipo_sesion"] = TIPOS_SESION[0]
    if "cuarto" not in df.columns:
        df["cuarto"] = "—"
    return calcular_intensidad_relativa(df)

try:
    df = cargar_datos()
except FileNotFoundError:
    df = pd.DataFrame()

TIPO_A, TIPO_B = TIPOS_SESION[0], TIPOS_SESION[1]  # Físico, Técnico-Táctico
df = df[df["tipo_sesion"].isin([TIPO_A, TIPO_B])] if not df.empty else df

hay_a = not df.empty and (df["tipo_sesion"] == TIPO_A).any()
hay_b = not df.empty and (df["tipo_sesion"] == TIPO_B).any()

if not (hay_a and hay_b):
    st.info(
        f"Todavía no hay suficientes datos para comparar — necesitás al menos una "
        f"sesión de tipo «{TIPO_A}» y una de tipo «{TIPO_B}» cargadas en Carga Física."
    )
    st.stop()

# ── Filtros ────────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def cargar_posiciones():
    try:
        return cargar_posiciones_desde_sheets(WELLNESS_SHEET_ID, ROSTER_SHEET_GID)
    except Exception:
        return None

df_pos = cargar_posiciones()
if df_pos is not None:
    df = df.merge(df_pos[["player_id", "posicion"]], on="player_id", how="left")

@st.cache_data(ttl=3600)
def cargar_sesiones():
    try:
        return cargar_sesiones_desde_sheets(WELLNESS_SHEET_ID, SESIONES_SHEET_GID)
    except Exception:
        return None

df_sesiones = cargar_sesiones()
if df_sesiones is not None:
    df = df.merge(df_sesiones[["fecha", "match_day"]], on="fecha", how="left")
    df["match_day"] = df["match_day"].fillna("Sin clasificar")

col_fecha, col_pos, col_md, col_modo = st.columns([1.3, 1, 1, 1.2])

fechas_disp = sorted(df["fecha"].unique())
with col_fecha:
    init_persistent("tt_rango_fechas", (fechas_disp[0], fechas_disp[-1]))
    rango = st.date_input(
        "Rango de fechas",
        min_value=fechas_disp[0],
        max_value=fechas_disp[-1],
        format="DD/MM/YYYY",
        key="tt_rango_fechas",
        on_change=lambda: save_persistent("tt_rango_fechas"),
    )

with col_pos:
    if df_pos is not None:
        posiciones = sorted(df_pos["posicion"].dropna().unique())
        st.markdown(
            '<p style="font-size:0.875rem; color:inherit; margin-bottom:0.25rem">Posición</p>',
            unsafe_allow_html=True,
        )
        with st.popover("Posición", use_container_width=True):
            init_persistent("tt_pos_sel", posiciones)
            pos_sel = st.multiselect(
                "Posición", posiciones, label_visibility="collapsed",
                key="tt_pos_sel",
                on_change=lambda: save_persistent("tt_pos_sel"),
            )
    else:
        pos_sel = None

with col_md:
    if df_sesiones is not None:
        mds_disponibles = sorted(df["match_day"].dropna().unique(), key=orden_match_day)
        st.markdown(
            '<p style="font-size:0.875rem; color:inherit; margin-bottom:0.25rem">Match Day</p>',
            unsafe_allow_html=True,
        )
        with st.popover("Match Day", use_container_width=True):
            init_persistent("tt_md_sel", mds_disponibles)
            md_sel = st.multiselect(
                "Match Day", mds_disponibles, label_visibility="collapsed",
                key="tt_md_sel",
                on_change=lambda: save_persistent("tt_md_sel"),
            )
    else:
        md_sel = None

with col_modo:
    init_persistent("tt_modo", "Promedio por sesión")
    modo = st.radio("Ver", ["Promedio por sesión", "Total acumulado"], horizontal=True,
                     key="tt_modo", on_change=lambda: save_persistent("tt_modo"))

if len(rango) != 2:
    st.info("Seleccioná un rango de fechas completo (desde y hasta).")
    st.stop()

desde, hasta = rango
df = df[(df["fecha"] >= desde) & (df["fecha"] <= hasta)]
if pos_sel is not None:
    df = df[df["posicion"].isin(pos_sel)]
if md_sel is not None:
    df = df[df["match_day"].isin(md_sel)]

hay_a = (df["tipo_sesion"] == TIPO_A).any()
hay_b = (df["tipo_sesion"] == TIPO_B).any()
if not (hay_a and hay_b):
    st.info("No hay sesiones de los dos tipos dentro de ese rango de fechas, posiciones y Match Day.")
    st.stop()

n_fis = df[df["tipo_sesion"] == TIPO_A]["fecha"].nunique()
n_tt  = df[df["tipo_sesion"] == TIPO_B]["fecha"].nunique()
st.caption(f"Basado en {n_fis} sesión/es física/s y {n_tt} sesión/es técnico-táctica/s, entre "
           f"{desde.strftime('%d/%m/%Y')} y {hasta.strftime('%d/%m/%Y')}.")

st.divider()

# ── Comparativa Físico vs Técnico-Táctico ──────────────────────────────────
COMPARAR_METRICAS = [
    ("Distancia total", "distancia_total", "{:,.0f} m"),
    ("Player Load",     "player_load",     "{:.1f}"),
    ("HSR Distance",    "hsr",             "{:.0f} m"),
    ("Sprints",         "sprints",         "{:.0f}"),
    ("Vel. Máx",        "vel_max_kmh",     "{:.1f} km/h"),
    ("Dist/min",        "dist_min",        "{:.1f} m/min"),
]
# Distancia, HSR, Dist/min y Vel. Máx siempre se muestran en promedio por
# sesión (Vel. Máx además siempre como pico, nunca suma — 10 sesiones a
# 25 km/h no son "250 km/h"). Solo Player Load y Sprints, que sí son
# acumuladores de carga/conteo, siguen el toggle Promedio/Total.
COLS_SIEMPRE_PROMEDIO = ["distancia_total", "hsr", "dist_min"]
COLS_SEGUN_MODO       = ["player_load", "sprints"]

def _calcular_agregado(df_tipo: pd.DataFrame) -> pd.Series:
    agregado = df_tipo[COLS_SIEMPRE_PROMEDIO].mean()
    agregado["vel_max_kmh"] = df_tipo["vel_max_kmh"].max()
    for c in COLS_SEGUN_MODO:
        agregado[c] = df_tipo[c].sum() if modo == "Total acumulado" else df_tipo[c].mean()
    return agregado

promedio_a = _calcular_agregado(df[df["tipo_sesion"] == TIPO_A])
promedio_b = _calcular_agregado(df[df["tipo_sesion"] == TIPO_B])

col_card_a, col_rows, col_card_b = st.columns([1, 2.2, 1])

with col_card_a:
    st.markdown(compare_card_html("🏃", TIPO_A, COMPARE_COLOR_A), unsafe_allow_html=True)

with col_rows:
    st.markdown(compare_rows_html(COMPARAR_METRICAS, promedio_a, promedio_b,
                                   COMPARE_COLOR_A, COMPARE_COLOR_B),
                unsafe_allow_html=True)

with col_card_b:
    st.markdown(compare_card_html("🥅", TIPO_B, COMPARE_COLOR_B), unsafe_allow_html=True)

nota_modo = (
    "Player Load y Sprints muestran el total acumulado del período; "
    "Distancia, HSR, Dist/min y Vel. Máx siempre se muestran en promedio por sesión "
    "(Vel. Máx además siempre como pico)."
    if modo == "Total acumulado"
    else "Promedio por sesión en el período, equipo completo."
)
st.caption(
    "Cada métrica se compara en su propia escala (barra más larga = valor más alto "
    f"entre los dos tipos de sesión). {nota_modo}"
)

st.divider()

# ── Evolución temporal ───────────────────────────────────────────────────────
st.subheader("Evolución en el tiempo")

resumen_a = resumen_carga_equipo(df[df["tipo_sesion"] == TIPO_A], col_carga="player_load")
resumen_a["tipo_sesion"] = TIPO_A
resumen_b = resumen_carga_equipo(df[df["tipo_sesion"] == TIPO_B], col_carga="player_load")
resumen_b["tipo_sesion"] = TIPO_B
df_evolucion = pd.concat([resumen_a, resumen_b], ignore_index=True)

fig_evol = px.line(
    df_evolucion, x="fecha", y="media", color="tipo_sesion",
    markers=True,
    labels={"media": "Player Load medio", "fecha": "", "tipo_sesion": ""},
    color_discrete_map={TIPO_A: COMPARE_COLOR_A, TIPO_B: COMPARE_COLOR_B},
)
fig_evol.update_traces(line=dict(width=2.5), marker=dict(size=8))
fig_evol.update_layout(**plotly_line_layout(360))
st.plotly_chart(fig_evol, use_container_width=True)
st.caption(
    "Evolución sesión a sesión del Player Load medio del equipo, dentro del "
    "rango de fechas seleccionado arriba — a diferencia de la comparativa de "
    "barras (que promedia todo el período en un solo valor), acá se ve la "
    "tendencia día a día."
)
