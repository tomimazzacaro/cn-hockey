# src/metrics/fuerza.py
"""
Módulo de métricas de fuerza — CN Hockey Femenino.
Calcula RM (directo o estimado), RM vigente y tonelaje.
Referencia 1RM estimado: Epley (1985).

Pura: sin IO ni Streamlit. Todo número estimado se marca como tal
(rm_origen) para no presentarlo como dato medido.
"""
import numpy as np
import pandas as pd

TIPO_TEST_RM = "RM"
TIPO_TEST_SUBMAXIMO = "Submáximo"

# Más allá de ~10 repeticiones la estimación de RM pierde confiabilidad.
REPS_MAX_ESTIMACION = 10


def estimar_rm_epley(kg: float, reps: float) -> float:
    """
    Estima el 1RM a partir de una serie submáxima (Epley).

        1RM = kg × (1 + reps / 30)

    Con reps=1 devuelve el mismo peso. Devuelve NaN si los datos son
    inválidos o si reps supera REPS_MAX_ESTIMACION.
    """
    if pd.isna(kg) or pd.isna(reps):
        return np.nan
    if kg <= 0 or reps < 1 or reps > REPS_MAX_ESTIMACION:
        return np.nan
    if reps == 1:
        return float(kg)
    return float(kg * (1 + reps / 30))


def agregar_rm_a_tests(df_tests: pd.DataFrame) -> pd.DataFrame:
    """
    Agrega rm_kg y rm_origen ("Directo" | "Estimado") a cada test.

    Args:
        df_tests: columnas [player_id, ejercicio, fecha, tipo, kg, reps].
                  tipo = "RM" usa el peso tal cual; "Submáximo" lo estima.

    Returns:
        Copia del DataFrame con rm_kg y rm_origen.
    """
    df = df_tests.copy()
    es_directo = df["tipo"] == TIPO_TEST_RM
    estimado = [estimar_rm_epley(k, r) for k, r in zip(df["kg"], df["reps"])]
    df["rm_kg"] = np.where(es_directo, df["kg"], estimado)
    df["rm_origen"] = np.where(es_directo, "Directo", "Estimado")
    return df


# Slugs de registros_rm (app de jugadoras) -> nombre del Catalogo_Fuerza del Sheet.
SLUGS_RM_A_EJERCICIO = {
    "banco_plano":        "Banco plano",
    "press_hombros":      "Press de hombros",
    "cargadas":           "Cargada",
    "hip_thrust":         "Hip thrust",
    "sentadilla_detras":  "Sentadilla trasera",
    "sentadilla_delante": "Sentadilla frontal",
    "peso_muerto":        "Peso muerto",
    "remo":               "Remo",
}

ORIGEN_AUTORREPORTADO = "Autorreportado"


def normalizar_registros_rm(df_rm: pd.DataFrame) -> pd.DataFrame:
    """
    Adapta registros_rm (RM que las propias jugadoras cargan en su app) al
    formato que espera rm_vigente().

    registros_rm no guarda reps ni si fue test directo o estimado, y lo tipea
    cada jugadora: por eso el origen se marca "Autorreportado", nunca "Directo".

    Args:
        df_rm: columnas [player_id, ejercicio (slug), rm_kg, fecha].

    Returns:
        Copia con ejercicio traducido al nombre del catálogo, fecha como
        Timestamp y rm_origen = "Autorreportado". Un slug desconocido no se
        descarta: se capitaliza ("press_inclinado" -> "Press inclinado").
    """
    df = df_rm.copy()
    df["ejercicio"] = df["ejercicio"].map(
        lambda s: SLUGS_RM_A_EJERCICIO.get(s, str(s).replace("_", " ").capitalize())
    )
    df["fecha"] = pd.to_datetime(df["fecha"])
    df["rm_origen"] = ORIGEN_AUTORREPORTADO
    return df


def rm_vigente(df_tests_rm: pd.DataFrame, player_id: str,
               ejercicio: str, fecha) -> float:
    """
    RM vigente "as-of": el del último test con fecha <= `fecha`.

    Nunca usa tests posteriores: si el RM sube a mitad de ciclo, el %RM
    de las sesiones previas no se recalcula (no se reescribe el pasado).

    Args:
        df_tests_rm: salida de agregar_rm_a_tests().

    Returns:
        RM en kg, o NaN si no hay test previo.
    """
    corte = pd.Timestamp(fecha)
    previos = df_tests_rm[
        (df_tests_rm["player_id"] == player_id)
        & (df_tests_rm["ejercicio"] == ejercicio)
        & (df_tests_rm["fecha"] <= corte)
        & df_tests_rm["rm_kg"].notna()
    ]
    if previos.empty:
        return np.nan
    return float(previos.sort_values("fecha")["rm_kg"].iloc[-1])


