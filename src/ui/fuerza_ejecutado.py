# src/ui/fuerza_ejecutado.py
"""
Pestañas "Sesión ejecutada" e "Historial" de la página de Fuerza (a nivel equipo).

Sesión ejecutada: se elige fecha y Match Day; la tabla arranca precargada con el plan
de esa semana y se corrige lo que realmente se hizo. Historial: carga real por semana
contra lo planificado, ACWR de fuerza y detalle de cada sesión.

Los cálculos viven en src/metrics/fuerza_ejecutado.py; el acceso a la base, en
src/loaders/fuerza_plan_loader.py. Acá solo hay pantalla.
"""
from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from src.loaders.fuerza_plan_loader import (
    listar_sesiones, cargar_items_sesiones, cargar_todos_items_plan, guardar_sesion,
)
from src.metrics.fuerza_ejecutado import (
    COLUMNAS_ITEM_EJECUTADO, acwr_fuerza, cumplimiento_vs_plan, ejecutado_a_plan,
    plan_a_ejecutado, resumen_semanal, resumen_sesiones, resumir_items_ejecutados,
    serie_diaria_ua,
)
from src.metrics.fuerza_plan import (
    COLUMNAS_ITEM_PLAN, armar_items_plan, editores_a_items, items_a_editores, resumir_plan_semana,
)
from src.ui.charts import plotly_grouped_bar_layout, plotly_line_layout
from src.ui.components import kpi_row, section_title
from src.ui.fuerza_planificador import (
    MDS_PLAN, editores_fuerza_pasadas, leer_items_plan, leer_parametros, leer_planes, sincronizar_match_day,
    leer_zonas, lunes_de, nota_alta_intensidad, preparar_catalogos, texto_limpio,
)
from src.ui.theme import BAR_CATEGORICAL_PALETTE, ICONS

COLORES_ZONA_ACWR = {
    "Subcarga": BAR_CATEGORICAL_PALETTE[0],
    "Óptimo": BAR_CATEGORICAL_PALETTE[1],
    "Precaución": BAR_CATEGORICAL_PALETTE[2],
    "Riesgo Alto": BAR_CATEGORICAL_PALETTE[5],
    "Sin datos": "#8a94a6",
}


def _miles(valor: float, sufijo: str = "") -> str:
    """1234.5 -> '1.235' (separador de miles con punto, como en el resto del dashboard)."""
    return f"{valor:,.0f}".replace(",", ".") + sufijo


def _porc(valor) -> str:
    return "—" if pd.isna(valor) else f"{valor:.0f} %"


@st.cache_data(ttl=60)
def leer_sesiones(cs: str) -> pd.DataFrame:
    return listar_sesiones(cs)


@st.cache_data(ttl=60)
def leer_items_sesion(cs: str, sesion_id: str) -> pd.DataFrame:
    return cargar_items_sesiones(cs, sesion_id)


@st.cache_data(ttl=60)
def leer_items_sesiones(cs: str) -> pd.DataFrame:
    return cargar_items_sesiones(cs)


@st.cache_data(ttl=60)
def leer_todos_items_plan(cs: str) -> pd.DataFrame:
    return cargar_todos_items_plan(cs)


# ── Sesión ejecutada ─────────────────────────────────────────────────────────

