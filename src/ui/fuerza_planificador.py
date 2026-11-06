# src/ui/fuerza_planificador.py
"""
Pestaña "Planificación" de la página de Fuerza: arma el plan de la semana,
separado por Match Day (MD-5 / MD-4 / MD-2), con fuerza y pasadas.

Flujo: elegir semana -> editar una tabla de fuerza y una de pasadas por MD ->
ver la carga prevista (UA y metros) -> guardar en Supabase.

Los cálculos viven en src/metrics/fuerza_plan.py y el acceso a la base en
src/loaders/fuerza_plan_loader.py; acá solo hay pantalla.
"""
from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

from src.loaders.fuerza_plan_loader import (
    listar_planes, cargar_items_plan, cargar_parametros, cargar_zonas_velocidad,
    guardar_plan, guardar_parametros,
)
from src.metrics.fuerza_plan import (
    COLS_EDITOR_FUERZA, COLS_EDITOR_PASADAS, COLUMNAS_ITEM_PLAN, SUPERSERIES, TIPO_FUERZA, TIPO_PASADA,
    armar_items_plan, editores_a_items, etiqueta_ejercicio, items_a_editores, match_day_para_fecha,
    resumir_plan_por_md, resumir_plan_semana,
)
from src.metrics.fuerza_vmax import (
    calcular_vmax_jugadoras, distancia_fuera_de_rango, factores_desde_parametros,
    tiempos_objetivo_jugadoras,
)
from src.ui.charts import plotly_grouped_bar_layout
from src.ui.components import kpi_row, section_title
from src.ui.theme import BAR_CATEGORICAL_PALETTE, ICONS

MDS_PLAN = ["MD-5", "MD-4", "MD-2"]
ESTADOS = ["borrador", "publicado"]


# ── Datos (cache corto: lo que se guarda tiene que verse enseguida) ──────────
@st.cache_data(ttl=60)
def leer_planes(cs: str) -> pd.DataFrame:
    return listar_planes(cs)


@st.cache_data(ttl=60)
def leer_items_plan(cs: str, plan_id: str) -> pd.DataFrame:
    return cargar_items_plan(cs, plan_id)


@st.cache_data(ttl=60)
def leer_parametros(cs: str) -> dict:
    return cargar_parametros(cs)


@st.cache_data(ttl=60)
def leer_zonas(cs: str) -> pd.DataFrame:
    return cargar_zonas_velocidad(cs)


def lunes_de(fecha: date) -> date:
    """Lunes de la semana de `fecha` (weekday(): lunes = 0)."""
    return fecha - timedelta(days=fecha.weekday())


def sincronizar_match_day(fecha: date, clave: str) -> None:
    """
    Deja en st.session_state[clave] el Match Day del día elegido (lunes -> MD-5, martes -> MD-4,
    jueves -> MD-2). Hay que llamarla ANTES de crear el widget (pestañas o selector) de esa clave.

    Solo pisa el valor cuando cambia el día o cuando la clave no existe (p. ej. al volver a la
    página, porque Streamlit borra el estado de un widget que no se dibuja). Si la persona elige
    otro Match Day a mano, su elección se respeta mientras no cambie el día. Un día sin fuerza
    (miércoles, viernes...) no toca la elección vigente.
    """
    marca = f"{clave}__dia"
    if st.session_state.get(marca) == fecha and clave in st.session_state:
        return
    md_del_dia = match_day_para_fecha(fecha)
    if md_del_dia is not None:
        st.session_state[clave] = md_del_dia
    elif clave not in st.session_state:
        st.session_state[clave] = MDS_PLAN[0]
    st.session_state[marca] = fecha


def _con_extras(opciones: list[str], actuales: pd.Series) -> list[str]:
    """
    Opciones del selector en el orden del catálogo, más los ejercicios que el plan
    ya usa pero que salieron del catálogo (así la tabla no los muestra en blanco).
    """
    extras = [e for e in dict.fromkeys(actuales) if e and e not in opciones]
    return opciones + extras


def texto_limpio(valor) -> str:
    """None / NaN -> '' (los textos vacíos de la base pueden venir como NaN)."""
    return "" if valor is None or pd.isna(valor) else str(valor)


