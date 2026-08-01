# src/metrics/parametros.py
"""
Evaluación de cumplimiento de parámetros — compara sesiones reales de GPS
contra el rango esperado por Match Day y Posición (hoja "Parametros").
Referencia de zonas: mismo esquema semáforo que ACWR/Readiness (ver
ZONE_CFG/READINESS_CFG en src/ui/theme.py), no un sistema nuevo.
"""
import pandas as pd

# Métrica (texto tal cual en la hoja "Parametros") → columna real del GPS
# procesado. "Sprints distancia" queda afuera a propósito: Catapult todavía
# no exporta esa columna — se suma acá el día que exista en el parquet.
METRICA_A_COLUMNA = {
    "Distancia Total":  "distancia_total",
    "HSR Distance":     "hsr",
    "Sprints cantidad": "sprints",
    "Player Load":      "player_load",
    "ACC>2":            "acc_2",
    "DECC>3":           "decc_3",
}

SIN_DATO   = "Sin dato"
POR_DEBAJO = "Por debajo"
EN_RANGO   = "En rango"
POR_ENCIMA = "Por encima"


def _clasificar(valor: float, rango_min: float, rango_max: float) -> str:
    if pd.isna(valor):
        return SIN_DATO
    if valor < rango_min:
        return POR_DEBAJO
    if valor > rango_max:
        return POR_ENCIMA
    return EN_RANGO


def evaluar_sesion(fila_sesion: pd.Series, df_parametros: pd.DataFrame,
                    match_day: str) -> pd.DataFrame:
    """
    Compara una fila de sesión GPS (una jugadora, un día) contra los
    parámetros esperados para su posición en ese Match Day.

    Devuelve [metrica, valor_real, rango_min, rango_max, estado, z_score] —
    solo para las métricas que tienen columna real Y rango cargado en el
    Sheet; una combinación todavía sin completar en Parametros (rango_min/max
    en NA) se omite en vez de mostrarse como "Sin dato", que se reserva para
    cuando el rango sí existe pero la sesión no tiene ese valor registrado.

    "z_score" es un dato COMPLEMENTARIO al rango del Sheet, no un reemplazo:
    viene de calcular_zscore_historico() (physical.py) si la columna
    "{columna}_zscore" ya está en fila_sesion (igual que acwr/zona_acwr, se
    calcula página arriba, antes del filtro de fecha, sobre el historial
    completo de la jugadora). Si no vino calculada, queda None — "estado"
    (contra el rango del Sheet) sigue siendo la única fuente de verdad para
    fortaleza/debilidad en analisis.py.
    """
    posicion = fila_sesion.get("posicion")
    parametros_pos = df_parametros[
        (df_parametros["match_day"] == match_day) & (df_parametros["posicion"] == posicion)
    ]

    filas = []
    for metrica, columna in METRICA_A_COLUMNA.items():
        if columna not in fila_sesion.index:
            continue
        params = parametros_pos[parametros_pos["metrica"] == metrica]
        if params.empty:
            continue
        rango_min, rango_max = params.iloc[0][["rango_min", "rango_max"]]
        if pd.isna(rango_min) or pd.isna(rango_max):
            continue

        valor_real = fila_sesion.get(columna)
        filas.append({
            "metrica": metrica,
            "valor_real": valor_real,
            "rango_min": rango_min,
            "rango_max": rango_max,
            "estado": _clasificar(valor_real, rango_min, rango_max),
            "z_score": fila_sesion.get(f"{columna}_zscore"),
        })

    columnas = ["metrica", "valor_real", "rango_min", "rango_max", "estado", "z_score"]
    return pd.DataFrame(filas, columns=columnas)


def evaluar_sesiones(df_sesiones: pd.DataFrame, df_parametros: pd.DataFrame,
                     col_etiqueta: str, match_day: str | None = None) -> pd.DataFrame:
    """
    Igual que evaluar_sesion() pero para varias filas a la vez — una fila
    por (etiqueta, métrica). Sirve tanto para "una sesión, varias
    jugadoras" (Carga Física: col_etiqueta="nombre", match_day fijo, todas
    las filas son el mismo día) como para "una jugadora, varias sesiones"
    (Perfil de Jugadora: col_etiqueta = una columna con fecha/MD, match_day
    en None porque cada fila es un día distinto y trae su propio "match_day").

    Devuelve [etiqueta, metrica, valor_real, rango_min, rango_max, estado,
    z_score], pensado para pivotear a una tabla ancha (ver
    tabla_asistente_html en theme.py).
    """
    columnas = ["etiqueta", "metrica", "valor_real", "rango_min", "rango_max", "estado", "z_score"]
    bloques = []
    for _, fila in df_sesiones.iterrows():
        md = match_day if match_day is not None else fila.get("match_day")
        if md is None or pd.isna(md):
            continue
        evaluacion = evaluar_sesion(fila, df_parametros, md)
        if evaluacion.empty:
            continue
        evaluacion.insert(0, "etiqueta", fila.get(col_etiqueta))
        bloques.append(evaluacion)

    if not bloques:
        return pd.DataFrame(columns=columnas)
    return pd.concat(bloques, ignore_index=True)[columnas]


