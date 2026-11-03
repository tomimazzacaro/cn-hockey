# src/metrics/fuerza_plan.py
"""
Métricas del PLAN de fuerza y pasadas, por Match Day y por semana.

Funciones puras: reciben DataFrames / números y devuelven DataFrames / números.
No leen ni escriben nada (eso es trabajo de src/loaders/fuerza_loader.py).

Convenciones (las mismas que las tablas de Supabase, migración 0063):
  * pct_rm y pct_vmax van en PORCENTAJE (80 = 80 %), no en fracción (0,80).
  * En las pasadas, 'repeticiones' es la cantidad de pasadas.
  * Las pasadas se miden en METROS (total y a alta intensidad), no en UA (decisión D5).
"""
import numpy as np
import pandas as pd

# Valores por defecto = los que carga la migración 0063 en fuerza_parametros.
# Son provisorios y se editan en la base, no acá.
PARAMETROS_DEFAULT = {
    "umbral_alta_intensidad_vmax": 85.0,  # % de Vmáx desde el cual una pasada es de alta intensidad
    "intensidad_base_sin_rm": 50.0,       # % de RM asumido cuando el ejercicio no tiene %RM
}

TIPO_FUERZA = "fuerza"
TIPO_PASADA = "pasada"

COLUMNAS_RESUMEN_MD = [
    "match_day", "ua_fuerza", "ejercicios_fuerza",
    "metros_pasadas", "metros_alta_intensidad", "pasadas_sin_pct_vmax",
]


def orden_match_day(match_day: str) -> int:
    """
    Convierte 'MD-5' en -5, 'MD-2' en -2, 'MD+1' en 1, para ordenar el microciclo
    cronológicamente (MD-5 antes que MD-4 antes que MD-2).

    Raises:
        ValueError: si el texto no tiene el formato MD-n / MD+n.
    """
    texto = str(match_day).strip().upper()
    if len(texto) < 4 or not texto.startswith("MD") or texto[2] not in "+-" or not texto[3:].isdigit():
        raise ValueError(f"Match Day inválido: {match_day!r} (se espera MD-5, MD-2, MD+1...)")
    signo = -1 if texto[2] == "-" else 1
    return signo * int(texto[3:])


def ua_fuerza(series: float, repeticiones: float, pct_rm: float,
              intensidad_base: float = PARAMETROS_DEFAULT["intensidad_base_sin_rm"]) -> float:
    """
    Unidades arbitrarias (UA) de un ejercicio de fuerza:

        UA = series × repeticiones × (%RM / 100)

    Si no hay %RM (ejercicio sin RM, como abdominales o Remo TRX), se usa la
    intensidad base: así un ejercicio "liviano" suma poco, pero no suma cero.

    Ejemplo: 4 series × 5 reps al 80 % de RM  ->  4 × 5 × 0,80 = 16 UA.
    """
    if pd.isna(series) or pd.isna(repeticiones):
        return float("nan")
    intensidad = intensidad_base if pd.isna(pct_rm) else pct_rm
    return float(series) * float(repeticiones) * float(intensidad) / 100.0


def metros_pasada(distancia_m: float, repeticiones: float) -> float:
    """Metros totales de una pasada prescrita: distancia × cantidad de pasadas."""
    if pd.isna(distancia_m) or pd.isna(repeticiones):
        return float("nan")
    return float(distancia_m) * float(repeticiones)


def es_alta_intensidad(pct_vmax: float,
                       umbral: float = PARAMETROS_DEFAULT["umbral_alta_intensidad_vmax"]) -> bool:
    """True si la pasada se corre a una intensidad >= umbral (% de la Vmáx). Sin dato -> False."""
    if pd.isna(pct_vmax):
        return False
    return float(pct_vmax) >= float(umbral)


def tiempo_objetivo_pasada(distancia_m: float, vmax_kmh: float, pct_vmax: float,
                           factor_distancia: float = 1.0) -> float:
    """
    Tiempo objetivo (en segundos) para recorrer una distancia a un % de la Vmáx
    de una jugadora:

        tiempo (s) = distancia (m) ÷ ( Vmáx (km/h) ÷ 3,6 × %Vmáx/100 × factor )

    Dividir por 3,6 pasa de km/h a m/s.

    OJO: es la opción A del PLAN (Vmáx con corrección por distancia). En 30 m una
    jugadora que sale de parada no llega a su Vmáx, así que con factor = 1 el tiempo
    sale más rápido que el real. El factor (< 1) corrige eso; el valor lo define
    Tomi cuando elija entre A y B. Hasta entonces el default es 1 (sin corrección).

    Raises:
        ValueError: si la distancia, la Vmáx, el % o el factor no son positivos.
    """
    for nombre, valor in (("distancia_m", distancia_m), ("vmax_kmh", vmax_kmh),
                          ("pct_vmax", pct_vmax), ("factor_distancia", factor_distancia)):
        if pd.isna(valor) or valor <= 0:
            raise ValueError(f"{nombre} debe ser un número positivo (recibido: {valor!r})")
    velocidad_ms = vmax_kmh / 3.6 * (pct_vmax / 100.0) * factor_distancia
    return float(distancia_m) / velocidad_ms


