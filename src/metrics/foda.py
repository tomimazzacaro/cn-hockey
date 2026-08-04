# src/metrics/foda.py
"""
Agregación por Match Day para la página Análisis (FODA de entrenamientos,
ver pages/08_analisis.py) — a diferencia del Asistente de Parámetros
(src/metrics/parametros.py), que evalúa UNA sesión puntual, acá se resume un
PERÍODO completo (todos los MD-4 del rango filtrado, por ejemplo) por Match
Day y métrica.

Determinístico igual que src/metrics/analisis.py: todo acá sale de un cálculo
sobre números reales, nada generado — esto termina en una reunión con el
cuerpo técnico.
"""
import re

import numpy as np
import pandas as pd

from settings import UMBRAL_CV_DURACION, UMBRAL_CALIBRACION_PCT
from src.metrics.parametros import EN_RANGO, POR_DEBAJO, POR_ENCIMA, SIN_DATO


def resumen_duracion_por_md(df: pd.DataFrame, claves: list[str] = None,
                             umbral_cv: float = UMBRAL_CV_DURACION) -> pd.DataFrame:
    """
    Duración de sesión (columna "duracion_min") agrupada por `claves`
    (default [match_day, tipo_sesion]), con el coeficiente de variación
    (desvío/media) de cada grupo.

    "variabilidad_alta" (cv >= umbral_cv) es la señal cuantitativa detrás de
    un aviso de calidad de dato: cuando el corte manual de "tiempos muertos"
    del GPS no se aplica siempre, la duración cruda de un mismo tipo de
    sesión salta de forma inconsistente entre cargas — un cv alto es esa
    inconsistencia medida, no una opinión. Con una sola sesión en el grupo
    (n=1) el desvío es NaN y "variabilidad_alta" queda en False: un solo dato
    no alcanza para hablar de variabilidad.

    Devuelve [claves..., media_min, desvio_min, minimo_min, maximo_min, n, cv,
    variabilidad_alta].
    """
    if claves is None:
        claves = ["match_day", "tipo_sesion"]
    columnas = claves + ["media_min", "desvio_min", "minimo_min", "maximo_min", "n", "cv", "variabilidad_alta"]
    if df.empty or "duracion_min" not in df.columns:
        return pd.DataFrame(columns=columnas)

    resumen = (
        df.groupby(claves, as_index=False)["duracion_min"]
          .agg(media_min="mean", desvio_min="std", minimo_min="min", maximo_min="max", n="count")
          .round(1)
    )
    resumen["cv"] = (resumen["desvio_min"] / resumen["media_min"].replace(0, np.nan)).round(2)
    resumen["variabilidad_alta"] = resumen["cv"] >= umbral_cv
    resumen["variabilidad_alta"] = resumen["variabilidad_alta"].fillna(False)
    return resumen[columnas]


def resumen_cumplimiento_por_md(df_individual: pd.DataFrame) -> pd.DataFrame:
    """
    % de sesiones por debajo/en rango/por encima del parámetro esperado,
    agrupado por [match_day, metrica] — sobre la salida de
    evaluar_por_jugadora() (src/metrics/parametros.py), que ya totaliza
    Físico+Técnico-Táctico del mismo día y evalúa cada (jugadora, día,
    métrica) individualmente contra su rango de posición.

    Las filas en SIN_DATO (rango cargado en el Sheet pero sin valor real
    registrado esa sesión) se excluyen del cálculo — no aportan señal de
    cumplimiento, solo restarían del denominador la evidencia real.

    Devuelve [match_day, metrica, n, pct_por_debajo, pct_en_rango,
    pct_por_encima] — porcentajes en 0-1, no en 0-100 (el caller decide el
    formato de presentación).
    """
    columnas = ["match_day", "metrica", "n", "pct_por_debajo", "pct_en_rango", "pct_por_encima"]
    if df_individual.empty:
        return pd.DataFrame(columns=columnas)

    evaluadas = df_individual[df_individual["estado"] != SIN_DATO]
    if evaluadas.empty:
        return pd.DataFrame(columns=columnas)

    filas = []
    for (match_day, metrica), grupo in evaluadas.groupby(["match_day", "metrica"]):
        n = len(grupo)
        conteos = grupo["estado"].value_counts()
        filas.append({
            "match_day": match_day,
            "metrica": metrica,
            "n": n,
            "pct_por_debajo": round(conteos.get(POR_DEBAJO, 0) / n, 3),
            "pct_en_rango": round(conteos.get(EN_RANGO, 0) / n, 3),
            "pct_por_encima": round(conteos.get(POR_ENCIMA, 0) / n, 3),
        })
    return pd.DataFrame(filas, columns=columnas)


