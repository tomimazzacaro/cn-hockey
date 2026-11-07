"""
Cambia el tema de fondo del dashboard reescribiendo .streamlit/config.toml.

    python scripts/aplicar_fondo.py            # lista los temas y dice cuál está activo
    python scripts/aplicar_fondo.py topo       # aplica "topo"
    python scripts/aplicar_fondo.py azul       # vuelve al azul oscuro de siempre

Después hay que REINICIAR Streamlit (Ctrl+C y `streamlit run app.py`): lee config.toml al arrancar.
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from src.ui.fondos import TEMAS, escribir_config, tema_para_fondo  # noqa: E402

CONFIG = RAIZ / ".streamlit" / "config.toml"


def _fondo_actual() -> str | None:
    import re
    m = re.search(r'(?m)^backgroundColor\s*=\s*"([^"]*)"', CONFIG.read_text(encoding="utf-8"))
    return m.group(1) if m else None


def main(argv: list[str]) -> int:
    activo = tema_para_fondo(_fondo_actual()).nombre
    if len(argv) != 2:
        print("Temas disponibles:")
        for nombre, t in TEMAS.items():
            marca = "  <- activo" if nombre == activo else ""
            print(f"  {nombre:11} página {t.pagina}  tarjetas {t.paradas[1]}{marca}")
        print("\nUso: python scripts/aplicar_fondo.py <tema>")
        return 0
    try:
        escribir_config(argv[1], CONFIG)
    except ValueError as e:
        print(f"Error: {e}")
        return 1
    print(f"Tema '{argv[1]}' aplicado en {CONFIG}. Reiniciá Streamlit (Ctrl+C y streamlit run app.py).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
