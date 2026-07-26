# pages/06_partidos.py
import re
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sys
from datetime import datetime
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from settings import (
    PROCESSED, WELLNESS_SHEET_ID, ROSTER_SHEET_GID, SESIONES_SHEET_GID, PARAMETROS_SHEET_GID,
    TIPOS_SESION, CUARTOS, LOGO_PATH, PAGE_COLORS,
)
from src.utils.auth import require_login
from src.utils.helpers import normalizar_0_10
from src.loaders.roster_loader import cargar_posiciones_desde_sheets
from src.loaders.sesiones_loader import cargar_sesiones_desde_sheets
from src.metrics.physical import calcular_intensidad_relativa, agregar_partidos_completos
from src.ui.theme import inject_dashboard_css, LINE_PALETTE, BAR_CATEGORICAL_PALETTE, ICONS
from src.ui.charts import plotly_radar_layout, plotly_grouped_bar_layout
from src.ui.components import (
    home_button, page_header, zebra_rows, resaltar_maximo_columna, kpi_row,
)
from src.ui.filtros import popover_multiselect
from src.ui.asistente import cargar_parametros_cacheado, render_asistente
from src.reports.pdf_builder import generar_pdf_reporte, SeccionFigura, SeccionTabla

st.set_page_config(page_title="Partidos", page_icon=str(LOGO_PATH), layout="wide")

require_login()
inject_dashboard_css()
home_button()
page_header("Partidos", "Radar comparativo de métricas GPS entre partidos",
            icon=ICONS["trofeo"], color=PAGE_COLORS["partidos"])
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

# Base propia para el Asistente de Parámetros — sus filtros (partido,
# posición, jugadora) son independientes de los filtros de arriba (que
# también alimentan el radar), así que se guarda esta copia acá, antes de
# que esos filtros recorten nada.
df_asistente_base = df_partidos.copy()

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
    partidos_sel = popover_multiselect("Partidos", partidos_disp, "pa_partidos_sel")

with col_pos:
    if df_pos is not None:
        posiciones = sorted(df_pos["posicion"].dropna().unique())
        pos_sel = popover_multiselect("Posición", posiciones, "pa_pos_sel")
    else:
        pos_sel = None

