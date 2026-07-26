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
    PARAMETROS_SHEET_GID, LOGO_PATH, PAGE_COLORS,
)
from src.utils.auth import require_login
from src.loaders.roster_loader import cargar_posiciones_desde_sheets
from src.loaders.sesiones_loader import cargar_sesiones_desde_sheets, orden_match_day
from src.metrics.physical import calcular_intensidad_relativa, resumen_carga_equipo
from src.ui.theme import inject_dashboard_css, COMPARE_COLOR_A, ICONS, BAR_CATEGORICAL_PALETTE
from src.ui.state import init_persistent, save_persistent
from src.ui.charts import plotly_line_layout, md_ordinal_axis, resaltar_md
from src.ui.components import (
    compare_card_html, compare_rows_html, home_button, page_header, kpi_row,
)
from src.ui.filtros import popover_multiselect
from src.ui.asistente import cargar_parametros_cacheado, render_asistente
from src.reports.pdf_builder import generar_pdf_reporte, SeccionFigura, SeccionTabla

st.set_page_config(page_title="Físico vs Técnico-Táctico", page_icon=str(LOGO_PATH), layout="wide")

require_login()
inject_dashboard_css()
home_button()
page_header("Físico vs Técnico-Táctico", "Comparativa de demanda física entre tipos de sesión",
            icon=ICONS["balance"], color=PAGE_COLORS["fisico_tt"])
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

# Base propia para el Asistente de Parámetros — sus filtros (posición,
# jugadora, MD) son independientes de los filtros de arriba (rango de
# fechas, posición, jugadora de la comparativa/evolución), así que se
# guarda esta copia ANTES de que esos filtros recorten `df`.
df_asistente_base = df.copy()

col_fecha, col_pos, col_jugadora, col_modo = st.columns([1.3, 1, 1, 1.2])

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
        pos_sel = popover_multiselect("Posición", posiciones, "tt_pos_sel")
    else:
        pos_sel = None

with col_jugadora:
    jugadoras_disp = sorted(df["nombre"].dropna().unique())
    jugadora_sel = popover_multiselect("Jugadora", jugadoras_disp, "tt_jugadora_sel")

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
df = df[df["nombre"].isin(jugadora_sel)]

hay_a = (df["tipo_sesion"] == TIPO_A).any()
hay_b = (df["tipo_sesion"] == TIPO_B).any()
if not hay_a and not hay_b:
    st.info("No hay sesiones de ningún tipo dentro de ese rango de fechas, posiciones y jugadora/s seleccionada/s.")
    st.stop()

n_fis = df[df["tipo_sesion"] == TIPO_A]["fecha"].nunique()
n_tt  = df[df["tipo_sesion"] == TIPO_B]["fecha"].nunique()
if not hay_a:
    st.caption(f"⚠️ No hay sesiones de «{TIPO_A}» en este rango — se muestra en 0 para poder comparar igual.")
elif not hay_b:
    st.caption(f"⚠️ No hay sesiones de «{TIPO_B}» en este rango — se muestra en 0 para poder comparar igual.")

mds_presentes = sorted(
    (m for m in df["match_day"].unique() if m != "Sin clasificar"),
    key=orden_match_day,
) if "match_day" in df.columns else []
valor_md = ", ".join(mds_presentes) if mds_presentes else "Sin clasificar"

kpis = [
    ("👥", "Jugadoras",              f"{df['nombre'].nunique()}", BAR_CATEGORICAL_PALETTE[0]),
    ("🏟️", "Match Day",              valor_md,                    BAR_CATEGORICAL_PALETTE[2]),
    ("🏃", f"Sesiones {TIPO_A}",     f"{n_fis}",                  COMPARE_COLOR_A),
    ("🥅", f"Sesiones {TIPO_B}",     f"{n_tt}",                   COLOR_TT),
    ("📅", "Período",                f"{desde.strftime('%d/%m')} – {hasta.strftime('%d/%m/%Y')}",
     BAR_CATEGORICAL_PALETTE[3]),
]
kpi_row(kpis)

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
    # Sin sesiones de este tipo en el rango elegido, .mean()/.max() de un
    # DataFrame vacío dan NaN — se pisa con 0 en cada métrica para poder
    # seguir comparando visualmente contra el otro tipo, en vez de bloquear
    # toda la página.
    if df_tipo.empty:
        return pd.Series(0.0, index=[col for _, col, _ in COMPARAR_METRICAS])
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

# ── Asistente de Parámetros ─────────────────────────────────────────────────
st.divider()
st.subheader("🎯 Asistente — Cumplimiento de parámetros")

# None si no hay datos/selección para evaluar — el informe PDF más abajo
# solo agrega la sección del Asistente cuando esto no es None.
resultado_asistente = None

