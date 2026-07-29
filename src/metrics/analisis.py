# src/metrics/analisis.py
"""
Análisis en lenguaje natural del Asistente de Parámetros — fortalezas,
debilidades y recomendaciones por jugadora.

Determinístico a propósito: NINGÚN LLM decide acá si una jugadora está bien
o mal — ese veredicto ya lo calculó evaluar_por_jugadora() (Python puro
contra la hoja de Parametros). Esto solo arma reglas fijas sobre esos
estados ya verificados. Es una herramienta que puede influir en decisiones
de carga/salud de jugadoras, así que el motivo detrás de cada hallazgo tiene
que poder rastrearse hasta un número real, nunca "inventado".
"""
import pandas as pd

from settings import ZSCORE_ALERTA
from src.metrics.parametros import EN_RANGO, POR_DEBAJO, POR_ENCIMA, SIN_DATO

UMBRAL_DEBILIDAD_DEFAULT = 2


def generar_analisis(df_individual: pd.DataFrame,
                      umbral_debilidad: int = UMBRAL_DEBILIDAD_DEFAULT) -> dict:
    """
    Arma fortalezas y debilidades a partir de una evaluación por jugadora
    (ver evaluar_por_jugadora() en parametros.py).

    - Fortaleza: la jugadora no tiene NINGUNA métrica fuera de rango entre
      las evaluadas.
    - Debilidad: la jugadora tiene `umbral_debilidad` o más métricas fuera
      de rango (por debajo o por encima, sumadas). Con 1 sola métrica fuera
      de rango no se marca como fortaleza NI como debilidad — un dato
      aislado no es un patrón todavía; ese umbral es un punto de partida,
      ajustable con más uso real.
    - Si se evaluó más de un día/sesión para la misma jugadora, las métricas
      fuera de rango de todos esos días se cuentan juntas para el umbral
      (no hay separación por día en esta primera versión).

    Devuelve {"fortalezas": [nombre, ...], "fortalezas_atipicas": [...],
    "debilidades": [...]}.

    "fortalezas_atipicas" es un dato COMPLEMENTARIO a "fortalezas", nunca lo
    reemplaza: una jugadora en rango en todas sus métricas del Sheet puede
    igual tener un pico atípico contra SU PROPIO historial (ver
    calcular_zscore_historico en physical.py) — algo que el rango por
    posición no puede ver. Cada entrada es un dict {"nombre",
    "metricas_atipicas"} donde "metricas_atipicas" son las filas de esa
    jugadora (formato igual a "metricas_fuera") con |z_score| >=
    ZSCORE_ALERTA. Queda vacía si no vino la columna "z_score" o si ninguna
    fortaleza tiene un pico atípico.

    Cada debilidad es un dict {"nombre", "posicion", "metricas_fuera",
    "metricas_en_rango", "peor_estado", "recomendaciones"}:
    - "metricas_fuera": lista de dicts {"metrica", "estado", "valor_real",
      "rango_min", "rango_max"} — una por métrica fuera de rango.
    - "metricas_en_rango": mismo formato, para las métricas de esa jugadora
      que SÍ están en rango óptimo — la tarjeta no muestra solo lo que está
      mal, también lo que está bien.
    - "peor_estado": POR_ENCIMA si tiene al menos una métrica por encima
      (más urgente — riesgo de sobrecarga), si no POR_DEBAJO. Pensado para
      elegir el color de acento de la tarjeta en la UI.
    - "recomendaciones": 1-2 oraciones consolidadas (una para las métricas
      por debajo agrupadas, otra para las por encima agrupadas) en vez de
      una línea repetida por métrica — más sintético para leer de un
      vistazo en una tarjeta chica.
    """
    vacio = {"fortalezas": [], "fortalezas_atipicas": [], "debilidades": []}
    if df_individual.empty:
        return vacio

    evaluadas = df_individual[df_individual["estado"] != SIN_DATO]
    if evaluadas.empty:
        return vacio

    # "z_score" es un dato complementario opcional (ver evaluar_sesion() en
    # parametros.py) — si df_individual viene de una fuente que no lo
    # calculó, se sigue evaluando fortaleza/debilidad igual, sin ese campo.
    cols_metrica = ["metrica", "estado", "valor_real", "rango_min", "rango_max"]
    if "z_score" in df_individual.columns:
        cols_metrica.append("z_score")

    fortalezas = []
    fortalezas_atipicas = []
    debilidades = []
    for nombre, grupo in evaluadas.groupby("nombre"):
        fuera = grupo[grupo["estado"].isin([POR_DEBAJO, POR_ENCIMA])]
        if fuera.empty:
            fortalezas.append(nombre)
            if "z_score" in grupo.columns:
                # to_numeric en vez de .abs() directo: si la columna vino
                # sin calcular en absolutamente ninguna fila, queda como
                # None (no NaN) y .abs() sobre eso tira TypeError.
                z_scores = pd.to_numeric(grupo["z_score"], errors="coerce")
                atipicas = grupo[z_scores.abs() >= ZSCORE_ALERTA]
                if not atipicas.empty:
                    fortalezas_atipicas.append({
                        "nombre": nombre,
                        "metricas_atipicas": atipicas[cols_metrica].to_dict("records"),
                    })
        elif len(fuera) >= umbral_debilidad:
            metricas_fuera = fuera[cols_metrica].to_dict("records")
            metricas_en_rango = grupo[grupo["estado"] == EN_RANGO][cols_metrica].to_dict("records")
            peor_estado = (
                POR_ENCIMA if any(m["estado"] == POR_ENCIMA for m in metricas_fuera) else POR_DEBAJO
            )
            debilidades.append({
                "nombre": nombre,
                "posicion": grupo["posicion"].iloc[0],
                "metricas_fuera": metricas_fuera,
                "metricas_en_rango": metricas_en_rango,
                "peor_estado": peor_estado,
                "recomendaciones": _consolidar_recomendaciones(metricas_fuera),
            })

    debilidades.sort(key=lambda d: len(d["metricas_fuera"]), reverse=True)

    return {
        "fortalezas": sorted(fortalezas),
        "fortalezas_atipicas": fortalezas_atipicas,
        "debilidades": debilidades,
    }


