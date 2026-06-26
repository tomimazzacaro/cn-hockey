# src/utils/auth.py
import base64
from pathlib import Path
import streamlit as st

def _get_credentials() -> dict:
    try:
        return dict(st.secrets.get("credentials", {}))
    except Exception:
        return {}
_LOGO_PATH   = Path(__file__).parent.parent.parent / "centro_escudo.jpeg"


def _logo_b64() -> str | None:
    try:
        with open(_LOGO_PATH, "rb") as f:
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
        st.markdown(
            '<h2 style="text-align:center; margin:6px 0 2px">Centro Naval Hockey</h2>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<p style="text-align:center; font-style:italic; color:gray; margin:0 0 8px">'
            'Primera División Femenina</p>',
            unsafe_allow_html=True,
        )
        st.divider()
        st.caption("Navegá usando el menú de páginas ↑")
        st.divider()
        if st.button("🔒 Cerrar sesión", use_container_width=True, key="_logout"):
            st.session_state.clear()
            st.rerun()


def _show_login_page() -> None:
    st.markdown("""
    <style>
    #MainMenu, header, footer { visibility: hidden; }
    .block-container { padding-top: 0 !important; }

    .login-wrapper {
        display: flex;
        justify-content: center;
        align-items: center;
        min-height: 90vh;
    }
    .login-card {
        background: linear-gradient(160deg, #0f2b5b 0%, #1a3a6b 70%, #1e4d8c 100%);
        border-radius: 20px;
        padding: 48px 44px 40px;
        width: 100%;
        max-width: 420px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.45);
        border: 1px solid rgba(255,255,255,0.08);
        text-align: center;
    }
    .login-icon  { font-size: 3.2rem; margin-bottom: 6px; }
    .login-title { font-size: 1.6rem; font-weight: 800; color: #fff; margin: 0 0 4px; }
    .login-sub   { font-size: 0.85rem; color: #93c5fd; margin: 0 0 32px;
                   font-style: italic; }
    .login-divider { border: none; border-top: 1px solid rgba(255,255,255,0.1);
                     margin: 0 0 28px; }
    </style>
    """, unsafe_allow_html=True)

    # Card contenedora centrada
    _, center, _ = st.columns([1, 1.4, 1])

    with center:
        st.markdown("""
        <div class="login-card">
            <div class="login-icon">🏑</div>
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
