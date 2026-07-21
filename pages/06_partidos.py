# pages/06_partidos.py
import re
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from settings import (
    PROCESSED, WELLNESS_SHEET_ID, ROSTER_SHEET_GID, SESIONES_SHEET_GID,
    TIPOS_SESION, CUARTOS, LOGO_PATH,
)
from src.utils.auth import require_login
from src.utils.helpers import normalizar_0_10
from src.loaders.roster_loader import cargar_posiciones_desde_sheets
from src.loaders.sesiones_loader import cargar_sesiones_desde_sheets
from src.metrics.physical import calcular_intensidad_relativa, agregar_partidos_completos
from src.ui.theme import (
    inject_dashboard_css, home_button, plotly_radar_layout, plotly_grouped_bar_layout,
    LINE_PALETTE, BAR_CATEGORICAL_PALETTE, page_header, init_persistent, save_persistent, ICONS,
)

st.set_page_config(page_title="Partidos", page_icon=str(LOGO_PATH), layout="wide")

require_login()
inject_dashboard_css()
home_button()
page_header("Partidos", "Radar comparativo de métricas GPS entre partidos",
            icon=ICONS["trofeo"], color="#EF5350")
st.divider()

# ── Cargar datos ───────────────────────────────────────────────────────────
@st.cache_data
def cargar_gps():
    try:
        df = pd.read_parquet(PROCESSED / "gps_procesado.parquet")
        return calcular_intensidad_relativa(df)
    except FileNotFoundError:
        return None

@st.cache_data(ttl=3600)
def cargar_posiciones():
    try:
        return cargar_posiciones_desde_sheets(WELLNESS_SHEET_ID, ROSTER_SHEET_GID)
    except Exception:
        return None

@st.cache_data(ttl=3600)
def cargar_sesiones():
    try:
        return cargar_sesiones_desde_sheets(WELLNESS_SHEET_ID, SESIONES_SHEET_GID)
    except Exception:
        return None

df_gps       = cargar_gps()
df_pos       = cargar_posiciones()
df_sesiones  = cargar_sesiones()

if df_gps is None:
    st.info("Sin datos de GPS disponibles todavía.")
    st.stop()

df_partidos = agregar_partidos_completos(df_gps, tipo_partido=TIPOS_SESION[2])
if df_partidos.empty:
    st.info(
        "Todavía no hay partidos cargados. Subí sesiones de tipo «Partido» "
        "(con sus cuartos) en Carga Física."
    )
    st.stop()

fmt_fecha = lambda f: f.strftime("%d/%m/%Y") if hasattr(f, "strftime") else str(f)

def _limpiar_rival(rival: str) -> str:
    """Saca un 'vs' que algunas filas de la planilla ya traen escrito a mano,
    para no duplicarlo cuando armamos la etiqueta (ej: 'vs Vilo' -> 'Vilo')."""
    return re.sub(r"^\s*vs\.?\s+", "", rival, flags=re.IGNORECASE).strip()

def _agregar_metadata_partido(df: pd.DataFrame) -> pd.DataFrame:
    """Suma posición, rival y una etiqueta legible ('DD/MM/AAAA vs Rival')
    a un df de GPS de sesiones de Partido. Reutilizado por el radar (filas
    'Completo') y por el gráfico de cuartos (filas Q1-Q4 crudas)."""
    df = df.copy()
    if df_pos is not None:
        df = df.merge(df_pos[["player_id", "posicion"]], on="player_id", how="left")
    if df_sesiones is not None:
        df = df.merge(
            df_sesiones[["fecha", "rival"]].drop_duplicates("fecha"), on="fecha", how="left"
        )
    else:
        df["rival"] = ""
    df["rival"] = df["rival"].fillna("")
    df["partido_label"] = df.apply(
        lambda r: fmt_fecha(r["fecha"])
                  + (f" vs {_limpiar_rival(r['rival'])}" if r["rival"] else ""),
        axis=1,
    )
    return df

df_partidos = _agregar_metadata_partido(df_partidos)

# ── Métricas disponibles para el radar ─────────────────────────────────────
METRICAS_RADAR = {
    "Distancia total": "distancia_total",
    "HSR Distance":    "hsr",
    "Sprints":         "sprints",
    "Player Load":     "player_load",
    "Vel. Máx":        "vel_max_kmh",
    "Dist/min":        "dist_min",
    "Player Load/min": "pl_min",
    "ACC >3":          "acc_3",
    "DECC >3":         "decc_3",
}
DEFAULT_METRICAS = ["Distancia total", "HSR Distance", "Sprints",
                     "Player Load", "Vel. Máx", "Dist/min"]

# ── Filtros ────────────────────────────────────────────────────────────────
col_partidos, col_pos, col_metricas = st.columns(3)

