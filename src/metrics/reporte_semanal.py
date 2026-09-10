# src/metrics/reporte_semanal.py
"""
Composición del reporte semanal — CN Hockey Femenino.

Arma el veredicto semanal por jugadora (semáforo Verde/Amarillo/Rojo)
cruzando señal física + señal de wellness — nunca una alerta a partir de
una sola métrica aislada (regla dura del proyecto y de la skill
sports-performance-alerts-reports).

Determinístico como el resto de src/metrics/: ningún LLM decide acá si una
jugadora está en riesgo — cada bandera tiene que poder rastrearse hasta un
número real. Este módulo NO recalcula ACWR, z-score, EWMA ni el Asistente
de Parámetros — todo eso ya existe (physical.py, wellness.py, parametros.py,
analisis.py) y se reusa tal cual. Lo único nuevo acá es:
  1. cruzar esas señales ya calculadas con la regla de semaforización del
     proyecto (1 señal = Amarillo, 2+ o ACWR>=alerta = Rojo),
  2. la detección de "caída brusca de carga crónica" (no existía antes), y
  3. la tabla de KPIs semana vs. equipo/posición vs. propio histórico.

Referencia semáforo: instrucciones del proyecto CN_HOCKEY (Cowork) y skill
sports-performance-alerts-reports.
"""
from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd
from scipy.stats import pearsonr

from settings import TIPOS_SESION, UMBRAL_CALIBRACION_PCT, ZSCORE_ALERTA
from src.metrics.foda import (
    detectar_posible_calibracion, resumen_acwr_por_md, resumen_cumplimiento_por_md,
    resumen_duracion_por_md,
)
from src.metrics.parametros import METRICA_A_COLUMNA, evaluar_por_jugadora
from src.metrics.physical import calcular_srpe, detectar_sesiones_atipicas

# Colores del semáforo — MISMO hue que ZONE_CFG en src/ui/theme.py (Riesgo
# Alto/Precaución/Óptimo), pero reporte_semanal.py no puede importar theme.py:
# ese módulo es Streamlit-facing (importa st indirectamente vía el resto de
# src/ui) y este es un módulo puro de src/metrics/ (regla de capas del
# repo — ver arquitectura en CLAUDE.md). Se copian los 3 valores hex a mano;
# si el semáforo de pantalla cambia de color algún día, actualizar acá
# también (son solo 3 constantes, no vale la pena romper la capa por eso).
COLOR_ROJO = "#EA4335"
COLOR_AMARILLO = "#FBBC04"
COLOR_VERDE = "#34A853"

# ── Umbrales propios del reporte semanal ────────────────────────────────────
# Primera versión, documentada y ajustable con uso real — mismo criterio que
# UMBRAL_CALIBRACION_PCT en foda.py: un punto de partida razonable a validar
# con Tomi/cuerpo técnico, no un valor "mágico" definitivo.
CAIDA_CRONICA_UMBRAL_PCT = 0.30    # EWMA crónica cae >=30% vs. ~3 semanas antes -> señal física
CAIDA_CRONICA_DIAS_ATRAS = 21
TQR_SOSTENIDO_UMBRAL = 5.0         # promedio semanal de TQR por debajo de esto -> "TQR bajo sostenido"
RPE_SOSTENIDO_UMBRAL = 8.0         # promedio semanal de RPE por encima de esto -> "RPE alto sostenido"
MIN_REGISTROS_SOSTENIDO = 3        # con menos wellness cargado en la semana no se habla de "sostenido"

# Métricas GPS que se vigilan por z-score histórico en el reporte semanal
# (subconjunto de las que ya calcula calcular_zscore_historico en physical.py).
COLS_METRICA_ZSCORE = ["distancia_total", "player_load", "hsr"]

VERDE, AMARILLO, ROJO = "Verde", "Amarillo", "Rojo"
EMOJI_SEMAFORO = {VERDE: "🟢", AMARILLO: "🟡", ROJO: "🔴"}
COLOR_SEMAFORO = {VERDE: COLOR_VERDE, AMARILLO: COLOR_AMARILLO, ROJO: COLOR_ROJO}

# Umbral propio del FODA de periodización semanal — mismo criterio que
# _UMBRAL_BULLET en pages/08_analisis.py (0.70): a partir de qué % de
# sesiones/jugadoras en una dirección un hallazgo entra como bullet. Es un
# umbral de "cuánto mostrar", no de calidad de dato — vive acá y no en
# settings.py por el mismo motivo que el de la página (ajuste fino de
# presentación, no una regla de negocio del proyecto).
UMBRAL_FODA_SEMANA = 0.70

# Piso de pares (x, y) para que un r de Pearson tenga algún sentido — con
# menos de esto, el número existe pero es ruido: la nota de la tabla de
# correlaciones dice explícitamente "muestra insuficiente" en vez de dejar
# que un r llamativo con n=4 se lea como si fuera confiable.
CORRELACION_MIN_N = 10


@dataclass
class Senal:
    tipo: str    # "fisica" | "wellness"
    texto: str


@dataclass
class VeredictoJugadora:
    player_id: str
    nombre: str
    posicion: str | None
    semaforo: str
    senales: list      # list[Senal]
    recomendacion: str
    acwr: float | None
    zona_acwr: str | None
    tqr_prom: float | None
    rpe_prom: float | None
    n_registros_wellness: int


