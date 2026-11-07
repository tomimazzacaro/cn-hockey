"""
Pruebas del arranque de la app (app.py) en sus dos modos, con Streamlit AppTest:
  * bandera apagada: la Home de siempre (lista plana de páginas);
  * bandera prendida: router con st.navigation (menú agrupado + hubs).
No tocan Google Sheets ni la base: la Home no carga datos.
"""
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

import settings  # noqa: E402

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def _correr(monkeypatch, agrupado: bool) -> AppTest:
    monkeypatch.setattr(settings, "USAR_MENU_AGRUPADO", agrupado)
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["authenticated"] = True
    return at.run()


def _secciones(at: AppTest) -> list[str]:
    import re
    html = " ".join(m.value for m in at.markdown)
    return re.findall(r'cn-section-title-text">([^<]+)<', html)


def _tarjetas(at: AppTest) -> set[str]:
    import re
    html = " ".join(m.value for m in at.markdown)
    return set(re.findall(r"st-key-(cn-navcard-[a-z_]+)", html))


@pytest.mark.parametrize("agrupado", [False, True])
def test_la_home_se_dibuja_igual_en_los_dos_modos(monkeypatch, agrupado):
    at = _correr(monkeypatch, agrupado)
    assert not at.exception
    assert _secciones(at) == ["Monitoreo del equipo", "Individual", "Planificación", "Análisis"]
    assert len(_tarjetas(at)) == 9


def test_modo_plano_conserva_el_menu_de_siempre_con_su_sidebar(monkeypatch):
    at = _correr(monkeypatch, False)
    assert len([b for b in at.sidebar.button if "Cerrar sesión" in b.label]) == 1


def test_modo_agrupado_dibuja_el_sidebar_una_sola_vez(monkeypatch):
    at = _correr(monkeypatch, True)
    assert len([b for b in at.sidebar.button if "Cerrar sesión" in b.label]) == 1
    textos = " ".join(m.value for m in at.sidebar.markdown)
    assert "Centro Naval Hockey" in textos


def test_modo_agrupado_sin_sesion_pide_login_y_no_muestra_la_home(monkeypatch):
    monkeypatch.setattr(settings, "USAR_MENU_AGRUPADO", True)
    at = AppTest.from_file(APP, default_timeout=60).run()      # sin authenticated
    assert not at.exception
    assert _tarjetas(at) == set()


# ── posición del menú: lateral (por defecto) o barra superior ────────────────

@pytest.mark.parametrize("posicion", ["sidebar", "top"])
def test_el_router_corre_con_el_menu_lateral_o_arriba(monkeypatch, posicion):
    monkeypatch.setattr(settings, "POSICION_MENU", posicion)
    at = _correr(monkeypatch, True)
    assert not at.exception
    assert _secciones(at) == ["Monitoreo del equipo", "Individual", "Planificación", "Análisis"]
    assert len(_tarjetas(at)) == 9


@pytest.mark.parametrize("posicion", ["sidebar", "top"])
def test_cerrar_sesion_sigue_disponible_en_las_dos_posiciones(monkeypatch, posicion):
    monkeypatch.setattr(settings, "POSICION_MENU", posicion)
    at = _correr(monkeypatch, True)
    assert len([b for b in at.sidebar.button if "Cerrar sesión" in b.label]) == 1
    assert "Centro Naval Hockey" in " ".join(m.value for m in at.sidebar.markdown)


def test_las_tarjetas_de_la_home_no_muestran_el_icono_de_la_pagina_destino(monkeypatch):
    # st.page_link hereda el ícono de la página destino (ahora las páginas tienen ícono para la barra
    # superior): en la tarjeta ya hay un ícono grande propio, el chico duplicado se oculta.
    import re
    at = _correr(monkeypatch, True)
    css = " ".join(m.value for m in at.markdown)
    assert re.search(r'st-key-cn-navcard-[^{]*\[data-testid="stPageLink"\][^{]*\[data-testid="stIconMaterial"\]\s*\{[^}]*display:\s*none', css)
