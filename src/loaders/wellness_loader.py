# src/loaders/wellness_loader.py
"""
Loader para wellness — soporta CSV local y Google Sheets público.
Form: Recuperación (TQR) + Esfuerzo (RPE) + Molestias físicas.
"""
import pandas as pd
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent.parent))
from settings import RAW_WELL, PROCESSED


# ── Mapeo columnas Form → canónicas ───────────────────────────────────────
COLUMN_MAP = {
    "Nombre completo": "nombre",
    "Fecha":           "fecha",
    "Recuperación":    "tqr",
    "Esfuerzo":        "rpe",
    "¿Tenés alguna molestia hoy? Indica dónde": "molestia",
}

COLS_DESCARTAR = ["Marca temporal", "Puntuación", "Columna 7"]

_RESPUESTAS_NEGATIVAS = {"no", "no.", "sin molestias", "nada", "ninguna",
                         "no, esta semana saf"}


def _normalizar_nombre(nombre: str) -> str:
    palabras = sorted(nombre.strip().upper().split())
    return "_".join(p.lower() for p in palabras)


def _parsear_fecha(fecha_str: str) -> pd.Timestamp:
    return pd.to_datetime(fecha_str, dayfirst=True, errors="coerce")


def _procesar_df(df: pd.DataFrame) -> pd.DataFrame:
    """Convierte un DataFrame crudo del form al esquema canónico."""
    cols_drop = [c for c in COLS_DESCARTAR if c in df.columns]
    df = df.drop(columns=cols_drop)

    df = df.rename(columns=COLUMN_MAP)
    df = df.dropna(subset=["nombre", "fecha"]).reset_index(drop=True)

    df["fecha"]     = df["fecha"].apply(_parsear_fecha).dt.date
    df["player_id"] = df["nombre"].apply(_normalizar_nombre)

    df["molestia"] = df["molestia"].fillna("Sin molestias")
    df["molestia"] = df["molestia"].apply(
        lambda x: "Sin molestias" if str(x).strip().lower() in _RESPUESTAS_NEGATIVAS else x
    )
    df["molestia_flag"] = df["molestia"] != "Sin molestias"

    df = (df.sort_values("rpe", ascending=False)
            .drop_duplicates(subset=["player_id", "fecha"], keep="first")
            .sort_values(["fecha", "nombre"])
            .reset_index(drop=True))

    for col in ["tqr", "rpe"]:
        df[col] = df[col].clip(1, 10)

    df["srpe"] = None

    cols_orden = ["player_id", "nombre", "fecha", "tqr", "rpe", "srpe",
                  "molestia", "molestia_flag"]
    return df[cols_orden].sort_values(["fecha", "nombre"]).reset_index(drop=True)


def cargar_wellness(path_csv: str | Path) -> pd.DataFrame:
    """Carga el CSV de respuestas de Google Forms y lo normaliza."""
    return _procesar_df(pd.read_csv(Path(path_csv)))


def cargar_desde_sheets(sheet_id: str, gid: str) -> pd.DataFrame:
    """Lee el Google Sheet público (sin autenticación) y devuelve el DataFrame normalizado."""
    url = (f"https://docs.google.com/spreadsheets/d/{sheet_id}"
           f"/export?format=csv&gid={gid}")
    return _procesar_df(pd.read_csv(url))


def guardar_procesado(df: pd.DataFrame,
                      nombre: str = "wellness_procesado.parquet") -> Path:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    destino = PROCESSED / nombre
    df.to_parquet(destino, index=False)
    print(f"💾 Guardado: {destino}")
    return destino


if __name__ == "__main__":
    if len(sys.argv) > 1:
        df = cargar_wellness(sys.argv[1])
    else:
        print("Uso: python wellness_loader.py <ruta_al_csv>")
        sys.exit(1)

    print(f"\n✅ Wellness cargado: {len(df)} registros | "
          f"{df['player_id'].nunique()} jugadoras | "
          f"{df['molestia_flag'].sum()} con molestias\n")
    print(df[["nombre", "fecha", "tqr", "rpe", "molestia_flag"]].to_string(index=False))

    molestias = df[df["molestia_flag"]][["nombre", "fecha", "molestia"]]
    if len(molestias) > 0:
        print(f"\n🚨 MOLESTIAS REGISTRADAS:")
        print(molestias.to_string(index=False))

    guardar_procesado(df)
    print("\n💾 Parquet guardado en data/processed/")
