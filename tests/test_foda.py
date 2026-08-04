import pandas as pd
import pytest

from src.metrics.foda import (
    resumen_duracion_por_md, resumen_cumplimiento_por_md,
    resumen_acwr_por_md, detectar_posible_calibracion, dividir_en_bullets,
)


# ── resumen_duracion_por_md ──────────────────────────────────────────────────

def test_duracion_vacio_devuelve_columnas_esperadas():
    resultado = resumen_duracion_por_md(pd.DataFrame())
    assert list(resultado.columns) == [
        "match_day", "tipo_sesion", "media_min", "desvio_min",
        "minimo_min", "maximo_min", "n", "cv", "variabilidad_alta",
    ]
    assert resultado.empty


def test_duracion_variabilidad_alta_con_cv_por_encima_del_umbral():
    # media 60, desvíos grandes (27 a 104, como el caso real de MD-5 TT) -> cv alto
    df = pd.DataFrame([
        {"match_day": "MD-5", "tipo_sesion": "Técnico-Táctico", "duracion_min": 27},
        {"match_day": "MD-5", "tipo_sesion": "Técnico-Táctico", "duracion_min": 104},
        {"match_day": "MD-5", "tipo_sesion": "Técnico-Táctico", "duracion_min": 68},
    ])
    resultado = resumen_duracion_por_md(df, umbral_cv=0.35)
    fila = resultado.iloc[0]
    assert fila["n"] == 3
    assert fila["variabilidad_alta"]


def test_duracion_una_sola_sesion_no_marca_variabilidad():
    # n=1 -> std es NaN, no puede haber "variabilidad alta" con un solo dato.
    df = pd.DataFrame([{"match_day": "MD-2", "tipo_sesion": "Físico", "duracion_min": 20}])
    resultado = resumen_duracion_por_md(df)
    assert resultado.iloc[0]["variabilidad_alta"] == False  # noqa: E712


def test_duracion_consistente_no_marca_variabilidad():
    df = pd.DataFrame([
        {"match_day": "MD-4", "tipo_sesion": "Físico", "duracion_min": 30},
        {"match_day": "MD-4", "tipo_sesion": "Físico", "duracion_min": 31},
        {"match_day": "MD-4", "tipo_sesion": "Físico", "duracion_min": 29},
    ])
    resultado = resumen_duracion_por_md(df, umbral_cv=0.35)
    assert resultado.iloc[0]["variabilidad_alta"] == False  # noqa: E712


# ── resumen_cumplimiento_por_md ──────────────────────────────────────────────

def _fila_individual(match_day, metrica, estado, nombre="Ana"):
    return {"nombre": nombre, "posicion": "Volante", "match_day": match_day,
            "metrica": metrica, "estado": estado, "valor_real": 100.0,
            "rango_min": 80.0, "rango_max": 120.0}


def test_cumplimiento_vacio_devuelve_columnas_esperadas():
    resultado = resumen_cumplimiento_por_md(pd.DataFrame())
    assert list(resultado.columns) == [
        "match_day", "metrica", "n", "pct_por_debajo", "pct_en_rango", "pct_por_encima",
    ]
    assert resultado.empty


def test_cumplimiento_calcula_porcentajes_por_direccion():
    df = pd.DataFrame([
        _fila_individual("MD-4", "ACC>2", "Por debajo", "Ana"),
        _fila_individual("MD-4", "ACC>2", "Por debajo", "Bea"),
        _fila_individual("MD-4", "ACC>2", "Por debajo", "Cami"),
        _fila_individual("MD-4", "ACC>2", "En rango", "Dana"),
    ])
    resultado = resumen_cumplimiento_por_md(df)
    fila = resultado.iloc[0]
    assert fila["n"] == 4
    assert fila["pct_por_debajo"] == pytest.approx(0.75)
    assert fila["pct_en_rango"] == pytest.approx(0.25)
    assert fila["pct_por_encima"] == pytest.approx(0.0)


def test_cumplimiento_excluye_sin_dato_del_denominador():
    df = pd.DataFrame([
        _fila_individual("MD-2", "HSR Distance", "Por debajo", "Ana"),
        _fila_individual("MD-2", "HSR Distance", "Sin dato", "Bea"),
    ])
    resultado = resumen_cumplimiento_por_md(df)
    fila = resultado.iloc[0]
    assert fila["n"] == 1
    assert fila["pct_por_debajo"] == pytest.approx(1.0)


