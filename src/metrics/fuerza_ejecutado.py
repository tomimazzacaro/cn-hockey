# src/metrics/fuerza_ejecutado.py
"""
Métricas de lo EJECUTADO en fuerza y pasadas (a nivel equipo): carga real por
sesión, cumplimiento contra el plan, resumen semanal y ACWR de fuerza.

Funciones puras (DataFrames adentro, DataFrames afuera). Reutilizan el cálculo del
plan (src/metrics/fuerza_plan.py): lo ejecutado tiene la misma forma que lo
prescrito, con tres columnas renombradas (series -> series_hechas, repeticiones ->
reps_hechas, pct_rm -> pct_rm_real).

Diferencia con el ACWR de GPS: acá la serie se completa con 0 en los días SIN
sesión. En fuerza se entrena 2 o 3 veces por semana; calcular la media móvil solo
sobre los días con sesión (como hace GPS) haría que un descanso de varios días no
bajara la carga aguda.
"""
import numpy as np
import pandas as pd

from settings import EWMA_AGUDA_DIAS, EWMA_CRONICA_DIAS
from src.metrics.fuerza_plan import PARAMETROS_DEFAULT, resumir_plan_semana
from src.metrics.physical import calcular_ewma, _clasificar_zona_acwr

_PLAN_A_EJECUTADO = {"series": "series_hechas", "repeticiones": "reps_hechas", "pct_rm": "pct_rm_real"}
_EJECUTADO_A_PLAN = {v: k for k, v in _PLAN_A_EJECUTADO.items()}

# Columnas de fuerza_sesion_items (migración 0063) que se cargan desde la pantalla.
COLUMNAS_ITEM_EJECUTADO = [
    "orden", "tipo", "ejercicio_id", "ejercicio_nombre", "series_hechas", "reps_hechas",
    "pct_rm_real", "distancia_m", "zona", "pct_vmax", "pausa_s", "notas",
]
_COLS_SUMA = ["ua_fuerza", "metros_pasadas", "metros_alta_intensidad", "metros_pasadas_fuera_gps"]


def plan_a_ejecutado(df_items_plan: pd.DataFrame) -> pd.DataFrame:
    """Precarga de una sesión: lo ejecutado arranca igual a lo planificado."""
    return df_items_plan.rename(columns=_PLAN_A_EJECUTADO).copy()


def ejecutado_a_plan(df_items_ej: pd.DataFrame) -> pd.DataFrame:
    """Pasa ítems ejecutados al formato del plan para reutilizar sus cálculos."""
    out = df_items_ej.rename(columns=_EJECUTADO_A_PLAN).copy()
    if "match_day" not in out.columns:
        out["match_day"] = "MD-0"   # una sesión tiene un solo MD; el valor no se usa
    return out


def resumir_items_ejecutados(df_items_ej: pd.DataFrame, parametros: dict | None = None) -> dict:
    """
    Carga real de UNA sesión.

    Returns:
        {'ua_fuerza', 'metros_pasadas', 'metros_alta_intensidad', 'pasadas_sin_pct_vmax'}
    """
    if df_items_ej is None or df_items_ej.empty:
        return resumir_plan_semana(pd.DataFrame(), parametros)
    return resumir_plan_semana(ejecutado_a_plan(df_items_ej), parametros)


