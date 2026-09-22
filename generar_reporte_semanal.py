"""
generar_reporte_semanal.py
---------------------------
Arma el reporte semanal de carga + wellness — SOLO jugadoras de 1era
división (a pedido de Tomi, "por el momento") — con: dashboard/resumen
ejecutivo arriba de todo, banderas rojas, FODA de periodización de la
semana (qué tan bien están distribuidas las cargas por día de
entrenamiento), KPIs físicos vs. equipo/histórico, cruce con wellness,
Asistente de Parámetros, correlaciones de temporada y un plan de acción
único y priorizado. Genera PDF (ejecutivo) Y DOCX (editable) del mismo
contenido.

Uso:
    python generar_reporte_semanal.py                          # último microciclo completo disponible
    python generar_reporte_semanal.py --fecha-fin 2026-08-30    # fuerza el fin del microciclo a evaluar
    python generar_reporte_semanal.py --out mi_reporte          # sin extensión: escribe mi_reporte.pdf y mi_reporte.docx

Solo LEE datos (Google Sheets en vivo + data/processed/gps_procesado.parquet)
— no modifica ni data/raw/ ni data/processed/, ni hace commit/push (eso, si
hace falta, queda en un paso aparte, igual que sync_pendientes_gps.py).
"""
import argparse
import sys
import tomllib
from datetime import datetime
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from settings import (
    CATEGORIA_PRIMERA, INFO_JUGADORAS_GID, INFO_JUGADORAS_SHEET_ID, PARAMETROS_SHEET_GID,
    PROCESSED, ROSTER_SHEET_GID, SESIONES_SHEET_GID, TIPOS_SESION, WELLNESS_SHEET_ID,
)
from src.loaders.categoria_loader import (
    advertir_no_matcheadas, cargar_categoria_desde_sheets, jugadoras_primera,
)
from src.loaders.parametros_loader import cargar_parametros_desde_sheets
from src.loaders.roster_loader import cargar_posiciones_desde_sheets
from src.loaders.sesiones_loader import cargar_sesiones_desde_sheets, orden_match_day
from src.loaders.wellness_loader import cargar_desde_supabase as cargar_wellness_desde_supabase
from src.metrics.analisis import generar_analisis
from src.metrics.foda import resumen_acwr_por_md
from src.metrics.parametros import evaluar_por_jugadora
from src.metrics.physical import calcular_acwr, calcular_intensidad_relativa, calcular_zscore_historico
from src.metrics.reporte_semanal import (
    AMARILLO, COLOR_AMARILLO, COLOR_ROJO, COLOR_VERDE, COLS_METRICA_ZSCORE,
    ROJO, VERDE, armar_veredictos_semana, correlaciones_temporada, definir_semana_reporte,
    foda_periodizacion_semana, plan_de_accion, resumen_ejecutivo, tabla_foda_periodizacion,
    tabla_kpis_semana,
)
from src.reports.docx_builder import generar_docx_reporte
from src.reports.pdf_builder import (
    SeccionAnalisis, SeccionFigura, SeccionTabla, SeccionTexto, generar_pdf_reporte,
)
from src.ui.charts import plotly_grouped_bar_layout
from src.ui.theme import ZONE_CFG


def _wellness_connection_string() -> str:
    """Lee el connection string de Supabase desde .streamlit/secrets.toml sin
    pasar por el runtime de Streamlit (este script corre standalone, vía
    CLI/cron) — mismo secreto que ya usan pages/03_wellness.py,
    04_fisico_vs_tt.py y 05_perfil_jugadora.py."""
    secrets_path = Path(__file__).parent / ".streamlit" / "secrets.toml"
    with open(secrets_path, "rb") as f:
        secrets = tomllib.load(f)
    return secrets["supabase"]["wellness_connection_string"]


