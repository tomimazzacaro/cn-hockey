# app.py
from pathlib import Path
import sys
import streamlit as st

sys.path.append(str(Path(__file__).parent))
from settings import PROJECT_NAME
from src.utils.auth import require_login

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

_card_style = """
<style>
.cn-card {
    background: linear-gradient(135deg, #0f2b5b 0%, #1a3a6b 60%, #1e4d8c 100%);
    border-radius: 14px;
    padding: 32px 24px;
    text-align: center;
    box-shadow: 0 4px 20px rgba(0,0,0,0.35);
    border-top: 4px solid var(--accent);
    transition: box-shadow 0.2s ease, transform 0.2s ease;
    cursor: pointer;
}
.cn-card:hover {
    box-shadow: 0 12px 28px rgba(0,0,0,0.45);
    transform: translateY(-3px);
}
.cn-card .icon  { font-size: 2.4rem; margin-bottom: 12px; }
.cn-card .title { font-size: 1.15rem; font-weight: 700; margin: 0 0 8px; color: #ffffff; }
.cn-card .sub   { font-size: 0.83rem; color: #93c5fd; margin: 0; letter-spacing: 0.02em; }
</style>
"""

def _card(icon, title, subtitle, color, href=None):
    onclick = f'window.location.href="{href}"' if href else ""
    cursor  = "pointer" if href else "default"
    return (
        f'<div class="cn-card" style="border-top-color:{color};--accent:{color};'
        f'cursor:{cursor}" onclick="{onclick}">'
        f'<div class="icon">{icon}</div>'
        f'<p class="title">{title}</p>'
        f'<p class="sub">{subtitle}</p>'
        f'</div>'
    )

st.markdown(_card_style, unsafe_allow_html=True)

col1, col2, col3 = st.columns(3)
with col1:
    st.markdown(_card("📊", "Carga Física", "GPS · ACWR · Intensidad relativa", "#1A73E8", "/carga_fisica"), unsafe_allow_html=True)
with col2:
    st.markdown(_card("💚", "Wellness", "Readiness · Alertas · Molestias", "#34A853", "/wellness"), unsafe_allow_html=True)
with col3:
    st.markdown(_card("📈", "Próximamente", "Tendencias · Comparativas", "#9CA3AF"), unsafe_allow_html=True)

st.divider()
st.caption("CN Hockey Performance")