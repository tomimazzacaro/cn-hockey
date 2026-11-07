"""
Home compacta: las cuatro secciones van lado a lado (una columna por sección, con sus tarjetas
apiladas) y las tarjetas son horizontales (ícono a la izquierda, texto a la derecha), para que toda
la Home entre en una pantalla sin scrollear. El ajuste fino se verifica midiendo en el navegador.
"""
import re
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

import settings  # noqa: E402
from src.ui.navegacion import SECCIONES  # noqa: E402

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def _home(monkeypatch, agrupado: bool) -> AppTest:
    monkeypatch.setattr(settings, "USAR_MENU_AGRUPADO", agrupado)
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["authenticated"] = True
    at.run()
    assert not at.exception
    return at


def _css(at: AppTest) -> str:
    return " ".join(m.value for m in at.markdown)


def _regla(css: str, selector_regex: str) -> str:
    m = re.search(selector_regex + r"\s*\{([^}]*)\}", css, re.S)
    assert m, f"no encontré la regla {selector_regex}"
    return m.group(1)


@pytest.mark.parametrize("agrupado", [True, False])
def test_las_secciones_van_lado_a_lado_una_columna_por_seccion(monkeypatch, agrupado):
    at = _home(monkeypatch, agrupado)
    assert len(at.columns) == len(SECCIONES)          # antes: 16 (cuatro filas de cuatro)


@pytest.mark.parametrize("agrupado", [True, False])
def test_cada_columna_trae_su_titulo_y_sus_tarjetas(monkeypatch, agrupado):
    at = _home(monkeypatch, agrupado)
    for columna, seccion in zip(at.columns, SECCIONES):
        texto = " ".join(m.value for m in columna.markdown)
        assert f'cn-section-title-text">{seccion.titulo}<' in texto
        for pagina in seccion.paginas:
            assert f"st-key-cn-navcard-{pagina.clave}" in texto


def test_la_tarjeta_es_horizontal_icono_a_la_izquierda_y_texto_a_la_derecha(monkeypatch):
    css = _css(_home(monkeypatch, True))
    tarjeta = _regla(css, r'div\[class\*="st-key-cn-navcard-"\]')
    assert re.search(r"display:\s*grid", tarjeta)
    assert re.search(r"grid-template-columns:\s*40px", tarjeta)
    assert re.search(r"padding:\s*8px 12px", tarjeta)          # chip de 40 + 2 x 8 = 56: entra sin salirse
    assert "min-height: 190px" not in tarjeta           # la altura de antes
    assert re.search(r"min-height:\s*56px", tarjeta)        # el chip (40) + relleno (2 x 8) tiene que caber
    assert "flex-direction: column" not in tarjeta
    assert re.search(r"text-align:\s*left", tarjeta)


def test_el_icono_de_la_tarjeta_ocupa_las_dos_filas_y_el_texto_va_en_la_segunda_columna(monkeypatch):
    css = _css(_home(monkeypatch, True))
    assert re.search(r'st-key-cn-navcard-"\]\s*>\s*div:nth-child\(1\)\s*\{[^}]*grid-row:\s*1\s*/\s*span 2', css)
    assert re.search(r'st-key-cn-navcard-"\]\s*>\s*div:nth-child\(2\)\s*\{[^}]*grid-column:\s*2', css)
    assert re.search(r'st-key-cn-navcard-"\]\s*>\s*div:nth-child\(3\)\s*\{[^}]*grid-column:\s*2', css)


def test_el_chip_del_icono_se_achica_dentro_de_la_tarjeta(monkeypatch):
    css = _css(_home(monkeypatch, True))
    chip = _regla(css, r'div\[class\*="st-key-cn-navcard-"\]\s+\.cn-page-header-icon')
    assert re.search(r"width:\s*40px", chip) and re.search(r"height:\s*40px", chip)
    assert re.search(r"margin:\s*0\s*!important", chip)             # pisa el margin inline que traía


def test_el_relleno_inferior_baja_para_que_no_obligue_a_scrollear(monkeypatch):
    css = _css(_home(monkeypatch, True))
    regla = _regla(css, r'\[data-testid="stMainBlockContainer"\]')
    relleno = re.search(r"padding-bottom:\s*([\d.]+)rem\s*!important", regla)
    assert relleno and float(relleno.group(1)) <= 4        # Streamlit deja 10 rem (160 px) por defecto


def test_las_nueve_tarjetas_siguen_estando(monkeypatch):
    at = _home(monkeypatch, True)
    claves = {p.clave for s in SECCIONES for p in s.paginas}
    assert len(claves) == 9
    assert all(f"st-key-cn-navcard-{c}" in _css(at) for c in claves)


