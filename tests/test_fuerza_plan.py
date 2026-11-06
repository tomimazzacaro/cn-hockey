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


def _fz(md, ej_id, nombre, ss, pausa=np.nan):
    """Fila de fuerza con superserie (columna 'superserie' al final)."""
    return [md, "fuerza", ej_id, nombre, 3, 8, 70, np.nan, "", np.nan, pausa, "", ss]


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
    COLS_EDITOR_FUERZA, COLS_EDITOR_PASADAS, COLUMNAS_ITEM_PLAN,
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
    fz = pd.DataFrame([["Sentadilla frontal", None, 4, 5, 80, 90, ""]], columns=COLS_EDITOR_FUERZA)
    ps = pd.DataFrame([["Pasadas · RES-007", 4, 30, 90, "", 120, ""]], columns=COLS_EDITOR_PASADAS)
    out = editores_a_items("MD-4", fz, ps, IDS)
    assert list(out["tipo"]) == ["fuerza", "pasada"]
    assert list(out["ejercicio_id"]) == ["FZA-001", "RES-007"]
    assert list(out["ejercicio_nombre"]) == ["Sentadilla frontal", "Pasadas"]
    assert out.loc[1, "distancia_m"] == 30 and out.loc[1, "repeticiones"] == 4


def test_editores_a_items_ignora_filas_en_blanco():
    fz = pd.DataFrame([[None, None, None, None, None, None, None]], columns=COLS_EDITOR_FUERZA)
    out = editores_a_items("MD-5", fz, pd.DataFrame(columns=COLS_EDITOR_PASADAS), IDS)
    assert out.empty


def test_ida_y_vuelta_editor_items_conserva_los_datos():
    fz = pd.DataFrame([["Sentadilla frontal", None, 4, 5, 80, 90, "técnica"],
                       ["Hip thrust", None, 3, 8, 70, 60, ""]], columns=COLS_EDITOR_FUERZA)
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
        "MD-5", pd.DataFrame([["Hip thrust", None, 3, 8, 70, 60, ""]], columns=COLS_EDITOR_FUERZA),
        pd.DataFrame(columns=COLS_EDITOR_PASADAS), IDS))
    fz, ps = items_a_editores(items, "MD-2", ETIQUETAS)
    assert fz.empty and ps.empty
    assert list(fz.columns) == COLS_EDITOR_FUERZA


def test_items_a_editores_usa_el_nombre_guardado_si_el_ejercicio_salio_del_catalogo():
    items, _ = armar_items_plan(editores_a_items(
        "MD-5", pd.DataFrame([["Hip thrust", None, 3, 8, 70, 60, ""]], columns=COLS_EDITOR_FUERZA),
        pd.DataFrame(columns=COLS_EDITOR_PASADAS), IDS))
    fz, _ = items_a_editores(items, "MD-5", etiquetas={})   # catálogo sin ese ID
    assert list(fz["Ejercicio"]) == ["Hip thrust"]


def test_armar_items_pasada_sin_cantidad_se_descarta_con_aviso():
    df = _editado([["MD-4", "pasada", "RES-006", "Pasadas x4", np.nan, np.nan, np.nan, 30, "", 90, np.nan, ""]])
    out, avisos = armar_items_plan(df)
    assert out.empty
    assert len(avisos) == 1 and "cantidad de pasadas" in avisos[0]


# ── superserie ───────────────────────────────────────────────────────────────

def _con_superserie(filas):
    cols = ["match_day", "tipo", "ejercicio_id", "ejercicio_nombre", "series", "repeticiones",
            "pct_rm", "distancia_m", "zona", "pct_vmax", "pausa_s", "notas", "superserie"]
    return pd.DataFrame(filas, columns=cols)


