# src/metrics/fuerza_vmax.py
"""
Vmáx por jugadora y tiempos objetivo de las pasadas (opción A del PLAN).

Opción A: la velocidad objetivo es la Vmáx de la jugadora × %Vmáx × un FACTOR POR
DISTANCIA (< 1). El factor existe porque al salir de parada en distancias cortas la
jugadora todavía está acelerando y no llega a su Vmáx; sin corrección, la fórmula
pide tiempos más rápidos que los reales.

    tiempo (s) = distancia (m) ÷ ( Vmáx (km/h) ÷ 3,6 × %Vmáx/100 × factor(distancia) )

Los factores por defecto son estimados de un modelo simple de aceleración (NO medidos)
y se editan en la pantalla de parámetros. Funciones puras: no leen ni escriben nada.
"""
import numpy as np
import pandas as pd

from src.metrics.fuerza_plan import PARAMETROS_DEFAULT, tiempo_objetivo_pasada

PREFIJO_FACTOR = "factor_pasada_"
COLUMNAS_VMAX = ["player_id", "nombre", "vmax_kmh", "n_dias", "ultima_fecha", "valores_descartados"]


def factores_desde_parametros(parametros: dict | None = None) -> dict[int, float]:
    """
    {distancia_m: factor} a partir de los parámetros (claves 'factor_pasada_30', ...).
    Lo que falte se completa con los valores por defecto.
    """
    params = {**PARAMETROS_DEFAULT, **(parametros or {})}
    return {int(k[len(PREFIJO_FACTOR):]): float(v)
            for k, v in sorted(params.items()) if k.startswith(PREFIJO_FACTOR)}


def factor_para_distancia(distancia_m: float, factores: dict[int, float]) -> float:
    """
    Factor para una distancia cualquiera: interpolación lineal entre las distancias
    calibradas (35 m cae entre el de 30 y el de 40). Fuera del rango calibrado se usa el
    factor del extremo más cercano; ver distancia_fuera_de_rango().
    """
    if not factores:
        raise ValueError("No hay factores por distancia configurados.")
    distancias = sorted(factores)
    return float(np.interp(distancia_m, distancias, [factores[d] for d in distancias]))


def distancia_fuera_de_rango(distancia_m: float, factores: dict[int, float]) -> bool:
    """True si la distancia está fuera del rango calibrado (el factor usado es el del extremo)."""
    return not (min(factores) <= distancia_m <= max(factores))


def calcular_vmax_jugadoras(df_gps: pd.DataFrame, top_n: int = 3, ventana_dias: int = 180,
                            tope_kmh: float = 35.0) -> pd.DataFrame:
    """
    Vmáx de cada jugadora a partir de las velocidades máximas del GPS.

    Método: se toma la velocidad máxima de cada DÍA, y la Vmáx es el promedio de los
    `top_n` mejores días dentro de la ventana. Promediar varios días evita que un solo
    registro raro defina el valor.

    Se descartan (y se cuentan) las velocidades > `tope_kmh`: son errores del chaleco
    (en el GPS de CN Hockey hay registros de 51 km/h, imposibles para una persona).

    Args:
        df_gps: columnas [player_id, nombre, fecha, vel_max_kmh].
        ventana_dias: días hacia atrás desde el ÚLTIMO dato del GPS (no desde hoy: así el
                      cálculo no queda vacío si el GPS tiene unos días de atraso).

    Returns:
        DataFrame COLUMNAS_VMAX, una fila por jugadora (vmax_kmh vacío si no tiene datos
        válidos). 'n_dias' = días usados en el promedio (puede ser < top_n si hay pocos).
    """
    if df_gps is None or df_gps.empty:
        return pd.DataFrame(columns=COLUMNAS_VMAX)

    df = df_gps[["player_id", "nombre", "fecha", "vel_max_kmh"]].copy()
    df["fecha"] = pd.to_datetime(df["fecha"]).dt.normalize()
    df["vel_max_kmh"] = pd.to_numeric(df["vel_max_kmh"], errors="coerce")
    ventana = df[df["fecha"] >= df["fecha"].max() - pd.Timedelta(days=int(ventana_dias))]
    ventana = ventana.dropna(subset=["vel_max_kmh"])

    nombres = (df.dropna(subset=["nombre"]).sort_values("fecha")
               .groupby("player_id")["nombre"].last())
    descartados = ventana[ventana["vel_max_kmh"] > tope_kmh].groupby("player_id").size()
    validos = ventana[ventana["vel_max_kmh"] <= tope_kmh]
    por_dia = validos.groupby(["player_id", "fecha"])["vel_max_kmh"].max().reset_index()

    filas = []
    for player_id in df["player_id"].drop_duplicates():
        dias = por_dia[por_dia["player_id"] == player_id].nlargest(int(top_n), "vel_max_kmh")
        filas.append({
            "player_id": player_id,
            "nombre": nombres.get(player_id, player_id),
            "vmax_kmh": round(float(dias["vel_max_kmh"].mean()), 1) if not dias.empty else np.nan,
            "n_dias": int(len(dias)),
            "ultima_fecha": por_dia.loc[por_dia["player_id"] == player_id, "fecha"].max(),
            "valores_descartados": int(descartados.get(player_id, 0)),
        })
    return pd.DataFrame(filas, columns=COLUMNAS_VMAX).sort_values("nombre").reset_index(drop=True)


def tiempos_objetivo_jugadoras(df_vmax: pd.DataFrame, df_pasadas: pd.DataFrame,
                               factores: dict[int, float]) -> pd.DataFrame:
    """
    Tiempo objetivo (s) de cada pasada prescrita para cada jugadora.

    Args:
        df_vmax: salida de calcular_vmax_jugadoras().
        df_pasadas: pasadas prescritas con [distancia_m, pct_vmax]. Las que no tienen
                    %Vmáx no se pueden calcular y se omiten.
        factores: {distancia: factor}, ver factores_desde_parametros().

    Returns:
        DataFrame con una fila por jugadora: [Jugadora, Vmáx (km/h)] + una columna por
        combinación distinta de distancia y %Vmáx, p. ej. '30 m al 90 %'. Vacío (sin
        columnas de pasadas) si no hay pasadas calculables.
    """
    base = pd.DataFrame({"Jugadora": df_vmax["nombre"].to_numpy(),
                         "Vmáx (km/h)": df_vmax["vmax_kmh"].to_numpy()})
    if df_pasadas is None or df_pasadas.empty:
        return base
    combos = (df_pasadas.dropna(subset=["distancia_m", "pct_vmax"])
              [["distancia_m", "pct_vmax"]].drop_duplicates()
              .sort_values(["distancia_m", "pct_vmax"]))
    for distancia, pct in combos.itertuples(index=False):
        factor = factor_para_distancia(distancia, factores)
        etiqueta = f"{distancia:g} m al {pct:g} %"
        base[etiqueta] = [
            round(tiempo_objetivo_pasada(distancia, v, pct, factor), 2) if pd.notna(v) and v > 0 else np.nan
            for v in df_vmax["vmax_kmh"]
        ]
    return base
