# src/ui/tipografia.py
"""
Tipografía de los títulos principales: UNA sola definición para los cuatro lugares donde aparecen
(título de página, nombre de la jugadora en Perfil, título del menú lateral y título del login).

Por defecto Bebas Neue en mayúsculas. Ojo con Bebas: existe en UN solo grosor (400); pedirle
`font-weight: 700` hace que el navegador invente una negrita falsa y deforme las letras, así que
todos sus estilos fijan 400. El `<h1>` de Streamlit trae su propio peso: el título de página lo
fuerza con !important.

Centrado: los títulos en mayúsculas llevan `letter-spacing`, que deja un hueco tras la última letra,
y se compensa con un `padding-left` igual. Además Streamlit agrega al final de cada <h1> un ícono de
enlace (24 px entre ancho y margen) que corría el texto 12 px a la izquierda: se oculta en theme.py.

Rollback al estilo anterior (Playfair Display cursiva): CN_FUENTE=playfair (ver settings.py).
La Presentación sigue usando Playfair por su cuenta, por eso siempre se cargan las dos fuentes.
"""
import settings

# Se cargan las dos: Bebas para los títulos y Playfair para la Presentación (y el rollback).
FUENTES_IMPORT_URL = ("https://fonts.googleapis.com/css2?family=Bebas+Neue"
                      "&family=Playfair+Display:ital,wght@1,600;1,700&display=swap")

SITIOS = ("pagina", "hero", "sidebar", "login")

_BEBAS = "font-family: 'Bebas Neue', sans-serif; font-style: normal; "
_PLAYFAIR = "font-family: 'Playfair Display', serif; font-style: italic; "

ESTILOS: dict[str, dict[str, str]] = {
    "bebas": {
        # !important: el <h1> de Streamlit trae su propia familia, peso y espaciado.
        "pagina": ("font-family: 'Bebas Neue', sans-serif !important; font-style: normal; "
                   "font-weight: 400 !important; font-size: 2.75rem; letter-spacing: 0.07em !important; "
                   # padding-left = letter-spacing: equilibra el hueco que el espaciado deja tras la última letra.
                   "padding-left: 0.07em !important; "
                   "text-transform: uppercase !important; line-height: 1.15;"),
        "hero": _BEBAS + ("font-weight: 400; font-size: 2.4rem; letter-spacing: 0.06em; "
                          "text-transform: uppercase; line-height: 1.1;"),
        "sidebar": _BEBAS + ("font-weight: 400; font-size: 1.6rem; letter-spacing: 0.06em; "
                             "padding-left: 0.06em; text-transform: uppercase; line-height: 1.15;"),
        "login": _BEBAS + ("font-weight: 400; font-size: 2.3rem; letter-spacing: 0.07em; "
                           "padding-left: 0.07em; text-transform: uppercase; line-height: 1.1;"),
    },
    # El estilo de antes, tal cual.
    "playfair": {
        "pagina": _PLAYFAIR + "font-size: 2.5rem; font-weight: 700; line-height: 1.2;",
        "hero": _PLAYFAIR + "font-weight: 700; font-size: 2rem; line-height: 1.15;",
        "sidebar": _PLAYFAIR + "font-size: 1.25rem; font-weight: 700;",
        "login": _PLAYFAIR + "font-size: 1.9rem; font-weight: 700;",
    },
}


def estilo_titulo(sitio: str, fuente: str | None = None) -> str:
    """
    Declaraciones CSS (sin llaves) del título de `sitio` ("pagina", "hero", "sidebar", "login").
    Sin `fuente` usa settings.FUENTE_TITULOS; una fuente desconocida cae a Bebas.
    """
    if fuente is None:
        fuente = settings.FUENTE_TITULOS
    return ESTILOS.get(fuente, ESTILOS["bebas"])[sitio]