partidos_disp = (
    df_partidos[["fecha", "partido_label"]]
    .drop_duplicates()
    .sort_values("fecha")["partido_label"]
    .tolist()
)

with col_partidos:
    st.markdown(
        '<p style="font-size:0.875rem; color:inherit; margin-bottom:0.25rem">Partidos</p>',
        unsafe_allow_html=True,
    )
    with st.popover("Partidos", use_container_width=True):
        init_persistent("pa_partidos_sel", partidos_disp)
        partidos_sel = st.multiselect(
            "Partidos", partidos_disp, label_visibility="collapsed",
            key="pa_partidos_sel",
            on_change=lambda: save_persistent("pa_partidos_sel"),
        )

with col_pos:
    if df_pos is not None:
        posiciones = sorted(df_pos["posicion"].dropna().unique())
        st.markdown(
            '<p style="font-size:0.875rem; color:inherit; margin-bottom:0.25rem">Posición</p>',
            unsafe_allow_html=True,
        )
        with st.popover("Posición", use_container_width=True):
            init_persistent("pa_pos_sel", posiciones)
            pos_sel = st.multiselect(
                "Posición", posiciones, label_visibility="collapsed",
                key="pa_pos_sel",
                on_change=lambda: save_persistent("pa_pos_sel"),
            )
    else:
        pos_sel = None

with col_metricas:
    st.markdown(
        '<p style="font-size:0.875rem; color:inherit; margin-bottom:0.25rem">Métricas</p>',
        unsafe_allow_html=True,
    )
    with st.popover("Métricas", use_container_width=True):
        init_persistent("pa_metricas_sel", DEFAULT_METRICAS)
        metricas_sel = st.multiselect(
            "Métricas", list(METRICAS_RADAR.keys()),
            label_visibility="collapsed", key="pa_metricas_sel",
            on_change=lambda: save_persistent("pa_metricas_sel"),
        )

st.divider()

if not partidos_sel:
    st.info("Seleccioná al menos un partido para comparar.")
    st.stop()
if len(metricas_sel) < 3:
    st.info("Seleccioná al menos 3 métricas para armar el radar.")
    st.stop()

df_filtrado = df_partidos
if pos_sel is not None:
    df_filtrado = df_filtrado[df_filtrado["posicion"].isin(pos_sel)]

if df_filtrado.empty:
    st.info("No hay datos para esa combinación de posición.")
    st.stop()

metric_cols = [METRICAS_RADAR[m] for m in metricas_sel]

# ── Resumen del equipo por partido (promedio entre jugadoras) ──────────────
resumen = df_filtrado.groupby("partido_label")[metric_cols].mean().reset_index()

# Normalización 0-10 por métrica, relativa a TODOS los partidos disponibles
# (no solo los tildados) — así el radar no cambia de escala cuando se
# agrega o saca un partido de la comparación, solo cambia qué formas se ven.
resumen_norm = resumen.copy()
for col in metric_cols:
    resumen_norm[col] = normalizar_0_10(resumen[col])


def _hex_to_rgba(hex_color: str, alpha: float) -> str:
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


# ── Radar ──────────────────────────────────────────────────────────────────
fig = go.Figure()

for i, partido in enumerate(partidos_sel):
    fila_raw  = resumen[resumen["partido_label"] == partido]
    fila_norm = resumen_norm[resumen_norm["partido_label"] == partido]
    if fila_raw.empty:
        continue

    valores_raw  = fila_raw.iloc[0][metric_cols].tolist()
    valores_norm = fila_norm.iloc[0][metric_cols].tolist()
    color = LINE_PALETTE[i % len(LINE_PALETTE)]

    fig.add_trace(go.Scatterpolar(
        r=valores_norm + [valores_norm[0]],
        theta=metricas_sel + [metricas_sel[0]],
        name=partido,
        line=dict(color=color, width=2),
        fill="toself",
        fillcolor=_hex_to_rgba(color, 0.2),
        customdata=valores_raw + [valores_raw[0]],
        hovertemplate="%{theta}: %{customdata:.1f}<extra>%{fullData.name}</extra>",
    ))

fig.update_layout(**plotly_radar_layout(440))
st.plotly_chart(fig, use_container_width=True)
st.caption(
    "Cada eje se normaliza 0–10 según el mínimo y máximo entre todos los "
    "partidos disponibles (no solo los tildados), para que las formas sean "
    "comparables entre métricas de escalas distintas. El valor real de cada "
    "métrica se muestra al pasar el mouse."
)

st.divider()

# ── Tabla de valores reales ─────────────────────────────────────────────────
st.subheader("Valores reales por partido")
tabla = resumen[resumen["partido_label"].isin(partidos_sel)].rename(
    columns={v: k for k, v in METRICAS_RADAR.items()}
)
st.dataframe(
    tabla.set_index("partido_label")[metricas_sel].round(1),
    use_container_width=True,
)

