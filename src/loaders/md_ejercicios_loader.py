# src/loaders/md_ejercicios_loader.py
"""
Loader de la propuesta de ejercicios por Match Day — lee la pestaña
"MD_Ejercicios" del mismo Google Sheet de wellness. Cargada a mano por el
cuerpo técnico como texto libre (sin un separador fijo entre ítems, ver
dividir_en_bullets() en src/metrics/foda.py para el parseo a viñetas).
"""
import pandas as pd
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent.parent))

# La primera columna de la pestaña no tiene encabezado (celda vacía en el
# Sheet) — pandas la nombra "Unnamed: 0", por eso se renombra por posición
# en vez de por nombre, a diferencia de las otras 3 columnas.
COLUMN_MAP = {
    "FISICO":           "fisico",
    "TECNICO-TACTICO":  "tecnico_tactico",
    "OBJETIVOS":        "objetivos",
}


def _procesar_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns={df.columns[0]: "match_day"})
    df = df.rename(columns=COLUMN_MAP)
    df["match_day"] = df["match_day"].astype(str).str.strip()
    for col in ("fisico", "tecnico_tactico", "objetivos"):
        df[col] = df[col].fillna("").astype(str).str.strip()
    return df[["match_day", "fisico", "tecnico_tactico", "objetivos"]]


def cargar_md_ejercicios_desde_sheets(sheet_id: str, gid: str) -> pd.DataFrame:
    """Lee la pestaña 'MD_Ejercicios' del Google Sheet público y devuelve
    [match_day, fisico, tecnico_tactico, objetivos]."""
    url = (f"https://docs.google.com/spreadsheets/d/{sheet_id}"
           f"/export?format=csv&gid={gid}")
    return _procesar_df(pd.read_csv(url))


if __name__ == "__main__":
    from settings import WELLNESS_SHEET_ID, MD_EJERCICIOS_SHEET_GID
    df = cargar_md_ejercicios_desde_sheets(WELLNESS_SHEET_ID, MD_EJERCICIOS_SHEET_GID)
    print(f"\n✅ MD_Ejercicios cargados: {len(df)} filas")
    print(df.to_string(index=False))