def render_ejecutado(cs_lectura: str, cs_escritura: str | None,
                     df_cat_fuerza: pd.DataFrame, df_cat_resist: pd.DataFrame, color: str) -> None:
    """Pestaña para registrar lo que el equipo hizo en una sesión (precargada desde el plan)."""
    cat = preparar_catalogos(df_cat_fuerza, df_cat_resist)
    if cat is None:
        st.error("El catálogo no trae la columna ID (FZA-### / RES-###). Revisá la planilla Ejercicios_fisico.")
        return
    try:
        planes = leer_planes(cs_lectura)
        parametros = leer_parametros(cs_lectura)
        zonas = leer_zonas(cs_lectura)
        sesiones = leer_sesiones(cs_lectura)
    except Exception:
        st.error("No se pudo leer la base de datos de fuerza. Probá recargar en unos minutos.")
        return

    section_title("Sesión a registrar", color, ICONS["fuerza"])
    c_fecha, c_md, c_info = st.columns([1, 1, 2])
    fecha = c_fecha.date_input("Fecha de la sesión", value=date.today(), format="DD/MM/YYYY", key="ej_fecha")
    sincronizar_match_day(fecha, "ej_md")   # lunes -> MD-5, martes -> MD-4, jueves -> MD-2
    md = c_md.selectbox("Match Day", MDS_PLAN, key="ej_md")
    ver = st.session_state.get("ej_ver", 0)

    # ── ¿Qué hay para esa fecha y MD? sesión ya guardada > plan de la semana > nada ──
    plan = planes[planes["semana_inicio"] == lunes_de(fecha)]
    plan_id = str(plan.iloc[0]["id"]) if not plan.empty else None
    items_plan = leer_items_plan(cs_lectura, plan_id) if plan_id else pd.DataFrame(columns=COLUMNAS_ITEM_PLAN)
    items_plan_md = items_plan[items_plan["match_day"] == md]

    guardada = sesiones[(sesiones["fecha"].dt.date == fecha) & (sesiones["match_day"] == md)]
    if not guardada.empty:
        origen = "guardada"
        fila = guardada.iloc[0]
        base = ejecutado_a_plan(leer_items_sesion(cs_lectura, str(fila["id"])).assign(match_day=md))
        c_info.info("Ya hay una sesión cargada para esta fecha y MD: al guardar se corrige.")
    elif not items_plan_md.empty:
        origen = "plan"
        fila = None
        base = items_plan_md
        c_info.success("Precargado desde el plan de la semana. Corregí lo que no se hizo igual.")
        if plan.iloc[0]["estado"] == "borrador":
            c_info.warning("Ese plan sigue en **borrador**.")
    else:
        origen = "vacia"
        fila = None
        base = pd.DataFrame(columns=COLUMNAS_ITEM_PLAN)
        c_info.info("No hay un plan cargado para ese MD en esa semana: se puede registrar igual, a mano.")

    kpis_box = st.container()

    # ── Tablas editables (mismas que el planificador) ───────────────────────
    section_title("Lo que se hizo", color, ICONS["entrenamiento"])
    df_fz, df_rs = items_a_editores(base, md, cat["etiquetas"])
    ed_fz, ed_rs = editores_fuerza_pasadas(df_fz, df_rs, cat["opciones_fz"], cat["opciones_rs"], zonas,
                                           key_base=f"ej_{fecha}_{md}_{origen}_{ver}", con_superserie=False)
    items_plan_fmt, avisos = armar_items_plan(editores_a_items(md, ed_fz, ed_rs, cat["ids_por_etiqueta"]))
    items_ej = plan_a_ejecutado(items_plan_fmt)[COLUMNAS_ITEM_EJECUTADO]

    # ── Datos de la sesión ──────────────────────────────────────────────────
    section_title("Datos de la sesión", color)
    clave = f"{fecha}_{md}_{origen}_{ver}"
    d1, d2, d3 = st.columns(3)
    dur_ini = None if fila is None or pd.isna(fila["duracion_min"]) else int(fila["duracion_min"])
    rpe_ini = None if fila is None or pd.isna(fila["rpe_sesion"]) else float(fila["rpe_sesion"])
    duracion = d1.number_input("Duración (min)", min_value=1, max_value=300, step=5, value=dur_ini, key=f"ej_dur_{clave}")
    rpe = d2.number_input("RPE de la sesión (0–10)", min_value=0.0, max_value=10.0, step=0.5, value=rpe_ini,
                          key=f"ej_rpe_{clave}")
    ya_en_gps = d3.checkbox("Las pasadas ya están en el GPS (chaleco)",
                            value=bool(fila["ya_en_gps"]) if fila is not None else False,
                            key=f"ej_gps_{clave}",
                            help="Si las pasadas se hicieron con el chaleco, sus metros ya los cuenta el GPS: "
                                 "se registran acá pero no se suman dos veces.")
    notas = st.text_area("Notas (opcional)", value=texto_limpio(fila["notas"]) if fila is not None else "",
                         key=f"ej_notas_{clave}")

    # ── KPIs en vivo (se dibujan arriba) ────────────────────────────────────
    real = resumir_items_ejecutados(items_ej, parametros)
    plan_md = resumir_plan_semana(items_plan_md, parametros) if not items_plan_md.empty else None
    cumpl_ua = (real["ua_fuerza"] / plan_md["ua_fuerza"] * 100) if plan_md and plan_md["ua_fuerza"] > 0 else float("nan")
    srpe = duracion * rpe if duracion is not None and rpe is not None else None
    with kpis_box:
        section_title("Carga real de la sesión", color, ICONS["fuerza"])
        kpi_row([
            (ICONS["fuerza"], "UA de fuerza", _miles(real["ua_fuerza"]), BAR_CATEGORICAL_PALETTE[0]),
            (ICONS["velocidad"], "Metros de pasadas", _miles(real["metros_pasadas"], " m"), BAR_CATEGORICAL_PALETTE[1]),
            (ICONS["rayo"], "Metros alta intensidad", _miles(real["metros_alta_intensidad"], " m"), BAR_CATEGORICAL_PALETTE[2]),
            (ICONS["check"], "Cumplimiento vs plan (UA)", _porc(cumpl_ua), BAR_CATEGORICAL_PALETTE[4]),
            (ICONS["reloj"], "sRPE (duración × RPE)", "—" if srpe is None else _miles(srpe), BAR_CATEGORICAL_PALETTE[6]),
        ])
        st.caption(nota_alta_intensidad(float(parametros["umbral_alta_intensidad_vmax"])))
        if real["pasadas_sin_pct_vmax"]:
            st.warning(f"{real['pasadas_sin_pct_vmax']} pasada(s) sin %Vmáx: cuentan en los metros totales "
                       "pero no como alta intensidad.")

    # ── Guardar ─────────────────────────────────────────────────────────────
    for aviso in avisos:
        st.warning(aviso)
    if cs_escritura is None:
        st.warning("Falta la credencial de escritura (`fuerza_connection_string` en los secrets): "
                   "se puede cargar la sesión, pero todavía no guardarla.")
    if st.button("Guardar sesión", type="primary", disabled=cs_escritura is None or items_ej.empty,
                 key=f"ej_guardar_{clave}"):
        try:
            guardar_sesion(cs_escritura, fecha, md, plan_id, duracion, rpe, ya_en_gps, notas, items_ej)
        except Exception as e:  # noqa: BLE001 — se muestra el motivo, no se traga
            st.error(f"No se pudo guardar la sesión: {e}")
        else:
            st.cache_data.clear()
            st.session_state["ej_ver"] = ver + 1
            st.success("Sesión guardada.")
            st.rerun()