def resumir_plan_por_md(df_items: pd.DataFrame, parametros: dict | None = None) -> pd.DataFrame:
    """
    Resume los ítems de UN plan semanal, un renglón por Match Day.

    Args:
        df_items: columnas [match_day, tipo, series, repeticiones, pct_rm,
                  distancia_m, pct_vmax] (las de fuerza_plan_items).
        parametros: {'umbral_alta_intensidad_vmax', 'intensidad_base_sin_rm'};
                  lo que falte se completa con PARAMETROS_DEFAULT.

    Returns:
        DataFrame [match_day, ua_fuerza, ejercicios_fuerza, metros_pasadas,
        metros_alta_intensidad, pasadas_sin_pct_vmax], ordenado MD-5 -> MD-2.
        'pasadas_sin_pct_vmax' avisa cuántas pasadas no traen % de Vmáx: esos metros
        entran en metros_pasadas pero NO se pueden clasificar como alta intensidad.
    """
    if df_items is None or df_items.empty:
        return pd.DataFrame(columns=COLUMNAS_RESUMEN_MD)

    params = {**PARAMETROS_DEFAULT, **(parametros or {})}
    base = params["intensidad_base_sin_rm"]
    umbral = params["umbral_alta_intensidad_vmax"]

    filas = []
    for match_day, grupo in df_items.groupby("match_day", sort=False):
        fuerza = grupo[grupo["tipo"] == TIPO_FUERZA]
        pasadas = grupo[grupo["tipo"] == TIPO_PASADA]

        ua = sum(ua_fuerza(r.series, r.repeticiones, r.pct_rm, base)
                 for r in fuerza.itertuples(index=False))
        metros = [metros_pasada(r.distancia_m, r.repeticiones) for r in pasadas.itertuples(index=False)]
        altos = [m for m, pct in zip(metros, pasadas["pct_vmax"]) if es_alta_intensidad(pct, umbral)]

        filas.append({
            "match_day": match_day,
            "ua_fuerza": round(float(np.nansum([ua])), 2),
            "ejercicios_fuerza": int(len(fuerza)),
            "metros_pasadas": float(np.nansum(metros)),
            "metros_alta_intensidad": float(np.nansum(altos)),
            "pasadas_sin_pct_vmax": int(pasadas["pct_vmax"].isna().sum()),
        })

    out = pd.DataFrame(filas, columns=COLUMNAS_RESUMEN_MD)
    out["_orden"] = out["match_day"].map(orden_match_day)
    return out.sort_values("_orden").drop(columns="_orden").reset_index(drop=True)


def resumir_plan_semana(df_items: pd.DataFrame, parametros: dict | None = None) -> dict:
    """
    Totales de la semana: suma de resumir_plan_por_md().

    Returns:
        {'ua_fuerza', 'metros_pasadas', 'metros_alta_intensidad', 'pasadas_sin_pct_vmax'}
    """
    por_md = resumir_plan_por_md(df_items, parametros)
    if por_md.empty:
        return {"ua_fuerza": 0.0, "metros_pasadas": 0.0,
                "metros_alta_intensidad": 0.0, "pasadas_sin_pct_vmax": 0}
    return {
        "ua_fuerza": float(por_md["ua_fuerza"].sum()),
        "metros_pasadas": float(por_md["metros_pasadas"].sum()),
        "metros_alta_intensidad": float(por_md["metros_alta_intensidad"].sum()),
        "pasadas_sin_pct_vmax": int(por_md["pasadas_sin_pct_vmax"].sum()),
    }


COLUMNAS_ITEM_PLAN = [
    "match_day", "orden", "tipo", "ejercicio_id", "ejercicio_nombre", "series",
    "repeticiones", "pct_rm", "distancia_m", "zona", "pct_vmax", "pausa_s", "notas",
]
_NUMERICAS_ITEM = ["series", "repeticiones", "pct_rm", "distancia_m", "pct_vmax", "pausa_s"]
_PREFIJO_POR_TIPO = {TIPO_FUERZA: "FZA-", TIPO_PASADA: "RES-"}