def resumen_sesiones(df_sesiones: pd.DataFrame, df_items_ej: pd.DataFrame,
                     parametros: dict | None = None) -> pd.DataFrame:
    """
    Un renglón por sesión ejecutada con su carga real.

    Args:
        df_sesiones: [id, fecha, match_day, plan_id, duracion_min, rpe_sesion, ya_en_gps].
        df_items_ej: ítems de todas las sesiones, con 'sesion_id' (+ columnas ejecutadas).

    Returns:
        DataFrame ordenado por fecha con: id, fecha, match_day, plan_id, ua_fuerza,
        metros_pasadas, metros_alta_intensidad, metros_pasadas_fuera_gps,
        pasadas_sin_pct_vmax, srpe, duracion_min, rpe_sesion, ya_en_gps.
        'metros_pasadas_fuera_gps' es 0 si la sesión se marcó "ya está en el GPS":
        esos metros ya los cuenta el chaleco y no deben sumarse dos veces.
        'srpe' = duración × RPE (solo si están los dos datos).
    """
    columnas = ["id", "fecha", "match_day", "plan_id", "ua_fuerza", "metros_pasadas",
                "metros_alta_intensidad", "metros_pasadas_fuera_gps", "pasadas_sin_pct_vmax",
                "srpe", "duracion_min", "rpe_sesion", "ya_en_gps"]
    if df_sesiones is None or df_sesiones.empty:
        return pd.DataFrame(columns=columnas)

    filas = []
    for s in df_sesiones.itertuples(index=False):
        items = (df_items_ej[df_items_ej["sesion_id"] == s.id]
                 if df_items_ej is not None and not df_items_ej.empty else pd.DataFrame())
        r = resumir_items_ejecutados(items, parametros)
        ya_en_gps = bool(s.ya_en_gps)
        duracion = pd.to_numeric(s.duracion_min, errors="coerce")
        rpe = pd.to_numeric(s.rpe_sesion, errors="coerce")
        filas.append({
            "id": s.id, "fecha": pd.Timestamp(s.fecha).normalize(), "match_day": s.match_day,
            "plan_id": s.plan_id,
            "ua_fuerza": r["ua_fuerza"],
            "metros_pasadas": r["metros_pasadas"],
            "metros_alta_intensidad": r["metros_alta_intensidad"],
            "metros_pasadas_fuera_gps": 0.0 if ya_en_gps else r["metros_pasadas"],
            "pasadas_sin_pct_vmax": r["pasadas_sin_pct_vmax"],
            "srpe": duracion * rpe if pd.notna(duracion) and pd.notna(rpe) else np.nan,
            "duracion_min": duracion, "rpe_sesion": rpe, "ya_en_gps": ya_en_gps,
        })
    return pd.DataFrame(filas, columns=columnas).sort_values("fecha").reset_index(drop=True)


def cumplimiento_vs_plan(df_resumen: pd.DataFrame, df_items_plan_all: pd.DataFrame,
                         parametros: dict | None = None) -> pd.DataFrame:
    """
    Agrega a cada sesión lo que decía el plan para ese MD y el % de cumplimiento.

    Args:
        df_resumen: salida de resumen_sesiones().
        df_items_plan_all: ítems de todos los planes, con 'plan_id' y 'match_day'.

    Returns:
        df_resumen + ua_planificada, metros_planificados, cumplimiento_ua,
        cumplimiento_metros (en %; vacío si la sesión no tiene plan o el plan era 0).
    """
    out = df_resumen.copy()
    out["ua_planificada"] = np.nan
    out["metros_planificados"] = np.nan
    if out.empty or df_items_plan_all is None or df_items_plan_all.empty:
        out["cumplimiento_ua"] = np.nan
        out["cumplimiento_metros"] = np.nan
        return out

    for i, s in out.iterrows():
        if pd.isna(s["plan_id"]):
            continue
        items = df_items_plan_all[(df_items_plan_all["plan_id"] == s["plan_id"])
                                  & (df_items_plan_all["match_day"] == s["match_day"])]
        if items.empty:
            continue
        r = resumir_plan_semana(items, parametros)
        out.loc[i, "ua_planificada"] = r["ua_fuerza"]
        out.loc[i, "metros_planificados"] = r["metros_pasadas"]

    out["cumplimiento_ua"] = _porcentaje(out["ua_fuerza"], out["ua_planificada"])
    out["cumplimiento_metros"] = _porcentaje(out["metros_pasadas"], out["metros_planificados"])
    return out


def _porcentaje(real: pd.Series, plan: pd.Series) -> pd.Series:
    """real / plan × 100; vacío donde el plan no existe o es 0."""
    return (real / plan.where(plan > 0) * 100).round(1)


def _lunes(fechas: pd.Series) -> pd.Series:
    f = pd.to_datetime(fechas).dt.normalize()
    return f - pd.to_timedelta(f.dt.weekday, unit="D")


