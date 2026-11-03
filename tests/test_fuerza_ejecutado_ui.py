"""
Pruebas de pantalla de "Sesión ejecutada" e "Historial" (Streamlit AppTest, base simulada).

Se saltean solas si el entorno no tiene streamlit o psycopg. No tocan Supabase ni
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


def _app_ejecutado(escenario: str, repo: str, lunes_iso: str):
    # Se ejecuta DENTRO de AppTest: debe ser autosuficiente (imports propios).
    import builtins
    import sys
    sys.path.insert(0, repo)
    from datetime import date
    import numpy as np
    import pandas as pd
    import streamlit as st
    import src.ui.fuerza_planificador as mp
    import src.ui.fuerza_ejecutado as me
    from src.metrics.fuerza_plan import COLUMNAS_ITEM_PLAN
    from src.metrics.fuerza_ejecutado import COLUMNAS_ITEM_EJECUTADO

    lunes = date.fromisoformat(lunes_iso)
    cat_fz = pd.DataFrame({
        "ejercicio_id": ["FZA-001", "FZA-003"], "ejercicio": ["Sentadilla frontal", "Hip thrust"],
        "categoria": ["a", "b"], "unilateral": [False] * 2, "admite_rm": [True] * 2, "ejercicio_referencia": [""] * 2})
    cat_rs = pd.DataFrame({"ejercicio_id": ["RES-006"], "ejercicio": ["Pasadas"], "categoria": [""]})

    if escenario == "sin_plan":
        planes = pd.DataFrame(columns=["id", "semana_inicio", "nombre", "estado", "notas"])
    else:
        estado = "borrador" if escenario == "borrador" else "publicado"
        planes = pd.DataFrame([{"id": "p1", "semana_inicio": lunes, "nombre": None, "estado": estado, "notas": None}])
    items_plan = pd.DataFrame([
        ["MD-5", 1, "fuerza", "FZA-001", "Sentadilla frontal", 4, 5, 80, np.nan, None, np.nan, 90, None],
        ["MD-5", 2, "fuerza", "FZA-003", "Hip thrust", 3, 8, 70, np.nan, None, np.nan, 90, None],
    ], columns=COLUMNAS_ITEM_PLAN)

    cols_ses = ["id", "fecha", "match_day", "plan_id", "duracion_min", "rpe_sesion", "ya_en_gps", "notas"]
    if escenario == "ya_guardada":
        sesiones = pd.DataFrame([["s1", pd.Timestamp(lunes), "MD-5", "p1", 45.0, 6.0, True, "nota previa"]], columns=cols_ses)
        items_ses = pd.DataFrame([[ "s1", 1, "fuerza", "FZA-001", "Sentadilla frontal", 3, 5, 80, np.nan, None, np.nan, 90, None]],
                                 columns=["sesion_id"] + COLUMNAS_ITEM_EJECUTADO)
    else:
        sesiones = pd.DataFrame(columns=cols_ses)
        sesiones["fecha"] = pd.to_datetime(sesiones["fecha"])
        items_ses = pd.DataFrame(columns=["sesion_id"] + COLUMNAS_ITEM_EJECUTADO)

    mp.listar_planes = lambda cs: planes
    mp.cargar_items_plan = lambda cs, pid: items_plan
    mp.cargar_parametros = lambda cs: {"umbral_alta_intensidad_vmax": 85.0, "intensidad_base_sin_rm": 50.0}
    mp.cargar_zonas_velocidad = lambda cs: pd.DataFrame(columns=["nombre", "orden", "desde_pct_vmax", "hasta_pct_vmax"])
    me.listar_sesiones = lambda cs: sesiones
    me.cargar_items_sesiones = lambda cs, sid=None: items_ses
    if not hasattr(builtins, "_SESIONES_GUARDADAS"):
        builtins._SESIONES_GUARDADAS = []
    guardadas = builtins._SESIONES_GUARDADAS
    me.guardar_sesion = lambda cs, fecha, md, plan_id, dur, rpe, gps, notas, df: (
        guardadas.append(dict(fecha=fecha, md=md, plan_id=plan_id, dur=dur, rpe=rpe, gps=gps, items=df.copy())) or "sid")
    st.cache_data.clear()
    st.session_state["ej_fecha"] = lunes
    me.render_ejecutado("cs_lectura", "cs_escritura", cat_fz, cat_rs, "#84CC16")


def _app_historial(escenario: str, repo: str):
    import sys
    sys.path.insert(0, repo)
    from datetime import date, timedelta
    import numpy as np
    import pandas as pd
    import streamlit as st
    import src.ui.fuerza_planificador as mp
    import src.ui.fuerza_ejecutado as me
    from src.metrics.fuerza_plan import COLUMNAS_ITEM_PLAN
    from src.metrics.fuerza_ejecutado import COLUMNAS_ITEM_EJECUTADO

    hoy = date.today()
    lunes = hoy - timedelta(days=hoy.weekday())
    cols_ses = ["id", "fecha", "match_day", "plan_id", "duracion_min", "rpe_sesion", "ya_en_gps", "notas"]
    if escenario == "vacio":
        sesiones = pd.DataFrame(columns=cols_ses)
        sesiones["fecha"] = pd.to_datetime(sesiones["fecha"])
    else:
        sesiones = pd.DataFrame([
            ["s1", pd.Timestamp(hoy - timedelta(days=10)), "MD-5", "p1", 60.0, 7.0, False, None],
            ["s2", pd.Timestamp(hoy - timedelta(days=3)), "MD-4", None, 45.0, np.nan, True, None],
        ], columns=cols_ses)
    items_ses = pd.DataFrame([
        ["s1", 1, "fuerza", "FZA-001", "Sentadilla frontal", 4, 5, 80, np.nan, None, np.nan, 90, None],
        ["s2", 1, "pasada", "RES-006", "Pasadas", np.nan, 4, np.nan, 30, "Z4", 90, 120, None],
    ], columns=["sesion_id"] + COLUMNAS_ITEM_EJECUTADO)
    planes = pd.DataFrame([{"id": "p1", "semana_inicio": lunes - timedelta(days=7), "nombre": None, "estado": "publicado", "notas": None}])
    items_plan = pd.DataFrame([["p1", "MD-5", 1, "fuerza", "FZA-001", "Sentadilla frontal", 4, 5, 80, np.nan, None, np.nan, 90, None]],
                              columns=["plan_id"] + COLUMNAS_ITEM_PLAN)

    mp.listar_planes = lambda cs: planes
    mp.cargar_parametros = lambda cs: {"umbral_alta_intensidad_vmax": 85.0, "intensidad_base_sin_rm": 50.0}
    me.listar_sesiones = lambda cs: sesiones
    me.cargar_items_sesiones = lambda cs, sid=None: items_ses
    me.cargar_todos_items_plan = lambda cs: items_plan
    st.cache_data.clear()
    me.render_historial("cs_lectura", "#84CC16")


def _correr_ej(escenario: str) -> AppTest:
    builtins._SESIONES_GUARDADAS = []
    return AppTest.from_function(_app_ejecutado, args=(escenario, REPO, LUNES.isoformat()), default_timeout=60).run()


def _correr_hist(escenario: str) -> AppTest:
    return AppTest.from_function(_app_historial, args=(escenario, REPO), default_timeout=60).run()


def _kpis(at: AppTest) -> str:
    return " ".join(md.value for md in at.markdown if "cn-kpi-card" in md.value)


def _boton(at: AppTest, texto: str):
    return [b for b in at.button if b.label == texto][0]


def _textos(at: AppTest) -> str:
    return " ".join([e.value for e in at.success] + [e.value for e in at.info] + [e.value for e in at.warning])


# ── Sesión ejecutada ─────────────────────────────────────────────────────────

def test_ejecutado_se_precarga_desde_el_plan_y_cumple_al_cien():
    at = _correr_ej("con_plan")
    assert not at.exception
    assert "Precargado desde el plan" in _textos(at)
    html = _kpis(at)
    assert 'cn-kpi-value">33<' in html      # 16 + 16,8 UA
    assert "100 %" in html                  # igual a lo planificado


def test_ejecutado_avisa_si_el_plan_esta_en_borrador():
    at = _correr_ej("borrador")
    assert any("borrador" in w.value for w in at.warning)


def test_ejecutado_sin_plan_deja_cargar_a_mano_pero_no_guardar_vacio():
    at = _correr_ej("sin_plan")
    assert not at.exception
    assert "No hay un plan cargado" in _textos(at)
    assert _boton(at, "Guardar sesión").disabled


def test_ejecutado_guardar_envia_plan_id_md_y_items():
    at = _correr_ej("con_plan")
    at.number_input[0].set_value(60)        # duración
    at.number_input[1].set_value(7.0)       # RPE
    at.run()
    assert "420" in _kpis(at)               # sRPE = 60 x 7
    _boton(at, "Guardar sesión").click().run()
    assert not at.exception
    assert len(builtins._SESIONES_GUARDADAS) == 1
    g = builtins._SESIONES_GUARDADAS[0]
    assert (g["fecha"], g["md"], g["plan_id"], g["dur"], g["rpe"], g["gps"]) == (LUNES, "MD-5", "p1", 60, 7.0, False)
    assert list(g["items"]["ejercicio_id"]) == ["FZA-001", "FZA-003"]
    assert list(g["items"]["series_hechas"]) == [4, 3]


def test_ejecutado_sesion_ya_guardada_se_carga_para_corregir():
    at = _correr_ej("ya_guardada")
    assert not at.exception
    assert "Ya hay una sesión cargada" in _textos(at)
    assert 'cn-kpi-value">12<' in _kpis(at)     # 3 x 5 x 0,80, no los 33 del plan
    assert at.number_input[0].value == 45
    assert at.checkbox[0].value is True         # "ya está en el GPS"


# ── Historial ────────────────────────────────────────────────────────────────

def test_historial_vacio_invita_a_cargar_la_primera_sesion():
    at = _correr_hist("vacio")
    assert not at.exception
    assert any("Todavía no hay sesiones ejecutadas" in i.value for i in at.info)


def test_historial_con_sesiones_muestra_kpis_acwr_provisorio_y_detalle():
    at = _correr_hist("con_sesiones")
    assert not at.exception
    html = _kpis(at)
    assert 'cn-kpi-value">2<' in html                    # sesiones registradas
    # Las pasadas de s2 (120 m) están marcadas "ya en el GPS": no deben sumar como metros fuera del GPS.
    assert 'cn-kpi-value">0 m<' in html
    assert any("provisorio" in c.value.lower() for c in at.caption)
    assert len(list(at.get("dataframe"))) == 1           # tabla de detalle
