"""
Tipografía de los títulos (Bebas Neue en mayúsculas; Playfair cursiva como respaldo). Una sola
definición en src/ui/tipografia.py para los cuatro lugares: título de página, nombre de la jugadora
en Perfil, título del menú lateral y título del login. Perilla de rollback: CN_FUENTE=playfair.
"""
import importlib
import re
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

import settings  # noqa: E402
from src.ui.tipografia import ESTILOS, FUENTES_IMPORT_URL, SITIOS, estilo_titulo  # noqa: E402

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def test_los_cuatro_sitios_estan_definidos_en_las_dos_fuentes():
    assert set(SITIOS) == {"pagina", "hero", "sidebar", "login"}
    for fuente in ESTILOS:
        for sitio in SITIOS:
            assert estilo_titulo(sitio, fuente)


@pytest.mark.parametrize("sitio", sorted(SITIOS))
def test_bebas_siempre_con_peso_400_y_en_mayusculas(sitio):
    css = estilo_titulo(sitio, "bebas")
    assert "'Bebas Neue'" in css
    assert re.search(r"font-weight:\s*400\b", css)          # Bebas solo existe en 400: 700 = negrita falsa
    assert "font-weight: 700" not in css
    assert "text-transform: uppercase" in css
    assert "font-style: italic" not in css
    assert "letter-spacing" in css                           # las mayúsculas necesitan aire


@pytest.mark.parametrize("sitio", sorted(SITIOS))
def test_playfair_conserva_el_estilo_de_antes_cursiva_700_sin_mayusculas(sitio):
    css = estilo_titulo(sitio, "playfair")
    assert "'Playfair Display'" in css and "font-style: italic" in css and "font-weight: 700" in css
    assert "text-transform" not in css


def test_los_tamanos_de_playfair_son_los_de_antes():
    assert "font-size: 2.5rem" in estilo_titulo("pagina", "playfair")
    assert "font-size: 2rem" in estilo_titulo("hero", "playfair")
    assert "font-size: 1.25rem" in estilo_titulo("sidebar", "playfair")
    assert "font-size: 1.9rem" in estilo_titulo("login", "playfair")


def test_el_titulo_de_pagina_fuerza_el_estilo_para_ganarle_al_h1_de_streamlit():
    css = estilo_titulo("pagina", "bebas")
    assert "font-weight: 400 !important" in css and "font-family" in css and "!important" in css


def test_una_fuente_inexistente_cae_a_bebas():
    assert estilo_titulo("pagina", "comic-sans") == estilo_titulo("pagina", "bebas")


def test_se_cargan_las_dos_fuentes_porque_la_presentacion_sigue_usando_playfair():
    assert "family=Bebas+Neue" in FUENTES_IMPORT_URL
    assert "family=Playfair+Display" in FUENTES_IMPORT_URL
    assert FUENTES_IMPORT_URL.startswith("https://fonts.googleapis.com/css2?")


# ── la perilla ───────────────────────────────────────────────────────────────

@pytest.fixture
def recargar(monkeypatch):
    def _(valor):
        if valor is None:
            monkeypatch.delenv("CN_FUENTE", raising=False)
        else:
            monkeypatch.setenv("CN_FUENTE", valor)
        return importlib.reload(settings)
    yield _
    monkeypatch.undo()
    importlib.reload(settings)


@pytest.mark.parametrize("valor, esperado", [(None, "bebas"), ("bebas", "bebas"), ("playfair", "playfair"),
                                              ("PLAYFAIR", "playfair"), ("otra", "bebas"), ("", "bebas")])
def test_perilla_cn_fuente(recargar, valor, esperado):
    assert recargar(valor).FUENTE_TITULOS == esperado


# ── se aplica de verdad en las pantallas ─────────────────────────────────────

def _css_markdown(at: AppTest) -> str:
    return " ".join(m.value for m in at.markdown)


def test_la_home_usa_bebas_en_el_titulo_de_pagina(monkeypatch):
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["authenticated"] = True
    at.run()
    assert not at.exception
    css = _css_markdown(at)
    m = re.search(r"\.cn-page-header-title\s*\{(.*?)\}", css, re.S)
    assert m and "'Bebas Neue'" in m.group(1) and "font-weight: 400" in m.group(1)


def test_el_login_y_el_sidebar_usan_bebas():
    login = AppTest.from_file(APP, default_timeout=60).run()                 # sin sesión: pantalla de login
    assert not login.exception
    m = re.search(r"\.login-title\s*\{(.*?)\}", _css_markdown(login), re.S)
    assert m and "'Bebas Neue'" in m.group(1)

    logueada = AppTest.from_file(APP, default_timeout=60)
    logueada.session_state["authenticated"] = True
    logueada.run()
    sidebar_css = " ".join(m.value for m in logueada.sidebar.markdown)
    m = re.search(r"\.cn-sidebar-title\s*\{(.*?)\}", sidebar_css, re.S)
    assert m and "'Bebas Neue'" in m.group(1)


# ── centrado: el hueco de las mayúsculas y el ícono de enlace de Streamlit ──────────────────────

@pytest.mark.parametrize("sitio", ["pagina", "sidebar", "login"])
def test_los_titulos_centrados_compensan_el_espaciado_entre_letras(sitio):
    # letter-spacing deja un hueco tras la ÚLTIMA letra y corre el texto a la izquierda; un padding-left
    # igual lo equilibra. (El nombre de la jugadora va alineado a la izquierda: no se compensa.)
    css = estilo_titulo(sitio, "bebas")
    espaciado = re.search(r"letter-spacing:\s*([\d.]+em)", css).group(1)
    assert re.search(rf"padding-left:\s*{re.escape(espaciado)}", css), css


def test_el_nombre_de_la_jugadora_no_se_compensa_porque_va_a_la_izquierda():
    assert "padding-left" not in estilo_titulo("hero", "bebas")


def test_playfair_no_lleva_compensacion_porque_no_tiene_espaciado_extra():
    for sitio in ("pagina", "sidebar", "login"):
        assert "padding-left" not in estilo_titulo(sitio, "playfair")


def test_el_css_oculta_el_icono_de_enlace_del_titulo_de_pagina():
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["authenticated"] = True
    at.run()
    css = " ".join(m.value for m in at.markdown)
    assert re.search(r'\.cn-page-header-title\s+\[data-testid="stHeaderActionElements"\]\s*\{[^}]*display:\s*none', css)
