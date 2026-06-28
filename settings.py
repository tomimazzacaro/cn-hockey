# settings.py
from pathlib import Path

# ── Rutas ──────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent
DATA_DIR    = BASE_DIR / "data"
RAW_GPS     = DATA_DIR / "raw" / "gps"
RAW_WELL    = DATA_DIR / "raw" / "wellness"
PROCESSED   = DATA_DIR / "processed"
SYNTHETIC   = DATA_DIR / "synthetic"

# ── Google Sheets ETL ──────────────────────────────────────────────────────
WELLNESS_SHEET_ID  = "1OIRNNMMlN7eh5BND6Rw894diRoENkwwyq3Bz4pFmkmk"
WELLNESS_SHEET_GID = "2111167157"

# ── Identidad del Proyecto ─────────────────────────────────────────────────
PROJECT_NAME = "CN Hockey — Performance Hub"
TEAM_NAME    = "Primera División Femenina"

# ── Columnas canónicas GPS (mapeo interno) ─────────────────────────────────
GPS_COLS = {
    "player_id":        "player_id",
    "fecha":            "fecha",
    "distancia_total":  "distancia_total",    # metros
    "hsr":              "hsr",                # High Speed Running (m)
    "sprints":          "sprints",            # cantidad
    "aceleraciones":    "aceleraciones",
    "desaceleraciones": "desaceleraciones",
    "player_load":      "player_load",
    "duracion_min":     "duracion_min",       # minutos
}

# ── Columnas canónicas Wellness ────────────────────────────────────────────
WELLNESS_COLS = {
    "player_id": "player_id",
    "fecha":     "fecha",
    "tqr":       "tqr",       # Recuperación percibida (1–10)
    "rpe":       "rpe",       # Esfuerzo percibido (1–10)
    "sueño":     "sueño",     # Calidad de sueño (1–10)
    "estres":    "estres",    # Nivel de estrés (1–10)
    "humor":     "humor",     # Estado de ánimo (1–10)
    "fatiga":    "fatiga",    # Nivel de fatiga (1–10)
}

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
RPE_MIN = 1
RPE_MAX = 10

# ── Readiness Index (pesos por componente) ────────────────────────────────
READINESS_PESOS = {
    "tqr":     0.50,   # 50% — recuperación percibida
    "rpe_inv": 0.30,   # 30% — RPE invertido (mayor RPE = menor readiness)
    "wellness":0.20,   # 20% — promedio sueño + humor + fatiga invertida
}

# ── Colores del Dashboard ──────────────────────────────────────────────────
COLORS = {
    "primary":    "#1A73E8",
    "success":    "#34A853",
    "warning":    "#FBBC04",
    "danger":     "#EA4335",
    "neutral":    "#5F6368",
    "background": "#F8F9FA",
    "card":       "#FFFFFF",
    "sidebar":    "#1E1E2E",
}

# ── Semáforo ACWR ──────────────────────────────────────────────────────────
def color_acwr(valor: float) -> str:
    """Devuelve color semáforo según zona de riesgo ACWR."""
    if valor < ACWR_OPTIMO_MIN:
        return COLORS["warning"]     # subcarga
    elif valor <= ACWR_OPTIMO_MAX:
        return COLORS["success"]     # zona óptima
    elif valor <= ACWR_ALERTA:
        return COLORS["warning"]     # precaución
    else:
        return COLORS["danger"]      # riesgo alto

# ── Semáforo Readiness ─────────────────────────────────────────────────────
def color_readiness(valor: float) -> str:
    """Devuelve color semáforo según índice de readiness (0–10)."""
    if valor >= 7:
        return COLORS["success"]
    elif valor >= 5:
        return COLORS["warning"]
    else:
        return COLORS["danger"]