# app.py
from pathlib import Path
import sys
import streamlit as st

sys.path.append(str(Path(__file__).parent))
from settings import PROJECT_NAME, LOGO_PATH, PAGE_COLORS
from src.utils.auth import require_login
from src.ui.theme import inject_dashboard_css, ICONS
from src.ui.components import nav_card, page_header, section_title
from src.ui.navegacion import PAGINA_PRESENTACION, SECCIONES

st.set_page_config(
    page_title=PROJECT_NAME,
    page_icon=str(LOGO_PATH),
    layout="wide",
    initial_sidebar_state="expanded",
)

require_login()
inject_dashboard_css()

# ── Home ───────────────────────────────────────────────────────────────────
page_header("Centro Naval Hockey", "Primera División Femenina")
st.divider()

# Una fila por sección, siempre con 4 columnas: las tarjetas miden lo mismo en todas las filas
# aunque la sección tenga 1, 2 o 3 páginas. Lo que se muestra sale de src/ui/navegacion.py.
COLUMNAS = 4
COLOR_SECCION = "#93c5fd"

for seccion in SECCIONES:
    section_title(seccion.titulo, COLOR_SECCION)
    columnas = st.columns(COLUMNAS)
    for columna, pagina in zip(columnas, seccion.paginas):
        with columna:
            nav_card(f"cn-navcard-{pagina.clave}", pagina.archivo, ICONS[pagina.icono],
                     pagina.titulo, pagina.subtitulo, PAGE_COLORS[pagina.color_clave])

st.divider()
st.page_link(PAGINA_PRESENTACION.archivo, label=f"{PAGINA_PRESENTACION.titulo} — {PAGINA_PRESENTACION.subtitulo}",
             icon=":material/slideshow:")
