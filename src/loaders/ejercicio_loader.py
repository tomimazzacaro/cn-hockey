# src/loaders/ejercicio_loader.py
"""
Loader del catálogo de ejercicios — pestaña "Catalogo_Ejercicios" del mismo
Google Sheet de wellness (ver CATALOGO_EJERCICIOS_SHEET_GID en settings.py).

Distinto de "MD_Ejercicios" (src/loaders/md_ejercicios_loader.py): aquella
pestaña es texto libre de periodización por Match Day (propuesta del cuerpo
técnico, sin estructura). Esta es un catálogo CERRADO — una lista fija de
nombres de ejercicio de la que se ELIGE (nunca se tipea) al taguear un
bloque real de una sesión Técnico-Táctica, para que el mismo ejercicio
quede identificado con el mismo nombre entre sesiones distintas. Ver
src/metrics/biblioteca_ejercicios.py, que agrupa por este nombre.
"""
import pandas as pd
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent.parent))

COLUMN_MAP = {
    "NOMBRE_EJERCICIO": "nombre",
    "CATEGORIA":         "categoria",
}


def _procesar_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns=COLUMN_MAP)
    df = df.dropna(subset=["nombre"]).reset_index(drop=True)

    df["nombre"] = df["nombre"].astype(str).str.strip()
    df["categoria"] = df["categoria"].fillna("").astype(str).str.strip()
    df = df[df["nombre"] != ""].reset_index(drop=True)

    return df[["nombre", "categoria"]]


def cargar_catalogo_ejercicios_desde_sheets(sheet_id: str, gid: str) -> pd.DataFrame:
    """Lee la pestaña 'Catalogo_Ejercicios' y devuelve [nombre, categoria]."""
    url = (f"https://docs.google.com/spreadsheets/d/{sheet_id}"
           f"/export?format=csv&gid={gid}")
    return _procesar_df(pd.read_csv(url))


if __name__ == "__main__":
    from settings import WELLNESS_SHEET_ID, CATALOGO_EJERCICIOS_SHEET_GID
    df = cargar_catalogo_ejercicios_desde_sheets(WELLNESS_SHEET_ID, CATALOGO_EJERCICIOS_SHEET_GID)
    print(f"\n✅ Catálogo de ejercicios: {len(df)} filas")
    print(df.to_string(index=False))
