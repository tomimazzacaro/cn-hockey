import datetime

import pandas as pd
import pytest

from src.metrics.entrenamiento import (
    METRICAS_ENTRENAMIENTO, filtrar_entrenamientos, totalizar_por_jugadora_dia,
    asignar_microciclo, promediar_por, pivot_por_md,
)

D = datetime.date


def _fila(nombre="J1", fecha=D(2026, 9, 21), match_day="MD-5", tipo="Físico",
          posicion="Defensora", **metricas):
    base = {m: 0 for m in METRICAS_ENTRENAMIENTO}
    base.update(metricas)
    return {"player_id": nombre.lower(), "nombre": nombre, "posicion": posicion,
            "fecha": fecha, "match_day": match_day, "tipo_sesion": tipo, **base}


# ── filtrar_entrenamientos ───────────────────────────────────────────────────

def test_filtra_fisico_tt_y_amistosos_pero_no_partidos():
    df = pd.DataFrame([
        _fila(tipo="Físico", match_day="MD-5"),
        _fila(tipo="Técnico-Táctico", match_day="MD-2"),
        _fila(tipo="Partido", match_day="MD"),
        _fila(tipo="Amistoso", match_day="MD-4"),       # amistoso de martes: referencia
        _fila(tipo="Amistoso", match_day="MD"),         # amistoso de sábado: también
        _fila(tipo="Físico", match_day="Sin clasificar"),
    ])
    resultado = filtrar_entrenamientos(df)
    assert list(resultado["tipo_sesion"]) == ["Físico", "Técnico-Táctico", "Amistoso", "Amistoso"]


def test_entrenamiento_suelto_en_dia_md_no_entra():
    # Un Físico/TT etiquetado "MD" (ej. sábado sin partido) no es un día del
    # microciclo de entrenamiento — solo los amistosos entran en "MD".
    df = pd.DataFrame([_fila(tipo="Físico", match_day="MD")])
    assert filtrar_entrenamientos(df).empty


# ── totalizar_por_jugadora_dia ───────────────────────────────────────────────

def test_suma_fisico_y_tt_del_mismo_dia_por_jugadora():
    df = pd.DataFrame([
        _fila(tipo="Físico", distancia_total=3000, sprints=2),
        _fila(tipo="Técnico-Táctico", distancia_total=1000, sprints=1),
        _fila(nombre="J2", distancia_total=2500),
    ])
    resultado = totalizar_por_jugadora_dia(df).set_index("nombre")
    assert resultado.loc["J1", "distancia_total"] == pytest.approx(4000)
    assert resultado.loc["J1", "sprints"] == 3
    assert resultado.loc["J2", "distancia_total"] == pytest.approx(2500)


def test_suma_cuartos_de_amistoso_y_marca_el_dia_como_amistoso():
    df = pd.DataFrame([
        _fila(tipo="Amistoso", match_day="MD-4", distancia_total=1500),  # Q1
        _fila(tipo="Amistoso", match_day="MD-4", distancia_total=1600),  # Q2
        _fila(nombre="J2", tipo="Físico", distancia_total=2000),
    ])
    resultado = totalizar_por_jugadora_dia(df).set_index("nombre")
    assert resultado.loc["J1", "distancia_total"] == pytest.approx(3100)
    assert bool(resultado.loc["J1", "amistoso"]) is True
    assert bool(resultado.loc["J2", "amistoso"]) is False


def test_jugadora_sin_posicion_no_se_pierde_al_totalizar():
    # groupby descarta filas con NaN en las claves por default — una jugadora
    # que no está en el roster desaparecería en silencio de la página.
    df = pd.DataFrame([_fila(posicion=None, distancia_total=3000)])
    resultado = totalizar_por_jugadora_dia(df)
    assert len(resultado) == 1
    assert resultado.iloc[0]["posicion"] == "Sin posición"


# ── asignar_microciclo ───────────────────────────────────────────────────────

def _sesiones():
    return pd.DataFrame([
        {"fecha": D(2026, 9, 19), "match_day": "MD", "rival": "G. Y Esgrima C"},
        {"fecha": D(2026, 9, 21), "match_day": "MD-5", "rival": ""},
        {"fecha": D(2026, 9, 24), "match_day": "MD-2", "rival": ""},
        {"fecha": D(2026, 9, 26), "match_day": "MD", "rival": "San Luis"},
    ])


def test_asigna_cada_dia_al_proximo_md_del_calendario():
    df = pd.DataFrame([_fila(fecha=D(2026, 9, 21)), _fila(fecha=D(2026, 9, 24), match_day="MD-2")])
    resultado = asignar_microciclo(df, _sesiones())
    assert list(resultado["microciclo_fecha"]) == [D(2026, 9, 26), D(2026, 9, 26)]
    assert resultado.iloc[0]["microciclo"] == "vs San Luis (26/09)"


def test_dia_sin_md_posterior_en_calendario_queda_sin_asignar():
    df = pd.DataFrame([_fila(fecha=D(2026, 9, 28))])
    resultado = asignar_microciclo(df, _sesiones())
    assert resultado.iloc[0]["microciclo"] == "Sin MD asignado"
    assert pd.isna(resultado.iloc[0]["microciclo_fecha"])


def test_md_que_no_fue_partido_ignora_el_texto_de_relleno_de_rival():
    # Semanas sin partido: el Sheet trae "No hay fecha"/"Entrenamiento" en
    # Partido_vs — no es un rival.
    sesiones = pd.DataFrame([{"fecha": D(2026, 9, 26), "match_day": "MD",
                              "tipo_dia": "Entrenamiento", "rival": "No hay fecha"}])
    resultado = asignar_microciclo(pd.DataFrame([_fila()]), sesiones)
    assert resultado.iloc[0]["microciclo"] == "MD 26/09"


def test_md_sin_rival_usa_solo_la_fecha():
    sesiones = pd.DataFrame([{"fecha": D(2026, 9, 26), "match_day": "MD", "rival": ""}])
    resultado = asignar_microciclo(pd.DataFrame([_fila()]), sesiones)
    assert resultado.iloc[0]["microciclo"] == "MD 26/09"


# ── promediar_por ────────────────────────────────────────────────────────────

def test_promedia_por_jugadora_y_cuenta_jugadoras():
    df_total = pd.DataFrame([
        _fila(nombre="J1", distancia_total=4000),
        _fila(nombre="J2", distancia_total=2000),
        _fila(nombre="J3", match_day="MD-2", distancia_total=1000),
    ])
    resultado = promediar_por(df_total, ["match_day"]).set_index("match_day")
    assert resultado.loc["MD-5", "distancia_total"] == pytest.approx(3000)
    assert resultado.loc["MD-5", "n_jugadoras"] == 2
    assert resultado.loc["MD-2", "n_jugadoras"] == 1


# ── pivot_por_md ─────────────────────────────────────────────────────────────

def test_pivot_ordena_columnas_cronologicamente_y_deja_vacio_si_falta():
    df = pd.DataFrame([
        {"nombre": "J1", "match_day": "MD-2", "hsr": 50},
        {"nombre": "J1", "match_day": "MD-5", "hsr": 10},
        {"nombre": "J2", "match_day": "MD-4", "hsr": 80},
    ])
    df.loc[len(df)] = {"nombre": "J2", "match_day": "MD", "hsr": 120}
    resultado = pivot_por_md(df, "nombre", "hsr")
    assert list(resultado.columns) == ["MD-5", "MD-4", "MD-2", "MD"]
    assert resultado.loc["J1", "MD-5"] == 10
    assert pd.isna(resultado.loc["J2", "MD-5"])
