# src/metrics/wellness.py
"""
Módulo de métricas de wellness — CN Hockey Femenino.
Calcula Readiness Index, tendencias de recuperación y alertas.
Referencia TQR: Kenttä & Hassmén (1998)
"""
import pandas as pd
import numpy as np
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent.parent))
from settings import (
    TQR_MIN, TQR_MAX,
    PROCESSED
)


# ── Readiness Index ────────────────────────────────────────────────────────

def calcular_readiness(df: pd.DataFrame) -> pd.DataFrame:
    """
    Readiness = último valor de TQR (recuperación percibida), directo.

    Interpretación:
        8–10 → Totalmente Apta
        6–7  → Apta Moderado
        4–5  → Precaución
        1–3  → No Apta

    Args:
        df: DataFrame con columnas [player_id, fecha, tqr]

    Returns:
        DataFrame con columna readiness_index agregada.
    """
    df = df.copy()

    df["readiness_index"] = df["tqr"].clip(TQR_MIN, TQR_MAX)
    df["readiness_zona"]  = df["readiness_index"].apply(_clasificar_readiness)

    return df


def _clasificar_readiness(valor: float) -> str:
    """Clasifica el Readiness Index en zona semafórica (4 niveles)."""
    if pd.isna(valor):
        return "Sin datos"
    elif valor >= 8:
        return "Totalmente Apta"
    elif valor >= 6:
        return "Apta Moderado"
    elif valor >= 4:
        return "Precaución"
    else:
        return "No Apta"


# ── Tendencia de recuperación ──────────────────────────────────────────────

def calcular_tendencia_tqr(df: pd.DataFrame,
                            ventana: int = 3) -> pd.DataFrame:
    """
    Calcula la tendencia de TQR por jugadora en los últimos N días.
    Permite detectar fatiga acumulada antes de que sea crítica.

    Tendencia:
        > 0  → Mejorando (recuperación positiva)
        = 0  → Estable
        < 0  → Deteriorando (señal de alerta)

    Args:
        df:      DataFrame con [player_id, fecha, tqr]
        ventana: Días hacia atrás para calcular pendiente

    Returns:
        DataFrame con columna tqr_tendencia agregada.
    """
    df = df.copy()
    df["fecha"] = pd.to_datetime(df["fecha"])
    df = df.sort_values(["player_id", "fecha"])

    df["tqr_tend"] = (
        df.groupby("player_id")["tqr"]
          .transform(lambda x: x.rolling(ventana, min_periods=2).mean().diff())
          .round(2)
    )

    df["fecha"] = df["fecha"].dt.date

    return df


# ── Alertas ────────────────────────────────────────────────────────────────

def generar_alertas(df: pd.DataFrame) -> pd.DataFrame:
    """
    Genera flags de alerta basados en umbrales clínicos.

    Alertas detectadas:
        alerta_tqr_bajo:     TQR < 5 (recuperación insuficiente)
        alerta_rpe_alto:     RPE > 8 (esfuerzo muy alto)
        alerta_readiness:    Readiness < 5 (no apta para entrenar)
        alerta_molestia:     Molestia física reportada
        alerta_combinada:    TQR bajo + RPE alto simultáneos (riesgo máximo)

    Args:
        df: DataFrame con métricas calculadas

    Returns:
        DataFrame con columnas de alerta booleanas.
    """
    df = df.copy()

    df["alerta_tqr_bajo"]  = df["tqr"] < 5
    df["alerta_rpe_alto"]  = df["rpe"] > 8

    if "readiness_index" in df.columns:
        df["alerta_readiness"] = df["readiness_index"] < 5
    
    if "molestia_flag" in df.columns:
        df["alerta_molestia"] = df["molestia_flag"]

    # Alerta combinada: la más crítica
    df["alerta_combinada"] = df["alerta_tqr_bajo"] & df["alerta_rpe_alto"]

    return df


def resumen_alertas_equipo(df: pd.DataFrame) -> pd.DataFrame:
    """
    Genera tabla resumen de alertas activas por jugadora.
    Diseñado para la vista diaria del cuerpo técnico.

    Returns:
        DataFrame con jugadoras que tienen al menos una alerta activa,
        ordenadas por número de alertas descendente.
    """
    cols_alerta = [c for c in df.columns if c.startswith("alerta_")]

    if not cols_alerta:
        return pd.DataFrame()

    # Último registro por jugadora
    df_ultimo = (
        df.sort_values("fecha")
          .groupby("player_id")
          .last()
          .reset_index()
    )

    df_ultimo["total_alertas"] = df_ultimo[cols_alerta].sum(axis=1)

    # Solo jugadoras con al menos una alerta
    alertadas = (
        df_ultimo[df_ultimo["total_alertas"] > 0]
        [["player_id", "nombre", "fecha", "tqr", "rpe",
          "readiness_index", "readiness_zona", "total_alertas"] + cols_alerta]
        .sort_values("total_alertas", ascending=False)
        .reset_index(drop=True)
    )

    return alertadas


# ── Test rápido ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ruta = PROCESSED / "wellness_procesado.parquet"
    if not ruta.exists():
        print("❌ No se encontró wellness_procesado.parquet")
        sys.exit(1)

    df = pd.read_parquet(ruta)

    # Pipeline completo
    df = calcular_readiness(df)
    df = calcular_tendencia_tqr(df)
    df = generar_alertas(df)

    print("✅ Métricas wellness calculadas\n")

    print("─── Readiness por jugadora (último registro) ───")
    ultimo = df.sort_values("fecha").groupby("player_id").last().reset_index()
    print(ultimo[["nombre", "fecha", "tqr", "rpe",
                  "readiness_index", "readiness_zona"]].to_string(index=False))

    print("\n─── Alertas activas ───")
    alertas = resumen_alertas_equipo(df)
    if len(alertas) > 0:
        print(alertas[["nombre", "tqr", "rpe",
                        "readiness_index", "total_alertas"]].to_string(index=False))
    else:
        print("✅ Sin alertas activas")