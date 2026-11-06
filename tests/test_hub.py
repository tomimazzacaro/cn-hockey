"""
Pruebas del "hub": una página con pestañas que corre el script de otra página SOLO cuando su
pestaña está abierta (Streamlit AppTest). Usan páginas falsas en un directorio temporal: no
dependen de Google Sheets ni de la base.
"""
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

REPO = str(Path(__file__).resolve().parent.parent)


def _crear_paginas(tmp_path: Path) -> tuple[str, str]:
    uno = tmp_path / "pag_uno.py"
    uno.write_text(
        "import streamlit as st\n"
        "st.set_page_config(page_title='uno', layout='wide')\n"
        "st.session_state.setdefault('corridas', []).append('uno')\n"
        "st.write('CONTENIDO_UNO')\n", encoding="utf-8")
    dos = tmp_path / "pag_dos.py"
    dos.write_text(
        "import streamlit as st\n"
        "st.session_state.setdefault('corridas', []).append('dos')\n"
        "st.write('CONTENIDO_DOS')\n", encoding="utf-8")
    return str(uno), str(dos)


def _app_hub(repo: str, archivo_uno: str, archivo_dos: str, con_login: bool = False):
    import sys
    sys.path.insert(0, repo)
    import streamlit as st
    from src.ui.hub import render_hub
    from src.ui.navegacion import PaginaNav
    original = st.page_link
    st.page_link = lambda *a, **k: None       # el sidebar real usa st.page_link y AppTest no tiene registro de páginas
    try:
        if con_login:
            st.session_state["authenticated"] = True
            from src.utils.auth import require_login
            require_login()                   # el "router" hace el login una sola vez
        paginas = [PaginaNav("uno", archivo_uno, "Uno", "", "inicio", None),
                   PaginaNav("dos", archivo_dos, "Dos", "", "inicio", None)]
        render_hub("prueba", paginas)
    finally:
        st.page_link = original


def _correr(tmp_path: Path, con_login: bool = False) -> AppTest:
    uno, dos = _crear_paginas(tmp_path)
    return AppTest.from_function(_app_hub, args=(REPO, uno, dos, con_login), default_timeout=30).run()


def _textos(at: AppTest) -> list[str]:
    return [m.value for m in at.markdown]


def test_hub_corre_la_primera_pestana_y_no_la_otra(tmp_path):
    at = _correr(tmp_path)
    assert not at.exception
    assert "CONTENIDO_UNO" in _textos(at)
    assert "CONTENIDO_DOS" not in _textos(at)
    assert at.session_state["corridas"] == ["uno"]          # la pestaña cerrada NO se ejecutó


def test_hub_al_abrir_otra_pestana_corre_solo_esa(tmp_path):
    at = _correr(tmp_path)
    at.session_state["hub_prueba"] = "Dos"                   # la persona abre la pestaña "Dos"
    at.run()
    assert not at.exception
    assert "CONTENIDO_DOS" in _textos(at) and "CONTENIDO_UNO" not in _textos(at)
    assert at.session_state["corridas"][-1] == "dos"


def test_hub_la_pagina_interna_puede_llamar_a_set_page_config_sin_romper(tmp_path):
    at = _correr(tmp_path)                                   # pag_uno llama a st.set_page_config
    assert not at.exception


def test_hub_deja_la_marca_de_sesion_apagada_al_terminar(tmp_path):
    at = _correr(tmp_path)
    assert at.session_state["__hub_activo"] is False


def test_hub_apaga_la_marca_aunque_la_pagina_falle(tmp_path):
    uno, dos = _crear_paginas(tmp_path)
    Path(uno).write_text("raise RuntimeError('pagina rota')\n", encoding="utf-8")
    at = AppTest.from_function(_app_hub, args=(REPO, uno, dos, False), default_timeout=30).run()
    assert at.exception                                      # el error se muestra, no se traga
    assert at.session_state["__hub_activo"] is False


def test_login_dentro_del_hub_no_dibuja_el_sidebar_dos_veces(tmp_path):
    uno, dos = _crear_paginas(tmp_path)
    Path(uno).write_text(
        "import streamlit as st\n"
        "from src.utils.auth import require_login\n"
        "require_login()                                    # como hacen las páginas reales\n"
        "st.write('CONTENIDO_UNO')\n", encoding="utf-8")
    at = AppTest.from_function(_app_hub, args=(REPO, uno, dos, True), default_timeout=30).run()
    assert not at.exception                                  # sin DuplicateWidgetID en "Cerrar sesión"
    assert "CONTENIDO_UNO" in _textos(at)
    assert len([b for b in at.sidebar.button if "Cerrar sesión" in b.label]) == 1


def test_sin_hub_require_login_sigue_dibujando_el_sidebar():
    def _app(repo):
        import sys
        sys.path.insert(0, repo)
        import streamlit as st
        original = st.page_link
        st.page_link = lambda *a, **k: None
        try:
            st.session_state["authenticated"] = True
            from src.utils.auth import require_login
            require_login()
        finally:
            st.page_link = original
    at = AppTest.from_function(_app, args=(REPO,), default_timeout=30).run()
    assert not at.exception
    assert len([b for b in at.sidebar.button if "Cerrar sesión" in b.label]) == 1


def test_sin_sesion_iniciada_require_login_sigue_frenando_aunque_la_marca_este_prendida():
    # La marca del hub NO puede saltear el login: solo vale con la sesión ya autenticada.
    def _app(repo):
        import sys
        sys.path.insert(0, repo)
        import streamlit as st
        st.session_state["__hub_activo"] = True
        from src.utils.auth import require_login
        require_login()
        st.write("NO_DEBERIA_LLEGAR_ACA")
    at = AppTest.from_function(_app, args=(REPO,), default_timeout=30).run()
    assert "NO_DEBERIA_LLEGAR_ACA" not in [m.value for m in at.markdown]
