import pandas as pd

from settings import TIPOS_SESION
from src.metrics.reporte_semanal import (
    AMARILLO, CORRELACION_MIN_N, ROJO, VERDE, Senal, VeredictoJugadora,
    _interpretar_correlacion, armar_veredictos_semana, correlaciones_temporada,
    definir_semana_reporte, detectar_caida_cronica, evaluar_jugadora_semana,
    foda_periodizacion_semana, plan_de_accion, resumen_ejecutivo,
    tabla_foda_periodizacion, tabla_kpis_semana,
)

FECHA_FIN = pd.Timestamp("2026-08-24").date()


def _gps_dia(fecha, acwr=1.0, zona="Óptimo", **zscores):
    fila = {"fecha": fecha, "acwr": acwr, "zona_acwr": zona}
    fila.update(zscores)
    return fila


def _wellness_dia(fecha, tqr=8, rpe=5, molestia_flag=False, molestia="Sin molestias"):
    return {"fecha": fecha, "tqr": tqr, "rpe": rpe, "molestia_flag": molestia_flag, "molestia": molestia}


def test_sin_senales_da_verde():
    df_gps = pd.DataFrame([_gps_dia(FECHA_FIN)])
    df_well = pd.DataFrame([_wellness_dia(FECHA_FIN) for _ in range(3)])
    v = evaluar_jugadora_semana("ana", "Ana", "Defensora", df_gps, df_gps, df_well, FECHA_FIN)
    assert v.semaforo == VERDE
    assert v.senales == []


def test_una_sola_senal_da_amarillo():
    # ACWR en Precaución (1.4) es UNA señal física, sin nada de wellness.
    df_gps = pd.DataFrame([_gps_dia(FECHA_FIN, acwr=1.4, zona="Precaución")])
    df_well = pd.DataFrame([_wellness_dia(FECHA_FIN) for _ in range(3)])
    v = evaluar_jugadora_semana("ana", "Ana", "Defensora", df_gps, df_gps, df_well, FECHA_FIN)
    assert v.semaforo == AMARILLO
    assert len(v.senales) == 1


def test_dos_senales_simultaneas_dan_rojo():
    # ACWR fuera de rango (Precaución, no Riesgo Alto) + molestia reportada
    # = 2 señales -> Rojo, aunque ninguna cruce el umbral fuerte por sí sola.
    df_gps = pd.DataFrame([_gps_dia(FECHA_FIN, acwr=1.4, zona="Precaución")])
    df_well = pd.DataFrame([
        _wellness_dia(FECHA_FIN, molestia_flag=True, molestia="Dolor de cadera"),
    ] + [_wellness_dia(FECHA_FIN - pd.Timedelta(days=i).to_pytimedelta()) for i in range(1, 3)])
    v = evaluar_jugadora_semana("ana", "Ana", "Defensora", df_gps, df_gps, df_well, FECHA_FIN)
    assert v.semaforo == ROJO
    assert len(v.senales) == 2
    assert "reducir" in v.recomendacion.lower() or "evaluar" in v.recomendacion.lower()


def test_riesgo_alto_es_rojo_aunque_sea_la_unica_senal():
    # Cruce de umbral fuerte (ACWR >= 1.5, "Riesgo Alto") -> Rojo aunque no
    # haya ninguna otra señal simultánea (regla dura del proyecto).
    df_gps = pd.DataFrame([_gps_dia(FECHA_FIN, acwr=1.7, zona="Riesgo Alto")])
    df_well = pd.DataFrame([_wellness_dia(FECHA_FIN) for _ in range(3)])
    v = evaluar_jugadora_semana("ana", "Ana", "Defensora", df_gps, df_gps, df_well, FECHA_FIN)
    assert v.semaforo == ROJO


def test_wellness_con_menos_de_3_registros_no_marca_sostenido():
    # TQR bajo pero con un solo registro en la semana -> no es "sostenido",
    # un dato aislado no es un patrón todavía.
    df_gps = pd.DataFrame([_gps_dia(FECHA_FIN)])
    df_well = pd.DataFrame([_wellness_dia(FECHA_FIN, tqr=2)])
    v = evaluar_jugadora_semana("ana", "Ana", "Defensora", df_gps, df_gps, df_well, FECHA_FIN)
    assert v.semaforo == VERDE