def cargar_todo():
    """
    Carga todo lo que necesita el reporte, YA FILTRADO a jugadoras de 1era
    división (categoria_loader.jugadoras_primera) — el filtro se aplica acá,
    antes de calcular ACWR/z-score y antes de cualquier promedio de
    equipo/posición, para que "media del equipo" en tabla_kpis_semana nunca
    se contamine con jugadoras de Intermedia.

    player_id que aparecen en GPS/wellness pero no matchean con
    Info_jugadoras (nombre distinto entre planillas, por ejemplo) NO se
    descartan en silencio — se imprimen como aviso, ver advertir_no_matcheadas.
    """
    df_categoria = cargar_categoria_desde_sheets(INFO_JUGADORAS_SHEET_ID, INFO_JUGADORAS_GID)
    ids_primera = jugadoras_primera(df_categoria, CATEGORIA_PRIMERA)

    df_gps = pd.read_parquet(PROCESSED / "gps_procesado.parquet")
    df_wellness = cargar_wellness_desde_supabase(_wellness_connection_string())
    df_roster = cargar_posiciones_desde_sheets(WELLNESS_SHEET_ID, ROSTER_SHEET_GID)
    df_sesiones = cargar_sesiones_desde_sheets(WELLNESS_SHEET_ID, SESIONES_SHEET_GID)
    df_parametros = cargar_parametros_desde_sheets(WELLNESS_SHEET_ID, PARAMETROS_SHEET_GID)

    for etiqueta, ids_presentes in (("GPS", set(df_gps["player_id"])),
                                     ("wellness", set(df_wellness["player_id"]))):
        faltantes = advertir_no_matcheadas(ids_presentes, df_categoria)
        if faltantes:
            print(f"⚠️  {etiqueta}: player_id sin match en Info_jugadoras (¿nombre distinto entre "
                  f"planillas?) — no se filtran, revisar a mano: {faltantes}")

    df_gps = df_gps[df_gps["player_id"].isin(ids_primera)].copy()
    df_wellness = df_wellness[df_wellness["player_id"].isin(ids_primera)].copy()
    df_roster = df_roster[df_roster["player_id"].isin(ids_primera)].copy()

    df_gps = calcular_intensidad_relativa(df_gps)
    df_gps = calcular_acwr(df_gps, col_carga="player_load")
    df_gps = calcular_zscore_historico(df_gps, COLS_METRICA_ZSCORE)

    df_gps = df_gps.merge(df_roster[["player_id", "posicion"]], on="player_id", how="left")
    df_gps = df_gps.merge(df_sesiones, on="fecha", how="left")

    return df_gps, df_wellness, df_roster, df_sesiones, df_parametros


def _solo_entrenamientos(df_gps: pd.DataFrame) -> pd.DataFrame:
    """Sesiones de Físico/Técnico-Táctico, sin Partido ni Amistoso — mismo
    recorte que usa foda_periodizacion_semana() puertas adentro, reexpuesto
    acá para que el gráfico de ACWR por Match Day mire exactamente el mismo
    universo de sesiones que el FODA de periodización."""
    if df_gps.empty or "tipo_sesion" not in df_gps.columns:
        return df_gps
    tipos_partido = [TIPOS_SESION[2], TIPOS_SESION[3]]
    df = df_gps[~df_gps["tipo_sesion"].isin(tipos_partido)]
    if "match_day" in df.columns:
        df = df[df["match_day"].notna() & (df["match_day"] != "Sin clasificar")]
    return df


def _tabla_banderas(veredictos) -> pd.DataFrame:
    # Sin emoji acá a propósito: reportlab (PDF) y python-docx (Word) no
    # renderizan emoji de color — quedan como un cuadrado vacío ("tofu box")
    # en vez del ícono. El nombre del semáforo en texto plano es más
    # profesional y prolijo que un glifo roto, más alineado con el pedido
    # de Tomi de un informe "estéticamente más limpio". EMOJI_SEMAFORO sigue
    # existiendo para un eventual uso en pantalla (Streamlit sí renderiza
    # emoji bien) — acá simplemente no se usa.
    filas = [{
        "Semáforo": v.semaforo,
        "Jugadora": v.nombre,
        "Posición": v.posicion or "—",
        "Señales": "; ".join(s.texto for s in v.senales) or "—",
        "Recomendación": v.recomendacion,
    } for v in veredictos]
    columnas = ["Semáforo", "Jugadora", "Posición", "Señales", "Recomendación"]
    return pd.DataFrame(filas, columns=columnas) if filas else pd.DataFrame(columns=columnas)


def _tabla_kpis_pdf(df_kpis: pd.DataFrame) -> pd.DataFrame:
    df = df_kpis.copy()
    for col in ["valor_semana", "media_equipo_posicion", "propio_historico"]:
        df[col] = df[col].map(lambda v: f"{v:.0f}" if pd.notna(v) else "—")
    return df.rename(columns={
        "nombre": "Jugadora", "posicion": "Posición", "metrica": "Métrica",
        "valor_semana": "Prom. diario (semana)", "media_equipo_posicion": "Media equipo/posición",
        "propio_historico": "Propio histórico (prom. diario)",
    })[["Jugadora", "Posición", "Métrica", "Prom. diario (semana)",
        "Media equipo/posición", "Propio histórico (prom. diario)"]]


def _tabla_wellness(df_well_semana: pd.DataFrame) -> pd.DataFrame:
    resumen = (
        df_well_semana.groupby("nombre")
        .agg(tqr_prom=("tqr", "mean"), rpe_prom=("rpe", "mean"),
             molestias=("molestia_flag", "sum"), registros=("tqr", "count"))
        .round(1).reset_index()
        .sort_values("nombre")
    )
    return resumen.rename(columns={
        "nombre": "Jugadora", "tqr_prom": "TQR prom.", "rpe_prom": "RPE prom.",
        "molestias": "Molestias", "registros": "Registros",
    })


