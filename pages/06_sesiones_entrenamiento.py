# pages/06_sesiones_entrenamiento.py
# Nombre "sesiones_entrenamiento" (no "entrenamiento") a propósito: Streamlit
# desempata páginas con el mismo número por orden alfabético, y así queda
# DESPUÉS de 06_partidos.py en el menú. El label visible ("Entrenamiento") lo
# pone el CSS de inject_dashboard_css().
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.append(str(Path(__file__).parent.parent))
from settings import (
    PROCESSED, WELLNESS_SHEET_ID, ROSTER_SHEET_GID, SESIONES_SHEET_GID, LOGO_PATH, PAGE_COLORS,
)
from src.utils.auth import require_login
from src.loaders.roster_loader import cargar_posiciones_desde_sheets
from src.loaders.sesiones_loader import cargar_sesiones_desde_sheets, orden_match_day
from src.metrics.entrenamiento import (
    METRICAS_ENTRENAMIENTO, MDS_ENTRENAMIENTO, SIN_MICROCICLO,
    filtrar_entrenamientos, totalizar_por_jugadora_dia, totalizar_por_tipo_jugadora_dia,
    asignar_microciclo, promediar_por, promediar_segmentos, pivot_por_md,
)
from src.ui.theme import inject_dashboard_css, ICONS, BAR_CATEGORICAL_PALETTE
from src.ui.charts import plotly_grouped_bar_layout
from src.ui.components import home_button, page_header, kpi_row, zebra_rows, resaltar_maximo_columna
from src.ui.state import init_persistent, save_persistent
from src.ui.filtros import popover_multiselect

st.set_page_config(page_title="Entrenamiento", page_icon=str(LOGO_PATH), layout="wide")

require_login()
inject_dashboard_css()
home_button()
page_header("Entrenamiento", "Cargas por día de entrenamiento — MD-5 / MD-4 / MD-2",
            icon=ICONS["entrenamiento"], color=PAGE_COLORS["entrenamiento"])
st.divider()

COLOR_ENTRENAMIENTO = PAGE_COLORS["entrenamiento"]
COLOR_AMISTOSO = BAR_CATEGORICAL_PALETTE[2]
COLORES_TIPO = {"Entrenamiento": COLOR_ENTRENAMIENTO, "Amistoso": COLOR_AMISTOSO}
# Segmentos de la barra apilada (Microciclo): el orden del dict es el orden de apilado
COLORES_SEGMENTO = {"Físico": BAR_CATEGORICAL_PALETTE[0],
                    "Técnico-Táctico": BAR_CATEGORICAL_PALETTE[1],
                    "Amistoso": COLOR_AMISTOSO}
# Promedios por jugadora: los conteos (sprints, ACC, DECC) quedan con 1
# decimal — redondearlos a entero escondería diferencias reales entre días.
REDONDEO = {"distancia_total": 0, "hsr": 0, "sprints": 1, "acc_2": 1, "decc_3": 1, "player_load": 1}


# ── Cargar datos ─────────────────────────────────────────────────────────────
@st.cache_data
def cargar_gps():
    return pd.read_parquet(PROCESSED / "gps_procesado.parquet")


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


try:
    df = cargar_gps()
except FileNotFoundError:
    df = pd.DataFrame()

if df.empty:
    st.info("Sin datos GPS todavía — cargá sesiones desde Carga Física.")
    st.stop()

df_sesiones = cargar_sesiones()
if df_sesiones is None:
    st.error("No se pudo leer la pestaña \"Sesiones\" del Sheet — sin ella no hay Match Day "
             "para clasificar los entrenamientos. Probá recargar en unos minutos.")
    st.stop()

df_pos = cargar_posiciones()
if df_pos is not None:
    df = df.merge(df_pos[["player_id", "posicion"]], on="player_id", how="left")
else:
    df["posicion"] = None

df = df.merge(df_sesiones[["fecha", "match_day"]], on="fecha", how="left")
df["match_day"] = df["match_day"].fillna("Sin clasificar")

df_entrenos = filtrar_entrenamientos(df)
df_total = asignar_microciclo(totalizar_por_jugadora_dia(df_entrenos), df_sesiones)
if df_total.empty:
    st.info("No hay sesiones de entrenamiento clasificadas por Match Day todavía.")
    st.stop()
