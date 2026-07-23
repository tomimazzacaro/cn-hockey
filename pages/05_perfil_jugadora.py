# pages/05_perfil_jugadora.py
import streamlit as st
import pandas as pd
import plotly.express as px
import sys
from datetime import datetime
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from settings import (
    PROCESSED, WELLNESS_SHEET_ID, WELLNESS_SHEET_GID, ROSTER_SHEET_GID, SESIONES_SHEET_GID,
    PARAMETROS_SHEET_GID, LOGO_PATH, ACWR_OPTIMO_MIN, ACWR_OPTIMO_MAX, ACWR_ALERTA,
)
from src.utils.auth import require_login
from src.loaders.wellness_loader import cargar_desde_sheets
from src.loaders.roster_loader import cargar_posiciones_desde_sheets
from src.loaders.sesiones_loader import cargar_sesiones_desde_sheets
from src.loaders.parametros_loader import cargar_parametros_desde_sheets
from src.metrics.wellness import calcular_readiness, calcular_tendencia_tqr, generar_alertas
from src.metrics.physical import (
    calcular_acwr, calcular_intensidad_relativa, calcular_srpe, agregar_partidos_completos,
)
from src.metrics.parametros import evaluar_sesiones
from src.ui.theme import (
    inject_dashboard_css, plotly_line_layout, LINE_PALETTE, ZONE_CFG, home_button,
    compare_card_html, foto_jugadora_path, COMPARE_COLOR_A, player_kpi_row,
    BAR_CATEGORICAL_PALETTE, md_ordinal_axis, apply_area_line_style, page_header,
    init_persistent, save_persistent, ICONS, tabla_asistente_html,
)
from src.reports.pdf_builder import generar_pdf_reporte, SeccionFigura, SeccionTabla, SeccionFotos

st.set_page_config(page_title="Perfil de Jugadora", page_icon=str(LOGO_PATH), layout="wide")

require_login()
inject_dashboard_css()
home_button()
page_header("Perfil de Jugadora", "Evolución individual — ACWR, wellness y sRPE en el tiempo",
            icon=ICONS["target"], color="#A78BFA")
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

col_foto, col_selector, _col_resto = st.columns([1, 1, 2.2])

with col_selector:
    init_persistent("perfil_jugadora_id", player_ids[0])
    jugadora_id = st.selectbox("Jugadora", player_ids,
                               format_func=lambda pid: id_a_nombre.get(pid, pid),
                               key="perfil_jugadora_id",
                               on_change=lambda: save_persistent("perfil_jugadora_id"))

