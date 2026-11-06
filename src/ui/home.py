# src/ui/home.py
"""
Pantalla de inicio: las tarjetas de cada sección. La usan los dos modos de la app:
  * menú plano (bandera apagada): las tarjetas llevan a cada archivo de pages/;
  * menú agrupado (bandera prendida): llevan a la pestaña correspondiente de cada hub.
Quien la llama decide el destino de cada tarjeta con `destino(pagina) -> (página, query_params)`.
"""
from typing import Callable

import streamlit as st

from settings import PAGE_COLORS, PROJECT_NAME
from src.ui.components import nav_card, page_header, section_title
from src.ui.navegacion import PAGINA_PRESENTACION, SECCIONES, PaginaNav
from src.ui.theme import ICONS

COLUMNAS = 4   # una fila por sección, siempre 4 columnas: las tarjetas miden lo mismo en todas
COLOR_SECCION = "#93c5fd"

Destino = Callable[[PaginaNav], tuple[object, dict | None]]


def render_home(destino: Destino) -> None:
    page_header("Centro Naval Hockey", "Primera División Femenina")
    st.divider()

    for seccion in SECCIONES:
        section_title(seccion.titulo, COLOR_SECCION)
        columnas = st.columns(COLUMNAS)
        for columna, pagina in zip(columnas, seccion.paginas):
            pagina_destino, query = destino(pagina)
            with columna:
                nav_card(f"cn-navcard-{pagina.clave}", pagina_destino, ICONS[pagina.icono],
                         pagina.titulo, pagina.subtitulo, PAGE_COLORS[pagina.color_clave],
                         query_params=query)

    st.divider()
    pagina_destino, query = destino(PAGINA_PRESENTACION)
    st.page_link(pagina_destino, label=f"{PAGINA_PRESENTACION.titulo} — {PAGINA_PRESENTACION.subtitulo}",
                 icon=":material/slideshow:", query_params=query)
