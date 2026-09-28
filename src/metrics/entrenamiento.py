# src/metrics/entrenamiento.py
"""
Monitoreo de cargas por día de entrenamiento (pages/06_sesiones_entrenamiento.py).

Unidad de análisis: una jugadora en un día — Físico + Técnico-Táctico (y los
cuartos de un amistoso) del mismo día se suman en un solo total, igual que
_totalizar_por_dia() del Asistente de Parámetros. Los amistosos entran como
referencia (marcados con `amistoso`), los partidos oficiales no: tienen su
propia página.
"""
import pandas as pd

from src.loaders.sesiones_loader import orden_match_day

# columna -> etiqueta legible. Orden = orden de las columnas en las tablas.
METRICAS_ENTRENAMIENTO = {
    "distancia_total": "Distancia (m)",
    "hsr":             "HSR (m)",
    "sprints":         "Sprints",
    "acc_2":           "ACC>2",
    "decc_3":          "DECC>3",
    "player_load":     "Player Load",
}

MDS_ENTRENAMIENTO = ["MD-5", "MD-4", "MD-2"]
TIPOS_ENTRENAMIENTO = ["Físico", "Técnico-Táctico"]
TIPO_AMISTOSO = "Amistoso"
SIN_POSICION = "Sin posición"
SIN_MICROCICLO = "Sin MD asignado"

_CLAVES_JUGADORA_DIA = ["player_id", "nombre", "posicion", "fecha", "match_day"]


def filtrar_entrenamientos(df: pd.DataFrame) -> pd.DataFrame:
    """Físico/TT de los días MD-5/MD-4/MD-2 + cualquier amistoso con MD asignado
    (en la práctica caen en MD-4, pero uno de sábado quedaría en "MD")."""
    es_entrenamiento = (df["tipo_sesion"].isin(TIPOS_ENTRENAMIENTO)
                        & df["match_day"].isin(MDS_ENTRENAMIENTO))
    es_amistoso = ((df["tipo_sesion"] == TIPO_AMISTOSO)
                   & df["match_day"].isin(MDS_ENTRENAMIENTO + ["MD"]))
    return df[es_entrenamiento | es_amistoso].reset_index(drop=True)


def totalizar_por_jugadora_dia(df: pd.DataFrame) -> pd.DataFrame:
    """Una fila por jugadora y día con la suma de cada métrica, más `amistoso`
    (True si ese día hubo al menos una sesión de amistoso)."""
    df = df.copy()
    # groupby descarta en silencio las filas con NaN en las claves — una
    # jugadora fuera del roster desaparecería de la página sin aviso.
    df["posicion"] = df["posicion"].fillna(SIN_POSICION)
    df["amistoso"] = df["tipo_sesion"] == TIPO_AMISTOSO
    cols = [c for c in METRICAS_ENTRENAMIENTO if c in df.columns]
    agg = {c: "sum" for c in cols} | {"amistoso": "any"}
    return df.groupby(_CLAVES_JUGADORA_DIA, as_index=False).agg(agg)


def asignar_microciclo(df: pd.DataFrame, df_sesiones: pd.DataFrame) -> pd.DataFrame:
    """
    Asigna cada día al microciclo del PRÓXIMO "MD" del calendario de Sesiones
    (el MD en sí incluido) — no a la semana de almanaque, así un cambio de día
    de partido no parte el microciclo en dos. Agrega `microciclo_fecha` (date
    del MD) y `microciclo` (etiqueta "vs Rival (dd/mm)").
    """
    mds = df_sesiones[df_sesiones["match_day"] == "MD"].copy()
    # En semanas sin partido el Sheet trae relleno en Partido_vs ("No hay
    # fecha", "Entrenamiento") — solo es rival si ese MD fue partido/amistoso.
    if "tipo_dia" in mds.columns:
        mds.loc[~mds["tipo_dia"].isin(["Partido", TIPO_AMISTOSO]), "rival"] = ""
    mds = mds[["fecha", "rival"]]
    mds["_ts"] = pd.to_datetime(mds["fecha"])
    mds = mds.sort_values("_ts").rename(columns={"fecha": "microciclo_fecha"})

    df = df.copy()
    df["_orden"] = range(len(df))
    df["_ts"] = pd.to_datetime(df["fecha"])
    df = pd.merge_asof(df.sort_values("_ts"), mds, on="_ts", direction="forward")
    df = df.sort_values("_orden").drop(columns=["_orden", "_ts"]).reset_index(drop=True)

    def _etiqueta(fila) -> str:
        if pd.isna(fila["microciclo_fecha"]):
            return SIN_MICROCICLO
        fecha = pd.Timestamp(fila["microciclo_fecha"]).strftime("%d/%m")
        rival = fila["rival"] if isinstance(fila["rival"], str) else ""
        return f"vs {rival} ({fecha})" if rival else f"MD {fecha}"

    df["microciclo"] = df.apply(_etiqueta, axis=1) if len(df) else pd.Series(dtype=str)
    return df.drop(columns=["rival"])


def promediar_por(df_total: pd.DataFrame, claves: list[str]) -> pd.DataFrame:
    """Promedio por jugadora de cada métrica (sobre el df ya totalizado por
    jugadora/día) agrupando por `claves`, más `n_jugadoras` con GPS."""
    cols = [c for c in METRICAS_ENTRENAMIENTO if c in df_total.columns]
    agg = {c: "mean" for c in cols}
    if "amistoso" in df_total.columns:
        agg["amistoso"] = "any"
    resultado = df_total.groupby(claves, as_index=False).agg(agg)
    n = df_total.groupby(claves)["nombre"].nunique().rename("n_jugadoras").reset_index()
    return resultado.merge(n, on=claves)


def pivot_por_md(df: pd.DataFrame, indice: str, metrica: str) -> pd.DataFrame:
    """`indice` × Match Day para una métrica, columnas en orden cronológico
    del microciclo (MD-5 → MD-4 → MD-2 → MD). Celda vacía = no hubo dato."""
    tabla = df.pivot_table(index=indice, columns="match_day", values=metrica, aggfunc="mean")
    tabla = tabla[sorted(tabla.columns, key=orden_match_day)]
    tabla.columns.name = None
    return tabla
