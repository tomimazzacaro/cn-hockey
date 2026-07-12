# pages/04_fisico_vs_tt.py
import streamlit as st
import pandas as pd
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from settings import (
    PROCESSED, TIPOS_SESION, WELLNESS_SHEET_ID, ROSTER_SHEET_GID, SESIONES_SHEET_GID,
)
from src.utils.auth import require_login
from src.loaders.roster_loader import cargar_posiciones_desde_sheets
from src.loaders.sesiones_loader import cargar_sesiones_desde_sheets, orden_match_day
from src.metrics.physical import calcular_intensidad_relativa

st.set_page_config(page_title="Físico vs Técnico-Táctico", page_icon="⚖️", layout="wide")

require_login()
st.markdown('<h1 style="text-align:center">⚖️ Físico vs Técnico-Táctico</h1>', unsafe_allow_html=True)
st.markdown(
    '<p style="text-align:center; color:gray">'
    'Comparativa de demanda física entre tipos de sesión</p>',
    unsafe_allow_html=True,
)
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
    rango = st.date_input(
        "Rango de fechas",
        value=(fechas_disp[0], fechas_disp[-1]),
        min_value=fechas_disp[0],
        max_value=fechas_disp[-1],
        format="DD/MM/YYYY",
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

with col_md:
    if df_sesiones is not None:
        mds_disponibles = sorted(df["match_day"].dropna().unique(), key=orden_match_day)
        st.markdown(
            '<p style="font-size:0.875rem; color:inherit; margin-bottom:0.25rem">Match Day</p>',
            unsafe_allow_html=True,
        )
        with st.popover("Match Day", use_container_width=True):
            md_sel = st.multiselect(
                "Match Day", mds_disponibles, default=mds_disponibles, label_visibility="collapsed"
            )
    else:
        md_sel = None

with col_modo:
    modo = st.radio("Ver", ["Promedio por sesión", "Total acumulado"], horizontal=True)

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
COLOR_A = "#3987e5"   # azul  — misma familia que la comparativa de jugadoras
COLOR_B = "#199e70"   # verde azulado

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

st.markdown("""
<style>
.cmp-card {
    border-radius: 14px;
    padding: 22px 12px;
    text-align: center;
    background: linear-gradient(135deg, #0f2b5b 0%, #1a3a6b 60%, #1e4d8c 100%);
    border-top: 4px solid var(--accent);
    box-shadow: 0 4px 15px rgba(0,0,0,0.3);
}
.cmp-avatar { font-size: 2.4rem; margin-bottom: 8px; }
.cmp-name   { font-size: 0.92rem; font-weight: 700; color: #fff;
              text-transform: uppercase; letter-spacing: 0.02em; }

.cmp-row { display: flex; align-items: center; gap: 8px; margin-bottom: 14px; }
.cmp-value { width: 72px; font-size: 0.82rem; font-weight: 700; color: #e2e8f0; }
.cmp-value-a { text-align: right; }
.cmp-value-b { text-align: left; }
.cmp-label  {
    width: 130px; flex-shrink: 0; text-align: center;
    font-size: 0.74rem; color: #93c5fd; text-transform: uppercase;
    letter-spacing: 0.04em;
}
.cmp-bar-a, .cmp-bar-b {
    flex: 1; display: flex; height: 12px;
    background: #16294f; border-radius: 6px;
}
.cmp-bar-a { justify-content: flex-end; }
.cmp-bar-b { justify-content: flex-start; }
.cmp-fill-a, .cmp-fill-b { height: 100%; }
.cmp-fill-a { background: var(--color-a); border-radius: 4px 0 0 4px; }
.cmp-fill-b { background: var(--color-b); border-radius: 0 4px 4px 0; }
</style>
""", unsafe_allow_html=True)

col_card_a, col_rows, col_card_b = st.columns([1, 2.2, 1])

with col_card_a:
    st.markdown(
        f'<div class="cmp-card" style="--accent:{COLOR_A}">'
        f'<div class="cmp-avatar">🏃</div>'
        f'<div class="cmp-name">{TIPO_A}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

with col_rows:
    rows_html = ""
    for label, col, fmt in COMPARAR_METRICAS:
        val_a = promedio_a.get(col)
        val_b = promedio_b.get(col)
        val_a = 0.0 if pd.isna(val_a) else float(val_a)
        val_b = 0.0 if pd.isna(val_b) else float(val_b)
        maximo = max(val_a, val_b, 1e-9)
        pct_a  = (val_a / maximo) * 100
        pct_b  = (val_b / maximo) * 100

        rows_html += (
            f'<div class="cmp-row">'
            f'<div class="cmp-value cmp-value-a">{fmt.format(val_a)}</div>'
            f'<div class="cmp-bar-a"><div class="cmp-fill-a" '
            f'style="width:{pct_a:.1f}%; --color-a:{COLOR_A}"></div></div>'
            f'<div class="cmp-label">{label}</div>'
            f'<div class="cmp-bar-b"><div class="cmp-fill-b" '
            f'style="width:{pct_b:.1f}%; --color-b:{COLOR_B}"></div></div>'
            f'<div class="cmp-value cmp-value-b">{fmt.format(val_b)}</div>'
            f'</div>'
        )
    st.markdown(rows_html, unsafe_allow_html=True)

with col_card_b:
    st.markdown(
        f'<div class="cmp-card" style="--accent:{COLOR_B}">'
        f'<div class="cmp-avatar">🥅</div>'
        f'<div class="cmp-name">{TIPO_B}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

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
