# pages/09_biblioteca_ejercicios.py
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.append(str(Path(__file__).parent.parent))
from settings import PROCESSED, TIPOS_SESION, LOGO_PATH, PAGE_COLORS
from src.utils.auth import require_login
from src.metrics.biblioteca_ejercicios import (
    perfil_por_ejercicio, variables_destacadas, METRICA_LABELS,
)
from src.ui.theme import inject_dashboard_css, ICONS, CHART_FONT
from src.ui.charts import plotly_bar_layout
from src.ui.components import home_button, page_header, kpi_row, section_title

st.set_page_config(page_title="Biblioteca de Ejercicios", page_icon=str(LOGO_PATH), layout="wide")

require_login()
inject_dashboard_css()
home_button()
page_header("Biblioteca de Ejercicios", "Demanda física real (GPS) por ejercicio Técnico-Táctico",
            icon=ICONS["biblioteca"], color=PAGE_COLORS["biblioteca"])
st.divider()


# ── Cargar datos ─────────────────────────────────────────────────────────
@st.cache_data
def cargar_base():
    df = pd.read_parquet(PROCESSED / "gps_procesado.parquet")
    if "tipo_sesion" not in df.columns:
        df["tipo_sesion"] = TIPOS_SESION[0]
    if "cuarto" not in df.columns:
        df["cuarto"] = "—"
    if "ejercicio" not in df.columns:
        df["ejercicio"] = "—"
    return df

try:
    df = cargar_base()
except FileNotFoundError:
    df = pd.DataFrame()

if df.empty:
    st.info("Sin datos GPS todavía — cargá sesiones desde Carga Física.")
    st.stop()

df_perfil = perfil_por_ejercicio(df)

if df_perfil.empty:
    st.info(
        "Todavía no hay bloques de Técnico-Táctico tageados con un ejercicio del "
        "catálogo. Subí sesiones por bloque desde **Carga Física → Sesión "
        "Técnico-Táctica**, eligiendo el ejercicio real de cada CSV."
    )
    st.stop()

# ── KPIs ─────────────────────────────────────────────────────────────────
kpi_row([
    (ICONS["biblioteca"], "Ejercicios en el catálogo usados", len(df_perfil), PAGE_COLORS["biblioteca"]),
    (ICONS["reloj"], "Bloques registrados", int(df_perfil["n_bloques"].sum()), PAGE_COLORS["carga_fisica"]),
    (ICONS["target"], "Muestras jugadora-bloque", int(df_perfil["n_muestras"].sum()), PAGE_COLORS["perfil"]),
])

st.divider()

# ── Ranking por métrica elegida ─────────────────────────────────────────
section_title("Ranking de ejercicios por variable", PAGE_COLORS["biblioteca"], icon=ICONS["biblioteca"])

cols_metrica = [c for c in df_perfil.columns if c.endswith("_por_min")]
opciones_metrica = {METRICA_LABELS.get(c, c): c for c in cols_metrica}
label_sel = st.selectbox("Variable a comparar", list(opciones_metrica.keys()))
col_sel = opciones_metrica[label_sel]

fig = px.bar(
    df_perfil.sort_values(col_sel, ascending=True),
    x=col_sel, y="ejercicio",
    orientation="h",
    color=col_sel,
    color_continuous_scale=["#3e2723", "#a1887f", "#efebe9"],
    labels={col_sel: label_sel, "ejercicio": ""},
    text=col_sel,
)
fig.update_traces(
    texttemplate="%{text:.1f}", textposition="outside", cliponaxis=False,
    textfont=dict(color=CHART_FONT),
    marker=dict(cornerradius=4, line=dict(width=0)),
)
fig.update_layout(**plotly_bar_layout(max(240, 60 + 40 * len(df_perfil))))
st.plotly_chart(fig, use_container_width=True)

st.caption(
    "Todo normalizado por minuto — los bloques duran distinto, comparar totales "
    "crudos entre un bloque de 8 minutos y uno de 20 sería engañoso."
)

st.divider()

# ── Qué destaca cada ejercicio ──────────────────────────────────────────
section_title("Qué carga más cada ejercicio", PAGE_COLORS["biblioteca"], icon=ICONS["target"])

df_destacadas = variables_destacadas(df_perfil, top_n=3)

if df_destacadas.empty:
    st.info("Hace falta al menos 2 ejercicios distintos con datos para poder comparar cuál se destaca en qué.")
else:
    for ejercicio in sorted(df_destacadas["ejercicio"].unique()):
        fila = df_perfil[df_perfil["ejercicio"] == ejercicio].iloc[0]
        destacadas_ej = df_destacadas[df_destacadas["ejercicio"] == ejercicio]
        bullets = "".join(
            f'<li>{METRICA_LABELS.get(r["metrica"], r["metrica"])}: '
            f'<b>{r["valor_por_min"]:.1f}</b> por minuto '
            f'({"+" if r["zscore"] >= 0 else ""}{r["zscore"]:.1f} vs. resto del catálogo)</li>'
            for _, r in destacadas_ej.iterrows()
        )
        st.markdown(
            f'<div class="cn-kpi-card" style="--accent:{PAGE_COLORS["biblioteca"]}; margin-bottom:12px; text-align:left; padding:16px 20px;">'
            f'<b>{ejercicio}</b> — {int(fila["n_bloques"])} bloque(s) registrado(s), '
            f'{fila["duracion_prom_min"]:.0f} min promedio'
            f'<ul style="margin:8px 0 0 18px; padding:0;">{bullets}</ul>'
            f'</div>',
            unsafe_allow_html=True,
        )

st.divider()

# ── Tabla completa ───────────────────────────────────────────────────────
section_title("Perfil completo por ejercicio", PAGE_COLORS["biblioteca"], icon=ICONS["analisis"])

tabla = df_perfil.rename(columns={
    "ejercicio": "Ejercicio", "n_bloques": "Bloques", "n_muestras": "Muestras",
    "duracion_prom_min": "Dur. prom. (min)", "vel_max_kmh_prom": "Vel. Máx prom. (km/h)",
    **{c: METRICA_LABELS[c] for c in cols_metrica},
}).round(1)

st.dataframe(tabla, use_container_width=True, hide_index=True)