def test_dia_con_fisico_y_tt_no_duplica_la_senal_de_acwr():
    # Dos filas el mismo día (Físico + Técnico-Táctico) comparten el mismo
    # acwr/zona -> debe contar como UNA sola señal, no dos.
    df_gps = pd.DataFrame([
        _gps_dia(FECHA_FIN, acwr=1.4, zona="Precaución"),
        _gps_dia(FECHA_FIN, acwr=1.4, zona="Precaución"),
    ])
    df_well = pd.DataFrame([_wellness_dia(FECHA_FIN) for _ in range(3)])
    v = evaluar_jugadora_semana("ana", "Ana", "Defensora", df_gps, df_gps, df_well, FECHA_FIN)
    assert len(v.senales) == 1
    assert v.semaforo == AMARILLO


def test_caida_cronica_detectada():
    fechas = [FECHA_FIN - pd.Timedelta(days=d).to_pytimedelta() for d in (21, 0)]
    df_hist = pd.DataFrame([
        {"fecha": fechas[0], "ewma_cronica": 500.0},
        {"fecha": fechas[1], "ewma_cronica": 300.0},  # cayó 40%
    ])
    senal = detectar_caida_cronica(df_hist, FECHA_FIN)
    assert senal is not None
    assert "40%" in senal.texto


def test_caida_cronica_sin_historial_suficiente_no_marca_nada():
    df_hist = pd.DataFrame([{"fecha": FECHA_FIN, "ewma_cronica": 300.0}])
    assert detectar_caida_cronica(df_hist, FECHA_FIN) is None


def test_definir_semana_reporte_usa_el_ultimo_microciclo_completo():
    df_sesiones = pd.DataFrame([
        {"fecha": pd.Timestamp("2026-08-08").date(), "match_day": "MD"},
        {"fecha": pd.Timestamp("2026-08-15").date(), "match_day": "MD"},
        {"fecha": pd.Timestamp("2026-08-22").date(), "match_day": "MD"},
        # Fixture futuro ya cargado en la hoja — no debe usarse sin tope.
        {"fecha": pd.Timestamp("2026-09-30").date(), "match_day": "MD"},
    ])
    rango = definir_semana_reporte(df_sesiones, fecha_maxima=pd.Timestamp("2026-08-24").date())
    assert rango == (pd.Timestamp("2026-08-16").date(), pd.Timestamp("2026-08-22").date())


def test_definir_semana_reporte_none_sin_dos_md():
    df_sesiones = pd.DataFrame([{"fecha": pd.Timestamp("2026-08-08").date(), "match_day": "MD"}])
    assert definir_semana_reporte(df_sesiones, fecha_maxima=pd.Timestamp("2026-08-10").date()) is None


def test_armar_veredictos_semana_incluye_jugadora_solo_con_wellness():
    # Sin GPS esa semana pero con wellness -> igual debe aparecer evaluada
    # (una jugadora lesionada/sin entrenar sigue reportando wellness).
    df_gps = pd.DataFrame(columns=["player_id", "nombre", "fecha", "acwr", "zona_acwr"])
    df_well = pd.DataFrame([
        {"player_id": "ana", "nombre": "Ana", "fecha": FECHA_FIN, "tqr": 8, "rpe": 5,
         "molestia_flag": False, "molestia": "Sin molestias"},
    ])
    df_roster = pd.DataFrame([{"player_id": "ana", "posicion": "Defensora"}])
    veredictos = armar_veredictos_semana(df_gps, df_well, df_roster, FECHA_FIN, FECHA_FIN)
    assert len(veredictos) == 1
    assert veredictos[0].nombre == "Ana"
    assert veredictos[0].semaforo == VERDE


