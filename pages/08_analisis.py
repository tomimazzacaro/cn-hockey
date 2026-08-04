# pages/08_analisis.py
import datetime
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.append(str(Path(__file__).parent.parent))
from settings import (
    PROCESSED, WELLNESS_SHEET_ID, ROSTER_SHEET_GID, SESIONES_SHEET_GID, PARAMETROS_SHEET_GID,
    MD_EJERCICIOS_SHEET_GID, TIPOS_SESION, LOGO_PATH, PAGE_COLORS,
    MDS_ENTRENAMIENTO_FOCO, UMBRAL_MUESTRA_MINIMA_MD, UMBRAL_CALIBRACION_PCT,
)
from src.utils.auth import require_login
from src.loaders.roster_loader import cargar_posiciones_desde_sheets
from src.loaders.sesiones_loader import cargar_sesiones_desde_sheets, orden_match_day
from src.loaders.md_ejercicios_loader import cargar_md_ejercicios_desde_sheets
from src.metrics.physical import calcular_intensidad_relativa, calcular_acwr
from src.metrics.parametros import evaluar_por_jugadora
from src.metrics.foda import (
    resumen_duracion_por_md, resumen_cumplimiento_por_md, resumen_acwr_por_md,
    detectar_posible_calibracion, dividir_en_bullets,
)
from src.ui.theme import inject_dashboard_css, ICONS, BAR_CATEGORICAL_PALETTE
from src.ui.charts import plotly_grouped_bar_layout
from src.ui.components import (
    home_button, page_header, kpi_row, foda_quadrant_html, periodizacion_cards_html,
)
from src.ui.filtros import popover_multiselect
from src.ui.asistente import cargar_parametros_cacheado
from src.reports.pdf_builder import generar_pdf_reporte, SeccionFigura, SeccionTabla

st.set_page_config(page_title="Análisis", page_icon=str(LOGO_PATH), layout="wide")

require_login()
inject_dashboard_css()
home_button()
page_header("Análisis", "FODA de entrenamientos — MD-5 / MD-4 / MD-2",
            icon=ICONS["analisis"], color=PAGE_COLORS["analisis"])
st.divider()

# ── Notas curadas — juicio del cuerpo técnico, no calculado ────────────────
# Texto fijo a propósito (ver plan de la página): si hay que cambiarlo, se
# edita acá, no hay un campo editable en runtime.
_NOTAS_PERIODIZACION = {
    "MD-5": [
        "Día de bajo volumen dentro del microciclo. Entrenamientos basados en la "
        "recuperación y fijación de conceptos.",
        "Foco en trabajos de fuerza estructural, aeróbicos y técnico-tácticos.",
        "ACC y DECC bajas/moderadas.",
        "Mínima o nula inclusión de HSR y Sprints.",
    ],
    "MD-4": [
        "Entrenamiento basado en grandes volúmenes. Distancia total similar a partido.",
        "Desarrollo de HSR, distancia relativa alta.",
        "Aumento de trabajo neuromuscular (ACC y DECC intensas).",
        "Sesión del microciclo con el mayor número y volumen de acciones a alta intensidad.",
    ],
    "MD-2": [
        "Entrenamiento tapering, bajando notablemente el volumen.",
        "Fundamental priorizar la calidad e intensidad de los ejercicios.",
        "Exposición a Sprints, cortos e intensos (activar sistema neuromuscular).",
        "Sesión del microciclo con el volumen más bajo de todos.",
    ],
}
_NOTA_TIEMPOS_MUERTOS = (
    "La duración de sesión depende de un corte manual de \"tiempos muertos\" en el "
    "GPS que no siempre se aplica — una duración inusualmente larga o muy variable "
    "puede ser una sesión real distinta, o simplemente un corte que faltó. Revisar "
    "la planilla de esa fecha antes de sacar conclusiones solo con el dato crudo."
)
_NOTA_TESTS_FISICOS = (
    "Incorporar YoYo Test y Test de Fuerza Máxima permitiría cruzar la capacidad "
    "física de base de cada jugadora con la demanda real de entrenamiento — hoy "
    "este análisis solo ve carga externa (GPS), no capacidad individual."
)
_UMBRAL_BULLET = 0.70  # a partir de qué % un hallazgo entra como bullet del FODA (no es un umbral de calidad de dato, solo de cuánto mostrar)