def detectar_caida_cronica(df_jugadora_historico: pd.DataFrame, fecha_fin_semana: date,
                            umbral_pct: float = CAIDA_CRONICA_UMBRAL_PCT,
                            dias_atras: int = CAIDA_CRONICA_DIAS_ATRAS) -> Senal | None:
    """
    Compara la EWMA crónica de la jugadora al final de la semana del reporte
    contra la de ~`dias_atras` antes. Una caída >= `umbral_pct` es la señal
    de "carga crónica en baja" (vuelta de lesión, parate, baja continuidad):
    el ACWR puede dar un número engañosamente cómodo cuando aguda y crónica
    bajan juntas, sin que la tolerancia real de la jugadora haya vuelto a
    subir — por eso se mira la crónica en valor absoluto, no el ACWR.

    Requiere ewma_cronica en ambos extremos de la ventana — si la jugadora
    no tiene historial suficiente, no hay caída que declarar (nunca penaliza
    falta de datos como si fuera una señal de riesgo).
    """
    if df_jugadora_historico.empty or "ewma_cronica" not in df_jugadora_historico.columns:
        return None

    df = df_jugadora_historico.sort_values("fecha")
    hasta_fin = df[df["fecha"] <= fecha_fin_semana]
    if hasta_fin.empty:
        return None
    cronica_fin = hasta_fin["ewma_cronica"].iloc[-1]
    if pd.isna(cronica_fin):
        return None

    fecha_referencia = fecha_fin_semana - timedelta(days=dias_atras)
    hasta_ref = df[df["fecha"] <= fecha_referencia]
    if hasta_ref.empty:
        return None
    cronica_ref = hasta_ref["ewma_cronica"].iloc[-1]
    if pd.isna(cronica_ref) or cronica_ref == 0:
        return None

    caida_pct = (cronica_ref - cronica_fin) / cronica_ref
    if caida_pct >= umbral_pct:
        return Senal("fisica", f"Carga crónica cayó {caida_pct * 100:.0f}% vs. ~{dias_atras} días antes")
    return None


def _senales_fisicas(df_jugadora_semana: pd.DataFrame) -> tuple[list, float | None, str | None]:
    """
    Señales físicas de UNA jugadora en la semana del reporte, a partir de
    filas de GPS que YA vienen con acwr/zona_acwr/{metrica}_zscore calculados
    contra el historial COMPLETO (calcular_acwr/calcular_zscore_historico
    corridos ANTES de filtrar a la semana — mismo criterio causal que ya usa
    el resto del repo, ver docstrings de physical.py).

    Se deduplica por fecha antes de evaluar: una jugadora con Físico +
    Técnico-Táctico (o los 4 cuartos de un partido) el mismo día comparte el
    mismo acwr/zscore en todas esas filas — sin dedup, un solo día atípico
    generaría 2-4 señales idénticas en vez de una.
    """
    senales = []
    acwr, zona = None, None
    if df_jugadora_semana.empty:
        return senales, acwr, zona

    cols_zscore_presentes = [f"{m}_zscore" for m in COLS_METRICA_ZSCORE
                              if f"{m}_zscore" in df_jugadora_semana.columns]
    cols_relevantes = [c for c in (["fecha", "acwr", "zona_acwr"] + cols_zscore_presentes)
                       if c in df_jugadora_semana.columns]
    df_dia = (df_jugadora_semana[cols_relevantes]
              .drop_duplicates(subset=["fecha"])
              .sort_values("fecha"))

    if "zona_acwr" in df_dia.columns and not df_dia.empty:
        fila_ultima = df_dia.iloc[-1]
        acwr, zona = fila_ultima.get("acwr"), fila_ultima.get("zona_acwr")
        if zona not in (None, "Sin datos", "Óptimo") and pd.notna(acwr):
            senales.append(Senal("fisica", f"ACWR {acwr:.2f} ({zona})"))

    if cols_zscore_presentes:
        atipica_mask = detectar_sesiones_atipicas(df_dia, cols_zscore_presentes, ZSCORE_ALERTA)
        for _, fila in df_dia[atipica_mask].iterrows():
            for col in cols_zscore_presentes:
                z = fila.get(col)
                if pd.notna(z) and abs(z) >= ZSCORE_ALERTA:
                    metrica = col.replace("_zscore", "")
                    senales.append(Senal(
                        "fisica", f"Sesión atípica el {fila['fecha']}: {metrica} z={z:.1f}",
                    ))

    return senales, acwr, zona