def _consolidar_recomendaciones(metricas: list[dict]) -> list[str]:
    """Agrupa las métricas fuera de rango de UNA jugadora por dirección de
    desvío, en vez de una oración por métrica — una jugadora con 3 métricas
    por debajo da 1 sola línea, no 3 repetidas."""
    por_debajo = [m["metrica"] for m in metricas if m["estado"] == POR_DEBAJO]
    por_encima = [m["metrica"] for m in metricas if m["estado"] == POR_ENCIMA]

    recomendaciones = []
    if por_debajo:
        recomendaciones.append(f"Reforzar estímulo en {', '.join(por_debajo)}.")
    if por_encima:
        recomendaciones.append(
            f"Vigilar sobrecarga en {', '.join(por_encima)} — "
            "considerar ajustar volumen o sumar descanso."
        )
    return recomendaciones


def tabla_analisis_pdf(analisis: dict) -> pd.DataFrame:
    """
    Formatea el resultado de generar_analisis() como tabla plana ["Jugadora",
    "Estado", "Detalle"] para el informe PDF — una fila por fortaleza (breve)
    y una fila por debilidad (métricas fuera de rango + recomendación ya
    consolidada). Sin tarjetas ni color, texto plano listo para SeccionTabla.

    Devuelve un DataFrame vacío si no hay ni fortalezas ni debilidades — el
    caller decide si igual agrega la sección o la omite del informe.
    """
    atipicas_por_nombre = {
        f["nombre"]: f["metricas_atipicas"] for f in analisis.get("fortalezas_atipicas", [])
    }
    filas = []
    for nombre in analisis["fortalezas"]:
        detalle = "En rango en todas las métricas evaluadas."
        if nombre in atipicas_por_nombre:
            metricas_txt = ", ".join(
                f"{m['metrica']} (z={m['z_score']:.1f})" for m in atipicas_por_nombre[nombre]
            )
            detalle += f" Atípica vs. su propio historial en: {metricas_txt}."
        filas.append({"Jugadora": nombre, "Estado": "Fortaleza", "Detalle": detalle})
    for d in analisis["debilidades"]:
        metricas_txt = ", ".join(f"{m['metrica']} ({m['estado']})" for m in d["metricas_fuera"])
        filas.append({
            "Jugadora": f"{d['nombre']} ({d['posicion']})",
            "Estado": "A vigilar",
            "Detalle": f"{metricas_txt}. {' '.join(d['recomendaciones'])}",
        })
    return pd.DataFrame(filas, columns=["Jugadora", "Estado", "Detalle"])
