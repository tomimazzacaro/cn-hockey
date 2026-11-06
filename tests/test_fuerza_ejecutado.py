import numpy as np
import pandas as pd
import pytest

from src.metrics.fuerza_ejecutado import (
    plan_a_ejecutado, ejecutado_a_plan, resumir_items_ejecutados, resumen_sesiones,
    cumplimiento_vs_plan, resumen_semanal, serie_diaria_ua, acwr_fuerza,
)
from src.metrics.fuerza_plan import COLUMNAS_ITEM_PLAN


def _items_ej(sesion_id, filas):
    cols = ["sesion_id", "tipo", "series_hechas", "reps_hechas", "pct_rm_real", "distancia_m", "pct_vmax"]
    return pd.DataFrame([[sesion_id, *f] for f in filas], columns=cols)


def _sesiones(filas):
    cols = ["id", "fecha", "match_day", "plan_id", "duracion_min", "rpe_sesion", "ya_en_gps"]
    return pd.DataFrame(filas, columns=cols)


def _items_plan(filas):
    cols = ["plan_id", "match_day", "tipo", "series", "repeticiones", "pct_rm", "distancia_m", "pct_vmax"]
    return pd.DataFrame(filas, columns=cols)


# ── conversión plan <-> ejecutado ────────────────────────────────────────────

def test_plan_a_ejecutado_renombra_las_tres_columnas():
    plan = pd.DataFrame([["MD-5", 1, "fuerza", "FZA-001", "Sentadilla", 4, 5, 80, np.nan, None, np.nan, 90, None, None]],
                        columns=COLUMNAS_ITEM_PLAN)
    ej = plan_a_ejecutado(plan)
    assert ej.loc[0, "series_hechas"] == 4 and ej.loc[0, "reps_hechas"] == 5 and ej.loc[0, "pct_rm_real"] == 80
    assert "series" not in ej.columns


def test_ida_y_vuelta_plan_ejecutado_conserva_los_valores():
    plan = pd.DataFrame([["MD-5", 1, "fuerza", "FZA-001", "Sentadilla", 4, 5, 80, np.nan, None, np.nan, 90, None, None]],
                        columns=COLUMNAS_ITEM_PLAN)
    pd.testing.assert_frame_equal(ejecutado_a_plan(plan_a_ejecutado(plan)), plan)


# ── resumen de una sesión ────────────────────────────────────────────────────

def test_resumir_items_ejecutados_ua_y_metros():
    items = _items_ej("s1", [
        ["fuerza", 4, 5, 80, np.nan, np.nan],     # 16 UA
        ["fuerza", 3, 10, np.nan, np.nan, np.nan],  # sin %RM -> base 50 % = 15 UA
        ["pasada", np.nan, 4, np.nan, 30, 90],    # 120 m, alta intensidad
    ])
    r = resumir_items_ejecutados(items)
    assert r["ua_fuerza"] == pytest.approx(31.0)
    assert r["metros_pasadas"] == pytest.approx(120.0)
    assert r["metros_alta_intensidad"] == pytest.approx(120.0)


def test_resumir_items_ejecutados_vacio_es_cero():
    assert resumir_items_ejecutados(pd.DataFrame())["ua_fuerza"] == 0.0


# ── resumen por sesión ───────────────────────────────────────────────────────

def test_resumen_sesiones_srpe_y_marca_gps():
    ses = _sesiones([
        ["s1", "2026-11-02", "MD-5", None, 60, 7, False],
        ["s2", "2026-11-04", "MD-4", None, 45, np.nan, True],
    ])
    items = pd.concat([
        _items_ej("s1", [["pasada", np.nan, 4, np.nan, 30, 90]]),
        _items_ej("s2", [["pasada", np.nan, 4, np.nan, 30, 90]]),
    ])
    out = resumen_sesiones(ses, items).set_index("id")
    assert out.loc["s1", "srpe"] == pytest.approx(420)
    assert np.isnan(out.loc["s2", "srpe"])                       # sin RPE no hay sRPE
    assert out.loc["s1", "metros_pasadas_fuera_gps"] == pytest.approx(120)
    assert out.loc["s2", "metros_pasadas_fuera_gps"] == 0        # ya está en el GPS
    assert out.loc["s2", "metros_pasadas"] == pytest.approx(120)  # igual se registra


def test_resumen_sesiones_ordena_por_fecha_y_tolera_vacio():
    ses = _sesiones([["b", "2026-11-04", "MD-4", None, None, None, False],
                     ["a", "2026-11-02", "MD-5", None, None, None, False]])
    out = resumen_sesiones(ses, pd.DataFrame())
    assert list(out["id"]) == ["a", "b"]
    assert resumen_sesiones(pd.DataFrame(), pd.DataFrame()).empty


# ── cumplimiento vs plan ─────────────────────────────────────────────────────

def test_cumplimiento_compara_contra_el_plan_del_mismo_md():
    ses = _sesiones([["s1", "2026-11-02", "MD-5", "p1", 60, 7, False]])
    resumen = resumen_sesiones(ses, _items_ej("s1", [["fuerza", 4, 4, 80, np.nan, np.nan]]))  # 12,8 UA
    plan = _items_plan([["p1", "MD-5", "fuerza", 4, 5, 80, np.nan, np.nan],     # 16 UA
                        ["p1", "MD-4", "fuerza", 9, 9, 99, np.nan, np.nan]])    # otro MD: no cuenta
    out = cumplimiento_vs_plan(resumen, plan)
    assert out.loc[0, "ua_planificada"] == pytest.approx(16.0)
    assert out.loc[0, "cumplimiento_ua"] == pytest.approx(80.0)


