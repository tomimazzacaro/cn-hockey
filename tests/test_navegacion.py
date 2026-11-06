"""
Guardas de la navegación: una sola lista (src/ui/navegacion.py) alimenta la Home y, más
adelante, el menú lateral. Estos tests evitan que una página nueva quede sin registrar o
que un ícono/color referenciado no exista.
"""
from pathlib import Path

import pytest

pytest.importorskip("streamlit")

from settings import PAGE_COLORS  # noqa: E402
from src.ui.navegacion import (  # noqa: E402
    PAGINA_PRESENTACION, SECCIONES, entradas_menu, paginas_registradas,
)
from src.ui.theme import ICONS  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent


def test_toda_pagina_del_directorio_pages_esta_registrada_una_sola_vez():
    en_disco = sorted(f"pages/{p.name}" for p in (RAIZ / "pages").glob("*.py"))
    registradas = sorted(p.archivo for p in paginas_registradas())
    assert registradas == en_disco


def test_toda_pagina_registrada_existe():
    for p in paginas_registradas():
        assert (RAIZ / p.archivo).is_file(), p.archivo


def test_iconos_y_colores_referenciados_existen():
    for p in paginas_registradas():
        assert p.icono in ICONS, f"{p.clave}: ícono '{p.icono}' no está en ICONS"
        if p.color_clave is not None:
            assert p.color_clave in PAGE_COLORS, f"{p.clave}: color '{p.color_clave}' no está en PAGE_COLORS"


def test_claves_y_titulos_de_seccion_son_unicos():
    claves = [p.clave for p in paginas_registradas()]
    assert len(claves) == len(set(claves))
    titulos = [s.titulo for s in SECCIONES]
    assert len(titulos) == len(set(titulos))


def test_las_secciones_acordadas_y_su_contenido():
    assert [s.titulo for s in SECCIONES] == ["Monitoreo del equipo", "Individual", "Planificación", "Análisis"]
    por_seccion = {s.titulo: [p.clave for p in s.paginas] for s in SECCIONES}
    assert por_seccion["Monitoreo del equipo"] == ["carga_fisica", "wellness", "partidos"]
    assert por_seccion["Individual"] == ["perfil"]
    assert por_seccion["Planificación"] == ["entrenamiento", "fuerza", "biblioteca"]
    assert por_seccion["Análisis"] == ["fisico_tt", "analisis"]


def test_presentacion_queda_fuera_de_las_secciones_pero_registrada():
    en_secciones = {p.clave for s in SECCIONES for p in s.paginas}
    assert PAGINA_PRESENTACION.clave not in en_secciones
    assert PAGINA_PRESENTACION in paginas_registradas()


@pytest.fixture
def settings_recargable(monkeypatch):
    """Recarga `settings` con el entorno que se defina en el test y lo deja como estaba al salir."""
    import importlib
    import settings
    yield lambda: importlib.reload(settings)
    monkeypatch.undo()
    importlib.reload(settings)


def test_el_menu_agrupado_arranca_prendido_por_defecto(monkeypatch, settings_recargable):
    monkeypatch.delenv("CN_MENU_AGRUPADO", raising=False)
    assert settings_recargable().USAR_MENU_AGRUPADO is True


@pytest.mark.parametrize("valor, esperado", [("0", False), ("1", True), ("", True), ("true", True)])
def test_el_menu_agrupado_solo_se_apaga_con_la_variable_en_0(monkeypatch, settings_recargable, valor, esperado):
    # Rollback sin tocar código: CN_MENU_AGRUPADO=0 devuelve el menú plano de siempre.
    monkeypatch.setenv("CN_MENU_AGRUPADO", valor)
    assert settings_recargable().USAR_MENU_AGRUPADO is esperado
