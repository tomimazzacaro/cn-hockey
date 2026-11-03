# pages/10_fuerza.py
# Nombre "fuerza" a propósito: el label del sidebar sale del CSS de
# inject_dashboard_css() (href$="/fuerza"), igual que el resto del nav automático.
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.append(str(Path(__file__).parent.parent))
from settings import (
    FUERZA_SHEET_ID, CATALOGO_FUERZA_SHEET_GID, CATALOGO_RESIST_SHEET_GID,
    FUERZA_PLAN_SHEET_GID, LOGO_PATH, PAGE_COLORS, PROCESSED,
)
from src.utils.auth import require_login
from src.loaders.fuerza_loader import (
    cargar_catalogo_fuerza_desde_sheets, cargar_catalogo_resist_desde_sheets,
    cargar_plan_fuerza_desde_sheets,
    cargar_rm_desde_supabase, cargar_series_desde_supabase,
    cargar_jugadoras_desde_supabase, guardar_series,
)
from src.loaders.wellness_loader import normalizar_nombre
from src.metrics.fuerza import (
    normalizar_registros_rm, rm_vigente, armar_series, enriquecer_series,
    resumen_por_periodo,
)
from src.ui.theme import inject_dashboard_css, ICONS, BAR_CATEGORICAL_PALETTE
from src.ui.charts import plotly_grouped_bar_layout, plotly_line_layout
from src.ui.components import home_button, page_header, kpi_row, section_title
from src.ui.filtros import popover_multiselect
from src.ui.fuerza_planificador import render_planificador
from src.ui.fuerza_ejecutado import render_ejecutado, render_historial

st.set_page_config(page_title="Fuerza", page_icon=str(LOGO_PATH), layout="wide")

require_login()
inject_dashboard_css()
home_button()
page_header("Fuerza", "Planificación, cuantificación y dosificación de la fuerza",
            icon=ICONS["fuerza"], color=PAGE_COLORS["fuerza"])
st.divider()

COLOR_FUERZA = PAGE_COLORS["fuerza"]
MSG_RM_AUTORREPORTADO = ("El RM lo cargan las propias jugadoras desde su app: es "
                         "**autorreportado**, no un test supervisado.")
FILAS_VACIAS_DEFAULT = 3


# ── Cargar datos ─────────────────────────────────────────────────────────────
def _cs_lectura() -> str:
    return st.secrets["supabase"]["wellness_connection_string"]


def _cs_escritura() -> str | None:
    """Credencial del rol fuerza_writer; None si todavía no está en los secrets."""
    return st.secrets["supabase"].get("fuerza_connection_string")


@st.cache_data(ttl=3600)
def cargar_catalogo():
    try:
        return cargar_catalogo_fuerza_desde_sheets(FUERZA_SHEET_ID, CATALOGO_FUERZA_SHEET_GID)
    except Exception:
        return None


@st.cache_data(ttl=3600)
def cargar_catalogo_resist():
    try:
        return cargar_catalogo_resist_desde_sheets(FUERZA_SHEET_ID, CATALOGO_RESIST_SHEET_GID)
    except Exception:
        return None


@st.cache_data(ttl=3600)
def cargar_gps():
    """GPS procesado: de ahí sale la Vmáx de cada jugadora (tiempos objetivo de las pasadas)."""
    try:
        return pd.read_parquet(PROCESSED / "gps_procesado.parquet")
    except Exception:
        return None


@st.cache_data(ttl=3600)
def cargar_plan():
    try:
        return cargar_plan_fuerza_desde_sheets(FUERZA_SHEET_ID, FUERZA_PLAN_SHEET_GID)
    except Exception:
        return None


@st.cache_data(ttl=300)
def cargar_rm():
    try:
        return normalizar_registros_rm(cargar_rm_desde_supabase(_cs_lectura()))
    except Exception:
        return None


@st.cache_data(ttl=60)
def cargar_series():
    try:
        return cargar_series_desde_supabase(_cs_lectura())
    except Exception:
        return None


@st.cache_data(ttl=3600)
def cargar_jugadoras():
    try:
        return cargar_jugadoras_desde_supabase(_cs_lectura())
    except Exception:
        return None


df_catalogo = cargar_catalogo()
if df_catalogo is None or df_catalogo.empty:
    st.error("No se pudo leer el catálogo de fuerza (pestaña \"Catalogo_Fuerza\"). "
             "Revisá que la planilla siga compartida por vínculo y probá recargar en unos minutos.")
    st.stop()

df_catalogo_resist = cargar_catalogo_resist()

# Carga INDIVIDUAL (series por jugadora): etapa 2. Por ahora el plan es general para
# todo el equipo, así que esas pestañas quedan ocultas. Para volver a mostrarlas,
# poner MOSTRAR_INDIVIDUAL = True (el código sigue abajo, sin cambios).
MOSTRAR_INDIVIDUAL = False

