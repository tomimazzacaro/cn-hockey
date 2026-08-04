# src/utils/auth.py
import base64
from pathlib import Path
import sys
import streamlit as st

sys.path.append(str(Path(__file__).parent.parent.parent))
from settings import LOGO_PATH
from src.ui.theme import CARD_GRADIENT

def _get_credentials() -> dict:
    try:
        return dict(st.secrets.get("credentials", {}))
    except Exception:
        return {}


def _logo_b64() -> str | None:
    try:
        with open(LOGO_PATH, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except FileNotFoundError:
        return None


def require_login() -> None:
    """
    Muestra el portal de login si el usuario no está autenticado.
    Si está autenticado, renderiza el sidebar compartido.
    Llamar al inicio de cada página, justo después de set_page_config.
    """
    if st.session_state.get("authenticated"):
        _render_sidebar()
        return

    _show_login_page()
    st.stop()


def _render_sidebar() -> None:
    logo = _logo_b64()
    with st.sidebar:
        if logo:
            st.markdown(
                f'<div style="text-align:center; padding: 8px 0 4px">'
                f'<img src="data:image/jpeg;base64,{logo}" width="110"/>'
                f'</div>',
                unsafe_allow_html=True,
            )
        st.markdown(f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@1,600;1,700&display=swap');
        .cn-sidebar-title {{
            font-family: 'Playfair Display', serif;
            font-style: italic; text-align: center;
            font-size: 1.25rem; font-weight: 700; color: #fff; margin: 6px 0 2px;
        }}
        .cn-sidebar-subtitle {{
            text-align: center; font-style: italic; color: #93c5fd;
            font-size: 0.78rem; margin: 0 0 8px;
        }}
        </style>
        <p class="cn-sidebar-title">Centro Naval Hockey</p>
        <p class="cn-sidebar-subtitle">Primera División Femenina</p>
        """, unsafe_allow_html=True)
        # Presentación y Análisis se repintan acá a mano, debajo del escudo —
        # el CSS de inject_dashboard_css() las esconde de la lista automática
        # de arriba (ver comentario ahí) para que queden separadas del resto
        # de las páginas como un bloque aparte, no mezcladas en la lista.
        st.page_link("pages/07_presentacion.py", label="Presentación", icon="🎤")
        st.page_link("pages/08_analisis.py", label="Análisis", icon="📋")
        st.divider()
        st.caption("Navegá usando el menú de páginas ↑")
        st.divider()
        if st.button("🔒 Cerrar sesión", use_container_width=True, key="_logout"):
            st.session_state.clear()
            st.rerun()


def _show_login_page() -> None:
    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@1,600;1,700&display=swap');

    #MainMenu, header, footer {{ visibility: hidden; }}
    .block-container {{ padding-top: 0 !important; }}

    .login-wrapper {{
        display: flex;
        justify-content: center;
        align-items: center;
        min-height: 90vh;
    }}
    .login-card {{
        background: {CARD_GRADIENT};
        border-radius: 20px;
        padding: 48px 44px 40px;
        width: 100%;
        max-width: 420px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.45);
        border: 1px solid rgba(255,255,255,0.08);
        text-align: center;
    }}
    .login-icon  {{ font-size: 3.2rem; margin-bottom: 6px; }}
    .login-logo  {{ width: 92px; height: 92px; object-fit: contain; margin: 0 auto 6px; display: block; }}
    .login-title {{
        font-family: 'Playfair Display', serif;
        font-style: italic;
        font-size: 1.9rem; font-weight: 700; color: #fff; margin: 0 0 4px;
    }}
    .login-sub   {{ font-size: 0.85rem; color: #93c5fd; margin: 0 0 32px;
                   font-style: italic; }}
    .login-divider {{ border: none; border-top: 1px solid rgba(255,255,255,0.1);
                     margin: 0 0 28px; }}
    </style>
    """, unsafe_allow_html=True)

    # Card contenedora centrada
    _, center, _ = st.columns([1, 1.4, 1])

    logo = _logo_b64()
    icon_html = (
        f'<img class="login-logo" src="data:image/jpeg;base64,{logo}"/>'
        if logo else '<div class="login-icon">🏑</div>'
    )

    with center:
        st.markdown(f"""
        <div class="login-card">
            {icon_html}
            <p class="login-title">Centro Naval Hockey</p>
            <p class="login-sub">Performance Hub · Primera División Femenina</p>
            <hr class="login-divider"/>
        </div>
        """, unsafe_allow_html=True)

        with st.form("login_form", clear_on_submit=False):
            usuario = st.text_input("Usuario", placeholder="Usuario")
            password = st.text_input("Contraseña", type="password",
                                     placeholder="Contraseña")
            submitted = st.form_submit_button("Ingresar",
                                              use_container_width=True,
                                              type="primary")

        if submitted:
            if _get_credentials().get(usuario) == password:
                st.session_state["authenticated"] = True
                st.session_state["usuario"] = usuario
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos.")