def _tipar(df: pd.DataFrame, numericas: list[str], textos: list[str]) -> pd.DataFrame:
    """Tipos limpios para st.data_editor: números como número, textos como texto."""
    df = df.copy()
    for col in numericas:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in textos:
        df[col] = df[col].where(df[col].notna(), "").astype(str)
    return df


def preparar_catalogos(df_cat_fuerza: pd.DataFrame, df_cat_resist: pd.DataFrame) -> dict | None:
    """
    Arma los textos de los selectores a partir de los catálogos de la planilla.

    Returns:
        None si el catálogo no trae IDs; si no, un dict con:
        etiquetas {id: texto}, ids_por_etiqueta {texto: (id, nombre)},
        opciones_fz / opciones_rs (textos en el orden del catálogo) y sin_rm
        (ejercicios de fuerza que no admiten RM).
    """
    cat_fz = df_cat_fuerza[df_cat_fuerza["ejercicio_id"] != ""]
    cat_rs = df_cat_resist[df_cat_resist["ejercicio_id"] != ""]
    if cat_fz.empty or cat_rs.empty:
        return None

    etiquetas: dict[str, str] = {}
    ids_por_etiqueta: dict[str, tuple[str, str]] = {}
    for tipo, cat in ((TIPO_FUERZA, cat_fz), (TIPO_PASADA, cat_rs)):
        for r in cat.itertuples():
            et = etiqueta_ejercicio(r.ejercicio, r.ejercicio_id, tipo)
            etiquetas[r.ejercicio_id] = et
            ids_por_etiqueta[et] = (r.ejercicio_id, r.ejercicio)
    return {
        "etiquetas": etiquetas,
        "ids_por_etiqueta": ids_por_etiqueta,
        "opciones_fz": [etiquetas[i] for i in cat_fz["ejercicio_id"]],
        "opciones_rs": [etiquetas[i] for i in cat_rs["ejercicio_id"]],
        "sin_rm": cat_fz.loc[~cat_fz["admite_rm"], "ejercicio"].tolist(),
    }


