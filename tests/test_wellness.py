import numpy as np
import pandas as pd
import pytest

from src.metrics.wellness import (
    calcular_readiness,
    _clasificar_readiness,
    calcular_tendencia_tqr,
    generar_alertas,
    resumen_alertas_equipo,
)


# ── calcular_readiness ───────────────────────────────────────────────────────

def test_readiness_clip_respeta_rango_1_10():
    df = pd.DataFrame({"tqr": [15, -2, 5]})
    resultado = calcular_readiness(df)
    assert resultado["readiness_index"].tolist() == [10, 1, 5]


@pytest.mark.parametrize("valor,zona_esperada", [
    (10, "Totalmente Apta"),
    (8, "Totalmente Apta"),
    (7.99, "Apta Moderado"),
    (6, "Apta Moderado"),
    (5.99, "Precaución"),
    (4, "Precaución"),
    (3.99, "No Apta"),
    (1, "No Apta"),
    (np.nan, "Sin datos"),
])
def test_clasificar_readiness_limites(valor, zona_esperada):
    assert _clasificar_readiness(valor) == zona_esperada


# ── calcular_tendencia_tqr ───────────────────────────────────────────────────

def test_tendencia_tqr_valores_conocidos():
    # ventana=3, min_periods=2: rolling mean = [NaN, 5.5, 6.0, 7.0, 8.0]
    # diff()                   = [NaN, NaN, 0.5, 1.0, 1.0]
    df = pd.DataFrame({
        "player_id": ["J1"] * 5,
        "fecha": pd.date_range("2026-01-01", periods=5, freq="D"),
        "tqr": [5, 6, 7, 8, 9],
    })
    resultado = calcular_tendencia_tqr(df, ventana=3)
    assert resultado["tqr_tend"].iloc[:2].isna().all()
    assert resultado["tqr_tend"].iloc[2:].tolist() == pytest.approx([0.5, 1.0, 1.0])


def test_tendencia_tqr_no_mezcla_jugadoras():
    df = pd.DataFrame({
        "player_id": ["J1", "J1", "J1", "J2", "J2", "J2"],
        "fecha": list(pd.date_range("2026-01-01", periods=3, freq="D")) * 2,
        "tqr": [5, 5, 5, 9, 1, 9],
    })
    resultado = calcular_tendencia_tqr(df, ventana=3)
    # J1 sin variación: tendencia final debe ser 0, no contaminada por J2
    tend_j1_final = resultado.loc[resultado["player_id"] == "J1", "tqr_tend"].iloc[-1]
    assert tend_j1_final == pytest.approx(0.0)


# ── generar_alertas ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("tqr,rpe,esperado_tqr_bajo,esperado_rpe_alto", [
    (5.0, 8.0, False, False),   # justo en el límite, no dispara (umbral estricto)
    (4.9, 8.0, True, False),
    (5.0, 8.1, False, True),
    (4.9, 8.1, True, True),
])
def test_generar_alertas_limites_estrictos(tqr, rpe, esperado_tqr_bajo, esperado_rpe_alto):
    df = pd.DataFrame({"tqr": [tqr], "rpe": [rpe]})
    resultado = generar_alertas(df)
    assert bool(resultado["alerta_tqr_bajo"].iloc[0]) == esperado_tqr_bajo
    assert bool(resultado["alerta_rpe_alto"].iloc[0]) == esperado_rpe_alto
    assert bool(resultado["alerta_combinada"].iloc[0]) == (esperado_tqr_bajo and esperado_rpe_alto)


def test_generar_alertas_readiness_y_molestia_son_opcionales():
    df_sin_extra = pd.DataFrame({"tqr": [7], "rpe": [5]})
    resultado = generar_alertas(df_sin_extra)
    assert "alerta_readiness" not in resultado.columns
    assert "alerta_molestia" not in resultado.columns

    df_con_extra = pd.DataFrame({
        "tqr": [7], "rpe": [5],
        "readiness_index": [3], "molestia_flag": [True],
    })
    resultado = generar_alertas(df_con_extra)
    assert resultado["alerta_readiness"].iloc[0] == True
    assert resultado["alerta_molestia"].iloc[0] == True


# ── resumen_alertas_equipo ───────────────────────────────────────────────────

def test_resumen_alertas_vacio_sin_columnas_alerta():
    df = pd.DataFrame({"player_id": ["J1"], "fecha": ["2026-01-01"], "tqr": [5]})
    resultado = resumen_alertas_equipo(df)
    assert resultado.empty


def test_resumen_alertas_solo_incluye_jugadoras_con_alertas():
    df = pd.DataFrame({
        "player_id": ["J1", "J2"],
        "nombre": ["Jugadora Uno", "Jugadora Dos"],
        "fecha": ["2026-01-01", "2026-01-01"],
        "tqr": [4, 7], "rpe": [5, 5],
        "readiness_index": [4, 8], "readiness_zona": ["Precaución", "Totalmente Apta"],
        "alerta_tqr_bajo": [True, False],
        "alerta_rpe_alto": [False, False],
    })
    resultado = resumen_alertas_equipo(df)
    assert resultado["player_id"].tolist() == ["J1"]
    assert resultado["total_alertas"].iloc[0] == 1


def test_resumen_alertas_usa_el_ultimo_registro_por_jugadora():
    # J1 tenía alerta el día 1 pero no el día 2 (más reciente) — debe
    # reflejar el estado actual, no un historial viejo.
    df = pd.DataFrame({
        "player_id": ["J1", "J1"],
        "nombre": ["Jugadora Uno", "Jugadora Uno"],
        "fecha": ["2026-01-01", "2026-01-02"],
        "tqr": [3, 7], "rpe": [9, 5],
        "readiness_index": [3, 8], "readiness_zona": ["No Apta", "Totalmente Apta"],
        "alerta_tqr_bajo": [True, False],
        "alerta_rpe_alto": [True, False],
    })
    resultado = resumen_alertas_equipo(df)
    assert resultado.empty  # el último registro (día 2) no tiene alertas activas


def test_resumen_alertas_ordena_por_total_descendente():
    df = pd.DataFrame({
        "player_id": ["J1", "J2"],
        "nombre": ["Jugadora Uno", "Jugadora Dos"],
        "fecha": ["2026-01-01", "2026-01-01"],
        "tqr": [4, 4], "rpe": [9, 9],
        "readiness_index": [4, 4], "readiness_zona": ["Precaución", "Precaución"],
        "alerta_tqr_bajo": [True, True],
        "alerta_rpe_alto": [False, True],
    })
    resultado = resumen_alertas_equipo(df)
    assert resultado["player_id"].tolist() == ["J2", "J1"]
