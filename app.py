# app.py
from pathlib import Path
import sys
import streamlit as st

sys.path.append(str(Path(__file__).parent))
from settings import PROJECT_NAME, LOGO_PATH, USAR_MENU_AGRUPADO

if USAR_MENU_AGRUPADO:
    # Menú agrupado por secciones: app.py es el router (ver src/ui/router.py).
    from src.ui.router import ejecutar_router
    ejecutar_router()
else:
    # Menú de siempre: lista plana de páginas (pages/) y esta pantalla como inicio.
    from src.utils.auth import require_login
    from src.ui.theme import inject_dashboard_css
    from src.ui.home import render_home

    st.set_page_config(
        page_title=PROJECT_NAME,
        page_icon=str(LOGO_PATH),
        layout="wide",
        initial_sidebar_state="expanded",
    )

    require_login()
    inject_dashboard_css()
    render_home(lambda pagina: (pagina.archivo, None))