def test_superserie_valida_se_conserva_y_se_normaliza():
    df = _con_superserie([
        _fz("MD-5", "FZA-001", "Sentadilla frontal", " a ", 120),
        _fz("MD-5", "FZA-003", "Hip thrust", "A"),
        _fz("MD-5", "FZA-005", "Banco plano", None, 90),
    ])
    out, avisos = armar_items_plan(df)
    assert avisos == []
    assert list(out["superserie"]) == ["A", "A", ""]


def test_superserie_con_letra_invalida_se_vacia_y_avisa():
    out, avisos = armar_items_plan(_con_superserie([_fz("MD-5", "FZA-001", "Sentadilla frontal", "Z9", 90)]))
    assert len(out) == 1 and out.loc[0, "superserie"] == ""
    assert len(avisos) == 1 and "superserie" in avisos[0].lower()


def test_superserie_en_una_pasada_se_ignora():
    df = _con_superserie([["MD-4", "pasada", "RES-006", "Pasadas", np.nan, 4, np.nan, 30, "", 90, np.nan, "", "A"]])
    out, _ = armar_items_plan(df)
    assert out.loc[0, "superserie"] == ""


def test_superserie_avisa_si_hay_mas_de_una_pausa_en_el_grupo():
    df = _con_superserie([
        _fz("MD-5", "FZA-001", "Sentadilla frontal", "A", 120),
        _fz("MD-5", "FZA-003", "Hip thrust", "A", 60),
    ])
    out, avisos = armar_items_plan(df)
    assert len(out) == 2                      # solo avisa: no descarta ni cambia las pausas
    assert list(out["pausa_s"]) == [120, 60]
    assert len(avisos) == 1 and "pausa" in avisos[0].lower() and "A" in avisos[0]


def test_superserie_con_una_sola_pausa_no_avisa():
    df = _con_superserie([
        _fz("MD-5", "FZA-001", "Sentadilla frontal", "A", 120),
        _fz("MD-5", "FZA-003", "Hip thrust", "A"),
    ])
    assert armar_items_plan(df)[1] == []


def test_superserie_la_misma_letra_en_distinto_match_day_son_grupos_distintos():
    df = _con_superserie([
        _fz("MD-5", "FZA-001", "Sentadilla frontal", "A", 120),
        _fz("MD-5", "FZA-003", "Hip thrust", "A"),
        _fz("MD-4", "FZA-001", "Sentadilla frontal", "A", 120),
        _fz("MD-4", "FZA-003", "Hip thrust", "A"),
    ])
    assert armar_items_plan(df)[1] == []


def test_superserie_de_un_solo_ejercicio_avisa():
    out, avisos = armar_items_plan(_con_superserie([_fz("MD-5", "FZA-001", "Sentadilla frontal", "B", 90)]))
    assert len(out) == 1
    assert len(avisos) == 1 and "un solo ejercicio" in avisos[0]


def test_superserie_ida_y_vuelta_editor_items():
    fz = pd.DataFrame([["Sentadilla frontal", "A", 4, 5, 80, 120, ""],
                       ["Hip thrust", "A", 4, 8, 70, None, ""]], columns=COLS_EDITOR_FUERZA)
    items, avisos = armar_items_plan(editores_a_items("MD-4", fz, pd.DataFrame(columns=COLS_EDITOR_PASADAS), IDS))
    assert avisos == []
    fz2, _ = items_a_editores(items, "MD-4", ETIQUETAS)
    assert list(fz2["Superserie"]) == ["A", "A"]


def test_items_a_editores_tolera_items_sin_columna_superserie():
    # lo ejecutado (ejecutado_a_plan) no trae superserie: no debe romper el editor
    items = pd.DataFrame([["MD-5", 1, "fuerza", "FZA-003", "Hip thrust", 3, 8, 70, np.nan, None, np.nan, 60, None]],
                         columns=[c for c in COLUMNAS_ITEM_PLAN if c != "superserie"])
    fz, _ = items_a_editores(items, "MD-5", ETIQUETAS)
    assert list(fz["Ejercicio"]) == ["Hip thrust"]
    assert fz["Superserie"].isna().all() or (fz["Superserie"] == "").all()