def _senales_wellness(df_jugadora_semana: pd.DataFrame) -> tuple[list, float | None, float | None, int]:
    """Señales de wellness de la semana: TQR/RPE 'sostenidos' (promedio de
    la semana, no un solo día) y cualquier molestia reportada."""
    senales = []
    n = len(df_jugadora_semana)
    tqr_prom = df_jugadora_semana["tqr"].mean() if n else None
    rpe_prom = df_jugadora_semana["rpe"].mean() if n else None

    if n >= MIN_REGISTROS_SOSTENIDO:
        if pd.notna(tqr_prom) and tqr_prom < TQR_SOSTENIDO_UMBRAL:
            senales.append(Senal("wellness", f"TQR bajo sostenido (prom. {tqr_prom:.1f}/10, {n} registros)"))
        if pd.notna(rpe_prom) and rpe_prom > RPE_SOSTENIDO_UMBRAL:
            senales.append(Senal("wellness", f"RPE alto sostenido (prom. {rpe_prom:.1f}/10, {n} registros)"))

    if "molestia_flag" in df_jugadora_semana.columns:
        for _, fila in df_jugadora_semana[df_jugadora_semana["molestia_flag"]].iterrows():
            senales.append(Senal("wellness", f"Molestia el {fila['fecha']}: {fila['molestia']}"))

    return senales, tqr_prom, rpe_prom, n


def _recomendacion(semaforo: str, senales: list) -> str:
    """
    Cierre accionable — cada hallazgo termina en una recomendación concreta,
    nunca en una descripción suelta (regla dura del proyecto). Se arma según
    QUÉ tipo de señal disparó, no con una frase genérica fija para todo Rojo.
    """
    if semaforo == VERDE:
        return "Sin restricciones — continuar con la planificación habitual."

    hay_fisica = any(s.tipo == "fisica" for s in senales)
    hay_wellness = any(s.tipo == "wellness" for s in senales)
    hay_molestia = any("Molestia" in s.texto for s in senales)
    hay_riesgo_alto = any("Riesgo Alto" in s.texto for s in senales)

    if semaforo == ROJO:
        if hay_riesgo_alto and hay_wellness:
            return ("Reducir volumen en la próxima sesión y monitorear molestias antes de "
                    "autorizar carga completa.")
        if hay_riesgo_alto:
            return ("Reducir volumen/intensidad en la próxima sesión — ACWR en zona de riesgo "
                    "alto, independientemente del wellness.")
        if hay_molestia and hay_fisica:
            return ("Evaluar con cuerpo médico antes de la próxima sesión de alta intensidad — "
                    "molestia física y señal de carga simultáneas.")
        if hay_wellness and not hay_fisica:
            return ("Priorizar sesión regenerativa y confirmar con la jugadora — dos o más "
                    "señales de wellness sin correlato físico todavía, no ignorar.")
        return "Cruzar con cuerpo médico y ajustar la carga de la próxima sesión."

    # AMARILLO
    if hay_molestia:
        return "Confirmar con la jugadora antes de la próxima sesión de alta intensidad."
    return "Monitorear en la próxima sesión — todavía sin acción sobre la planificación."


def evaluar_jugadora_semana(player_id: str, nombre: str, posicion: str | None,
                             df_gps_jugadora_semana: pd.DataFrame,
                             df_gps_jugadora_historico: pd.DataFrame,
                             df_wellness_jugadora_semana: pd.DataFrame,
                             fecha_fin_semana: date) -> VeredictoJugadora:
    """
    Semaforización (instrucciones del proyecto):
        🔴 Rojo:     2+ señales fuera de rango simultáneas, o ACWR en Riesgo Alto.
        🟡 Amarillo: exactamente 1 señal fuera de rango.
        🟢 Verde:    ninguna señal.
    """
    senales_fisicas, acwr, zona = _senales_fisicas(df_gps_jugadora_semana)

    senal_caida = detectar_caida_cronica(df_gps_jugadora_historico, fecha_fin_semana)
    if senal_caida:
        senales_fisicas.append(senal_caida)

    senales_wellness, tqr_prom, rpe_prom, n_wellness = _senales_wellness(df_wellness_jugadora_semana)

    todas = senales_fisicas + senales_wellness
    if zona == "Riesgo Alto" or len(todas) >= 2:
        semaforo = ROJO
    elif len(todas) == 1:
        semaforo = AMARILLO
    else:
        semaforo = VERDE

    return VeredictoJugadora(
        player_id=player_id, nombre=nombre, posicion=posicion, semaforo=semaforo,
        senales=todas, recomendacion=_recomendacion(semaforo, todas),
        acwr=acwr, zona_acwr=zona, tqr_prom=tqr_prom, rpe_prom=rpe_prom,
        n_registros_wellness=n_wellness,
    )


def definir_semana_reporte(df_sesiones: pd.DataFrame, fecha_maxima: date) -> tuple[date, date] | None:
    """
    Última semana/microciclo COMPLETO disponible, anclado al calendario real
    (match_day == "MD" marca el ancla de cada microciclo — mismo criterio
    que fecha_corte_microciclos() en physical.py, acá devolviendo el rango
    [inicio, fin] completo en vez de solo el corte).

    fecha_maxima tiene que ser la última fecha con datos REALES (típicamente
    min(última fecha GPS, última fecha wellness)) — la hoja de Sesiones ya
    trae cargado el fixture futuro de la temporada, así que sin este tope el
    "último MD" podría ser una fecha que todavía no pasó.

    Devuelve None si todavía no hay un microciclo completo con datos.
    """
    md = df_sesiones[(df_sesiones["match_day"] == "MD") & (df_sesiones["fecha"] <= fecha_maxima)]
    fechas_md = sorted(md["fecha"].unique())
    if len(fechas_md) < 2:
        return None
    fecha_fin = fechas_md[-1]
    fecha_inicio = fechas_md[-2] + timedelta(days=1)
    return fecha_inicio, fecha_fin


