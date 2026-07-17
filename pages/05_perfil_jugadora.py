# pages/05_perfil_jugadora.py
import streamlit as st
import pandas as pd
import plotly.express as px
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from settings import (
    PROCESSED, WELLNESS_SHEET_ID, WELLNESS_SHEET_GID, ROSTER_SHEET_GID, SESIONES_SHEET_GID,
    LOGO_PATH, ACWR_OPTIMO_MIN, ACWR_OPTIMO_MAX, ACWR_ALERTA,
)
from src.utils.auth import require_login
from src.loaders.wellness_loader import cargar_desde_sheets
from src.loaders.roster_loader import cargar_posiciones_desde_sheets
from src.loaders.sesiones_loader import cargar_sesiones_desde_sheets
from src.metrics.wellness import calcular_readiness, calcular_tendencia_tqr, generar_alertas
from src.metrics.physical import (
    calcular_acwr, calcular_intensidad_relativa, calcular_srpe, agregar_partidos_completos,
)
from src.ui.theme import (
    inject_dashboard_css, plotly_line_layout, LINE_PALETTE, ZONE_CFG, home_button,
    compare_card_html, COMPARE_COLOR_A, player_kpi_row, BAR_CATEGORICAL_PALETTE,
    md_ordinal_axis, apply_area_line_style, page_header,
)

st.set_page_config(page_title="Perfil de Jugadora", page_icon=str(LOGO_PATH), layout="wide")

require_login()
inject_dashboard_css()
home_button()
page_header("Perfil de Jugadora", "Evolución individual — ACWR, wellness y sRPE en el tiempo",
            icon="🎯", color="#A78BFA")
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

@st.cache_data(ttl=300)
def cargar_sesiones():
    try:
        return cargar_sesiones_desde_sheets(WELLNESS_SHEET_ID, SESIONES_SHEET_GID)
    except Exception:
        return None

df_gps      = cargar_gps()
df_well     = cargar_wellness()
df_pos      = cargar_posiciones()
df_sesiones = cargar_sesiones()

def con_match_day(df: pd.DataFrame | None) -> pd.DataFrame | None:
    """Suma la columna match_day (MD-5, MD-2, MD, MD+1...) cruzando por fecha
    contra la hoja de Sesiones. Los días sin sesión registrada quedan como
    'Sin clasificar' — se usa como texto de tick del eje X en los gráficos
    de línea, en vez de la fecha cruda."""
    if df is None or df_sesiones is None:
        if df is not None:
            df = df.copy()
            df["match_day"] = df["fecha"].astype(str)
        return df
    df = df.merge(df_sesiones[["fecha", "match_day"]], on="fecha", how="left")
    df["match_day"] = df["match_day"].fillna("Sin clasificar")
    return df

df_gps  = con_match_day(df_gps)
df_well = con_match_day(df_well)

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

col_foto, col_selector, _col_resto = st.columns([2, 1, 2])

with col_selector:
    jugadora_id = st.selectbox("Jugadora", player_ids,
                               format_func=lambda pid: id_a_nombre.get(pid, pid))

with col_foto:
    # Todavía no hay fotos cargadas — mientras tanto, la tarjeta muestra el
    # nombre de la jugadora seleccionada. El día que haya fotos, alcanza con
    # pasar una URL/ruta de imagen acá en vez del ícono.
    # Tarjeta agrandada solo en esta página — compare_card_html() es un
    # componente compartido con las comparaciones A/B de otras páginas, así
    # que el tamaño más grande se pisa acá con CSS scopeado al container en
    # vez de tocar .cn-cmp-card/.cn-cmp-avatar/.cn-cmp-name globalmente.
    st.markdown(
        """
        <style>
        .st-key-cn-perfil-foto .cn-cmp-card   { padding: 34px 20px; }
        .st-key-cn-perfil-foto .cn-cmp-avatar { font-size: 4rem; margin-bottom: 14px; }
        .st-key-cn-perfil-foto .cn-cmp-name   { font-size: 1.35rem; }
        </style>
        <div style="height:1.6rem"></div>
        """,
        unsafe_allow_html=True,
    )
    with st.container(key="cn-perfil-foto"):
        st.markdown(
            compare_card_html("🏑", id_a_nombre.get(jugadora_id, jugadora_id), COMPARE_COLOR_A),
            unsafe_allow_html=True,
        )