def resumen_semanal(df_resumen: pd.DataFrame, df_planes: pd.DataFrame,
                    df_items_plan_all: pd.DataFrame, parametros: dict | None = None) -> pd.DataFrame:
    """
    Planificado vs ejecutado por semana (lunes a domingo).

    Lo planificado sale del plan de cada semana, aunque una sesión no se haya hecho:
    así una MD-2 salteada baja el cumplimiento en vez de pasar inadvertida.

    Args:
        df_planes: [id, semana_inicio].

    Returns:
        DataFrame [semana, ua_planificada, ua_ejecutada, metros_planificados,
        metros_ejecutados, metros_alta_intensidad, metros_fuera_gps, cumplimiento_ua,
        cumplimiento_metros], ordenado por semana.
    """
    columnas = ["semana", "ua_planificada", "ua_ejecutada", "metros_planificados",
                "metros_ejecutados", "metros_alta_intensidad", "metros_fuera_gps",
                "cumplimiento_ua", "cumplimiento_metros"]

    if df_resumen is not None and not df_resumen.empty:
        ej = df_resumen.assign(semana=_lunes(df_resumen["fecha"]))
        ej = ej.groupby("semana")[_COLS_SUMA].sum().reset_index().rename(columns={
            "ua_fuerza": "ua_ejecutada", "metros_pasadas": "metros_ejecutados",
            "metros_pasadas_fuera_gps": "metros_fuera_gps"})
    else:
        ej = pd.DataFrame(columns=["semana", "ua_ejecutada", "metros_ejecutados",
                                   "metros_alta_intensidad", "metros_fuera_gps"])

    filas = []
    if df_planes is not None and not df_planes.empty and df_items_plan_all is not None:
        for p in df_planes.itertuples(index=False):
            r = resumir_plan_semana(df_items_plan_all[df_items_plan_all["plan_id"] == p.id], parametros)
            filas.append({"semana": pd.Timestamp(p.semana_inicio).normalize(),
                          "ua_planificada": r["ua_fuerza"], "metros_planificados": r["metros_pasadas"]})
    pl = pd.DataFrame(filas, columns=["semana", "ua_planificada", "metros_planificados"])

    out = pl.merge(ej, on="semana", how="outer").sort_values("semana").reset_index(drop=True)
    for col in ("ua_planificada", "ua_ejecutada", "metros_planificados", "metros_ejecutados",
                "metros_alta_intensidad", "metros_fuera_gps"):
        out[col] = pd.to_numeric(out[col]).fillna(0.0)
    out["cumplimiento_ua"] = _porcentaje(out["ua_ejecutada"], out["ua_planificada"])
    out["cumplimiento_metros"] = _porcentaje(out["metros_ejecutados"], out["metros_planificados"])
    return out[columnas]


def serie_diaria_ua(df_resumen: pd.DataFrame, hasta=None) -> pd.DataFrame:
    """
    UA de fuerza por día calendario, con 0 en los días sin sesión.

    Args:
        hasta: último día de la serie (por defecto, la última sesión). Pasar la fecha
               de hoy hace que la carga aguda siga bajando si hace días que no se entrena.

    Returns:
        DataFrame [fecha, ua_fuerza]; vacío si no hay sesiones.
    """
    if df_resumen is None or df_resumen.empty:
        return pd.DataFrame(columns=["fecha", "ua_fuerza"])
    por_dia = (df_resumen.assign(fecha=pd.to_datetime(df_resumen["fecha"]).dt.normalize())
               .groupby("fecha")["ua_fuerza"].sum())
    fin = max(por_dia.index.max(), pd.Timestamp(hasta).normalize()) if hasta is not None else por_dia.index.max()
    dias = pd.date_range(por_dia.index.min(), fin, freq="D")
    return por_dia.reindex(dias, fill_value=0.0).rename_axis("fecha").reset_index()


def acwr_fuerza(df_diaria: pd.DataFrame) -> pd.DataFrame:
    """
    ACWR de fuerza del equipo por EWMA (mismas ventanas que GPS: 7 y 28 días).

        ACWR = EWMA aguda (7 d) ÷ EWMA crónica (28 d)

    Returns:
        df_diaria + ewma_aguda, ewma_cronica, acwr, zona_acwr, dias_historia,
        historia_suficiente. 'historia_suficiente' es False mientras haya menos de
        28 días de historia: antes de eso la crónica todavía no es confiable y el
        ACWR (que arranca en 1,0 por construcción) no debe leerse como señal.
    """
    out = df_diaria.copy()
    if out.empty:
        for col in ("ewma_aguda", "ewma_cronica", "acwr", "zona_acwr", "dias_historia", "historia_suficiente"):
            out[col] = pd.Series(dtype="float64" if col != "zona_acwr" else "object")
        return out
    out["ewma_aguda"] = calcular_ewma(out["ua_fuerza"], EWMA_AGUDA_DIAS)
    out["ewma_cronica"] = calcular_ewma(out["ua_fuerza"], EWMA_CRONICA_DIAS)
    out["acwr"] = (out["ewma_aguda"] / out["ewma_cronica"].replace(0, np.nan)).round(3)
    out["zona_acwr"] = out["acwr"].apply(_clasificar_zona_acwr)
    out["dias_historia"] = (pd.to_datetime(out["fecha"]) - pd.to_datetime(out["fecha"]).min()).dt.days + 1
    out["historia_suficiente"] = out["dias_historia"] >= EWMA_CRONICA_DIAS
    return out
