# src/ui/filtros.py
"""
Widget de filtro compartido — encabezado + popover + multiselect con
persistencia entre páginas. Mismo patrón que se repetía en cada filtro de
Posición/Jugadora/Sesión/Partido/Métricas de todas las páginas, tanto en los
filtros principales como en el Asistente de Parámetros.
"""
import streamlit as st

from src.ui.state import init_persistent, save_persistent


def popover_multiselect(label: str, opciones: list, key: str, default: list | None = None,
                          format_func=None, use_container_width: bool = True) -> list:
    """Encabezado + popover + multiselect con persistencia entre páginas."""
    st.markdown(
        f'<p style="font-size:0.875rem; color:inherit; margin-bottom:0.25rem">{label}</p>',
        unsafe_allow_html=True,
    )
    with st.popover(label, use_container_width=use_container_width, key=f"{key}_pop"):
        init_persistent(key, opciones if default is None else default)
        kwargs = {"format_func": format_func} if format_func else {}
        seleccion = st.multiselect(
            label, opciones, label_visibility="collapsed", key=key,
            on_change=lambda: save_persistent(key), **kwargs,
        )
    return seleccion