df_gps_jug  = (df_gps[df_gps["player_id"] == jugadora_id].sort_values("fecha")
               if df_gps is not None else None)
df_well_jug = (df_well[df_well["player_id"] == jugadora_id].sort_values("fecha")
               if df_well is not None else None)

sin_gps  = df_gps_jug is None or df_gps_jug.empty
sin_well = df_well_jug is None or df_well_jug.empty

if sin_gps and sin_well:
    st.info(f"{id_a_nombre.get(jugadora_id, jugadora_id)} todavía no tiene registros de GPS ni de wellness.")
    st.stop()

# Para los gráficos de línea (ACWR, TQR/RPE, sRPE) solo interesan los días
# con un MD asignado en la hoja de Sesiones — un día "Sin clasificar" no
# tiene sentido en un eje pensado para leerse en relación al partido.
df_gps_md  = df_gps_jug[df_gps_jug["match_day"] != "Sin clasificar"]  if not sin_gps  else df_gps_jug
df_well_md = df_well_jug[df_well_jug["match_day"] != "Sin clasificar"] if not sin_well else df_well_jug
sin_gps_md  = df_gps_md is None or df_gps_md.empty
sin_well_md = df_well_md is None or df_well_md.empty

# Eje X con espaciado parejo entre MDs (ver md_ordinal_axis en theme.py) —
# se arma una sola vez por dataset y se reutiliza en los gráficos de abajo.
if not sin_gps_md:
    df_gps_md, ticks_gps = md_ordinal_axis(df_gps_md)
if not sin_well_md:
    df_well_md, ticks_well = md_ordinal_axis(df_well_md)

# ── KPIs individuales (GPS) ────────────────────────────────────────────────
# Los promedios se calculan sobre partidos completos (Q1-Q4 sumados a un
# total por partido, vía agregar_partidos_completos) — no sobre todas sus
# sesiones GPS. La Vel. Máx Alcanzada es la excepción: se mantiene como el
# pico histórico sobre TODAS sus sesiones (Físico, Técnico-Táctico y
# Partido), no solo partidos.
df_partidos_jug = agregar_partidos_completos(df_gps_jug) if not sin_gps else pd.DataFrame()
sin_partidos_jug = df_partidos_jug.empty

def _prom_partido(col: str, fmt: str) -> str:
    return fmt.format(df_partidos_jug[col].mean()) if not sin_partidos_jug else "—"

if not sin_gps:
    kpis_jugadora = [
        ("🚀", "Vel. Máx Alcanzada",       f"{df_gps_jug['vel_max_kmh'].max():.1f} km/h",
         BAR_CATEGORICAL_PALETTE[0]),
        ("🏃", "HSR Promedio",              _prom_partido("hsr", "{:,.0f} m"),
         BAR_CATEGORICAL_PALETTE[1]),
        ("📏", "Distancia Total Promedio",  _prom_partido("distancia_total", "{:,.0f} m"),
         BAR_CATEGORICAL_PALETTE[2]),
        ("⬆️", "ACC Promedio",              _prom_partido("acc_3", "{:.1f}"),
         BAR_CATEGORICAL_PALETTE[3]),
        ("⬇️", "DESC Promedio",             _prom_partido("decc_3", "{:.1f}"),
         BAR_CATEGORICAL_PALETTE[5]),
        ("🔋", "Player Load Promedio",      _prom_partido("player_load", "{:,.1f}"),
         BAR_CATEGORICAL_PALETTE[4]),
    ]
    player_kpi_row(kpis_jugadora)
    if sin_partidos_jug:
        st.caption(
            "Todavía no hay partidos completos (4 cuartos cargados) para esta "
            "jugadora — los promedios muestran \"—\", solo la Vel. Máx queda "
            "calculada sobre todo su historial GPS."
        )
else:
    st.info("Sin datos de GPS para mostrar KPIs de esta jugadora.")

st.divider()

# ── ACWR en el tiempo ──────────────────────────────────────────────────────
st.subheader("ACWR — Externo (GPS) vs Interno (RPE)")

