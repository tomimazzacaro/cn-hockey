# app.py
from pathlib import Path
import sys
import streamlit as st

sys.path.append(str(Path(__file__).parent))
from settings import PROJECT_NAME, LOGO_PATH, PAGE_COLORS
from src.utils.auth import require_login
from src.ui.theme import inject_dashboard_css, ICONS
from src.ui.components import nav_card, page_header

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

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    nav_card("cn-navcard-carga-fisica", "pages/02_carga_fisica.py",
             ICONS["carga_fisica"], "Carga Física", "GPS · ACWR · Intensidad relativa",
             PAGE_COLORS["carga_fisica"])
with col2:
    nav_card("cn-navcard-wellness", "pages/03_wellness.py",
             ICONS["wellness"], "Wellness", "Readiness · Alertas · Molestias",
             PAGE_COLORS["wellness"])
with col3:
    nav_card("cn-navcard-fisico-tt", "pages/04_fisico_vs_tt.py",
             ICONS["balance"], "Físico vs Técnico-Táctico", "Comparativa de demandas",
             PAGE_COLORS["fisico_tt"])
with col4:
    nav_card("cn-navcard-perfil", "pages/05_perfil_jugadora.py",
             ICONS["target"], "Perfil de Jugadora", "Evolución individual en el tiempo",
             PAGE_COLORS["perfil"])
with col5:
    nav_card("cn-navcard-partidos", "pages/06_partidos.py",
             ICONS["trofeo"], "Partidos", "Radar comparativo entre partidos",
             PAGE_COLORS["partidos"])

st.divider()
st.caption("CN Hockey Performance")