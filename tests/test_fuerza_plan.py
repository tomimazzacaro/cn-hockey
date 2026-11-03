import numpy as np
import pandas as pd
import pytest

from src.metrics.fuerza_plan import (
    orden_match_day,
    ua_fuerza,
    metros_pasada,
    es_alta_intensidad,
    tiempo_objetivo_pasada,
    resumir_plan_por_md,
    resumir_plan_semana,
)


def _items(filas):
    cols = ["match_day", "tipo", "series", "repeticiones", "pct_rm", "distancia_m", "pct_vmax"]
    return pd.DataFrame(filas, columns=cols)


# ── orden_match_day ──────────────────────────────────────────────────────────

def test_orden_match_day_ordena_cronologicamente():
    mds = ["MD-2", "MD-5", "MD-4", "MD+1"]
    assert sorted(mds, key=orden_match_day) == ["MD-5", "MD-4", "MD-2", "MD+1"]


@pytest.mark.parametrize("malo", ["", "MD", "MD5", "XX-5", "MD-x", "MD--5"])
def test_orden_match_day_rechaza_formatos_invalidos(malo):
    with pytest.raises(ValueError):
        orden_match_day(malo)


# ── ua_fuerza ────────────────────────────────────────────────────────────────

def test_ua_fuerza_valor_conocido():
    # 4 series x 5 reps al 80 % = 16 UA
    assert ua_fuerza(4, 5, 80) == pytest.approx(16.0)


def test_ua_fuerza_sin_pct_rm_usa_intensidad_base():
    # 3 x 10 al 50 % base = 15 UA
    assert ua_fuerza(3, 10, np.nan, intensidad_base=50) == pytest.approx(15.0)


def test_ua_fuerza_intensidad_base_editable():
    assert ua_fuerza(3, 10, np.nan, intensidad_base=40) == pytest.approx(12.0)


def test_ua_fuerza_sin_series_devuelve_nan():
    assert np.isnan(ua_fuerza(np.nan, 5, 80))


# ── metros y alta intensidad ─────────────────────────────────────────────────

def test_metros_pasada_distancia_por_cantidad():
    assert metros_pasada(30, 4) == pytest.approx(120.0)


def test_es_alta_intensidad_incluye_el_umbral():
    assert es_alta_intensidad(85, umbral=85) is True
    assert es_alta_intensidad(84.9, umbral=85) is False


def test_es_alta_intensidad_sin_dato_es_false():
    assert es_alta_intensidad(np.nan) is False


# ── tiempo_objetivo_pasada ───────────────────────────────────────────────────

def test_tiempo_objetivo_valor_conocido():
    # 30 m a 100 % de 27 km/h (= 7,5 m/s) -> 4,0 s
    assert tiempo_objetivo_pasada(30, 27, 100) == pytest.approx(4.0)


def test_tiempo_objetivo_a_menor_porcentaje_tarda_mas():
    assert tiempo_objetivo_pasada(30, 27, 80) == pytest.approx(5.0)


def test_tiempo_objetivo_factor_menor_a_uno_tarda_mas():
    assert tiempo_objetivo_pasada(30, 27, 100, factor_distancia=0.9) > 4.0


@pytest.mark.parametrize("args", [(0, 27, 90), (30, 0, 90), (30, 27, 0), (30, np.nan, 90)])
def test_tiempo_objetivo_rechaza_datos_invalidos(args):
    with pytest.raises(ValueError):
        tiempo_objetivo_pasada(*args)


# ── resumir_plan_por_md ──────────────────────────────────────────────────────

def test_resumen_por_md_separa_dias_y_ordena():
    df = _items([
        ["MD-2", "fuerza", 3, 8, 70, np.nan, np.nan],
        ["MD-5", "fuerza", 4, 5, 80, np.nan, np.nan],
        ["MD-5", "fuerza", 3, 10, np.nan, np.nan, np.nan],   # sin %RM -> base 50 %
        ["MD-4", "pasada", 4, 4, np.nan, 30, 90],             # 4 pasadas x 30 m
    ])
    out = resumir_plan_por_md(df).set_index("match_day")
    assert list(out.index) == ["MD-5", "MD-4", "MD-2"]
    assert out.loc["MD-5", "ua_fuerza"] == pytest.approx(16 + 15)
    assert out.loc["MD-5", "ejercicios_fuerza"] == 2
    assert out.loc["MD-2", "ua_fuerza"] == pytest.approx(3 * 8 * 0.70)


def test_resumen_por_md_metros_totales_y_alta_intensidad():
    df = _items([
        ["MD-4", "pasada", np.nan, 4, np.nan, 30, 90],   # 120 m, alta
        ["MD-4", "pasada", np.nan, 6, np.nan, 20, 70],   # 120 m, no alta
    ])
    fila = resumir_plan_por_md(df).iloc[0]
    assert fila["metros_pasadas"] == pytest.approx(240.0)
    assert fila["metros_alta_intensidad"] == pytest.approx(120.0)
    assert fila["ua_fuerza"] == 0.0