df_parametros = cargar_parametros_cacheado(WELLNESS_SHEET_ID, PARAMETROS_SHEET_GID)
if df_parametros is None:
    st.info("No se pudo cargar la hoja de Parametros todavía.")
else:
    # Elegir una o más sesiones reales (fecha + tipo) — el mismo día suele
    # tener Físico Y Técnico-Táctico, así que "una sola fecha" no alcanza.
    # Multiselect en vez de selectbox, pero por default arranca con solo la
    # sesión más reciente para no volver a la tabla larguísima de antes.
    sesiones_asist_disp = list(
        df_asistente_base[["fecha", "tipo_sesion"]]
          .drop_duplicates()
          .sort_values("fecha", ascending=False)
          .itertuples(index=False, name=None)
    )

    def _fmt_sesion(x):
        fecha_str = x[0].strftime("%d/%m/%Y") if hasattr(x[0], "strftime") else x[0]
        return f"{fecha_str} · {x[1]}"

    if not sesiones_asist_disp:
        st.info("No hay sesiones disponibles para evaluar.")
    else:
        col_asist_ses, col_asist_pos, col_asist_jug = st.columns([1.6, 1, 1])

        with col_asist_ses:
            sesiones_asist_sel = popover_multiselect(
                "Sesión", sesiones_asist_disp, "tt_asist_sesion_sel",
                default=[sesiones_asist_disp[0]], format_func=_fmt_sesion,
            )

        with col_asist_pos:
            if df_pos is not None:
                posiciones_asist = sorted(df_pos["posicion"].dropna().unique())
                pos_asist_sel = popover_multiselect("Posición", posiciones_asist, "tt_asist_pos_sel")
            else:
                pos_asist_sel = None

        with col_asist_jug:
            jugadoras_asist = sorted(df_asistente_base["nombre"].dropna().unique())
            jugadora_asist_sel = popover_multiselect("Jugadora", jugadoras_asist, "tt_asist_jugadora_sel")

        if not sesiones_asist_sel:
            st.info("Elegí al menos una sesión para evaluar.")
        else:
            claves_sel = set(sesiones_asist_sel)
            df_asistente_tt = df_asistente_base[
                df_asistente_base[["fecha", "tipo_sesion"]]
                    .apply(tuple, axis=1)
                    .isin(claves_sel)
            ].copy()
            df_asistente_tt = df_asistente_tt[df_asistente_tt["match_day"] != "Sin clasificar"]
            if pos_asist_sel is not None:
                df_asistente_tt = df_asistente_tt[df_asistente_tt["posicion"].isin(pos_asist_sel)]
            df_asistente_tt = df_asistente_tt[df_asistente_tt["nombre"].isin(jugadora_asist_sel)]

            if df_asistente_tt.empty:
                st.info(
                    "Ninguna sesión coincide con los filtros seleccionados, o las sesiones "
                    "elegidas son \"Sin clasificar\" — no hay Match Day para buscar en Parametros."
                )
            else:
                resultado_asistente = render_asistente(
                    df_asistente_tt, df_parametros,
                    claves_grupo=["posicion", "fecha", "match_day"],
                    etiqueta_fn=lambda f: (
                        f"{f['posicion']} · "
                        f"{f['fecha'].strftime('%d/%m') if hasattr(f['fecha'], 'strftime') else f['fecha']}"
                        f" · {f['match_day']}"
                    ),
                    etiqueta_header="Posición · Día",
                    caption=(
                        "Promedio del equipo por posición y por día — si la jugadora tuvo Físico Y "
                        "Técnico-Táctico ese día, se suman ambas sesiones antes de promediar — "
                        "contra el rango esperado para cada posición en ese Match Day. Sprints "
                        "distancia todavía no tiene columna real en el GPS, se suma cuando "
                        "Catapult la exporte."
                    ),
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

            if resultado_asistente is not None:
                if not resultado_asistente["tabla_pdf"].empty:
                    secciones_pdf.append(SeccionTabla(
                        "Asistente — Cumplimiento de parámetros", resultado_asistente["tabla_pdf"]
                    ))
                if not resultado_asistente["analisis_pdf"].empty:
                    secciones_pdf.append(SeccionTabla(
                        "Análisis — Fortalezas y debilidades", resultado_asistente["analisis_pdf"]
                    ))

            kpis_pdf = [(label, value) for _icon, label, value, _color in kpis]
            pdf_bytes = generar_pdf_reporte(
                titulo="Físico vs Técnico-Táctico",
                subtitulo=(f"Centro Naval Hockey — {desde.strftime('%d/%m/%Y')} "
                           f"a {hasta.strftime('%d/%m/%Y')}"),
                kpis=kpis_pdf,
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
