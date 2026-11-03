import numpy as np
import pandas as pd
import pytest

from src.metrics.fuerza import (
    estimar_rm_epley,
    agregar_rm_a_tests,
    rm_vigente,
    calcular_tonelaje,
    normalizar_registros_rm,
    armar_series,
    enriquecer_series,
    resumen_por_periodo,
)


# ── estimar_rm_epley ─────────────────────────────────────────────────────────

def test_epley_una_repeticion_devuelve_el_mismo_peso():
    assert estimar_rm_epley(100.0, 1) == pytest.approx(100.0)


def test_epley_valor_conocido_5_reps():
    # 80 * (1 + 5/30) = 93.333...
    assert estimar_rm_epley(80.0, 5) == pytest.approx(93.3333, rel=1e-4)


@pytest.mark.parametrize("kg,reps", [
    (0, 5),       # peso nulo
    (-10, 5),     # peso negativo
    (80, 0),      # sin repeticiones
    (80, 11),     # >10 reps: la estimación deja de ser confiable
    (np.nan, 5),
    (80, np.nan),
])
def test_epley_entradas_invalidas_devuelven_nan(kg, reps):
    assert np.isnan(estimar_rm_epley(kg, reps))


# ── agregar_rm_a_tests ───────────────────────────────────────────────────────

def test_rm_directo_usa_el_peso_tal_cual_y_submaximo_se_estima():
    df = pd.DataFrame({
        "player_id": ["a", "a"],
        "ejercicio": ["Sentadilla trasera"] * 2,
        "fecha": pd.to_datetime(["2026-08-01", "2026-09-01"]),
        "tipo": ["RM", "Submáximo"],
        "kg": [100.0, 80.0],
        "reps": [1, 5],
    })
    out = agregar_rm_a_tests(df)
    assert out["rm_kg"].iloc[0] == pytest.approx(100.0)
    assert out["rm_kg"].iloc[1] == pytest.approx(93.3333, rel=1e-4)
    assert list(out["rm_origen"]) == ["Directo", "Estimado"]


def test_agregar_rm_no_muta_el_dataframe_original():
    df = pd.DataFrame({
        "player_id": ["a"], "ejercicio": ["Hip thrust"],
        "fecha": pd.to_datetime(["2026-08-01"]),
        "tipo": ["RM"], "kg": [120.0], "reps": [1],
    })
    agregar_rm_a_tests(df)
    assert "rm_kg" not in df.columns


# ── rm_vigente (as-of) ───────────────────────────────────────────────────────

@pytest.fixture
def tests_rm():
    df = pd.DataFrame({
        "player_id": ["a", "a", "a", "b"],
        "ejercicio": ["Sentadilla trasera"] * 3 + ["Sentadilla trasera"],
        "fecha": pd.to_datetime(["2026-08-01", "2026-09-01", "2026-10-01", "2026-08-15"]),
        "tipo": ["RM", "RM", "RM", "RM"],
        "kg": [90.0, 95.0, 100.0, 70.0],
        "reps": [1, 1, 1, 1],
    })
    return agregar_rm_a_tests(df)


def test_rm_vigente_toma_el_ultimo_test_anterior_o_igual_a_la_fecha(tests_rm):
    # El 2026-09-15 el vigente es el del 09-01, NO el del 10-01 (futuro):
    # si usáramos el más nuevo reescribiríamos el pasado.
    assert rm_vigente(tests_rm, "a", "Sentadilla trasera", "2026-09-15") == 95.0


def test_rm_vigente_el_mismo_dia_del_test_cuenta(tests_rm):
    assert rm_vigente(tests_rm, "a", "Sentadilla trasera", "2026-10-01") == 100.0


def test_rm_vigente_antes_del_primer_test_es_nan(tests_rm):
    assert np.isnan(rm_vigente(tests_rm, "a", "Sentadilla trasera", "2026-07-01"))


def test_rm_vigente_no_mezcla_jugadoras_ni_ejercicios(tests_rm):
    assert rm_vigente(tests_rm, "b", "Sentadilla trasera", "2026-12-01") == 70.0
    assert np.isnan(rm_vigente(tests_rm, "a", "Banco plano", "2026-12-01"))


# ── calcular_tonelaje ────────────────────────────────────────────────────────

def test_tonelaje_es_suma_de_kg_por_reps():
    df = pd.DataFrame({"kg": [60.0, 60.0, 70.0], "reps": [8, 8, 5]})
    # 480 + 480 + 350
    assert calcular_tonelaje(df) == pytest.approx(1310.0)


