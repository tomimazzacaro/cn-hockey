# app.py
from pathlib import Path
import sys
import streamlit as st

sys.path.append(str(Path(__file__).parent))
from settings import PROJECT_NAME
from src.utils.auth import require_login
from src.ui.theme import inject_dashboard_css, nav_card

st.set_page_config(
    page_title=PROJECT_NAME,
    page_icon="🏑",
    layout="wide",
    initial_sidebar_state="expanded",
)

require_login()

# ── Home ───────────────────────────────────────────────────────────────────
st.markdown('<h1 style="text-align:center">Centro Naval Hockey</h1>', unsafe_allow_html=True)
st.markdown('<h3 style="text-align:center; font-style:italic; font-weight:normal">Primera División Femenina</h3>', unsafe_allow_html=True)
st.divider()

inject_dashboard_css()

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    nav_card("cn-navcard-carga-fisica", "pages/02_carga_fisica.py",
             "📊", "Carga Física", "GPS · ACWR · Intensidad relativa", "#1A73E8")
with col2:
    nav_card("cn-navcard-wellness", "pages/03_wellness.py",
             "💚", "Wellness", "Readiness · Alertas · Molestias", "#34A853")
with col3:
    nav_card("cn-navcard-fisico-tt", "pages/04_fisico_vs_tt.py",
             "⚖️", "Físico vs Técnico-Táctico", "Comparativa de demandas", "#F9AB00")
with col4:
    nav_card("cn-navcard-perfil", "pages/05_perfil_jugadora.py",
             "🎯", "Perfil de Jugadora", "Evolución individual en el tiempo", "#A78BFA")
with col5:
    nav_card("cn-navcard-partidos", "pages/06_partidos.py",
             "🏆", "Partidos", "Radar comparativo entre partidos", "#EF5350")

st.divider()
st.caption("CN Hockey Performance")