# ── Cargar datos ─────────────────────────────────────────────────────────────
@st.cache_data
def cargar_base():
    df = pd.read_parquet(PROCESSED / "gps_procesado.parquet")
    if "tipo_sesion" not in df.columns:
        df["tipo_sesion"] = TIPOS_SESION[0]
    if "cuarto" not in df.columns:
        df["cuarto"] = "—"
    return calcular_intensidad_relativa(df)

try:
    df = cargar_base()
except FileNotFoundError:
    df = pd.DataFrame()

if df.empty:
    st.info("Sin datos GPS todavía — cargá sesiones desde Carga Física.")
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

df_parametros = cargar_parametros_cacheado(WELLNESS_SHEET_ID, PARAMETROS_SHEET_GID)


@st.cache_data(ttl=3600)
def cargar_md_ejercicios():
    try:
        return cargar_md_ejercicios_desde_sheets(WELLNESS_SHEET_ID, MD_EJERCICIOS_SHEET_GID)
    except Exception:
        return None

df_md_ejercicios = cargar_md_ejercicios()
# {match_day: {"fisico": [...bullets...], "tecnico_tactico": [...bullets...]}}
# — ya parseado a viñetas acá (no en el componente de UI), para que
# periodizacion_cards_html() reciba listas listas para pintar.
ejercicios_por_md = {}
if df_md_ejercicios is not None:
    for _, fila in df_md_ejercicios.iterrows():
        ejercicios_por_md[fila["match_day"]] = {
            "fisico": dividir_en_bullets(fila["fisico"]),
            "tecnico_tactico": dividir_en_bullets(fila["tecnico_tactico"]),
        }

# ── Filtrar a entrenamientos (sin Partido) ──────────────────────────────────
df_train_all = df[df["tipo_sesion"] != TIPOS_SESION[2]].copy()

if df_train_all.empty or "match_day" not in df_train_all.columns:
    st.info("No hay sesiones de entrenamiento clasificadas por Match Day todavía.")
    st.stop()

mds_disponibles = sorted(
    [m for m in df_train_all["match_day"].dropna().unique() if m != "Sin clasificar"],
    key=orden_match_day,
)
if not mds_disponibles:
    st.info("No hay entrenamientos con Match Day clasificado en la hoja de Sesiones.")
    st.stop()

col_md, col_pos = st.columns([1.4, 1])
with col_md:
    default_md = [m for m in MDS_ENTRENAMIENTO_FOCO if m in mds_disponibles] or mds_disponibles
    md_sel = popover_multiselect("Match Day", mds_disponibles, "an_md_sel", default=default_md)
with col_pos:
    if df_pos is not None:
        posiciones = sorted(df_pos["posicion"].dropna().unique())
        pos_sel = popover_multiselect("Posición", posiciones, "an_pos_sel")
    else:
        pos_sel = None

if not md_sel:
    st.info("Elegí al menos un Match Day para analizar.")
    st.stop()

df_train = df_train_all[df_train_all["match_day"].isin(md_sel)]
if pos_sel is not None:
    df_train = df_train[df_train["posicion"].isin(pos_sel)]

if df_train.empty:
    st.info("Ninguna sesión coincide con los filtros elegidos.")
    st.stop()

orden_md_sel = [m for m in mds_disponibles if m in md_sel]

st.divider()

# ── KPIs ──────────────────────────────────────────────────────────────────
n_sesiones = len(df_train[["fecha", "tipo_sesion"]].drop_duplicates())
n_jugadoras = df_train["nombre"].nunique()

