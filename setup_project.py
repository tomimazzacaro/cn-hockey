from pathlib import Path

BASE = Path(".")

carpetas = [
    "data/raw/gps",
    "data/raw/wellness",
    "data/processed",
    "data/synthetic",
    "src/loaders",
    "src/metrics",
    "src/utils",
    "pages",
]

archivos = [
    "src/loaders/__init__.py",
    "src/loaders/gps_loader.py",
    "src/loaders/wellness_loader.py",
    "src/metrics/__init__.py",
    "src/metrics/physical.py",
    "src/metrics/wellness.py",
    "src/utils/__init__.py",
    "src/utils/helpers.py",
    "pages/01_overview.py",
    "pages/02_carga_fisica.py",
    "pages/03_wellness.py",
    "app.py",
    "settings.py",
    "requirements.txt",
    "CLAUDE.md",
    ".gitignore",
]

for carpeta in carpetas:
    (BASE / carpeta).mkdir(parents=True, exist_ok=True)
    print(f"📁 {carpeta}")

for archivo in archivos:
    path = BASE / archivo
    path.touch()
    print(f"📄 {archivo}")

print("\n✅ Estructura creada correctamente.")