def armar_veredictos_semana(df_gps_historico: pd.DataFrame, df_wellness_historico: pd.DataFrame,
                             df_roster: pd.DataFrame, fecha_inicio: date, fecha_fin: date) -> list:
    """
    Veredicto semanal para toda jugadora con al menos un dato (GPS o
    wellness) en [fecha_inicio, fecha_fin].

    df_gps_historico y df_wellness_historico deben traer TODO el historial
    disponible, no solo la semana: physical.py necesita el historial
    completo para EWMA/z-score, y detectar_caida_cronica() compara contra
    ~3 semanas antes de fecha_fin.
    """
    df_gps_semana = df_gps_historico[
        (df_gps_historico["fecha"] >= fecha_inicio) & (df_gps_historico["fecha"] <= fecha_fin)
    ]
    df_well_semana = df_wellness_historico[
        (df_wellness_historico["fecha"] >= fecha_inicio) & (df_wellness_historico["fecha"] <= fecha_fin)
    ]

    jugadoras_semana = set(df_gps_semana["player_id"]) | set(df_well_semana["player_id"])

    mapa_pos = df_roster.set_index("player_id")["posicion"].to_dict() if not df_roster.empty else {}
    mapa_nombre = {}
    if not df_gps_historico.empty:
        for _, fila in df_gps_historico.drop_duplicates("player_id").iterrows():
            mapa_nombre[fila["player_id"]] = fila["nombre"]
    if not df_wellness_historico.empty:
        for _, fila in df_wellness_historico.drop_duplicates("player_id").iterrows():
            mapa_nombre.setdefault(fila["player_id"], fila["nombre"])

    veredictos = []
    for player_id in sorted(jugadoras_semana):
        veredictos.append(evaluar_jugadora_semana(
            player_id=player_id,
            nombre=mapa_nombre.get(player_id, player_id),
            posicion=mapa_pos.get(player_id),
            df_gps_jugadora_semana=df_gps_semana[df_gps_semana["player_id"] == player_id],
            df_gps_jugadora_historico=df_gps_historico[df_gps_historico["player_id"] == player_id],
            df_wellness_jugadora_semana=df_well_semana[df_well_semana["player_id"] == player_id],
            fecha_fin_semana=fecha_fin,
        ))

    orden_semaforo = {ROJO: 0, AMARILLO: 1, VERDE: 2}
    veredictos.sort(key=lambda v: (orden_semaforo[v.semaforo], -len(v.senales)))
    return veredictos


def tabla_kpis_semana(df_gps_semana: pd.DataFrame, df_gps_previo: pd.DataFrame) -> pd.DataFrame:
    """
    KPIs físicos clave por jugadora para la semana del reporte, comparados
    contra (a) la media del equipo/posición esa misma semana y (b) el
    propio histórico de la jugadora — nunca el valor crudo aislado (regla
    dura del proyecto).

    Las tres columnas son PROMEDIO POR DÍA de entrenamiento/partido, nunca
    una suma: sumar toda la ventana del reporte (que puede ser una semana
    calendario o, si hubo un hueco de partidos, varias semanas — ver
    definir_semana_reporte()) y compararlo contra un promedio diario
    histórico mezclaría dos unidades distintas. Se totaliza primero
    Físico+Técnico-Táctico del mismo día (mismo criterio que
    _totalizar_por_dia en parametros.py) y recién ahí se promedia sobre los
    días — nunca sobre sesiones sueltas, para no pesar doble un día con dos
    sesiones.

    df_gps_semana debe traer la columna "posicion" ya mergeada. df_gps_previo
    es el historial ANTERIOR a la semana (ver armar_veredictos_semana): no
    incluye la semana del reporte, para que "propio histórico" no se
    compare contra sí mismo.

    Devuelve una fila por (jugadora, métrica): [player_id, nombre, posicion,
    metrica, valor_semana, media_equipo_posicion, propio_historico].
    """
    columnas = ["player_id", "nombre", "posicion", "metrica",
                "valor_semana", "media_equipo_posicion", "propio_historico"]
    columnas_metrica = [c for c in METRICA_A_COLUMNA.values() if c in df_gps_semana.columns]
    if df_gps_semana.empty or not columnas_metrica or "posicion" not in df_gps_semana.columns:
        return pd.DataFrame(columns=columnas)

    diario_semana = (
        df_gps_semana.groupby(["player_id", "nombre", "posicion", "fecha"], as_index=False)[columnas_metrica]
        .sum()
    )
    promedio_semana = (
        diario_semana.groupby(["player_id", "nombre", "posicion"], as_index=False)[columnas_metrica]
        .mean()
    )
    # Media equipo/posición = promedio, ENTRE JUGADORAS de esa posición, de
    # su propio promedio diario de la semana — no el promedio de sesiones
    # sueltas (una jugadora con más sesiones sueltas pesaría más que una con
    # menos, aunque ambas hayan entrenado los mismos días).
    media_equipo_pos = promedio_semana.groupby("posicion")[columnas_metrica].mean()

    propio_historico = pd.DataFrame(columns=columnas_metrica)
    if not df_gps_previo.empty:
        propio_historico = (
            df_gps_previo.groupby(["player_id", "fecha"])[columnas_metrica].sum()
            .groupby("player_id").mean()
        )

    metrica_por_columna = {c: m for m, c in METRICA_A_COLUMNA.items()}
    filas = []
    for _, fila in promedio_semana.iterrows():
        for columna in columnas_metrica:
            valor_equipo = (media_equipo_pos.loc[fila["posicion"], columna]
                             if fila["posicion"] in media_equipo_pos.index else None)
            valor_propio = (propio_historico.loc[fila["player_id"], columna]
                             if fila["player_id"] in propio_historico.index else None)
            filas.append({
                "player_id": fila["player_id"], "nombre": fila["nombre"], "posicion": fila["posicion"],
                "metrica": metrica_por_columna[columna], "valor_semana": fila[columna],
                "media_equipo_posicion": valor_equipo, "propio_historico": valor_propio,
            })
    return pd.DataFrame(filas, columns=columnas)


