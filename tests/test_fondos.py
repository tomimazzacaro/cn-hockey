"""
Temas de fondo (gris topo / azul): una sola fuente de verdad en src/ui/fondos.py, atada al tema
de .streamlit/config.toml. Garantías: el tema "azul" es EXACTAMENTE lo de antes (rollback), todo
se lee sobre cada tema, el script que cambia de tema reescribe config.toml sin romperlo, y el
tema que usa el código es el mismo que declara config.toml (no pueden contradecirse).
"""
import importlib
import re
from pathlib import Path

import pytest

pytest.importorskip("streamlit")

from src.ui.fondos import (  # noqa: E402
    TEMAS, escribir_config, tema_activo, tema_para_fondo,
)
from src.utils.colores import contraste, suavizar  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
CONFIG = RAIZ / ".streamlit" / "config.toml"
ACENTOS_ORIGINALES = ["#1A73E8", "#34A853", "#F9AB00", "#A78BFA", "#EF5350", "#0EA5A5", "#F472B6", "#84CC16"]


def test_los_temas_acordados_existen():
    assert set(TEMAS) == {"azul", "topo", "topo_medio", "grafito"}


def test_el_tema_azul_es_exactamente_lo_de_antes():
    a = TEMAS["azul"]
    assert a.pagina == "#0a1628" and a.secundario == "#0f2b5b"
    assert a.degradado == "linear-gradient(135deg, #0f2b5b 0%, #1a3a6b 60%, #1e4d8c 100%)"
    assert (a.chart_bg, a.chart_grid) == ("#0d1b3e", "#1a2f5a")
    assert (a.pista, a.chip) == ("#16294f", "#0f2b5b")


def test_los_fondos_de_pagina_son_unicos_para_poder_identificar_el_tema():
    paginas = [t.pagina.lower() for t in TEMAS.values()]
    assert len(set(paginas)) == len(paginas)


def test_tema_para_fondo_identifica_por_el_color_de_pagina_sin_importar_mayusculas():
    assert tema_para_fondo("#262324") == TEMAS["topo"]
    assert tema_para_fondo("#262324".upper()) == TEMAS["topo"]
    assert tema_para_fondo("#0A1628") == TEMAS["azul"]


@pytest.mark.parametrize("desconocido", [None, "", "#123456", "rojo"])
def test_un_fondo_desconocido_cae_al_tema_azul_de_siempre(desconocido):
    assert tema_para_fondo(desconocido) == TEMAS["azul"]


@pytest.mark.parametrize("nombre", ["azul", "topo", "topo_medio", "grafito"])
def test_el_texto_claro_se_lee_sobre_cada_tema(nombre):
    t = TEMAS[nombre]
    for fondo in (t.pagina, t.secundario, t.chart_bg, *t.paradas):
        # 4,5 = lectura cómoda (WCAG AA). El azul de siempre baja a 6,8 en el extremo claro del degradado.
        assert contraste("#e2e8f0", fondo) >= 4.5, f"{nombre}: {fondo}"          # color de texto de config.toml
    assert contraste("#ffffff", t.paradas[1]) >= 7.0                              # texto blanco sobre la tarjeta


def test_topo_oscuro_se_lee_con_holgura_aaa_en_todas_sus_superficies():
    t = TEMAS["topo"]
    for fondo in (t.pagina, t.secundario, t.chart_bg, *t.paradas):
        assert contraste("#e2e8f0", fondo) >= 7.0, fondo


@pytest.mark.parametrize("nombre", ["azul", "topo", "grafito"])
def test_los_acentos_suaves_se_ven_en_los_graficos_de_cada_tema(nombre):
    t = TEMAS[nombre]
    for c in ACENTOS_ORIGINALES:
        assert contraste(suavizar(c, 0.5), t.chart_bg) >= 3.0, f"{nombre}: {c}"


def test_el_degradado_se_arma_con_las_tres_paradas():
    t = TEMAS["topo"]
    assert t.degradado == f"linear-gradient(135deg, {t.paradas[0]} 0%, {t.paradas[1]} 60%, {t.paradas[2]} 100%)"


# ── config.toml y el tema activo ─────────────────────────────────────────────

def test_config_toml_declara_el_tema_topo_y_el_codigo_lo_sigue():
    texto = CONFIG.read_text(encoding="utf-8")
    assert re.search(r'backgroundColor\s*=\s*"#262324"', texto)
    assert re.search(r'secondaryBackgroundColor\s*=\s*"#302c2d"', texto)
    assert tema_activo() == TEMAS["topo"]


def test_theme_py_usa_el_tema_activo_en_tarjetas_y_graficos():
    import src.ui.theme as theme
    t = tema_activo()
    assert theme.CARD_GRADIENT == t.degradado
    assert (theme.CHART_BG, theme.CHART_GRID) == (t.chart_bg, t.chart_grid)


def test_escribir_config_cambia_solo_los_dos_colores_de_fondo(tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text(CONFIG.read_text(encoding="utf-8"), encoding="utf-8")
    escribir_config("azul", cfg)
    nuevo = cfg.read_text(encoding="utf-8")
    assert 'backgroundColor = "#0a1628"' in nuevo and 'secondaryBackgroundColor = "#0f2b5b"' in nuevo
    # lo demás queda intacto
    for linea in ('base = "dark"', 'primaryColor = "#60a5fa"', 'textColor = "#e2e8f0"', "maxUploadSize = 50"):
        assert linea in nuevo


def test_escribir_config_ida_y_vuelta_deja_el_archivo_igual(tmp_path):
    cfg = tmp_path / "config.toml"
    original = CONFIG.read_text(encoding="utf-8")
    cfg.write_text(original, encoding="utf-8")
    escribir_config("grafito", cfg)
    escribir_config("topo", cfg)
    assert cfg.read_text(encoding="utf-8") == original


def test_escribir_config_rechaza_un_tema_inexistente(tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text(CONFIG.read_text(encoding="utf-8"), encoding="utf-8")
    with pytest.raises(ValueError):
        escribir_config("fucsia", cfg)
    assert cfg.read_text(encoding="utf-8") == CONFIG.read_text(encoding="utf-8")