# Mismo universo que df_total, pero una fila por tipo (Físico / TT / Amistoso): para las barras apiladas
df_tipo = asignar_microciclo(totalizar_por_tipo_jugadora_dia(df_entrenos), df_sesiones)


# ── Helpers de presentación ──────────────────────────────────────────────────
def selectbox_persistente(label: str, opciones: list, key: str, **kwargs):
    """st.selectbox que sobrevive el cambio de página (ver src/ui/state.py).
    Si el valor guardado ya no existe (ej. cambió el calendario), vuelve al
    primero en vez de romper."""
    init_persistent(key, opciones[0])
    if st.session_state[key] not in opciones:
        st.session_state[key] = st.session_state[f"__persist_{key}"] = opciones[0]
    return st.selectbox(label, opciones, key=key, on_change=lambda: save_persistent(key), **kwargs)


def etiqueta_md(match_day: str, es_amistoso: bool) -> str:
    return f"{match_day} · Amistoso" if es_amistoso else match_day


def textos_segmentos(tipos, valores, decimales: int) -> list[str]:
    """Número dentro de cada segmento; el amistoso no lleva (su valor ya es el total de arriba)."""
    return ["" if (t == "Amistoso" or pd.isna(v)) else f"{v:.{decimales}f}"
            for t, v in zip(tipos, valores)]


def apilar_segmentos(fig):
    """Barras apiladas (Físico abajo, TT arriba) con el número centrado en cada segmento."""
    fig.update_layout(barmode="stack")
    fig.update_traces(selector=dict(type="bar"), textposition="inside",
                      insidetextanchor="middle", textfont=dict(color="#ffffff"))
    return fig


def tabla_estilizada(tabla: pd.DataFrame, decimales: dict[str, int]):
    """zebra + máximo resaltado por columna; `decimales` = {columna: n decimales}."""
    tabla = tabla.reset_index(drop=True).round(decimales)
    cols = list(decimales)
    return (tabla.style
            .apply(zebra_rows, axis=1)
            .apply(resaltar_maximo_columna, subset=cols)
            .format({c: f"{{:.{d}f}}" for c, d in decimales.items()}, na_rep="—"))


def tabla_metricas(df_resumen: pd.DataFrame, cols_identidad: dict) -> None:
    """Tabla identidad + las 6 métricas (promedio por jugadora) + n jugadoras."""
    tabla = df_resumen[list(cols_identidad) + list(METRICAS_ENTRENAMIENTO) + ["n_jugadoras"]]
    tabla = tabla.rename(columns=cols_identidad | METRICAS_ENTRENAMIENTO
                         | {"n_jugadoras": "Jugadoras"})
    decimales = {label: REDONDEO[col] for col, label in METRICAS_ENTRENAMIENTO.items()}
    st.dataframe(tabla_estilizada(tabla, decimales),
                 hide_index=True, use_container_width=True)


def bar_layout(fig, titulo_y: str, height: int = 360):
    fig.update_layout(**plotly_grouped_bar_layout(height))
    fig.update_layout(yaxis_title=titulo_y, xaxis_title=None, legend_title_text=None)
    return fig


def en_grilla(metricas: list[str], render_fn) -> None:
    """Un gráfico por métrica ("small multiples"), de a 2 por fila — cada
    métrica con su propia escala: en un mismo eje, ~5000 m de distancia
    aplastarían contra el cero a ~1 sprint. Con una sola métrica usa todo
    el ancho."""
    n_cols = 1 if len(metricas) == 1 else 2
    for i in range(0, len(metricas), n_cols):
        for col, metrica in zip(st.columns(n_cols), metricas[i:i + n_cols]):
            with col:
                render_fn(metrica)


# ── Filtros ──────────────────────────────────────────────────────────────────
microciclos = (df_total[["microciclo_fecha", "microciclo"]].drop_duplicates()
               .sort_values("microciclo_fecha", ascending=False, na_position="last"))
opciones_micro = microciclos["microciclo"].tolist()

col_micro, col_metrica = st.columns(2)
with col_micro:
    micro_sel = selectbox_persistente("Microciclo", opciones_micro, key="entrenamiento_microciclo",
                                      help="Días de entrenamiento previos a cada MD del calendario.")