def test_tonelaje_ignora_filas_incompletas():
    df = pd.DataFrame({"kg": [60.0, np.nan], "reps": [8, 8]})
    assert calcular_tonelaje(df) == pytest.approx(480.0)


def test_tonelaje_de_dataframe_vacio_es_cero():
    assert calcular_tonelaje(pd.DataFrame({"kg": [], "reps": []})) == 0.0


# ── normalizar_registros_rm (registros_rm de la app de jugadoras) ────────────

def _registros_rm_crudos():
    return pd.DataFrame({
        "player_id": ["a", "a", "b"],
        "ejercicio": ["sentadilla_detras", "cargadas", "peso_muerto"],
        "rm_kg": [90.0, 50.0, 100.0],
        "fecha": ["2026-08-01", "2026-09-01", "2026-09-01"],
    })


def test_normalizar_registros_rm_traduce_slugs_al_nombre_del_catalogo():
    out = normalizar_registros_rm(_registros_rm_crudos())
    assert list(out["ejercicio"]) == ["Sentadilla trasera", "Cargada", "Peso muerto"]


def test_normalizar_registros_rm_marca_el_origen_como_autorreportado():
    out = normalizar_registros_rm(_registros_rm_crudos())
    assert (out["rm_origen"] == "Autorreportado").all()


def test_normalizar_registros_rm_slug_desconocido_no_se_pierde():
    df = _registros_rm_crudos()
    df.loc[0, "ejercicio"] = "press_inclinado"
    out = normalizar_registros_rm(df)
    assert out["ejercicio"].iloc[0] == "Press inclinado"


def test_normalizar_registros_rm_traduce_arranque_y_tirones_de_cargada():
    df = _registros_rm_crudos()
    df["ejercicio"] = ["arranque", "tirones_cargada", "cargadas"]
    out = normalizar_registros_rm(df)
    assert list(out["ejercicio"]) == ["Arranque", "Tirones de cargada", "Cargada"]


def test_registros_normalizados_son_compatibles_con_rm_vigente():
    out = normalizar_registros_rm(_registros_rm_crudos())
    assert rm_vigente(out, "a", "Sentadilla trasera", "2026-12-01") == 90.0
    assert np.isnan(rm_vigente(out, "a", "Sentadilla trasera", "2026-07-01"))


# ── armar_series (filas del formulario de carga) ─────────────────────────────

def test_armar_series_numera_las_series_desde_1():
    df = pd.DataFrame({"reps": [5, 5, 5], "kg": [60.0, 70.0, 80.0], "rir": [3, 2, 1]})
    out = armar_series(df)
    assert list(out["nro_serie"]) == [1, 2, 3]


def test_armar_series_descarta_filas_incompletas_y_renumera():
    df = pd.DataFrame({
        "reps": [5, np.nan, 5],
        "kg": [60.0, 70.0, np.nan],
        "rir": [None, None, None],
    })
    out = armar_series(df)
    assert len(out) == 1
    assert out["nro_serie"].iloc[0] == 1


def test_armar_series_descarta_reps_menor_a_1_y_kg_negativo():
    df = pd.DataFrame({"reps": [0, 5, 5], "kg": [60.0, -5.0, 50.0], "rir": [None] * 3})
    out = armar_series(df)
    assert list(out["kg"]) == [50.0]


def test_armar_series_rir_fuera_de_rango_queda_vacio_no_descarta_la_serie():
    df = pd.DataFrame({"reps": [5, 5], "kg": [60.0, 60.0], "rir": [3, 15]})
    out = armar_series(df)
    assert len(out) == 2
    assert out["rir"].iloc[0] == 3
    assert pd.isna(out["rir"].iloc[1])


def test_armar_series_dataframe_vacio_devuelve_vacio_con_columnas():
    out = armar_series(pd.DataFrame({"reps": [], "kg": [], "rir": []}))
    assert out.empty
    assert list(out.columns) == ["nro_serie", "reps", "kg", "rir"]


# ── enriquecer_series (%RM real as-of + tonelaje) ────────────────────────────

def _rm_base():
    return pd.DataFrame({
        "player_id": ["a", "a", "a"],
        "ejercicio": ["Sentadilla trasera", "Sentadilla trasera", "Cargada"],
        "fecha": pd.to_datetime(["2026-08-01", "2026-09-15", "2026-08-01"]),
        "rm_kg": [100.0, 110.0, 50.0],
    })


def _series_base(**cambios):
    df = pd.DataFrame({
        "player_id": ["a"],
        "fecha": pd.to_datetime(["2026-09-01"]),
        "ejercicio": ["Sentadilla trasera"],
        "nro_serie": [1],
        "reps": [5],
        "kg": [80.0],
    })
    for k, v in cambios.items():
        df[k] = v
    return df


