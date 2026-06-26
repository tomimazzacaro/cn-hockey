# src/loaders/wellness_loader.py
"""
Loader para exports CSV de Google Forms — Carga Interna CN Hockey.
Form: Recuperación (TQR) + Esfuerzo (RPE) + Molestias físicas.
"""
import pandas as pd
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent.parent))
from settings import RAW_WELL, PROCESSED


# ── Mapeo columnas Form → canónicas ───────────────────────────────────────
COLUMN_MAP = {
    "Nombre completo": "nombre",
    "Fecha":           "fecha",
    "Recuperación":    "tqr",
    "Esfuerzo":        "rpe",
    "¿Tenés alguna molestia hoy? Indica dónde": "molestia",
}

# Columnas a descartar (vacías o redundantes)
COLS_DESCARTAR = ["Marca temporal", "Puntuación", "Columna 7"]


def _normalizar_nombre(nombre: str) -> str:
    """
    Normaliza el nombre completo para generar player_id consistente
    con el GPS loader.

    El form tiene formato 'APELLIDO NOMBRE' (ej: 'SOSA ANA')
    El GPS tiene formato 'NOMBRE APELLIDO' (ej: 'ANA SOSA')
    Ambos se convierten a minúsculas con guión bajo.

    Estrategia: usamos el nombre completo ordenado alfabéticamente
    por palabras → genera el mismo ID sin importar el orden.
    Ej: 'SOSA ANA' y 'ANA SOSA' → 'ana_sosa'
    """
    palabras = sorted(nombre.strip().upper().split())
    return "_".join(p.lower() for p in palabras)


def _parsear_fecha(fecha_str: str) -> pd.Timestamp:
    """
    Convierte string de fecha del form a datetime.
    Formato esperado: 'DD/M/YYYY' o 'DD/MM/YYYY'
    Ej: '24/6/2026' → Timestamp('2026-06-24')
    """
    return pd.to_datetime(fecha_str, dayfirst=True, errors="coerce")


def cargar_wellness(path_csv: str | Path) -> pd.DataFrame:
    """
    Carga el CSV de respuestas de Google Forms y lo normaliza.

    Args:
        path_csv: Ruta al CSV exportado de Google Sheets.

    Returns:
        DataFrame con esquema canónico listo para análisis.
    """
    path_csv = Path(path_csv)

    # 1 — Leer CSV crudo
    df = pd.read_csv(path_csv)

    # 2 — Descartar columnas vacías/irrelevantes
    cols_a_descartar = [c for c in COLS_DESCARTAR if c in df.columns]
    df = df.drop(columns=cols_a_descartar)

    # 3 — Renombrar al esquema canónico
    df = df.rename(columns=COLUMN_MAP)

    # 4 — Eliminar filas completamente vacías
    df = df.dropna(subset=["nombre", "fecha"]).reset_index(drop=True)

    # 5 — Parsear fecha
    df["fecha"] = df["fecha"].apply(_parsear_fecha).dt.date

    # 6 — Generar player_id normalizado
    df["player_id"] = df["nombre"].apply(_normalizar_nombre)

    # 7 — Limpiar columna molestia
    # Normalizar respuestas negativas escritas como texto ("no", "No", "NO", etc.)
    respuestas_negativas = ["no", "no.", "sin molestias", "nada", "ninguna",
                            "no, esta semana saf"]
    df["molestia"] = df["molestia"].fillna("Sin molestias")
    df["molestia"] = df["molestia"].apply(
        lambda x: "Sin molestias" if str(x).strip().lower() in respuestas_negativas else x
    )
    df["molestia_flag"] = df["molestia"] != "Sin molestias"

    # 7 — Resolver duplicados (misma jugadora, mismo día)
    # Estrategia: quedarse con el registro de mayor RPE (más informativo)
    n_antes = len(df)
    df = (df.sort_values("rpe", ascending=False)
            .drop_duplicates(subset=["player_id", "fecha"], keep="first")
            .sort_values(["fecha", "nombre"])
            .reset_index(drop=True))
    n_despues = len(df)
    if n_antes != n_despues:
        print(f"  ℹ️  Se resolvieron {n_antes - n_despues} registros duplicados (se conserva mayor RPE)")

    # 8 — Validar rangos TQR y RPE (1–10)
    for col in ["tqr", "rpe"]:
        fuera_rango = df[(df[col] < 1) | (df[col] > 10)]
        if len(fuera_rango) > 0:
            print(f"  ⚠️  {len(fuera_rango)} valores fuera de rango en '{col}'")
        df[col] = df[col].clip(1, 10)

    # 9 — Calcular sRPE (Session RPE = RPE × duración en minutos)
    # Por ahora lo dejamos como None hasta cruzar con GPS
    df["srpe"] = None

    # 10 — Ordenar columnas
    cols_orden = [
        "player_id", "nombre", "fecha",
        "tqr", "rpe", "srpe",
        "molestia", "molestia_flag",
    ]
    df = df[cols_orden]

    # 11 — Ordenar por fecha y nombre
    df = df.sort_values(["fecha", "nombre"]).reset_index(drop=True)

    return df


def guardar_procesado(df: pd.DataFrame,
                      nombre: str = "wellness_procesado.parquet") -> Path:
    """Guarda el DataFrame procesado en Parquet."""
    PROCESSED.mkdir(parents=True, exist_ok=True)
    destino = PROCESSED / nombre
    df.to_parquet(destino, index=False)
    print(f"💾 Guardado: {destino}")
    return destino


# ── Test rápido ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        ruta = sys.argv[1]
    else:
        print("Uso: python wellness_loader.py <ruta_al_csv>")
        sys.exit(1)

    df = cargar_wellness(ruta)

    print(f"\n✅ Wellness cargado: {len(df)} registros | "
          f"{df['player_id'].nunique()} jugadoras | "
          f"{df['molestia_flag'].sum()} con molestias\n")

    print(df[["nombre", "fecha", "tqr", "rpe", "molestia_flag"]].to_string(index=False))

    # Mostrar jugadoras con molestias
    molestias = df[df["molestia_flag"]][["nombre", "fecha", "molestia"]]
    if len(molestias) > 0:
        print(f"\n🚨 MOLESTIAS REGISTRADAS:")
        print(molestias.to_string(index=False))
    
    guardar_procesado(df)
    print("\n💾 Parquet guardado en data/processed/")