kpi_row([
    ("👥", "Jugadoras", f"{n_jugadoras}", BAR_CATEGORICAL_PALETTE[0]),
    ("📅", "Sesiones", f"{n_sesiones}", BAR_CATEGORICAL_PALETTE[1]),
    ("🏑", "Match Days elegidos", f"{len(md_sel)}", BAR_CATEGORICAL_PALETTE[2]),
])

st.divider()

# ── Duración de las sesiones ─────────────────────────────────────────────────
st.subheader("⏱️ Duración de las sesiones")

resumen_dur = resumen_duracion_por_md(df_train)
fig_dur = None
if resumen_dur.empty:
    st.info("Sin datos de duración para los filtros elegidos.")
else:
    fig_dur = px.bar(
        resumen_dur, x="match_day", y="media_min", color="tipo_sesion",
        barmode="group", text="media_min",
        category_orders={"match_day": orden_md_sel},
        labels={"media_min": "Duración media (min)", "match_day": "Match Day",
                "tipo_sesion": "Tipo de sesión"},
    )
    fig_dur.update_traces(texttemplate="%{text:.0f} min", textposition="outside")
    fig_dur.update_layout(**plotly_grouped_bar_layout(360))
    st.plotly_chart(fig_dur, use_container_width=True)

    for _, fila in resumen_dur[resumen_dur["variabilidad_alta"]].iterrows():
        st.warning(
            f"**{fila['match_day']} · {fila['tipo_sesion']}**: duración muy variable entre "
            f"sesiones ({fila['minimo_min']:.0f}-{fila['maximo_min']:.0f} min, desvío "
            f"{fila['desvio_min']:.0f} min sobre una media de {fila['media_min']:.0f} min) — "
            "probablemente algunas sesiones no tuvieron el corte manual de \"tiempos muertos\" "
            "del GPS. Tratar la duración de este grupo con cautela."
        )
    st.caption("Media de duración de sesión (minutos) por Match Day y tipo de sesión.")

st.divider()

# ── Cumplimiento/ACWR — cálculo silencioso, solo para alimentar el FODA ────
# A pedido del usuario ya no se muestran como secciones propias en pantalla
# (ni Cumplimiento por Match Day, ni Distribución ACWR, ni Sesiones atípicas),
# pero el FODA de más abajo sigue necesitando estos números — calibración de
# parámetros, fortaleza de ACWR, debilidades reales por métrica — así que se
# calculan acá sin pintar nada.
resumen_cump = pd.DataFrame()
resultado_calibracion = []

if df_parametros is not None and df_pos is not None:
    df_individual = evaluar_por_jugadora(
        df_train, df_parametros, claves_dia=["posicion", "fecha", "match_day"],
    )
    if not df_individual.empty:
        resumen_cump = resumen_cumplimiento_por_md(df_individual)
        resultado_calibracion = detectar_posible_calibracion(resumen_cump, UMBRAL_CALIBRACION_PCT)

resumen_acwr = resumen_acwr_por_md(df_train)

# ── FODA ──────────────────────────────────────────────────────────────────
st.subheader("📋 FODA de entrenamientos")

st.markdown("**📖 Expectativa de periodización** — referencia del cuerpo técnico:")
_COLOR_POR_MD = {
    "MD-5": BAR_CATEGORICAL_PALETTE[0],
    "MD-4": BAR_CATEGORICAL_PALETTE[1],
    "MD-2": BAR_CATEGORICAL_PALETTE[2],
}
periodizacion_items = [
    (md, _NOTAS_PERIODIZACION[md], _COLOR_POR_MD.get(md, BAR_CATEGORICAL_PALETTE[3]))
    for md in orden_md_sel if md in _NOTAS_PERIODIZACION
]
if periodizacion_items:
    periodizacion_cards_html(periodizacion_items, ejercicios=ejercicios_por_md)

fortalezas, debilidades, oportunidades, amenazas = [], [], [], []

if not resumen_acwr.empty:
    fila_optimo = resumen_acwr[resumen_acwr["zona_acwr"] == "Óptimo"]
    if not fila_optimo.empty:
        pct_prom_optimo = fila_optimo["pct"].mean() * 100
        fortalezas.append(
            f"ACWR en zona <b>Óptimo</b> en el {pct_prom_optimo:.0f}% de las sesiones "
            "filtradas — sin señal de sobrecarga crónica."
        )

