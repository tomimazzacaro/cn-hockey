# src/metrics/physical.py
"""
Módulo de métricas físicas — CN Hockey Femenino.
Calcula ACWR por EWMA, sRPE y métricas de intensidad relativa.
Referencia ACWR: Hulin et al. (2016), Gabbett (2016)
Referencia EWMA: Williams et al. (2017)
"""
import pandas as pd
import numpy as np
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent.parent))
from settings import (
    EWMA_AGUDA_DIAS, EWMA_CRONICA_DIAS,
    ACWR_OPTIMO_MIN, ACWR_OPTIMO_MAX, ACWR_ALERTA,
    PROCESSED, CUARTOS,
)


# ── EWMA ───────────────────────────────────────────────────────────────────

def calcular_ewma(serie: pd.Series, dias: int) -> pd.Series:
    """
    Calcula la media móvil exponencialmente ponderada (EWMA).

    A diferencia de la media móvil simple, la EWMA pondera más
    los datos recientes. Esto es más sensible a cambios agudos
    de carga, lo que la hace superior para monitoreo de fatiga.

    Fórmula del factor de decaimiento:
        α = 2 / (N + 1)
    Donde N = ventana de días (7 para aguda, 28 para crónica)

    Args:
        serie: Serie temporal de carga (ej: player_load por día)
        dias:  Ventana en días (7 = aguda, 28 = crónica)

    Returns:
        Serie con valores EWMA para cada punto temporal.
    """
    return serie.ewm(span=dias, adjust=False).mean()


def calcular_acwr(df: pd.DataFrame,
                  col_carga: str = "player_load",
                  por_jugadora: bool = True) -> pd.DataFrame:
    """
    Calcula el ACWR (Acute:Chronic Workload Ratio) por EWMA.

    El ACWR es el indicador más importante de riesgo de lesión
    por carga. Compara la carga aguda reciente (7 días) contra
    la carga crónica habitual (28 días).

    Zonas de riesgo (Hulin et al., 2016):
        < 0.8  → Subcarga (desacondicionamiento)
        0.8–1.3 → Zona óptima (fitness sin fatiga)
        1.3–1.5 → Precaución
        > 1.5  → Riesgo alto de lesión

    Args:
        df:          DataFrame con columnas [player_id, fecha, col_carga]
        col_carga:   Métrica a usar como proxy de carga externa
        por_jugadora: Si True, calcula EWMA individual por jugadora

    Returns:
        DataFrame original con columnas adicionales:
        ewma_aguda, ewma_cronica, acwr, zona_acwr

    Nota: si una jugadora tiene más de una fila el mismo día (ej: sesión
    física + técnico-táctica, o los 4 cuartos de un partido), la carga se
    SUMA a nivel día antes de calcular el EWMA. El EWMA opera sobre una
    serie de un valor por día — tratar cada fila como un paso de tiempo
    independiente distorsiona la ventana de 7/28 días.
    """
    df = df.copy()
    df["fecha"] = pd.to_datetime(df["fecha"])

    # Carga diaria total por jugadora (suma todas las sesiones/cuartos del día)
    diaria = (
        df.groupby(["player_id", "fecha"])[col_carga]
          .sum()
          .reset_index()
          .sort_values(["player_id", "fecha"])
    )

    if por_jugadora:
        # Calcular EWMA individualmente para cada jugadora
        diaria["ewma_aguda"] = (
            diaria.groupby("player_id")[col_carga]
                  .transform(lambda x: calcular_ewma(x, EWMA_AGUDA_DIAS))
        )
        diaria["ewma_cronica"] = (
            diaria.groupby("player_id")[col_carga]
                  .transform(lambda x: calcular_ewma(x, EWMA_CRONICA_DIAS))
        )
    else:
        diaria["ewma_aguda"]   = calcular_ewma(diaria[col_carga], EWMA_AGUDA_DIAS)
        diaria["ewma_cronica"] = calcular_ewma(diaria[col_carga], EWMA_CRONICA_DIAS)

    # ACWR = carga aguda / carga crónica
    # Evitamos división por cero con replace
    diaria["acwr"] = (
        diaria["ewma_aguda"] / diaria["ewma_cronica"].replace(0, np.nan)
    ).round(3)

    # Clasificar zona de riesgo
    diaria["zona_acwr"] = diaria["acwr"].apply(_clasificar_zona_acwr)

    # Volcar el ACWR diario a cada fila original (todas las sesiones de un
    # mismo día comparten el mismo ACWR, porque el riesgo es a nivel día)
    df = df.merge(
        diaria[["player_id", "fecha", "ewma_aguda", "ewma_cronica",
                "acwr", "zona_acwr"]],
        on=["player_id", "fecha"], how="left",
    )
    df = df.sort_values(["player_id", "fecha"]).reset_index(drop=True)
    df["fecha"] = df["fecha"].dt.date

    return df


