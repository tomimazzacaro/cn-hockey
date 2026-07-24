import pandas as pd
import pytest

from src.metrics.parametros import armar_evaluacion_equipo, evaluar_por_jugadora


def _parametros(posicion="Defensora", match_day="MD", metrica="Distancia Total", rango=(0, 100000)):
    return pd.DataFrame([{
        "match_day": match_day, "posicion": posicion, "metrica": metrica,
        "rango_min": rango[0], "rango_max": rango[1],
    }])


# ── armar_evaluacion_equipo ──────────────────────────────────────────────────

def test_totaliza_fisico_y_tt_del_mismo_dia_antes_de_promediar():
    # J1 tuvo Físico (3000) + Técnico-Táctico (1000) el mismo día -> 4000 total.
    # J2 solo tuvo Físico -> 2000. Promedio esperado por posición: 3000.
    df = pd.DataFrame([
        {"nombre": "J1", "posicion": "Defensora", "fecha": "2026-01-01", "match_day": "MD",
         "distancia_total": 3000},
        {"nombre": "J1", "posicion": "Defensora", "fecha": "2026-01-01", "match_day": "MD",
         "distancia_total": 1000},
        {"nombre": "J2", "posicion": "Defensora", "fecha": "2026-01-01", "match_day": "MD",
         "distancia_total": 2000},
    ])
    resultado = armar_evaluacion_equipo(
        df, _parametros(), claves_grupo=["posicion", "fecha", "match_day"],
        etiqueta_fn=lambda f: f["posicion"],
    )
    fila = resultado[resultado["metrica"] == "Distancia Total"].iloc[0]
    assert fila["valor_real"] == pytest.approx(3000.0)


def test_una_sola_jugadora_no_altera_el_total():
    # Perfil de Jugadora: sin "nombre" variando entre filas, el paso de
    # promediar es un no-op sobre la fila ya totalizada por día.
    df = pd.DataFrame([
        {"nombre": "J1", "posicion": "Defensora", "fecha": "2026-01-01", "match_day": "MD",
         "distancia_total": 3000},
        {"nombre": "J1", "posicion": "Defensora", "fecha": "2026-01-01", "match_day": "MD",
         "distancia_total": 1000},
    ])
    resultado = armar_evaluacion_equipo(
        df, _parametros(), claves_grupo=["fecha", "match_day", "posicion"],
        etiqueta_fn=lambda f: f["fecha"],
    )
    fila = resultado[resultado["metrica"] == "Distancia Total"].iloc[0]
    assert fila["valor_real"] == pytest.approx(4000.0)


def test_datos_ya_agregados_no_suman_entre_jugadoras():
    # Partidos: ya una fila por jugadora/partido (agregar_partidos_completos
    # ya sumó los 4 cuartos) — "totalizar" no debe sumar J1+J2, el promedio
    # entre jugadoras de la misma posición tiene que quedar en 6000, no 12000.
    df = pd.DataFrame([
        {"nombre": "J1", "posicion": "Defensora", "partido_label": "vs Rival", "distancia_total": 5000},
        {"nombre": "J2", "posicion": "Defensora", "partido_label": "vs Rival", "distancia_total": 7000},
    ])
    resultado = armar_evaluacion_equipo(
        df, _parametros(), claves_grupo=["posicion", "partido_label"],
        etiqueta_fn=lambda f: f"{f['posicion']} · {f['partido_label']}",
        match_day="MD",
    )
    fila = resultado[resultado["metrica"] == "Distancia Total"].iloc[0]
    assert fila["valor_real"] == pytest.approx(6000.0)


def test_match_day_fijo_se_usa_en_vez_de_la_columna_del_df():
    df = pd.DataFrame([
        {"nombre": "J1", "posicion": "Defensora", "partido_label": "vs Rival", "distancia_total": 5000},
    ])
    resultado = armar_evaluacion_equipo(
        df, _parametros(match_day="MD"), claves_grupo=["posicion", "partido_label"],
        etiqueta_fn=lambda f: "x", match_day="MD",
    )
    assert not resultado.empty
    assert resultado.iloc[0]["valor_real"] == pytest.approx(5000.0)


def test_col_identidad_ausente_no_rompe():
    # No debería pasar en uso normal, pero si col_identidad no está en el
    # df, el paso de totalizar se saltea en vez de tirar KeyError.
    df = pd.DataFrame([
        {"posicion": "Defensora", "fecha": "2026-01-01", "match_day": "MD", "distancia_total": 3000},
    ])
    resultado = armar_evaluacion_equipo(
        df, _parametros(), claves_grupo=["posicion", "fecha", "match_day"],
        etiqueta_fn=lambda f: "x",
    )
    assert not resultado.empty
    assert resultado.iloc[0]["valor_real"] == pytest.approx(3000.0)


# ── evaluar_por_jugadora ─────────────────────────────────────────────────────

def test_evaluar_por_jugadora_no_promedia_entre_companeras():
    # A diferencia de armar_evaluacion_equipo, cada jugadora tiene que
    # conservar SU propio valor, no el promedio del equipo.
    df = pd.DataFrame([
        {"nombre": "J1", "posicion": "Defensora", "fecha": "2026-01-01", "match_day": "MD",
         "distancia_total": 3000},
        {"nombre": "J2", "posicion": "Defensora", "fecha": "2026-01-01", "match_day": "MD",
         "distancia_total": 9000},
    ])
    resultado = evaluar_por_jugadora(
        df, _parametros(), claves_dia=["posicion", "fecha", "match_day"],
    )
    valores = dict(zip(resultado["nombre"], resultado["valor_real"]))
    assert valores["J1"] == pytest.approx(3000.0)
    assert valores["J2"] == pytest.approx(9000.0)


def test_evaluar_por_jugadora_suma_fisico_y_tt_del_mismo_dia():
    df = pd.DataFrame([
        {"nombre": "J1", "posicion": "Defensora", "fecha": "2026-01-01", "match_day": "MD",
         "distancia_total": 3000},
        {"nombre": "J1", "posicion": "Defensora", "fecha": "2026-01-01", "match_day": "MD",
         "distancia_total": 1000},
    ])
    resultado = evaluar_por_jugadora(
        df, _parametros(), claves_dia=["posicion", "fecha", "match_day"],
    )
    assert resultado.iloc[0]["valor_real"] == pytest.approx(4000.0)


def test_evaluar_por_jugadora_match_day_fijo():
    df = pd.DataFrame([
        {"nombre": "J1", "posicion": "Defensora", "partido_label": "vs Rival", "distancia_total": 5000},
        {"nombre": "J2", "posicion": "Defensora", "partido_label": "vs Rival", "distancia_total": 7000},
    ])
    resultado = evaluar_por_jugadora(
        df, _parametros(match_day="MD"), claves_dia=["posicion", "partido_label"], match_day="MD",
    )
    assert set(resultado["nombre"]) == {"J1", "J2"}
    assert len(resultado) == 2


def test_evaluar_por_jugadora_sin_match_day_da_vacio():
    df = pd.DataFrame([
        {"nombre": "J1", "posicion": "Defensora", "fecha": "2026-01-01", "match_day": None,
         "distancia_total": 3000},
    ])
    resultado = evaluar_por_jugadora(
        df, _parametros(), claves_dia=["posicion", "fecha", "match_day"],
    )
    assert resultado.empty
    assert list(resultado.columns) == [
        "nombre", "posicion", "fecha", "match_day", "metrica", "valor_real",
        "rango_min", "rango_max", "estado",
    ]