def test_se_oculta_la_caja_entera_del_icono_heredado_no_solo_el_dibujo(monkeypatch):
    # Ocultar solo el <span> del ícono dejaba su caja de 20 px + 8 de separación: el título quedaba 28 px
    # corrido a la derecha del subtítulo.
    css = _css(_home(monkeypatch, True))
    assert re.search(r'st-key-cn-navcard-"\][^{]*\[data-testid="stPageLink"\]\s+a\s*>\s*span:has\(\[data-testid="stIconMaterial"\]\)\s*\{[^}]*display:\s*none', css)


def test_se_anula_el_margen_negativo_del_markdown_que_encogia_la_caja_del_icono(monkeypatch):
    # Streamlit pone margin-bottom:-16px al contenedor de markdown: la caja del chip medía 24 px en vez de
    # 40 y el chip se salía 16 px por abajo de la tarjeta (medido en el navegador).
    css = _css(_home(monkeypatch, True))
    assert re.search(r'st-key-cn-navcard-"\]\s*>\s*div:nth-child\(1\)\s*\[data-testid="stMarkdownContainer"\]\s*\{[^}]*margin-bottom:\s*0\s*!important', css)


def test_las_filas_de_la_tarjeta_son_iguales_para_que_el_icono_quede_centrado(monkeypatch):
    # Con filas "auto" la grilla le daba toda la sobra a la última fila: el chip quedaba 4 px más abajo.
    css = _css(_home(monkeypatch, True))
    tarjeta = _regla(css, r'div\[class\*="st-key-cn-navcard-"\]')
    assert re.search(r"grid-template-rows:\s*1fr 1fr", tarjeta)
    assert re.search(r'st-key-cn-navcard-"\]\s*>\s*div:nth-child\(2\)\s*\{[^}]*align-self:\s*end', css)
    assert re.search(r'st-key-cn-navcard-"\]\s*>\s*div:nth-child\(3\)\s*\{[^}]*align-self:\s*start', css)


# ── espaciado y centrado de la Home ────────────────────────────────────────────────────────────

def test_el_titulo_de_cada_seccion_va_alineado_a_la_izquierda_con_sus_tarjetas(monkeypatch):
    # Centrado se veía desprolijo: el título tiene que arrancar en la misma línea vertical que el borde
    # izquierdo de las tarjetas de su columna (la barra de color queda justo sobre ese borde).
    css = _css(_home(monkeypatch, True))
    regla = _regla(css, r'\[data-testid="stColumn"\]:has\(div\[class\*="st-key-cn-navcard-"\]\)\s+\.cn-section-title')
    assert re.search(r"justify-content:\s*flex-start", regla)
    assert not re.search(r"justify-content:\s*center", regla)


def test_hay_aire_entre_el_titulo_de_la_seccion_y_su_primera_tarjeta(monkeypatch):
    # Medido: 2 px. Con 20 px se separan sin gastar demasiada altura.
    css = _css(_home(monkeypatch, True))
    regla = _regla(css, r'\[data-testid="stColumn"\]:has\(div\[class\*="st-key-cn-navcard-"\]\)\s+\.cn-section-title')
    assert re.search(r"margin:\s*0 0 20px", regla)


def test_el_contenido_de_la_home_va_en_un_contenedor_con_ancho_maximo_y_centrado(monkeypatch):
    # Sin tope, en una pantalla de 1920 px el bloque se estiraba a 1760 px de ancho.
    at = _home(monkeypatch, True)
    css = _css(at)
    assert "st-key-cn-home" in css
    regla = _regla(css, r'div\.st-key-cn-home')
    assert re.search(r"max-width:\s*1280px", regla) and re.search(r"margin:\s*0 auto", regla)


def test_el_enlace_a_presentacion_va_centrado_al_pie(monkeypatch):
    # Centrar el texto DENTRO del enlace no alcanza: el enlace mide lo que mide su contenido y queda a la
    # izquierda (medido: centro en x=255 contra 683 de la ventana). Hay que centrar el contenedor.
    css = _css(_home(monkeypatch, True))
    regla = _regla(css, r'div\.st-key-cn-home-presentacion')
    # El contenedor de Streamlit es una columna flex: para centrar en HORIZONTAL hace falta align-items
    # (justify-content centraría en vertical, y fue el primer intento que no funcionó).
    assert re.search(r"display:\s*flex", regla) and re.search(r"align-items:\s*center", regla)


@pytest.mark.parametrize("agrupado", [True, False])
def test_el_contenedor_de_la_home_no_agrega_columnas_ni_rompe_la_estructura(monkeypatch, agrupado):
    at = _home(monkeypatch, agrupado)
    assert len(at.columns) == len(SECCIONES)
