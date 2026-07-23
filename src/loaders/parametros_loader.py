# src/loaders/parametros_loader.py
"""
Loader de parámetros esperados — rangos objetivo por Match Day, Posición y
Métrica. Lee la pestaña "Parametros" del mismo Google Sheet de wellness.
"""
import pandas as pd
import re
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent.parent))

COLUMN_MAP = {
    "Match Day": "match_day",
    "Posicion":  "posicion",
    "Metrica":   "metrica",
    "Valor":     "valor",
}

_RANGO_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*$")


def _parsear_rango(valor) -> tuple[float, float] | None:
    """
    Convierte '2500-3000' en (2500.0, 3000.0). Devuelve None si la celda
    está vacía o no tiene el formato "min-max" esperado — significa que
    todavía no se cargó ese parámetro en el Sheet, no un error.
    """
    if pd.isna(valor):
        return None
    match = _RANGO_RE.match(str(valor))
    if not match:
        return None
    return float(match.group(1)), float(match.group(2))


def _procesar_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns=COLUMN_MAP)
    df["match_day"] = df["match_day"].astype(str).str.strip()
    df["posicion"]  = df["posicion"].astype(str).str.strip()
    df["metrica"]   = df["metrica"].astype(str).str.strip()

    rangos = df["valor"].apply(_parsear_rango)
    df["rango_min"] = pd.to_numeric(rangos.apply(lambda r: r[0] if r else None))
    df["rango_max"] = pd.to_numeric(rangos.apply(lambda r: r[1] if r else None))

    return df[["match_day", "posicion", "metrica", "rango_min", "rango_max"]]


def cargar_parametros_desde_sheets(sheet_id: str, gid: str) -> pd.DataFrame:
    """Lee la pestaña 'Parametros' del Google Sheet público y devuelve
    [match_day, posicion, metrica, rango_min, rango_max]. Una combinación
    todavía sin cargar en el Sheet queda con rango_min/rango_max en NA, no
    se descarta la fila — quien consume esto decide qué hacer con eso."""
    url = (f"https://docs.google.com/spreadsheets/d/{sheet_id}"
           f"/export?format=csv&gid={gid}")
    return _procesar_df(pd.read_csv(url))


if __name__ == "__main__":
    from settings import WELLNESS_SHEET_ID, PARAMETROS_SHEET_GID
    df = cargar_parametros_desde_sheets(WELLNESS_SHEET_ID, PARAMETROS_SHEET_GID)
    print(f"\n✅ Parámetros cargados: {len(df)} combinaciones")
    print(df.to_string(index=False))
