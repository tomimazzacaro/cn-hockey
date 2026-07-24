import pandas as pd
import pytest

from src.metrics.analisis import generar_analisis


def _fila(nombre, posicion, metrica, estado, valor_real=100.0, rango=(80.0, 120.0)):
    return {
        "nombre": nombre, "posicion": posicion, "metrica": metrica, "estado": estado,
        "valor_real": valor_real, "rango_min": rango[0], "rango_max": rango[1],
    }


def test_df_vacio_devuelve_listas_vacias():
    resultado = generar_analisis(pd.DataFrame())
    assert resultado == {"fortalezas": [], "debilidades": []}


def test_fortaleza_cuando_todas_las_metricas_en_rango():
    df = pd.DataFrame([
        _fila("Ana", "Defensora", "Distancia Total", "En rango"),
        _fila("Ana", "Defensora", "HSR Distance", "En rango"),
    ])
    resultado = generar_analisis(df)
    assert resultado["fortalezas"] == ["Ana"]
    assert resultado["debilidades"] == []


def test_una_sola_metrica_fuera_no_es_fortaleza_ni_debilidad():
    df = pd.DataFrame([
        _fila("Ana", "Defensora", "Distancia Total", "En rango"),
        _fila("Ana", "Defensora", "HSR Distance", "Por debajo", valor_real=50.0),
    ])
    resultado = generar_analisis(df)
    assert resultado["fortalezas"] == []
    assert resultado["debilidades"] == []


def test_debilidad_con_2_o_mas_metricas_fuera_de_rango():
    df = pd.DataFrame([
        _fila("Ana", "Defensora", "Distancia Total", "Por debajo", valor_real=50.0),
        _fila("Ana", "Defensora", "HSR Distance", "Por encima", valor_real=400.0, rango=(150.0, 300.0)),
        _fila("Ana", "Defensora", "Player Load", "En rango"),
    ])
    resultado = generar_analisis(df)
    assert resultado["fortalezas"] == []
    assert len(resultado["debilidades"]) == 1
    debilidad = resultado["debilidades"][0]
    assert debilidad["nombre"] == "Ana"
    assert debilidad["posicion"] == "Defensora"
    assert {m["metrica"] for m in debilidad["metricas_fuera"]} == {"Distancia Total", "HSR Distance"}


def test_metricas_en_rango_de_la_debilidad_incluye_lo_que_esta_bien():
    # La tarjeta no debe mostrar solo lo que está mal — Player Load está en
    # rango y tiene que aparecer en "metricas_en_rango", no perderse.
    df = pd.DataFrame([
        _fila("Ana", "Defensora", "Distancia Total", "Por debajo", valor_real=50.0),
        _fila("Ana", "Defensora", "HSR Distance", "Por encima", valor_real=400.0, rango=(150.0, 300.0)),
        _fila("Ana", "Defensora", "Player Load", "En rango"),
    ])
    debilidad = generar_analisis(df)["debilidades"][0]
    assert {m["metrica"] for m in debilidad["metricas_en_rango"]} == {"Player Load"}


def test_metricas_en_rango_vacia_si_todo_esta_fuera_de_rango():
    df = pd.DataFrame([
        _fila("Ana", "Defensora", "Distancia Total", "Por debajo", valor_real=50.0),
        _fila("Ana", "Defensora", "HSR Distance", "Por debajo", valor_real=60.0),
    ])
    debilidad = generar_analisis(df)["debilidades"][0]
    assert debilidad["metricas_en_rango"] == []


def test_peor_estado_es_por_encima_si_tiene_al_menos_una():
    df = pd.DataFrame([
        _fila("Ana", "Defensora", "Distancia Total", "Por debajo", valor_real=50.0),
        _fila("Ana", "Defensora", "HSR Distance", "Por encima", valor_real=400.0, rango=(150.0, 300.0)),
    ])
    debilidad = generar_analisis(df)["debilidades"][0]
    assert debilidad["peor_estado"] == "Por encima"


def test_peor_estado_es_por_debajo_si_no_tiene_ninguna_por_encima():
    df = pd.DataFrame([
        _fila("Ana", "Defensora", "Distancia Total", "Por debajo", valor_real=50.0),
        _fila("Ana", "Defensora", "HSR Distance", "Por debajo", valor_real=60.0),
    ])
    debilidad = generar_analisis(df)["debilidades"][0]
    assert debilidad["peor_estado"] == "Por debajo"


def test_umbral_debilidad_configurable():
    df = pd.DataFrame([
        _fila("Ana", "Defensora", "Distancia Total", "Por debajo", valor_real=50.0),
    ])
    assert generar_analisis(df)["debilidades"] == []
    resultado = generar_analisis(df, umbral_debilidad=1)
    assert len(resultado["debilidades"]) == 1


def test_recomendaciones_se_consolidan_por_direccion_no_por_metrica():
    # 2 métricas "por debajo" + 1 "por encima" tienen que dar SOLO 2 líneas
    # (una por dirección), no 3 (una por métrica).
    df = pd.DataFrame([
        _fila("Ana", "Defensora", "Distancia Total", "Por debajo", valor_real=50.0, rango=(80.0, 120.0)),
        _fila("Ana", "Defensora", "Sprints cantidad", "Por debajo", valor_real=2.0, rango=(5.0, 10.0)),
        _fila("Ana", "Defensora", "HSR Distance", "Por encima", valor_real=400.0, rango=(150.0, 300.0)),
    ])
    debilidad = generar_analisis(df)["debilidades"][0]
    assert len(debilidad["recomendaciones"]) == 2
    texto = " ".join(debilidad["recomendaciones"])
    assert "Distancia Total" in texto and "Sprints cantidad" in texto
    assert "reforzar estímulo" in texto.lower() or "Reforzar estímulo" in texto
    assert "vigilar sobrecarga" in texto.lower()


def test_ignora_sin_dato_al_evaluar_fortaleza():
    df = pd.DataFrame([
        _fila("Ana", "Defensora", "Distancia Total", "Sin dato", valor_real=float("nan")),
    ])
    resultado = generar_analisis(df)
    assert resultado["fortalezas"] == []
    assert resultado["debilidades"] == []


def test_debilidades_ordenadas_por_cantidad_de_metricas_fuera_de_rango():
    df = pd.DataFrame([
        _fila("Ana", "Defensora", "Distancia Total", "Por debajo", valor_real=50.0),
        _fila("Ana", "Defensora", "HSR Distance", "Por debajo", valor_real=50.0),
        _fila("Bea", "Delantera", "Distancia Total", "Por debajo", valor_real=50.0),
        _fila("Bea", "Delantera", "HSR Distance", "Por debajo", valor_real=50.0),
        _fila("Bea", "Delantera", "Player Load", "Por encima", valor_real=999.0),
    ])
    resultado = generar_analisis(df)
    assert [d["nombre"] for d in resultado["debilidades"]] == ["Bea", "Ana"]