metricas_flag_calibracion = {h["metrica"] for h in resultado_calibracion}
if not resumen_cump.empty:
    for _, fila in resumen_cump.iterrows():
        if fila["metrica"] in metricas_flag_calibracion:
            continue  # ya va en Amenazas como posible problema de calibración
        if fila["pct_por_debajo"] >= _UMBRAL_BULLET:
            debilidades.append(
                f"<b>{fila['metrica']}</b> por debajo del rango en el "
                f"{fila['pct_por_debajo']*100:.0f}% de las sesiones de {fila['match_day']}."
            )
        elif fila["pct_por_encima"] >= _UMBRAL_BULLET:
            debilidades.append(
                f"<b>{fila['metrica']}</b> por encima del rango en el "
                f"{fila['pct_por_encima']*100:.0f}% de las sesiones de {fila['match_day']} "
                "— evaluar si es sobrecarga."
            )
        elif fila["pct_en_rango"] >= _UMBRAL_BULLET:
            fortalezas.append(
                f"<b>{fila['metrica']}</b> en rango en el {fila['pct_en_rango']*100:.0f}% de "
                f"las sesiones de {fila['match_day']}."
            )

oportunidades.append(
    "El z-score histórico (ya disponible en el Asistente de Parámetros de las otras páginas de "
    "fitting) permite separar un pico puntual de una jugadora, contra su propio historial, de un "
    "patrón sistemático de todo el equipo antes de ajustar la planificación de un Match Day."
)
if df_pos is not None:
    oportunidades.append(
        "Hay diferencias marcadas de exigencia por posición dentro del mismo Match Day — se "
        "puede prescribir carga diferenciada por puesto (filtrando por Posición arriba) en vez "
        "de un objetivo único para todo el equipo."
    )
oportunidades.append(_NOTA_TESTS_FISICOS)

# ACC>2 y DECC>3 suelen quedar flageadas juntas en las 3 MDs — un bullet por
# (métrica, MD) las repite casi textual 5-7 veces. Se consolidan en una sola
# línea que nombra ambas métricas y todas las MDs involucradas, con el rango
# real de % (no siempre es 100% parejo: MD-2 suele dar algo más bajo que
# MD-5/MD-4) en vez de redondear a un solo número inventado.
_METRICAS_ACC_DECC = {"ACC>2", "DECC>3"}
hallazgos_acc_decc = [h for h in resultado_calibracion if h["metrica"] in _METRICAS_ACC_DECC]
hallazgos_resto = [h for h in resultado_calibracion if h["metrica"] not in _METRICAS_ACC_DECC]

if hallazgos_acc_decc:
    mds_involucrados = sorted({h["match_day"] for h in hallazgos_acc_decc}, key=orden_match_day)
    pcts = [h["pct"] * 100 for h in hallazgos_acc_decc]
    pct_min, pct_max = min(pcts), max(pcts)
    rango_pct = f"{pct_min:.0f}%" if pct_min == pct_max else f"{pct_min:.0f}-{pct_max:.0f}%"
    amenazas.append(
        f"Tanto en {', '.join(mds_involucrados)} las <b>ACC</b> y <b>DECC</b> están por debajo "
        f"del rango en el <b>{rango_pct}</b> de las sesiones — patrón demasiado parejo, revisar "
        "el rango del Sheet \"Parametros\" antes de asumir que es un problema de entrenamiento."
    )

for h in hallazgos_resto:
    amenazas.append(
        f"<b>{h['metrica']}</b> ({h['match_day']}): {h['direccion'].lower()} del rango en "
        f"<b>{h['pct']*100:.0f}%</b> de las sesiones — patrón demasiado parejo, revisar el "
        "rango del Sheet \"Parametros\" antes de asumir que es un problema de entrenamiento."
    )