# ── FODA de periodización de la semana ──────────────────────────────────────
# Responde específicamente "qué tan bien o no están distribuidas las cargas
# según el día de entrenamiento" (feedback de Tomi) — adapta la MISMA lógica
# que ya arma pages/08_analisis.py (ver _NOTAS_PERIODIZACION / bullets de ahí),
# pero acotada a la ventana de la semana del reporte en vez de un rango
# elegido a mano, y reusando foda.py tal cual (nunca reimplementado).

def foda_periodizacion_semana(df_gps_semana: pd.DataFrame, df_parametros: pd.DataFrame,
                               umbral_bullet: float = UMBRAL_FODA_SEMANA) -> dict:
    """
    FODA de periodización de ESTA semana: solo sesiones de entrenamiento
    (Físico/Técnico-Táctico — se excluye Partido/Amistoso, ver TIPOS_SESION
    en settings.py), agrupado por Match Day.

    A diferencia de pages/08_analisis.py (que suele mirar varias semanas o
    una temporada), acá el universo de "sesiones por Match Day" es chico
    (normalmente 1 por tipo en la semana) — por eso NO se repite el aviso de
    "muestra chica" de duración (UMBRAL_MUESTRA_MINIMA_MD): con una sola
    sesión por MD ese aviso dispararía siempre y no aportaría señal nueva.
    El % de cumplimiento del Asistente de Parámetros, en cambio, sí tiene
    una n razonable (una fila por jugadora evaluada ese día), así que ESE
    número es el que sostiene fortalezas/debilidades acá.

    Devuelve {"fortalezas": [...], "debilidades": [...], "oportunidades": [...],
    "amenazas": [...]} — mismo shape que usa foda_quadrant_html() en pantalla,
    listas de str (pueden traer <b>...</b>, igual que ya hace la página).
    """
    fortalezas, debilidades, oportunidades, amenazas = [], [], [], []

    if df_gps_semana.empty or "tipo_sesion" not in df_gps_semana.columns:
        return {"fortalezas": fortalezas, "debilidades": debilidades,
                "oportunidades": oportunidades, "amenazas": amenazas}

    tipos_partido = [TIPOS_SESION[2], TIPOS_SESION[3]]  # Partido, Amistoso
    df_train = df_gps_semana[~df_gps_semana["tipo_sesion"].isin(tipos_partido)].copy()
    if df_train.empty or "match_day" not in df_train.columns:
        return {"fortalezas": fortalezas, "debilidades": debilidades,
                "oportunidades": oportunidades, "amenazas": amenazas}
    df_train = df_train[df_train["match_day"].notna() & (df_train["match_day"] != "Sin clasificar")]

    # ── ACWR por Match Day (fortaleza si el equipo está mayormente en Óptimo) ──
    resumen_acwr = resumen_acwr_por_md(df_train)
    if not resumen_acwr.empty:
        fila_optimo = resumen_acwr[resumen_acwr["zona_acwr"] == "Óptimo"]
        if not fila_optimo.empty:
            pct_prom_optimo = fila_optimo["pct"].mean() * 100
            if pct_prom_optimo >= umbral_bullet * 100:
                fortalezas.append(
                    f"ACWR en zona <b>Óptimo</b> en el {pct_prom_optimo:.0f}% de las sesiones "
                    "de entrenamiento de esta semana — sin señal de sobrecarga crónica."
                )
        fila_riesgo = resumen_acwr[resumen_acwr["zona_acwr"] == "Riesgo Alto"]
        if not fila_riesgo.empty:
            pct_prom_riesgo = fila_riesgo["pct"].mean() * 100
            if pct_prom_riesgo > 0:
                debilidades.append(
                    f"ACWR en <b>Riesgo Alto</b> en el {pct_prom_riesgo:.0f}% de las sesiones "
                    "de entrenamiento de esta semana — ver el detalle por jugadora en Banderas."
                )

    # ── Cumplimiento vs. Asistente de Parámetros, por Match Day ─────────────
    resumen_cump = pd.DataFrame()
    calibracion = []
    if df_parametros is not None and not df_parametros.empty and "posicion" in df_train.columns:
        df_individual = evaluar_por_jugadora(
            df_train, df_parametros, claves_dia=["posicion", "fecha", "match_day"],
        )
        if not df_individual.empty:
            resumen_cump = resumen_cumplimiento_por_md(df_individual)
            calibracion = detectar_posible_calibracion(resumen_cump, UMBRAL_CALIBRACION_PCT)

    metricas_flag_calibracion = {h["metrica"] for h in calibracion}
    if not resumen_cump.empty:
        for _, fila in resumen_cump.iterrows():
            if fila["metrica"] in metricas_flag_calibracion:
                continue  # ya va en amenazas como posible problema de calibración, no de entrenamiento
            n_evaluadas = fila["n"]
            if fila["pct_por_debajo"] >= umbral_bullet:
                debilidades.append(
                    f"<b>{fila['metrica']}</b> por debajo del rango esperado en el "
                    f"{fila['pct_por_debajo']*100:.0f}% de las jugadoras evaluadas en "
                    f"{fila['match_day']} (n={n_evaluadas}) — carga insuficiente para ese día "
                    "de periodización."
                )
            elif fila["pct_por_encima"] >= umbral_bullet:
                debilidades.append(
                    f"<b>{fila['metrica']}</b> por encima del rango esperado en el "
                    f"{fila['pct_por_encima']*100:.0f}% de las jugadoras evaluadas en "
                    f"{fila['match_day']} (n={n_evaluadas}) — posible sobrecarga para ese día."
                )
            elif fila["pct_en_rango"] >= umbral_bullet:
                fortalezas.append(
                    f"<b>{fila['metrica']}</b> en rango esperado en el "
                    f"{fila['pct_en_rango']*100:.0f}% de las jugadoras evaluadas en "
                    f"{fila['match_day']} (n={n_evaluadas})."
                )

    for h in calibracion:
        amenazas.append(
            f"<b>{h['metrica']}</b> ({h['match_day']}): {h['direccion'].lower()} del rango en "
            f"<b>{h['pct']*100:.0f}%</b> de las jugadoras — patrón demasiado parejo para ser "
            "solo entrenamiento; revisar el rango cargado en el Sheet \"Parametros\" antes de "
            "actuar sobre la planificación."
        )

    # ── Duración — variabilidad dentro de la semana ─────────────────────────
    resumen_dur = resumen_duracion_por_md(df_train)
    for _, fila in resumen_dur[resumen_dur["variabilidad_alta"]].iterrows():
        amenazas.append(
            f"<b>{fila['match_day']} · {fila['tipo_sesion']}</b>: duración muy variable entre "
            f"sesiones de esta semana ({fila['minimo_min']:.0f}-{fila['maximo_min']:.0f} min) — "
            "probablemente falta el corte manual de \"tiempos muertos\" del GPS en alguna; no "
            "sacar conclusiones de carga sobre esta MD todavía."
        )

    if not resumen_cump.empty:
        oportunidades.append(
            "Hay diferencias de exigencia por posición dentro de un mismo Match Day — "
            "prescribir carga diferenciada por puesto (no un objetivo único) puede mejorar "
            "el cumplimiento de esta tabla la próxima semana."
        )
    oportunidades.append(
        "El z-score histórico de la sección de Banderas separa un pico puntual de una "
        "jugadora, contra su propio historial, de un patrón de todo el equipo — usarlo antes "
        "de tocar la planificación general de un Match Day."
    )

    return {"fortalezas": fortalezas, "debilidades": debilidades,
            "oportunidades": oportunidades, "amenazas": amenazas}