def armar_series(df_editado: pd.DataFrame) -> pd.DataFrame:
    """
    Limpia las filas que cargó el cuerpo técnico en el formulario y numera las series.

    Se descartan las filas incompletas (reps o kg vacíos) o inválidas (reps < 1,
    kg < 0): una fila a medio llenar no debe llegar a la base. El RIR es opcional:
    si está fuera de 0–10 se deja vacío, pero la serie se conserva.

    Args:
        df_editado: columnas [reps, kg, rir], en el orden en que se hicieron.

    Returns:
        DataFrame [nro_serie, reps, kg, rir] con nro_serie correlativo desde 1.
    """
    df = df_editado[["reps", "kg", "rir"]].copy()
    df["reps"] = pd.to_numeric(df["reps"], errors="coerce")
    df["kg"] = pd.to_numeric(df["kg"], errors="coerce")
    df["rir"] = pd.to_numeric(df["rir"], errors="coerce")

    df = df[df["reps"].notna() & df["kg"].notna() & (df["reps"] >= 1) & (df["kg"] >= 0)]
    df.loc[~df["rir"].between(0, 10), "rir"] = np.nan

    df = df.reset_index(drop=True)
    df.insert(0, "nro_serie", range(1, len(df) + 1))
    return df


def enriquecer_series(df_series: pd.DataFrame, df_rm: pd.DataFrame,
                      referencias: dict | None = None) -> pd.DataFrame:
    """
    Agrega a cada serie su RM vigente "as-of", el %RM real y el tonelaje.

    El RM es el último con fecha <= la de la serie (merge_asof hacia atrás):
    la intensidad de una sesión vieja nunca se recalcula con un RM posterior.
    Una serie sin RM previo se conserva (pct_rm_real = NaN, tonelaje intacto).

    Args:
        df_series:   [player_id, fecha, ejercicio, nro_serie, reps, kg].
        df_rm:       salida de normalizar_registros_rm() [player_id, ejercicio, fecha, rm_kg].
        referencias: {ejercicio: ejercicio_cuyo_RM_se_usa}, ej. los tirones de
                     cargada se miden contra el RM de la cargada.

    Returns:
        Copia de df_series (mismo orden) con rm_kg, pct_rm_real y tonelaje.
    """
    referencias = referencias or {}
    izq = df_series.copy()
    izq["_orden"] = range(len(izq))
    izq["_ref"] = izq["ejercicio"].map(referencias).fillna(izq["ejercicio"])
    izq["fecha"] = pd.to_datetime(izq["fecha"]).astype("datetime64[ns]")
    # merge_asof exige claves del mismo dtype y pandas 3 distingue object de str:
    # los datos de Supabase y del Sheet no llegan con el mismo tipo.
    izq["player_id"] = izq["player_id"].astype(str)
    izq["_ref"] = izq["_ref"].astype(str)
    izq = izq.drop(columns=["rm_kg"], errors="ignore").sort_values("fecha")

    der = (df_rm.dropna(subset=["rm_kg"])
                .rename(columns={"ejercicio": "_ref"})[["player_id", "_ref", "fecha", "rm_kg"]]
                .copy())
    der["fecha"] = pd.to_datetime(der["fecha"]).astype("datetime64[ns]")
    der["player_id"] = der["player_id"].astype(str)
    der["_ref"] = der["_ref"].astype(str)
    der = der.sort_values("fecha")

    out = pd.merge_asof(izq, der, on="fecha", by=["player_id", "_ref"], direction="backward")
    out = out.sort_values("_orden").drop(columns=["_orden", "_ref"]).reset_index(drop=True)
    out["pct_rm_real"] = out["kg"] / out["rm_kg"] * 100
    out["tonelaje"] = out["kg"] * out["reps"]
    return out


def resumen_por_periodo(df_enriquecido: pd.DataFrame, freq: str = "W",
                        por: list[str] | None = None) -> pd.DataFrame:
    """
    Historial agregado: tonelaje, series, reps y %RM medio por semana o mes.

    Args:
        df_enriquecido: salida de enriquecer_series() (con fecha).
        freq: "W" (semana, desde el lunes) o "M" (mes, desde el día 1).
        por:  columnas extra para abrir el resumen (ej. ["ejercicio"] o ["player_id"]).

    Returns:
        [periodo, *por, n_sesiones, n_series, reps, tonelaje, pct_rm_medio]
        ordenado por periodo. pct_rm_medio ignora las series sin RM.
    """
    por = por or []
    columnas = ["periodo", *por, "n_sesiones", "n_series", "reps", "tonelaje", "pct_rm_medio"]
    if df_enriquecido.empty:
        return pd.DataFrame(columns=columnas)

    df = df_enriquecido.copy()
    df["periodo"] = pd.to_datetime(df["fecha"]).dt.to_period(freq).dt.start_time
    resumen = (df.groupby(["periodo", *por])
                 .agg(n_sesiones=("fecha", "nunique"),
                      n_series=("fecha", "size"),
                      reps=("reps", "sum"),
                      tonelaje=("tonelaje", "sum"),
                      pct_rm_medio=("pct_rm_real", "mean"))
                 .reset_index()
                 .sort_values(["periodo", *por])
                 .reset_index(drop=True))
    return resumen[columnas]


def calcular_tonelaje(df_registro: pd.DataFrame) -> float:
    """Tonelaje = Σ kg × reps. Ignora filas con kg o reps faltantes."""
    producto = (df_registro["kg"] * df_registro["reps"]).dropna()
    return float(producto.sum())
