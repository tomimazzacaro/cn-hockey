# src/loaders/categoria_loader.py
"""
Loader de categoría — mapea jugadora -> categoria (1era / Intermedia).

Lee "Info_jugadoras", una planilla SEPARADA de la de Carga_interna_CNaval
(wellness/roster/sesiones/parametros) — no es una pestaña de esa, es otro
Google Sheet (ver INFO_JUGADORAS_SHEET_ID en settings.py). Se usa para
filtrar el reporte semanal a solo jugadoras de 1era división, ya que el
tab "Plantel" de la planilla principal (roster_loader.py) no distingue
categoría.

Ojo: esta planilla mezcla jugadoras Y CUERPO TÉCNICO en las mismas filas
categoria="1era" (el staff de 1era también está tageado "1era" ahí, tiene
sentido para otros usos de esa planilla pero NO para nuestro filtro). La
columna POSICION es la forma de distinguirlos: el staff tiene
POSICION="STAFF" literal; las jugadoras tienen una posición real (CENTRAL,
VOLANTE, DELANTERA, DEFENSORA, ARQUERA). `jugadoras_primera()` ya excluye
STAFF -- no filtrar solo por categoria en el resto del código.
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).parent.parent.parent))
from src.loaders.wellness_loader import normalizar_nombre

COLUMN_MAP = {
    "JUGADORA": "nombre",
    "POSICION": "posicion",
    "CATEGORIA": "categoria",
}


def _procesar_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns=COLUMN_MAP)
    df = df.dropna(subset=["nombre"]).reset_index(drop=True)

    df["categoria"] = df["categoria"].astype(str).str.strip()
    df["posicion"] = df["posicion"].astype(str).str.strip().str.upper()
    df["player_id"] = df["nombre"].apply(normalizar_nombre)
    df["es_staff"] = df["posicion"].eq("STAFF")

    return df[["player_id", "nombre", "categoria", "posicion", "es_staff"]]


def cargar_categoria_desde_sheets(sheet_id: str, gid: str) -> pd.DataFrame:
    """Lee la planilla Info_jugadoras y devuelve [player_id, nombre, categoria, posicion, es_staff]."""
    url = (f"https://docs.google.com/spreadsheets/d/{sheet_id}"
           f"/export?format=csv&gid={gid}")
    return _procesar_df(pd.read_csv(url))


def jugadoras_primera(df_categoria: pd.DataFrame, categoria_primera: str) -> set:
    """player_id de jugadoras (no staff) cuya categoria == categoria_primera."""
    mask = (df_categoria["categoria"] == categoria_primera) & (~df_categoria["es_staff"])
    return set(df_categoria.loc[mask, "player_id"])


def advertir_no_matcheadas(player_ids_gps: set, df_categoria: pd.DataFrame) -> list[str]:
    """
    player_id que aparecen en el GPS/wellness pero NO están en Info_jugadoras
    -- nunca los descartamos en silencio: se listan para que el reporte
    (o quien lo corre) los revise, porque puede ser un desajuste de nombre
    (normalizar_nombre) y no una jugadora fuera del plantel.
    """
    conocidos = set(df_categoria["player_id"])
    return sorted(player_ids_gps - conocidos)
