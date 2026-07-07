# src/loaders/roster_loader.py
"""
Loader del plantel — mapea jugadora → posición.
Lee la pestaña "Plantel" del mismo Google Sheet de wellness.
"""
import pandas as pd
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent.parent))
from src.loaders.wellness_loader import normalizar_nombre

COLUMN_MAP = {
    "Jugadora": "nombre",
    "Posicion": "posicion",
}


def _procesar_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns=COLUMN_MAP)
    df = df.dropna(subset=["nombre"]).reset_index(drop=True)

    df["posicion"]  = df["posicion"].str.strip().str.upper()
    df["player_id"] = df["nombre"].apply(normalizar_nombre)

    return df[["player_id", "nombre", "posicion"]]


def cargar_posiciones_desde_sheets(sheet_id: str, gid: str) -> pd.DataFrame:
    """Lee la pestaña de posiciones del Google Sheet público y devuelve [player_id, nombre, posicion]."""
    url = (f"https://docs.google.com/spreadsheets/d/{sheet_id}"
           f"/export?format=csv&gid={gid}")
    return _procesar_df(pd.read_csv(url))
