# pages/02_carga_fisica.py
import io
import datetime
import streamlit as st
import pandas as pd
import plotly.express as px
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from settings import (
    PROCESSED, WELLNESS_SHEET_ID, ROSTER_SHEET_GID, SESIONES_SHEET_GID,
    TIPOS_SESION, CUARTOS, LOGO_PATH,
)
from src.utils.auth import require_login
from src.loaders.gps_loader import (
    cargar_sesion_desde_upload,
    extraer_fecha_de_nombre,
)
from src.loaders.roster_loader import cargar_posiciones_desde_sheets
from src.loaders.sesiones_loader import cargar_sesiones_desde_sheets, orden_match_day
from src.metrics.physical import (
    calcular_acwr, calcular_intensidad_relativa, agregar_partidos_completos,
)
from src.ui.theme import (
    inject_dashboard_css, render_kpi_row, plotly_bar_layout,
    compare_card_html, compare_rows_html, home_button, page_header, foto_jugadora_path,
    COMPARE_COLOR_A, COMPARE_COLOR_B, CHART_FONT, init_persistent, save_persistent, ICONS,
)
from src.reports.pdf_builder import generar_pdf_reporte, SeccionFigura, SeccionTabla, SeccionFotos

st.set_page_config(page_title="Carga Física", page_icon=str(LOGO_PATH), layout="wide")

require_login()
inject_dashboard_css()
home_button()
page_header("Carga Física", "GPS Catapult — Métricas de carga externa e intensidad relativa",
            icon=ICONS["carga_fisica"], color="#1A73E8")
st.divider()

# ── Helpers para subir sesión GPS (la UI se arma al final de la página) ────
def _backfill_columnas(df: pd.DataFrame) -> pd.DataFrame:
    """Datos históricos previos a tipo_sesion/cuarto."""
    if "tipo_sesion" not in df.columns:
        df["tipo_sesion"] = TIPOS_SESION[0]
    if "cuarto" not in df.columns:
        df["cuarto"] = "—"
    return df


def _panel_upload(tipo_sesion: str, key_prefix: str) -> None:
    uploaded = st.file_uploader(
        "Archivo CSV exportado de Catapult",
        type=["csv"],
        key=f"{key_prefix}_upload",
        help="El nombre del archivo debe tener formato export_DD-MM-YY.csv",
    )

    if not uploaded:
        return

    # Intentar detectar fecha del nombre
    try:
        fecha_default = extraer_fecha_de_nombre(uploaded.name).date()
    except ValueError:
        fecha_default = datetime.date.today()

    fecha_input = st.date_input(
        "Fecha de la sesión",
        value=fecha_default,
        format="DD/MM/YYYY",
        key=f"{key_prefix}_fecha_{uploaded.file_id}",
    )

    try:
        df_prev = cargar_sesion_desde_upload(uploaded, tipo_sesion, fecha_override=fecha_input)
        df_prev = calcular_intensidad_relativa(df_prev)

        st.success(
            f"✅ {len(df_prev)} jugadoras detectadas — "
            f"{fecha_input.strftime('%d/%m/%Y')}"
        )
        st.dataframe(
            df_prev[["nombre", "fecha", "distancia_total",
                      "hsr", "sprints", "player_load", "vel_max_kmh"]]
                    .reset_index(drop=True),
            use_container_width=True,
            hide_index=True,
        )

        if st.button("➕ Agregar al historial", type="primary", key=f"{key_prefix}_add"):
            _reemplazar_en_historial(df_prev)
            st.rerun()

    except Exception as e:
        st.error(f"Error al procesar el archivo: {e}")


def _reemplazar_en_historial(df_nuevo: pd.DataFrame) -> None:
    """Agrega df_nuevo a gps_extra, reemplazando cualquier entrada previa
    con la misma combinación (fecha, tipo_sesion, cuarto)."""
    fecha, tipo, cuarto = (df_nuevo["fecha"].iloc[0], df_nuevo["tipo_sesion"].iloc[0],
                            df_nuevo["cuarto"].iloc[0])
    extras = st.session_state.get("gps_extra", [])
    extras = [d for d in extras
              if not (d["fecha"].iloc[0] == fecha
                      and d["tipo_sesion"].iloc[0] == tipo
                      and d["cuarto"].iloc[0] == cuarto)]
    extras.append(df_nuevo)
    st.session_state["gps_extra"] = extras