nombres_tabs = ["Planificación", "Sesión ejecutada", "Historial"]
if MOSTRAR_INDIVIDUAL:
    nombres_tabs += ["Cargar sesión (individual)", "Historial individual"]
tabs = st.tabs(nombres_tabs)
tab_plan, tab_ejecutado, tab_historial_equipo = tabs[:3]


def _catalogo_resist_ok() -> bool:
    if df_catalogo_resist is None or df_catalogo_resist.empty:
        st.error("No se pudo leer el catálogo de pasadas (pestaña \"Catalogo_resist\"). "
                 "Revisá que la planilla siga compartida por vínculo y probá recargar en unos minutos.")
        return False
    return True


# ── Planificación (plan semanal por Match Day) ───────────────────────────────
with tab_plan:
    if _catalogo_resist_ok():
        render_planificador(_cs_lectura(), _cs_escritura(), df_catalogo, df_catalogo_resist, COLOR_FUERZA,
                           df_gps=cargar_gps())

# ── Sesión ejecutada (equipo): precargada desde el plan ──────────────────────
with tab_ejecutado:
    if _catalogo_resist_ok():
        render_ejecutado(_cs_lectura(), _cs_escritura(), df_catalogo, df_catalogo_resist, COLOR_FUERZA)

# ── Historial del equipo: carga real vs plan y ACWR de fuerza ────────────────
with tab_historial_equipo:
    render_historial(_cs_lectura(), COLOR_FUERZA)


