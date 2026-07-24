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

# ── Escalas Wellness ───────────────────────────────────────────────────────
TQR_MIN = 1
TQR_MAX = 10

# Paleta visual del dashboard (colores, CSS, layouts de Plotly) vive en
# src/ui/theme.py — no acá.