def _panel_partido() -> None:
    fecha_input = st.date_input(
        "Fecha del partido",
        value=datetime.date.today(),
        format="DD/MM/YYYY",
        key="pa_fecha",
    )

    dfs_cuartos = {}
    for cuarto in CUARTOS:
        uploaded = st.file_uploader(
            f"CSV — {cuarto}",
            type=["csv"],
            key=f"pa_{cuarto}_upload",
        )
        if not uploaded:
            continue
        try:
            df_q = cargar_sesion_desde_upload(
                uploaded, TIPOS_SESION[2], fecha_override=fecha_input, cuarto=cuarto,
            )
            df_q = calcular_intensidad_relativa(df_q)
            dfs_cuartos[cuarto] = df_q
            st.caption(f"✅ {cuarto}: {len(df_q)} jugadoras detectadas")
        except Exception as e:
            st.error(f"{cuarto}: error al procesar el archivo — {e}")

    if dfs_cuartos and st.button("➕ Agregar partido al historial",
                                  type="primary", key="pa_add"):
        for df_q in dfs_cuartos.values():
            _reemplazar_en_historial(df_q)
        st.rerun()


# El panel para subir una nueva sesión GPS se armó más abajo, al final de la
# página (ver "Subir nueva sesión GPS" cerca del final del archivo) — así el
# primer tramo de la página queda despejado, directo a los datos.

# ── Cargar datos (base + uploads de esta sesión) ───────────────────────────
@st.cache_data
def cargar_base():
    df = pd.read_parquet(PROCESSED / "gps_procesado.parquet")
    df = _backfill_columnas(df)
    return calcular_intensidad_relativa(df)

try:
    df_base = cargar_base()
except FileNotFoundError:
    df_base = pd.DataFrame()

extras = st.session_state.get("gps_extra", [])
if extras:
    df = pd.concat([df_base] + extras, ignore_index=True)
    df = (df.drop_duplicates(subset=["player_id", "fecha", "tipo_sesion", "cuarto"], keep="last")
            .sort_values(["fecha", "nombre"])
            .reset_index(drop=True))
else:
    df = df_base

if df.empty:
    st.info("Sin datos GPS. Subí una sesión usando el panel de arriba.")
    st.stop()

df = calcular_acwr(df, col_carga="player_load")


@st.cache_data(ttl=3600)
def cargar_posiciones():
    try:
        return cargar_posiciones_desde_sheets(WELLNESS_SHEET_ID, ROSTER_SHEET_GID)
    except Exception:
        return None

df_pos = cargar_posiciones()
if df_pos is not None:
    df = df.merge(df_pos[["player_id", "posicion"]], on="player_id", how="left")

completos = agregar_partidos_completos(df, tipo_partido=TIPOS_SESION[2])
if not completos.empty:
    df = pd.concat([df, completos], ignore_index=True)


@st.cache_data(ttl=3600)
def cargar_sesiones():
    try:
        return cargar_sesiones_desde_sheets(WELLNESS_SHEET_ID, SESIONES_SHEET_GID)
    except Exception:
        return None

df_sesiones = cargar_sesiones()
if df_sesiones is not None:
    df = df.merge(df_sesiones, on="fecha", how="left")
    df["match_day"] = df["match_day"].fillna("Sin clasificar")
    df["tipo_dia"]  = df["tipo_dia"].fillna("Sin clasificar")
    df["rival"]     = df["rival"].fillna("")

# ── Filtros ────────────────────────────────────────────────────────────────
col_ses, col_pos, col_md = st.columns([1.8, 1, 1])

rival_por_fecha = (
    df[["fecha", "rival"]].drop_duplicates("fecha").set_index("fecha")["rival"].to_dict()
    if "rival" in df.columns else {}
)