def test_tabla_kpis_promedia_por_dia_no_por_sesion_suelta():
    # Ana tiene 2 sesiones el mismo día (Físico + Técnico-Táctico) que suman
    # 1000 de distancia_total en un único día de la semana. Compañera Bea
    # tiene 1 sola sesión de 400 otro día. El promedio diario de POSICIÓN
    # tiene que ser (1000 + 400) / 2 = 700 -- NO el promedio de las 3 filas
    # sueltas (1000/2=500 en el día de Ana cuenta como 2 valores de 500),
    # que daría un número distinto y subestimado.
    df_semana = pd.DataFrame([
        {"player_id": "ana", "nombre": "Ana", "posicion": "Defensora",
         "fecha": FECHA_FIN, "distancia_total": 600.0},
        {"player_id": "ana", "nombre": "Ana", "posicion": "Defensora",
         "fecha": FECHA_FIN, "distancia_total": 400.0},
        {"player_id": "bea", "nombre": "Bea", "posicion": "Defensora",
         "fecha": FECHA_FIN, "distancia_total": 400.0},
    ])
    df_previo = pd.DataFrame(columns=["player_id", "fecha", "distancia_total"])
    tabla = tabla_kpis_semana(df_semana, df_previo)

    fila_ana = tabla[(tabla["player_id"] == "ana") & (tabla["metrica"] == "Distancia Total")].iloc[0]
    assert fila_ana["valor_semana"] == 1000.0  # Físico + TT del mismo día, sumados
    assert fila_ana["media_equipo_posicion"] == 700.0  # promedio de los promedios diarios (1000, 400)


# ── Tests agregados: FODA de periodización, correlaciones, plan de acción, resumen ejecutivo ──
COLUMNAS_CORRELACIONES = ["Correlación", "r", "p-valor", "n", "Interpretación", "Nota"]
COLUMNAS_PLAN = ["Prioridad", "Área", "Hallazgo", "Acción recomendada"]


def _veredicto(nombre, semaforo, senales=None):
    """Fixture mínima de VeredictoJugadora — solo importan al caso de test
    los campos que plan_de_accion()/resumen_ejecutivo() realmente leen
    (nombre, semaforo, senales, recomendacion); el resto queda en valores
    neutros, sin significado para estos tests."""
    return VeredictoJugadora(
        player_id=nombre.lower(), nombre=nombre, posicion="Defensora", semaforo=semaforo,
        senales=senales or [], recomendacion=f"Recomendación para {nombre}",
        acwr=1.0, zona_acwr="Óptimo", tqr_prom=8.0, rpe_prom=5.0, n_registros_wellness=3,
    )


# ── _interpretar_correlacion ─────────────────────────────────────────────

def test_interpretar_correlacion_n_insuficiente():
    # n por debajo del piso -> aviso de muestra chica, ni se mira el signo de r.
    resultado = _interpretar_correlacion(r=0.9, p=0.001, n=5, min_n=CORRELACION_MIN_N)
    assert "insuficiente" in resultado


def test_interpretar_correlacion_sin_significancia_no_describe_fuerza_ni_direccion():
    # p >= 0.05 con n suficiente -> "sin significancia", el r no se
    # describe como hallazgo (ni fuerza ni dirección en el texto).
    resultado = _interpretar_correlacion(r=0.6, p=0.20, n=15, min_n=10)
    assert "Sin significancia" in resultado
    assert "positiva" not in resultado and "negativa" not in resultado
    assert "fuerte" not in resultado and "débil" not in resultado and "moderada" not in resultado


def test_interpretar_correlacion_positiva_debil():
    resultado = _interpretar_correlacion(r=0.15, p=0.01, n=15, min_n=10)
    assert "Correlación positiva débil" in resultado


def test_interpretar_correlacion_positiva_moderada():
    resultado = _interpretar_correlacion(r=0.40, p=0.01, n=15, min_n=10)
    assert "Correlación positiva moderada" in resultado


def test_interpretar_correlacion_positiva_fuerte():
    resultado = _interpretar_correlacion(r=0.60, p=0.01, n=15, min_n=10)
    assert "Correlación positiva fuerte" in resultado
    assert "muy fuerte" not in resultado


def test_interpretar_correlacion_positiva_muy_fuerte():
    resultado = _interpretar_correlacion(r=0.85, p=0.01, n=15, min_n=10)
    assert "Correlación positiva muy fuerte" in resultado


def test_interpretar_correlacion_negativa():
    resultado = _interpretar_correlacion(r=-0.55, p=0.01, n=15, min_n=10)
    assert "Correlación negativa fuerte" in resultado