def tabla_foda_periodizacion(foda: dict) -> pd.DataFrame:
    """FODA de periodización como tabla [Cuadrante, Hallazgo] — mismo shape
    que ya arma pages/08_analisis.py para su propio PDF (filas_foda_pdf),
    reusado acá para que PDF y DOCX del reporte semanal dibujen una tabla
    simple en vez de necesitar layout propio."""
    filas = (
        [{"Cuadrante": "Fortaleza", "Hallazgo": h} for h in foda["fortalezas"]]
        + [{"Cuadrante": "Debilidad", "Hallazgo": h} for h in foda["debilidades"]]
        + [{"Cuadrante": "Oportunidad", "Hallazgo": h} for h in foda["oportunidades"]]
        + [{"Cuadrante": "Amenaza", "Hallazgo": h} for h in foda["amenazas"]]
    )
    columnas = ["Cuadrante", "Hallazgo"]
    return pd.DataFrame(filas, columns=columnas) if filas else pd.DataFrame(columns=columnas)


# ── Correlaciones de temporada ──────────────────────────────────────────────
# "Comparación y correlación de variables" (feedback de Tomi) — Pearson
# (scipy.stats.pearsonr) sobre TODO el historial disponible, no solo la
# semana: una correlación con pocos pares no dice nada (ver CORRELACION_MIN_N)
# y una sola semana normalmente no alcanza. Determinístico: r/p salen de la
# fórmula, nunca de una estimación — la única parte "de texto" es la nota de
# contexto de cada par, que es fija de antemano, no generada en runtime.