def armar_items_plan(df_editado: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """
    Limpia las filas que cargó el cuerpo técnico en el planificador y numera el
    orden dentro de cada Match Day. Una fila inválida NO llega a la base: se
    descarta y se explica por qué.

    Una fila es válida si:
      * el Match Day tiene formato MD-n / MD+n;
      * tiene ejercicio_id y su prefijo coincide con el tipo (fuerza -> FZA-, pasada -> RES-);
      * fuerza: series >= 1 y repeticiones >= 1;  pasada: distancia_m > 0.
    Los porcentajes fuera de rango (pct_rm > 150, pct_vmax > 120 o <= 0) se dejan
    vacíos, pero la fila se conserva (mismo criterio que el RIR en armar_series).

    Args:
        df_editado: columnas de COLUMNAS_ITEM_PLAN (menos 'orden'), en el orden
                    en que se quieren hacer los ejercicios de cada día.

    Returns:
        (df_validos, avisos): df con COLUMNAS_ITEM_PLAN y 'orden' correlativo por
        match_day desde 1; avisos = un texto por cada fila descartada o corregida.
    """
    avisos: list[str] = []
    df = df_editado.copy()
    for col in COLUMNAS_ITEM_PLAN:
        if col not in df.columns:
            df[col] = np.nan
    for col in _NUMERICAS_ITEM:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in ("match_day", "tipo", "ejercicio_id", "ejercicio_nombre", "zona", "notas"):
        df[col] = df[col].where(df[col].notna(), "").astype(str).str.strip()

    validas = []
    for pos, fila in df.iterrows():
        etiqueta = f"Fila {pos + 1}" if isinstance(pos, (int, np.integer)) else f"Fila {pos}"
        try:
            orden_match_day(fila["match_day"])
        except ValueError:
            avisos.append(f"{etiqueta}: Match Day inválido ({fila['match_day'] or 'vacío'}).")
            continue
        tipo = fila["tipo"]
        if tipo not in _PREFIJO_POR_TIPO:
            avisos.append(f"{etiqueta}: tipo inválido ({tipo or 'vacío'}).")
            continue
        if not fila["ejercicio_id"].startswith(_PREFIJO_POR_TIPO[tipo]):
            avisos.append(f"{etiqueta}: el ejercicio no corresponde a una {tipo}.")
            continue
        if tipo == TIPO_FUERZA and not (fila["series"] >= 1 and fila["repeticiones"] >= 1):
            avisos.append(f"{etiqueta}: faltan series o repeticiones.")
            continue
        if tipo == TIPO_PASADA and not (fila["distancia_m"] > 0):
            avisos.append(f"{etiqueta}: falta la distancia de la pasada.")
            continue
        validas.append(pos)

    out = df.loc[validas].copy()
    for col, tope in (("pct_rm", 150), ("pct_vmax", 120)):
        fuera = out[col].notna() & ~((out[col] > 0) & (out[col] <= tope))
        if fuera.any():
            avisos.append(f"{col}: {int(fuera.sum())} valor(es) fuera de rango (0–{tope}) se dejaron vacíos.")
            out.loc[fuera, col] = np.nan
    fuera = out["pausa_s"].notna() & (out["pausa_s"] < 0)
    out.loc[fuera, "pausa_s"] = np.nan

    out["orden"] = out.groupby("match_day", sort=False).cumcount() + 1
    out["_md"] = out["match_day"].map(orden_match_day)
    out = out.sort_values(["_md", "orden"]).drop(columns="_md").reset_index(drop=True)
    return out[COLUMNAS_ITEM_PLAN], avisos


# ── Conversión entre las tablas del editor y los ítems del plan ──────────────
# En pantalla, cada Match Day tiene DOS tablas editables (fuerza y pasadas) con
# encabezados en castellano. Estas funciones las pasan de ida y vuelta al formato
# de la base (COLUMNAS_ITEM_PLAN). Son puras: no tocan Streamlit ni Supabase.

COLS_EDITOR_FUERZA = ["Ejercicio", "Series", "Reps", "%RM", "Pausa (s)", "Notas"]
COLS_EDITOR_PASADAS = ["Pasada", "Pasadas", "Distancia (m)", "%Vmáx", "Zona", "Pausa (s)", "Notas"]

# Columna del editor -> columna de la base
_MAP_FUERZA = {"Series": "series", "Reps": "repeticiones", "%RM": "pct_rm",
               "Pausa (s)": "pausa_s", "Notas": "notas"}
_MAP_PASADAS = {"Pasadas": "repeticiones", "Distancia (m)": "distancia_m", "%Vmáx": "pct_vmax",
                "Zona": "zona", "Pausa (s)": "pausa_s", "Notas": "notas"}


def etiqueta_ejercicio(nombre: str, ejercicio_id: str, tipo: str) -> str:
    """
    Texto que se muestra en el selector del editor. Las pasadas llevan el ID porque
    el catálogo repite nombres (hay cuatro "Pasadas"): sin el ID no se distinguirían.
    """
    return nombre if tipo == TIPO_FUERZA else f"{nombre} · {ejercicio_id}"


def items_a_editores(df_items: pd.DataFrame, match_day: str,
                     etiquetas: dict[str, str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Arma las dos tablas del editor para UN Match Day a partir de los ítems guardados.

    Args:
        df_items: ítems del plan (columnas de COLUMNAS_ITEM_PLAN); puede ser vacío.
        match_day: 'MD-5', 'MD-4'...
        etiquetas: {ejercicio_id: texto del selector}. Si un ID ya no está en el
            catálogo se usa el nombre guardado en el plan (el historial no se rompe).

    Returns:
        (df_fuerza, df_pasadas) con COLS_EDITOR_FUERZA / COLS_EDITOR_PASADAS, en el
        orden guardado.
    """
    if df_items is None or df_items.empty:
        return (pd.DataFrame(columns=COLS_EDITOR_FUERZA),
                pd.DataFrame(columns=COLS_EDITOR_PASADAS))

    del_dia = df_items[df_items["match_day"] == match_day].sort_values("orden")

    def etiqueta(r) -> str:
        return etiquetas.get(r.ejercicio_id) or etiqueta_ejercicio(r.ejercicio_nombre, r.ejercicio_id, r.tipo)

    def tabla(tipo: str, columnas: list[str], mapa: dict[str, str], col_ejercicio: str) -> pd.DataFrame:
        filas = del_dia[del_dia["tipo"] == tipo]
        out = pd.DataFrame({col_ejercicio: [etiqueta(r) for r in filas.itertuples(index=False)]})
        for col_editor, col_base in mapa.items():
            out[col_editor] = filas[col_base].to_numpy() if len(filas) else []
        return out[columnas].reset_index(drop=True)

    return (tabla(TIPO_FUERZA, COLS_EDITOR_FUERZA, _MAP_FUERZA, "Ejercicio"),
            tabla(TIPO_PASADA, COLS_EDITOR_PASADAS, _MAP_PASADAS, "Pasada"))


def editores_a_items(match_day: str, df_fuerza: pd.DataFrame, df_pasadas: pd.DataFrame,
                     ids_por_etiqueta: dict[str, tuple[str, str]]) -> pd.DataFrame:
    """
    Convierte las dos tablas del editor de UN Match Day al formato de la base
    (todavía sin validar: el resultado se pasa por armar_items_plan).

    Args:
        ids_por_etiqueta: {texto del selector: (ejercicio_id, nombre del catálogo)}.
        Las filas sin ejercicio elegido se ignoran en silencio (son filas en blanco
        que el usuario agregó y no completó).
    """
    partes = []
    for tipo, df, mapa, col_ejercicio in (
        (TIPO_FUERZA, df_fuerza, _MAP_FUERZA, "Ejercicio"),
        (TIPO_PASADA, df_pasadas, _MAP_PASADAS, "Pasada"),
    ):
        if df is None or df.empty:
            continue
        df = df[df[col_ejercicio].notna() & (df[col_ejercicio].astype(str).str.strip() != "")]
        if df.empty:
            continue
        resueltos = [ids_por_etiqueta.get(str(e).strip(), ("", str(e).strip())) for e in df[col_ejercicio]]
        parte = pd.DataFrame({
            "match_day": match_day,
            "tipo": tipo,
            "ejercicio_id": [r[0] for r in resueltos],
            "ejercicio_nombre": [r[1] for r in resueltos],
        })
        for col_editor, col_base in mapa.items():
            parte[col_base] = df[col_editor].to_numpy() if col_editor in df.columns else np.nan
        partes.append(parte)

    if not partes:
        return pd.DataFrame(columns=[c for c in COLUMNAS_ITEM_PLAN if c != "orden"])
    return pd.concat(partes, ignore_index=True)
