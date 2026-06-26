# src/utils/helpers.py
"""
Funciones utilitarias generales reutilizables en todo el proyecto.
"""
import pandas as pd
import numpy as np
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent.parent))
from settings import COLORS, ACWR_OPTIMO_MIN, ACWR_OPTIMO_MAX, ACWR_ALERTA


# ── Fechas ─────────────────────────────────────────────────────────────────

def parsear_fecha(df: pd.DataFrame, col: str = "fecha") -> pd.DataFrame:
    """Convierte la columna de fecha al tipo datetime.date de forma segura."""
    df[col] = pd.to_datetime(df[col], dayfirst=True, errors="coerce").dt.date
    return df


# ── Normalización ──────────────────────────────────────────────────────────

def normalizar_0_10(serie: pd.Series) -> pd.Series:
    """
    Normaliza una Serie al rango 0–10 usando Min-Max scaling.
    Útil para comparar métricas de distintas escalas.
    """
    min_val = serie.min()
    max_val = serie.max()
    if max_val == min_val:
        return pd.Series([5.0] * len(serie), index=serie.index)
    return ((serie - min_val) / (max_val - min_val)) * 10


def invertir_escala(serie: pd.Series,
                    escala_max: float = 10.0) -> pd.Series:
    """
    Invierte una escala (ej: RPE alto → readiness bajo).
    Fórmula: valor_invertido = escala_max - valor_original
    """
    return escala_max - serie


# ── Clasificación ACWR ─────────────────────────────────────────────────────

def clasificar_acwr(valor: float) -> str:
    """
    Clasifica un valor ACWR en zona de riesgo.
    Referencia: Hulin et al. (2016)
    """
    if valor < ACWR_OPTIMO_MIN:
        return "Subcarga"
    elif valor <= ACWR_OPTIMO_MAX:
        return "Óptimo"
    elif valor <= ACWR_ALERTA:
        return "Precaución"
    else:
        return "Riesgo Alto"


def clasificar_readiness(valor: float) -> str:
    """Clasifica el índice de readiness en categoría semafórica."""
    if valor >= 7:
        return "Apta"
    elif valor >= 5:
        return "Precaución"
    else:
        return "No Apta"


# ── Estadísticas rápidas ───────────────────────────────────────────────────

def resumen_estadistico(df: pd.DataFrame,
                        cols: list) -> pd.DataFrame:
    """
    Devuelve media, desvío, min, max y percentiles 25/75
    para las columnas especificadas.
    """
    return df[cols].agg(["mean", "std", "min",
                         lambda x: x.quantile(0.25),
                         lambda x: x.quantile(0.75),
                         "max"]).T.rename(columns={
        "mean":      "Media",
        "std":       "Desvío",
        "min":       "Mín",
        "<lambda_0>": "P25",
        "<lambda_1>": "P75",
        "max":       "Máx",
    })


# ── Validación de DataFrames ───────────────────────────────────────────────

def validar_columnas(df: pd.DataFrame,
                     cols_requeridas: list,
                     nombre_df: str = "DataFrame") -> None:
    """
    Verifica que el DataFrame tenga todas las columnas requeridas.
    Lanza ValueError si falta alguna.
    """
    faltantes = [c for c in cols_requeridas if c not in df.columns]
    if faltantes:
        raise ValueError(
            f"[{nombre_df}] Columnas faltantes: {faltantes}\n"
            f"Columnas disponibles: {list(df.columns)}"
        )