def test_interpretar_correlacion_r_nan_no_explota():
    # scipy puede devolver NaN cuando no hay varianza suficiente en los
    # datos -- no debe romper, tiene que devolver un string explicativo.
    resultado = _interpretar_correlacion(r=float("nan"), p=float("nan"), n=15, min_n=10)
    assert isinstance(resultado, str)
    assert "no se pudo calcular" in resultado.lower()


def test_interpretar_correlacion_p_nan_no_explota():
    resultado = _interpretar_correlacion(r=0.5, p=float("nan"), n=15, min_n=10)
    assert isinstance(resultado, str)
    assert "no se pudo calcular" in resultado.lower()


# ── correlaciones_temporada ───────────────────────────────────────────────

def test_correlaciones_temporada_vacio_devuelve_columnas_esperadas():
    resultado = correlaciones_temporada(pd.DataFrame(), pd.DataFrame())
    assert resultado.empty
    assert list(resultado.columns) == COLUMNAS_CORRELACIONES


def test_correlaciones_srpe_perfectamente_correlacionado_con_player_load():
    # duracion_min FIJA en todos los días -> sRPE = rpe * duracion queda
    # como función lineal de rpe. Si además rpe es proporcional a
    # player_load, sRPE y player_load quedan perfectamente correlacionados
    # (r ~= 1) sin necesidad de simular ruido real de campo.
    fechas = [FECHA_FIN - pd.Timedelta(days=d).to_pytimedelta() for d in range(10)]
    player_loads = [100 + 10 * i for i in range(10)]
    df_gps = pd.DataFrame([
        {"player_id": "ana", "fecha": f, "duracion_min": 60.0, "player_load": pl}
        for f, pl in zip(fechas, player_loads)
    ])
    df_well = pd.DataFrame([
        {"player_id": "ana", "fecha": f, "tqr": 8, "rpe": pl / 20}
        for f, pl in zip(fechas, player_loads)
    ])
    resultado = correlaciones_temporada(df_gps, df_well)
    fila = resultado[resultado["Correlación"].str.startswith("sRPE")].iloc[0]
    assert fila["n"] == 10
    assert fila["r"] > 0.99
    assert "Correlación positiva" in fila["Interpretación"]


def test_correlaciones_sin_columna_player_load_no_explota_y_omite_esa_fila():
    # Si al GPS histórico le falta "player_load", esa correlación puntual
    # no tiene que romper el cálculo -- simplemente no aparece en el resultado.
    fechas = [FECHA_FIN - pd.Timedelta(days=d).to_pytimedelta() for d in range(10)]
    df_gps = pd.DataFrame([{"player_id": "ana", "fecha": f, "duracion_min": 60.0} for f in fechas])
    df_well = pd.DataFrame([{"player_id": "ana", "fecha": f, "tqr": 8, "rpe": 5} for f in fechas])
    resultado = correlaciones_temporada(df_gps, df_well)
    assert not resultado["Correlación"].str.startswith("sRPE").any()


def test_correlaciones_fisico_y_tt_mismo_dia_no_pesa_doble():
    # Ana entrena Físico + Técnico-Táctico el mismo día (2 filas de GPS con
    # el mismo player_id/fecha) -- el groupby+sum por día que hace el propio
    # código tiene que colapsarlas en un solo día antes de correlacionar, así
    # que el "n" final cuenta DÍAS, no sesiones sueltas (3 días, no 4 filas).
    fechas = [FECHA_FIN - pd.Timedelta(days=d).to_pytimedelta() for d in range(3)]
    df_gps = pd.DataFrame([
        {"player_id": "ana", "fecha": fechas[0], "duracion_min": 30.0, "player_load": 50.0},
        {"player_id": "ana", "fecha": fechas[0], "duracion_min": 20.0, "player_load": 30.0},  # mismo día
        {"player_id": "ana", "fecha": fechas[1], "duracion_min": 50.0, "player_load": 80.0},
        {"player_id": "ana", "fecha": fechas[2], "duracion_min": 50.0, "player_load": 90.0},
    ])
    df_well = pd.DataFrame([
        {"player_id": "ana", "fecha": fechas[0], "tqr": 8, "rpe": 5},
        {"player_id": "ana", "fecha": fechas[1], "tqr": 8, "rpe": 6},
        {"player_id": "ana", "fecha": fechas[2], "tqr": 8, "rpe": 7},
    ])
    resultado = correlaciones_temporada(df_gps, df_well, min_n=3)
    fila = resultado[resultado["Correlación"].str.startswith("sRPE")].iloc[0]
    assert fila["n"] == 3  # 3 días, no 4 filas de GPS


