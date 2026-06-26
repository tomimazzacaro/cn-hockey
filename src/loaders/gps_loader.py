# src/loaders/gps_loader.py
"""
Loader para exports CSV de Catapult — Hockey CN Femenino.
Mapea las columnas reales del export al esquema canónico interno.
Extrae la fecha desde el nombre del archivo (formato: export_DD-MM-YY.csv)
"""
import pandas as pd
from pathlib import Path
import sys
import re

sys.path.append(str(Path(__file__).parent.parent.parent))
from settings import RAW_GPS, PROCESSED


# ── Mapeo columnas Catapult → canónicas ────────────────────────────────────
COLUMN_MAP = {
    "Name":                     "nombre",
    "Total Duration":           "duracion",
    "Total Distance (m)":       "distancia_total",
    "Max Vel (% Max)":          "vel_max_pct",
    "Maximum Velocity (m/s)":   "vel_max_ms",
    "HSR Distance (m)":         "hsr",
    "HSR Efforts":              "hsr_esfuerzos",
    "Sprint Efforts":           "sprints",
    "DECC>3":                   "decc_3",
    "DECC>2":                   "decc_2",
    "ACC>3":                    "acc_3",
    "ACC>2":                    "acc_2",
    "Total Player Load":        "player_load",
    "Player Load (1D Fwd)":     "pl_fwd",
    "Player Load (1D Side)":    "pl_side",
    "Player Load (1D Up)":      "pl_up",
    "Player Load (2D)":         "pl_2d",
    "Player Load (Slow)":       "pl_slow",
    "Total Acceleration Load":  "acc_load",
}


def _extraer_fecha(nombre_archivo: str) -> pd.Timestamp:
    """
    Extrae la fecha del nombre del archivo Catapult.
    Formato esperado: export_DD-MM-YY.csv  →  ej: export_27-06-26.csv
    """
    match = re.search(r"(\d{2})-(\d{2})-(\d{2})", nombre_archivo)
    if not match:
        raise ValueError(
            f"No se pudo extraer fecha del archivo: '{nombre_archivo}'\n"
            f"Formato esperado: export_DD-MM-YY.csv"
        )
    dia, mes, anio = match.groups()
    return pd.Timestamp(f"20{anio}-{mes}-{dia}")


def _generar_player_id(nombre: str) -> str:
    """
    Genera un player_id limpio desde el nombre completo.
    Ej: 'ANA SOSA' → 'ana_sosa'
    """
    return nombre.strip().lower().replace(" ", "_")


def _convertir_duracion(duracion_str: str) -> float:
    """
    Convierte string de duración 'HH:MM:SS' a minutos decimales.
    Ej: '01:57:14' → 117.23
    """
    try:
        partes = str(duracion_str).split(":")
        if len(partes) == 3:
            h, m, s = int(partes[0]), int(partes[1]), int(partes[2])
            return round(h * 60 + m + s / 60, 2)
        elif len(partes) == 2:
            m, s = int(partes[0]), int(partes[1])
            return round(m + s / 60, 2)
    except Exception:
        pass
    return None


