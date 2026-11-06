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


def _app(escenario: str, repo: str, lunes_iso: str, con_escritura: bool, con_gps: bool = False):
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
            ["MD-5", 1, "fuerza", "FZA-001", "Sentadilla frontal", 4, 5, 80, np.nan, None, np.nan, 90, None, None],
            ["MD-5", 2, "fuerza", "FZA-003", "Hip thrust", 3, 8, 70, np.nan, None, np.nan, 90, None, None],
            ["MD-4", 1, "pasada", "RES-006", "Pasadas", np.nan, 4, np.nan, 30, "Z4", 90, 120, None, None],
        ], columns=COLUMNAS_ITEM_PLAN)
    else:
        planes = pd.DataFrame(columns=["id", "semana_inicio", "nombre", "estado", "notas"])
        items = pd.DataFrame(columns=COLUMNAS_ITEM_PLAN)

    m.listar_planes = lambda cs: planes
    m.cargar_items_plan = lambda cs, pid: items
    m.cargar_parametros = lambda cs: dict(__import__("src.metrics.fuerza_plan", fromlist=["x"]).PARAMETROS_DEFAULT)
    m.cargar_zonas_velocidad = lambda cs: pd.DataFrame(
        columns=["nombre", "orden", "desde_pct_vmax", "hasta_pct_vmax"])
    if not hasattr(builtins, "_GUARDADOS"):
        builtins._GUARDADOS = []
    guardados = builtins._GUARDADOS
    m.guardar_plan = lambda cs, sem, nombre, estado, notas, df: (
        guardados.append((sem, nombre, estado, df.copy())) or "pid")
    if not hasattr(builtins, "_PARAMS"):
        builtins._PARAMS = []
    params_guardados = builtins._PARAMS
    m.guardar_parametros = lambda cs, valores: params_guardados.append(dict(valores))
    gps = None
    if con_gps:
        gps = pd.DataFrame({
            "player_id": ["a"] * 3 + ["b"] * 3, "nombre": ["Ana"] * 3 + ["Bea"] * 3,
            "fecha": pd.to_datetime(["2026-10-01", "2026-10-08", "2026-10-15"] * 2),
            "vel_max_kmh": [27.0, 26.0, 25.0, 24.0, 23.0, 22.0]})
    st.cache_data.clear()
    if "plan_fecha" not in st.session_state:   # solo la 1ª corrida: los tests pueden cambiar el día
        st.session_state["plan_fecha"] = lunes
    m.render_planificador("cs_lectura", "cs_escritura" if con_escritura else None,
                          cat_fz, cat_rs, "#84CC16", df_gps=gps)


def _correr(escenario: str, con_escritura: bool = True, con_gps: bool = False) -> AppTest:
    builtins._GUARDADOS = []
    builtins._PARAMS = []
    at = AppTest.from_function(_app, args=(escenario, REPO, LUNES.isoformat(), con_escritura, con_gps),
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


def test_con_gps_aparecen_tiempos_objetivo_y_tabla_de_vmax():
    at = _correr("con_plan", con_gps=True)
    assert not at.exception
    etiquetas = [e.label for e in at.expander]
    assert "Tiempos objetivo por jugadora" in etiquetas
    assert "Vmáx por jugadora (desde el GPS)" in etiquetas
    # Ana: Vmáx 26 (promedio 27, 26, 25); 30 m al 90 %: 30 / (26/3,6 * 0,9 * 0,82) = 5,63 s
    tablas = [d.value for d in at.dataframe]
    tiempos = [d for d in tablas if "Vmáx (km/h)" in d.columns and "Jugadora" in d.columns]
    assert tiempos and tiempos[0].loc[tiempos[0]["Jugadora"] == "Ana", "30 m al 90 %"].iloc[0] == pytest.approx(5.63, abs=0.01)


def test_sin_gps_avisa_que_no_hay_vmax():
    at = _correr("con_plan", con_gps=False)
    assert not at.exception
    assert any("No hay datos de GPS" in i.value for i in at.info)


def test_guardar_parametros_envia_umbral_factores_y_criterio_vmax():
    at = _correr("con_plan")
    [b for b in at.button if b.label == "Guardar parámetros"][0].click().run()
    assert not at.exception
    assert len(builtins._PARAMS) == 1
    valores = builtins._PARAMS[0]
    assert valores["umbral_alta_intensidad_vmax"] == 85.0
    assert valores["factor_pasada_30"] == 0.82 and valores["factor_pasada_70"] == 0.91
    assert valores["vmax_top_n"] == 3 and valores["vmax_tope_kmh"] == 35.0


# ── la pestaña de Match Day sigue al día elegido ─────────────────────────────

def _elegir_dia(at: AppTest, fecha: date) -> AppTest:
    [d for d in at.date_input if d.key == "plan_fecha"][0].set_value(fecha)
    return at.run()


def test_lunes_abre_md5_martes_md4_jueves_md2():
    at = _correr("vacia")                      # arranca en el lunes de esta semana
    assert at.session_state["plan_tabs_md"] == "MD-5"
    assert _elegir_dia(at, LUNES + timedelta(days=1)).session_state["plan_tabs_md"] == "MD-4"
    assert _elegir_dia(at, LUNES + timedelta(days=3)).session_state["plan_tabs_md"] == "MD-2"
    assert _elegir_dia(at, LUNES).session_state["plan_tabs_md"] == "MD-5"


def test_dia_sin_entrenamiento_no_cambia_la_pestana():
    at = _elegir_dia(_correr("vacia"), LUNES + timedelta(days=3))     # MD-2
    assert _elegir_dia(at, LUNES + timedelta(days=2)).session_state["plan_tabs_md"] == "MD-2"   # miércoles


def test_elegir_una_pestana_a_mano_se_respeta_mientras_no_cambie_el_dia():
    at = _correr("vacia")
    at.session_state["plan_tabs_md"] = "MD-2"
    at.run()
    assert not at.exception
    assert at.session_state["plan_tabs_md"] == "MD-2"