# ── plan_de_accion ─────────────────────────────────────────────────────────

def test_plan_de_accion_vacio_da_dataframe_vacio():
    resultado = plan_de_accion([], {})
    assert resultado.empty
    assert list(resultado.columns) == COLUMNAS_PLAN


def test_plan_de_accion_rojo_antes_que_amarillo():
    v_amarillo = _veredicto("Bea", AMARILLO, [Senal("fisica", "ACWR 1.4 (Precaución)")])
    v_rojo = _veredicto("Ana", ROJO, [Senal("fisica", "ACWR 1.7 (Riesgo Alto)")])
    # Orden de entrada A PROPÓSITO al revés (amarillo primero) -- el orden
    # final lo tiene que dar ORDEN_PRIORIDAD, no el orden de la lista de veredictos.
    resultado = plan_de_accion([v_amarillo, v_rojo], {})
    assert list(resultado["Prioridad"]) == ["Alta", "Media"]
    assert resultado.iloc[0]["Área"] == "Ana"
    assert resultado.iloc[1]["Área"] == "Bea"


def test_plan_de_accion_verde_no_genera_fila():
    v_verde = _veredicto("Cami", VERDE, [])
    resultado = plan_de_accion([v_verde], {})
    assert resultado.empty


def test_plan_de_accion_debilidad_periodizacion_prioridad_media():
    foda = {"debilidades": ["Player Load por debajo del rango esperado en MD-4."], "amenazas": []}
    resultado = plan_de_accion([], foda)
    assert len(resultado) == 1
    assert resultado.iloc[0]["Área"] == "Equipo — periodización"
    assert resultado.iloc[0]["Prioridad"] == "Media"


def test_plan_de_accion_amenaza_de_calibracion_prioridad_baja():
    # Criterio real del código: "calibra" o "revisar el rango" en minúsculas
    # dentro del texto de la amenaza.
    foda = {"debilidades": [], "amenazas": ["HSR (MD-4): revisar el rango cargado en el Sheet antes de actuar."]}
    resultado = plan_de_accion([], foda)
    assert len(resultado) == 1
    assert resultado.iloc[0]["Prioridad"] == "Baja"
    assert resultado.iloc[0]["Área"] == "Parámetros del Sheet"


def test_plan_de_accion_amenaza_sin_texto_de_calibracion_no_genera_fila():
    # Una amenaza que no menciona calibración/rango (ej. variabilidad de
    # duración) no es responsabilidad de "Parámetros del Sheet" -> no entra al plan.
    foda = {"debilidades": [], "amenazas": ["MD-2 · Físico: duración muy variable entre sesiones."]}
    resultado = plan_de_accion([], foda)
    assert resultado.empty


# ── resumen_ejecutivo ────────────────────────────────────────────────────

def test_resumen_ejecutivo_nunca_vacio_y_primer_parrafo_con_conteo_correcto():
    veredictos = [_veredicto("Ana", ROJO), _veredicto("Bea", AMARILLO), _veredicto("Cami", VERDE)]
    parrafos = resumen_ejecutivo(veredictos, {}, pd.DataFrame())
    assert isinstance(parrafos, list) and len(parrafos) > 0
    assert "<b>3</b>" in parrafos[0]
    assert "<b>1</b> en Rojo" in parrafos[0]
    assert "<b>1</b> en Amarillo" in parrafos[0]
    assert "<b>1</b> en Verde" in parrafos[0]


def test_resumen_ejecutivo_con_rojo_menciona_prioridad_inmediata_y_nombre():
    veredictos = [_veredicto("Ana", ROJO)]
    parrafos = resumen_ejecutivo(veredictos, {}, pd.DataFrame())
    texto = " ".join(parrafos)
    assert "Prioridad inmediata" in texto
    assert "Ana" in texto


