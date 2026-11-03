# src/metrics/fuerza_plan.py
"""
Métricas del PLAN de fuerza y pasadas, por Match Day y por semana.

Funciones puras: reciben DataFrames / números y devuelven DataFrames / números.
No leen ni escriben nada (eso es trabajo de src/loaders/fuerza_loader.py).

Convenciones (las mismas que las tablas de Supabase, migración 0063):
  * pct_rm y pct_vmax van en PORCENTAJE (80 = 80 %), no en fracción (0,80).
  * En las pasadas, 'repeticiones' es la cantidad de pasadas.
  * Las pasadas se miden en METROS (total y a alta intensidad), no en UA (decisión D5).
"""
import numpy as np
import pandas as pd

# Valores por defecto = los que carga la migración 0063 en fuerza_parametros.
# Son provisorios y se editan en la base, no acá.
PARAMETROS_DEFAULT = {
    "umbral_alta_intensidad_vmax": 85.0,  # % de Vmáx desde el cual una pasada es de alta intensidad
    "intensidad_base_sin_rm": 50.0,       # % de RM asumido cuando el ejercicio no tiene %RM
}

TIPO_FUERZA = "fuerza"
TIPO_PASADA = "pasada"

COLUMNAS_RESUMEN_MD = [
    "match_day", "ua_fuerza", "ejercicios_fuerza",
    "metros_pasadas", "metros_alta_intensidad", "pasadas_sin_pct_vmax",
]


def orden_match_day(match_day: str) -> int:
    """
    Convierte 'MD-5' en -5, 'MD-2' en -2, 'MD+1' en 1, para ordenar el microciclo
    cronológicamente (MD-5 antes que MD-4 antes que MD-2).

    Raises:
        ValueError: si el texto no tiene el formato MD-n / MD+n.
    """
    texto = str(match_day).strip().upper()
    if len(texto) < 4 or not texto.startswith("MD") or texto[2] not in "+-" or not texto[3:].isdigit():
        raise ValueError(f"Match Day inválido: {match_day!r} (se espera MD-5, MD-2, MD+1...)")
    signo = -1 if texto[2] == "-" else 1
    return signo * int(texto[3:])


def ua_fuerza(series: float, repeticiones: float, pct_rm: float,
              intensidad_base: float = PARAMETROS_DEFAULT["intensidad_base_sin_rm"]) -> float:
    """
    Unidades arbitrarias (UA) de un ejercicio de fuerza:

        UA = series × repeticiones × (%RM / 100)

    Si no hay %RM (ejercicio sin RM, como abdominales o Remo TRX), se usa la
    intensidad base: así un ejercicio "liviano" suma poco, pero no suma cero.

    Ejemplo: 4 series × 5 reps al 80 % de RM  ->  4 × 5 × 0,80 = 16 UA.
    """
    if pd.isna(series) or pd.isna(repeticiones):
        return float("nan")
    intensidad = intensidad_base if pd.isna(pct_rm) else pct_rm
    return float(series) * float(repeticiones) * float(intensidad) / 100.0


def metros_pasada(distancia_m: float, repeticiones: float) -> float:
    """Metros totales de una pasada prescrita: distancia × cantidad de pasadas."""
    if pd.isna(distancia_m) or pd.isna(repeticiones):
        return float("nan")
    return float(distancia_m) * float(repeticiones)


def es_alta_intensidad(pct_vmax: float,
                       umbral: float = PARAMETROS_DEFAULT["umbral_alta_intensidad_vmax"]) -> bool:
    """True si la pasada se corre a una intensidad >= umbral (% de la Vmáx). Sin dato -> False."""
    if pd.isna(pct_vmax):
        return False
    return float(pct_vmax) >= float(umbral)