# ── Historial ────────────────────────────────────────────────────────────────

def render_historial(cs_lectura: str, color: str) -> None:
    """Carga real por semana vs plan, ACWR de fuerza y detalle de cada sesión."""
    try:
        parametros = leer_parametros(cs_lectura)
        sesiones = leer_sesiones(cs_lectura)
        items_ej = leer_items_sesiones(cs_lectura)
        planes = leer_planes(cs_lectura)
        items_plan = leer_todos_items_plan(cs_lectura)
    except Exception:
        st.error("No se pudo leer la base de datos de fuerza. Probá recargar en unos minutos.")
        return

    if sesiones.empty:
        st.info("Todavía no hay sesiones ejecutadas. Cargá la primera en la pestaña **Sesión ejecutada**.")
        return

    resumen = cumplimiento_vs_plan(resumen_sesiones(sesiones, items_ej, parametros), items_plan, parametros)
    semanal = resumen_semanal(resumen, planes, items_plan, parametros)
    acwr = acwr_fuerza(serie_diaria_ua(resumen, hasta=date.today()))
    actual = acwr.iloc[-1]

    # ── KPIs ────────────────────────────────────────────────────────────────
    ultimas_4s = resumen[resumen["fecha"] >= pd.Timestamp(date.today()) - pd.Timedelta(days=27)]
    cump_medio = semanal["cumplimiento_ua"].mean()
    section_title("Resumen", color, ICONS["fuerza"])
    kpi_row([
        (ICONS["check"], "Sesiones registradas", str(len(resumen)), BAR_CATEGORICAL_PALETTE[0]),
        (ICONS["fuerza"], "UA de fuerza (últimas 4 semanas)", _miles(ultimas_4s["ua_fuerza"].sum()), BAR_CATEGORICAL_PALETTE[1]),
        (ICONS["alerta"], "ACWR de fuerza hoy" + ("" if actual["historia_suficiente"] else " (provisorio)"),
         "—" if pd.isna(actual["acwr"]) else f"{actual['acwr']:.2f}", COLORES_ZONA_ACWR[actual["zona_acwr"]]),
        (ICONS["trofeo"], "Cumplimiento medio vs plan", _porc(cump_medio), BAR_CATEGORICAL_PALETTE[4]),
        (ICONS["velocidad"], "Metros de pasadas fuera del GPS", _miles(resumen["metros_pasadas_fuera_gps"].sum(), " m"),
         BAR_CATEGORICAL_PALETTE[2]),
    ])
    if not actual["historia_suficiente"]:
        st.caption(f"El ACWR es **provisorio**: hay {int(actual['dias_historia'])} días de historia y hacen falta 28 "
                   "para que la carga crónica sea confiable. No lo leas como señal de riesgo todavía.")

    # ── Planificado vs ejecutado por semana ─────────────────────────────────
    g1, g2 = st.columns(2)
    sem = semanal.assign(semana_txt=semanal["semana"].dt.strftime("%d/%m"))
    with g1:
        section_title("UA de fuerza por semana", color)
        largo = sem.melt(id_vars="semana_txt", value_vars=["ua_planificada", "ua_ejecutada"],
                         var_name="serie", value_name="UA")
        largo["serie"] = largo["serie"].map({"ua_planificada": "Planificado", "ua_ejecutada": "Ejecutado"})
        fig = px.bar(largo, x="semana_txt", y="UA", color="serie", barmode="group", text="UA",
                     color_discrete_sequence=[BAR_CATEGORICAL_PALETTE[4], BAR_CATEGORICAL_PALETTE[0]],
                     labels={"semana_txt": "Semana (lunes)", "serie": ""})
        fig.update_layout(**plotly_grouped_bar_layout(320))
        fig.update_traces(textposition="outside", texttemplate="%{text:.0f}")
        st.plotly_chart(fig, width="stretch")
    with g2:
        section_title("Metros de pasadas por semana", color)
        largo = sem.melt(id_vars="semana_txt", value_vars=["metros_planificados", "metros_ejecutados", "metros_alta_intensidad"],
                         var_name="serie", value_name="m")
        largo["serie"] = largo["serie"].map({"metros_planificados": "Planificado", "metros_ejecutados": "Ejecutado",
                                             "metros_alta_intensidad": "Alta intensidad"})
        fig = px.bar(largo, x="semana_txt", y="m", color="serie", barmode="group", text="m",
                     color_discrete_sequence=[BAR_CATEGORICAL_PALETTE[4], BAR_CATEGORICAL_PALETTE[1], BAR_CATEGORICAL_PALETTE[2]],
                     labels={"semana_txt": "Semana (lunes)", "serie": ""})
        fig.update_layout(**plotly_grouped_bar_layout(320))
        fig.update_traces(textposition="outside", texttemplate="%{text:.0f}")
        st.plotly_chart(fig, width="stretch")

    # ── ACWR de fuerza ──────────────────────────────────────────────────────
    section_title("ACWR de fuerza (equipo)", color, ICONS["alerta"])
    acwr_plot = acwr.dropna(subset=["acwr"]).assign(
        tramo=lambda d: d["historia_suficiente"].map({True: "Confiable (≥ 28 días)", False: "Provisorio (< 28 días)"}))
    if acwr_plot.empty:
        st.info("Todavía no hay carga suficiente para calcular el ACWR (las sesiones cargadas suman 0 UA).")
    else:
        fig = px.line(acwr_plot, x="fecha", y="acwr", color="tramo",
                      color_discrete_map={"Confiable (≥ 28 días)": BAR_CATEGORICAL_PALETTE[0],
                                          "Provisorio (< 28 días)": "#8a94a6"},
                      labels={"fecha": "", "acwr": "ACWR", "tramo": ""})
        fig.add_hrect(y0=0.8, y1=1.3, fillcolor=BAR_CATEGORICAL_PALETTE[1], opacity=0.12, line_width=0)
        fig.add_hline(y=1.5, line_dash="dot", line_color=BAR_CATEGORICAL_PALETTE[5], opacity=0.7)
        fig.update_layout(**plotly_line_layout(340))
        st.plotly_chart(fig, width="stretch")
    st.caption("Banda verde: zona óptima (0,8–1,3). Línea punteada: 1,5 (riesgo alto). "
               "Se completa con 0 los días sin sesión de fuerza.")

    # ── Detalle de sesiones ─────────────────────────────────────────────────
    section_title("Detalle de sesiones", color, ICONS["entrenamiento"])
    tabla = resumen.sort_values("fecha", ascending=False).assign(
        fecha_txt=lambda d: d["fecha"].dt.strftime("%d/%m/%Y"),
        gps=lambda d: d["ya_en_gps"].map({True: "Sí", False: "No"}))
    st.dataframe(
        tabla[["fecha_txt", "match_day", "ua_fuerza", "ua_planificada", "cumplimiento_ua", "metros_pasadas",
               "metros_alta_intensidad", "duracion_min", "rpe_sesion", "srpe", "gps"]],
        hide_index=True, width="stretch",
        column_config={
            "fecha_txt": "Fecha", "match_day": "MD",
            "ua_fuerza": st.column_config.NumberColumn("UA", format="%.1f"),
            "ua_planificada": st.column_config.NumberColumn("UA plan", format="%.1f"),
            "cumplimiento_ua": st.column_config.NumberColumn("Cumpl. %", format="%.0f"),
            "metros_pasadas": st.column_config.NumberColumn("Metros", format="%.0f"),
            "metros_alta_intensidad": st.column_config.NumberColumn("Metros alta int.", format="%.0f"),
            "duracion_min": st.column_config.NumberColumn("Min", format="%.0f"),
            "rpe_sesion": st.column_config.NumberColumn("RPE", format="%.1f"),
            "srpe": st.column_config.NumberColumn("sRPE", format="%.0f"),
            "gps": "Pasadas en GPS",
        })