def test_resumen_por_md_usa_umbral_editable():
    df = _items([["MD-4", "pasada", np.nan, 4, np.nan, 30, 80]])
    fila = resumir_plan_por_md(df, {"umbral_alta_intensidad_vmax": 75}).iloc[0]
    assert fila["metros_alta_intensidad"] == pytest.approx(120.0)


def test_resumen_por_md_avisa_pasadas_sin_pct_vmax():
    df = _items([["MD-4", "pasada", np.nan, 4, np.nan, 30, np.nan]])
    fila = resumir_plan_por_md(df).iloc[0]
    assert fila["metros_pasadas"] == pytest.approx(120.0)
    assert fila["metros_alta_intensidad"] == 0.0
    assert fila["pasadas_sin_pct_vmax"] == 1


def test_resumen_por_md_vacio_devuelve_columnas_sin_filas():
    out = resumir_plan_por_md(_items([]))
    assert out.empty
    assert "ua_fuerza" in out.columns


def test_resumen_por_md_no_modifica_el_dataframe_de_entrada():
    df = _items([["MD-5", "fuerza", 4, 5, 80, np.nan, np.nan]])
    copia = df.copy()
    resumir_plan_por_md(df)
    pd.testing.assert_frame_equal(df, copia)


# ── resumir_plan_semana ──────────────────────────────────────────────────────

def test_resumen_semana_suma_los_dias():
    df = _items([
        ["MD-5", "fuerza", 4, 5, 80, np.nan, np.nan],
        ["MD-2", "fuerza", 3, 8, 70, np.nan, np.nan],
        ["MD-4", "pasada", np.nan, 4, np.nan, 30, 90],
    ])
    sem = resumir_plan_semana(df)
    assert sem["ua_fuerza"] == pytest.approx(16 + 16.8)
    assert sem["metros_pasadas"] == pytest.approx(120.0)
    assert sem["metros_alta_intensidad"] == pytest.approx(120.0)


def test_resumen_semana_vacia_es_cero():
    assert resumir_plan_semana(_items([]))["ua_fuerza"] == 0.0


# ── armar_items_plan ─────────────────────────────────────────────────────────

from src.metrics.fuerza_plan import armar_items_plan


def _editado(filas):
    cols = ["match_day", "tipo", "ejercicio_id", "ejercicio_nombre", "series", "repeticiones",
            "pct_rm", "distancia_m", "zona", "pct_vmax", "pausa_s", "notas"]
    return pd.DataFrame(filas, columns=cols)


def test_armar_items_numera_el_orden_por_match_day():
    df = _editado([
        ["MD-5", "fuerza", "FZA-001", "Sentadilla frontal", 4, 5, 80, np.nan, "", np.nan, 90, ""],
        ["MD-2", "fuerza", "FZA-003", "Hip thrust", 3, 8, 70, np.nan, "", np.nan, 90, ""],
        ["MD-5", "fuerza", "FZA-005", "Banco plano", 4, 6, 75, np.nan, "", np.nan, 90, ""],
    ])
    out, avisos = armar_items_plan(df)
    assert avisos == []
    assert list(zip(out["match_day"], out["orden"])) == [("MD-5", 1), ("MD-5", 2), ("MD-2", 1)]


def test_armar_items_descarta_filas_invalidas_y_avisa():
    df = _editado([
        ["MD-5", "fuerza", "FZA-001", "Sentadilla frontal", np.nan, 5, 80, np.nan, "", np.nan, np.nan, ""],  # sin series
        ["MD-9x", "fuerza", "FZA-002", "Sentadilla trasera", 4, 5, 80, np.nan, "", np.nan, np.nan, ""],      # MD malo
        ["MD-4", "pasada", "FZA-001", "x", np.nan, 4, np.nan, 30, "", 90, np.nan, ""],                       # prefijo no coincide
        ["MD-4", "pasada", "RES-006", "Pasadas x4", np.nan, 4, np.nan, np.nan, "", 90, np.nan, ""],          # sin distancia
        ["MD-4", "pasada", "RES-006", "Pasadas x4", np.nan, 4, np.nan, 30, "", 90, np.nan, ""],              # válida
    ])
    out, avisos = armar_items_plan(df)
    assert len(out) == 1
    assert len(avisos) == 4


def test_armar_items_porcentajes_fuera_de_rango_quedan_vacios_pero_la_fila_se_conserva():
    df = _editado([["MD-5", "fuerza", "FZA-001", "Sentadilla frontal", 4, 5, 999, np.nan, "", np.nan, np.nan, ""]])
    out, avisos = armar_items_plan(df)
    assert len(out) == 1
    assert np.isnan(out.loc[0, "pct_rm"])
    assert len(avisos) == 1


