# src/ui/hub.py
"""
Hub: una página con pestañas donde cada pestaña corre el script de una página existente
de pages/ SIN modificarla, y solo cuando esa pestaña está abierta.

Por qué solo la abierta: st.tabs(on_change="rerun") deja saber cuál está abierta (`.open`).
Con el st.tabs común Streamlit ejecuta TODAS las pestañas en cada rerun, y páginas pesadas
(Carga Física, ~940 líneas) se volverían lentas. Cambiar de pestaña cuesta lo mismo que hoy
cambiar de página.

Cómo se evita que la página interna rompa dentro del hub:
  * st.set_page_config admite varias llamadas por corrida (Streamlit 1.56), no hace falta parche.
  * require_login() de la página interna no vuelve a dibujar el sidebar (duplicaría el botón
    "Cerrar sesión"): lo salta una marca POR SESIÓN (st.session_state), nunca una variable
    global, así que no puede afectar a otro usuario que esté navegando a la vez. Y la marca
    solo saltea el sidebar: sin sesión iniciada el login sigue frenando (ver auth.py).
"""
import runpy
from pathlib import Path
from typing import Sequence

import streamlit as st

from src.ui.navegacion import PaginaNav
from src.utils.auth import HUB_ACTIVO_KEY

RAIZ = Path(__file__).resolve().parent.parent.parent


def ejecutar_pagina(archivo: str) -> None:
    """
    Corre el script `archivo` (ruta relativa a la raíz del proyecto, o absoluta) en el lugar
    donde se la llama, como lo haría Streamlit. La marca del hub se apaga siempre, incluso si
    la página falla (el error se propaga y Streamlit lo muestra).
    """
    previa = bool(st.session_state.get(HUB_ACTIVO_KEY, False))   # el router ya pudo haberla prendido
    st.session_state[HUB_ACTIVO_KEY] = True
    try:
        runpy.run_path(str(RAIZ / archivo), run_name="__main__")
    finally:
        st.session_state[HUB_ACTIVO_KEY] = previa


def render_hub(clave: str, paginas: Sequence[PaginaNav]) -> None:
    """
    Dibuja una pestaña por página y ejecuta únicamente la que está abierta.
    `clave` identifica al hub (la pestaña elegida queda en st.session_state[f"hub_{clave}"]).

    Enlace directo: una URL con ?tab=<título> abre esa pestaña. El parámetro se CONSUME (se borra
    de la URL): si quedara, cada rerun volvería a la pestaña del enlace y no se podría cambiar.
    """
    titulos = [p.titulo for p in paginas]
    pedida = st.query_params.get("tab")
    if pedida is not None:
        if pedida in titulos:
            st.session_state[f"hub_{clave}"] = pedida
        del st.query_params["tab"]
    pestanas = st.tabs(titulos, key=f"hub_{clave}", on_change="rerun")
    for pestana, pagina in zip(pestanas, paginas):
        if pestana.open:
            with pestana:
                ejecutar_pagina(pagina.archivo)
