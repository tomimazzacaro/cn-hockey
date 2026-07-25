# src/ui/asistente.py
"""
UI compartida del Asistente de Parámetros — arma el filtro popover+multiselect
persistente y renderiza la tabla de cumplimiento, reutilizado por las 4
páginas de fitting (Carga Física, Físico vs TT, Perfil de Jugadora, Partidos).
Cada página sigue siendo dueña de sus propias claves de session_state,
opciones de filtro y etiquetas — acá solo vive lo que era copy-paste byte a
byte entre ellas.
"""
import streamlit as st

from src.loaders.parametros_loader import cargar_parametros_desde_sheets
from src.metrics.parametros import armar_evaluacion_equipo, evaluar_por_jugadora, pivotear_evaluacion
from src.metrics.analisis import generar_analisis, tabla_analisis_pdf
from src.ui.components import tabla_asistente_html, analisis_asistente_html


@st.cache_data(ttl=3600)
def cargar_parametros_cacheado(sheet_id: str, gid: str):
    try:
        return cargar_parametros_desde_sheets(sheet_id, gid)
    except Exception:
        return None


def render_asistente(df_filtrado, df_parametros, *, claves_grupo: list[str], etiqueta_fn,
                       etiqueta_header: str, caption: str, match_day: str | None = None) -> dict:
    """
    Corre armar_evaluacion_equipo() y pinta la tabla + el caption — el tramo
    final, idéntico en las 4 páginas, de cada sección de Asistente.

    Debajo de la tabla de equipo, también arma el análisis por jugadora
    (evaluar_por_jugadora() + generar_analisis()) — reutiliza el mismo
    df_filtrado y claves_grupo ya recibidos como claves_dia, sin pedirle
    nada nuevo a las páginas que llaman a esta función.

    Devuelve {"tabla_pdf": DataFrame, "analisis_pdf": DataFrame} — versión
    texto-plano (sin emoji/color) de la tabla y el análisis, para que cada
    página los agregue a su informe PDF como SeccionTabla. Antes esta
    función no devolvía nada y el PDF quedaba sin el Asistente ni el
    Análisis — el caller SIEMPRE debe capturar y usar este resultado si
    quiere que el informe los incluya.
    """
    df_evaluacion = armar_evaluacion_equipo(
        df_filtrado, df_parametros, claves_grupo=claves_grupo,
        etiqueta_fn=etiqueta_fn, match_day=match_day,
    )
    tabla_asistente_html(df_evaluacion, etiqueta_header=etiqueta_header)
    st.caption(caption)

    df_individual = evaluar_por_jugadora(
        df_filtrado, df_parametros, claves_dia=claves_grupo, match_day=match_day,
    )
    analisis = generar_analisis(df_individual)
    analisis_asistente_html(analisis)

    return {
        "tabla_pdf": pivotear_evaluacion(df_evaluacion, etiqueta_header=etiqueta_header),
        "analisis_pdf": tabla_analisis_pdf(analisis),
    }
