"""
Limpieza del CSS viejo del menú lateral automático (relabel/íconos por nombre de archivo, páginas
escondidas de la lista, enlaces manuales repintados). Con el menú agrupado el nombre y el ícono de cada
entrada salen de src/ui/navegacion.py: renombrar un archivo de pages/ ya no rompe ningún selector.
"""
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

import settings  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
APP = str(RAIZ / "app.py")
VIEJOS = ("stSidebarNavItems", "stSidebarNavLink", 'a[href$="/', 'stPageLink-NavLink"][href=')


def test_theme_ya_no_trae_selectores_del_menu_automatico_atados_a_nombres_de_archivo():
    fuente = (RAIZ / "src" / "ui" / "theme.py").read_text(encoding="utf-8")
    for viejo in VIEJOS:
        assert viejo not in fuente, viejo
    assert "_icon_data_uri" not in fuente           # solo lo usaba ese CSS


@pytest.mark.parametrize("agrupado", [True, False])
def test_el_css_inyectado_ya_no_contiene_esos_selectores(monkeypatch, agrupado):
    monkeypatch.setattr(settings, "USAR_MENU_AGRUPADO", agrupado)
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["authenticated"] = True
    at.run()
    assert not at.exception
    css = " ".join(m.value for m in at.markdown)
    for viejo in VIEJOS:
        assert viejo not in css, viejo


def test_el_menu_plano_de_respaldo_ya_no_repinta_a_mano_tres_enlaces(monkeypatch):
    # Sin ese CSS la lista automática ya no los esconde: repintarlos acá los duplicaría.
    monkeypatch.setattr(settings, "USAR_MENU_AGRUPADO", False)
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["authenticated"] = True
    at.run()
    assert not at.exception
    assert len(at.sidebar.get("page_link")) == 0
    assert len([b for b in at.sidebar.button if "Cerrar sesión" in b.label]) == 1


def test_las_tarjetas_de_la_home_y_el_boton_home_conservan_su_css(monkeypatch):
    monkeypatch.setattr(settings, "USAR_MENU_AGRUPADO", True)
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["authenticated"] = True
    at.run()
    css = " ".join(m.value for m in at.markdown)
    assert "st-key-cn-navcard-" in css and "st-key-cn-home-link" in css      # lo que SÍ se usa sigue ahí
