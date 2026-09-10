import pandas as pd
import pytest

from src.metrics.biblioteca_ejercicios import (
    normalizar_por_minuto, perfil_por_ejercicio, variables_destacadas,
)


def _bloque(ejercicio, fecha, cuarto, jugadora, duracion_min=10,
            distancia_total=1000, hsr=50, sprints=2, acc_2=5, acc_3=1,
            decc_2=4, decc_3=1, player_load=100, vel_max_kmh=25,
            tipo_sesion="Técnico-Táctico"):
    return {
        "player_id": jugadora, "nombre": jugadora, "fecha": fecha,
        "tipo_sesion": tipo_sesion, "cuarto": cuarto, "ejercicio": ejercicio,
        "duracion_min": duracion_min, "distancia_total": distancia_total,
        "hsr": hsr, "sprints": sprints, "acc_2": acc_2, "acc_3": acc_3,
        "decc_2": decc_2, "decc_3": decc_3, "player_load": player_load,
        "vel_max_kmh": vel_max_kmh,
    }


# ── normalizar_por_minuto ────────────────────────────────────────────────

def test_normaliza_dividiendo_por_duracion():
    df = pd.DataFrame([_bloque("ABC", "2026-09-03", "1", "J1",
                                duracion_min=10, distancia_total=1000)])
    resultado = normalizar_por_minuto(df)
    assert resultado["distancia_por_min"].iloc[0] == pytest.approx(100.0)


def test_duracion_cero_da_nan_no_infinito():
    df = pd.DataFrame([_bloque("ABC", "2026-09-03", "1", "J1", duracion_min=0)])
    resultado = normalizar_por_minuto(df)
    assert pd.isna(resultado["distancia_por_min"].iloc[0])


# ── perfil_por_ejercicio ──────────────────────────────────────────────────

def test_excluye_bloques_sin_taguear():
    df = pd.DataFrame([
        _bloque("—", "2026-09-03", "1", "J1"),
        _bloque("ABC", "2026-09-03", "2", "J1"),
    ])
    resultado = perfil_por_ejercicio(df)
    assert resultado["ejercicio"].tolist() == ["ABC"]


def test_excluye_sesiones_que_no_son_tecnico_tactico():
    df = pd.DataFrame([
        _bloque("ABC", "2026-09-03", "1", "J1", tipo_sesion="Físico"),
    ])
    resultado = perfil_por_ejercicio(df)
    assert resultado.empty


def test_dataframe_vacio_sin_nada_tageado():
    df = pd.DataFrame([_bloque("—", "2026-09-03", "1", "J1")])
    assert perfil_por_ejercicio(df).empty


def test_n_bloques_cuenta_sesiones_no_jugadoras():
    # Mismo bloque (fecha+cuarto), 3 jugadoras -> 1 bloque, 3 muestras.
    df = pd.DataFrame([
        _bloque("ABC", "2026-09-03", "1", "J1"),
        _bloque("ABC", "2026-09-03", "1", "J2"),
        _bloque("ABC", "2026-09-03", "1", "J3"),
    ])
    resultado = perfil_por_ejercicio(df)
    fila = resultado[resultado["ejercicio"] == "ABC"].iloc[0]
    assert fila["n_bloques"] == 1
    assert fila["n_muestras"] == 3


def test_repeticion_del_mismo_ejercicio_en_bloques_distintos_se_promedia():
    # ABC aparece 2 veces en la sesión (cuarto 1 y 2), con distinta carga.
    df = pd.DataFrame([
        _bloque("ABC", "2026-09-03", "1", "J1", duracion_min=10, distancia_total=1000),  # 100/min
        _bloque("ABC", "2026-09-03", "2", "J1", duracion_min=10, distancia_total=2000),  # 200/min
    ])
    resultado = perfil_por_ejercicio(df)
    fila = resultado[resultado["ejercicio"] == "ABC"].iloc[0]
    assert fila["n_bloques"] == 2
    assert fila["distancia_por_min"] == pytest.approx(150.0)


# ── variables_destacadas ─────────────────────────────────────────────────

def test_un_solo_ejercicio_no_da_destacadas():
    df = pd.DataFrame([
        _bloque("ABC", "2026-09-03", "1", "J1"),
    ])
    perfil = perfil_por_ejercicio(df)
    assert variables_destacadas(perfil).empty


def test_detecta_la_metrica_que_mas_se_destaca():
    # "Sprints" (ABC) tiene sprints muy por encima del resto -> debe aparecer
    # primero en las destacadas de ABC.
    df = pd.DataFrame([
        _bloque("ABC", "2026-09-03", "1", "J1", duracion_min=10, sprints=20,
                distancia_total=1000, hsr=50, acc_2=5, acc_3=1, decc_2=4, decc_3=1, player_load=100),
        _bloque("Rondo", "2026-09-04", "1", "J1", duracion_min=10, sprints=1,
                distancia_total=1000, hsr=50, acc_2=5, acc_3=1, decc_2=4, decc_3=1, player_load=100),
        _bloque("Posesion", "2026-09-05", "1", "J1", duracion_min=10, sprints=1,
                distancia_total=1000, hsr=50, acc_2=5, acc_3=1, decc_2=4, decc_3=1, player_load=100),
    ])
    perfil = perfil_por_ejercicio(df)
    destacadas = variables_destacadas(perfil, top_n=1)
    fila_abc = destacadas[destacadas["ejercicio"] == "ABC"].iloc[0]
    assert fila_abc["metrica"] == "sprints_por_min"


def test_metrica_sin_variacion_entre_ejercicios_no_aparece():
    # distancia_total es igual en los 3 ejercicios -> std 0 -> se excluye.
    df = pd.DataFrame([
        _bloque("ABC", "2026-09-03", "1", "J1", distancia_total=1000, sprints=20),
        _bloque("Rondo", "2026-09-04", "1", "J1", distancia_total=1000, sprints=1),
        _bloque("Posesion", "2026-09-05", "1", "J1", distancia_total=1000, sprints=1),
    ])
    perfil = perfil_por_ejercicio(df)
    destacadas = variables_destacadas(perfil, top_n=10)
    assert "distancia_por_min" not in destacadas["metrica"].values