# ── resumen_acwr_por_md ───────────────────────────────────────────────────────

def test_acwr_vacio_devuelve_columnas_esperadas():
    resultado = resumen_acwr_por_md(pd.DataFrame())
    assert list(resultado.columns) == ["match_day", "zona_acwr", "n", "pct"]
    assert resultado.empty


def test_acwr_distribuye_porcentajes_por_zona():
    df = pd.DataFrame([
        {"match_day": "MD-4", "zona_acwr": "Óptimo"},
        {"match_day": "MD-4", "zona_acwr": "Óptimo"},
        {"match_day": "MD-4", "zona_acwr": "Óptimo"},
        {"match_day": "MD-4", "zona_acwr": "Subcarga"},
    ])
    resultado = resumen_acwr_por_md(df)
    fila_optimo = resultado[resultado["zona_acwr"] == "Óptimo"].iloc[0]
    assert fila_optimo["n"] == 3
    assert fila_optimo["pct"] == pytest.approx(0.75)


# ── detectar_posible_calibracion ────────────────────────────────────────────

def test_calibracion_vacio_devuelve_lista_vacia():
    assert detectar_posible_calibracion(pd.DataFrame()) == []


def test_calibracion_flaguea_metrica_casi_siempre_por_debajo():
    resumen = pd.DataFrame([
        {"match_day": "MD-4", "metrica": "ACC>2", "n": 49,
         "pct_por_debajo": 1.0, "pct_en_rango": 0.0, "pct_por_encima": 0.0},
        {"match_day": "MD-4", "metrica": "Distancia Total", "n": 49,
         "pct_por_debajo": 0.55, "pct_en_rango": 0.22, "pct_por_encima": 0.23},
    ])
    hallazgos = detectar_posible_calibracion(resumen, umbral_pct=0.90)
    assert len(hallazgos) == 1
    assert hallazgos[0]["metrica"] == "ACC>2"
    assert hallazgos[0]["direccion"] == "Por debajo"
    assert hallazgos[0]["pct"] == pytest.approx(1.0)


def test_calibracion_no_flaguea_por_debajo_del_umbral():
    resumen = pd.DataFrame([
        {"match_day": "MD-2", "metrica": "HSR Distance", "n": 43,
         "pct_por_debajo": 0.84, "pct_en_rango": 0.0, "pct_por_encima": 0.16},
    ])
    assert detectar_posible_calibracion(resumen, umbral_pct=0.90) == []


# ── dividir_en_bullets ───────────────────────────────────────────────────────

def test_dividir_en_bullets_vacio_o_nan():
    assert dividir_en_bullets("") == []
    assert dividir_en_bullets("   ") == []
    assert dividir_en_bullets(float("nan")) == []


def test_dividir_en_bullets_separa_por_guion_seguido_de_mayuscula():
    texto = "-Primero: hace algo. -Segundo: hace otra cosa."
    assert dividir_en_bullets(texto) == ["Primero: hace algo.", "Segundo: hace otra cosa."]


def test_dividir_en_bullets_no_corta_rangos_numericos_sin_espacio():
    # "2-3" y "40 mts." no tienen espacio antes del guión -> no es un bullet nuevo.
    texto = "-TOP UPS: 2-3 bloques de 4 repes de Sprint en 40 mts."
    assert dividir_en_bullets(texto) == ["TOP UPS: 2-3 bloques de 4 repes de Sprint en 40 mts."]


def test_dividir_en_bullets_separador_sin_punto_previo():
    # Caso real de la planilla: cierre de paréntesis + espacios + guión, sin punto.
    texto = ("-Salidas del fondo y posesión (igual o superior a partido) "
             "-Driles de desmarques")
    assert dividir_en_bullets(texto) == [
        "Salidas del fondo y posesión (igual o superior a partido)",
        "Driles de desmarques",
    ]


def test_dividir_en_bullets_un_solo_bullet_sin_guion_final():
    texto = "-Juegos de activación neuromuscular"
    assert dividir_en_bullets(texto) == ["Juegos de activación neuromuscular"]
