# pages/03_wellness.py
import streamlit as st
import pandas as pd
import plotly.express as px
import sys
from datetime import datetime
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from settings import (
    PROCESSED, WELLNESS_SHEET_ID, WELLNESS_SHEET_GID, ROSTER_SHEET_GID, LOGO_PATH, PAGE_COLORS,
)
from src.utils.auth import require_login
from src.loaders.wellness_loader import cargar_desde_sheets
from src.loaders.roster_loader import cargar_posiciones_desde_sheets
from src.metrics.wellness import (
    calcular_readiness,
    calcular_tendencia_tqr,
    generar_alertas,
    resumen_alertas_equipo
)
from src.metrics.physical import calcular_acwr, calcular_intensidad_relativa
from src.ui.theme import (
    inject_dashboard_css, LINE_PALETTE, READINESS_CFG, ICONS, BAR_CATEGORICAL_PALETTE,
    CHART_FONT,
)
from src.ui.state import init_persistent, save_persistent
from src.ui.filtros import popover_multiselect
from src.ui.charts import plotly_line_layout
from src.ui.components import (
    kpi_row, acwr_table_html, home_button, page_header,
    molestias_cards_html, alertas_cards_html,
)
from src.reports.pdf_builder import generar_pdf_reporte, SeccionFigura, SeccionTabla

st.set_page_config(page_title="Wellness", page_icon=str(LOGO_PATH), layout="wide")

require_login()
inject_dashboard_css()
home_button()
page_header("Wellness & Readiness", "Carga interna · Recuperación · Alertas diarias",
            icon=ICONS["wellness"], color=PAGE_COLORS["wellness"])
st.divider()

# ── Cargar datos ───────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def cargar_datos():
    try:
        df = cargar_desde_sheets(WELLNESS_SHEET_ID, WELLNESS_SHEET_GID)
        df = calcular_readiness(df)
        df = calcular_tendencia_tqr(df)
        df = generar_alertas(df)
        df = calcular_acwr(df, col_carga="rpe")
        return df
    except Exception as e:
        return None

@st.cache_data(ttl=3600)
def cargar_posiciones():
    try:
        return cargar_posiciones_desde_sheets(WELLNESS_SHEET_ID, ROSTER_SHEET_GID)
    except Exception:
        return None

df     = cargar_datos()
df_pos = cargar_posiciones()

if df is None:
    st.error("No se pudieron cargar los datos de wellness. Verificá que el Google Sheet esté compartido como público (Lector).")
    st.stop()

if df_pos is not None:
    df = df.merge(df_pos[["player_id", "posicion"]], on="player_id", how="left")

# ── Selectores: fechas + posición ──────────────────────────────────────────
col_fecha, col_pos = st.columns([2, 1])

with col_fecha:
    fechas_disponibles = sorted(df["fecha"].unique(), reverse=True)
    fmt_fecha = lambda x: x.strftime("%d/%m/%Y") if hasattr(x, "strftime") else str(x)
    fechas_sel = popover_multiselect(
        "Fechas", fechas_disponibles, "well_fechas_sel",
        default=[fechas_disponibles[0]], format_func=fmt_fecha,
    )

with col_pos:
    if df_pos is not None:
        posiciones = sorted(df_pos["posicion"].dropna().unique())
        pos_sel = popover_multiselect("Posición", posiciones, "well_pos_sel")
    else:
        pos_sel = None

if not fechas_sel:
    st.warning("Seleccioná al menos una fecha.")
    st.stop()

df_filtrado = df[df["fecha"].isin(fechas_sel)]
if pos_sel is not None:
    df_filtrado = df_filtrado[df_filtrado["posicion"].isin(pos_sel)]

# Último registro por jugadora dentro de las fechas seleccionadas
df_hoy = (df_filtrado.sort_values("fecha")
                     .groupby("player_id")
                     .last()
                     .reset_index())

# ── KPIs ───────────────────────────────────────────────────────────────────
totalmente_apta = (df_hoy["readiness_zona"] == "Totalmente Apta").sum()
apta_moderado   = (df_hoy["readiness_zona"] == "Apta Moderado").sum()
precaucion      = (df_hoy["readiness_zona"] == "Precaución").sum()
no_aptas        = (df_hoy["readiness_zona"] == "No Apta").sum()
con_molest      = df_hoy["molestia_flag"].sum()

if len(fechas_sel) == 1:
    fecha_label = fechas_sel[0].strftime("%d/%m/%Y") if hasattr(fechas_sel[0], "strftime") else str(fechas_sel[0])
else:
    fecha_label = f"{len(fechas_sel)} fechas"

