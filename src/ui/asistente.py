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
from src.metrics.parametros import armar_evaluacion_equipo
from src.ui.components import tabla_asistente_html


@st.cache_data(ttl=3600)
def cargar_parametros_cacheado(sheet_id: str, gid: str):
    try:
        return cargar_parametros_desde_sheets(sheet_id, gid)
    except Exception:
        return None


def render_asistente(df_filtrado, df_parametros, *, claves_grupo: list[str], etiqueta_fn,
                       etiqueta_header: str, caption: str, match_day: str | None = None) -> None:
    """Corre armar_evaluacion_equipo() y pinta la tabla + el caption — el
    tramo final, idéntico en las 4 páginas, de cada sección de Asistente."""
    df_evaluacion = armar_evaluacion_equipo(
        df_filtrado, df_parametros, claves_grupo=claves_grupo,
        etiqueta_fn=etiqueta_fn, match_day=match_day,
    )
    tabla_asistente_html(df_evaluacion, etiqueta_header=etiqueta_header)
    st.caption(caption)