def resumen_acwr_por_md(df_acwr: pd.DataFrame, claves: list[str] = None) -> pd.DataFrame:
    """
    Distribución de zona ACWR (ver calcular_acwr() en src/metrics/physical.py)
    agrupada por `claves` (default [match_day]).

    Nota: NO deduplica por (jugadora, fecha) — si una jugadora tuvo Físico y
    Técnico-Táctico el mismo día, ambas filas comparten la misma zona_acwr
    (se calcula a nivel día) y cuentan las dos. Es intencional: el resumen
    representa "sesiones registradas en esa zona", no "días distintos", igual
    criterio que se usó para validar estos números en la conversación con el
    cuerpo técnico. Si se necesitara "días únicos" en el futuro, dedup antes
    de llamar a esta función.

    Devuelve [claves..., zona_acwr, n, pct].
    """
    if claves is None:
        claves = ["match_day"]
    columnas = claves + ["zona_acwr", "n", "pct"]
    if df_acwr.empty or "zona_acwr" not in df_acwr.columns:
        return pd.DataFrame(columns=columnas)

    conteo = df_acwr.groupby(claves + ["zona_acwr"]).size().reset_index(name="n")
    totales = conteo.groupby(claves)["n"].transform("sum")
    conteo["pct"] = (conteo["n"] / totales).round(3)
    return conteo[columnas]


def detectar_posible_calibracion(resumen_cumplimiento: pd.DataFrame,
                                  umbral_pct: float = UMBRAL_CALIBRACION_PCT) -> list[dict]:
    """
    Marca combinaciones (match_day, métrica) donde el % fuera de rango en UNA
    sola dirección (todo por debajo, o todo por encima) supera `umbral_pct`
    (default 90%) — un patrón así de parejo es más compatible con un rango
    del Sheet mal calibrado que con que absolutamente todas las jugadoras
    fallen la misma métrica en la misma dirección. No reemplaza el juicio del
    cuerpo técnico, solo señala dónde conviene desconfiar del parámetro antes
    que del entrenamiento.

    Devuelve una lista de {match_day, metrica, direccion, pct} — direccion es
    "Por debajo" o "Por encima" (las mismas constantes de parametros.py).
    """
    if resumen_cumplimiento.empty:
        return []

    hallazgos = []
    for _, fila in resumen_cumplimiento.iterrows():
        if fila["pct_por_debajo"] >= umbral_pct:
            hallazgos.append({
                "match_day": fila["match_day"], "metrica": fila["metrica"],
                "direccion": POR_DEBAJO, "pct": fila["pct_por_debajo"],
            })
        elif fila["pct_por_encima"] >= umbral_pct:
            hallazgos.append({
                "match_day": fila["match_day"], "metrica": fila["metrica"],
                "direccion": POR_ENCIMA, "pct": fila["pct_por_encima"],
            })
    hallazgos.sort(key=lambda h: h["pct"], reverse=True)
    return hallazgos


# ── Ejercicios propuestos por Match Day (pestaña "MD_Ejercicios") ──────────

_PATRON_BULLET = re.compile(r"\s+-\s*(?=[A-ZÁÉÍÓÚÑ0-9])")


def dividir_en_bullets(texto) -> list[str]:
    """
    Parte el texto libre de una celda de la pestaña "MD_Ejercicios" (cargada
    a mano por el cuerpo técnico, sin un separador fijo) en una lista de
    puntos cortos, para mostrar como viñetas en vez de un párrafo denso.

    El separador real varía según cómo se tipeó cada celda — a veces
    ". -Bullet", a veces ")  -Bullet", a veces "- Bullet". Lo único
    consistente en los datos reales es que cada punto nuevo arranca con un
    guión precedido de espacio y seguido inmediatamente de mayúscula o
    dígito — nunca un guión "pegado" sin espacio antes, como en "2-3
    bloques" o "15-20 metros", que por eso no se cortan. Validado a mano
    contra las 6 celdas reales (FISICO/TECNICO-TACTICO × MD-5/MD-4/MD-2).
    Texto tipeado a mano no tiene garantía 100% — si aparece un caso nuevo
    que no separa bien, el fix es acá, no en la página.
    """
    if pd.isna(texto) or not str(texto).strip():
        return []
    limpio = re.sub(r"^-\s*", "", str(texto).strip())
    return [p.strip() for p in _PATRON_BULLET.split(limpio) if p.strip()]
