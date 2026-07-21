import numpy as np
import pandas as pd
import pytest

from src.metrics.physical import (
    calcular_ewma,
    calcular_acwr,
    _clasificar_zona_acwr,
    calcular_srpe,
    calcular_intensidad_relativa,
    agregar_partidos_completos,
    resumen_carga_equipo,
)


# ── calcular_ewma ────────────────────────────────────────────────────────────

def test_ewma_serie_constante_se_mantiene_constante():
    serie = pd.Series([50.0] * 10)
    resultado = calcular_ewma(serie, dias=7)
    assert (resultado == 50.0).all()


def test_ewma_valor_conocido_span_7():
    # adjust=False: y0=x0 ; y1=(1-alpha)*y0 + alpha*x1, alpha=2/(7+1)=0.25
    serie = pd.Series([10.0, 20.0])
    resultado = calcular_ewma(serie, dias=7)
    assert resultado.iloc[0] == pytest.approx(10.0)
    assert resultado.iloc[1] == pytest.approx(12.5)


# ── _clasificar_zona_acwr ────────────────────────────────────────────────────

@pytest.mark.parametrize("valor,zona_esperada", [
    (0.79, "Subcarga"),
    (0.8, "Óptimo"),
    (1.3, "Óptimo"),
    (1.31, "Precaución"),
    (1.5, "Precaución"),
    (1.51, "Riesgo Alto"),
    (np.nan, "Sin datos"),
])
def test_clasificar_zona_acwr_limites(valor, zona_esperada):
    assert _clasificar_zona_acwr(valor) == zona_esperada


# ── calcular_acwr ────────────────────────────────────────────────────────────

def _df_carga_constante(player_id: str, carga: float, dias: int, fecha_inicio="2026-01-01"):
    fechas = pd.date_range(fecha_inicio, periods=dias, freq="D")
    return pd.DataFrame({
        "player_id": player_id,
        "fecha": fechas,
        "player_load": carga,
    })


def test_acwr_con_carga_constante_es_uno():
    df = _df_carga_constante("J1", carga=100.0, dias=30)
    resultado = calcular_acwr(df, col_carga="player_load")
    # Con carga constante, EWMA aguda y crónica son idénticas desde el día 1
    # (adjust=False arranca en y0=x0), así que el ACWR debe ser exactamente 1.0.
    assert (resultado["acwr"] == 1.0).all()
    assert (resultado["zona_acwr"] == "Óptimo").all()


def test_acwr_suma_carga_del_mismo_dia_antes_del_ewma():
    # Dos filas el mismo día (ej: 2 cuartos de partido) deben sumarse a nivel
    # día antes de calcular el EWMA — si no, la ventana de 7/28 días queda
    # distorsionada tratando cada fila como un paso de tiempo independiente.
    df = pd.DataFrame({
        "player_id": ["J1", "J1"],
        "fecha": ["2026-01-01", "2026-01-01"],
        "player_load": [50.0, 50.0],
    })
    resultado = calcular_acwr(df, col_carga="player_load")
    # Carga diaria total = 100, día único => ewma_aguda = ewma_cronica = 100
    assert (resultado["ewma_aguda"] == 100.0).all()
    assert (resultado["ewma_cronica"] == 100.0).all()
    # Ambas filas del día comparten el mismo ACWR (riesgo es a nivel día)
    assert resultado["acwr"].nunique() == 1


def test_acwr_por_jugadora_no_mezcla_cargas_entre_jugadoras():
    df = pd.concat([
        _df_carga_constante("J1", carga=50.0, dias=10),
        _df_carga_constante("J2", carga=200.0, dias=10),
    ])
    resultado = calcular_acwr(df, col_carga="player_load", por_jugadora=True)
    ewma_j1 = resultado.loc[resultado["player_id"] == "J1", "ewma_aguda"]
    ewma_j2 = resultado.loc[resultado["player_id"] == "J2", "ewma_aguda"]
    assert (ewma_j1 == 50.0).all()
    assert (ewma_j2 == 200.0).all()


def test_acwr_cronica_cero_da_sin_datos_no_crash():
    df = _df_carga_constante("J1", carga=0.0, dias=10)
    resultado = calcular_acwr(df, col_carga="player_load")
    assert resultado["acwr"].isna().all()
    assert (resultado["zona_acwr"] == "Sin datos").all()


# ── calcular_srpe ────────────────────────────────────────────────────────────

