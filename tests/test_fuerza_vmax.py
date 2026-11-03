import numpy as np
import pandas as pd
import pytest

from src.metrics.fuerza_vmax import (
    factores_desde_parametros, factor_para_distancia, distancia_fuera_de_rango,
    calcular_vmax_jugadoras, tiempos_objetivo_jugadoras,
)
from src.metrics.fuerza_plan import tiempo_objetivo_pasada

FACTORES = {30: 0.82, 40: 0.86, 50: 0.88, 60: 0.90, 70: 0.91}


def _gps(filas):
    return pd.DataFrame(filas, columns=["player_id", "nombre", "fecha", "vel_max_kmh"])


# ── factores ─────────────────────────────────────────────────────────────────

def test_factores_por_defecto_vienen_de_los_parametros():
    assert factores_desde_parametros() == FACTORES


def test_factores_editados_pisan_el_default():
    f = factores_desde_parametros({"factor_pasada_30": 0.75})
    assert f[30] == 0.75 and f[40] == 0.86


def test_factor_interpola_entre_distancias():
    assert factor_para_distancia(35, FACTORES) == pytest.approx(0.84)
    assert factor_para_distancia(30, FACTORES) == pytest.approx(0.82)


def test_factor_fuera_de_rango_usa_el_extremo_y_lo_marca():
    assert factor_para_distancia(20, FACTORES) == pytest.approx(0.82)
    assert factor_para_distancia(100, FACTORES) == pytest.approx(0.91)
    assert distancia_fuera_de_rango(20, FACTORES) and distancia_fuera_de_rango(100, FACTORES)
    assert not distancia_fuera_de_rango(45, FACTORES)


def test_factor_sin_factores_falla_claro():
    with pytest.raises(ValueError):
        factor_para_distancia(30, {})


# ── Vmáx por jugadora ────────────────────────────────────────────────────────

def test_vmax_es_el_promedio_de_los_mejores_dias():
    df = _gps([["a", "Ana", "2026-10-01", 26.0], ["a", "Ana", "2026-10-02", 28.0],
               ["a", "Ana", "2026-10-03", 27.0], ["a", "Ana", "2026-10-04", 20.0]])
    out = calcular_vmax_jugadoras(df, top_n=3).iloc[0]
    assert out["vmax_kmh"] == pytest.approx(27.0)       # (28 + 27 + 26) / 3
    assert out["n_dias"] == 3


def test_vmax_toma_el_maximo_de_cada_dia_antes_de_promediar():
    # Dos cuartos el mismo día cuentan como UN día, no como dos.
    df = _gps([["a", "Ana", "2026-10-01", 25.0], ["a", "Ana", "2026-10-01", 28.0],
               ["a", "Ana", "2026-10-02", 24.0]])
    out = calcular_vmax_jugadoras(df, top_n=3).iloc[0]
    assert out["n_dias"] == 2
    assert out["vmax_kmh"] == pytest.approx(26.0)       # (28 + 24) / 2


def test_vmax_descarta_valores_imposibles_del_chaleco_y_los_cuenta():
    df = _gps([["a", "Ana", "2026-10-01", 51.0], ["a", "Ana", "2026-10-02", 27.0],
               ["a", "Ana", "2026-10-03", 26.0]])
    out = calcular_vmax_jugadoras(df, top_n=3, tope_kmh=35).iloc[0]
    assert out["vmax_kmh"] == pytest.approx(26.5)
    assert out["valores_descartados"] == 1


def test_vmax_respeta_la_ventana_desde_el_ultimo_dato():
    df = _gps([["a", "Ana", "2026-01-01", 30.0], ["a", "Ana", "2026-10-01", 25.0]])
    out = calcular_vmax_jugadoras(df, top_n=3, ventana_dias=180).iloc[0]
    assert out["vmax_kmh"] == pytest.approx(25.0)       # el dato de enero queda afuera


def test_vmax_jugadora_sin_datos_validos_queda_vacia_pero_listada():
    df = _gps([["a", "Ana", "2026-10-01", 27.0], ["b", "Bea", "2026-10-01", 60.0]])
    out = calcular_vmax_jugadoras(df).set_index("player_id")
    assert np.isnan(out.loc["b", "vmax_kmh"]) and out.loc["b", "n_dias"] == 0
    assert out.loc["a", "vmax_kmh"] == pytest.approx(27.0)


def test_vmax_vacio():
    assert calcular_vmax_jugadoras(pd.DataFrame()).empty


# ── tiempos objetivo ─────────────────────────────────────────────────────────

def test_tiempos_objetivo_coinciden_con_la_formula_con_factor():
    vmax = pd.DataFrame({"nombre": ["Ana"], "vmax_kmh": [27.0]})
    pasadas = pd.DataFrame({"distancia_m": [30.0], "pct_vmax": [100.0]})
    out = tiempos_objetivo_jugadoras(vmax, pasadas, FACTORES)
    esperado = tiempo_objetivo_pasada(30, 27, 100, factor_distancia=0.82)   # 4,0 / 0,82
    assert out.loc[0, "30 m al 100 %"] == pytest.approx(round(esperado, 2))
    assert out.loc[0, "30 m al 100 %"] > 4.0        # con factor, más lento que la fórmula sin corregir


def test_tiempos_objetivo_sin_vmax_queda_vacio_y_sin_pct_se_omite():
    vmax = pd.DataFrame({"nombre": ["Ana", "Bea"], "vmax_kmh": [27.0, np.nan]})
    pasadas = pd.DataFrame({"distancia_m": [30.0, 40.0], "pct_vmax": [90.0, np.nan]})
    out = tiempos_objetivo_jugadoras(vmax, pasadas, FACTORES)
    assert list(out.columns) == ["Jugadora", "Vmáx (km/h)", "30 m al 90 %"]   # la de 40 m sin %Vmáx no está
    assert np.isnan(out.loc[1, "30 m al 90 %"])


def test_tiempos_objetivo_sin_pasadas_devuelve_solo_la_base():
    vmax = pd.DataFrame({"nombre": ["Ana"], "vmax_kmh": [27.0]})
    assert list(tiempos_objetivo_jugadoras(vmax, pd.DataFrame(), FACTORES).columns) == ["Jugadora", "Vmáx (km/h)"]


def test_a_mayor_porcentaje_menor_tiempo():
    vmax = pd.DataFrame({"nombre": ["Ana"], "vmax_kmh": [27.0]})
    pasadas = pd.DataFrame({"distancia_m": [30.0, 30.0], "pct_vmax": [80.0, 95.0]})
    out = tiempos_objetivo_jugadoras(vmax, pasadas, FACTORES)
    assert out.loc[0, "30 m al 95 %"] < out.loc[0, "30 m al 80 %"]