def tiempo_objetivo_pasada(distancia_m: float, vmax_kmh: float, pct_vmax: float,
                           factor_distancia: float = 1.0) -> float:
    """
    Tiempo objetivo (en segundos) para recorrer una distancia a un % de la Vmáx
    de una jugadora:

        tiempo (s) = distancia (m) ÷ ( Vmáx (km/h) ÷ 3,6 × %Vmáx/100 × factor )

    Dividir por 3,6 pasa de km/h a m/s.

    OJO: es la opción A del PLAN (Vmáx con corrección por distancia). En 30 m una
    jugadora que sale de parada no llega a su Vmáx, así que con factor = 1 el tiempo
    sale más rápido que el real. El factor (< 1) corrige eso; el valor lo define
    Tomi cuando elija entre A y B. Hasta entonces el default es 1 (sin corrección).

    Raises:
        ValueError: si la distancia, la Vmáx, el % o el factor no son positivos.
    """
    for nombre, valor in (("distancia_m", distancia_m), ("vmax_kmh", vmax_kmh),
                          ("pct_vmax", pct_vmax), ("factor_distancia", factor_distancia)):
        if pd.isna(valor) or valor <= 0:
            raise ValueError(f"{nombre} debe ser un número positivo (recibido: {valor!r})")
    velocidad_ms = vmax_kmh / 3.6 * (pct_vmax / 100.0) * factor_distancia
    return float(distancia_m) / velocidad_ms


def resumir_plan_por_md(df_items: pd.DataFrame, parametros: dict | None = None) -> pd.DataFrame:
    """
    Resume los ítems de UN plan semanal, un renglón por Match Day.

    Args:
        df_items: columnas [match_day, tipo, series, repeticiones, pct_rm,
                  distancia_m, pct_vmax] (las de fuerza_plan_items).
        parametros: {'umbral_alta_intensidad_vmax', 'intensidad_base_sin_rm'};
                  lo que falte se completa con PARAMETROS_DEFAULT.

    Returns:
        DataFrame [match_day, ua_fuerza, ejercicios_fuerza, metros_pasadas,
        metros_alta_intensidad, pasadas_sin_pct_vmax], ordenado MD-5 -> MD-2.
        'pasadas_sin_pct_vmax' avisa cuántas pasadas no traen % de Vmáx: esos metros
        entran en metros_pasadas pero NO se pueden clasificar como alta intensidad.
    """
    if df_items is None or df_items.empty:
        return pd.DataFrame(columns=COLUMNAS_RESUMEN_MD)

    params = {**PARAMETROS_DEFAULT, **(parametros or {})}
    base = params["intensidad_base_sin_rm"]
    umbral = params["umbral_alta_intensidad_vmax"]

    filas = []
    for match_day, grupo in df_items.groupby("match_day", sort=False):
        fuerza = grupo[grupo["tipo"] == TIPO_FUERZA]
        pasadas = grupo[grupo["tipo"] == TIPO_PASADA]

        ua = sum(ua_fuerza(r.series, r.repeticiones, r.pct_rm, base)
                 for r in fuerza.itertuples(index=False))
        metros = [metros_pasada(r.distancia_m, r.repeticiones) for r in pasadas.itertuples(index=False)]
        altos = [m for m, pct in zip(metros, pasadas["pct_vmax"]) if es_alta_intensidad(pct, umbral)]

        filas.append({
            "match_day": match_day,
            "ua_fuerza": round(float(np.nansum([ua])), 2),
            "ejercicios_fuerza": int(len(fuerza)),
            "metros_pasadas": float(np.nansum(metros)),
            "metros_alta_intensidad": float(np.nansum(altos)),
            "pasadas_sin_pct_vmax": int(pasadas["pct_vmax"].isna().sum()),
        })

    out = pd.DataFrame(filas, columns=COLUMNAS_RESUMEN_MD)
    out["_orden"] = out["match_day"].map(orden_match_day)
    return out.sort_values("_orden").drop(columns="_orden").reset_index(drop=True)


def resumir_plan_semana(df_items: pd.DataFrame, parametros: dict | None = None) -> dict:
    """
    Totales de la semana: suma de resumir_plan_por_md().

    Returns:
        {'ua_fuerza', 'metros_pasadas', 'metros_alta_intensidad', 'pasadas_sin_pct_vmax'}
    """
    por_md = resumir_plan_por_md(df_items, parametros)
    if por_md.empty:
        return {"ua_fuerza": 0.0, "metros_pasadas": 0.0,
                "metros_alta_intensidad": 0.0, "pasadas_sin_pct_vmax": 0}
    return {
        "ua_fuerza": float(por_md["ua_fuerza"].sum()),
        "metros_pasadas": float(por_md["metros_pasadas"].sum()),
        "metros_alta_intensidad": float(por_md["metros_alta_intensidad"].sum()),
        "pasadas_sin_pct_vmax": int(por_md["pasadas_sin_pct_vmax"].sum()),
    }