with col_ses:
    sesiones_disp = list(
        df[["fecha", "tipo_sesion", "cuarto"]]
          .drop_duplicates()
          .sort_values("fecha", ascending=False)
          .itertuples(index=False, name=None)
    )
    init_persistent("cf_sesion_sel", sesiones_disp[0])
    sesion_sel = st.selectbox(
        "Sesión",
        sesiones_disp,
        format_func=lambda x: (
            f"{x[0].strftime('%d/%m/%Y') if hasattr(x[0], 'strftime') else x[0]} · {x[1]}"
            + (f" · {x[2]}" if x[2] != "—" else "")
            + (f" · vs {rival_por_fecha.get(x[0])}" if rival_por_fecha.get(x[0]) else "")
        ),
        key="cf_sesion_sel",
        on_change=lambda: save_persistent("cf_sesion_sel"),
    )
    fecha_sel, tipo_sel, cuarto_sel = sesion_sel

with col_pos:
    if df_pos is not None:
        posiciones = sorted(df_pos["posicion"].dropna().unique())
        st.markdown(
            '<p style="font-size:0.875rem; color:inherit; margin-bottom:0.25rem">Posición</p>',
            unsafe_allow_html=True,
        )
        with st.popover("Posición", use_container_width=True):
            init_persistent("cf_pos_sel", posiciones)
            pos_sel = st.multiselect(
                "Posición", posiciones, label_visibility="collapsed",
                key="cf_pos_sel",
                on_change=lambda: save_persistent("cf_pos_sel"),
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
            init_persistent("cf_md_sel", mds_disponibles)
            md_sel = st.multiselect(
                "Match Day", mds_disponibles, label_visibility="collapsed",
                key="cf_md_sel",
                on_change=lambda: save_persistent("cf_md_sel"),
            )
    else:
        md_sel = None

df_ses = df[(df["fecha"] == fecha_sel) & (df["tipo_sesion"] == tipo_sel)
            & (df["cuarto"] == cuarto_sel)]
if pos_sel is not None:
    df_ses = df_ses[df_ses["posicion"].isin(pos_sel)]
if md_sel is not None:
    df_ses = df_ses[df_ses["match_day"].isin(md_sel)]

st.divider()

# ── KPIs del equipo ────────────────────────────────────────────────────────
st.subheader("Equipo — Resumen de sesión")

kpis = [
    ("Jugadoras",         f"{len(df_ses)}"),
    ("Distancia media",   f"{df_ses['distancia_total'].mean():,.0f} m"),
    ("HSR media",         f"{df_ses['hsr'].mean():,.0f} m"),
    ("Player Load medio", f"{df_ses['player_load'].mean():,.1f}"),
    ("Vel. Máx media",    f"{df_ses['vel_max_kmh'].mean():,.1f} km/h"),
]

render_kpi_row(kpis)

st.divider()

# ── Config gráficos ────────────────────────────────────────────────────────
METRICAS = {
    "Distancia total (m)": ("distancia_total", "%{text:,.0f} m", ["#1e3a8a", "#60a5fa", "#bfdbfe"]),
    "Player Load":         ("player_load",     "%{text:.1f}",    ["#064e3b", "#34d399", "#a7f3d0"]),
    "HSR Distance (m)":    ("hsr",             "%{text:.0f} m",  ["#78350f", "#fbbf24", "#fef3c7"]),
    "Sprints":             ("sprints",         "%{text:.0f}",    ["#7f1d1d", "#f87171", "#fee2e2"]),
    "Vel. Máx (km/h)":     ("vel_max_kmh",     "%{text:.1f}",    ["#4c1d95", "#a78bfa", "#ede9fe"]),
    "Dist/min (m/min)":    ("dist_min",        "%{text:.1f}",    ["#0c4a6e", "#38bdf8", "#e0f2fe"]),
    "Player Load/min":     ("pl_min",          "%{text:.2f}",    ["#052e16", "#4ade80", "#dcfce7"]),
    "ACC >3 (m/s²)":       ("acc_3",           "%{text:.0f}",    ["#431407", "#fb923c", "#ffedd5"]),
    "DECC >3 (m/s²)":      ("decc_3",          "%{text:.0f}",    ["#422006", "#fcd34d", "#fef9c3"]),
}


def _bar_chart(data, col, label, fmt, scale, height):
    fig = px.bar(
        data.sort_values(col, ascending=True),
        x=col, y="nombre",
        orientation="h",
        color=col,
        color_continuous_scale=scale,
        labels={col: label, "nombre": ""},
        text=col,
    )
    fig.update_traces(
        texttemplate=fmt, textposition="outside",
        textfont=dict(color=CHART_FONT),
        marker=dict(cornerradius=4, line=dict(width=0)),
    )
    fig.update_layout(**plotly_bar_layout(height))
    return fig


# ── Gráfico principal ──────────────────────────────────────────────────────
init_persistent("sel_principal", list(METRICAS.keys())[0])
sel_principal = st.selectbox("Métrica", list(METRICAS.keys()), key="sel_principal",
                              on_change=lambda: save_persistent("sel_principal"))
col_p, fmt_p, scale_p = METRICAS[sel_principal]
st.subheader(sel_principal)
fig_principal = _bar_chart(df_ses, col_p, sel_principal, fmt_p, scale_p, 420)
st.plotly_chart(fig_principal, use_container_width=True)

# ── Dos columnas con selector independiente ────────────────────────────────
col_izq, col_der = st.columns(2)

with col_izq:
    init_persistent("sel_izq", list(METRICAS.keys())[1])
    sel_izq = st.selectbox("Métrica", list(METRICAS.keys()), key="sel_izq",
                            on_change=lambda: save_persistent("sel_izq"))
    col_i, fmt_i, scale_i = METRICAS[sel_izq]
    st.subheader(sel_izq)
    fig_izq = _bar_chart(df_ses, col_i, sel_izq, fmt_i, scale_i, 360)
    st.plotly_chart(fig_izq, use_container_width=True)

with col_der:
    init_persistent("sel_der", list(METRICAS.keys())[2])
    sel_der = st.selectbox("Métrica", list(METRICAS.keys()), key="sel_der",
                            on_change=lambda: save_persistent("sel_der"))
    col_d, fmt_d, scale_d = METRICAS[sel_der]
    st.subheader(sel_der)
    fig_der = _bar_chart(df_ses, col_d, sel_der, fmt_d, scale_d, 360)
    st.plotly_chart(fig_der, use_container_width=True)

st.divider()

# ── Comparativa entre jugadoras ────────────────────────────────────────────
st.subheader("Comparativa entre jugadoras")

COMPARAR_METRICAS = [
    ("Distancia total", "distancia_total", "{:,.0f} m"),
    ("Player Load",     "player_load",     "{:.1f}"),
    ("HSR Distance",    "hsr",             "{:.0f} m"),
    ("Sprints",         "sprints",         "{:.0f}"),
    ("Vel. Máx",        "vel_max_kmh",     "{:.1f} km/h"),
    ("Dist/min",        "dist_min",        "{:.1f} m/min"),
]
jugadoras_ses = sorted(df_ses["nombre"].unique())

if len(jugadoras_ses) < 2:
    st.info("Se necesitan al menos 2 jugadoras en la sesión filtrada para comparar.")
else:
    # jugadoras_ses depende de la Sesión elegida arriba, así que puede
    # cambiar entre una visita y otra — sanear la selección guardada contra
    # las opciones actuales antes de restaurarla.
    for k in ("cmp_a", "cmp_b"):
        if f"__persist_{k}" in st.session_state and st.session_state[f"__persist_{k}"] not in jugadoras_ses:
            del st.session_state[f"__persist_{k}"]

    col_sel_a, _, col_sel_b = st.columns([1, 0.1, 1])
    with col_sel_a:
        init_persistent("cmp_a", jugadoras_ses[0])
        jugadora_a = st.selectbox("Jugadora A", jugadoras_ses, key="cmp_a",
                                   on_change=lambda: save_persistent("cmp_a"))
    with col_sel_b:
        idx_b = 1 if len(jugadoras_ses) > 1 else 0
        init_persistent("cmp_b", jugadoras_ses[idx_b])
        jugadora_b = st.selectbox("Jugadora B", jugadoras_ses, key="cmp_b",
                                   on_change=lambda: save_persistent("cmp_b"))

    fila_a = df_ses[df_ses["nombre"] == jugadora_a].iloc[0]
    fila_b = df_ses[df_ses["nombre"] == jugadora_b].iloc[0]

    col_card_a, col_rows, col_card_b = st.columns([1, 2.2, 1])

    with col_card_a:
        st.markdown(
            compare_card_html("🏑", jugadora_a, COMPARE_COLOR_A,
                              foto_jugadora_path(fila_a["player_id"])),
            unsafe_allow_html=True,
        )

    with col_rows:
        st.markdown(compare_rows_html(COMPARAR_METRICAS, fila_a, fila_b,
                                       COMPARE_COLOR_A, COMPARE_COLOR_B),
                    unsafe_allow_html=True)

    with col_card_b:
        st.markdown(
            compare_card_html("🏑", jugadora_b, COMPARE_COLOR_B,
                              foto_jugadora_path(fila_b["player_id"])),
            unsafe_allow_html=True,
        )

    st.caption("Cada métrica se compara en su propia escala (barra más larga = valor más alto entre las dos).")

st.divider()

# ── Fatiga por cuarto (Q1-Q4) ───────────────────────────────────────────────
st.subheader("🏑 Fatiga por cuarto — Partidos")

df_cuartos = df[(df["tipo_sesion"] == TIPOS_SESION[2]) & (df["cuarto"] != "—")].copy()
if pos_sel is not None:
    df_cuartos = df_cuartos[df_cuartos["posicion"].isin(pos_sel)]

if df_cuartos.empty:
    st.info(
        "Todavía no hay sesiones de Partido cargadas por cuarto (Q1-Q4) para "
        "analizar fatiga. Subí un partido con CSV por cuarto en el panel de arriba."
    )
else:
    # Un partido puntual, no el agregado de todos los que matchean los
    # filtros de arriba — "fatiga por cuarto" solo tiene sentido leído
    # dentro de un mismo partido, promediar cuartos entre partidos distintos
    # mezclaría rivales/exigencias distintas en la misma barra.
    fmt_fecha = lambda f: f.strftime("%d/%m/%Y") if hasattr(f, "strftime") else str(f)
    df_cuartos["partido_label"] = df_cuartos.apply(
        lambda r: fmt_fecha(r["fecha"]) + (f" vs {r['rival']}" if r.get("rival") else ""),
        axis=1,
    )
    partidos_fatiga_disp = (
        df_cuartos[["fecha", "partido_label"]]
        .drop_duplicates()
        .sort_values("fecha", ascending=False)["partido_label"]
        .tolist()
    )

    METRICA_FATIGA = {
        "Distancia total (m)": "distancia_total",
        "HSR Distance (m)":    "hsr",
        "Dist/min (m/min)":    "dist_min",
    }

    col_partido_fatiga, col_jugadora_fatiga, col_metrica_fatiga = st.columns(3)
    with col_partido_fatiga:
        init_persistent("partido_fatiga", partidos_fatiga_disp[0])
        partido_fatiga_sel = st.selectbox("Partido", partidos_fatiga_disp, key="partido_fatiga",
                                           on_change=lambda: save_persistent("partido_fatiga"))

    df_partido_fatiga_base = df_cuartos[df_cuartos["partido_label"] == partido_fatiga_sel]
    jugadoras_fatiga_disp = ["Equipo (promedio)"] + sorted(df_partido_fatiga_base["nombre"].unique())

    # jugadoras_fatiga_disp depende del Partido elegido arriba (cascada) —
    # si la jugadora guardada no jugó este partido, sanear antes de restaurar.
    if ("__persist_jugadora_fatiga" in st.session_state
            and st.session_state["__persist_jugadora_fatiga"] not in jugadoras_fatiga_disp):
        del st.session_state["__persist_jugadora_fatiga"]

    with col_jugadora_fatiga:
        init_persistent("jugadora_fatiga", jugadoras_fatiga_disp[0])
        jugadora_fatiga_sel = st.selectbox("Jugadora", jugadoras_fatiga_disp, key="jugadora_fatiga",
                                            on_change=lambda: save_persistent("jugadora_fatiga"))
    with col_metrica_fatiga:
        init_persistent("sel_fatiga", list(METRICA_FATIGA.keys())[0])
        sel_fatiga = st.selectbox("Métrica", list(METRICA_FATIGA.keys()), key="sel_fatiga",
                                   on_change=lambda: save_persistent("sel_fatiga"))
    col_fatiga = METRICA_FATIGA[sel_fatiga]

    if jugadora_fatiga_sel == "Equipo (promedio)":
        df_partido_fatiga = df_partido_fatiga_base
    else:
        df_partido_fatiga = df_partido_fatiga_base[df_partido_fatiga_base["nombre"] == jugadora_fatiga_sel]

    resumen_cuarto = (
        df_partido_fatiga.groupby("cuarto")[col_fatiga]
                  .mean()
                  .reindex(CUARTOS)
                  .dropna()
                  .reset_index()
    )
    # % de cambio respecto al cuarto anterior (Q1 no tiene "anterior")
    resumen_cuarto["pct_cambio"] = resumen_cuarto[col_fatiga].pct_change() * 100

    fig_fatiga = px.bar(
        resumen_cuarto, x="cuarto", y=col_fatiga,
        labels={"cuarto": "Cuarto", col_fatiga: sel_fatiga},
        text=col_fatiga,
    )
    fig_fatiga.update_traces(
        texttemplate="%{text:,.1f}", textposition="outside",
        textfont=dict(color=CHART_FONT),
        marker=dict(color=COMPARE_COLOR_A, cornerradius=4, line=dict(width=0)),
    )
    fig_fatiga.update_layout(**plotly_bar_layout(360))
    fig_fatiga.update_xaxes(categoryorder="array", categoryarray=CUARTOS)

    for _, fila in resumen_cuarto.iterrows():
        if pd.notna(fila["pct_cambio"]):
            baja = fila["pct_cambio"] < 0
            fig_fatiga.add_annotation(
                x=fila["cuarto"], y=fila[col_fatiga], yshift=32,
                text=f"{'▼' if baja else '▲'} {fila['pct_cambio']:+.0f}%",
                showarrow=False,
                font=dict(color="#f87171" if baja else "#34d399", size=12),
            )

    st.plotly_chart(fig_fatiga, use_container_width=True)
    sujeto_fatiga = "del equipo" if jugadora_fatiga_sel == "Equipo (promedio)" else f"de {jugadora_fatiga_sel}"
    st.caption(
        f"Evolución {sujeto_fatiga} por cuarto en el partido elegido. El porcentaje "
        "arriba de cada barra es el cambio respecto al cuarto anterior — una caída "
        "marcada (en rojo) sugiere fatiga acumulada de partido."
    )

st.divider()

# ── Tabla detallada ────────────────────────────────────────────────────────
st.subheader("Tabla completa de la sesión")
cols_tabla = ["nombre", "duracion_min", "distancia_total",
              "dist_min", "hsr", "hsr_pct", "sprints",
              "acc_3", "decc_3", "player_load", "pl_min", "vel_max_kmh"]
st.dataframe(
    df_ses[cols_tabla].sort_values("distancia_total", ascending=False)
                      .reset_index(drop=True),
    use_container_width=True,
    hide_index=True,
)

st.divider()

# ── Informe PDF ────────────────────────────────────────────────────────────
st.subheader("📄 Informe PDF")
st.caption("Genera un PDF con los KPIs, los gráficos y la tabla de la sesión filtrada arriba.")

if st.button("Generar informe PDF", key="cf_gen_pdf"):
    with st.spinner("Generando PDF..."):
        try:
            secciones_pdf = [
                SeccionFigura(sel_principal, fig_principal, alto_cm=10),
                SeccionFigura(sel_izq, fig_izq),
                SeccionFigura(sel_der, fig_der),
            ]

            if len(jugadoras_ses) >= 2:
                secciones_pdf.append(SeccionFotos("Jugadoras", [
                    (jugadora_a, foto_jugadora_path(fila_a["player_id"])),
                    (jugadora_b, foto_jugadora_path(fila_b["player_id"])),
                ]))
                df_comp_pdf = pd.DataFrame({
                    "Métrica": [m[0] for m in COMPARAR_METRICAS],
                    jugadora_a: [fmt.format(fila_a.get(col, 0) or 0) for _, col, fmt in COMPARAR_METRICAS],
                    jugadora_b: [fmt.format(fila_b.get(col, 0) or 0) for _, col, fmt in COMPARAR_METRICAS],
                })
                secciones_pdf.append(SeccionTabla("Comparativa entre jugadoras", df_comp_pdf))

            if not df_cuartos.empty:
                secciones_pdf.append(SeccionFigura(f"Fatiga por cuarto — {sel_fatiga}", fig_fatiga))

            tabla_sesion_pdf = df_ses[cols_tabla].sort_values("distancia_total", ascending=False).copy()
            redondeos = {"duracion_min": 0, "distancia_total": 0, "dist_min": 1, "hsr": 0,
                         "hsr_pct": 1, "sprints": 0, "acc_3": 0, "decc_3": 0,
                         "player_load": 1, "pl_min": 2, "vel_max_kmh": 1}
            for col, dec in redondeos.items():
                tabla_sesion_pdf[col] = tabla_sesion_pdf[col].round(dec)
            tabla_sesion_pdf.columns = ["Jugadora", "Dur (min)", "Dist (m)", "Dist/min", "HSR (m)",
                                        "HSR %", "Sprints", "ACC>3", "DECC>3", "Player Load",
                                        "PL/min", "Vel Máx (km/h)"]
            secciones_pdf.append(SeccionTabla("Tabla completa de la sesión", tabla_sesion_pdf))

            fecha_sel_str = (fecha_sel.strftime("%d/%m/%Y") if hasattr(fecha_sel, "strftime")
                              else str(fecha_sel))
            pdf_bytes = generar_pdf_reporte(
                titulo="Carga Física",
                subtitulo=f"Centro Naval Hockey — {fecha_sel_str} · {tipo_sel}",
                kpis=kpis,
                secciones=secciones_pdf,
            )
            st.session_state["_cf_pdf_bytes"] = pdf_bytes
        except Exception as e:
            st.error(f"No se pudo generar el PDF: {e}")

if "_cf_pdf_bytes" in st.session_state:
    st.download_button(
        "⬇️ Descargar informe PDF",
        data=st.session_state["_cf_pdf_bytes"],
        file_name=f"carga_fisica_{datetime.datetime.now():%Y%m%d_%H%M}.pdf",
        mime="application/pdf",
        key="cf_download_pdf",
    )

st.divider()

# ── Subir nueva sesión GPS ─────────────────────────────────────────────────
n_extra = len(st.session_state.get("gps_extra", []))
expander_label = (
    f"📂 Subir nueva sesión GPS  ·  {n_extra} sesión/es cargada/s en esta sesión"
    if n_extra else "📂 Subir nueva sesión GPS"
)

with st.expander(expander_label, expanded=(n_extra == 0)):
    tab_fis, tab_tt, tab_pa = st.tabs(
        ["🏃 Sesión Física", "🥅 Sesión Técnico-Táctica", "🏑 Partido"]
    )
    with tab_fis:
        _panel_upload(TIPOS_SESION[0], "fis")
    with tab_tt:
        _panel_upload(TIPOS_SESION[1], "tt")
    with tab_pa:
        st.caption("Subí el CSV de cada cuarto (Catapult los exporta por separado).")
        _panel_partido()

    # Download del parquet actualizado
    extras_dl = st.session_state.get("gps_extra", [])
    if extras_dl:
        st.divider()
        st.caption(
            "Descargá el parquet actualizado y commitealo al repo para que "
            "Streamlit Cloud lo persista entre sesiones."
        )
        try:
            base_dl = pd.read_parquet(PROCESSED / "gps_procesado.parquet")
            base_dl = _backfill_columnas(base_dl)
            base_dl = calcular_intensidad_relativa(base_dl)
        except FileNotFoundError:
            base_dl = pd.DataFrame()

        df_dl = pd.concat([base_dl] + extras_dl, ignore_index=True)
        df_dl = (df_dl.drop_duplicates(subset=["player_id", "fecha", "tipo_sesion", "cuarto"],
                                       keep="last")
                      .sort_values(["fecha", "nombre"])
                      .reset_index(drop=True))

        buf = io.BytesIO()
        df_dl.to_parquet(buf, index=False)
        buf.seek(0)

        st.download_button(
            "⬇️ Descargar gps_procesado.parquet actualizado",
            data=buf,
            file_name="gps_procesado.parquet",
            mime="application/octet-stream",
            use_container_width=True,
        )
