# settings.py
from pathlib import Path

# ── Rutas ──────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent
DATA_DIR    = BASE_DIR / "data"
RAW_GPS     = DATA_DIR / "raw" / "gps"
RAW_WELL    = DATA_DIR / "raw" / "wellness"
PROCESSED   = DATA_DIR / "processed"
SYNTHETIC   = DATA_DIR / "synthetic"
LOGO_PATH   = BASE_DIR / "centro_escudo.jpeg"
FOTOS_DIR   = BASE_DIR / "assets" / "jugadoras"

# ── Google Sheets ETL ──────────────────────────────────────────────────────
WELLNESS_SHEET_ID  = "1OIRNNMMlN7eh5BND6Rw894diRoENkwwyq3Bz4pFmkmk"
WELLNESS_SHEET_GID = "2111167157"
ROSTER_SHEET_GID   = "989899898"   # pestaña "Plantel" — Jugadora / Posicion, misma planilla
SESIONES_SHEET_GID = "2000368568"  # pestaña "Sesiones" — Fecha / Match Day / Tipo_sesion / Rival
PARAMETROS_SHEET_GID = "640360409"  # pestaña "Parametros" — Match Day / Posicion / Metrica / Valor (rango esperado)
MD_EJERCICIOS_SHEET_GID = "1549489102"  # pestaña "MD_Ejercicios" — propuesta de ejercicios Físico/Técnico-Táctico por Match Day

# ── Identidad del Proyecto ─────────────────────────────────────────────────
PROJECT_NAME = "CN Hockey — Performance Hub"
TEAM_NAME    = "Primera División Femenina"

# ── Colores de acento por página ────────────────────────────────────────────
# Mismo color en la nav_card de la home (app.py) y en el page_header() de la
# página correspondiente — un solo lugar para cambiarlo en los dos.
PAGE_COLORS = {
    "carga_fisica": "#1A73E8",
    "wellness":     "#34A853",
    "fisico_tt":    "#F9AB00",
    "perfil":       "#A78BFA",
    "partidos":     "#EF5350",
    "analisis":     "#0EA5A5",
}

# ── Tipos de sesión GPS ─────────────────────────────────────────────────────
TIPOS_SESION = ["Físico", "Técnico-Táctico", "Partido"]
CUARTOS      = ["Q1", "Q2", "Q3", "Q4"]

# ── Umbrales ACWR (Hulin et al., 2016) ────────────────────────────────────
ACWR_OPTIMO_MIN = 0.8
ACWR_OPTIMO_MAX = 1.3
ACWR_ALERTA     = 1.5

# ── Parámetros EWMA ───────────────────────────────────────────────────────
EWMA_AGUDA_DIAS   = 7
EWMA_CRONICA_DIAS = 28

# ── Z-score histórico por jugadora ─────────────────────────────────────────
ZSCORE_MIN_SESIONES = 10   # piso de sesiones previas para que el desvío sea confiable
ZSCORE_ALERTA       = 2.0  # |z| >= esto marca una sesión como atípica

# ── Escalas Wellness ───────────────────────────────────────────────────────
TQR_MIN = 1
TQR_MAX = 10

# ── Análisis — FODA de entrenamientos (src/metrics/foda.py) ───────────────
MDS_ENTRENAMIENTO_FOCO = ["MD-5", "MD-4", "MD-2"]  # foco por defecto de pages/08_analisis.py
UMBRAL_CV_DURACION = 0.35      # coef. de variación (desvío/media) a partir del cual se avisa variabilidad alta
UMBRAL_CALIBRACION_PCT = 0.90  # % de sesiones fuera de rango en una sola dirección que hace sospechar del parámetro, no del entrenamiento
UMBRAL_MUESTRA_MINIMA_MD = 15  # sesiones GPS por debajo de esto -> aviso de muestra chica

# Paleta visual del dashboard (colores, CSS, layouts de Plotly) vive en
# src/ui/theme.py — no acá.