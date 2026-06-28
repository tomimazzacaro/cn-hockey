# src/loaders/gps_loader.py
"""
Loader para exports CSV de Catapult — Hockey CN Femenino.
Soporta carga desde archivo local y desde st.file_uploader().
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

_COLS_ORDEN = [
    "player_id", "nombre", "fecha",
    "duracion_min", "distancia_total",
    "hsr", "hsr_esfuerzos", "sprints",
    "acc_3", "acc_2", "decc_3", "decc_2",
    "vel_max_kmh", "vel_max_ms", "vel_max_pct",
    "player_load", "pl_fwd", "pl_side", "pl_up", "pl_2d", "pl_slow",
    "acc_load",
]


def extraer_fecha_de_nombre(nombre_archivo: str) -> pd.Timestamp:
    """
    Extrae la fecha del nombre de archivo Catapult.
    Formato: export_DD-MM-YY.csv  →  ej: export_13-06-26.csv
    """
    match = re.search(r"(\d{2})-(\d{2})-(\d{2})", nombre_archivo)
    if not match:
        raise ValueError(
            f"No se pudo extraer fecha de '{nombre_archivo}'. "
            f"Formato esperado: export_DD-MM-YY.csv"
        )
    dia, mes, anio = match.groups()
    return pd.Timestamp(f"20{anio}-{mes}-{dia}")


def _generar_player_id(nombre: str) -> str:
    return nombre.strip().lower().replace(" ", "_")


def _convertir_duracion(duracion_str: str) -> float:
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


def _procesar_sesion(df: pd.DataFrame, fecha) -> pd.DataFrame:
    """Aplica el esquema canónico a un DataFrame crudo de Catapult."""
    df = df.rename(columns=COLUMN_MAP)

    ts = pd.Timestamp(fecha)
    df["fecha"]      = ts.date()
    df["player_id"]  = df["nombre"].apply(_generar_player_id)
    df["duracion_min"] = df["duracion"].apply(_convertir_duracion)
    df = df.drop(columns=["duracion"])
    df["vel_max_kmh"] = (df["vel_max_ms"] * 3.6).round(2)

    df = df[_COLS_ORDEN]

    df = df[df["distancia_total"] > 500].reset_index(drop=True)

    cols_redondear = ["distancia_total", "hsr", "player_load",
                      "pl_fwd", "pl_side", "pl_up", "pl_2d", "pl_slow"]
    df[cols_redondear] = df[cols_redondear].round(2)

    return df


def cargar_sesion_gps(path_csv: str | Path) -> pd.DataFrame:
    """Carga un CSV de Catapult desde ruta local."""
    path_csv = Path(path_csv)
    df    = pd.read_csv(path_csv)
    fecha = extraer_fecha_de_nombre(path_csv.name)
    return _procesar_sesion(df, fecha)


def cargar_sesion_desde_upload(uploaded_file, fecha_override=None) -> pd.DataFrame:
    """
    Carga una sesión GPS desde st.file_uploader().

    Args:
        uploaded_file: UploadedFile de Streamlit.
        fecha_override: datetime.date — si se provee, ignora el nombre del archivo.
    """
    df = pd.read_csv(uploaded_file)
    if fecha_override is not None:
        fecha = fecha_override
    else:
        fecha = extraer_fecha_de_nombre(uploaded_file.name)
    return _procesar_sesion(df, fecha)


def cargar_todas_las_sesiones(carpeta: str | Path = None) -> pd.DataFrame:
    carpeta  = Path(carpeta) if carpeta else RAW_GPS
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

    return (pd.concat(sesiones, ignore_index=True)
              .sort_values(["fecha", "nombre"])
              .reset_index(drop=True))


def guardar_procesado(df: pd.DataFrame,
                      nombre: str = "gps_procesado.parquet") -> Path:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    destino = PROCESSED / nombre
    df.to_parquet(destino, index=False)
    print(f"💾 Guardado: {destino}")
    return destino


if __name__ == "__main__":
    if len(sys.argv) > 1:
        df = cargar_sesion_gps(sys.argv[1])
    else:
        print("Uso: python gps_loader.py <ruta_al_csv>")
        sys.exit(1)

    print(f"\n✅ Sesión cargada: {len(df)} jugadoras | Fecha: {df['fecha'].iloc[0]}")
    print(df[["nombre", "fecha", "distancia_total", "hsr",
              "sprints", "player_load", "vel_max_kmh"]].to_string(index=False))
    guardar_procesado(df)
    print("\n💾 Parquet guardado en data/processed/")
