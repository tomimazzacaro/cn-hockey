# src/ui/state.py
"""
Estado persistente entre páginas — Streamlit borra el session_state de un
widget apenas ese widget deja de renderizarse en un run, o sea que cambiar
de página pierde todos los filtros de la página anterior aunque tengan
key= (ver "Working with widgets in multipage apps" en la doc de Streamlit).
Para que un filtro sobreviva la navegación hay que guardar su valor en OTRO
key de session_state que no esté atado a ningún widget, y restaurarlo antes
de crear el widget en cada run.
"""
import streamlit as st


def init_persistent(key: str, default) -> None:
    """
    Llamar ANTES de crear el widget con key=key. Restaura el valor guardado
    la última vez que se tocó ese filtro (en esta página o en otra), o usa
    `default` la primera vez que se ve ese key en la sesión.
    """
    storage_key = f"__persist_{key}"
    if storage_key not in st.session_state:
        st.session_state[storage_key] = default
    st.session_state[key] = st.session_state[storage_key]


def save_persistent(key: str) -> None:
    """
    Callback on_change del widget: copia su valor actual al key de
    almacenamiento aparte, que Streamlit no borra al cambiar de página.
    """
    st.session_state[f"__persist_{key}"] = st.session_state[key]