def editores_fuerza_pasadas(df_fz: pd.DataFrame, df_rs: pd.DataFrame, opciones_fz: list[str],
                            opciones_rs: list[str], zonas: pd.DataFrame,
                            key_base: str, con_superserie: bool = True) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Dibuja las dos tablas editables (fuerza y pasadas) y devuelve lo que quedó cargado.
    Las usan el planificador (lo prescrito) y la sesión ejecutada (lo realmente hecho):
    tienen las mismas columnas, salvo "Superserie": solo el plan la guarda
    (con_superserie=False la oculta en lo ejecutado, donde no se persiste).
    """
    df_fz = _tipar(df_fz, ["Series", "Reps", "%RM", "Pausa (s)"], ["Ejercicio", "Notas"])
    if con_superserie:
        # vacío = ejercicio suelto; el selector no admite "" (NaN -> None)
        df_fz["Superserie"] = df_fz["Superserie"].astype(object).where(df_fz["Superserie"].notna() & (df_fz["Superserie"] != ""), None)
    else:
        df_fz = df_fz.drop(columns="Superserie")
    df_rs = _tipar(df_rs, ["Pasadas", "Distancia (m)", "%Vmáx", "Pausa (s)"], ["Pasada", "Zona", "Notas"])

    st.markdown("**Fuerza**")
    ed_fz = st.data_editor(
        df_fz, num_rows="dynamic", hide_index=True, width="stretch", key=f"{key_base}_fz",
        column_config={
            "Ejercicio": st.column_config.SelectboxColumn("Ejercicio", options=_con_extras(opciones_fz, df_fz["Ejercicio"]), required=True),
            "Superserie": (st.column_config.SelectboxColumn(
                "Superserie", options=SUPERSERIES, required=False, width="small",
                help="Los ejercicios con la misma letra (en el mismo día) forman una superserie. "
                     "Vacío = ejercicio suelto. La pausa se carga en UN solo ejercicio del grupo "
                     "(el más fuerte) y vale para todo el grupo.") if con_superserie else None),
            "Series": st.column_config.NumberColumn("Series", min_value=1, max_value=20, step=1),
            "Reps": st.column_config.NumberColumn("Reps", min_value=1, max_value=100, step=1),
            "%RM": st.column_config.NumberColumn("%RM", min_value=1, max_value=150, step=1, format="%d"),
            "Pausa (s)": st.column_config.NumberColumn("Pausa (s)", min_value=0, max_value=600, step=5),
            "Notas": st.column_config.TextColumn("Notas"),
        })

    st.markdown("**Pasadas**")
    col_zona = (st.column_config.SelectboxColumn("Zona", options=zonas["nombre"].tolist())
                if not zonas.empty else st.column_config.TextColumn("Zona"))
    ed_rs = st.data_editor(
        df_rs, num_rows="dynamic", hide_index=True, width="stretch", key=f"{key_base}_rs",
        column_config={
            "Pasada": st.column_config.SelectboxColumn("Pasada", options=_con_extras(opciones_rs, df_rs["Pasada"]), required=True),
            "Pasadas": st.column_config.NumberColumn("Pasadas", min_value=1, max_value=50, step=1,
                                                     help="Cantidad de pasadas"),
            "Distancia (m)": st.column_config.NumberColumn("Distancia (m)", min_value=5, max_value=400, step=5),
            "%Vmáx": st.column_config.NumberColumn("%Vmáx", min_value=1, max_value=120, step=1, format="%d",
                                                   help="% de la velocidad máxima de cada jugadora"),
            "Zona": col_zona,
            "Pausa (s)": st.column_config.NumberColumn("Pausa (s)", min_value=0, max_value=600, step=5),
            "Notas": st.column_config.TextColumn("Notas"),
        })
    return ed_fz, ed_rs


def render_tiempos_objetivo(df_pasadas: pd.DataFrame, df_vmax: pd.DataFrame | None,
                            factores: dict[int, float]) -> None:
    """Tiempo objetivo de cada pasada de un MD, por jugadora (opción A, ver fuerza_vmax.py)."""
    with st.expander("Tiempos objetivo por jugadora"):
        if df_vmax is None or df_vmax.empty:
            st.info("No hay datos de GPS para calcular la Vmáx de cada jugadora.")
            return
        con_pct = df_pasadas.dropna(subset=["distancia_m", "pct_vmax"]) if not df_pasadas.empty else df_pasadas
        if con_pct.empty:
            st.info("Cargá al menos una pasada con distancia y %Vmáx para ver los tiempos objetivo.")
            return
        tabla = tiempos_objetivo_jugadoras(df_vmax, con_pct, factores)
        cols_tiempo = [c for c in tabla.columns if c not in ("Jugadora", "Vmáx (km/h)")]
        st.dataframe(tabla, hide_index=True, width="stretch", column_config={
            "Vmáx (km/h)": st.column_config.NumberColumn(format="%.1f"),
            **{c: st.column_config.NumberColumn(c + " (s)", format="%.2f") for c in cols_tiempo}})
        st.caption("tiempo = distancia ÷ (Vmáx ÷ 3,6 × %Vmáx × factor de la distancia). Los factores son "
                   "**provisorios** (estimados, no medidos): calibralos con tiempos reales en Parámetros de cálculo.")
        if any(distancia_fuera_de_rango(d, factores) for d in con_pct["distancia_m"]):
            st.warning(f"Hay distancias fuera del rango calibrado ({min(factores)}–{max(factores)} m): "
                       "se usa el factor del extremo y el tiempo es menos confiable.")
        if tabla["Vmáx (km/h)"].isna().any():
            st.caption("Las jugadoras sin Vmáx (sin datos válidos de GPS) quedan en blanco.")


def render_planificador(cs_lectura: str, cs_escritura: str | None,
                        df_cat_fuerza: pd.DataFrame, df_cat_resist: pd.DataFrame,
                        color: str, df_gps: pd.DataFrame | None = None) -> None:
    """Dibuja la pestaña completa. Todo lo que cambia datos pasa por el botón Guardar."""
    # ── Catálogos -> textos del selector ────────────────────────────────────
    cat = preparar_catalogos(df_cat_fuerza, df_cat_resist)
    if cat is None:
        st.error("El catálogo no trae la columna ID (FZA-### / RES-###). Revisá la planilla "
                 "Ejercicios_fisico: cada ejercicio necesita su ID para poder planificarlo.")
        return
    etiquetas, ids_por_etiqueta = cat["etiquetas"], cat["ids_por_etiqueta"]
    opciones_fz, opciones_rs, sin_rm = cat["opciones_fz"], cat["opciones_rs"], cat["sin_rm"]

    # ── Datos de la base ────────────────────────────────────────────────────
    try:
        planes = leer_planes(cs_lectura)
        parametros = leer_parametros(cs_lectura)
        zonas = leer_zonas(cs_lectura)
    except Exception:
        st.error("No se pudo leer el plan desde la base. Probá recargar en unos minutos.")
        return

    # Vmáx por jugadora y factores por distancia (opción A de pasadas)
    factores = factores_desde_parametros(parametros)
    df_vmax = None
    if df_gps is not None:
        df_vmax = calcular_vmax_jugadoras(df_gps, int(parametros["vmax_top_n"]),
                                          int(parametros["vmax_ventana_dias"]), float(parametros["vmax_tope_kmh"]))

    # ── Semana ──────────────────────────────────────────────────────────────
    section_title("Semana a planificar", color, ICONS["fuerza"])
    c_fecha, c_estado, c_nombre = st.columns([1, 1, 2])
    fecha = c_fecha.date_input("Día de la semana", value=date.today(), key="plan_fecha",
                               format="DD/MM/YYYY",
                               help="Se toma el lunes de la semana que contiene ese día.")
    lunes = lunes_de(fecha)
    existente = planes[planes["semana_inicio"] == lunes]
    plan_id = str(existente.iloc[0]["id"]) if not existente.empty else None
    items_guardados = leer_items_plan(cs_lectura, plan_id) if plan_id else pd.DataFrame(columns=COLUMNAS_ITEM_PLAN)

    estado_guardado = existente.iloc[0]["estado"] if plan_id else "borrador"
    nombre_guardado = texto_limpio(existente.iloc[0]["nombre"]) if plan_id else ""
    notas_guardadas = texto_limpio(existente.iloc[0]["notas"]) if plan_id else ""
    estado = c_estado.selectbox("Estado", ESTADOS, index=ESTADOS.index(estado_guardado),
                                key=f"plan_estado_{lunes}")
    nombre = c_nombre.text_input("Nombre (opcional)", value=nombre_guardado,
                                 placeholder="Ej: Semana vs. H.C. Andersen", key=f"plan_nombre_{lunes}")
    st.caption(f"Semana del lunes **{lunes:%d/%m/%Y}** · "
               + ("plan guardado, se está editando." if plan_id else "todavía no hay plan guardado para esta semana."))

    # `ver` cambia al guardar: fuerza a los editores a recargarse desde la base.
    ver = st.session_state.get("plan_ver", 0)

    kpis_box = st.container()

    # ── Una pestaña por Match Day ───────────────────────────────────────────
    section_title("Plan por Match Day", color, ICONS["entrenamiento"])
    if sin_rm:
        st.caption(f"Sin RM (se usa la intensidad base de {parametros['intensidad_base_sin_rm']:.0f} %): "
                   + ", ".join(sin_rm) + ". Dejá el %RM vacío en esos ejercicios.")
    # La pestaña sigue al día elegido: lunes -> MD-5, martes -> MD-4, jueves -> MD-2.
    # OJO: st.tabs con on_change="ignore" (el valor por defecto) NO guarda estado y su `default`
    # solo cuenta la primera vez que el navegador dibuja las pestañas: hace falta `key` +
    # on_change="rerun" y escribir el valor en session_state ANTES de crearlas (ver abajo).
    sincronizar_match_day(fecha, "plan_tabs_md")
    tabs_md = st.tabs(MDS_PLAN, key="plan_tabs_md", on_change="rerun")
    partes = []
    for md, tab in zip(MDS_PLAN, tabs_md):
        with tab:
            df_fz, df_rs = items_a_editores(items_guardados, md, etiquetas)
            ed_fz, ed_rs = editores_fuerza_pasadas(df_fz, df_rs, opciones_fz, opciones_rs, zonas,
                                                   key_base=f"plan_{lunes}_{md}_{ver}")
            parte = editores_a_items(md, ed_fz, ed_rs, ids_por_etiqueta)
            items_md, _ = armar_items_plan(parte)
            render_tiempos_objetivo(items_md[items_md["tipo"] == TIPO_PASADA], df_vmax, factores)
            partes.append(parte)

    partes = [p for p in partes if not p.empty]   # concat de tablas vacías: aviso de pandas
    if partes:
        items_editados, avisos = armar_items_plan(pd.concat(partes, ignore_index=True))
    else:
        items_editados, avisos = pd.DataFrame(columns=COLUMNAS_ITEM_PLAN), []
    por_md = resumir_plan_por_md(items_editados, parametros)
    semana = resumir_plan_semana(items_editados, parametros)

    # ── KPIs de la semana (se dibujan arriba, en el contenedor reservado) ───
    with kpis_box:
        section_title("Carga prevista de la semana", color, ICONS["fuerza"])
        kpi_row([
            (ICONS["fuerza"], "UA de fuerza", f"{semana['ua_fuerza']:,.0f}".replace(",", "."), BAR_CATEGORICAL_PALETTE[0]),
            (ICONS["velocidad"], "Metros de pasadas", f"{semana['metros_pasadas']:,.0f} m".replace(",", "."), BAR_CATEGORICAL_PALETTE[1]),
            (ICONS["rayo"], "Metros alta intensidad", f"{semana['metros_alta_intensidad']:,.0f} m".replace(",", "."), BAR_CATEGORICAL_PALETTE[2]),
            (ICONS["check"], "Ejercicios de fuerza", f"{int((items_editados['tipo'] == TIPO_FUERZA).sum())}", BAR_CATEGORICAL_PALETTE[4]),
            (ICONS["entrenamiento"], "Pasadas prescritas", f"{int((items_editados['tipo'] == TIPO_PASADA).sum())}", BAR_CATEGORICAL_PALETTE[6]),
        ])
        if semana["pasadas_sin_pct_vmax"]:
            st.warning(f"{semana['pasadas_sin_pct_vmax']} pasada(s) sin %Vmáx: cuentan en los metros "
                       "totales pero no se pueden clasificar como alta intensidad.")

    # ── Gráficos por MD ─────────────────────────────────────────────────────
    if not por_md.empty:
        g1, g2 = st.columns(2)
        with g1:
            section_title("UA de fuerza por MD", color)
            fig = px.bar(por_md, x="match_day", y="ua_fuerza", text="ua_fuerza",
                         color_discrete_sequence=[BAR_CATEGORICAL_PALETTE[0]],
                         labels={"match_day": "", "ua_fuerza": "UA"})
            fig.update_layout(**plotly_grouped_bar_layout(320))
            fig.update_traces(textposition="outside")
            st.plotly_chart(fig, width="stretch")
            st.caption(f"UA = series × repeticiones × %RM ÷ 100, sumado por ejercicio. "
                       f"Ej.: 4 × 5 al 80 % = 16 UA. Sin %RM se usa {parametros['intensidad_base_sin_rm']:.0f} %.")
        with g2:
            section_title("Metros de pasadas por MD", color)
            largo = por_md.melt(id_vars="match_day", value_vars=["metros_pasadas", "metros_alta_intensidad"],
                                var_name="tipo", value_name="metros")
            largo["tipo"] = largo["tipo"].map({"metros_pasadas": "Totales", "metros_alta_intensidad": "Alta intensidad"})
            fig = px.bar(largo, x="match_day", y="metros", color="tipo", barmode="group", text="metros",
                         color_discrete_sequence=[BAR_CATEGORICAL_PALETTE[1], BAR_CATEGORICAL_PALETTE[2]],
                         labels={"match_day": "", "metros": "m", "tipo": ""})
            fig.update_layout(**plotly_grouped_bar_layout(320))
            fig.update_traces(textposition="outside")
            st.plotly_chart(fig, width="stretch")

    # ── Guardar ─────────────────────────────────────────────────────────────
    section_title("Guardar", color)
    notas = st.text_area("Notas del plan (opcional)", value=notas_guardadas, key=f"plan_notas_{lunes}")
    for aviso in avisos:
        st.warning(aviso)
    if cs_escritura is None:
        st.warning("Falta la credencial de escritura (`fuerza_connection_string` en los secrets): "
                   "se puede armar el plan, pero todavía no guardarlo.")
    if st.button("Guardar plan", type="primary", disabled=cs_escritura is None or items_editados.empty,
                 key=f"plan_guardar_{lunes}"):
        try:
            guardar_plan(cs_escritura, lunes, nombre, estado, notas, items_editados)
        except Exception as e:  # noqa: BLE001 — se muestra el motivo, no se traga
            st.error(f"No se pudo guardar el plan: {e}")
        else:
            st.cache_data.clear()
            st.session_state["plan_ver"] = ver + 1
            st.success(f"Plan guardado: {len(items_editados)} ítems.")
            st.rerun()

    # ── Parámetros editables ────────────────────────────────────────────────
    with st.expander("Parámetros de cálculo (editables)"):
        st.caption("Valores provisorios: se ajustan cuando el cuerpo técnico los defina. "
                   "Cambian cómo se calculan los KPIs y los tiempos, no lo ya guardado.")
        p1, p2 = st.columns(2)
        umbral = p1.number_input("Alta intensidad desde (% de Vmáx)", min_value=50.0, max_value=120.0,
                                 value=float(parametros["umbral_alta_intensidad_vmax"]), step=1.0, key="par_umbral")
        base = p2.number_input("Intensidad base sin RM (% de RM)", min_value=10.0, max_value=100.0,
                               value=float(parametros["intensidad_base_sin_rm"]), step=1.0, key="par_base")

        st.markdown("**Pasadas: factor de corrección por distancia**")
        st.caption("Corrige que al salir de parada la jugadora todavía acelera y no llega a su Vmáx "
                   "(menor factor = tiempo objetivo más lento). Los valores iniciales son estimados de un "
                   "modelo, no medidos: calibralos con tiempos reales.")
        cols_f = st.columns(len(factores))
        nuevos_factores = {
            d: col.number_input(f"{d} m", min_value=0.50, max_value=1.00, step=0.01, format="%.2f",
                                value=float(factores[d]), key=f"par_factor_{d}")
            for d, col in zip(sorted(factores), cols_f)
        }

        st.markdown("**Vmáx de cada jugadora (desde el GPS)**")
        v1, v2, v3 = st.columns(3)
        top_n = v1.number_input("Promedio de sus mejores N días", min_value=1, max_value=10, step=1,
                                value=int(parametros["vmax_top_n"]), key="par_vmax_top")
        ventana = v2.number_input("Ventana (días hacia atrás)", min_value=30, max_value=730, step=30,
                                  value=int(parametros["vmax_ventana_dias"]), key="par_vmax_ventana")
        tope = v3.number_input("Descartar velocidades mayores a (km/h)", min_value=25.0, max_value=45.0, step=0.5,
                               value=float(parametros["vmax_tope_kmh"]), key="par_vmax_tope",
                               help="Por encima de este valor se considera un error del chaleco.")

        if st.button("Guardar parámetros", disabled=cs_escritura is None, key="par_guardar"):
            valores = {"umbral_alta_intensidad_vmax": umbral, "intensidad_base_sin_rm": base,
                       "vmax_top_n": top_n, "vmax_ventana_dias": ventana, "vmax_tope_kmh": tope,
                       **{f"factor_pasada_{d}": f for d, f in nuevos_factores.items()}}
            try:
                guardar_parametros(cs_escritura, valores)
            except Exception as e:  # noqa: BLE001
                st.error(f"No se pudieron guardar los parámetros: {e}")
            else:
                st.cache_data.clear()
                st.success("Parámetros guardados.")
                st.rerun()
        if zonas.empty:
            st.info("Las zonas de velocidad todavía no están definidas: la zona de cada pasada se escribe a mano.")

    if df_vmax is not None and not df_vmax.empty:
        with st.expander("Vmáx por jugadora (desde el GPS)"):
            st.caption(f"Promedio de los {int(parametros['vmax_top_n'])} mejores días de los últimos "
                       f"{int(parametros['vmax_ventana_dias'])} días del GPS. "
                       "Revisá que los valores sean razonables: son la base de todos los tiempos objetivo.")
            st.dataframe(df_vmax.assign(ultima_fecha=df_vmax["ultima_fecha"].dt.strftime("%d/%m/%Y")),
                         hide_index=True, width="stretch", column_config={
                "player_id": None, "nombre": "Jugadora",
                "vmax_kmh": st.column_config.NumberColumn("Vmáx (km/h)", format="%.1f"),
                "n_dias": st.column_config.NumberColumn("Días usados", format="%d"),
                "ultima_fecha": "Último dato válido",
                "valores_descartados": st.column_config.NumberColumn(
                    "Descartados", format="%d", help="Velocidades por encima del tope (errores del chaleco)")})
