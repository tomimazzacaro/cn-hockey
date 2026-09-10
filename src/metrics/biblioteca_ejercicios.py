# src/metrics/biblioteca_ejercicios.py
"""
Biblioteca de Ejercicios — perfil de demanda física real (GPS) por ejercicio
Técnico-Táctico tageado (ver src/loaders/ejercicio_loader.py para el
catálogo). Puramente descriptivo, sin rangos esperados ni veredictos como
Asistente de Parámetros — solo agrupa bloques históricos por "ejercicio" y
resume qué variables carga más cada uno.

Todo normalizado por minuto (`*_por_min`): los bloques duran distinto
(8 min vs 20 min), comparar totales crudos entre ejercicios sería engañoso.
"""
import pandas as pd

# Métricas ACUMULATIVAS (crecen con el tiempo del bloque) → nombre de la
# columna normalizada por minuto. vel_max_kmh queda afuera a propósito: es
# un pico puntual, no algo que se acumula, promediarlo crudo ya tiene sentido.
METRICAS_ACUMULATIVAS = {
    "distancia_total": "distancia_por_min",
    "hsr":              "hsr_por_min",
    "sprints":          "sprints_por_min",
    "acc_2":            "acc_2_por_min",
    "acc_3":            "acc_3_por_min",
    "decc_2":           "decc_2_por_min",
    "decc_3":           "decc_3_por_min",
    "player_load":      "player_load_por_min",
}

METRICA_LABELS = {
    "distancia_por_min":   "Distancia/min (m)",
    "hsr_por_min":         "HSR/min (m)",
    "sprints_por_min":     "Sprints/min",
    "acc_2_por_min":       "ACC>2/min",
    "acc_3_por_min":       "ACC>3/min",
    "decc_2_por_min":      "DECC>2/min",
    "decc_3_por_min":      "DECC>3/min",
    "player_load_por_min": "Player Load/min",
}

SIN_TAG = "—"


def normalizar_por_minuto(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega '<metrica>_por_min' para cada métrica acumulativa presente,
    dividiendo por duracion_min. Bloques con duracion_min <= 0 quedan en
    NaN — no se puede normalizar por tiempo cero."""
    df = df.copy()
    for col, col_norm in METRICAS_ACUMULATIVAS.items():
        if col in df.columns:
            df[col_norm] = df[col] / df["duracion_min"].where(df["duracion_min"] > 0)
    return df


def perfil_por_ejercicio(df_gps: pd.DataFrame) -> pd.DataFrame:
    """
    Perfil histórico de demanda física por ejercicio tageado.

    Filtra a Técnico-Táctico con ejercicio distinto de "—" (bloques sin
    taguear no aportan a la Biblioteca), normaliza por minuto y promedia
    por ejercicio.

    Devuelve una fila por ejercicio con:
    - n_bloques: sesiones distintas (fecha+cuarto) en que apareció ese
      ejercicio — no cuenta jugadoras.
    - n_muestras: filas jugadora-bloque (n_bloques * jugadoras promedio).
    - duracion_prom_min, vel_max_kmh_prom, y el promedio "_por_min" de cada
      métrica acumulativa disponible en el df.

    DataFrame vacío si no hay ningún bloque tageado todavía.
    """
    base = df_gps[
        (df_gps["tipo_sesion"] == "Técnico-Táctico") & (df_gps["ejercicio"] != SIN_TAG)
    ]
    if base.empty:
        return pd.DataFrame()

    base = normalizar_por_minuto(base)
    cols_por_min = [c for c in METRICAS_ACUMULATIVAS.values() if c in base.columns]

    n_bloques = (
        base[["ejercicio", "fecha", "cuarto"]]
        .drop_duplicates()
        .groupby("ejercicio")
        .size()
        .rename("n_bloques")
    )

    resumen = base.groupby("ejercicio").agg(
        n_muestras=("player_id", "count"),
        duracion_prom_min=("duracion_min", "mean"),
        vel_max_kmh_prom=("vel_max_kmh", "mean"),
        **{c: (c, "mean") for c in cols_por_min},
    )
    resumen = resumen.join(n_bloques)

    cols_orden = ["n_bloques", "n_muestras", "duracion_prom_min"] + cols_por_min + ["vel_max_kmh_prom"]
    return (resumen[cols_orden]
            .reset_index()
            .sort_values("ejercicio")
            .reset_index(drop=True))


def variables_destacadas(df_perfil: pd.DataFrame, top_n: int = 3) -> pd.DataFrame:
    """
    Para cada ejercicio, qué métricas "_por_min" se destacan MÁS que en el
    resto de los ejercicios del catálogo — z-score de cada métrica
    calculado ENTRE EJERCICIOS (no entre jugadoras ni entre sesiones).
    Necesita al menos 2 ejercicios con perfil: con uno solo no hay
    "relativo a qué otro ejercicio" comparar.

    Devuelve [ejercicio, metrica, valor_por_min, zscore] — top_n filas por
    ejercicio, ordenadas de mayor a menor zscore. Una métrica con desvío 0
    entre ejercicios (todos cargan igual) se excluye — no aporta señal.
    """
    if df_perfil.empty or len(df_perfil) < 2:
        return pd.DataFrame()

    cols_metrica = [c for c in df_perfil.columns if c.endswith("_por_min")]
    largo = df_perfil.melt(
        id_vars="ejercicio", value_vars=cols_metrica,
        var_name="metrica", value_name="valor_por_min",
    )
    stats = largo.groupby("metrica")["valor_por_min"].agg(["mean", "std"]).reset_index()
    largo = largo.merge(stats, on="metrica")
    largo["zscore"] = (largo["valor_por_min"] - largo["mean"]) / largo["std"].replace(0, pd.NA)
    largo = largo.dropna(subset=["zscore"])

    return (largo.sort_values(["ejercicio", "zscore"], ascending=[True, False])
                 .groupby("ejercicio", group_keys=False)
                 .head(top_n)[["ejercicio", "metrica", "valor_por_min", "zscore"]]
                 .reset_index(drop=True))