with col_metricas:
    metricas_sel = popover_multiselect(
        "Métricas", list(METRICAS_RADAR.keys()), "pa_metricas_sel", default=DEFAULT_METRICAS,
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

# ── KPIs ───────────────────────────────────────────────────────────────────
def _top3_html(serie: pd.Series, fmt: str) -> str:
    """Arma el HTML de una tarjeta KPI con el top 3 de `serie` (ya
    agrupada por jugadora), en texto chico apilado — el valor grande por
    default de .cn-kpi-value no entra bien con 3 nombres."""
    top3 = serie.sort_values(ascending=False).head(3)
    if top3.empty:
        return "—"
    return "<br>".join(
        f'<span style="font-size:0.95rem; font-weight:600">{nombre} '
        f'<span style="color:#93c5fd">{fmt.format(valor)}</span></span>'
        for nombre, valor in top3.items()
    )


def _top3_pdf(serie: pd.Series, fmt: str) -> str:
    """Misma idea que _top3_html pero en el markup mínimo que entiende
    reportlab (<br/> en vez de <br>, sin <span style=...> que no es un tag
    válido ahí) — usado en el KPI del informe PDF."""
    top3 = serie.sort_values(ascending=False).head(3)
    if top3.empty:
        return "—"
    return "<br/>".join(f"{nombre} {fmt.format(valor)}" for nombre, valor in top3.items())


df_top3 = df_filtrado[df_filtrado["partido_label"].isin(partidos_sel)]
top_minutos = df_top3.groupby("nombre")["duracion_min"].sum()
top_hsr     = df_top3.groupby("nombre")["hsr"].sum()
top_vel     = df_top3.groupby("nombre")["vel_max_kmh"].max()

kpis_partidos = [
    ("🏑", "Partidos comparados", f"{len(partidos_sel)}", BAR_CATEGORICAL_PALETTE[0]),
    ("⏱️", "Top 3 — Minutos jugados", _top3_html(top_minutos, "{:.0f}′"), BAR_CATEGORICAL_PALETTE[4]),
    ("🏃", "Top 3 — HSR recorrida", _top3_html(top_hsr, "{:,.0f} m"), BAR_CATEGORICAL_PALETTE[2]),
    ("🚀", "Top 3 — Más veloces", _top3_html(top_vel, "{:.1f} km/h"),
     BAR_CATEGORICAL_PALETTE[7]),
]
kpi_row(kpis_partidos)

st.divider()

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
tabla_valores = (
    tabla[["partido_label"] + metricas_sel]
    .round(1)
    .rename(columns={"partido_label": "Partido"})
    .reset_index(drop=True)
)
tabla_valores_estilizada = (
    tabla_valores.style
    .apply(zebra_rows, axis=1)
    .apply(resaltar_maximo_columna, subset=metricas_sel)
)
# Sin esto, un Styler (a diferencia de un DataFrame plano) se muestra con el
# float crudo (ej. "5906.600000") en vez del valor ya redondeado — acá
# todas las métricas son un promedio de equipo, no una cantidad entera de
# una sola jugadora, así que van todas a 1 decimal parejo (no el esquema
# de decimales por métrica de GPS_COLUMN_CONFIG_METRICAS, pensado para
# tablas de una fila por jugadora).
column_config_valores = {
    m: st.column_config.NumberColumn(alignment="center", format="%.1f")
    for m in metricas_sel
}
st.dataframe(
    tabla_valores_estilizada, use_container_width=True, hide_index=True,
    column_config=column_config_valores,
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
    partidos_q_sel = popover_multiselect("Partido", partidos_disp, "ms_partido_q")

with col_pos_q:
    if df_pos is not None:
        pos_q_sel = popover_multiselect("Posición", posiciones, "ms_pos_q")
    else:
        pos_q_sel = None

with col_metricas_q:
    metricas_q_sel = popover_multiselect(
        "Métricas", list(METRICAS_RADAR.keys()), "ms_metricas_q",
        default=["Distancia total", "Player Load"],
    )

st.divider()

figs_cuartos = []
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

        figs_cuartos = []
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
            figs_cuartos.append((metrica_label, fig_q))

        st.caption(
            "Promedio del equipo (según posición filtrada) por cuarto en cada "
            "partido seleccionado — sirve para ver si la demanda física cae "
            "hacia el final del partido (fatiga) y si eso cambia entre partidos."
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
    col_asist_partido, col_asist_pos, col_asist_jug = st.columns(3)

    with col_asist_partido:
        partidos_asist_sel = popover_multiselect(
            "Partido", partidos_disp, "pa_asist_partido_sel", default=partidos_disp[:1],
        )

    with col_asist_pos:
        if df_pos is not None:
            posiciones_asist = sorted(df_pos["posicion"].dropna().unique())
            pos_asist_sel = popover_multiselect("Posición", posiciones_asist, "pa_asist_pos_sel")
        else:
            pos_asist_sel = None

    with col_asist_jug:
        jugadoras_asist = sorted(df_asistente_base["nombre"].dropna().unique())
        jugadora_asist_sel = popover_multiselect("Jugadora", jugadoras_asist, "pa_asist_jugadora_sel")

    if not partidos_asist_sel:
        st.info("Elegí al menos un partido para evaluar.")
    else:
        df_asistente_partidos = df_asistente_base[
            df_asistente_base["partido_label"].isin(partidos_asist_sel)
        ].copy()
        if pos_asist_sel is not None:
            df_asistente_partidos = df_asistente_partidos[df_asistente_partidos["posicion"].isin(pos_asist_sel)]
        df_asistente_partidos = df_asistente_partidos[df_asistente_partidos["nombre"].isin(jugadora_asist_sel)]

        if df_asistente_partidos.empty:
            st.info("Ninguna jugadora coincide con los filtros de partido, posición y jugadora seleccionados.")
        else:
            # Un partido es, por definición, el día de Match Day en sí ("MD")
            # — no hace falta cruzar contra la hoja de Sesiones para saberlo
            # acá.
            resultado_asistente = render_asistente(
                df_asistente_partidos, df_parametros,
                claves_grupo=["posicion", "partido_label"],
                etiqueta_fn=lambda f: f"{f['posicion']} · {f['partido_label']}",
                etiqueta_header="Posición · Partido",
                match_day="MD",
                caption=(
                    "Promedio del equipo por posición en cada partido elegido, contra el rango "
                    "esperado para cada posición en Match Day — Sprints distancia todavía no "
                    "tiene columna real en el GPS, se suma cuando Catapult la exporte."
                ),
            )

# ── Informe PDF ────────────────────────────────────────────────────────────
st.divider()
st.subheader("📄 Informe PDF")
st.caption("Genera un PDF con el radar comparativo, la tabla de valores reales y el comportamiento por cuarto.")

if st.button("Generar informe PDF", key="pa_gen_pdf"):
    with st.spinner("Generando PDF..."):
        try:
            secciones_pdf = [
                SeccionFigura("Radar comparativo", fig, alto_cm=10),
                SeccionTabla("Valores reales por partido", tabla_valores),
            ]
            for metrica_label, fig_q in figs_cuartos:
                secciones_pdf.append(SeccionFigura(f"Comportamiento por cuarto — {metrica_label}", fig_q))

            if resultado_asistente is not None:
                if not resultado_asistente["tabla_pdf"].empty:
                    secciones_pdf.append(SeccionTabla(
                        "Asistente — Cumplimiento de parámetros", resultado_asistente["tabla_pdf"]
                    ))
                if not resultado_asistente["analisis_pdf"].empty:
                    secciones_pdf.append(SeccionTabla(
                        "Análisis — Fortalezas y debilidades", resultado_asistente["analisis_pdf"]
                    ))

            kpis_pdf = [
                ("Partidos comparados", f"{len(partidos_sel)}"),
                ("Top 3 — Minutos jugados", _top3_pdf(top_minutos, "{:.0f}′")),
                ("Top 3 — HSR recorrida", _top3_pdf(top_hsr, "{:,.0f} m")),
                ("Top 3 — Más veloces", _top3_pdf(top_vel, "{:.1f} km/h")),
            ]
            pdf_bytes = generar_pdf_reporte(
                titulo="Partidos",
                subtitulo=f"Centro Naval Hockey — {len(partidos_sel)} partido/s comparado/s",
                kpis=kpis_pdf,
                secciones=secciones_pdf,
            )
            st.session_state["_pa_pdf_bytes"] = pdf_bytes
        except Exception as e:
            st.error(f"No se pudo generar el PDF: {e}")

if "_pa_pdf_bytes" in st.session_state:
    st.download_button(
        "⬇️ Descargar informe PDF",
        data=st.session_state["_pa_pdf_bytes"],
        file_name=f"partidos_{datetime.now():%Y%m%d_%H%M}.pdf",
        mime="application/pdf",
        key="pa_download_pdf",
    )
