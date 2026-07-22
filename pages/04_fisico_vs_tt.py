# pages/04_fisico_vs_tt.py
import streamlit as st
import pandas as pd
import plotly.express as px
import sys
from datetime import datetime
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
    plotly_line_layout, COMPARE_COLOR_A, init_persistent, save_persistent, ICONS,
    md_ordinal_axis, resaltar_md,
)
from src.reports.pdf_builder import generar_pdf_reporte, SeccionFigura, SeccionTabla

st.set_page_config(page_title="Físico vs Técnico-Táctico", page_icon=str(LOGO_PATH), layout="wide")

require_login()
inject_dashboard_css()
home_button()
page_header("Físico vs Técnico-Táctico", "Comparativa de demanda física entre tipos de sesión",
            icon=ICONS["balance"], color="#F9AB00")
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
# Color propio de esta página para Técnico-Táctico (no COMPARE_COLOR_B — esa
# es la del "lado B" genérico en las comparativas de jugadora de Carga Física
# y Perfil de Jugadora, ya validada en verde; tocarla ahí cambiaría páginas
# que no tienen nada que ver con esta). Naranja ya validado en
# BAR_CATEGORICAL_PALETTE contra el fondo oscuro del dashboard.
COLOR_TT = "#d95926"
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
                                   COMPARE_COLOR_A, COLOR_TT),
                unsafe_allow_html=True)

with col_card_b:
    st.markdown(compare_card_html("🥅", TIPO_B, COLOR_TT), unsafe_allow_html=True)

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
st.subheader("Evolución temporal")

col_metrica, _ = st.columns([1, 3])
with col_metrica:
    init_persistent("tt_metrica_evol", COMPARAR_METRICAS[1][0])  # default: Player Load
    metrica_evol_label = st.selectbox(
        "Métrica", [m[0] for m in COMPARAR_METRICAS],
        key="tt_metrica_evol",
        on_change=lambda: save_persistent("tt_metrica_evol"),
    )
metrica_evol_col = next(col for label, col, _fmt in COMPARAR_METRICAS if label == metrica_evol_label)

resumen_a = resumen_carga_equipo(df[df["tipo_sesion"] == TIPO_A], col_carga=metrica_evol_col)
resumen_a["tipo_sesion"] = TIPO_A
resumen_b = resumen_carga_equipo(df[df["tipo_sesion"] == TIPO_B], col_carga=metrica_evol_col)
resumen_b["tipo_sesion"] = TIPO_B
df_evolucion = pd.concat([resumen_a, resumen_b], ignore_index=True)

# Match Day por fecha, para el label del eje X.
if "match_day" in df.columns:
    md_por_fecha = df.drop_duplicates("fecha").set_index("fecha")["match_day"]
else:
    md_por_fecha = pd.Series(dtype=object)
df_evolucion["match_day"] = df_evolucion["fecha"].map(md_por_fecha).fillna("Sin clasificar")
df_evolucion["_label_fecha"] = df_evolucion["fecha"].apply(lambda f: pd.Timestamp(f).strftime("%d/%m/%Y"))

# Eje X con espaciado PAREJO entre jornadas, no por fecha real (ver
# md_ordinal_axis en theme.py) — si no, dos sesiones separadas por 10 días
# en el calendario quedan mucho más lejos entre sí en el gráfico que dos
# sesiones seguidas, distorsionando la lectura de la tendencia.
df_evolucion, ticks_evol = md_ordinal_axis(df_evolucion)
fechas_evol = sorted(df_evolucion["fecha"].unique())

def _tick_label_evol(fecha) -> str:
    md = md_por_fecha.get(fecha, "Sin clasificar")
    label = f"{pd.Timestamp(fecha).strftime('%d/%m')} · {md}"
    return resaltar_md(label, md)

ticks_evol["ticktext"] = [_tick_label_evol(f) for f in fechas_evol]

etiqueta_y = f"{metrica_evol_label} (promedio)"
fig_evol = px.line(
    df_evolucion, x="_md_x", y="media", color="tipo_sesion",
    markers=True,
    labels={"media": etiqueta_y, "_md_x": "", "tipo_sesion": ""},
    color_discrete_map={TIPO_A: COMPARE_COLOR_A, TIPO_B: COLOR_TT},
    custom_data=["_label_fecha"],
)
fig_evol.update_traces(
    line=dict(width=2.5), marker=dict(size=8),
    hovertemplate=f"%{{customdata[0]}}<br>{etiqueta_y}: " + "%{y:.1f}<extra></extra>",
)
fig_evol.update_layout(**plotly_line_layout(360))
fig_evol.update_layout(
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5)
)
fig_evol.update_xaxes(**ticks_evol, tickangle=-45)

st.plotly_chart(fig_evol, use_container_width=True)
st.caption(
    f"Evolución sesión a sesión de {metrica_evol_label} (promedio del equipo), dentro del "
    "rango de fechas seleccionado arriba — a diferencia de la comparativa de "
    "barras (que promedia todo el período en un solo valor), acá se ve la "
    "tendencia día a día."
)

# ── Informe PDF ────────────────────────────────────────────────────────────
st.divider()
st.subheader("📄 Informe PDF")
st.caption("Genera un PDF con la comparativa Físico vs Técnico-Táctico y la evolución temporal.")

if st.button("Generar informe PDF", key="tt_gen_pdf"):
    with st.spinner("Generando PDF..."):
        try:
            df_comp_pdf = pd.DataFrame({
                "Métrica": [m[0] for m in COMPARAR_METRICAS],
                TIPO_A: [fmt.format(promedio_a.get(col, 0) or 0) for _, col, fmt in COMPARAR_METRICAS],
                TIPO_B: [fmt.format(promedio_b.get(col, 0) or 0) for _, col, fmt in COMPARAR_METRICAS],
            })

            secciones_pdf = [
                SeccionTabla("Comparativa Físico vs Técnico-Táctico", df_comp_pdf),
                SeccionFigura("Evolución temporal", fig_evol),
            ]

            pdf_bytes = generar_pdf_reporte(
                titulo="Físico vs Técnico-Táctico",
                subtitulo=(f"Centro Naval Hockey — {desde.strftime('%d/%m/%Y')} "
                           f"a {hasta.strftime('%d/%m/%Y')}"),
                secciones=secciones_pdf,
            )
            st.session_state["_tt_pdf_bytes"] = pdf_bytes
        except Exception as e:
            st.error(f"No se pudo generar el PDF: {e}")

if "_tt_pdf_bytes" in st.session_state:
    st.download_button(
        "⬇️ Descargar informe PDF",
        data=st.session_state["_tt_pdf_bytes"],
        file_name=f"fisico_vs_tt_{datetime.now():%Y%m%d_%H%M}.pdf",
        mime="application/pdf",
        key="tt_download_pdf",
    )
