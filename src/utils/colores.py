# src/utils/colores.py
"""
Matemática de color pura (sin Streamlit): suavizado "pastel" de la paleta y las medidas que
usan los tests para comprobar que sigue siendo legible (contraste WCAG y distancia perceptual).
"""
import colorsys

# Luminosidad (HLS) hacia la que se empuja un color para volverlo pastel, y cuánto del camino
# se recorre con el nivel al máximo. Los colores más claros que esto no se oscurecen.
_LUMINOSIDAD_PASTEL = 0.74
_ALCANCE_LUMINOSIDAD = 0.55
_ALCANCE_SATURACION = 0.35


def _rgb(hex_color: str) -> tuple[float, float, float]:
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


def _hex(r: float, g: float, b: float) -> str:
    return "#%02X%02X%02X" % tuple(max(0, min(255, round(c * 255))) for c in (r, g, b))


def hls(hex_color: str) -> tuple[float, float, float]:
    """(tono, luminosidad, saturación), cada uno de 0 a 1."""
    return colorsys.rgb_to_hls(*_rgb(hex_color))


def suavizar(hex_color: str, nivel: float) -> str:
    """
    Versión más "pastel" de un color: conserva el tono, baja la saturación y sube la
    luminosidad. `nivel` va de 0 (el mismo color) a 1 (pastel completo); 0,5 es "suave".
    Nunca aumenta la saturación ni oscurece.
    """
    nivel = max(0.0, min(1.0, nivel))
    if nivel == 0:
        return hex_color          # idéntico, sin tocar ni las mayúsculas: rollback exacto
    h, luz, sat = hls(hex_color)
    sat2 = sat * (1 - _ALCANCE_SATURACION * nivel)
    luz2 = luz + max(0.0, _LUMINOSIDAD_PASTEL - luz) * _ALCANCE_LUMINOSIDAD * nivel
    return _hex(*colorsys.hls_to_rgb(h, luz2, sat2))


# ── Medidas para verificar legibilidad ───────────────────────────────────────

def _luminancia(hex_color: str) -> float:
    def lineal(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lineal(c) for c in _rgb(hex_color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contraste(color_a: str, color_b: str) -> float:
    """Relación de contraste WCAG entre dos colores (1 a 21). 4,5 es el mínimo para texto."""
    la, lb = sorted((_luminancia(color_a), _luminancia(color_b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _lab(hex_color: str) -> tuple[float, float, float]:
    def lineal(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lineal(c) for c in _rgb(hex_color))
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    return 116 * f(y) - 16, 500 * (f(x) - f(y)), 200 * (f(y) - f(z))


def distancia_color(color_a: str, color_b: str) -> float:
    """Distancia perceptual entre dos colores (ΔE 1976 en CIELAB). Más de ~40 se ve muy distinto."""
    la, lb = _lab(color_a), _lab(color_b)
    return sum((x - y) ** 2 for x, y in zip(la, lb)) ** 0.5
