# src/ui/router.py
"""
Arranque de la app con el MENÚ AGRUPADO (settings.USAR_MENU_AGRUPADO = True).

app.py pasa a ser un router (st.navigation con el menú nativo oculto) y el menú lateral lo
dibujamos nosotros: Inicio + una entrada por sección (src/ui/navegacion.py). Cada sección con
varias páginas es un hub de pestañas (src/ui/hub.py); la de una sola página (Perfil) abre
directo. Las páginas originales de pages/ NO se tocan: siguen registradas (ocultas) para que
los enlaces viejos y los st.page_link("pages/...") sigan funcionando.
"""
import streamlit as st

from settings import LOGO_PATH, PROJECT_NAME
from src.ui.home import render_home
from src.ui.hub import render_hub
from src.ui.navegacion import (
    PAGINA_HOME_KEY, PAGINA_PRESENTACION, SECCIONES, PaginaNav, entradas_menu,
)
from src.ui.theme import inject_dashboard_css
from src.utils.auth import (
    HUB_ACTIVO_KEY, render_boton_logout, render_encabezado_sidebar, require_login,
)


def _crear_paginas() -> tuple[list, dict, dict]:
    """
    Returns:
        (todas, por_url, destinos): `todas` va a st.navigation; `por_url` {url_path: página} para
        el menú lateral; `destinos` {clave de PaginaNav: (página, query_params)} para las tarjetas.
    """
    por_url: dict = {}
    destinos: dict = {}
    ocultas: list = []

    def inicio() -> None:
        render_home(lambda p: destinos[p.clave])

    home = st.Page(inicio, title="Inicio", url_path="", default=True)
    por_url[""] = home

    for seccion in SECCIONES:
        if len(seccion.paginas) == 1:
            pagina = seccion.paginas[0]
            pg = st.Page(pagina.archivo, title=pagina.titulo, url_path=seccion.url_path)
            destinos[pagina.clave] = (pg, None)
        else:
            def hub(seccion=seccion) -> None:
                render_hub(seccion.url_path, seccion.paginas)
            hub.__name__ = f"hub_{seccion.url_path}"
            pg = st.Page(hub, title=seccion.titulo, url_path=seccion.url_path)
            for pagina in seccion.paginas:
                destinos[pagina.clave] = (pg, {"tab": pagina.titulo})
                # Ruta de siempre (/carga_fisica...) y destino de st.page_link("pages/..."): oculta.
                ocultas.append(st.Page(pagina.archivo, title=pagina.titulo, url_path=pagina.url_path,
                                       visibility="hidden"))
        por_url[seccion.url_path] = pg

    presentacion = st.Page(PAGINA_PRESENTACION.archivo, title=PAGINA_PRESENTACION.titulo,
                           url_path=PAGINA_PRESENTACION.url_path, visibility="hidden")
    destinos[PAGINA_PRESENTACION.clave] = (presentacion, None)

    todas = [home] + [por_url[s.url_path] for s in SECCIONES] + ocultas + [presentacion]
    return todas, por_url, destinos


def _dibujar_sidebar(por_url: dict) -> None:
    with st.sidebar:
        render_encabezado_sidebar()
        for entrada in entradas_menu():
            st.page_link(por_url[entrada.url_path], label=entrada.etiqueta, icon=entrada.icono)
        st.divider()
        render_boton_logout()


def ejecutar_router() -> None:
    st.set_page_config(
        page_title=PROJECT_NAME,
        page_icon=str(LOGO_PATH),
        layout="wide",
        initial_sidebar_state="expanded",
    )
    require_login(con_sidebar=False)          # sin sesión: muestra el login y corta acá
    inject_dashboard_css()
    # El router dibuja el sidebar: las páginas (que llaman a require_login) no deben repetirlo.
    st.session_state[HUB_ACTIVO_KEY] = True

    todas, por_url, _ = _crear_paginas()
    st.session_state[PAGINA_HOME_KEY] = por_url[""]      # home_button() vuelve acá
    pagina = st.navigation(todas, position="hidden")
    _dibujar_sidebar(por_url)
    pagina.run()