# ── match_day_para_fecha ─────────────────────────────────────────────────────

from datetime import date
from src.metrics.fuerza_plan import match_day_para_fecha


@pytest.mark.parametrize("fecha, esperado", [
    (date(2026, 11, 2), "MD-5"),    # lunes
    (date(2026, 11, 3), "MD-4"),    # martes
    (date(2026, 11, 5), "MD-2"),    # jueves
    (date(2026, 11, 4), None),      # miércoles: no se entrena
    (date(2026, 11, 6), None),      # viernes
    (date(2026, 11, 7), None),      # sábado (partido)
    (date(2026, 11, 8), None),      # domingo
])
def test_match_day_para_fecha_segun_el_dia_de_entrenamiento(fecha, esperado):
    assert match_day_para_fecha(fecha) == esperado


def test_match_day_para_fecha_acepta_datetime():
    from datetime import datetime
    assert match_day_para_fecha(datetime(2026, 11, 3, 18, 30)) == "MD-4"


# ── plan_tiene_cambios (¿hay algo sin guardar?) ──────────────────────────────

from src.metrics.fuerza_plan import plan_tiene_cambios


def _guardado():
    """Plan 'guardado' tal como lo devuelve la base: trae 'id' y vacíos como None/NaN."""
    items, _ = armar_items_plan(_con_superserie([
        _fz("MD-5", "FZA-001", "Sentadilla frontal", "A", 120),
        _fz("MD-5", "FZA-003", "Hip thrust", "A"),
        _fz("MD-4", "FZA-005", "Banco plano", None, 90),
    ]))
    items = items.assign(id=["i1", "i2", "i3"])
    return items.replace("", None)       # la base devuelve NULL, no ""


def _copia_editada():
    items, _ = armar_items_plan(_con_superserie([
        _fz("MD-5", "FZA-001", "Sentadilla frontal", "A", 120),
        _fz("MD-5", "FZA-003", "Hip thrust", "A"),
        _fz("MD-4", "FZA-005", "Banco plano", None, 90),
    ]))
    return items


def test_cambios_sin_tocar_nada_no_hay_cambios_aunque_la_base_traiga_none_y_id():
    assert plan_tiene_cambios(_guardado(), _copia_editada()) is False


def test_cambios_detecta_un_valor_modificado():
    ed = _copia_editada()
    ed.loc[0, "series"] = 5
    assert plan_tiene_cambios(_guardado(), ed) is True


def test_cambios_detecta_un_ejercicio_agregado_y_uno_quitado():
    ed = _copia_editada()
    assert plan_tiene_cambios(_guardado(), ed.iloc[:-1]) is True
    extra, _ = armar_items_plan(_con_superserie([_fz("MD-2", "FZA-001", "Sentadilla frontal", None, 90)]))
    assert plan_tiene_cambios(_guardado(), pd.concat([ed, extra], ignore_index=True)) is True


def test_cambios_detecta_cambio_de_superserie_y_de_orden():
    ed = _copia_editada()
    ed.loc[1, "superserie"] = "B"
    assert plan_tiene_cambios(_guardado(), ed) is True
    ed2 = _copia_editada()
    ed2.loc[[0, 1], ["ejercicio_id", "ejercicio_nombre"]] = ed2.loc[[1, 0], ["ejercicio_id", "ejercicio_nombre"]].to_numpy()
    assert plan_tiene_cambios(_guardado(), ed2) is True


def test_cambios_plan_nuevo_vacio_no_cuenta_como_cambio_y_con_ejercicios_si():
    vacio = pd.DataFrame(columns=COLUMNAS_ITEM_PLAN)
    assert plan_tiene_cambios(vacio, vacio) is False
    assert plan_tiene_cambios(vacio, _copia_editada()) is True


def test_cambios_borrar_todo_de_un_plan_guardado_es_un_cambio():
    assert plan_tiene_cambios(_guardado(), pd.DataFrame(columns=COLUMNAS_ITEM_PLAN)) is True