# ── Carga individual (etapa 2, oculta) ───────────────────────────────────────
if MOSTRAR_INDIVIDUAL:
    tab_cargar, tab_historial = tabs[3:]
    df_plan = cargar_plan()
    df_rm = cargar_rm()
    df_series = cargar_series()
    df_jugadoras = cargar_jugadoras()

    if df_rm is None or df_series is None or df_jugadoras is None:
        st.error("No se pudo leer la base de datos de fuerza. Probá recargar en unos minutos.")
        st.stop()

    # Ejercicios sin RM propio se miden contra el RM de otro (ej. tirones -> cargada)
    REFERENCIAS = {
        r.ejercicio: r.ejercicio_referencia
        for r in df_catalogo.itertuples() if r.ejercicio_referencia
    }
    EJERCICIOS = df_catalogo["ejercicio"].tolist()

    # ── Pestaña 1: Cargar sesión ─────────────────────────────────────────────────
    with tab_cargar:
        section_title("Datos de la sesión", COLOR_FUERZA, ICONS["fuerza"])

        c_fecha, c_jug, c_ej = st.columns(3)
        fecha_sesion = c_fecha.date_input("Fecha", value=date.today(), key="fuerza_fecha")
        nombre_jug = c_jug.selectbox("Jugadora", df_jugadoras["nombre"].tolist(), key="fuerza_jug")
        ejercicio = c_ej.selectbox("Ejercicio", EJERCICIOS, key="fuerza_ej")

        jugadora_id = str(df_jugadoras.loc[df_jugadoras["nombre"] == nombre_jug, "jugadora_id"].iloc[0])
        player_id = normalizar_nombre(nombre_jug)

        # RM vigente a la fecha de la sesión (nunca uno posterior), con la referencia si aplica
        ejercicio_rm = REFERENCIAS.get(ejercicio, ejercicio)
        rm = rm_vigente(df_rm, player_id, ejercicio_rm, fecha_sesion)
        if pd.isna(rm):
            st.warning(f"{nombre_jug} no tiene RM registrado de **{ejercicio_rm}** hasta esta fecha: "
                       "se guardan las series, pero no se puede calcular el %RM.")
        else:
            sufijo = f" (referencia: {ejercicio_rm})" if ejercicio_rm != ejercicio else ""
            st.caption(f"RM vigente: **{rm:g} kg**{sufijo}. {MSG_RM_AUTORREPORTADO}")

        # Plan prescrito para este ejercicio (opcional)
        plan_fila = None
        if df_plan is not None and not df_plan.empty:
            plan_ej = df_plan[df_plan["ejercicio"] == ejercicio].reset_index(drop=True)
            if not plan_ej.empty:
                etiquetas = ["Sin plan"] + [f"{r.semana} · {r.match_day}" for r in plan_ej.itertuples()]
                elegido = st.selectbox("Plan a seguir", etiquetas, key="fuerza_plan_sel")
                if elegido != "Sin plan":
                    plan_fila = plan_ej.iloc[etiquetas.index(elegido) - 1]
                    objetivo = (f" → carga objetivo **{rm * plan_fila.pct_rm / 100:.1f} kg**"
                                if pd.notna(rm) and pd.notna(plan_fila.pct_rm) else "")
                    st.caption(f"Plan: {plan_fila.series:g} × {plan_fila.reps:g} @ {plan_fila.pct_rm:g}% RM{objetivo}")

        # Filas iniciales del editor: lo ya guardado > lo planificado > filas vacías
        ya_guardadas = df_series[
            (df_series["jugadora_id"].astype(str) == jugadora_id)
            & (df_series["fecha"].dt.date == fecha_sesion)
            & (df_series["ejercicio"] == ejercicio)
        ].sort_values("nro_serie")

        if not ya_guardadas.empty:
            inicial = ya_guardadas[["reps", "kg", "rir"]].reset_index(drop=True)
            st.info(f"Ya hay {len(ya_guardadas)} serie(s) guardadas para esta jugadora, fecha y ejercicio: "
                    "al guardar se **reemplazan** por las de la tabla.")
        elif plan_fila is not None and pd.notna(plan_fila.series):
            kg_obj = round(rm * plan_fila.pct_rm / 100 / 2.5) * 2.5 if pd.notna(rm) and pd.notna(plan_fila.pct_rm) else None
            inicial = pd.DataFrame({"reps": [plan_fila.reps] * int(plan_fila.series),
                                    "kg": [kg_obj] * int(plan_fila.series),
                                    "rir": [None] * int(plan_fila.series)})
        else:
            inicial = pd.DataFrame({"reps": [None] * FILAS_VACIAS_DEFAULT,
                                    "kg": [None] * FILAS_VACIAS_DEFAULT,
                                    "rir": [None] * FILAS_VACIAS_DEFAULT})

        section_title("Series realizadas", COLOR_FUERZA, ICONS["carga_fisica"])
        st.caption("Una fila por serie, en el orden en que se hicieron. Las filas incompletas se descartan. "
                   "El RIR (repeticiones en reserva) es opcional.")
        clave_editor = f"fuerza_editor_{jugadora_id}_{fecha_sesion}_{ejercicio}_{plan_fila is not None}_{len(ya_guardadas)}"
        editado = st.data_editor(
            inicial.astype({"reps": "float64", "kg": "float64", "rir": "float64"}),
            num_rows="dynamic", width="stretch", hide_index=True, key=clave_editor,
            column_config={
                "reps": st.column_config.NumberColumn("Reps", min_value=1, max_value=50, step=1),
                "kg":   st.column_config.NumberColumn("Kg", min_value=0, max_value=500, step=0.5),
                "rir":  st.column_config.NumberColumn("RIR", min_value=0, max_value=10, step=1),
            },
        )

        series_ok = armar_series(editado)
        if not series_ok.empty:
            vista = series_ok.copy()
            vista["%RM"] = (vista["kg"] / rm * 100).round(1) if pd.notna(rm) else None
            vista["Tonelaje"] = vista["kg"] * vista["reps"]
            st.dataframe(vista.rename(columns={"nro_serie": "Serie", "reps": "Reps", "kg": "Kg", "rir": "RIR"}),
                         hide_index=True, width="stretch")
            st.caption(f"Tonelaje total: **{vista['Tonelaje'].sum():,.0f} kg** · {len(vista)} serie(s)")

        cs_escritura = _cs_escritura()
        if cs_escritura is None:
            st.warning("Falta la credencial de escritura (`fuerza_connection_string` en los secrets): "
                       "podés ver el historial, pero todavía no guardar sesiones.")

        if st.button("Guardar sesión", type="primary",
                     disabled=series_ok.empty or cs_escritura is None, key="fuerza_guardar"):
            try:
                n = guardar_series(cs_escritura, jugadora_id, fecha_sesion, ejercicio, series_ok)
            except Exception as e:
                st.error(f"No se pudo guardar ({type(e).__name__}). No se perdió nada de lo cargado en la tabla: "
                         "probá de nuevo en unos segundos.")
            else:
                st.cache_data.clear()
                st.success(f"Guardadas {n} serie(s) de {ejercicio} — {nombre_jug}, {fecha_sesion:%d/%m/%Y}.")


    # ── Pestaña 2: Historial ─────────────────────────────────────────────────────
    with tab_historial:
        f1, f2, f3 = st.columns(3)
        periodo = f1.radio("Agrupar por", ["Semanal", "Mensual"], horizontal=True, key="fuerza_periodo")
        freq = "W" if periodo == "Semanal" else "M"
        jug_hist = f2.selectbox("Jugadora", ["Todo el equipo"] + df_jugadoras["nombre"].tolist(),
                                key="fuerza_hist_jug")
        with f3:
            ejercicios_hist = popover_multiselect("Ejercicios", EJERCICIOS, key="fuerza_hist_ej",
                                                  default=EJERCICIOS)

        series_f = df_series[df_series["ejercicio"].isin(ejercicios_hist)]
        if jug_hist != "Todo el equipo":
            series_f = series_f[series_f["player_id"] == normalizar_nombre(jug_hist)]

        section_title("Volumen e intensidad", COLOR_FUERZA, ICONS["carga_fisica"])
        if series_f.empty:
            st.info("Todavía no hay series cargadas para este filtro. Cuando se guarden sesiones en "
                    "\"Cargar sesión\", acá aparece el historial semanal y mensual.")
        else:
            enr = enriquecer_series(series_f, df_rm, REFERENCIAS)
            total = resumen_por_periodo(enr, freq)
            por_ej = resumen_por_periodo(enr, freq, por=["ejercicio"])

            pct_global = enr["pct_rm_real"].mean()
            kpi_row([
                (ICONS["fuerza"], "Tonelaje total", f"{enr['tonelaje'].sum():,.0f} kg", COLOR_FUERZA),
                (ICONS["carga_fisica"], "Series", f"{len(enr):,}", BAR_CATEGORICAL_PALETTE[0]),
                (ICONS["entrenamiento"], "Días de fuerza", f"{enr['fecha'].nunique()}", BAR_CATEGORICAL_PALETTE[1]),
                (ICONS["target"], "%RM medio", "—" if pd.isna(pct_global) else f"{pct_global:.0f}%",
                 BAR_CATEGORICAL_PALETTE[2]),
            ])

            fig = px.bar(por_ej, x="periodo", y="tonelaje", color="ejercicio",
                         color_discrete_sequence=BAR_CATEGORICAL_PALETTE,
                         labels={"periodo": "", "tonelaje": "Tonelaje (kg)", "ejercicio": "Ejercicio"})
            fig.update_layout(**plotly_grouped_bar_layout(360), barmode="stack")
            st.markdown(f"**Tonelaje {periodo.lower()} por ejercicio**")
            st.plotly_chart(fig, width="stretch")

            con_pct = total.dropna(subset=["pct_rm_medio"])
            if not con_pct.empty:
                fig2 = px.line(con_pct, x="periodo", y="pct_rm_medio", markers=True,
                               labels={"periodo": "", "pct_rm_medio": "%RM medio"})
                fig2.update_traces(line_color=COLOR_FUERZA)
                fig2.update_layout(**plotly_line_layout(300))
                st.markdown(f"**Intensidad {periodo.lower()} (%RM medio)**")
                st.plotly_chart(fig2, width="stretch")
                st.caption("El %RM de cada serie usa el RM vigente **a la fecha de esa sesión**: "
                           "un RM nuevo no reescribe la intensidad de las sesiones anteriores.")

            tabla = total.rename(columns={
                "periodo": "Período", "n_sesiones": "Días", "n_series": "Series",
                "reps": "Reps", "tonelaje": "Tonelaje (kg)", "pct_rm_medio": "%RM medio",
            })
            tabla["Período"] = tabla["Período"].dt.strftime("%d/%m/%Y")
            st.dataframe(tabla.round({"Tonelaje (kg)": 0, "%RM medio": 1}),
                         hide_index=True, width="stretch")

        # Evolución del RM — existe desde antes de cargar la primera serie
        section_title("Evolución del RM", COLOR_FUERZA, ICONS["target"])
        rm_f = df_rm[df_rm["ejercicio"].isin(ejercicios_hist)]
        if jug_hist != "Todo el equipo":
            rm_f = rm_f[rm_f["player_id"] == normalizar_nombre(jug_hist)]
            evol = rm_f.sort_values("fecha")
            titulo_rm = f"RM de {jug_hist}"
        else:
            evol = (rm_f.assign(mes=rm_f["fecha"].dt.to_period("M").dt.start_time)
                        .groupby(["mes", "ejercicio"], as_index=False)["rm_kg"].mean()
                        .rename(columns={"mes": "fecha"}))
            titulo_rm = "RM promedio del equipo por mes"

        if evol.empty:
            st.info("No hay RM registrados para este filtro.")
        else:
            fig3 = px.line(evol, x="fecha", y="rm_kg", color="ejercicio", markers=True,
                           color_discrete_sequence=BAR_CATEGORICAL_PALETTE,
                           labels={"fecha": "", "rm_kg": "RM (kg)", "ejercicio": "Ejercicio"})
            fig3.update_layout(**plotly_line_layout(360))
            st.markdown(f"**{titulo_rm}**")
            st.plotly_chart(fig3, width="stretch")
            st.caption(MSG_RM_AUTORREPORTADO)
