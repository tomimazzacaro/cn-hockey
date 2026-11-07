"""
Compactación del espacio superior de las páginas:
  A) menos relleno arriba del contenido (contenedor principal y encabezado del título);
  B) sin el botón "Home" cuando el menú está en la barra superior (ya hay un "Inicio" arriba).
"""
import re
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

import settings  # noqa: E402
from src.ui.navegacion import MENU_ARRIBA_KEY  # noqa: E402

APP = str(Path(__file__).resolve().parent.parent / "app.py")
REPO = str(Path(__file__).resolve().parent.parent)


def _css_home(monkeypatch) -> str:
    monkeypatch.setattr(settings, "USAR_MENU_AGRUPADO", True)
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["authenticated"] = True
    at.run()
    assert not at.exception
    return " ".join(m.value for m in at.markdown)


def _regla(css: str, selector_regex: str) -> str:
    m = re.search(selector_regex + r"\s*\{([^}]*)\}", css, re.S)
    assert m, f"no encontré la regla {selector_regex}"
    return m.group(1)


# ── A) rellenos ──────────────────────────────────────────────────────────────

def test_el_contenedor_principal_tiene_menos_relleno_arriba(monkeypatch):
    regla = _regla(_css_home(monkeypatch), r'\[data-testid="stMainBlockContainer"\]')
    assert re.search(r"padding-top:\s*4\.5rem\s*!important", regla)     # 72 px (antes 96-128) bajo la barra de 60


def test_el_encabezado_del_titulo_se_compacta(monkeypatch):
    css = _css_home(monkeypatch)
    cab = _regla(css, r"\.cn-page-header")
    assert re.search(r"margin:\s*0 0 4px", cab)          # vale con el ícono arriba y al costado
    titulo = _regla(css, r"\.cn-page-header-title")
    assert re.search(r"padding-top:\s*0\s*!important", titulo)
    assert re.search(r"padding-bottom:\s*4px\s*!important", titulo)


def test_la_compactacion_no_toca_el_centrado_del_titulo(monkeypatch):
    titulo = _regla(_css_home(monkeypatch), r"\.cn-page-header-title")
    assert re.search(r"padding-left:\s*0\.07em\s*!important", titulo)    # el equilibrio del letter-spacing sigue


# ── B) botón Home ────────────────────────────────────────────────────────────

def _app_home_button(repo: str, arriba):
    import sys
    sys.path.insert(0, repo)
    import streamlit as st
    from src.ui.components import home_button
    from src.ui.navegacion import MENU_ARRIBA_KEY      # la app de prueba corre aislada: import propio
    llamadas = st.session_state.setdefault("llamadas", [])
    st.page_link = lambda *a, **k: llamadas.append(k.get("label"))      # AppTest no tiene registro de páginas
    if arriba is not None:
        st.session_state[MENU_ARRIBA_KEY] = arriba
    home_button()


def _llamadas(arriba) -> list:
    at = AppTest.from_function(_app_home_button, args=(REPO, arriba), default_timeout=30).run()
    assert not at.exception
    return at.session_state["llamadas"]


def test_el_boton_home_no_se_dibuja_con_la_barra_superior():
    assert _llamadas(True) == []


def test_el_boton_home_se_dibuja_con_el_menu_lateral_o_sin_router():
    assert _llamadas(False) == ["Home"]
    assert _llamadas(None) == ["Home"]          # menú plano de siempre: no hay router


@pytest.mark.parametrize("posicion, esperado", [("top", True), ("sidebar", False)])
def test_el_router_avisa_si_el_menu_esta_arriba(monkeypatch, posicion, esperado):
    monkeypatch.setattr(settings, "USAR_MENU_AGRUPADO", True)
    monkeypatch.setattr(settings, "POSICION_MENU", posicion)
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["authenticated"] = True
    at.run()
    assert not at.exception
    assert at.session_state[MENU_ARRIBA_KEY] is esperado