def _clasificar_zona_acwr(valor: float) -> str:
    """Clasifica el ACWR en zona de riesgo semafórica."""
    if pd.isna(valor):
        return "Sin datos"
    elif valor < ACWR_OPTIMO_MIN:
        return "Subcarga"
    elif valor <= ACWR_OPTIMO_MAX:
        return "Óptimo"
    elif valor <= ACWR_ALERTA:
        return "Precaución"
    else:
        return "Riesgo Alto"


# ── sRPE ───────────────────────────────────────────────────────────────────

def calcular_srpe(df_wellness: pd.DataFrame,
                  df_gps: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula el sRPE (Session RPE = RPE × duración en minutos).

    El sRPE es el indicador de carga interna más usado en campo.
    Cuantifica el estrés fisiológico percibido por la jugadora
    en función de la intensidad y duración de la sesión.

    Unidad: UA (unidades arbitrarias)
    Referencia: Foster et al. (2001)

    Args:
        df_wellness: DataFrame con columnas [player_id, fecha, rpe]
        df_gps:      DataFrame con columnas [player_id, fecha, duracion_min]

    Returns:
        df_wellness con columna srpe calculada.
    """
    df_wellness = df_wellness.copy()
    df_gps      = df_gps.copy()

    # Asegurar tipos de fecha consistentes
    df_wellness["fecha"] = pd.to_datetime(df_wellness["fecha"])
    df_gps["fecha"]      = pd.to_datetime(df_gps["fecha"])

    # Merge para traer duración del GPS al wellness
    df_merge = df_wellness.merge(
        df_gps[["player_id", "fecha", "duracion_min"]],
        on=["player_id", "fecha"],
        how="left"
    )

    # sRPE = RPE × duración (minutos)
    df_merge["srpe"] = (df_merge["rpe"] * df_merge["duracion_min"]).round(1)

    # Devolver wellness con srpe actualizado
    df_wellness["srpe"] = df_merge["srpe"].values
    df_wellness["fecha"] = df_wellness["fecha"].dt.date

    return df_wellness


# ── Métricas de intensidad relativa ───────────────────────────────────────

def calcular_intensidad_relativa(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula métricas de intensidad relativa normalizadas por minuto.
    Permite comparar sesiones de diferente duración.

    Métricas generadas:
        dist_min:   Distancia total por minuto (m/min)
        hsr_pct:    % de distancia en HSR sobre distancia total
        pl_min:     Player Load por minuto
    """
    df = df.copy()

    # Evitar división por cero
    duracion_segura = df["duracion_min"].replace(0, np.nan)

    df["dist_min"] = (df["distancia_total"] / duracion_segura).round(2)
    df["hsr_pct"]  = (df["hsr"] / df["distancia_total"].replace(0, np.nan) * 100).round(2)
    df["pl_min"]   = (df["player_load"] / duracion_segura).round(2)

    return df


# ── Partidos completos (agregado de cuartos) ───────────────────────────────

def agregar_partidos_completos(df: pd.DataFrame,
                               tipo_partido: str = "Partido") -> pd.DataFrame:
    """
    Agrega una fila 'Completo' por jugadora y partido, sumando sus 4 cuartos
    (o el máximo, para métricas de velocidad pico). Sirve para ver el
    partido entero como una sesión más — no se persiste ni se usa para el
    ACWR, que ya suma la carga por día sobre los cuartos reales.

    Solo genera la fila 'Completo' para jugadoras con los 4 cuartos (Q1-Q4)
    cargados. Si al GPS le faltó registrar uno o más cuartos de una jugadora,
    su total parcial no es comparable a un partido completo — incluirlo
    arrastraría hacia abajo el promedio del equipo como si esa jugadora
    hubiese tenido baja demanda, cuando en realidad faltan datos. Se la
    excluye de ese partido en vez de arrastrar el promedio con datos a medias.

    Devuelve SOLO las filas 'Completo' generadas (no el df original) —
    quien llama decide si concatenarlas o usarlas solas.
    """
    partidos = df[df["tipo_sesion"] == tipo_partido]
    if partidos.empty:
        return partidos

    n_cuartos = partidos.groupby(["player_id", "fecha"])["cuarto"].transform("nunique")
    partidos = partidos[n_cuartos >= len(CUARTOS)]
    if partidos.empty:
        return partidos

    COLS_SUMA = ["duracion_min", "distancia_total", "hsr", "hsr_esfuerzos", "sprints",
                 "acc_3", "acc_2", "decc_3", "decc_2",
                 "player_load", "pl_fwd", "pl_side", "pl_up", "pl_2d", "pl_slow", "acc_load"]
    COLS_MAX  = ["vel_max_kmh", "vel_max_ms", "vel_max_pct"]
    COLS_ACWR = ["ewma_aguda", "ewma_cronica", "acwr", "zona_acwr"]

    agg = {c: "sum" for c in COLS_SUMA if c in partidos.columns}
    agg.update({c: "max" for c in COLS_MAX if c in partidos.columns})
    # El ACWR ya es el mismo en las 4 filas del día (se agrega por día en calcular_acwr)
    agg.update({c: "first" for c in COLS_ACWR if c in partidos.columns})

    completos = partidos.groupby(["player_id", "nombre", "fecha"], as_index=False).agg(agg)
    completos["tipo_sesion"] = tipo_partido
    completos["cuarto"] = "Completo"

    if "posicion" in partidos.columns:
        mapa_pos = partidos.drop_duplicates("player_id").set_index("player_id")["posicion"]
        completos["posicion"] = completos["player_id"].map(mapa_pos)

    return calcular_intensidad_relativa(completos)


# ── Resumen de carga del equipo ────────────────────────────────────────────

def resumen_carga_equipo(df: pd.DataFrame,
                         col_carga: str = "player_load") -> pd.DataFrame:
    """
    Genera resumen estadístico de carga por fecha para el equipo completo.
    Útil para la vista de overview del dashboard.

    Returns:
        DataFrame con media, desvío, min y max de carga por sesión.
    """
    return (
        df.groupby("fecha")[col_carga]
          .agg(
              media="mean",
              desvio="std",
              minimo="min",
              maximo="max",
              n_jugadoras="count"
          )
          .round(2)
          .reset_index()
    )


# ── Test rápido ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Cargar GPS procesado
    ruta_gps = PROCESSED / "gps_procesado.parquet"
    if not ruta_gps.exists():
        print("❌ No se encontró gps_procesado.parquet — ejecutá primero el gps_loader.py")
        sys.exit(1)

    df_gps = pd.read_parquet(ruta_gps)

    # Métricas de intensidad relativa
    df_gps = calcular_intensidad_relativa(df_gps)

    # ACWR (con una sola sesión los valores son iguales, es esperado)
    df_acwr = calcular_acwr(df_gps, col_carga="player_load")

    print("✅ Métricas físicas calculadas\n")
    print("─── Intensidad relativa ───")
    print(df_acwr[["nombre", "fecha", "distancia_total",
                   "dist_min", "hsr_pct", "pl_min"]].to_string(index=False))

    print("\n─── ACWR ───")
    print(df_acwr[["nombre", "ewma_aguda",
                   "ewma_cronica", "acwr", "zona_acwr"]].to_string(index=False))

    print("\n─── Resumen equipo ───")
    print(resumen_carga_equipo(df_gps).to_string(index=False))