def test_cambios_cabecera_de_un_plan_guardado_cuenta_pero_espacios_no():
    base = {"nombre": "Semana A", "estado": "borrador", "notas": ""}
    assert plan_tiene_cambios(_guardado(), _copia_editada(), base, dict(base)) is False
    assert plan_tiene_cambios(_guardado(), _copia_editada(), base, {**base, "estado": "publicado"}) is True
    assert plan_tiene_cambios(_guardado(), _copia_editada(), base, {**base, "nombre": "Otra"}) is True
    assert plan_tiene_cambios(_guardado(), _copia_editada(), base, {**base, "notas": "algo"}) is True
    assert plan_tiene_cambios(_guardado(), _copia_editada(), base, {**base, "nombre": " Semana A "}) is False


def test_cambios_sin_plan_guardado_la_cabecera_sola_no_cuenta():
    vacio = pd.DataFrame(columns=COLUMNAS_ITEM_PLAN)
    assert plan_tiene_cambios(vacio, vacio, None, {"nombre": "x", "estado": "publicado", "notas": "y"}) is False


# ── variación semana a semana ────────────────────────────────────────────────

from src.metrics.fuerza_plan import resumen_semana_completo, variacion_porcentual, variaciones_semana


@pytest.mark.parametrize("actual, anterior, esperado", [
    (110, 100, 10.0),
    (80, 100, -20.0),
    (100, 100, 0.0),
    (0, 100, -100.0),
])
def test_variacion_porcentual_sube_baja_o_igual(actual, anterior, esperado):
    assert variacion_porcentual(actual, anterior) == pytest.approx(esperado)


@pytest.mark.parametrize("anterior", [0, 0.0, None, float("nan"), -5])
def test_variacion_porcentual_sin_referencia_valida_devuelve_none(anterior):
    assert variacion_porcentual(50, anterior) is None


def test_resumen_semana_completo_suma_conteos_a_los_totales():
    df = _items([
        ["MD-5", "fuerza", 4, 5, 80, np.nan, np.nan],
        ["MD-5", "fuerza", 3, 8, 70, np.nan, np.nan],
        ["MD-4", "pasada", np.nan, 4, np.nan, 30, 90],
    ])
    r = resumen_semana_completo(df)
    assert r["ejercicios_fuerza"] == 2 and r["pasadas"] == 1
    assert r["ua_fuerza"] == pytest.approx(32.8) and r["metros_pasadas"] == pytest.approx(120.0)


def test_resumen_semana_completo_vacio_es_todo_cero():
    r = resumen_semana_completo(_items([]))
    assert r["ejercicios_fuerza"] == 0 and r["pasadas"] == 0 and r["ua_fuerza"] == 0.0


def test_variaciones_semana_compara_cada_indicador():
    actual = {"ua_fuerza": 33.0, "metros_pasadas": 120.0, "metros_alta_intensidad": 120.0,
              "ejercicios_fuerza": 2, "pasadas": 1}
    anterior = {"ua_fuerza": 30.0, "metros_pasadas": 0.0, "metros_alta_intensidad": 240.0,
                "ejercicios_fuerza": 2, "pasadas": 2}
    v = variaciones_semana(actual, anterior)
    assert v["ua_fuerza"] == pytest.approx(10.0)
    assert v["metros_pasadas"] is None                 # la semana anterior no tenía pasadas
    assert v["metros_alta_intensidad"] == pytest.approx(-50.0)
    assert v["ejercicios_fuerza"] == pytest.approx(0.0)
    assert v["pasadas"] == pytest.approx(-50.0)


def test_variaciones_semana_sin_semana_anterior_son_todas_none():
    actual = {"ua_fuerza": 33.0, "metros_pasadas": 1.0, "metros_alta_intensidad": 1.0,
              "ejercicios_fuerza": 2, "pasadas": 1}
    assert set(variaciones_semana(actual, None).values()) == {None}