def _tabla_correlaciones_presentacion(df_corr: pd.DataFrame) -> pd.DataFrame:
    """Columnas de correlaciones_temporada() ya son texto listo para tabla,
    salvo r/p-valor (float) — formatea esas dos nada más."""
    if df_corr.empty:
        return df_corr
    df = df_corr.copy()
    df["r"] = df["r"].map(lambda v: f"{v:.2f}" if pd.notna(v) else "—")
    df["p-valor"] = df["p-valor"].map(lambda v: f"{v:.3f}" if pd.notna(v) else "—")
    return df


def _figura_semaforo(veredictos: list) -> go.Figure | None:
    """Distribución Verde/Amarillo/Rojo de la semana — mismo color y MISMO
    orden fijo que el resto del reporte (nunca alfabético ni por cantidad:
    un color de estado no rota, ver reporte_semanal.COLOR_SEMAFORO)."""
    if not veredictos:
        return None
    orden = [VERDE, AMARILLO, ROJO]
    conteo = {s: 0 for s in orden}
    for v in veredictos:
        conteo[v.semaforo] += 1
    df_plot = pd.DataFrame({"Semáforo": orden, "Jugadoras": [conteo[s] for s in orden]})
    fig = px.bar(
        df_plot, x="Semáforo", y="Jugadoras", color="Semáforo", text="Jugadoras",
        color_discrete_map={VERDE: COLOR_VERDE, AMARILLO: COLOR_AMARILLO, ROJO: COLOR_ROJO},
        category_orders={"Semáforo": orden},
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(**plotly_grouped_bar_layout(260))
    fig.update_layout(showlegend=False, title=dict(text="Jugadoras por semáforo esta semana"))
    return fig


def _figura_acwr_por_md(df_train_semana: pd.DataFrame) -> go.Figure | None:
    """% de sesiones de entrenamiento por zona de ACWR, por Match Day —
    responde "qué tan bien están distribuidas las cargas según el día de
    entrenamiento" con un vistazo (barras 100% apiladas, una por MD)."""
    resumen = resumen_acwr_por_md(df_train_semana)
    if resumen.empty:
        return None
    resumen = resumen.copy()
    resumen["pct_100"] = resumen["pct"] * 100
    orden_md = sorted(resumen["match_day"].unique(), key=orden_match_day)
    orden_zonas = [z for z in ["Subcarga", "Óptimo", "Precaución", "Riesgo Alto"]
                   if z in resumen["zona_acwr"].unique()]
    color_map = {z: ZONE_CFG[z]["color"] for z in orden_zonas}
    fig = px.bar(
        resumen, x="match_day", y="pct_100", color="zona_acwr", barmode="stack", text="pct_100",
        category_orders={"match_day": orden_md, "zona_acwr": orden_zonas},
        color_discrete_map=color_map,
        labels={"match_day": "Match Day", "pct_100": "% de sesiones", "zona_acwr": "Zona ACWR"},
    )
    fig.update_traces(texttemplate="%{text:.0f}%", textposition="inside")
    fig.update_layout(**plotly_grouped_bar_layout(300))
    fig.update_layout(title=dict(text="ACWR por Match Day — sesiones de entrenamiento de la semana"))
    return fig


def main(fecha_fin_arg: str | None, out_path: str | None):
    df_gps, df_wellness, df_roster, df_sesiones, df_parametros = cargar_todo()

    if df_gps.empty and df_wellness.empty:
        print("Sin datos de 1era división todavía (¿Info_jugadoras vacío o nombres sin match?). Abortando.")
        sys.exit(1)

    fecha_maxima = (datetime.strptime(fecha_fin_arg, "%Y-%m-%d").date()
                     if fecha_fin_arg else min(df_gps["fecha"].max(), df_wellness["fecha"].max()))
    rango = definir_semana_reporte(df_sesiones, fecha_maxima)
    if rango is None:
        print("Todavía no hay un microciclo completo (2 'MD' seguidos) con datos reales. Abortando.")
        sys.exit(1)
    fecha_inicio, fecha_fin = rango
    print(f"Reporte semanal (1era división): {fecha_inicio} → {fecha_fin}  (datos hasta {fecha_maxima})")

    veredictos = armar_veredictos_semana(df_gps, df_wellness, df_roster, fecha_inicio, fecha_fin)
    rojos = [v for v in veredictos if v.semaforo == ROJO]
    amarillos = [v for v in veredictos if v.semaforo == AMARILLO]

    df_gps_semana = df_gps[(df_gps["fecha"] >= fecha_inicio) & (df_gps["fecha"] <= fecha_fin)]
    df_gps_previo = df_gps[df_gps["fecha"] < fecha_inicio]
    df_kpis = tabla_kpis_semana(df_gps_semana, df_gps_previo)

    df_individual = pd.DataFrame()
    if not df_gps_semana.empty:
        df_individual = evaluar_por_jugadora(
            df_gps_semana, df_parametros, claves_dia=["posicion", "fecha", "match_day"],
        )
    analisis = (generar_analisis(df_individual) if not df_individual.empty
                else {"fortalezas": [], "fortalezas_atipicas": [], "debilidades": []})

    df_well_semana = df_wellness[(df_wellness["fecha"] >= fecha_inicio) & (df_wellness["fecha"] <= fecha_fin)]

    # ── Análisis nuevo — FODA de periodización, correlaciones, plan de acción ──
    foda = foda_periodizacion_semana(df_gps_semana, df_parametros)
    df_corr = correlaciones_temporada(df_gps, df_wellness)
    df_plan = plan_de_accion(veredictos, foda)
    parrafos_resumen = resumen_ejecutivo(veredictos, foda, df_corr)

    fig_semaforo = _figura_semaforo(veredictos)
    fig_acwr_md = _figura_acwr_por_md(_solo_entrenamientos(df_gps_semana))

    # ── Secciones, en el orden del proyecto: dashboard/resumen primero, ────
    # banderas rojas siempre arriba del resto del detalle, cierre accionable
    # (plan de acción) al final.
    # Sin emoji en títulos/KPIs del documento — mismo motivo que en
    # _tabla_banderas (reportlab/python-docx no renderizan emoji de color).
    secciones = [SeccionTexto("Resumen Ejecutivo", parrafos_resumen)]
    if fig_semaforo is not None:
        secciones.append(SeccionFigura("Distribución de semáforo", fig_semaforo, alto_cm=7.0))
    if fig_acwr_md is not None:
        secciones.append(SeccionFigura("ACWR por Match Day", fig_acwr_md, alto_cm=8.0))

    secciones.append(SeccionTabla("Banderas — jugadoras a vigilar esta semana",
                                   _tabla_banderas(rojos + amarillos)))

    secciones.append(SeccionTabla("FODA de periodización de la semana",
                                   tabla_foda_periodizacion(foda)))

    if not df_kpis.empty:
        secciones.append(SeccionTabla("KPIs físicos de la semana", _tabla_kpis_pdf(df_kpis)))

    if not df_well_semana.empty:
        secciones.append(SeccionTabla("Wellness de la semana", _tabla_wellness(df_well_semana)))

    secciones.append(SeccionAnalisis("Asistente de Parámetros — fortalezas y debilidades", analisis))

    if not df_corr.empty:
        secciones.append(SeccionTabla("Correlaciones de temporada",
                                       _tabla_correlaciones_presentacion(df_corr)))

    if not df_plan.empty:
        secciones.append(SeccionTabla("Plan de acción de la semana", df_plan))

    kpis_header = [
        ("Semana", f"{fecha_inicio:%d/%m} - {fecha_fin:%d/%m}"),
        ("Jugadoras evaluadas", str(len(veredictos))),
        ("Rojo", str(len(rojos))),
        ("Amarillo", str(len(amarillos))),
    ]
    titulo = "Reporte Semanal de Carga y Wellness"
    subtitulo = (f"Centro Naval Hockey — Primera División Femenina · "
                 f"{fecha_inicio:%d/%m/%Y} - {fecha_fin:%d/%m/%Y}")

    pdf_bytes = generar_pdf_reporte(titulo=titulo, subtitulo=subtitulo, kpis=kpis_header, secciones=secciones)
    docx_bytes = generar_docx_reporte(titulo=titulo, subtitulo=subtitulo, kpis=kpis_header, secciones=secciones)

    if out_path:
        base = Path(out_path)
        if base.suffix:
            base = base.with_suffix("")
    else:
        base = Path("data/reportes") / f"reporte_semanal_{fecha_inicio:%Y%m%d}_{fecha_fin:%Y%m%d}"
    base.parent.mkdir(parents=True, exist_ok=True)

    destino_pdf = base.with_suffix(".pdf")
    destino_docx = base.with_suffix(".docx")
    destino_pdf.write_bytes(pdf_bytes)
    destino_docx.write_bytes(docx_bytes)
    print(f"✅ Reporte generado: {destino_pdf} y {destino_docx}  "
          f"({len(rojos)} en rojo, {len(amarillos)} en amarillo)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--fecha-fin", dest="fecha_fin", default=None,
                         help="Fuerza el fin del microciclo a evaluar (YYYY-MM-DD). "
                              "Default: último microciclo completo con datos reales.")
    parser.add_argument("--out", dest="out", default=None,
                         help="Ruta base de salida, sin extensión (se generan .pdf y .docx).")
    args = parser.parse_args()
    main(args.fecha_fin, args.out)