st.divider()

# ── Comportamiento por cuarto (Q1-Q4) ──────────────────────────────────────
st.subheader("📊 Comportamiento por cuarto")

df_cuartos_raw = df_gps[
    (df_gps["tipo_sesion"] == TIPOS_SESION[2]) & (df_gps["cuarto"].isin(CUARTOS))
]
# Solo jugadoras con los 4 cuartos cargados en ESE partido — si no, el
# promedio de Q4 podría estar hecho con un grupo de jugadoras distinto al
# de Q1 (por rotación o datos faltantes), y una caída se leería como
# fatiga cuando en realidad cambió quién está en el promedio.
n_cuartos = df_cuartos_raw.groupby(["player_id", "fecha"])["cuarto"].transform("nunique")
df_cuartos_raw = df_cuartos_raw[n_cuartos >= len(CUARTOS)]
df_cuartos_raw = _agregar_metadata_partido(calcular_intensidad_relativa(df_cuartos_raw))

col_partidos_q, col_pos_q, col_metricas_q = st.columns(3)

with col_partidos_q:
    st.markdown(
        '<p style="font-size:0.875rem; color:inherit; margin-bottom:0.25rem">Partido</p>',
        unsafe_allow_html=True,
    )
    with st.popover("Partido", use_container_width=True, key="pop_partido_q"):
        init_persistent("ms_partido_q", partidos_disp)
        partidos_q_sel = st.multiselect(
            "Partido", partidos_disp,
            label_visibility="collapsed", key="ms_partido_q",
            on_change=lambda: save_persistent("ms_partido_q"),
        )

with col_pos_q:
    if df_pos is not None:
        st.markdown(
            '<p style="font-size:0.875rem; color:inherit; margin-bottom:0.25rem">Posición</p>',
            unsafe_allow_html=True,
        )
        with st.popover("Posición", use_container_width=True, key="pop_pos_q"):
            init_persistent("ms_pos_q", posiciones)
            pos_q_sel = st.multiselect(
                "Posición", posiciones,
                label_visibility="collapsed", key="ms_pos_q",
                on_change=lambda: save_persistent("ms_pos_q"),
            )
    else:
        pos_q_sel = None

with col_metricas_q:
    st.markdown(
        '<p style="font-size:0.875rem; color:inherit; margin-bottom:0.25rem">Métricas</p>',
        unsafe_allow_html=True,
    )
    with st.popover("Métricas", use_container_width=True, key="pop_metricas_q"):
        init_persistent("ms_metricas_q", ["Distancia total", "Player Load"])
        metricas_q_sel = st.multiselect(
            "Métricas", list(METRICAS_RADAR.keys()),
            label_visibility="collapsed", key="ms_metricas_q",
            on_change=lambda: save_persistent("ms_metricas_q"),
        )

st.divider()

if not partidos_q_sel:
    st.info("Seleccioná al menos un partido.")
elif not metricas_q_sel:
    st.info("Seleccioná al menos una métrica.")
else:
    df_cuartos_filtrado = df_cuartos_raw[df_cuartos_raw["partido_label"].isin(partidos_q_sel)]
    if pos_q_sel is not None:
        df_cuartos_filtrado = df_cuartos_filtrado[df_cuartos_filtrado["posicion"].isin(pos_q_sel)]

    if df_cuartos_filtrado.empty:
        st.info("No hay datos de cuartos para esa combinación de filtros.")
    else:
        metric_cols_q = [METRICAS_RADAR[m] for m in metricas_q_sel]
        resumen_cuartos = (
            df_cuartos_filtrado.groupby(["partido_label", "cuarto"])[metric_cols_q]
            .mean()
            .reset_index()
        )

        for metrica_label in metricas_q_sel:
            col = METRICAS_RADAR[metrica_label]
            fig_q = px.bar(
                resumen_cuartos, x="cuarto", y=col, color="partido_label",
                barmode="group",
                category_orders={"cuarto": CUARTOS, "partido_label": partidos_q_sel},
                labels={"cuarto": "Cuarto", col: metrica_label, "partido_label": "Partido"},
                color_discrete_sequence=BAR_CATEGORICAL_PALETTE,
            )
            fig_q.update_traces(marker=dict(cornerradius=4, line=dict(width=0)))
            fig_q.update_layout(**plotly_grouped_bar_layout(360))
            st.subheader(metrica_label, divider=False)
            st.plotly_chart(fig_q, use_container_width=True)

        st.caption(
            "Promedio del equipo (según posición filtrada) por cuarto en cada "
            "partido seleccionado — sirve para ver si la demanda física cae "
            "hacia el final del partido (fatiga) y si eso cambia entre partidos."
        )
