# src/loaders/fuerza_plan_loader.py
"""
Loaders del PLAN de fuerza y pasadas (tablas de la migración 0063 de Supabase).

Lectura: rol streamlit_readonly (wellness_connection_string).
Escritura: rol fuerza_writer (fuerza_connection_string).

Todas las escrituras van en UNA transacción: o entra todo o no entra nada.
prepare_threshold=None: el puerto 6543 es el Transaction Pooler de Supabase,
que no soporta sentencias preparadas de psycopg.
"""
import pandas as pd
import psycopg

from src.metrics.fuerza_plan import COLUMNAS_ITEM_PLAN, PARAMETROS_DEFAULT

_COLS_ITEMS_SQL = ", ".join(COLUMNAS_ITEM_PLAN)
_NUMERICAS = ["orden", "series", "repeticiones", "pct_rm", "distancia_m", "pct_vmax", "pausa_s"]


def _leer(connection_string: str, query: str, params: tuple = ()) -> pd.DataFrame:
    with psycopg.connect(connection_string) as conn:
        return pd.read_sql(query, conn, params=params)


# ── Lectura ──────────────────────────────────────────────────────────────────

def listar_planes(connection_string: str) -> pd.DataFrame:
    """Planes existentes, el más reciente primero: [id, semana_inicio, nombre, estado, notas]."""
    df = _leer(connection_string,
               "select id, semana_inicio, nombre, estado, notas from fuerza_planes "
               "order by semana_inicio desc")
    df["id"] = df["id"].astype(str)
    df["semana_inicio"] = pd.to_datetime(df["semana_inicio"]).dt.date
    return df


def cargar_items_plan(connection_string: str, plan_id: str) -> pd.DataFrame:
    """Ítems prescritos de un plan, con las columnas de COLUMNAS_ITEM_PLAN (más 'id')."""
    df = _leer(connection_string,
               f"select id, {_COLS_ITEMS_SQL} from fuerza_plan_items where plan_id = %s",
               (plan_id,))
    df["id"] = df["id"].astype(str)
    for col in _NUMERICAS:
        df[col] = pd.to_numeric(df[col])
    return df


def cargar_parametros(connection_string: str) -> dict:
    """
    Parámetros editables {clave: valor}. Lo que falte en la base se completa con
    los valores por defecto, así la página nunca se rompe por un parámetro borrado.
    """
    df = _leer(connection_string, "select clave, valor from fuerza_parametros")
    return {**PARAMETROS_DEFAULT, **{r.clave: float(r.valor) for r in df.itertuples(index=False)}}


def cargar_zonas_velocidad(connection_string: str) -> pd.DataFrame:
    """Zonas de pasadas: [nombre, orden, desde_pct_vmax, hasta_pct_vmax]. Puede estar vacía."""
    df = _leer(connection_string,
               "select nombre, orden, desde_pct_vmax, hasta_pct_vmax "
               "from zonas_velocidad order by orden")
    for col in ("desde_pct_vmax", "hasta_pct_vmax"):
        df[col] = pd.to_numeric(df[col])
    return df


# ── Escritura ────────────────────────────────────────────────────────────────

_UPSERT_PLAN = """
    insert into fuerza_planes (semana_inicio, nombre, estado, notas)
    values (%s, %s, %s, %s)
    on conflict (semana_inicio)
    do update set nombre = excluded.nombre, estado = excluded.estado, notas = excluded.notas
    returning id
"""

_UPSERT_ITEM = f"""
    insert into fuerza_plan_items (plan_id, {_COLS_ITEMS_SQL})
    values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    on conflict (plan_id, match_day, orden)
    do update set tipo = excluded.tipo, ejercicio_id = excluded.ejercicio_id,
                  ejercicio_nombre = excluded.ejercicio_nombre, series = excluded.series,
                  repeticiones = excluded.repeticiones, pct_rm = excluded.pct_rm,
                  distancia_m = excluded.distancia_m, zona = excluded.zona,
                  pct_vmax = excluded.pct_vmax, pausa_s = excluded.pausa_s,
                  notas = excluded.notas
"""

# Borra solo los ítems que YA NO están en el plan editado.
_BORRAR_ITEMS_SOBRANTES = """
    delete from fuerza_plan_items
    where plan_id = %s
      and (match_day, orden) not in (select * from unnest(%s::text[], %s::smallint[]))
"""


def _nulo(valor):
    """NaN / None / '' -> None (NULL en la base); lo demás pasa tal cual."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)) or valor == "":
        return None
    return valor


def _entero(valor):
    valor = _nulo(valor)
    return None if valor is None else int(valor)


def _decimal(valor):
    valor = _nulo(valor)
    return None if valor is None else float(valor)


def guardar_plan(connection_string: str, semana_inicio, nombre: str | None, estado: str,
                 notas: str | None, df_items: pd.DataFrame) -> str:
    """
    Guarda el plan de UNA semana con el rol fuerza_writer.

    Actualiza (upsert) por (plan, match_day, orden) en vez de borrar y recrear: así
    los ítems que siguen en el plan conservan su id y lo ya ejecutado sigue
    apuntando a ellos. Solo se borran los ítems que se quitaron del plan.
    OJO: si se reordenan ejercicios dentro de un día, cada 'orden' pasa a tener
    otro contenido; el vínculo con lo ejecutado es informativo, no una garantía.

    Args:
        semana_inicio: lunes de la semana (date).
        estado: 'borrador' o 'publicado'.
        df_items: salida de metrics.fuerza_plan.armar_items_plan().

    Returns:
        id (str) del plan.
    """
    filas = [
        (r.match_day, int(r.orden), r.tipo, r.ejercicio_id, r.ejercicio_nombre,
         _entero(r.series), _entero(r.repeticiones), _decimal(r.pct_rm),
         _decimal(r.distancia_m), _nulo(r.zona), _decimal(r.pct_vmax),
         _entero(r.pausa_s), _nulo(r.notas))
        for r in df_items[COLUMNAS_ITEM_PLAN].itertuples(index=False)
    ]
    with psycopg.connect(connection_string, prepare_threshold=None) as conn:
        with conn.cursor() as cur:
            cur.execute(_UPSERT_PLAN, (semana_inicio, _nulo(nombre), estado, _nulo(notas)))
            plan_id = cur.fetchone()[0]
            cur.executemany(_UPSERT_ITEM, [(plan_id, *f) for f in filas])
            cur.execute(_BORRAR_ITEMS_SOBRANTES,
                        (plan_id, [f[0] for f in filas], [f[1] for f in filas]))
    return str(plan_id)


def guardar_parametro(connection_string: str, clave: str, valor: float) -> None:
    """Actualiza un parámetro editable existente (no crea claves nuevas)."""
    with psycopg.connect(connection_string, prepare_threshold=None) as conn:
        cur = conn.execute("update fuerza_parametros set valor = %s where clave = %s",
                           (float(valor), clave))
        if cur.rowcount != 1:
            raise ValueError(f"Parámetro inexistente: {clave!r}")
