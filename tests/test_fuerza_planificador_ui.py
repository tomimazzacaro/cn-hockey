"""
Prueba de pantalla de la pestaña Planificación (Streamlit AppTest, base simulada).

Se saltea sola si el entorno no tiene streamlit o psycopg. No toca Supabase ni
Google Sheets: los loaders se reemplazan dentro de la app de prueba.
"""
import builtins
from datetime import date, timedelta
from pathlib import Path

import pytest

pytest.importorskip("psycopg")
pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

REPO = str(Path(__file__).resolve().parent.parent)
HOY = date.today()
LUNES = HOY - timedelta(days=HOY.weekday())


def _app(escenario: str, repo: str, lunes_iso: str, con_escritura: bool):
    # Se ejecuta DENTRO de AppTest: debe ser autosuficiente (imports propios).
    import builtins
    import sys
    sys.path.insert(0, repo)
    from datetime import date
    import numpy as np
    import pandas as pd
    import streamlit as st
    import src.ui.fuerza_planificador as m
    from src.metrics.fuerza_plan import COLUMNAS_ITEM_PLAN

    lunes = date.fromisoformat(lunes_iso)
    cat_fz = pd.DataFrame({
        "ejercicio_id": ["FZA-001", "FZA-003", "FZA-009"],
        "ejercicio": ["Sentadilla frontal", "Hip thrust", "Remo TRX"],
        "categoria": ["a", "b", "c"], "unilateral": [False] * 3,
        "admite_rm": [True, True, False], "ejercicio_referencia": [""] * 3})
    cat_rs = pd.DataFrame({"ejercicio_id": ["RES-006", "RES-007"],
                           "ejercicio": ["Pasadas", "Pasadas"], "categoria": ["", ""]})

    if escenario == "con_plan":
        planes = pd.DataFrame([{"id": "p1", "semana_inicio": lunes, "nombre": "Semana test",
                                "estado": "borrador", "notas": None}])
        items = pd.DataFrame([
            ["MD-5", 1, "fuerza", "FZA-001", "Sentadilla frontal", 4, 5, 80, np.nan, None, np.nan, 90, None],
            ["MD-5", 2, "fuerza", "FZA-003", "Hip thrust", 3, 8, 70, np.nan, None, np.nan, 90, None],
            ["MD-4", 1, "pasada", "RES-006", "Pasadas", np.nan, 4, np.nan, 30, "Z4", 90, 120, None],
        ], columns=COLUMNAS_ITEM_PLAN)
    else:
        planes = pd.DataFrame(columns=["id", "semana_inicio", "nombre", "estado", "notas"])
        items = pd.DataFrame(columns=COLUMNAS_ITEM_PLAN)

    m.listar_planes = lambda cs: planes
    m.cargar_items_plan = lambda cs, pid: items
    m.cargar_parametros = lambda cs: {"umbral_alta_intensidad_vmax": 85.0, "intensidad_base_sin_rm": 50.0}
    m.cargar_zonas_velocidad = lambda cs: pd.DataFrame(
        columns=["nombre", "orden", "desde_pct_vmax", "hasta_pct_vmax"])
    if not hasattr(builtins, "_GUARDADOS"):
        builtins._GUARDADOS = []
    guardados = builtins._GUARDADOS
    m.guardar_plan = lambda cs, sem, nombre, estado, notas, df: (
        guardados.append((sem, nombre, estado, df.copy())) or "pid")
    st.cache_data.clear()
    st.session_state["plan_fecha"] = lunes
    m.render_planificador("cs_lectura", "cs_escritura" if con_escritura else None,
                          cat_fz, cat_rs, "#84CC16")


def _correr(escenario: str, con_escritura: bool = True) -> AppTest:
    builtins._GUARDADOS = []
    at = AppTest.from_function(_app, args=(escenario, REPO, LUNES.isoformat(), con_escritura),
                               default_timeout=60)
    return at.run()


def _kpis(at: AppTest) -> str:
    return " ".join(md.value for md in at.markdown if "cn-kpi-card" in md.value)


def _boton_guardar(at: AppTest):
    return [b for b in at.button if b.label == "Guardar plan"][0]


def test_semana_vacia_muestra_ceros_y_no_deja_guardar():
    at = _correr("vacia")
    assert not at.exception
    assert 'cn-kpi-value">0<' in _kpis(at)
    assert _boton_guardar(at).disabled
    assert [t.label for t in at.tabs if t.label.startswith("MD-")] == ["MD-5", "MD-4", "MD-2"]


def test_plan_guardado_calcula_los_kpis_de_la_semana():
    at = _correr("con_plan")
    assert not at.exception
    html = _kpis(at)
    assert 'cn-kpi-value">33<' in html          # 4x5x0,80 + 3x8x0,70 = 32,8 UA
    assert "120 m" in html                      # 4 pasadas x 30 m
    assert any(t.value == "Semana test" for t in at.text_input)
    assert not at.warning


def test_guardar_envia_los_items_ordenados_por_match_day():
    at = _correr("con_plan")
    _boton_guardar(at).click().run()
    assert not at.exception
    assert len(builtins._GUARDADOS) == 1
    semana, _nombre, _estado, df = builtins._GUARDADOS[0]
    assert semana == LUNES
    assert len(df) == 3
    assert df.groupby("match_day")["orden"].apply(list).to_dict() == {"MD-4": [1], "MD-5": [1, 2]}


def test_sin_credencial_de_escritura_avisa_y_bloquea_el_guardado():
    at = _correr("con_plan", con_escritura=False)
    assert any("fuerza_connection_string" in w.value for w in at.warning)
    assert _boton_guardar(at).disabled
