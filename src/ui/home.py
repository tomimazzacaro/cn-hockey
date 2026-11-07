# src/ui/home.py
"""
Pantalla de inicio: las tarjetas de cada sección. La usan los dos modos de la app:
  * menú plano (bandera apagada): las tarjetas llevan a cada archivo de pages/;
  * menú agrupado (bandera prendida): llevan a la pestaña correspondiente de cada hub.
La Home es compacta: secciones lado a lado y tarjetas horizontales (ver theme.py).
Quien la llama decide el destino de cada tarjeta con `destino(pagina) -> (página, query_params)`.
"""
from typing import Callable

import streamlit as st

from settings import PAGE_COLORS, PROJECT_NAME
from src.ui.components import nav_card, page_header, section_title
from src.ui.navegacion import PAGINA_PRESENTACION, SECCIONES, PaginaNav
from src.ui.theme import ICONS

COLOR_SECCION = "#93c5fd"

Destino = Callable[[PaginaNav], tuple[object, dict | None]]


def render_home(destino: Destino) -> None:
    # Todo dentro de un contenedor con ancho máximo y centrado (ver theme.py): en una pantalla grande el
    # bloque se estiraba a casi todo el ancho y las tarjetas quedaban enormes y lejos del título.
    with st.container(key="cn-home"):
        page_header("Centro Naval Hockey", "Primera División Femenina")
        st.divider()

        # Las secciones van LADO A LADO, una columna por sección, con sus tarjetas apiladas: así toda la
        # Home entra en una pantalla sin scrollear (la sección más alta tiene 3 tarjetas).
        for columna, seccion in zip(st.columns(len(SECCIONES)), SECCIONES):
            with columna:
                section_title(seccion.titulo, COLOR_SECCION)
                for pagina in seccion.paginas:
                    pagina_destino, query = destino(pagina)
                    nav_card(f"cn-navcard-{pagina.clave}", pagina_destino, ICONS[pagina.icono],
                             pagina.titulo, pagina.subtitulo, PAGE_COLORS[pagina.color_clave],
                             query_params=query)

        # Enlace discreto a la Presentación, centrado bajo todo el bloque.
        with st.container(key="cn-home-presentacion"):
            pagina_destino, query = destino(PAGINA_PRESENTACION)
            st.page_link(pagina_destino, label=f"{PAGINA_PRESENTACION.titulo} — {PAGINA_PRESENTACION.subtitulo}",
                         icon=":material/slideshow:", query_params=query)