with col_metrica:
    seleccion = popover_multiselect("Métricas de los gráficos", list(METRICAS_ENTRENAMIENTO),
                                    key="entrenamiento_metricas",
                                    default=["distancia_total", "hsr"],
                                    format_func=METRICAS_ENTRENAMIENTO.get)
# Orden fijo (el de METRICAS_ENTRENAMIENTO), no el orden en que se clickearon.
metricas = [m for m in METRICAS_ENTRENAMIENTO if m in seleccion]
if not metricas:
    st.info("Elegí al menos una métrica en el selector de arriba.")
    st.stop()

df_micro = df_total[df_total["microciclo"] == micro_sel]
df_micro_tipo = df_tipo[df_tipo["microciclo"] == micro_sel]
# MD -> hubo amistoso ese día (para marcar columnas/barras de este microciclo)
amistoso_por_md = df_micro.groupby("match_day")["amistoso"].any().to_dict()

st.caption("Valores = promedio por jugadora de la carga total del día (Físico + Técnico-Táctico "
           "sumados; en amistosos, la suma de los cuartos jugados). Los amistosos se muestran "
           "como referencia, marcados aparte.")

tab_micro, tab_pos, tab_jug, tab_md = st.tabs(
    ["Microciclo", "Por posición", "Por jugadora", "Por MD"])

# ── Microciclo ───────────────────────────────────────────────────────────────
with tab_micro:
    resumen = promediar_por(df_micro, ["match_day"])
    resumen = resumen.sort_values("match_day", key=lambda s: s.map(orden_match_day))
    resumen["Día"] = [etiqueta_md(md, a) for md, a in zip(resumen["match_day"], resumen["amistoso"])]
    resumen["tipo"] = resumen["amistoso"].map({True: "Amistoso", False: "Entrenamiento"})

    # Promedio por jugadora de cada segmento (Físico / TT / Amistoso) por día
    resumen_tipo = promediar_segmentos(df_micro_tipo, df_micro, ["match_day"])
    resumen_tipo = resumen_tipo.sort_values("match_day", key=lambda s: s.map(orden_match_day))
    resumen_tipo["Día"] = [etiqueta_md(md, amistoso_por_md.get(md, False))
                           for md in resumen_tipo["match_day"]]

    semanal =df_micro.groupby("nombre")[["distancia_total", "hsr", "player_load"]].sum().mean()
    kpi_row([
        (ICONS["entrenamiento"], "Días registrados", f"{len(resumen)}", COLOR_ENTRENAMIENTO),
        (ICONS["target"], "Jugadoras con GPS", f"{df_micro['nombre'].nunique()}",
         BAR_CATEGORICAL_PALETTE[0]),
        (ICONS["carga_fisica"], "Distancia semanal / jugadora",
         f"{semanal['distancia_total']:,.0f} m".replace(",", "."), BAR_CATEGORICAL_PALETTE[1]),
        (ICONS["velocidad"], "HSR semanal / jugadora",
         f"{semanal['hsr']:,.0f} m".replace(",", "."), BAR_CATEGORICAL_PALETTE[3]),
        (ICONS["rayo"], "Player Load semanal / jugadora", f"{semanal['player_load']:.0f}",
         COLOR_AMISTOSO),
    ])

    def grafico_microciclo(metrica: str) -> None:
        # Barras apiladas: Físico abajo, Técnico-Táctico arriba. category_orders
        # explícito en "Día" y "tipo_sesion": sin eso el eje toma las categorías
        # en orden de aparición por traza — un amistoso de MD-4 quedaba al final.
        fig = px.bar(resumen_tipo, x="Día", y=metrica, color="tipo_sesion",
                     color_discrete_map=COLORES_SEGMENTO, hover_data={"n_jugadoras": True},
                     text=textos_segmentos(resumen_tipo["tipo_sesion"], resumen_tipo[metrica],
                                           REDONDEO[metrica]),
                     category_orders={"Día": resumen["Día"].tolist(),
                                      "tipo_sesion": list(COLORES_SEGMENTO)})
        apilar_segmentos(fig)
        # Total de cada día encima de la barra (= suma de los segmentos, mismo universo de jugadoras)
        fig.add_scatter(x=resumen["Día"], y=resumen[metrica], mode="text",
                        text=resumen[metrica].round(REDONDEO[metrica]), textposition="top center",
                        showlegend=False, hoverinfo="skip", cliponaxis=False)
        st.plotly_chart(bar_layout(fig, METRICAS_ENTRENAMIENTO[metrica]),
                        use_container_width=True, key=f"micro_{metrica}")

    en_grilla(metricas, grafico_microciclo)

    tabla_metricas(resumen, {"Día": "Día"})