def _totalizar_por_dia(df: pd.DataFrame, claves: list[str], cols_metricas: list[str]) -> pd.DataFrame:
    """Suma cada métrica agrupando por `claves` — colapsa Físico+TT (u otras
    sesiones que compartan esas claves) del mismo día en un solo total."""
    return df.groupby(claves, as_index=False)[cols_metricas].sum()


def armar_evaluacion_equipo(df_filtrado: pd.DataFrame, df_parametros: pd.DataFrame, *,
                             claves_grupo: list[str], etiqueta_fn, match_day: str | None = None,
                             col_identidad: str = "nombre") -> pd.DataFrame:
    """
    Pipeline compartido del Asistente de Parámetros: totaliza por
    (col_identidad + claves_grupo) — junta Físico+TT del mismo día para la
    misma jugadora, sumándolos — y después promedia por claves_grupo, o sea
    entre las jugadoras que comparten esas claves (típicamente posición).

    Si col_identidad no está en el df (no debería pasar en uso normal) se
    saltea el paso de totalizar. Cuando ya hay una sola fila por
    (col_identidad + claves_grupo) — una sola jugadora, o datos ya agregados
    como los partidos "Completo" — el paso de promediar es un no-op sobre
    filas ya únicas, así que este pipeline sirve igual para "varias
    jugadoras, posible Físico+TT el mismo día" (Carga Física, Físico vs TT,
    Partidos) y para "una sola jugadora" (Perfil de Jugadora) sin ramas
    especiales por página.

    etiqueta_fn recibe una fila del df ya promediado y devuelve el string de
    la columna "etiqueta" que arma evaluar_sesiones().
    """
    cols_metricas = [c for c in METRICA_A_COLUMNA.values() if c in df_filtrado.columns]
    if col_identidad in df_filtrado.columns:
        df_total = _totalizar_por_dia(df_filtrado, [col_identidad] + claves_grupo, cols_metricas)
    else:
        df_total = df_filtrado
    df_promedio = df_total.groupby(claves_grupo, as_index=False)[cols_metricas].mean()
    df_promedio["etiqueta"] = df_promedio.apply(etiqueta_fn, axis=1)
    return evaluar_sesiones(df_promedio, df_parametros, col_etiqueta="etiqueta", match_day=match_day)


def evaluar_por_jugadora(df_filtrado: pd.DataFrame, df_parametros: pd.DataFrame, *,
                          claves_dia: list[str], match_day: str | None = None,
                          col_identidad: str = "nombre") -> pd.DataFrame:
    """
    Como armar_evaluacion_equipo() pero SIN promediar entre compañeras de
    posición — pensado para el análisis que señala jugadoras puntuales
    (ver src/metrics/analisis.py), no para la tabla resumen de equipo.

    Igual que ahí, primero totaliza por (col_identidad + claves_dia) para
    juntar Físico+TT del mismo día, pero después evalúa CADA fila
    individualmente contra su rango de posición, conservando col_identidad y
    claves_dia como columnas (no las colapsa en un único "etiqueta") para que
    quien consuma esto pueda agrupar/filtrar por jugadora.

    Devuelve [col_identidad] + claves_dia + [metrica, valor_real, rango_min,
    rango_max, estado, z_score] — una fila por (jugadora, día, métrica).

    Si df_filtrado ya trae columnas "{columna}_zscore" (calculadas página
    arriba con calcular_zscore_historico(), antes del filtro de fecha — ver
    docstring de evaluar_sesion()), se recuperan con "first" por
    (col_identidad + claves_dia): todas las filas del mismo día comparten el
    mismo z-score (se calculó a nivel día), así que sumarlas como las
    métricas crudas lo duplicaría/triplicaría según cuántas sesiones tuvo
    ese día. Si no vinieron calculadas, evaluar_sesion() las deja en None.
    """
    cols_metricas = [c for c in METRICA_A_COLUMNA.values() if c in df_filtrado.columns]
    claves = [col_identidad] + claves_dia
    df_total = _totalizar_por_dia(df_filtrado, claves, cols_metricas)

    cols_zscore = [f"{c}_zscore" for c in cols_metricas if f"{c}_zscore" in df_filtrado.columns]
    if cols_zscore:
        df_zscore = df_filtrado.groupby(claves, as_index=False)[cols_zscore].first()
        df_total = df_total.merge(df_zscore, on=claves, how="left")

    columnas = claves + ["metrica", "valor_real", "rango_min", "rango_max", "estado", "z_score"]
    bloques = []
    for _, fila in df_total.iterrows():
        md = match_day if match_day is not None else fila.get("match_day")
        if md is None or pd.isna(md):
            continue
        evaluacion = evaluar_sesion(fila, df_parametros, md)
        if evaluacion.empty:
            continue
        for col in claves:
            evaluacion[col] = fila[col]
        bloques.append(evaluacion[columnas])

    if not bloques:
        return pd.DataFrame(columns=columnas)
    return pd.concat(bloques, ignore_index=True)