def test_resumen_ejecutivo_sin_rojo_da_parrafo_alternativo():
    veredictos = [_veredicto("Ana", VERDE)]
    parrafos = resumen_ejecutivo(veredictos, {}, pd.DataFrame())
    texto = " ".join(parrafos)
    assert "Sin jugadoras en Rojo" in texto


def test_resumen_ejecutivo_periodizacion_bien_distribuida_sin_debilidades():
    foda = {"fortalezas": ["ACWR en Óptimo en el 100% de las sesiones."], "debilidades": []}
    parrafos = resumen_ejecutivo([], foda, pd.DataFrame())
    texto = " ".join(parrafos)
    assert "bien distribuida" in texto


def test_resumen_ejecutivo_con_debilidades_menciona_puntos_a_revisar():
    foda = {"fortalezas": [], "debilidades": ["HSR por debajo del rango en MD-4."]}
    parrafos = resumen_ejecutivo([], foda, pd.DataFrame())
    texto = " ".join(parrafos)
    assert "punto(s) a revisar" in texto


# ── tabla_foda_periodizacion ──────────────────────────────────────────────

def test_tabla_foda_con_items_en_las_4_listas():
    foda = {
        "fortalezas": ["ACWR en Óptimo el 100% de las sesiones."],
        "debilidades": ["Player Load por debajo del rango en MD-4."],
        "oportunidades": ["Prescribir carga diferenciada por puesto."],
        "amenazas": ["Revisar el rango cargado en el Sheet."],
    }
    tabla = tabla_foda_periodizacion(foda)
    assert list(tabla.columns) == ["Cuadrante", "Hallazgo"]
    assert len(tabla) == 4
    assert set(tabla["Cuadrante"]) == {"Fortaleza", "Debilidad", "Oportunidad", "Amenaza"}
    fila_debilidad = tabla[tabla["Cuadrante"] == "Debilidad"].iloc[0]
    assert fila_debilidad["Hallazgo"] == "Player Load por debajo del rango en MD-4."


def test_tabla_foda_vacio_da_dataframe_con_columnas_pero_sin_filas():
    foda = {"fortalezas": [], "debilidades": [], "oportunidades": [], "amenazas": []}
    tabla = tabla_foda_periodizacion(foda)
    assert tabla.empty
    assert list(tabla.columns) == ["Cuadrante", "Hallazgo"]


# ── foda_periodizacion_semana ──────────────────────────────────────────────

def test_foda_periodizacion_semana_vacio_no_explota():
    resultado = foda_periodizacion_semana(pd.DataFrame(), pd.DataFrame())
    assert resultado == {"fortalezas": [], "debilidades": [], "oportunidades": [], "amenazas": []}


def test_foda_periodizacion_semana_excluye_partido_del_acwr():
    # 3 sesiones de entrenamiento en zona Óptimo + 1 Partido en Riesgo Alto:
    # si el Partido entrara al cálculo, el % Óptimo bajaría de 100% a 83% --
    # que el bullet siga diciendo 100% confirma que Partido quedó afuera.
    filas = [
        {"tipo_sesion": TIPOS_SESION[0], "match_day": "MD-4", "fecha": FECHA_FIN,
         "posicion": "Defensora", "zona_acwr": "Óptimo"},
        {"tipo_sesion": TIPOS_SESION[1], "match_day": "MD-4", "fecha": FECHA_FIN,
         "posicion": "Defensora", "zona_acwr": "Óptimo"},
        {"tipo_sesion": TIPOS_SESION[0], "match_day": "MD-2", "fecha": FECHA_FIN,
         "posicion": "Delantera", "zona_acwr": "Óptimo"},
        {"tipo_sesion": TIPOS_SESION[2], "match_day": "MD-4", "fecha": FECHA_FIN,
         "posicion": "Defensora", "zona_acwr": "Riesgo Alto"},  # Partido -- debe excluirse
    ]
    df_gps = pd.DataFrame(filas)
    resultado = foda_periodizacion_semana(df_gps, pd.DataFrame())
    fortalezas_texto = " ".join(resultado["fortalezas"])
    assert "100%" in fortalezas_texto
    assert "Óptimo" in fortalezas_texto