def test_cumplimiento_sin_plan_queda_vacio():
    ses = _sesiones([["s1", "2026-11-02", "MD-5", None, 60, 7, False]])
    resumen = resumen_sesiones(ses, _items_ej("s1", [["fuerza", 4, 5, 80, np.nan, np.nan]]))
    out = cumplimiento_vs_plan(resumen, _items_plan([["p1", "MD-5", "fuerza", 4, 5, 80, np.nan, np.nan]]))
    assert np.isnan(out.loc[0, "cumplimiento_ua"])


# ── resumen semanal ──────────────────────────────────────────────────────────

def test_resumen_semanal_cuenta_lo_planificado_aunque_no_se_haya_hecho():
    planes = pd.DataFrame([{"id": "p1", "semana_inicio": "2026-11-02"}])
    plan = _items_plan([["p1", "MD-5", "fuerza", 4, 5, 80, np.nan, np.nan],    # 16
                        ["p1", "MD-2", "fuerza", 4, 5, 80, np.nan, np.nan]])   # 16 (no se hizo)
    ses = _sesiones([["s1", "2026-11-03", "MD-5", "p1", 60, 7, False]])
    resumen = resumen_sesiones(ses, _items_ej("s1", [["fuerza", 4, 5, 80, np.nan, np.nan]]))
    out = resumen_semanal(resumen, planes, plan)
    assert len(out) == 1
    assert out.loc[0, "ua_planificada"] == pytest.approx(32.0)
    assert out.loc[0, "ua_ejecutada"] == pytest.approx(16.0)
    assert out.loc[0, "cumplimiento_ua"] == pytest.approx(50.0)
    assert out.loc[0, "semana"] == pd.Timestamp("2026-11-02")     # lunes


def test_resumen_semanal_semana_sin_plan_tiene_cumplimiento_vacio():
    ses = _sesiones([["s1", "2026-11-03", "MD-5", None, 60, 7, False]])
    resumen = resumen_sesiones(ses, _items_ej("s1", [["fuerza", 4, 5, 80, np.nan, np.nan]]))
    out = resumen_semanal(resumen, pd.DataFrame(columns=["id", "semana_inicio"]), pd.DataFrame())
    assert out.loc[0, "ua_ejecutada"] == pytest.approx(16.0)
    assert np.isnan(out.loc[0, "cumplimiento_ua"])


def test_resumen_semanal_todo_vacio():
    assert resumen_semanal(pd.DataFrame(), pd.DataFrame(), pd.DataFrame()).empty


# ── serie diaria y ACWR ──────────────────────────────────────────────────────

def _resumen_ua(pares):
    return pd.DataFrame({"fecha": [pd.Timestamp(f) for f, _ in pares], "ua_fuerza": [u for _, u in pares]})


def test_serie_diaria_rellena_con_cero_los_dias_sin_sesion():
    out = serie_diaria_ua(_resumen_ua([("2026-11-02", 30), ("2026-11-05", 20)]))
    assert list(out["ua_fuerza"]) == [30, 0, 0, 20]
    assert out["fecha"].iloc[0] == pd.Timestamp("2026-11-02")


def test_serie_diaria_suma_sesiones_del_mismo_dia():
    out = serie_diaria_ua(_resumen_ua([("2026-11-02", 30), ("2026-11-02", 10)]))
    assert list(out["ua_fuerza"]) == [40]


def test_serie_diaria_hasta_extiende_con_ceros():
    out = serie_diaria_ua(_resumen_ua([("2026-11-02", 30)]), hasta="2026-11-05")
    assert len(out) == 4 and out["ua_fuerza"].iloc[-1] == 0


def test_serie_diaria_vacia():
    assert serie_diaria_ua(pd.DataFrame()).empty


def test_acwr_carga_constante_converge_a_uno():
    dias = pd.date_range("2026-01-01", periods=60, freq="D")
    out = acwr_fuerza(pd.DataFrame({"fecha": dias, "ua_fuerza": 30.0}))
    assert out["acwr"].iloc[-1] == pytest.approx(1.0, abs=0.01)
    assert out["zona_acwr"].iloc[-1] == "Óptimo"


def test_acwr_un_pico_despues_de_carga_baja_sube_por_encima_de_uno():
    carga = [10.0] * 40 + [60.0] * 4
    out = acwr_fuerza(pd.DataFrame({"fecha": pd.date_range("2026-01-01", periods=44, freq="D"), "ua_fuerza": carga}))
    assert out["acwr"].iloc[-1] > 1.3


def test_acwr_marca_historia_insuficiente_antes_de_28_dias():
    dias = pd.date_range("2026-01-01", periods=40, freq="D")
    out = acwr_fuerza(pd.DataFrame({"fecha": dias, "ua_fuerza": 30.0}))
    assert not out["historia_suficiente"].iloc[26]
    assert out["historia_suficiente"].iloc[27]
    assert out["dias_historia"].iloc[0] == 1


def test_acwr_descanso_largo_baja_la_carga_aguda_mas_que_la_cronica():
    carga = [30.0] * 30 + [0.0] * 10
    out = acwr_fuerza(pd.DataFrame({"fecha": pd.date_range("2026-01-01", periods=40, freq="D"), "ua_fuerza": carga}))
    assert out["acwr"].iloc[-1] < 0.8
    assert out["zona_acwr"].iloc[-1] == "Subcarga"


def test_acwr_vacio_no_rompe():
    out = acwr_fuerza(pd.DataFrame(columns=["fecha", "ua_fuerza"]))
    assert out.empty and "acwr" in out.columns
