# src/loaders/fuerza_loader.py
"""
Loaders de fuerza — pestañas "Catalogo_Fuerza" y "Fuerza_Plan" de la planilla
"Planificacion_fuerza" (ver FUERZA_SHEET_ID en settings.py).

Catalogo_Fuerza es un catálogo CERRADO: el formulario de carga solo ofrece
estos ejercicios (nunca se tipea). Los ejercicios sin RM propio (ADMITE_RM =
No, ej. tirones de cargada) declaran en EJERCICIO_REFERENCIA el ejercicio cuyo
RM se usa para calcular el %RM.

Fuerza_Plan es lo PLANIFICADO (series x reps x %RM por Match Day). Lo
realmente ejecutado vive en Supabase (fuerza_registro), no acá.
"""
import pandas as pd
import psycopg
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent.parent))
from src.loaders.wellness_loader import normalizar_nombre

COLUMN_MAP_CATALOGO = {
    "EJERCICIO":            "ejercicio",
    "EJERCICIOS":           "ejercicio",   # la planilla actual usa el plural
    "CATEGORIA":            "categoria",
    "UNILATERAL":           "unilateral",
    "ADMITE_RM":            "admite_rm",
    "EJERCICIO_REFERENCIA": "ejercicio_referencia",
    "ID":                   "ejercicio_id",  # FZA-### (ver docs/fuerza/PLAN.md)
}

# Catálogo de pasadas / resistencia (pestaña Catalogo_resist). Los nombres se
# repiten a propósito (hay varias "Pasadas"): lo que los distingue es el ID.
COLUMN_MAP_RESIST = {
    "NOMBRE_EJERCICIO": "ejercicio",
    "CATEGORIA":        "categoria",
    "ID":               "ejercicio_id",   # RES-###
}

COLUMN_MAP_PLAN = {
    "SEMANA":    "semana",
    "MATCH_DAY": "match_day",
    "EJERCICIO": "ejercicio",
    "ORDEN":     "orden",
    "SERIES":    "series",
    "REPS":      "reps",
    "PCT_RM":    "pct_rm",
}


def _es_si(serie: pd.Series) -> pd.Series:
    return serie.fillna("").astype(str).str.strip().str.lower().isin(["sí", "si"])


def _procesar_catalogo(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns=COLUMN_MAP_CATALOGO)
    # Columnas opcionales: si la planilla no las trae, se completan vacías.
    for col in ("categoria", "unilateral", "admite_rm", "ejercicio_referencia", "ejercicio_id"):
        if col not in df.columns:
            df[col] = ""
    df = df.dropna(subset=["ejercicio"]).reset_index(drop=True)

    df["ejercicio"] = df["ejercicio"].astype(str).str.strip()
    df = df[df["ejercicio"] != ""].reset_index(drop=True)

    df["categoria"] = df["categoria"].fillna("").astype(str).str.strip()
    df["unilateral"] = _es_si(df["unilateral"])
    df["admite_rm"] = _es_si(df["admite_rm"])
    df["ejercicio_referencia"] = (
        df["ejercicio_referencia"].fillna("").astype(str).str.strip()
    )
    df["ejercicio_id"] = df["ejercicio_id"].fillna("").astype(str).str.strip()

    return df[["ejercicio_id", "ejercicio", "categoria", "unilateral", "admite_rm",
               "ejercicio_referencia"]]


def _procesar_catalogo_resist(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns=COLUMN_MAP_RESIST)
    for col in ("categoria", "ejercicio_id"):
        if col not in df.columns:
            df[col] = ""
    df = df.dropna(subset=["ejercicio"]).reset_index(drop=True)
    df["ejercicio"] = df["ejercicio"].astype(str).str.strip()
    df = df[df["ejercicio"] != ""].reset_index(drop=True)
    df["categoria"] = df["categoria"].fillna("").astype(str).str.strip()
    df["ejercicio_id"] = df["ejercicio_id"].fillna("").astype(str).str.strip()
    return df[["ejercicio_id", "ejercicio", "categoria"]]


