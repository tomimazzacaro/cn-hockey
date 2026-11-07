"""
Suavizado de la paleta ("pastel"): la función es pura y la perilla CN_PASTEL controla cuánto.
Garantías que importan: conserva el tono de cada color, nunca aumenta la saturación, con la
perilla en 0 vuelven EXACTAMENTE los colores de antes (rollback), el semáforo se suaviza menos
que los acentos y sigue siendo distinguible, y todo se lee sobre el fondo oscuro del dashboard.
"""
import colorsys
import importlib

import pytest

pytest.importorskip("streamlit")

from src.utils.colores import contraste, distancia_color, hls, suavizar  # noqa: E402

FONDO = "#0d1b3e"    # CHART_BG: el fondo real del dashboard
BASES = ["#1A73E8", "#34A853", "#F9AB00", "#A78BFA", "#EF5350", "#0EA5A5", "#F472B6", "#84CC16", "#8D6E63"]


def _tono_grados(h: str) -> float:
    return hls(h)[0] * 360


def _dist_circular(a: float, b: float) -> float:
    d = abs(a - b) % 360
    return min(d, 360 - d)


@pytest.mark.parametrize("h", BASES)
def test_nivel_cero_devuelve_el_mismo_color(h):
    assert suavizar(h, 0.0).upper() == h.upper()


@pytest.mark.parametrize("h", BASES)
def test_conserva_el_tono_aunque_se_suavice_al_maximo(h):
    if hls(h)[2] < 0.25:          # casi gris (marrón de Biblioteca): el tono casi no existe
        return
    assert _dist_circular(_tono_grados(h), _tono_grados(suavizar(h, 1.0))) < 6


@pytest.mark.parametrize("h", BASES)
def test_nunca_aumenta_la_saturacion_ni_oscurece(h):
    for nivel in (0.25, 0.5, 1.0):
        s = suavizar(h, nivel)
        assert hls(s)[2] <= hls(h)[2] + 1e-6
        assert hls(s)[1] >= hls(h)[1] - 1e-6      # pastel = más claro, nunca más oscuro


def test_mas_nivel_significa_mas_suave_de_forma_monotona():
    sat = [hls(suavizar("#F9AB00", n))[2] for n in (0, 0.25, 0.5, 0.75, 1.0)]
    assert sat == sorted(sat, reverse=True)
    assert hls(suavizar("#F9AB00", 0.5))[2] < 0.9      # el ámbar deja de estar al 100 %


@pytest.mark.parametrize("h", BASES)
def test_los_acentos_suavizados_se_leen_sobre_el_fondo_oscuro(h):
    assert contraste(suavizar(h, 0.5), FONDO) >= 4.5


def test_formato_hex_valido():
    import re
    for h in BASES:
        assert re.fullmatch(r"#[0-9A-F]{6}", suavizar(h, 0.5))


# ── la perilla y las paletas reales ──────────────────────────────────────────

@pytest.fixture
def recargar(monkeypatch):
    """Recarga settings y theme con el entorno definido en el test, y los restaura al salir."""
    import settings
    import src.ui.theme as theme

    def _(valor: str | None):
        if valor is None:
            monkeypatch.delenv("CN_PASTEL", raising=False)
        else:
            monkeypatch.setenv("CN_PASTEL", valor)
        importlib.reload(settings)
        return settings, importlib.reload(theme)

    yield _
    monkeypatch.undo()
    importlib.reload(settings)
    importlib.reload(theme)


def test_perilla_en_cero_restaura_exactamente_los_colores_originales(recargar):
    settings, theme = recargar("0")
    assert settings.PAGE_COLORS == settings.PAGE_COLORS_ORIGINAL
    assert theme.ZONE_CFG == theme.ZONE_CFG_ORIGINAL
    assert theme.BAR_CATEGORICAL_PALETTE == theme.BAR_CATEGORICAL_PALETTE_ORIGINAL


def test_por_defecto_es_suave_y_los_acentos_cambian(recargar):
    settings, _ = recargar(None)
    assert settings.NIVEL_PASTEL == 0.5
    assert settings.PAGE_COLORS != settings.PAGE_COLORS_ORIGINAL
    assert set(settings.PAGE_COLORS) == set(settings.PAGE_COLORS_ORIGINAL)


@pytest.mark.parametrize("valor, esperado", [("0", 0.0), ("100", 1.0), ("30", 0.3), ("250", 1.0),
                                              ("-5", 0.0), ("abc", 0.5), ("", 0.5)])
def test_la_perilla_se_acota_y_ignora_valores_invalidos(recargar, valor, esperado):
    settings, _ = recargar(valor)
    assert settings.NIVEL_PASTEL == pytest.approx(esperado)


def test_el_semaforo_se_suaviza_menos_que_los_acentos(recargar):
    settings, theme = recargar(None)
    for zona, cfg in theme.ZONE_CFG.items():
        orig = theme.ZONE_CFG_ORIGINAL[zona]["color"]
        caida_semaforo = hls(orig)[2] - hls(cfg["color"])[2]
        assert caida_semaforo >= -1e-6
    caida_acento = hls("#F9AB00")[2] - hls(settings.PAGE_COLORS["fisico_tt"])[2]
    caida_rojo = hls("#EA4335")[2] - hls(theme.ZONE_CFG["Riesgo Alto"]["color"])[2]
    assert caida_rojo < caida_acento


def test_el_semaforo_sigue_distinguiendo_optimo_precaucion_y_riesgo(recargar):
    _, theme = recargar(None)
    colores = [theme.ZONE_CFG[z]["color"] for z in ("Óptimo", "Precaución", "Riesgo Alto")]
    for i in range(3):
        for j in range(i + 1, 3):
            assert distancia_color(colores[i], colores[j]) > 40       # bien separados a simple vista
    for z, cfg in theme.ZONE_CFG.items():
        antes = contraste(theme.ZONE_CFG_ORIGINAL[z]["color"], cfg["bg"])
        ahora = contraste(cfg["color"], cfg["bg"])
        # Si antes se leía bien (>= 4,5) tiene que seguir leyéndose bien; si ya estaba bajo (el gris
        # de "Sin datos", 3,04), al menos no empeora. Una décima de diferencia en el ámbar no importa.
        assert ahora >= min(antes, 4.5) - 1e-6


def test_el_reporte_semanal_conserva_los_colores_originales_del_semaforo(recargar):
    _, theme = recargar(None)
    assert theme.ZONE_CFG_ORIGINAL["Riesgo Alto"]["color"] == "#EA4335"
    assert theme.ZONE_CFG_ORIGINAL["Óptimo"]["color"] == "#34A853"