# ── Por posición ─────────────────────────────────────────────────────────────
with tab_pos:
    resumen_pos = promediar_por(df_micro, ["posicion", "match_day"])
    resumen_pos = resumen_pos.sort_values(["match_day", "posicion"],
                                          key=lambda s: s.map(orden_match_day) if s.name == "match_day" else s)
    resumen_pos["Día"] = [etiqueta_md(md, amistoso_por_md.get(md, False))
                          for md in resumen_pos["match_day"]]

    # Una barra apilada por posición y por día: Físico/TT del promedio de esa posición
    resumen_pos_tipo = promediar_segmentos(df_micro_tipo, df_micro, ["posicion", "match_day"])
    resumen_pos_tipo["Día"] = [etiqueta_md(md, amistoso_por_md.get(md, False))
                               for md in resumen_pos_tipo["match_day"]]
    dias_pos = resumen_pos["Día"].drop_duplicates().tolist()
    grilla_pos = pd.MultiIndex.from_product([dias_pos, sorted(resumen_pos["posicion"].unique())],
                                            names=["Día", "posicion"])

    def grafico_posicion(metrica: str) -> None:
        # Grilla fija día × posición: si una posición no tiene un segmento, la barra queda
        # vacía en su lugar en vez de correrse. Multi-categoría: día arriba, posición abajo.
        ejes = [grilla_pos.get_level_values("Día").tolist(),
                grilla_pos.get_level_values("posicion").tolist()]
        fig = go.Figure()
        for tipo, color in COLORES_SEGMENTO.items():
            valores = (resumen_pos_tipo[resumen_pos_tipo["tipo_sesion"] == tipo]
                       .set_index(["Día", "posicion"])[metrica].reindex(grilla_pos))
            fig.add_bar(x=ejes, y=valores.tolist(), name=tipo, marker_color=color,
                        text=textos_segmentos(
                            [tipo] * len(valores), valores.tolist(), REDONDEO[metrica]))
        totales = resumen_pos.set_index(["Día", "posicion"])[metrica].reindex(grilla_pos)
        fig.add_scatter(x=ejes, y=totales.tolist(), mode="text",
                        text=[f"{v:.{REDONDEO[metrica]}f}" if pd.notna(v) else "" for v in totales],
                        textposition="top center", showlegend=False, hoverinfo="skip",
                        cliponaxis=False)
        apilar_segmentos(fig)
        st.plotly_chart(bar_layout(fig, METRICAS_ENTRENAMIENTO[metrica]),
                        use_container_width=True, key=f"pos_{metrica}")

    def tabla_posicion(metrica: str) -> None:
        pivot = pivot_por_md(resumen_pos, "posicion", metrica)
        pivot.columns = [etiqueta_md(md, amistoso_por_md.get(md, False)) for md in pivot.columns]
        pivot = pivot.reset_index().rename(columns={"posicion": "Posición"})
        st.markdown(f"**{METRICAS_ENTRENAMIENTO[metrica]}** — promedio por jugadora de cada posición")
        st.dataframe(tabla_estilizada(pivot, {c: REDONDEO[metrica] for c in pivot.columns[1:]}),
                     hide_index=True, use_container_width=True, key=f"tabla_pos_{metrica}")

    en_grilla(metricas, grafico_posicion)
    en_grilla(metricas, tabla_posicion)