def test_enriquecer_usa_el_rm_vigente_de_la_fecha_de_la_serie():
    # 09-01: el vigente es 100 (el de 09-15 todavía no existe)
    out = enriquecer_series(_series_base(), _rm_base())
    assert out["rm_kg"].iloc[0] == pytest.approx(100.0)
    assert out["pct_rm_real"].iloc[0] == pytest.approx(80.0)


def test_enriquecer_despues_de_un_nuevo_rm_usa_el_nuevo():
    out = enriquecer_series(_series_base(fecha=pd.to_datetime(["2026-09-20"])), _rm_base())
    assert out["rm_kg"].iloc[0] == pytest.approx(110.0)


def test_enriquecer_calcula_tonelaje_por_serie():
    out = enriquecer_series(_series_base(), _rm_base())
    assert out["tonelaje"].iloc[0] == pytest.approx(400.0)


def test_enriquecer_sin_rm_previo_deja_pct_vacio_pero_conserva_la_serie():
    out = enriquecer_series(_series_base(fecha=pd.to_datetime(["2026-07-01"])), _rm_base())
    assert len(out) == 1
    assert np.isnan(out["pct_rm_real"].iloc[0])
    assert out["tonelaje"].iloc[0] == pytest.approx(400.0)


def test_enriquecer_ejercicio_con_referencia_usa_el_rm_del_ejercicio_referido():
    # Tirones de cargada no tiene RM propio: se mide contra el RM de Cargada (50)
    series = _series_base(ejercicio="Tirones de cargada", kg=40.0)
    out = enriquecer_series(series, _rm_base(),
                            referencias={"Tirones de cargada": "Cargada"})
    assert out["rm_kg"].iloc[0] == pytest.approx(50.0)
    assert out["pct_rm_real"].iloc[0] == pytest.approx(80.0)


def test_enriquecer_no_mezcla_jugadoras():
    out = enriquecer_series(_series_base(player_id="b"), _rm_base())
    assert np.isnan(out["rm_kg"].iloc[0])


def test_enriquecer_conserva_el_orden_original_de_las_filas():
    series = pd.concat([
        _series_base(fecha=pd.to_datetime(["2026-09-20"])),
        _series_base(fecha=pd.to_datetime(["2026-09-01"])),
    ], ignore_index=True)
    out = enriquecer_series(series, _rm_base())
    assert list(out["rm_kg"]) == [110.0, 100.0]


# ── resumen_por_periodo (historial semanal / mensual) ────────────────────────

def _enriquecido():
    return pd.DataFrame({
        "fecha": pd.to_datetime(["2026-09-01", "2026-09-03", "2026-09-10", "2026-10-02"]),
        "ejercicio": ["Banco plano"] * 4,
        "reps": [5, 5, 5, 5],
        "tonelaje": [300.0, 200.0, 100.0, 50.0],
        "pct_rm_real": [80.0, 60.0, np.nan, 70.0],
    })


def test_resumen_semanal_suma_las_sesiones_de_la_misma_semana():
    out = resumen_por_periodo(_enriquecido(), freq="W")
    # 09-01 (mar) y 09-03 (jue) caen en la misma semana
    primera = out.iloc[0]
    assert primera["tonelaje"] == pytest.approx(500.0)
    assert primera["n_series"] == 2
    assert primera["n_sesiones"] == 2


def test_resumen_semanal_separa_las_semanas():
    out = resumen_por_periodo(_enriquecido(), freq="W")
    assert len(out) == 3
    assert out["periodo"].is_monotonic_increasing


def test_resumen_mensual_agrupa_por_mes():
    out = resumen_por_periodo(_enriquecido(), freq="M")
    assert list(out["tonelaje"]) == [pytest.approx(600.0), pytest.approx(50.0)]


def test_resumen_pct_rm_medio_ignora_las_series_sin_rm():
    out = resumen_por_periodo(_enriquecido(), freq="M")
    # septiembre: 80, 60 y NaN -> media de 70
    assert out["pct_rm_medio"].iloc[0] == pytest.approx(70.0)


def test_resumen_puede_abrirse_por_ejercicio():
    df = _enriquecido()
    df.loc[1, "ejercicio"] = "Hip thrust"
    out = resumen_por_periodo(df, freq="M", por=["ejercicio"])
    sept = out[out["periodo"] == pd.Timestamp("2026-09-01")]
    assert set(sept["ejercicio"]) == {"Banco plano", "Hip thrust"}


def test_resumen_de_dataframe_vacio_devuelve_vacio():
    vacio = _enriquecido().iloc[0:0]
    assert resumen_por_periodo(vacio, freq="W").empty