def _interpretar_correlacion(r: float, p: float, n: int, min_n: int = CORRELACION_MIN_N) -> str:
    """
    Traduce (r, p, n) a una frase ejecutiva, determinística:
      - n insuficiente -> aviso de muestra chica, no se interpreta el signo.
      - p >= 0.05       -> "sin significancia", el r no se describe como hallazgo.
      - p < 0.05        -> fuerza (Cohen, umbrales de |r| habituales en ciencias
                            del deporte) + dirección.
    """
    if n < min_n:
        return f"Muestra insuficiente (n={n}, mínimo {min_n}) — no sacar conclusiones todavía."
    if pd.isna(r) or pd.isna(p):
        return f"No se pudo calcular (datos sin varianza suficiente, n={n})."
    if p >= 0.05:
        return f"Sin significancia estadística (r={r:.2f}, p={p:.3f}, n={n})."
    direccion = "positiva" if r >= 0 else "negativa"
    abs_r = abs(r)
    if abs_r < 0.30:
        fuerza = "débil"
    elif abs_r < 0.50:
        fuerza = "moderada"
    elif abs_r < 0.70:
        fuerza = "fuerte"
    else:
        fuerza = "muy fuerte"
    return f"Correlación {direccion} {fuerza} (r={r:.2f}, p={p:.3f}, n={n})."


def _correlacion_par(x: pd.Series, y: pd.Series, nombre: str, nota: str,
                      min_n: int = CORRELACION_MIN_N) -> dict:
    n = len(x)
    if n < 3:
        r, p = float("nan"), float("nan")
    else:
        r, p = pearsonr(x, y)
    return {
        "Correlación": nombre, "r": round(r, 3) if pd.notna(r) else None,
        "p-valor": round(p, 4) if pd.notna(p) else None, "n": n,
        "Interpretación": _interpretar_correlacion(r, p, n, min_n),
        "Nota": nota,
    }


def correlaciones_temporada(df_gps_historico: pd.DataFrame, df_wellness_historico: pd.DataFrame,
                             min_n: int = CORRELACION_MIN_N) -> pd.DataFrame:
    """
    Correlaciones de temporada completa (no solo la semana del reporte —
    para tener n razonable) entre:
      1. sRPE (RPE × duración, carga INTERNA percibida) vs. Player Load
         (carga EXTERNA del GPS) del mismo día — coherencia entre lo que la
         jugadora siente y lo que el GPS mide.
      2. ACWR vs. TQR del mismo día — si la carga aguda/crónica se refleja
         en cómo la jugadora dice llegar de recuperada.

    Ambas a nivel (jugadora, día): si una jugadora tuvo Físico + Técnico-
    Táctico el mismo día, el GPS se totaliza a nivel día ANTES de correlacionar
    (mismo criterio que tabla_kpis_semana) para no pesar doble ese día.

    Devuelve columnas [Correlación, r, p-valor, n, Interpretación, Nota] —
    listo para SeccionTabla, ninguna celda requiere formateo adicional salvo
    convertir a string.
    """
    columnas = ["Correlación", "r", "p-valor", "n", "Interpretación", "Nota"]
    filas = []

    if (not df_gps_historico.empty and not df_wellness_historico.empty
            and {"player_id", "fecha", "duracion_min", "player_load"} <= set(df_gps_historico.columns)):
        gps_diario = (
            df_gps_historico.groupby(["player_id", "fecha"], as_index=False)[["duracion_min", "player_load"]]
            .sum()
        )
        well_srpe = calcular_srpe(df_wellness_historico, gps_diario)
        merged = well_srpe.merge(
            gps_diario[["player_id", "fecha", "player_load"]], on=["player_id", "fecha"], how="inner",
        ).dropna(subset=["srpe", "player_load"])
        filas.append(_correlacion_par(
            merged["srpe"], merged["player_load"],
            "sRPE (carga interna) vs. Player Load (carga externa)",
            "Coherencia esperada: si el RPE reportado no acompaña la carga externa medida por "
            "GPS, revisar si el formulario se completa con atención antes de asumir un problema "
            "físico real.",
            min_n,
        ))

    if not df_gps_historico.empty and "acwr" in df_gps_historico.columns and not df_wellness_historico.empty:
        acwr_diario = (
            df_gps_historico.dropna(subset=["acwr"])
            .drop_duplicates(["player_id", "fecha"])[["player_id", "fecha", "acwr"]]
        )
        merged = df_wellness_historico.merge(
            acwr_diario, on=["player_id", "fecha"], how="inner",
        ).dropna(subset=["acwr", "tqr"])
        filas.append(_correlacion_par(
            merged["acwr"], merged["tqr"], "ACWR vs. TQR (mismo día)",
            "Se espera una relación negativa (más ACWR, menor recuperación reportada) — si "
            "aparece positiva o nula con n suficiente, la carga no está siendo el principal "
            "driver del TQR de las jugadoras y conviene mirar otros factores (sueño, estrés "
            "extradeportivo, ciclo menstrual).",
            min_n,
        ))

    return pd.DataFrame(filas, columns=columnas)


# ── Plan de acción ───────────────────────────────────────────────────────────
# Cierre accionable a nivel EQUIPO (además del que ya trae cada VeredictoJugadora
# en .recomendacion) — junta Rojo/Amarillo individuales con las debilidades y
# amenazas del FODA de periodización en una sola lista priorizada, para que el
# cuerpo técnico tenga un único lugar de "qué hacer" en vez de tener que armar
# el plan mentalmente cruzando 3 secciones distintas del informe.
ORDEN_PRIORIDAD = {"Alta": 0, "Media": 1, "Baja": 2}