kpis_well = [
    ("📅", "Fecha",           fecha_label,        BAR_CATEGORICAL_PALETTE[0]),
    ("✅", "Totalmente Apta", totalmente_apta,    READINESS_CFG["Totalmente Apta"]["color"]),
    ("🙂", "Apta Moderado",   apta_moderado,      READINESS_CFG["Apta Moderado"]["color"]),
    ("⚠️", "Precaución",      precaucion,         READINESS_CFG["Precaución"]["color"]),
    ("🚨", "No Aptas",        no_aptas,           READINESS_CFG["No Apta"]["color"]),
    ("🤕", "Con molestias",   con_molest,         READINESS_CFG["Precaución"]["color"]),
]
kpi_row(kpis_well)

st.divider()

# ── ACWR Interno (RPE) vs Externo (GPS) ────────────────────────────────────
@st.cache_data
def cargar_gps():
    # El ACWR Externo se recalcula más abajo según la métrica que elija el
    # usuario (Player Load, Distancia Total, HSR...), así que acá solo se
    # deja la intensidad relativa — calcular_acwr() depende de esa elección.
    try:
        df_gps = pd.read_parquet(PROCESSED / "gps_procesado.parquet")
        return calcular_intensidad_relativa(df_gps)
    except Exception:
        return None

df_gps = cargar_gps()

METRICAS_ACWR_EXTERNO = {
    "Player Load":     "player_load",
    "Distancia Total": "distancia_total",
    "HSR Distance":    "hsr",
    "Sprints":         "sprints",
    "ACC >2":          "acc_2",
    "DECC >3":         "decc_3",
}

col_acwr_rpe, col_acwr_gps = st.columns([1.1, 0.9], gap="large")

with col_acwr_rpe:
    st.subheader("ACWR Interno — Esfuerzo Percibido (RPE)")
    n_registros = df["fecha"].nunique()
    acwr_table_html(df_hoy, n_registros)

with col_acwr_gps:
    init_persistent("well_metrica_acwr_ext", next(iter(METRICAS_ACWR_EXTERNO)))
    metrica_acwr_label = st.selectbox(
        "Métrica", list(METRICAS_ACWR_EXTERNO.keys()),
        key="well_metrica_acwr_ext",
        on_change=lambda: save_persistent("well_metrica_acwr_ext"),
    )
    st.subheader(f"ACWR Externo — GPS ({metrica_acwr_label})")
    if df_gps is not None:
        df_gps_ext = calcular_acwr(df_gps, col_carga=METRICAS_ACWR_EXTERNO[metrica_acwr_label])
        df_gps_ext_last = df_gps_ext.sort_values("fecha").groupby("player_id").last().reset_index()
        if df_pos is not None:
            df_gps_ext_last = df_gps_ext_last.merge(
                df_pos[["player_id", "posicion"]], on="player_id", how="left"
            )
            if pos_sel is not None:
                df_gps_ext_last = df_gps_ext_last[df_gps_ext_last["posicion"].isin(pos_sel)]
        acwr_table_html(df_gps_ext_last, df_gps_ext["fecha"].nunique())
    else:
        df_gps_ext_last = None
        st.info("Sin datos de GPS disponibles.")

st.divider()

# ── TQR vs RPE ──────────────────────────────────────────────────────────────
st.subheader("TQR vs RPE — Recuperación vs Esfuerzo")

fig_tqr_rpe = px.scatter(
    df_filtrado, x="rpe", y="tqr", text="nombre", hover_name="nombre",
    labels={"rpe": "RPE (1–10)", "tqr": "TQR (1–10)"},
)
# Cuando 2+ jugadoras caen en el mismo (rpe, tqr) exacto, sus etiquetas se
# superponen — alternamos arriba/abajo por orden de aparición en ese punto
# para que se puedan leer todas.
orden_en_punto = df_filtrado.groupby(["rpe", "tqr"]).cumcount()
textposition = ["top center" if i % 2 == 0 else "bottom center" for i in orden_en_punto]
fig_tqr_rpe.update_traces(
    marker=dict(size=12, color=LINE_PALETTE[0], line=dict(width=1.5, color="#ffffff")),
    textposition=textposition,
    textfont=dict(size=10, color=CHART_FONT),
)
fig_tqr_rpe.add_hline(y=5, line_dash="dash", line_color="#FBBC04",
                  annotation_text="Umbral mínimo TQR",
                  annotation_position="top left",
                  annotation_font_color="#FBBC04")
fig_tqr_rpe.add_vline(x=8, line_dash="dash", line_color="#f87171",
                  annotation_text="Alerta RPE alto",
                  annotation_position="bottom right",
                  annotation_font_color="#f87171")
