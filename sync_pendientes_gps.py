"""
sync_pendientes_gps.py
-----------------------
Detecta CSVs de Catapult/Openfield pendientes en la carpeta de Descargas de
Windows, interpreta fecha/tipo de sesión/cuarto a partir del nombre de
archivo, los copia a data/raw/gps/ (con la fecha normalizada a 2 dígitos) y
regenera data/processed/gps_procesado.parquet a partir de TODA la carpeta
data/raw/gps (viejos + nuevos) — nunca modifica ni borra un CSV existente.

Uso:
    python sync_pendientes_gps.py            # dry-run: solo muestra qué haría
    python sync_pendientes_gps.py --apply    # aplica los cambios de verdad

No hace commit/push — eso queda para un paso aparte, después de revisar
el resultado.
"""
import argparse
import re
import shutil
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent))
from settings import RAW_GPS, PROCESSED
from src.loaders.gps_loader import cargar_sesion_gps, guardar_procesado, extraer_fecha_de_nombre

import os

# En uso normal (Windows, corrido por Tomi) esto resuelve solo a su carpeta
# de Descargas real. GPS_DOWNLOADS_DIR permite pisarlo — se usa cuando este
# script corre dentro del sandbox de Cowork, donde esa carpeta está montada
# en otra ruta.
DOWNLOADS = Path(os.environ.get("GPS_DOWNLOADS_DIR", str(Path.home() / "Downloads")))


def interpretar_tipo(nombre: str):
    """(tipo_sesion, cuarto) a partir del nombre de archivo Catapult.

    Soporta las convenciones vistas hasta ahora:
      - ..._fisico.csv
      - ..._tecnico.csv / ..._tec-tac.csv / ..._tec-tactico[N].csv
      - ..._partido-qN.csv          (convención vieja)
      - ..._qN-vs-RIVAL.csv         -> Partido
      - ..._A-qN-vs-RIVAL.csv       -> Amistoso
    """
    n = nombre.lower()
    m = re.search(r"-a-q(\d)-vs-", n)
    if m:
        return "Amistoso", f"Q{m.group(1)}"
    m = re.search(r"-q(\d)-vs-", n)
    if m:
        return "Partido", f"Q{m.group(1)}"
    m = re.search(r"-partido-q(\d)", n)
    if m:
        return "Partido", f"Q{m.group(1)}"
    if "fisico" in n:
        return "Físico", "—"
    if "tec" in n:
        return "Técnico-Táctico", "—"
    return None, None


def normalizar_fecha_en_nombre(nombre: str) -> str:
    """Zero-pads día y mes en el nombre de archivo, deja el resto intacto."""
    def _pad(m):
        return f"{int(m.group(1)):02d}-{int(m.group(2)):02d}-{m.group(3)}"
    return re.sub(r"(\d{1,2})-(\d{1,2})-(\d{2})", _pad, nombre, count=1)


def main(apply: bool):
    ya_en_pipeline = {p.name for p in RAW_GPS.glob("*.csv")}
    candidatos = sorted(DOWNLOADS.glob("export_*.csv"))

    nuevos = []
    for csv in candidatos:
        try:
            fecha = extraer_fecha_de_nombre(csv.name)
        except ValueError:
            print(f"⚠️  Nombre no reconocido, salteado: {csv.name}")
            continue
        tipo, cuarto = interpretar_tipo(csv.name)
        if tipo is None:
            print(f"⚠️  No pude determinar el tipo de sesión de: {csv.name} — revisar a mano")
            continue
        nombre_normalizado = normalizar_fecha_en_nombre(csv.name)
        if nombre_normalizado in ya_en_pipeline:
            continue
        nuevos.append((csv, nombre_normalizado, fecha, tipo, cuarto))

    if not nuevos:
        print("No hay sesiones nuevas para procesar.")
        return

    print(f"\n{len(nuevos)} sesión/es nueva/s detectada/s:\n")
    for _, nombre, fecha, tipo, cuarto in nuevos:
        print(f"  {fecha.date()}  {tipo:16s} {cuarto:3s}  <- {nombre}")

    if not apply:
        print("\n(dry-run — no se copió ni procesó nada. Correr con --apply para aplicar de verdad.)")
        return

    RAW_GPS.mkdir(parents=True, exist_ok=True)
    for origen, nombre_normalizado, *_ in nuevos:
        shutil.copy2(origen, RAW_GPS / nombre_normalizado)

    import pandas as pd
    sesiones = []
    for archivo in sorted(RAW_GPS.glob("*.csv")):
        tipo, cuarto = interpretar_tipo(archivo.name)
        if tipo is None:
            print(f"⚠️  {archivo.name}: tipo no reconocido, salteado del merge")
            continue
        try:
            sesiones.append(cargar_sesion_gps(archivo, tipo, cuarto))
        except Exception as e:
            print(f"⚠️  {archivo.name}: ERROR — {e}")

    df_total = (pd.concat(sesiones, ignore_index=True)
                  .sort_values(["fecha", "nombre"])
                  .reset_index(drop=True))
    guardar_procesado(df_total)
    print(f"\n✅ {len(nuevos)} sesiones nuevas copiadas a data/raw/gps/")
    print(f"✅ Parquet regenerado: {len(df_total)} filas, {df_total['fecha'].nunique()} fechas distintas")
    print("\nRevisá el resultado. El commit + push queda pendiente de tu confirmación.")


def rebuild():
    """Regenera el parquet desde TODOS los CSV ya presentes en data/raw/gps/,
    sin pasar por la detección de 'pendientes' — útil después de corregir
    la interpretación de un archivo (tipo de sesión, etc.)."""
    import pandas as pd
    sesiones = []
    for archivo in sorted(RAW_GPS.glob("*.csv")):
        tipo, cuarto = interpretar_tipo(archivo.name)
        if tipo is None:
            print(f"⚠️  {archivo.name}: tipo no reconocido, salteado del merge")
            continue
        try:
            sesiones.append(cargar_sesion_gps(archivo, tipo, cuarto))
        except Exception as e:
            print(f"⚠️  {archivo.name}: ERROR — {e}")
    df_total = (pd.concat(sesiones, ignore_index=True)
                  .sort_values(["fecha", "nombre"])
                  .reset_index(drop=True))
    guardar_procesado(df_total)
    print(f"\n✅ Parquet reconstruido: {len(df_total)} filas, {df_total['fecha'].nunique()} fechas distintas")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--rebuild", action="store_true",
                         help="Regenera el parquet desde todo data/raw/gps/, sin detectar pendientes.")
    args = parser.parse_args()
    if args.rebuild:
        rebuild()
    else:
        main(apply=args.apply)