def plan_de_accion(veredictos: list, foda_periodizacion: dict) -> pd.DataFrame:
    """Devuelve [Prioridad, Área, Hallazgo, Acción recomendada], ordenado
    Alta -> Media -> Baja. Cada fila es trazable: viene de un VeredictoJugadora
    real (con su .recomendacion ya calculada por _recomendacion()) o de un
    bullet real del FODA de la semana — nada se redacta de cero acá."""
    filas = []
    for v in veredictos:
        if v.semaforo == ROJO:
            filas.append({
                "Prioridad": "Alta", "Área": v.nombre,
                "Hallazgo": "; ".join(s.texto for s in v.senales) or "—",
                "Acción recomendada": v.recomendacion,
            })
        elif v.semaforo == AMARILLO:
            filas.append({
                "Prioridad": "Media", "Área": v.nombre,
                "Hallazgo": "; ".join(s.texto for s in v.senales) or "—",
                "Acción recomendada": v.recomendacion,
            })

    for h in foda_periodizacion.get("debilidades", []):
        filas.append({
            "Prioridad": "Media", "Área": "Equipo — periodización",
            "Hallazgo": h,
            "Acción recomendada": "Revisar el diseño de esa sesión con cuerpo técnico "
                                   "(volumen/intensidad prescripta vs. lo realmente ejecutado).",
        })
    for h in foda_periodizacion.get("amenazas", []):
        if "calibra" in h.lower() or "revisar el rango" in h.lower():
            filas.append({
                "Prioridad": "Baja", "Área": "Parámetros del Sheet",
                "Hallazgo": h,
                "Acción recomendada": "Revisar el rango cargado en la pestaña \"Parametros\" "
                                       "antes de tomar una decisión de entrenamiento sobre esto.",
            })

    columnas = ["Prioridad", "Área", "Hallazgo", "Acción recomendada"]
    df = pd.DataFrame(filas, columns=columnas)
    if df.empty:
        return df
    df["_orden"] = df["Prioridad"].map(ORDEN_PRIORIDAD)
    return df.sort_values("_orden").drop(columns="_orden").reset_index(drop=True)


# ── Resumen ejecutivo ────────────────────────────────────────────────────────
# Texto de portada/dashboard del informe — cada oración sale de un número ya
# calculado más arriba (veredictos, FODA, correlaciones): ninguna frase se
# redacta libre en runtime, es selección de plantilla + interpolación de
# datos reales, mismo criterio determinístico que el resto del módulo.

def resumen_ejecutivo(veredictos: list, foda_periodizacion: dict,
                       df_correlaciones: pd.DataFrame) -> list[str]:
    """Devuelve una lista de párrafos (str, pueden traer <b>) para la
    portada del informe — ni tabla ni gráfico, puro texto ejecutivo."""
    rojos = [v for v in veredictos if v.semaforo == ROJO]
    amarillos = [v for v in veredictos if v.semaforo == AMARILLO]
    verdes = [v for v in veredictos if v.semaforo == VERDE]
    parrafos = []

    parrafos.append(
        f"Se evaluaron <b>{len(veredictos)}</b> jugadoras de 1era división esta semana: "
        f"<b>{len(rojos)}</b> en Rojo, <b>{len(amarillos)}</b> en Amarillo y "
        f"<b>{len(verdes)}</b> en Verde."
    )

    if rojos:
        nombres = ", ".join(v.nombre for v in rojos[:5])
        sufijo = f" y {len(rojos) - 5} más" if len(rojos) > 5 else ""
        parrafos.append(
            f"Prioridad inmediata: <b>{nombres}{sufijo}</b> — ver Banderas y Plan de acción "
            "para el detalle de cada caso y su recomendación puntual."
        )
    else:
        parrafos.append("Sin jugadoras en Rojo esta semana — ninguna con 2+ señales "
                         "simultáneas de riesgo ni ACWR en zona de Riesgo Alto.")

    n_fort = len(foda_periodizacion.get("fortalezas", []))
    n_deb = len(foda_periodizacion.get("debilidades", []))
    if n_deb == 0 and n_fort > 0:
        parrafos.append(
            "La periodización de la semana estuvo bien distribuida por día de entrenamiento: "
            f"{n_fort} hallazgo(s) positivo(s) y ninguna debilidad detectada en el cruce contra "
            "el Asistente de Parámetros."
        )
    elif n_deb > 0:
        parrafos.append(
            f"La periodización de la semana muestra <b>{n_deb}</b> punto(s) a revisar por día de "
            f"entrenamiento (frente a {n_fort} fortaleza(s)) — ver FODA de periodización para el "
            "detalle por Match Day y métrica."
        )
    else:
        parrafos.append(
            "No hubo suficientes sesiones de entrenamiento clasificadas por Match Day esta "
            "semana para evaluar la periodización."
        )

    if df_correlaciones is not None and not df_correlaciones.empty:
        significativas = df_correlaciones[df_correlaciones["Interpretación"].str.startswith("Correlación")]
        if not significativas.empty:
            primera = significativas.iloc[0]
            parrafos.append(
                f"De temporada: {primera['Correlación']} muestra {primera['Interpretación'].lower()} "
                "— ver Correlaciones de temporada para el resto de los cruces."
            )

    return parrafos
