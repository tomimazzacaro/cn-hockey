# src/loaders/sesiones_loader.py
"""
Loader del calendario de sesiones — Match Day, tipo de día y rival.
Lee la pestaña "Sesiones" del mismo Google Sheet de wellness.
"""
import pandas as pd
import re
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent.parent))

COLUMN_MAP = {
    "Fecha":       "fecha",
    "Match Day":   "match_day",
    "Tipo_sesion": "tipo_dia",
    "Partido_vs":  "rival",
}


def _parsear_fecha(fecha_str) -> pd.Timestamp:
    return pd.to_datetime(fecha_str, dayfirst=True, errors="coerce")


def _procesar_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns=COLUMN_MAP)
    df = df.dropna(subset=["fecha"]).reset_index(drop=True)

    df["fecha"]     = df["fecha"].apply(_parsear_fecha).dt.date
    df["match_day"] = df["match_day"].astype(str).str.strip()
    df["tipo_dia"]  = df["tipo_dia"].astype(str).str.strip().str.title()
    df["rival"]     = df["rival"].fillna("").astype(str).str.strip()

    return df[["fecha", "match_day", "tipo_dia", "rival"]]


def cargar_sesiones_desde_sheets(sheet_id: str, gid: str) -> pd.DataFrame:
    """Lee la pestaña 'Sesiones' del Google Sheet público y devuelve
    [fecha, match_day, tipo_dia, rival]."""
    url = (f"https://docs.google.com/spreadsheets/d/{sheet_id}"
           f"/export?format=csv&gid={gid}")
    return _procesar_df(pd.read_csv(url))


def orden_match_day(match_day: str) -> int:
    """
    Clave de orden cronológico para valores tipo MD-5, MD-2, MD, MD+1.
    El orden alfabético falla acá porque '+' (43) < '-' (45) en ASCII,
    así que "MD+1" quedaría antes que "MD-2" ordenando como texto.
    """
    if match_day == "MD":
        return 0
    m = re.match(r"^MD([+-]\d+)$", match_day)
    return int(m.group(1)) if m else 999


if __name__ == "__main__":
    from settings import WELLNESS_SHEET_ID, SESIONES_SHEET_GID
    df = cargar_sesiones_desde_sheets(WELLNESS_SHEET_ID, SESIONES_SHEET_GID)
    print(f"\n✅ Sesiones cargadas: {len(df)} días")
    print(df.to_string(index=False))