with col_foto:
    # Si todavía no se cargó la foto de la jugadora, la tarjeta muestra el
    # ícono de placeholder — foto_jugadora_path() devuelve None en ese caso.
    # Misma proporción de columna que las tarjetas de "Comparativa entre
    # jugadoras" en Carga Física (1 parte de 4.2) — sin overrides de CSS acá,
    # así la tarjeta y la foto quedan del mismo tamaño real en las dos
    # páginas, en vez de agrandar/achicar esta con CSS scopeado.
    st.markdown('<div style="height:1.6rem"></div>', unsafe_allow_html=True)
    with st.container(key="cn-perfil-foto"):
        st.markdown(
            compare_card_html("🏑", id_a_nombre.get(jugadora_id, jugadora_id), COMPARE_COLOR_A,
                              foto_jugadora_path(jugadora_id)),
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
        fig_acwr_gps = px.line(df_gps_md, x="_md_x", y="acwr", markers=True,
                      labels={"acwr": "ACWR (Player Load)", "_md_x": ""})
        fig_acwr_gps.update_traces(line=dict(color=LINE_PALETTE[0]))
        fig_acwr_gps.add_hrect(y0=0.8, y1=1.3, fillcolor=ZONE_CFG["Óptimo"]["color"],
                      opacity=0.12, line_width=0)
        _lineas_umbral_acwr(fig_acwr_gps)
        fig_acwr_gps.update_layout(**plotly_line_layout(320, "ACWR Externo (GPS)"))
        fig_acwr_gps.update_xaxes(**ticks_gps)
        apply_area_line_style(fig_acwr_gps)
        st.plotly_chart(fig_acwr_gps, use_container_width=True)
    else:
        st.info("Sin días con MD clasificado para esta jugadora.")

with col_acwr_rpe:
    if not sin_well_md:
        fig_acwr_rpe = px.line(df_well_md, x="_md_x", y="acwr", markers=True,
                      labels={"acwr": "ACWR (RPE)", "_md_x": ""})
        fig_acwr_rpe.update_traces(line=dict(color=LINE_PALETTE[1]))
        fig_acwr_rpe.add_hrect(y0=0.8, y1=1.3, fillcolor=ZONE_CFG["Óptimo"]["color"],
                      opacity=0.12, line_width=0)
        _lineas_umbral_acwr(fig_acwr_rpe)
        fig_acwr_rpe.update_layout(**plotly_line_layout(320, "ACWR Interno (RPE)"))
        fig_acwr_rpe.update_xaxes(**ticks_well)
        apply_area_line_style(fig_acwr_rpe)
        st.plotly_chart(fig_acwr_rpe, use_container_width=True)
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
        fig_tqr_rpe = px.line(df_well_md, x="_md_x", y=["tqr", "rpe"], markers=True,
                      labels={"value": "Escala 1–10", "_md_x": "", "variable": ""},
                      color_discrete_sequence=[LINE_PALETTE[2], LINE_PALETTE[3]])
        fig_tqr_rpe.update_layout(**plotly_line_layout(320, "TQR vs RPE"))
        fig_tqr_rpe.update_xaxes(**ticks_well)
        apply_area_line_style(fig_tqr_rpe, fill=False)
        # Umbrales de generar_alertas(): TQR<5 (recuperación insuficiente),
        # RPE>8 (esfuerzo muy alto) — cada línea en el color de su métrica.
        fig_tqr_rpe.add_hline(y=5, line_dash="dash", line_width=1.3, line_color=LINE_PALETTE[2],
                      annotation_text="TQR bajo <5", annotation_position="bottom left",
                      annotation_font=dict(color=LINE_PALETTE[2], size=10))
        fig_tqr_rpe.add_hline(y=8, line_dash="dash", line_width=1.3, line_color=LINE_PALETTE[3],
                      annotation_text="RPE alto >8", annotation_position="top left",
                      annotation_font=dict(color=LINE_PALETTE[3], size=10))
        st.plotly_chart(fig_tqr_rpe, use_container_width=True)

    with col_srpe:
        if df_well_md["srpe"].notna().any():
            fig_srpe = px.line(df_well_md, x="_md_x", y="srpe", markers=True,
                          labels={"srpe": "sRPE (UA)", "_md_x": ""})
            fig_srpe.update_traces(line=dict(color=LINE_PALETTE[4]))
            fig_srpe.update_layout(**plotly_line_layout(320, "sRPE (RPE × duración)"))
            fig_srpe.update_xaxes(**ticks_well)
            apply_area_line_style(fig_srpe)
            st.plotly_chart(fig_srpe, use_container_width=True)
        else:
            fig_srpe = None
            st.info(
                "sRPE requiere sesiones GPS con duración registrada en las "
                "mismas fechas que los registros de wellness de esta jugadora."
            )
else:
    st.info("Sin días con MD clasificado para esta jugadora.")

st.divider()

# ── Partidos jugados ───────────────────────────────────────────────────────
st.subheader("🏑 Partidos jugados")

COLS_PARTIDOS = ["fecha", "rival", "duracion_min", "distancia_total", "dist_min",
                 "hsr", "hsr_pct", "sprints", "acc_3", "decc_3", "player_load",
                 "pl_min", "vel_max_kmh"]
ENCABEZADOS_PARTIDOS = ["Fecha", "Rival", "Dur (min)", "Dist (m)", "Dist/min",
                        "HSR (m)", "HSR %", "Sprints", "ACC>3", "DECC>3",
                        "Player Load", "PL/min", "Vel Máx (km/h)"]
REDONDEO_PARTIDOS = {"duracion_min": 0, "distancia_total": 0, "dist_min": 1, "hsr": 0,
                     "hsr_pct": 1, "sprints": 0, "acc_3": 0, "decc_3": 0,
                     "player_load": 1, "pl_min": 2, "vel_max_kmh": 1}
# Columnas que son cantidades enteras de verdad (duración en minutos, metros
# redondeados, conteos) — sin esto quedaban como float y mostraban "44.0",
# "0.0" en vez de "44", "0".
COLS_ENTERAS_PARTIDOS = ["duracion_min", "distancia_total", "hsr", "sprints", "acc_3", "decc_3"]
COLS_METRICAS_PARTIDOS = ENCABEZADOS_PARTIDOS[2:]  # todo menos Fecha y Rival

def _tabla_partidos_jugados() -> pd.DataFrame:
    """Una fila por partido completo (4 cuartos) de esta jugadora, con el
    rival cruzado desde la hoja de Sesiones — mismos partidos que alimentan
    los promedios de los KPIs de arriba (agregar_partidos_completos)."""
    tabla = df_partidos_jug.sort_values("fecha", ascending=False).copy()
    if df_sesiones is not None:
        rival_por_fecha = df_sesiones.drop_duplicates("fecha").set_index("fecha")["rival"]
        tabla["rival"] = tabla["fecha"].map(rival_por_fecha).fillna("")
    else:
        tabla["rival"] = ""
    tabla = tabla[COLS_PARTIDOS].round(REDONDEO_PARTIDOS)
    tabla[COLS_ENTERAS_PARTIDOS] = tabla[COLS_ENTERAS_PARTIDOS].astype("Int64")
    tabla["fecha"] = tabla["fecha"].apply(
        lambda f: f.strftime("%d/%m/%Y") if hasattr(f, "strftime") else str(f)
    )
    tabla.columns = ENCABEZADOS_PARTIDOS
    return tabla

def _zebra(fila: pd.Series) -> list[str]:
    """Fondo apenas más claro en las filas impares, toda la fila (Fecha y
    Rival incluidos) — ayuda a no "perder la fila" a medida que se acumulan
    más partidos en la temporada."""
    color = "background-color: #16294f" if fila.name % 2 == 1 else ""
    return [color] * len(fila)


def _resaltar_maximos(col: pd.Series) -> list[str]:
    """Resalta el valor máximo de esta métrica en todos los partidos —
    aunque haya sido en un partido distinto al de las demás columnas
    resaltadas de esa fila — para ver de un vistazo el techo alcanzado en
    cada una. Va después de _zebra en el Styler para que este fondo gane
    por encima del rayado en esa celda puntual."""
    es_maximo = (col == col.max()).fillna(False)
    estilo = "background-color: rgba(167,139,250,0.35); font-weight: 700; color: #ffffff"
    return [estilo if v else "" for v in es_maximo]


if not sin_partidos_jug:
    # Rayado cebra en toda la tabla + el máximo de cada métrica resaltado en
    # violeta (mismo acento que el ícono de esta página) — valores centrados
    # vía column_config, porque el text-align de un Styler no lo respeta el
    # grid de st.dataframe.
    tabla_partidos = _tabla_partidos_jugados().reset_index(drop=True)
    tabla_estilizada = (
        tabla_partidos.style
        .apply(_zebra, axis=1)
        .apply(_resaltar_maximos, subset=COLS_METRICAS_PARTIDOS)
    )
    st.dataframe(
        tabla_estilizada, use_container_width=True, hide_index=True,
        column_config={
            "Dur (min)":       st.column_config.NumberColumn(alignment="center"),
            "Dist (m)":        st.column_config.NumberColumn(alignment="center"),
            "Dist/min":        st.column_config.NumberColumn(alignment="center", format="%.1f"),
            "HSR (m)":         st.column_config.NumberColumn(alignment="center"),
            "HSR %":           st.column_config.NumberColumn(alignment="center", format="%.1f"),
            "Sprints":         st.column_config.NumberColumn(alignment="center"),
            "ACC>3":           st.column_config.NumberColumn(alignment="center"),
            "DECC>3":          st.column_config.NumberColumn(alignment="center"),
            "Player Load":     st.column_config.NumberColumn(alignment="center", format="%.1f"),
            "PL/min":          st.column_config.NumberColumn(alignment="center", format="%.2f"),
            "Vel Máx (km/h)":  st.column_config.NumberColumn(alignment="center", format="%.1f"),
        },
    )
else:
    st.info(
        "Todavía no hay partidos completos (4 cuartos cargados) para esta jugadora."
    )

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

# ── Asistente de Parámetros ─────────────────────────────────────────────────
st.divider()
st.subheader("🎯 Asistente — Cumplimiento de parámetros")

@st.cache_data(ttl=3600)
def cargar_parametros():
    try:
        return cargar_parametros_desde_sheets(WELLNESS_SHEET_ID, PARAMETROS_SHEET_GID)
    except Exception:
        return None

posicion_jugadora = None
if df_pos is not None:
    fila_pos = df_pos[df_pos["player_id"] == jugadora_id]
    if not fila_pos.empty:
        posicion_jugadora = fila_pos["posicion"].iloc[0]

if posicion_jugadora is None:
    st.info("Esta jugadora no tiene posición cargada en el roster — no se puede evaluar contra los parámetros.")
elif sin_gps:
    st.info("Sin datos de GPS para evaluar contra los parámetros.")
else:
    df_parametros = cargar_parametros()
    if df_parametros is None:
        st.info("No se pudo cargar la hoja de Parametros todavía.")
    else:
        # Entrenamientos con MD real: cada fila ya es una sesión completa,
        # se evalúan tal cual. Los partidos se evalúan agregados (Q1-Q4
        # sumados, agregar_partidos_completos) — comparar un cuarto suelto
        # contra el rango de un partido entero siempre daría "por debajo".
        df_entrenos_md = (
            df_gps_md[df_gps_md["tipo_sesion"] != "Partido"].copy()
            if not sin_gps_md else pd.DataFrame()
        )

        df_partidos_md = df_partidos_jug.copy()
        if not df_partidos_md.empty:
            if df_sesiones is not None:
                md_por_fecha = df_sesiones.drop_duplicates("fecha").set_index("fecha")["match_day"]
                df_partidos_md["match_day"] = df_partidos_md["fecha"].map(md_por_fecha).fillna("Sin clasificar")
            else:
                df_partidos_md["match_day"] = "Sin clasificar"
            df_partidos_md = df_partidos_md[df_partidos_md["match_day"] != "Sin clasificar"]

        df_sesiones_asistente = pd.concat([df_entrenos_md, df_partidos_md], ignore_index=True)

        if df_sesiones_asistente.empty:
            st.info("Sin sesiones con Match Day asignado para evaluar todavía.")
        else:
            df_sesiones_asistente["posicion"] = posicion_jugadora
            # La etiqueta necesita el tipo de sesión además de fecha+MD: un
            # día de entrenamiento suele tener Físico Y Técnico-Táctico (y un
            # día de partido, Físico Y el partido) — sin el tipo, dos filas
            # distintas del mismo día colisionan en la misma etiqueta.
            df_sesiones_asistente["etiqueta_sesion"] = df_sesiones_asistente.apply(
                lambda f: (f"{f['fecha'].strftime('%d/%m/%Y') if hasattr(f['fecha'], 'strftime') else f['fecha']}"
                           f" · {f['match_day']} · {f['tipo_sesion']}"),
                axis=1,
            )
            df_sesiones_asistente = df_sesiones_asistente.sort_values("fecha", ascending=False)

            df_evaluacion = evaluar_sesiones(
                df_sesiones_asistente, df_parametros, col_etiqueta="etiqueta_sesion", match_day=None
            )
            tabla_asistente_html(df_evaluacion, etiqueta_header="Sesión")
            st.caption(
                "Compara cada sesión de esta jugadora (con Match Day asignado) contra "
                "el rango esperado para su posición — Sprints distancia todavía no "
                "tiene columna real en el GPS, se suma cuando Catapult la exporte."
            )

# ── Informe PDF ────────────────────────────────────────────────────────────
st.divider()
st.subheader("📄 Informe PDF")
st.caption("Genera un PDF con los KPIs, el ACWR, la recuperación/esfuerzo y las molestias de la jugadora.")

if st.button("Generar informe PDF", key="perfil_gen_pdf"):
    with st.spinner("Generando PDF..."):
        try:
            kpis_pdf = (
                [(label, value) for _icon, label, value, _color in kpis_jugadora]
                if not sin_gps else None
            )

            secciones_pdf = [
                SeccionFotos("Jugadora", [
                    (id_a_nombre.get(jugadora_id, jugadora_id), foto_jugadora_path(jugadora_id)),
                ]),
            ]
            if not sin_gps_md:
                secciones_pdf.append(SeccionFigura("ACWR Externo (GPS)", fig_acwr_gps))
            if not sin_well_md:
                secciones_pdf.append(SeccionFigura("ACWR Interno (RPE)", fig_acwr_rpe))
                secciones_pdf.append(SeccionFigura("TQR vs RPE", fig_tqr_rpe))
                if fig_srpe is not None:
                    secciones_pdf.append(SeccionFigura("sRPE (RPE × duración)", fig_srpe))
            if not sin_partidos_jug:
                secciones_pdf.append(SeccionTabla("Partidos jugados", _tabla_partidos_jugados()))
            if not sin_well and len(molestias) > 0:
                df_molestias_pdf = molestias.copy()
                df_molestias_pdf["fecha"] = df_molestias_pdf["fecha"].apply(
                    lambda f: f.strftime("%d/%m/%Y") if hasattr(f, "strftime") else str(f)
                )
                df_molestias_pdf.columns = ["Fecha", "Molestia"]
                secciones_pdf.append(SeccionTabla("Molestias reportadas", df_molestias_pdf))

            pdf_bytes = generar_pdf_reporte(
                titulo="Perfil de Jugadora",
                subtitulo=f"Centro Naval Hockey — {id_a_nombre.get(jugadora_id, jugadora_id)}",
                kpis=kpis_pdf,
                secciones=secciones_pdf,
            )
            st.session_state["_perfil_pdf_bytes"] = pdf_bytes
        except Exception as e:
            st.error(f"No se pudo generar el PDF: {e}")

if "_perfil_pdf_bytes" in st.session_state:
    st.download_button(
        "⬇️ Descargar informe PDF",
        data=st.session_state["_perfil_pdf_bytes"],
        file_name=f"perfil_{jugadora_id}_{datetime.now():%Y%m%d_%H%M}.pdf",
        mime="application/pdf",
        key="perfil_download_pdf",
    )