def _procesar_plan(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns=COLUMN_MAP_PLAN)
    df = df.dropna(subset=["ejercicio"]).reset_index(drop=True)

    for col in ("semana", "match_day", "ejercicio"):
        df[col] = df[col].fillna("").astype(str).str.strip()
    df = df[df["ejercicio"] != ""].reset_index(drop=True)

    for col in ("orden", "series", "reps", "pct_rm"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return df[["semana", "match_day", "ejercicio", "orden", "series", "reps", "pct_rm"]]


def _url_csv(sheet_id: str, gid: str) -> str:
    return (f"https://docs.google.com/spreadsheets/d/{sheet_id}"
            f"/export?format=csv&gid={gid}")


def cargar_catalogo_fuerza_desde_sheets(sheet_id: str, gid: str) -> pd.DataFrame:
    """Lee 'Catalogo_fuerza' y devuelve [ejercicio_id, ejercicio, categoria, unilateral, admite_rm, ejercicio_referencia]."""
    return _procesar_catalogo(pd.read_csv(_url_csv(sheet_id, gid)))


def cargar_catalogo_resist_desde_sheets(sheet_id: str, gid: str) -> pd.DataFrame:
    """Lee 'Catalogo_resist' (pasadas, intermitentes) y devuelve [ejercicio_id, ejercicio, categoria]."""
    return _procesar_catalogo_resist(pd.read_csv(_url_csv(sheet_id, gid)))


def cargar_plan_fuerza_desde_sheets(sheet_id: str, gid: str) -> pd.DataFrame:
    """Lee 'Fuerza_Plan' y devuelve [semana, match_day, ejercicio, orden, series, reps, pct_rm]."""
    return _procesar_plan(pd.read_csv(_url_csv(sheet_id, gid)))


def _con_player_id(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega player_id (misma clave que GPS/wellness/roster) a partir del nombre."""
    df = df.copy()
    df["player_id"] = df["nombre_completo"].apply(normalizar_nombre)
    return df.rename(columns={"nombre_completo": "nombre"})


def cargar_rm_desde_supabase(connection_string: str) -> pd.DataFrame:
    """
    RM autorreportado por las jugadoras (registros_rm, vista jugadoras_rm_analitica,
    rol streamlit_readonly). Devuelve [jugadora_id, player_id, nombre, ejercicio
    (slug), rm_kg, fecha]; pasar por metrics.fuerza.normalizar_registros_rm().
    """
    query = "select jugadora_id, nombre_completo, ejercicio, rm_kg, fecha from jugadoras_rm_analitica"
    with psycopg.connect(connection_string) as conn:
        df = pd.read_sql(query, conn)
    df["rm_kg"] = pd.to_numeric(df["rm_kg"])
    return _con_player_id(df)


def cargar_series_desde_supabase(connection_string: str) -> pd.DataFrame:
    """Series realizadas (vista jugadoras_fuerza_analitica, rol de solo lectura)."""
    query = ("select jugadora_id, nombre_completo, fecha, ejercicio, nro_serie, reps, kg, rir "
             "from jugadoras_fuerza_analitica")
    with psycopg.connect(connection_string) as conn:
        df = pd.read_sql(query, conn)
    df["kg"] = pd.to_numeric(df["kg"])
    df["fecha"] = pd.to_datetime(df["fecha"])
    return _con_player_id(df)


def cargar_jugadoras_desde_supabase(connection_string: str) -> pd.DataFrame:
    """
    Jugadoras elegibles para el formulario: [jugadora_id, nombre]. Sale de las vistas
    de lectura (no de la tabla jugadoras: el rol de escritura no la puede leer por RLS).
    """
    query = """
        select jugadora_id, nombre_completo from jugadoras_wellness_analitica
        union
        select jugadora_id, nombre_completo from jugadoras_rm_analitica
    """
    with psycopg.connect(connection_string) as conn:
        df = pd.read_sql(query, conn)
    return (df.rename(columns={"nombre_completo": "nombre"})
              .sort_values("nombre").reset_index(drop=True))


_UPSERT_SERIES = """
    insert into fuerza_registro (jugadora_id, fecha, ejercicio, nro_serie, reps, kg, rir)
    values (%s, %s, %s, %s, %s, %s, %s)
    on conflict (jugadora_id, fecha, ejercicio, nro_serie)
    do update set reps = excluded.reps, kg = excluded.kg, rir = excluded.rir
"""


_BORRAR_SERIES_SOBRANTES = """
    delete from fuerza_registro
    where jugadora_id = %s and fecha = %s and ejercicio = %s and nro_serie > %s
"""


def guardar_series(connection_string: str, jugadora_id: str, fecha,
                   ejercicio: str, df_series: pd.DataFrame) -> int:
    """
    Guarda las series de UNA jugadora / ejercicio / día con el rol fuerza_writer.

    Upsert por (jugadora, fecha, ejercicio, nro_serie): volver a guardar corrige las
    series ya cargadas en vez de duplicarlas. Todo en una transacción (o entran todas
    o ninguna). prepare_threshold=None: el puerto 6543 es el Transaction Pooler de
    Supabase, que no soporta sentencias preparadas de psycopg.

    Args:
        df_series: salida de metrics.fuerza.armar_series().

    Returns:
        Cantidad de series guardadas.
    """
    filas = [
        (jugadora_id, fecha, ejercicio, int(r.nro_serie), int(r.reps), float(r.kg),
         None if pd.isna(r.rir) else int(r.rir))
        for r in df_series.itertuples(index=False)
    ]
    if not filas:
        return 0
    with psycopg.connect(connection_string, prepare_threshold=None) as conn:
        with conn.cursor() as cur:
            cur.executemany(_UPSERT_SERIES, filas)
            # Reemplazo completo: si antes había más series que ahora (se borró una
            # fila en el editor), las sobrantes no pueden quedar como fantasmas.
            cur.execute(_BORRAR_SERIES_SOBRANTES,
                        (jugadora_id, fecha, ejercicio, len(filas)))
    return len(filas)


if __name__ == "__main__":
    from settings import FUERZA_SHEET_ID, CATALOGO_FUERZA_SHEET_GID, FUERZA_PLAN_SHEET_GID
    cat = cargar_catalogo_fuerza_desde_sheets(FUERZA_SHEET_ID, CATALOGO_FUERZA_SHEET_GID)
    print(f"\n✅ Catálogo de fuerza: {len(cat)} filas")
    print(cat.to_string(index=False))
    plan = cargar_plan_fuerza_desde_sheets(FUERZA_SHEET_ID, FUERZA_PLAN_SHEET_GID)
    print(f"\n✅ Plan de fuerza: {len(plan)} filas")
    print(plan.to_string(index=False))