def test_srpe_es_rpe_por_duracion():
    df_wellness = pd.DataFrame({
        "player_id": ["J1"],
        "fecha": ["2026-01-01"],
        "rpe": [7],
    })
    df_gps = pd.DataFrame({
        "player_id": ["J1"],
        "fecha": ["2026-01-01"],
        "duracion_min": [90],
    })
    resultado = calcular_srpe(df_wellness, df_gps)
    assert resultado["srpe"].iloc[0] == pytest.approx(630.0)


def test_srpe_sin_sesion_gps_da_nan():
    df_wellness = pd.DataFrame({
        "player_id": ["J1"],
        "fecha": ["2026-01-01"],
        "rpe": [7],
    })
    df_gps = pd.DataFrame({
        "player_id": ["J1"],
        "fecha": ["2026-01-02"],  # otro día, no matchea
        "duracion_min": [90],
    })
    resultado = calcular_srpe(df_wellness, df_gps)
    assert pd.isna(resultado["srpe"].iloc[0])


# ── calcular_intensidad_relativa ─────────────────────────────────────────────

def test_intensidad_relativa_calculo_basico():
    df = pd.DataFrame({
        "duracion_min": [60],
        "distancia_total": [6000],
        "hsr": [600],
        "player_load": [300],
    })
    resultado = calcular_intensidad_relativa(df)
    assert resultado["dist_min"].iloc[0] == pytest.approx(100.0)
    assert resultado["hsr_pct"].iloc[0] == pytest.approx(10.0)
    assert resultado["pl_min"].iloc[0] == pytest.approx(5.0)


def test_intensidad_relativa_division_por_cero_da_nan():
    df = pd.DataFrame({
        "duracion_min": [0],
        "distancia_total": [0],
        "hsr": [0],
        "player_load": [0],
    })
    resultado = calcular_intensidad_relativa(df)
    assert resultado["dist_min"].isna().iloc[0]
    assert resultado["hsr_pct"].isna().iloc[0]
    assert resultado["pl_min"].isna().iloc[0]


# ── agregar_partidos_completos ───────────────────────────────────────────────

def _fila_cuarto(player_id, nombre, fecha, cuarto, duracion=15, distancia=1000):
    return {
        "player_id": player_id, "nombre": nombre, "fecha": fecha,
        "tipo_sesion": "Partido", "cuarto": cuarto,
        "duracion_min": duracion, "distancia_total": distancia,
        "hsr": 100, "hsr_esfuerzos": 2, "sprints": 3,
        "acc_3": 1, "acc_2": 2, "decc_3": 1, "decc_2": 2,
        "player_load": 50, "pl_fwd": 10, "pl_side": 10, "pl_up": 10,
        "pl_2d": 10, "pl_slow": 10, "acc_load": 5,
        "vel_max_kmh": 20, "vel_max_ms": 5.5, "vel_max_pct": 90,
    }


def test_partidos_completos_solo_jugadoras_con_4_cuartos():
    filas = (
        [_fila_cuarto("J1", "Jugadora Uno", "2026-01-01", q) for q in ["Q1", "Q2", "Q3", "Q4"]]
        + [_fila_cuarto("J2", "Jugadora Dos", "2026-01-01", q) for q in ["Q1", "Q2"]]  # incompleta
    )
    df = pd.DataFrame(filas)
    resultado = agregar_partidos_completos(df)
    assert set(resultado["player_id"]) == {"J1"}
    assert resultado["duracion_min"].iloc[0] == pytest.approx(60)  # 4 x 15
    assert resultado["distancia_total"].iloc[0] == pytest.approx(4000)  # 4 x 1000


def test_partidos_completos_sin_partidos_devuelve_vacio():
    df = pd.DataFrame([{
        "player_id": "J1", "nombre": "Jugadora Uno", "fecha": "2026-01-01",
        "tipo_sesion": "Físico", "cuarto": "—",
    }])
    resultado = agregar_partidos_completos(df)
    assert resultado.empty


# ── resumen_carga_equipo ─────────────────────────────────────────────────────

def test_resumen_carga_equipo_estadisticas():
    df = pd.DataFrame({
        "fecha": ["2026-01-01", "2026-01-01", "2026-01-01"],
        "player_load": [100, 200, 300],
    })
    resultado = resumen_carga_equipo(df, col_carga="player_load")
    fila = resultado.iloc[0]
    assert fila["media"] == pytest.approx(200.0)
    assert fila["minimo"] == pytest.approx(100.0)
    assert fila["maximo"] == pytest.approx(300.0)
    assert fila["n_jugadoras"] == 3