def _lineas_umbral_acwr(fig) -> None:
    """Líneas punteadas en los umbrales clínicos de ACWR (Hulin et al., 2016) —
    la banda sombreada ya marca la zona óptima, esto agrega el límite exacto
    de subcarga, precaución y riesgo alto para leerlo de un vistazo."""
    for y, zona in [(ACWR_OPTIMO_MIN, "Subcarga"),
                     (ACWR_OPTIMO_MAX, "Precaución"),
                     (ACWR_ALERTA, "Riesgo Alto")]:
        color = ZONE_CFG[zona]["color"]
        fig.add_hline(
            y=y, line_dash="dash", line_width=1.3, line_color=color,
            annotation_text=f"{zona} {y}", annotation_position="top left",
            annotation_font=dict(color=color, size=10),
        )

col_acwr_gps, col_acwr_rpe = st.columns(2)

with col_acwr_gps:
    if not sin_gps_md:
        fig = px.line(df_gps_md, x="_md_x", y="acwr", markers=True,
                      labels={"acwr": "ACWR (Player Load)", "_md_x": ""})
        fig.update_traces(line=dict(color=LINE_PALETTE[0]))
        fig.add_hrect(y0=0.8, y1=1.3, fillcolor=ZONE_CFG["Óptimo"]["color"],
                      opacity=0.12, line_width=0)
        _lineas_umbral_acwr(fig)
        fig.update_layout(**plotly_line_layout(320, "ACWR Externo (GPS)"))
        fig.update_xaxes(**ticks_gps)
        apply_area_line_style(fig)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sin días con MD clasificado para esta jugadora.")

with col_acwr_rpe:
    if not sin_well_md:
        fig = px.line(df_well_md, x="_md_x", y="acwr", markers=True,
                      labels={"acwr": "ACWR (RPE)", "_md_x": ""})
        fig.update_traces(line=dict(color=LINE_PALETTE[1]))
        fig.add_hrect(y0=0.8, y1=1.3, fillcolor=ZONE_CFG["Óptimo"]["color"],
                      opacity=0.12, line_width=0)
        _lineas_umbral_acwr(fig)
        fig.update_layout(**plotly_line_layout(320, "ACWR Interno (RPE)"))
        fig.update_xaxes(**ticks_well)
        apply_area_line_style(fig)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sin días con MD clasificado para esta jugadora.")

st.caption(
    "Banda sombreada: zona óptima 0.8–1.3. Líneas punteadas: umbrales de "
    "subcarga, precaución y riesgo alto (Hulin et al., 2016)."
)

st.divider()

# ── TQR / RPE / sRPE en el tiempo ──────────────────────────────────────────
st.subheader("Recuperación, esfuerzo y sRPE")

if not sin_well_md:
    col_tqr_rpe, col_srpe = st.columns(2)

    with col_tqr_rpe:
        fig = px.line(df_well_md, x="_md_x", y=["tqr", "rpe"], markers=True,
                      labels={"value": "Escala 1–10", "_md_x": "", "variable": ""},
                      color_discrete_sequence=[LINE_PALETTE[2], LINE_PALETTE[3]])
        fig.update_layout(**plotly_line_layout(320, "TQR vs RPE"))
        fig.update_xaxes(**ticks_well)
        apply_area_line_style(fig, fill=False)
        # Umbrales de generar_alertas(): TQR<5 (recuperación insuficiente),
        # RPE>8 (esfuerzo muy alto) — cada línea en el color de su métrica.
        fig.add_hline(y=5, line_dash="dash", line_width=1.3, line_color=LINE_PALETTE[2],
                      annotation_text="TQR bajo <5", annotation_position="bottom left",
                      annotation_font=dict(color=LINE_PALETTE[2], size=10))
        fig.add_hline(y=8, line_dash="dash", line_width=1.3, line_color=LINE_PALETTE[3],
                      annotation_text="RPE alto >8", annotation_position="top left",
                      annotation_font=dict(color=LINE_PALETTE[3], size=10))
        st.plotly_chart(fig, use_container_width=True)

    with col_srpe:
        if df_well_md["srpe"].notna().any():
            fig = px.line(df_well_md, x="_md_x", y="srpe", markers=True,
                          labels={"srpe": "sRPE (UA)", "_md_x": ""})
            fig.update_traces(line=dict(color=LINE_PALETTE[4]))
            fig.update_layout(**plotly_line_layout(320, "sRPE (RPE × duración)"))
            fig.update_xaxes(**ticks_well)
            apply_area_line_style(fig)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info(
                "sRPE requiere sesiones GPS con duración registrada en las "
                "mismas fechas que los registros de wellness de esta jugadora."
            )
else:
    st.info("Sin días con MD clasificado para esta jugadora.")

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