def cargar_sesion_gps(path_csv: str | Path) -> pd.DataFrame:
    """
    Carga un CSV de Catapult, normaliza columnas y agrega fecha + player_id.

    Args:
        path_csv: Ruta al archivo CSV exportado de Catapult.

    Returns:
        DataFrame con esquema canónico interno listo para análisis.
    """
    path_csv = Path(path_csv)

    # 1 — Leer CSV crudo
    df = pd.read_csv(path_csv)

    # 2 — Renombrar columnas al esquema canónico
    df = df.rename(columns=COLUMN_MAP)

    # 3 — Extraer fecha del nombre del archivo
    fecha = _extraer_fecha(path_csv.name)
    df["fecha"] = fecha.date()

    # 4 — Generar player_id desde nombre
    df["player_id"] = df["nombre"].apply(_generar_player_id)

    # 5 — Convertir duración a minutos decimales
    df["duracion_min"] = df["duracion"].apply(_convertir_duracion)
    df = df.drop(columns=["duracion"])

    # 6 — Convertir vel_max de m/s a km/h (más intuitivo para el cuerpo técnico)
    df["vel_max_kmh"] = (df["vel_max_ms"] * 3.6).round(2)

    # 7 — Ordenar columnas: identificadores primero
    cols_orden = [
        "player_id", "nombre", "fecha",
        "duracion_min", "distancia_total",
        "hsr", "hsr_esfuerzos", "sprints",
        "acc_3", "acc_2", "decc_3", "decc_2",
        "vel_max_kmh", "vel_max_ms", "vel_max_pct",
        "player_load", "pl_fwd", "pl_side", "pl_up", "pl_2d", "pl_slow",
        "acc_load",
    ]
    df = df[cols_orden]

    # 7b — Filtro de calidad: excluir registros con distancia irreal
    n_antes = len(df)
    df = df[df["distancia_total"] > 500].reset_index(drop=True)
    n_despues = len(df)
    if n_antes != n_despues:
        print(f"  ⚠️  Se excluyeron {n_antes - n_despues} registros con distancia < 500m")

    # 8 — Redondear métricas continuas
    cols_redondear = ["distancia_total", "hsr", "player_load",
                      "pl_fwd", "pl_side", "pl_up", "pl_2d", "pl_slow"]
    df[cols_redondear] = df[cols_redondear].round(2)

    return df


def cargar_todas_las_sesiones(carpeta: str | Path = None) -> pd.DataFrame:
    """
    Carga y concatena todos los CSV de Catapult en una carpeta.
    Útil cuando tenés múltiples sesiones acumuladas.

    Args:
        carpeta: Ruta a la carpeta con los CSV. Default: RAW_GPS de settings.py

    Returns:
        DataFrame unificado con todas las sesiones, ordenado por fecha.
    """
    carpeta = Path(carpeta) if carpeta else RAW_GPS
    archivos = sorted(carpeta.glob("*.csv"))

    if not archivos:
        raise FileNotFoundError(f"No se encontraron archivos CSV en: {carpeta}")

    sesiones = []
    for archivo in archivos:
        try:
            df = cargar_sesion_gps(archivo)
            sesiones.append(df)
            print(f"  ✅ {archivo.name} — {len(df)} jugadoras")
        except Exception as e:
            print(f"  ⚠️  {archivo.name} — ERROR: {e}")

    if not sesiones:
        raise ValueError("Ningún archivo se pudo cargar correctamente.")

    df_total = pd.concat(sesiones, ignore_index=True)
    df_total = df_total.sort_values(["fecha", "nombre"]).reset_index(drop=True)

    return df_total


def guardar_procesado(df: pd.DataFrame,
                      nombre: str = "gps_procesado.parquet") -> Path:
    """Guarda el DataFrame procesado en Parquet."""
    PROCESSED.mkdir(parents=True, exist_ok=True)
    destino = PROCESSED / nombre
    df.to_parquet(destino, index=False)
    print(f"💾 Guardado: {destino}")
    return destino


# ── Test rápido ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    # Aceptar ruta como argumento o usar el archivo de uploads
    if len(sys.argv) > 1:
        ruta = sys.argv[1]
    else:
        print("Uso: python gps_loader.py <ruta_al_csv>")
        sys.exit(1)

    df = cargar_sesion_gps(ruta)
    print(f"\n✅ Sesión cargada: {len(df)} jugadoras | Fecha: {df['fecha'].iloc[0]}")
    print(f"\n{df[['nombre','fecha','distancia_total','hsr','sprints','player_load','vel_max_kmh']].to_string(index=False)}")

    guardar_procesado(df)
    print("\n💾 Parquet guardado en data/processed/")