# ── Por jugadora ─────────────────────────────────────────────────────────────
with tab_jug:
    posiciones = df_micro.drop_duplicates("nombre").set_index("nombre")["posicion"]
    st.caption("\"—\" = sin GPS ese día.")
    # Una tabla por métrica, una debajo de la otra (no en grilla): con nombre +
    # posición + 3-4 días + total, a media pantalla no entran sin scroll lateral.
    for metrica in metricas:
        pivot = pivot_por_md(df_micro, "nombre", metrica)
        cols_md = list(pivot.columns)
        pivot["Total semana"] = pivot[cols_md].sum(axis=1, min_count=1)
        pivot.columns = ([etiqueta_md(md, amistoso_por_md.get(md, False)) for md in cols_md]
                         + ["Total semana"])
        pivot.insert(0, "Posición", posiciones.reindex(pivot.index))
        pivot = (pivot.reset_index().rename(columns={"nombre": "Jugadora"})
                 .sort_values(["Posición", "Jugadora"]))

        st.markdown(f"**{METRICAS_ENTRENAMIENTO[metrica]}** por jugadora")
        st.dataframe(tabla_estilizada(pivot, {c: REDONDEO[metrica] for c in pivot.columns[2:]}),
                     hide_index=True, use_container_width=True,
                     height=min(38 + 35 * len(pivot), 700), key=f"tabla_jug_{metrica}")

# ── Por MD ───────────────────────────────────────────────────────────────────
with tab_md:
    st.caption("Evolución de un mismo día del microciclo a lo largo de las semanas — "
               "no usa el filtro de microciclo de arriba.")
    mds_disponibles = sorted(df_total["match_day"].unique(), key=orden_match_day)
    md_sel = st.segmented_control("Match Day", mds_disponibles, default=MDS_ENTRENAMIENTO[1]
                                  if MDS_ENTRENAMIENTO[1] in mds_disponibles else mds_disponibles[0],
                                  key="entrenamiento_md_sel") or mds_disponibles[0]

    evolucion = promediar_por(df_total[df_total["match_day"] == md_sel],
                              ["microciclo_fecha", "microciclo"])
    evolucion = evolucion.sort_values("microciclo_fecha", na_position="last")
    evolucion["tipo"] = evolucion["amistoso"].map({True: "Amistoso", False: "Entrenamiento"})
    # Mismo MD por microciclo, pero partido en Físico / TT (para las barras apiladas)
    evolucion_tipo = promediar_segmentos(df_tipo[df_tipo["match_day"] == md_sel],
                                         df_total[df_total["match_day"] == md_sel],
                                         ["microciclo_fecha", "microciclo"])
    evolucion_tipo = evolucion_tipo.sort_values("microciclo_fecha", na_position="last")

    def grafico_evolucion(metrica: str) -> None:
        fig = px.bar(evolucion_tipo, x="microciclo", y=metrica, color="tipo_sesion",
                     color_discrete_map=COLORES_SEGMENTO, hover_data={"n_jugadoras": True},
                     text=textos_segmentos(evolucion_tipo["tipo_sesion"], evolucion_tipo[metrica],
                                           REDONDEO[metrica]),
                     category_orders={"microciclo": evolucion["microciclo"].tolist(),
                                      "tipo_sesion": list(COLORES_SEGMENTO)})
        apilar_segmentos(fig)
        fig.add_scatter(x=evolucion["microciclo"], y=evolucion[metrica], mode="text",
                        text=evolucion[metrica].round(REDONDEO[metrica]),
                        textposition="top center", showlegend=False, hoverinfo="skip",
                        cliponaxis=False)
        # Referencia: promedio de las semanas de ENTRENAMIENTO de ese MD (sin
        # amistosos, que tienen otra demanda y correrían la referencia).
        solo_entrenos = evolucion.loc[~evolucion["amistoso"], metrica]
        if not solo_entrenos.empty:
            fig.add_hline(y=solo_entrenos.mean(), line_dash="dash", line_color="#94a3b8",
                          annotation_text=f"Promedio {md_sel} (entrenamientos)",
                          annotation_font_color="#94a3b8")
        st.plotly_chart(bar_layout(fig, METRICAS_ENTRENAMIENTO[metrica], height=380),
                        use_container_width=True, key=f"md_{metrica}")

    en_grilla(metricas, grafico_evolucion)

    evolucion["Microciclo"] = [f"{m} · Amistoso" if a else m
                               for m, a in zip(evolucion["microciclo"], evolucion["amistoso"])]
    tabla_metricas(evolucion.iloc[::-1], {"Microciclo": "Microciclo"})

if micro_sel == SIN_MICROCICLO:
    st.warning("Hay entrenamientos sin un MD posterior en la pestaña \"Sesiones\" — cargá el "
               "próximo partido en el Sheet para que se agrupen en su microciclo.")