if not resumen_dur.empty:
    muestras_por_md = df_train.groupby("match_day")["fecha"].nunique()
    for md in orden_md_sel:
        n_dias = int(muestras_por_md.get(md, 0))
        if n_dias > 0 and n_dias < UMBRAL_MUESTRA_MINIMA_MD:
            amenazas.append(
                f"<b>{md}</b> tiene solo {n_dias} día(s) de entrenamiento registrados en el "
                "período filtrado — cualquier conclusión sobre esta MD pesa menos que las demás."
            )
amenazas.append(_NOTA_TIEMPOS_MUERTOS)

foda_quadrant_html(fortalezas, debilidades, oportunidades, amenazas)

st.divider()

# ── Tests físicos (próximamente) ────────────────────────────────────────────
st.subheader("🏋️ Tests físicos")
st.info(
    "**Próximamente**: YoYo Test, Test de Fuerza Máxima y otras evaluaciones tomadas al "
    "plantel. Hoy este análisis solo cruza datos de GPS (carga externa) — falta definir la "
    "estructura de carga de esos datos para poder cruzarlos acá."
)

st.divider()

# ── Informe PDF ────────────────────────────────────────────────────────────
st.subheader("📄 Informe PDF")
st.caption("Genera un PDF con el resumen de duración y el FODA de esta selección.")

if st.button("Generar informe PDF", key="an_gen_pdf"):
    with st.spinner("Generando PDF..."):
        try:
            secciones_pdf = []

            if not resumen_dur.empty and fig_dur is not None:
                df_dur_pdf = resumen_dur.rename(columns={
                    "match_day": "Match Day", "tipo_sesion": "Tipo de sesión",
                    "media_min": "Media (min)", "desvio_min": "Desvío (min)",
                    "minimo_min": "Mínimo (min)", "maximo_min": "Máximo (min)", "n": "N",
                })[["Match Day", "Tipo de sesión", "Media (min)", "Desvío (min)",
                    "Mínimo (min)", "Máximo (min)", "N"]].copy()
                for col in ["Media (min)", "Desvío (min)", "Mínimo (min)", "Máximo (min)"]:
                    df_dur_pdf[col] = df_dur_pdf[col].map(lambda v: f"{v:.0f}")
                secciones_pdf.append(SeccionFigura("Duración de las sesiones", fig_dur))
                secciones_pdf.append(SeccionTabla("Duración — detalle", df_dur_pdf))

            filas_foda_pdf = (
                [{"Cuadrante": "Fortalezas", "Hallazgo": b} for b in fortalezas]
                + [{"Cuadrante": "Debilidades", "Hallazgo": b} for b in debilidades]
                + [{"Cuadrante": "Oportunidades", "Hallazgo": b} for b in oportunidades]
                + [{"Cuadrante": "Amenazas", "Hallazgo": b} for b in amenazas]
            )
            if filas_foda_pdf:
                secciones_pdf.append(SeccionTabla(
                    "FODA de entrenamientos", pd.DataFrame(filas_foda_pdf, columns=["Cuadrante", "Hallazgo"]),
                ))

            kpis_pdf = [
                ("Jugadoras", f"{n_jugadoras}"),
                ("Sesiones", f"{n_sesiones}"),
                ("Match Days", ", ".join(md_sel)),
            ]
            pdf_bytes = generar_pdf_reporte(
                titulo="Análisis",
                subtitulo=f"Centro Naval Hockey — FODA de entrenamientos · {', '.join(md_sel)}",
                kpis=kpis_pdf,
                secciones=secciones_pdf,
            )
            st.session_state["_an_pdf_bytes"] = pdf_bytes
        except Exception as e:
            st.error(f"No se pudo generar el PDF: {e}")

if "_an_pdf_bytes" in st.session_state:
    st.download_button(
        "⬇️ Descargar informe PDF",
        data=st.session_state["_an_pdf_bytes"],
        file_name=f"analisis_{datetime.datetime.now():%Y%m%d_%H%M}.pdf",
        mime="application/pdf",
        key="an_download_pdf",
    )