fig_tqr_rpe.update_layout(**plotly_line_layout(420, "TQR vs RPE"))
st.plotly_chart(fig_tqr_rpe, use_container_width=True)

st.divider()

# ── Alertas activas ────────────────────────────────────────────────────────
st.subheader("🚨 Alertas activas")
alertas = resumen_alertas_equipo(df_filtrado)
if len(alertas) > 0:
    alertas_cards_html(alertas)
else:
    st.success("✅ Sin alertas activas en el plantel")

# ── Molestias físicas ──────────────────────────────────────────────────────
st.divider()
st.subheader("🤕 Molestias físicas reportadas")
molestias = (df_filtrado[df_filtrado["molestia_flag"]][["nombre", "fecha", "molestia"]]
             .sort_values(["nombre", "fecha"])
             .reset_index(drop=True))
if len(molestias) > 0:
    molestias_cards_html(molestias)
else:
    st.success("✅ Sin molestias reportadas")

# ── Informe PDF ────────────────────────────────────────────────────────────
st.divider()
st.subheader("📄 Informe PDF")
st.caption(
    "Genera un PDF con los KPIs, el readiness, el ACWR Interno y Externo, la "
    "evolución de TQR/RPE y las alertas — según las fechas y posición filtradas arriba."
)

if st.button("Generar informe PDF", key="well_gen_pdf"):
    with st.spinner("Generando PDF..."):
        try:
            kpis_pdf = [(label, str(valor)) for _icon, label, valor, _color in kpis_well]

            df_acwr_pdf = df_hoy[["nombre", "acwr", "zona_acwr"]].sort_values("acwr", ascending=False).copy()
            df_acwr_pdf["acwr"] = df_acwr_pdf["acwr"].apply(lambda v: f"{v:.2f}" if pd.notna(v) else "—")
            df_acwr_pdf.columns = ["Jugadora", "ACWR", "Zona"]

            secciones_pdf = [
                SeccionTabla("ACWR Interno — Esfuerzo Percibido (RPE)", df_acwr_pdf),
            ]
            if df_gps_ext_last is not None:
                df_acwr_ext_pdf = (
                    df_gps_ext_last[["nombre", "acwr", "zona_acwr"]]
                    .sort_values("acwr", ascending=False).copy()
                )
                df_acwr_ext_pdf["acwr"] = df_acwr_ext_pdf["acwr"].apply(
                    lambda v: f"{v:.2f}" if pd.notna(v) else "—"
                )
                df_acwr_ext_pdf.columns = ["Jugadora", "ACWR", "Zona"]
                secciones_pdf.append(
                    SeccionTabla(f"ACWR Externo — GPS ({metrica_acwr_label})", df_acwr_ext_pdf)
                )
            secciones_pdf.append(SeccionFigura("TQR vs RPE", fig_tqr_rpe))
            if len(alertas) > 0:
                df_alertas_pdf = alertas[
                    ["nombre", "fecha", "tqr", "rpe", "readiness_zona", "total_alertas"]
                ].copy()
                df_alertas_pdf["fecha"] = df_alertas_pdf["fecha"].apply(
                    lambda f: f.strftime("%d/%m/%Y") if hasattr(f, "strftime") else str(f)
                )
                df_alertas_pdf.columns = ["Jugadora", "Fecha", "TQR", "RPE", "Zona", "Alertas"]
                secciones_pdf.append(SeccionTabla("Alertas activas", df_alertas_pdf))
            if len(molestias) > 0:
                df_molestias_pdf = molestias.copy()
                df_molestias_pdf["fecha"] = df_molestias_pdf["fecha"].apply(
                    lambda f: f.strftime("%d/%m/%Y") if hasattr(f, "strftime") else str(f)
                )
                df_molestias_pdf.columns = ["Jugadora", "Fecha", "Molestia"]
                secciones_pdf.append(SeccionTabla("Molestias físicas reportadas", df_molestias_pdf))

            pdf_bytes = generar_pdf_reporte(
                titulo="Wellness & Readiness",
                subtitulo=f"Centro Naval Hockey — {fecha_label}",
                kpis=kpis_pdf,
                secciones=secciones_pdf,
            )
            st.session_state["_well_pdf_bytes"] = pdf_bytes
        except Exception as e:
            st.error(f"No se pudo generar el PDF: {e}")

if "_well_pdf_bytes" in st.session_state:
    st.download_button(
        "⬇️ Descargar informe PDF",
        data=st.session_state["_well_pdf_bytes"],
        file_name=f"wellness_{datetime.now():%Y%m%d_%H%M}.pdf",
        mime="application/pdf",
        key="well_download_pdf",
    )