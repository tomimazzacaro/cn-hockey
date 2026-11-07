# src/ui/fondos.py
"""
Temas de fondo del dashboard (azul oscuro de siempre, gris topo, grafito...). Datos puros más
una función que reescribe .streamlit/config.toml.

UNA SOLA FUENTE DE VERDAD: el tema activo es el que declara .streamlit/config.toml
(`backgroundColor` identifica al tema). Streamlit pinta con eso la página, la barra lateral y los
widgets nativos (campos, selectores, tablas); el resto (degradado de las tarjetas, fondo de los
gráficos, barras y chips del CSS) lo toma de acá, así no pueden contradecirse. Para cambiar de
tema: `python scripts/aplicar_fondo.py <nombre>` y reiniciar Streamlit. Si el fondo de
config.toml no corresponde a ningún tema, se usa el azul de siempre.

Los PDFs y la Presentación usan su propio azul y no dependen de esto.
"""
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Tema:
    nombre: str
    pagina: str                       # fondo de la página (identifica al tema)
    secundario: str                   # barra lateral y widgets nativos
    paradas: tuple[str, str, str]     # degradado de las tarjetas: inicio, medio, fin
    chart_bg: str                     # fondo de los gráficos
    chart_grid: str                   # grilla de los gráficos
    pista: str                        # barras de fondo, filas alternas de tablas
    chip: str                         # chips y botones sobre fondo
    enlace: tuple[int, int, int]      # RGB del botón "Home" (normal)
    enlace_hover: tuple[int, int, int]

    @property
    def degradado(self) -> str:
        a, b, c = self.paradas
        return f"linear-gradient(135deg, {a} 0%, {b} 60%, {c} 100%)"


TEMAS: dict[str, Tema] = {
    # El azul oscuro de siempre: valores EXACTOS de antes (rollback).
    "azul": Tema("azul", "#0a1628", "#0f2b5b", ("#0f2b5b", "#1a3a6b", "#1e4d8c"),
                 "#0d1b3e", "#1a2f5a", "#16294f", "#0f2b5b", (15, 43, 91), (26, 58, 107)),
    # Gris topo oscuro: se lee igual de bien que el azul (ver tests/test_fondos.py).
    "topo": Tema("topo", "#262324", "#302c2d", ("#302c2d", "#3c3839", "#4a4546"),
                 "#2b2728", "#403b3c", "#342f30", "#302c2d", (48, 44, 45), (60, 56, 57)),
    # Un poco más claro: los acentos pierden contraste (mínimo ~2,6 sobre la tarjeta).
    "topo_medio": Tema("topo_medio", "#2f2b2c", "#3a3637", ("#3a3637", "#4a4546", "#5a5455"),
                       "#353132", "#4b4647", "#3f3b3c", "#3a3637", (58, 54, 55), (74, 69, 70)),
    # Gris neutro, sin tono cálido.
    "grafito": Tema("grafito", "#222222", "#2a2a2a", ("#2a2a2a", "#3d3d3d", "#4b4b4b"),
                    "#262626", "#3a3a3a", "#303030", "#2a2a2a", (42, 42, 42), (61, 61, 61)),
}


def tema_para_fondo(color_fondo: str | None) -> Tema:
    """El tema cuyo fondo de página es `color_fondo` (sin importar mayúsculas); azul si no hay."""
    if color_fondo:
        for tema in TEMAS.values():
            if tema.pagina.lower() == color_fondo.strip().lower():
                return tema
    return TEMAS["azul"]


def tema_activo() -> Tema:
    """El tema que declara .streamlit/config.toml (lo lee Streamlit al arrancar)."""
    import streamlit as st
    return tema_para_fondo(st.get_option("theme.backgroundColor"))


def escribir_config(nombre: str, ruta: Path) -> None:
    """
    Reescribe en `ruta` (config.toml) SOLO `backgroundColor` y `secondaryBackgroundColor` con los
    del tema `nombre`; el resto del archivo, saltos de línea incluidos, queda byte a byte igual.

    Raises:
        ValueError: si el tema no existe o el archivo no tiene alguno de los dos colores
            (no se escribe nada en ese caso).
    """
    if nombre not in TEMAS:
        raise ValueError(f"Tema desconocido: {nombre!r}. Opciones: {', '.join(TEMAS)}")
    tema = TEMAS[nombre]
    texto = Path(ruta).read_bytes().decode("utf-8")
    for clave, valor in (("backgroundColor", tema.pagina), ("secondaryBackgroundColor", tema.secundario)):
        texto, n = re.subn(rf'(?m)^({clave}\s*=\s*)"[^"]*"', rf'\1"{valor}"', texto)
        if n != 1:
            raise ValueError(f"No encontré '{clave}' en {ruta}.")
    Path(ruta).write_bytes(texto.encode("utf-8"))