def test_armar_items_vacio_devuelve_columnas():
    out, avisos = armar_items_plan(_editado([]))
    assert out.empty and avisos == []
    assert "orden" in out.columns


# ── etiquetas y conversión editor <-> ítems ──────────────────────────────────

from src.metrics.fuerza_plan import (
    etiqueta_ejercicio, items_a_editores, editores_a_items,
    COLS_EDITOR_FUERZA, COLS_EDITOR_PASADAS,
)

ETIQUETAS = {
    "FZA-001": "Sentadilla frontal",
    "FZA-003": "Hip thrust",
    "RES-006": "Pasadas · RES-006",
    "RES-007": "Pasadas · RES-007",
}
IDS = {
    "Sentadilla frontal": ("FZA-001", "Sentadilla frontal"),
    "Hip thrust": ("FZA-003", "Hip thrust"),
    "Pasadas · RES-006": ("RES-006", "Pasadas"),
    "Pasadas · RES-007": ("RES-007", "Pasadas"),
}


def test_etiqueta_distingue_pasadas_con_el_mismo_nombre():
    assert etiqueta_ejercicio("Pasadas", "RES-006", "pasada") != etiqueta_ejercicio("Pasadas", "RES-007", "pasada")
    assert etiqueta_ejercicio("Hip thrust", "FZA-003", "fuerza") == "Hip thrust"


def test_editores_a_items_resuelve_ids_y_tipos():
    fz = pd.DataFrame([["Sentadilla frontal", 4, 5, 80, 90, ""]], columns=COLS_EDITOR_FUERZA)
    ps = pd.DataFrame([["Pasadas · RES-007", 4, 30, 90, "", 120, ""]], columns=COLS_EDITOR_PASADAS)
    out = editores_a_items("MD-4", fz, ps, IDS)
    assert list(out["tipo"]) == ["fuerza", "pasada"]
    assert list(out["ejercicio_id"]) == ["FZA-001", "RES-007"]
    assert list(out["ejercicio_nombre"]) == ["Sentadilla frontal", "Pasadas"]
    assert out.loc[1, "distancia_m"] == 30 and out.loc[1, "repeticiones"] == 4


def test_editores_a_items_ignora_filas_en_blanco():
    fz = pd.DataFrame([[None, None, None, None, None, None]], columns=COLS_EDITOR_FUERZA)
    out = editores_a_items("MD-5", fz, pd.DataFrame(columns=COLS_EDITOR_PASADAS), IDS)
    assert out.empty


def test_ida_y_vuelta_editor_items_conserva_los_datos():
    fz = pd.DataFrame([["Sentadilla frontal", 4, 5, 80, 90, "técnica"],
                       ["Hip thrust", 3, 8, 70, 60, ""]], columns=COLS_EDITOR_FUERZA)
    ps = pd.DataFrame([["Pasadas · RES-006", 4, 30, 90, "Z4", 120, ""]], columns=COLS_EDITOR_PASADAS)
    items, avisos = armar_items_plan(editores_a_items("MD-4", fz, ps, IDS))
    assert avisos == []
    fz2, ps2 = items_a_editores(items, "MD-4", ETIQUETAS)
    assert list(fz2["Ejercicio"]) == ["Sentadilla frontal", "Hip thrust"]
    assert list(fz2["%RM"]) == [80, 70]
    assert list(ps2["Pasada"]) == ["Pasadas · RES-006"]
    assert ps2.loc[0, "Distancia (m)"] == 30 and ps2.loc[0, "Zona"] == "Z4"


def test_items_a_editores_filtra_por_match_day():
    items, _ = armar_items_plan(editores_a_items(
        "MD-5", pd.DataFrame([["Hip thrust", 3, 8, 70, 60, ""]], columns=COLS_EDITOR_FUERZA),
        pd.DataFrame(columns=COLS_EDITOR_PASADAS), IDS))
    fz, ps = items_a_editores(items, "MD-2", ETIQUETAS)
    assert fz.empty and ps.empty
    assert list(fz.columns) == COLS_EDITOR_FUERZA


def test_items_a_editores_usa_el_nombre_guardado_si_el_ejercicio_salio_del_catalogo():
    items, _ = armar_items_plan(editores_a_items(
        "MD-5", pd.DataFrame([["Hip thrust", 3, 8, 70, 60, ""]], columns=COLS_EDITOR_FUERZA),
        pd.DataFrame(columns=COLS_EDITOR_PASADAS), IDS))
    fz, _ = items_a_editores(items, "MD-5", etiquetas={})   # catálogo sin ese ID
    assert list(fz["Ejercicio"]) == ["Hip thrust"]
