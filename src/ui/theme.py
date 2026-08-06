# src/ui/theme.py
"""
Design system centralizado — CN Hockey Performance Hub.

Fuente única de colores, íconos y CSS. Antes de este módulo, cada página
bajo pages/ reimplementaba su propia paleta y sus propios bloques <style>;
esto unifica esos valores (sin cambiar ningún tono) para que un cambio de
color se haga en un solo lugar. Los layouts de Plotly viven en
src/ui/charts.py y los componentes HTML (tarjetas, tablas) en
src/ui/components.py — ambos importan la paleta desde acá.
"""
import streamlit as st

# ── Paleta base ─────────────────────────────────────────────────────────────
CARD_GRADIENT = "linear-gradient(135deg, #0f2b5b 0%, #1a3a6b 60%, #1e4d8c 100%)"

# Variante clara de CARD_GRADIENT, exclusiva de pages/07_presentacion.py (ver
# inject_presentacion_light_theme() más abajo) — mismo diagonal, tonos claros.
CARD_GRADIENT_LIGHT = "linear-gradient(135deg, #ffffff 0%, #f4f8fd 55%, #e9f0fb 100%)"

# Los PAGE_COLORS de settings.py (definidos para texto/acentos sobre el fondo
# navy del resto de la app) son demasiado pastel para usarse como color de
# TEXTO sobre blanco — #F9AB00 ámbar, #A78BFA violeta y #EF5350 rojo no llegan
# a contraste legible ahí. Esta versión oscurece cada tono lo justo para
# servir de texto+ícono+borde en pages/07_presentacion.py cuando pasa a tema
# claro, sin tocar PAGE_COLORS (que sigue siendo la paleta del tema oscuro
# del resto de la app). "carga_fisica" queda igual: #1A73E8 ya es el azul de
# link/texto que usa Google sobre blanco, no hace falta oscurecerlo.
PAGE_COLORS_LIGHT = {
    "carga_fisica": "#1A73E8",
    "wellness":     "#188038",
    "fisico_tt":    "#B45309",
    "perfil":       "#6D28D9",
    "partidos":     "#C62828",
}

CHART_BG   = "#0d1b3e"
CHART_GRID = "#1a2f5a"
CHART_FONT = "#e2e8f0"

LINE_PALETTE = ["#60a5fa", "#34d399", "#f472b6", "#fbbf24",
                "#a78bfa", "#38bdf8", "#fb923c", "#4ade80"]

COMPARE_COLOR_A = "#3987e5"   # azul — misma familia que el resto del dashboard
COMPARE_COLOR_B = "#199e70"   # verde azulado — validado contra el fondo oscuro (CVD ΔE 69.8)

# Paleta categórica para gráficos de barras agrupadas por identidad (ej: un
# color por partido). Validada con scripts/validate_palette.js del skill de
# dataviz contra el fondo real del dashboard (#0d1b3e, modo oscuro): banda de
# luminosidad OK, piso de croma OK, contraste OK, CVD ΔE mínimo 10.3 (banda
# 8–12 — por eso siempre va con leyenda + tooltip, nunca solo color).
BAR_CATEGORICAL_PALETTE = [
    "#3987e5",  # azul
    "#199e70",  # verde azulado
    "#c98500",  # mostaza
    "#008300",  # verde
    "#9085e9",  # violeta
    "#e66767",  # rojo
    "#d55181",  # magenta
    "#d95926",  # naranja
]

# ── Íconos SVG (línea fina, currentColor) ───────────────────────────────────
# Reemplazan los emojis (📊💚⚖️🎯🏆) en nav_card() y page_header(): un emoji
# se dibuja distinto en cada sistema operativo (Windows/Mac/Android), un SVG
# con stroke="currentColor" se ve idéntico en cualquier lado y hereda el color
# de acento de cada card, así el chip con tinte no compite con un ícono
# relleno de color plano encima.
_ICON_ATTRS = 'width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"'

ICONS = {
    "carga_fisica": f'''<svg {_ICON_ATTRS}>
        <rect x="3" y="12" width="4" height="8" rx="1"/>
        <rect x="10" y="7" width="4" height="13" rx="1"/>
        <rect x="17" y="3" width="4" height="17" rx="1"/>
    </svg>''',
    "wellness": f'''<svg {_ICON_ATTRS}>
        <path d="M12 21c-4.6-3-9-6.9-9-11.5A5 5 0 0 1 12 6a5 5 0 0 1 9 3.5C21 14.1 16.6 18 12 21z"/>
    </svg>''',
    "balance": f'''<svg {_ICON_ATTRS}>
        <line x1="12" y1="3" x2="12" y2="21"/>
        <line x1="5" y1="7" x2="19" y2="7"/>
        <path d="M5 7 2 13a3 3 0 0 0 6 0z"/>
        <path d="M19 7l-3 6a3 3 0 0 0 6 0z"/>
        <line x1="8" y1="21" x2="16" y2="21"/>
    </svg>''',
    "target": f'''<svg {_ICON_ATTRS}>
        <circle cx="12" cy="12" r="9"/>
        <circle cx="12" cy="12" r="5"/>
        <circle cx="12" cy="12" r="1.3" fill="currentColor" stroke="none"/>
    </svg>''',
    "trofeo": f'''<svg {_ICON_ATTRS}>
        <path d="M7 4h10v4a5 5 0 0 1-10 0z"/>
        <path d="M7 5H4.5A2.5 2.5 0 0 0 7 9.5"/>
        <path d="M17 5h2.5A2.5 2.5 0 0 1 17 9.5"/>
        <line x1="12" y1="13" x2="12" y2="17"/>
        <line x1="8.5" y1="20" x2="15.5" y2="20"/>
        <line x1="12" y1="17" x2="12" y2="20"/>
    </svg>''',
    # Grilla 2x2 — representa literalmente los 4 cuadrantes del FODA
    # (pages/08_analisis.py), no un ícono genérico de "gráfico".
    "analisis": f'''<svg {_ICON_ATTRS}>
        <rect x="3" y="3" width="8" height="8" rx="1.5"/>
        <rect x="13" y="3" width="8" height="8" rx="1.5"/>
        <rect x="3" y="13" width="8" height="8" rx="1.5"/>
        <rect x="13" y="13" width="8" height="8" rx="1.5"/>
    </svg>''',
}


# ── Zonas ACWR (semáforo de riesgo) ─────────────────────────────────────────
ZONE_CFG = {
    "Óptimo":      {"color": "#34A853", "bg": "#0a2e14"},
    "Precaución":  {"color": "#FBBC04", "bg": "#2e2200"},
    "Riesgo Alto": {"color": "#EA4335", "bg": "#2e0a08"},
    "Subcarga":    {"color": "#38bdf8", "bg": "#0c2a3a"},
    "Sin datos":   {"color": "#6b7280", "bg": "#1f2937"},
}

# ── Zonas Readiness ─────────────────────────────────────────────────────────
READINESS_CFG = {
    "Totalmente Apta": {"color": "#34A853", "bg": "#0a2e14", "icon": "✅"},
    "Apta Moderado":   {"color": "#8BC34A", "bg": "#1c2e0a", "icon": "🙂"},
    "Precaución":      {"color": "#FBBC04", "bg": "#2e2200", "icon": "⚠️"},
    "No Apta":         {"color": "#EA4335", "bg": "#2e0a08", "icon": "🚨"},
    "Sin datos":       {"color": "#6b7280", "bg": "#1f2937", "icon": "—"},
}

# ── Zonas Asistente de Parámetros ───────────────────────────────────────────
PARAMETRO_CFG = {
    "Por debajo": {"color": "#38bdf8", "bg": "#0c2a3a", "icon": "🔽"},
    "En rango":   {"color": "#34A853", "bg": "#0a2e14", "icon": "✅"},
    "Por encima": {"color": "#EA4335", "bg": "#2e0a08", "icon": "🔺"},
    "Sin dato":   {"color": "#6b7280", "bg": "#1f2937", "icon": "—"},
}


# ── CSS compartido ───────────────────────────────────────────────────────────

def inject_dashboard_css() -> None:
    """
    Inyecta el CSS compartido por todas las páginas: cards de navegación,
    grillas de KPI, tarjetas de comparación, tabla ACWR, tarjetas de
    readiness, filas de alerta/molestia. Llamar una vez por página.
    """
    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@1,600;1,700&display=swap');

    /* Cards de navegación clickeables (home) — ver nav_card() en components.py */
    div[class*="st-key-cn-navcard-"] {{
        background: {CARD_GRADIENT};
        border-radius: 14px;
        padding: 26px 20px 16px;
        text-align: center;
        box-shadow: 0 4px 20px rgba(0,0,0,0.35);
        transition: box-shadow 0.2s ease, transform 0.2s ease;
        min-height: 190px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
    }}
    div[class*="st-key-cn-navcard-"]:hover {{
        box-shadow: 0 12px 28px rgba(0,0,0,0.45);
        transform: translateY(-3px);
    }}
    div[class*="st-key-cn-navcard-"] [data-testid="stPageLink"] {{
        width: 100%;
    }}
    div[class*="st-key-cn-navcard-"] [data-testid="stPageLink"] a {{
        justify-content: center;
        text-decoration: none !important;
        white-space: normal !important;
        height: auto !important;
    }}
    div[class*="st-key-cn-navcard-"] [data-testid="stPageLink"] p {{
        color: #ffffff !important;
        font-size: 1.05rem;
        white-space: normal !important;
        overflow-wrap: break-word;
        text-align: center;
    }}
    div[class*="st-key-cn-navcard-"] [data-testid="stCaptionContainer"] {{
        color: #93c5fd !important;
        text-align: center;
        margin-top: 2px;
    }}

    /* Grilla de KPIs — ícono en chip con tinte del color de acento, borde
       superior a juego y hover; un solo componente para KPIs de equipo
       (Carga Física, Wellness) y de una jugadora individual (Perfil de
       Jugadora) — ver kpi_row() en components.py */
    .cn-kpi-grid {{
        display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
        gap: 14px; margin: 4px 0;
    }}
    .cn-kpi-card {{
        background: {CARD_GRADIENT};
        border-radius: 16px; padding: 18px 18px 16px;
        border-top: 3px solid var(--accent);
        border-left: 1px solid rgba(255,255,255,0.06);
        border-right: 1px solid rgba(255,255,255,0.06);
        border-bottom: 1px solid rgba(255,255,255,0.06);
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
        text-align: center;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }}
    .cn-kpi-card:hover {{
        transform: translateY(-2px);
        box-shadow: 0 10px 24px rgba(0,0,0,0.4);
    }}
    .cn-kpi-icon {{
        width: 38px; height: 38px; border-radius: 10px;
        display: flex; align-items: center; justify-content: center;
        background: color-mix(in srgb, var(--accent) 22%, transparent);
        font-size: 1.15rem; margin: 0 auto 12px;
    }}
    .cn-kpi-label {{
        font-size: 0.7rem; color: #93c5fd; text-transform: uppercase;
        letter-spacing: 0.05em; margin-bottom: 5px;
    }}
    .cn-kpi-value {{ font-size: 1.55rem; font-weight: 800; color: #fff; }}

    /* Tarjetas de comparación (jugadoras / tipos de sesión) */
    .cn-cmp-card {{
        border-radius: 14px;
        padding: 12px 12px 16px;
        text-align: center;
        background: {CARD_GRADIENT};
        border-top: 4px solid var(--accent);
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    }}
    .cn-cmp-avatar {{ font-size: 2.4rem; margin-bottom: 8px; }}
    .cn-cmp-avatar-foto {{
        width: 100%; max-width: 240px; aspect-ratio: 1 / 1; border-radius: 10px;
        object-fit: cover; display: block; margin: 0 auto 8px;
        border: 2px solid var(--accent);
    }}
    .cn-cmp-name   {{ font-size: 0.92rem; font-weight: 700; color: #fff;
                     text-transform: uppercase; letter-spacing: 0.02em; }}

    /* Cabecera "hero" de Perfil Jugadora — foto + nombre + posición + el
       selector real de Streamlit, unificados en una sola tarjeta (ver
       hero_foto_html()/hero_info_html() en components.py). El borde de
       acento y --accent se agregan inline en la página (mismo patrón que
       nav_card()), acá solo el fondo/forma compartidos. */
    div[class*="st-key-cn-perfil-hero"] {{
        background: {CARD_GRADIENT};
        border-radius: 18px;
        padding: 22px 28px 18px;
        box-shadow: 0 6px 20px rgba(0,0,0,0.35);
        margin-bottom: 6px;
    }}
    .cn-hero-foto {{
        width: 100%; max-width: 160px; aspect-ratio: 1 / 1; border-radius: 50%;
        object-fit: cover; display: block; margin: 0 auto;
        border: 3px solid var(--accent);
        box-shadow: 0 0 0 6px color-mix(in srgb, var(--accent) 18%, transparent);
    }}
    .cn-hero-foto-placeholder {{
        display: flex; align-items: center; justify-content: center;
        font-size: 3rem; background: #16294f;
    }}
    .cn-hero-name {{
        font-family: 'Playfair Display', serif; font-style: italic;
        font-weight: 700; font-size: 2rem; color: #fff; line-height: 1.15;
        margin-bottom: 8px;
    }}
    .cn-hero-posicion {{
        display: inline-block; border-radius: 20px; padding: 4px 14px;
        font-size: 0.75rem; font-weight: 700; text-transform: uppercase;
        letter-spacing: 0.05em; color: var(--accent);
        background: color-mix(in srgb, var(--accent) 20%, transparent);
        border: 1px solid color-mix(in srgb, var(--accent) 45%, transparent);
        margin-bottom: 12px;
    }}

    /* Filas de barras comparativas (jugadora A vs B, tipo A vs B) */
    .cn-cmp-row {{ display: flex; align-items: center; gap: 8px; margin-bottom: 14px; }}
    .cn-cmp-value {{ width: 72px; font-size: 0.82rem; font-weight: 700; color: {CHART_FONT}; }}
    .cn-cmp-value-a {{ text-align: right; }}
    .cn-cmp-value-b {{ text-align: left; }}
    .cn-cmp-label  {{
        width: 130px; flex-shrink: 0; text-align: center;
        font-size: 0.74rem; color: #93c5fd; text-transform: uppercase;
        letter-spacing: 0.04em;
    }}
    .cn-cmp-bar-a, .cn-cmp-bar-b {{
        flex: 1; display: flex; height: 12px;
        background: #16294f; border-radius: 6px;
    }}
    .cn-cmp-bar-a {{ justify-content: flex-end; }}
    .cn-cmp-bar-b {{ justify-content: flex-start; }}
    .cn-cmp-fill-a, .cn-cmp-fill-b {{ height: 100%; }}
    .cn-cmp-fill-a {{ background: var(--color-a); border-radius: 4px 0 0 4px; }}
    .cn-cmp-fill-b {{ background: var(--color-b); border-radius: 0 4px 4px 0; }}

    /* Análisis del Asistente — chips de fortalezas + grilla de tarjetas de
       debilidad (ver analisis_asistente_html() en components.py) */
    .cn-analisis-fortalezas {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 16px; }}
    .cn-analisis-grid {{
        display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
        gap: 14px; margin: 4px 0;
    }}
    .cn-analisis-card {{
        background: {CARD_GRADIENT};
        border-radius: 14px; padding: 14px 16px 12px;
        border-top: 4px solid var(--accent);
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    }}
    .cn-analisis-nombre {{ font-weight: 700; color: #fff; font-size: 0.92rem; }}
    .cn-analisis-posicion {{
        font-size: 0.72rem; color: #93c5fd; text-transform: uppercase;
        letter-spacing: 0.04em; margin-bottom: 10px;
    }}
    .cn-analisis-badges {{ display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; }}
    .cn-analisis-reco {{ font-size: 0.78rem; color: #cbd5e1; line-height: 1.5; margin: 4px 0 0; }}

    /* Tabla ACWR */
    .cn-acwr-table {{ width:100%; border-collapse:collapse; }}
    .cn-acwr-table th {{ font-size:0.72rem; color:#93c5fd; text-transform:uppercase;
                        letter-spacing:0.05em; padding:8px 12px; text-align:left;
                        border-bottom:1px solid {CHART_GRID}; }}
    .cn-acwr-table td {{ padding:9px 12px; font-size:0.88rem; color:{CHART_FONT};
                        border-bottom:1px solid #0f2040; }}
    .cn-acwr-badge {{ border-radius:20px; padding:3px 12px; font-size:0.75rem;
                     font-weight:700; display:inline-block; }}

    /* Caption debajo de la tabla del Asistente de Parámetros — centrado
       igual que la leyenda de colores de arriba (ver render_asistente() en
       asistente.py, tabla_asistente_html() en components.py), compartido
       por las 4 páginas de fitting. st.caption() trae su propio text-align
       explícito de fábrica (no hereda del contenedor), por eso hay que
       pisarlo con !important apuntando directo a stCaptionContainer, no
       alcanza con centrar el div del container que lo envuelve. */
    div[class*="st-key-cn-asistente-caption"] [data-testid="stCaptionContainer"] {{
        text-align: center !important;
    }}

    /* Leyenda simple del Ratio A:C (ver acwr_leyenda_html() en
       components.py) — reemplaza la explicación técnica de antes por una
       frase corta + 3 zonas de color, para que se entienda de un vistazo
       en la presentación a las jugadoras. */
    .cn-acwr-leyenda {{ margin: 10px 0 4px; }}
    .cn-acwr-leyenda-intro {{
        font-size: 0.85rem; color: #cbd5e1; line-height: 1.5; margin: 0 0 14px;
    }}
    .cn-acwr-leyenda-zonas {{ display: flex; flex-wrap: wrap; gap: 22px; }}
    .cn-acwr-leyenda-item {{
        display: flex; align-items: flex-start; gap: 8px;
        flex: 1; min-width: 220px;
    }}
    .cn-acwr-leyenda-dot {{
        width: 10px; height: 10px; border-radius: 50%;
        margin-top: 5px; flex-shrink: 0;
    }}
    .cn-acwr-leyenda-texto {{ display: flex; flex-direction: column; }}
    .cn-acwr-leyenda-label {{ font-size: 0.84rem; font-weight: 700; }}
    .cn-acwr-leyenda-rango {{ font-weight: 500; opacity: 0.8; }}
    .cn-acwr-leyenda-desc {{ font-size: 0.78rem; color: #93c5fd; margin-top: 1px; }}

    /* Encabezado de página compartido — ver page_header() en components.py.
       Ícono arriba del título, apilados en columna y centrados — así el
       ícono siempre queda justo encima del título sin importar cuánto mida. */
    .cn-page-header {{
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 10px;
        margin: 6px 0 4px;
    }}
    .cn-page-header-icon {{
        width: 56px; height: 56px; border-radius: 14px; flex-shrink: 0;
        display: flex; align-items: center; justify-content: center;
        font-size: 1.8rem; color: var(--accent);
        background: color-mix(in srgb, var(--accent) 22%, transparent);
        border: 1px solid color-mix(in srgb, var(--accent) 45%, transparent);
    }}
    .cn-page-header-text {{ text-align: center; }}
    .cn-page-header-title {{
        font-family: 'Playfair Display', serif;
        font-style: italic; font-size: 2.5rem; font-weight: 700; color: #fff;
        margin: 0; line-height: 1.2;
    }}
    .cn-page-header-subtitle {{
        font-size: 0.85rem; color: #93c5fd; font-style: italic; margin: 4px 0 0;
    }}

    /* Título de sección chico — ver section_title() en components.py. Barra
       de acento + ícono opcional + texto, más liviano que .cn-page-header
       para anteceder un grupo de tarjetas sin competir con los
       st.subheader() grandes de la página. */
    .cn-section-title {{
        display: flex; align-items: center; gap: 10px;
        margin: 4px 0 14px;
    }}
    .cn-section-title-bar {{
        width: 4px; height: 20px; border-radius: 2px;
        background: var(--accent); flex-shrink: 0;
    }}
    .cn-section-title-icon {{
        display: flex; color: var(--accent); flex-shrink: 0;
    }}
    .cn-section-title-icon svg {{ width: 18px; height: 18px; }}
    .cn-section-title-text {{
        font-size: 0.85rem; font-weight: 700; color: #cbd5e1;
        text-transform: uppercase; letter-spacing: 0.1em;
    }}

    /* Título "hero" exclusivo de pages/07_presentacion.py (ver
       presentacion_title() en components.py) — degradado animado que
       recorre los mismos 5 colores de PAGE_COLORS que ya usa cada página,
       pasado por --title-gradient inline. A propósito NO se toca
       .cn-page-header-title de arriba: ese lo comparten las otras 6
       páginas y este efecto es sólo para la portada de la charla. */
    .cn-presentacion-title {{
        font-family: 'Playfair Display', serif;
        font-style: italic; font-weight: 700; font-size: 2.7rem;
        text-align: center; margin: 0; line-height: 1.25;
        background: var(--title-gradient);
        background-size: 200% auto;
        -webkit-background-clip: text; background-clip: text;
        -webkit-text-fill-color: transparent; color: transparent;
        animation: cn-title-shimmer 7s ease-in-out infinite;
    }}
    @keyframes cn-title-shimmer {{
        0%   {{ background-position: 0% center; }}
        50%  {{ background-position: 100% center; }}
        100% {{ background-position: 0% center; }}
    }}

    /* Tarjeta que envuelve el título hero de pages/07_presentacion.py — un
       borde con el mismo degradado animado del texto, logrado con dos
       pseudo-elementos apilados (truco estándar de "gradient border"):
       ::before pinta el degradado completo un par de px más grande que la
       tarjeta, ::after tapa el centro con el fondo real, dejando solo un
       anillo de color visible alrededor. isolation:isolate + z-index
       negativo evita que los pseudo-elementos se cuelen por encima del
       contenido real. */
    .cn-presentacion-hero {{
        position: relative;
        border-radius: 24px;
        padding: 36px 44px 30px;
        margin: 8px 0 26px;
        background: {CARD_GRADIENT};
        box-shadow: 0 10px 40px rgba(0,0,0,0.45);
        isolation: isolate;
    }}
    .cn-presentacion-hero::before {{
        content: "";
        position: absolute; inset: -3px;
        border-radius: 27px;
        background: var(--title-gradient);
        background-size: 300% 300%;
        z-index: -2;
        animation: cn-title-shimmer 7s ease-in-out infinite;
    }}
    .cn-presentacion-hero::after {{
        content: "";
        position: absolute; inset: 2px;
        border-radius: 22px;
        background: {CARD_GRADIENT};
        z-index: -1;
    }}

    /* Slide 1 — "los 3 pilares del cuidado" (ver slide_pilares_html() en
       components.py). Layout propio dentro del mismo marco .cn-slide-card
       que usa el resto del deck, porque esta slide no entra en el molde
       ícono+título+cuerpo de slide_html(). */
    .cn-pilar-headline {{
        font-family: 'Playfair Display', serif;
        font-style: italic; font-weight: 700; font-size: 2.4rem;
        text-align: center; margin: 0 0 10px; line-height: 1.2;
    }}
    .cn-pilar-lead {{
        font-size: 1.15rem; color: #e2e8f0; text-align: center;
        max-width: 820px; margin: 0 auto 6px; line-height: 1.6;
    }}
    .cn-pilar-grid {{
        display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        gap: 18px; width: 100%; margin: 24px 0 12px;
    }}
    .cn-pilar-card {{
        background: {CARD_GRADIENT};
        border-radius: 16px; padding: 22px 20px 20px;
        border-top: 4px solid var(--accent);
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
        text-align: center;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }}
    .cn-pilar-card:hover {{
        transform: translateY(-6px);
        box-shadow: 0 18px 34px rgba(0,0,0,0.5),
                    0 0 0 1px color-mix(in srgb, var(--accent) 40%, transparent);
    }}
    .cn-pilar-label {{
        font-family: 'Playfair Display', serif;
        font-style: italic; font-weight: 700; font-size: 1.05rem;
        color: var(--accent); margin-bottom: 6px;
        word-break: keep-all; overflow-wrap: normal;
    }}
    .cn-pilar-subtitle {{
        font-size: 0.72rem; color: #93c5fd; text-transform: uppercase;
        letter-spacing: 0.06em; margin-bottom: 12px;
    }}
    .cn-pilar-body {{ font-size: 0.98rem; color: #e2e8f0; line-height: 1.55; margin: 0; }}
    .cn-pilar-list {{
        text-align: left; margin: 0; padding-left: 1.2em;
    }}
    .cn-pilar-list li {{
        font-size: 0.94rem; color: #e2e8f0; line-height: 1.5; margin-bottom: 6px;
    }}
    .cn-pilar-footer {{
        font-size: 1rem; color: #93c5fd; font-style: italic;
        margin-top: 20px; text-align: center;
    }}

    /* Alertas activas — grilla de tarjetas (ver alertas_cards_html() en
       components.py), mismo lenguaje visual que Análisis/Molestias */
    .cn-alerta-grid {{
        display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        gap: 14px; margin: 4px 0;
    }}
    .cn-alerta-card {{
        background: {CARD_GRADIENT};
        border-radius: 14px; padding: 14px 16px 12px;
        border-top: 4px solid var(--accent);
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    }}
    .cn-alerta-nombre {{ font-weight: 700; color: #fff; font-size: 0.92rem; }}
    .cn-alerta-fecha {{
        font-size: 0.72rem; color: #93c5fd; text-transform: uppercase;
        letter-spacing: 0.04em; margin-bottom: 10px;
    }}
    .cn-alerta-badges {{ display: flex; flex-wrap: wrap; gap: 6px; }}

    /* Molestias — grilla de tarjetas (ver molestias_cards_html() en
       components.py), mismo lenguaje visual que las tarjetas de Análisis */
    .cn-molestia-grid {{
        display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        gap: 14px; margin: 4px 0;
    }}
    .cn-molestia-card {{
        background: {CARD_GRADIENT};
        border-radius: 14px; padding: 14px 16px 12px;
        border-top: 4px solid #FBBC04;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    }}
    .cn-molestia-nombre {{ font-weight: 700; color: #fff; font-size: 0.92rem; }}
    .cn-molestia-fecha {{
        font-size: 0.72rem; color: #93c5fd; text-transform: uppercase;
        letter-spacing: 0.04em; margin-bottom: 10px;
    }}
    .cn-molestia-detalle {{ font-size: 0.82rem; color: #fde68a; line-height: 1.5; }}

    /* Tarjetas de "Expectativa de periodización" (ver periodizacion_cards_html()
       en components.py, pages/08_analisis.py) — SIEMPRE visibles arriba del
       FODA, no en un expander plegado: es el contexto de lectura para el
       resto de la sección, no un detalle opcional. A diferencia de
       .cn-foda-card (un solo bloque de HTML), acá cada tarjeta es un
       st.container(key=...) real — necesario porque adentro va un
       st.popover real (widget de Streamlit, no se puede meter en un string
       de HTML) con la propuesta de ejercicios de ese Match Day. El color de
       borde por tarjeta se inyecta con un bloque de estilo puntual por key
       (mismo truco que nav_card()), no con var(--accent) acá. Ojo: nunca
       escribir la etiqueta HTML de estilo entre ángulos dentro de un
       comentario de ESTE bloque — el navegador la toma como cierre del
       bloque exterior real y el resto del CSS queda como texto plano en
       la página. */
    div[class*="st-key-cn-periodizacion-"] {{
        background: {CARD_GRADIENT};
        border-radius: 14px; padding: 16px 18px 14px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
        margin-bottom: 14px;
        height: 100%; box-sizing: border-box;
    }}
    /* Las 3 columnas de periodización quedan a distinta altura por
       default — cada tarjeta st.container() solo ocupa lo que necesita su
       propio texto, Streamlit no las estira parejo entre sí. Se fuerza
       height:100% en toda la cadena de wrappers intermedios (stColumn ->
       stVerticalBlock -> stLayoutWrapper -> nuestra tarjeta) SOLO dentro de
       la fila que contiene estas tarjetas (:has(), no todo el resto de la
       app que también usa st.columns) para que las 3 terminen con el mismo
       alto que la más alta. */
    div[data-testid="stHorizontalBlock"]:has([class*="st-key-cn-periodizacion-"]) {{
        align-items: stretch !important;
    }}
    /* Cadena de wrappers EXACTA entre la columna y nuestra tarjeta (stColumn
       > div > stLayoutWrapper > tarjeta) — con combinador directo ">" en vez
       de descendiente, a propósito: si se usara un selector "en cualquier
       profundidad" para stLayoutWrapper, también agarraría los wrappers que
       Streamlit mete DENTRO de la tarjeta (uno para el texto, otro para el
       popover) y los estiraría a los dos por igual, rompiendo el anclaje del
       botón al fondo que se arma más abajo. */
    div[data-testid="stHorizontalBlock"]:has([class*="st-key-cn-periodizacion-"])
    > [data-testid="stColumn"] {{
        align-self: stretch !important;
        height: auto !important;
        display: flex !important;
        flex-direction: column !important;
    }}
    div[data-testid="stHorizontalBlock"]:has([class*="st-key-cn-periodizacion-"])
    > [data-testid="stColumn"] > div,
    div[data-testid="stHorizontalBlock"]:has([class*="st-key-cn-periodizacion-"])
    > [data-testid="stColumn"] > div > [data-testid="stLayoutWrapper"] {{
        height: 100% !important;
        flex: 1 !important;
        display: flex !important;
        flex-direction: column !important;
    }}
    /* Con la tarjeta ya a la altura pareja, el botón "Ver propuesta de
       ejercicios" (adentro de su propio stLayoutWrapper, hermano del que
       envuelve el texto) queda pegado al texto en vez de anclado al fondo —
       margin-top:auto lo empuja hasta abajo del todo, así el botón queda a
       la misma altura en las 3 tarjetas sin importar cuántas líneas ocupe
       el texto de cada una. */
    div[class*="st-key-cn-periodizacion-"] > [data-testid="stLayoutWrapper"]:has([data-testid="stPopover"]) {{
        margin-top: auto !important;
    }}
    .cn-periodizacion-md {{
        display: block; width: fit-content; margin: 0 auto 14px;
        font-weight: 800; font-size: 0.95rem; letter-spacing: 0.08em;
        text-transform: uppercase; color: var(--accent);
        background: color-mix(in srgb, var(--accent) 22%, transparent);
        border: 1px solid color-mix(in srgb, var(--accent) 45%, transparent);
        border-radius: 20px; padding: 6px 22px;
        box-shadow: 0 2px 10px color-mix(in srgb, var(--accent) 30%, transparent);
    }}
    .cn-periodizacion-lista {{ margin: 0; padding-left: 1.1em; }}
    .cn-periodizacion-lista li {{
        font-size: 0.86rem; color: #cbd5e1; line-height: 1.6; margin-bottom: 6px;
    }}
    .cn-periodizacion-lista li:last-child {{ margin-bottom: 0; }}

    /* Grilla FODA — 4 cuadrantes fijos (ver foda_quadrant_html() en
       components.py, pages/08_analisis.py). A propósito 2 columnas fijas
       (no auto-fit como el resto de las grillas de tarjetas): un FODA
       "se lee" como cuadrantes, no como una lista que se reordena según el
       ancho de pantalla. */
    .cn-foda-grid {{
        display: grid; grid-template-columns: repeat(2, 1fr);
        gap: 14px; margin: 4px 0;
    }}
    .cn-foda-card {{
        background: {CARD_GRADIENT};
        border-radius: 14px; padding: 16px 18px 14px;
        border-top: 4px solid var(--accent);
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    }}
    .cn-foda-titulo {{
        font-weight: 700; color: #fff; font-size: 0.98rem;
        margin-bottom: 10px;
    }}
    .cn-foda-lista {{ margin: 0; padding-left: 1.1em; }}
    .cn-foda-lista li {{
        font-size: 0.85rem; color: #cbd5e1; line-height: 1.55; margin-bottom: 6px;
    }}
    .cn-foda-vacio {{ font-size: 0.82rem; color: #6b7280; font-style: italic; }}
    @media (max-width: 900px) {{
        .cn-foda-grid {{ grid-template-columns: 1fr; }}
    }}

    /* Slides de la Presentación institucional (ver slide_html() en
       components.py, pages/07_presentacion.py) — tarjeta única grande,
       pensada para proyectarse durante una charla en vivo: por eso el
       cuerpo va en fuente más grande que el resto del dashboard. */
    .cn-slide-card {{
        background: {CARD_GRADIENT};
        border-radius: 20px;
        padding: 48px 56px;
        margin: 12px 0 20px;
        border-top: 5px solid var(--accent);
        box-shadow: 0 8px 30px rgba(0,0,0,0.4);
        min-height: 340px;
        display: flex;
        flex-direction: column;
        align-items: center;
        text-align: center;
    }}
    .cn-slide-icon {{
        width: 72px; height: 72px; border-radius: 18px;
        display: flex; align-items: center; justify-content: center;
        font-size: 2.4rem; color: var(--accent);
        background: color-mix(in srgb, var(--accent) 22%, transparent);
        border: 1px solid color-mix(in srgb, var(--accent) 45%, transparent);
        margin-bottom: 18px;
    }}
    .cn-slide-eyebrow {{
        font-size: 0.8rem; color: #93c5fd; text-transform: uppercase;
        letter-spacing: 0.08em; margin-bottom: 8px;
    }}
    .cn-slide-title {{
        font-family: 'Playfair Display', serif;
        font-style: italic; font-size: 2.1rem; font-weight: 700; color: #fff;
        margin: 0 0 20px; line-height: 1.25;
    }}
    .cn-slide-body p {{
        font-size: 1.25rem; color: #e2e8f0; line-height: 1.7;
        max-width: 780px; margin: 0 auto 14px;
    }}

    /* Saca "Presentación" y "Análisis" de la lista automática de páginas que
       Streamlit arma arriba del todo del sidebar (antes de cualquier
       contenido propio, ver _render_sidebar() en src/utils/auth.py) — esas
       dos páginas se repintan a mano DEBAJO del escudo (mismo archivo) para
       quedar separadas del resto como un bloque "institucional" aparte.
       :has() en vez de ocultar el <a> suelto: así se esconde toda la fila
       (<li>), no deja un espacio en blanco clickeable vacío. */
    [data-testid="stSidebarNavItems"] li:has(a[href$="/presentacion"]),
    [data-testid="stSidebarNavItems"] li:has(a[href$="/analisis"]) {{
        display: none;
    }}

    /* Link "Home" arriba a la derecha (ver home_button() en components.py) */
    div[class*="st-key-cn-home-link"] [data-testid="stPageLink"] a {{
        background: rgba(15,43,91,0.55);
        border: 1px solid rgba(147,197,253,0.25);
        border-radius: 20px;
        padding: 2px 12px;
        justify-content: center;
        text-decoration: none !important;
    }}
    div[class*="st-key-cn-home-link"] [data-testid="stPageLink"] a:hover {{
        background: rgba(26,58,107,0.85);
    }}
    div[class*="st-key-cn-home-link"] [data-testid="stPageLink"] p {{
        color: #93c5fd !important;
        font-size: 0.8rem;
        white-space: nowrap;
    }}
    </style>
    """, unsafe_allow_html=True)


def inject_presentacion_light_theme() -> None:
    """
    Override de tema claro EXCLUSIVO de pages/07_presentacion.py — llamar
    justo después de inject_dashboard_css() en esa página únicamente (nunca
    en las otras 6). Cada `st.markdown(unsafe_allow_html=True)` inyecta su
    `<style>` en el árbol DOM de la página actual; al navegar a otra página
    Streamlit tira abajo ese árbol y lo reconstruye desde cero, así que este
    bloque nunca llega a existir en el DOM de las demás páginas — no hace
    falta un selector "de más" para evitar que se filtre.

    Repinta a claro el fondo del área principal y las tarjetas/textos
    propios de esta página (.cn-presentacion-hero/.cn-slide-card/.cn-pilar-*).
    Los ACENTOS de color (headline_color, color de cada tarjeta, el
    degradado del título) NO se tocan acá — esos van inline (`style=...`)
    desde pages/07_presentacion.py vía PAGE_COLORS_LIGHT, porque ninguna
    regla de CSS externa le gana la especificidad a un estilo inline.
    """
    st.markdown(f"""
    <style>
    [data-testid="stMain"] {{
        background: linear-gradient(180deg, #eef3fb 0%, #f7f9fc 100%);
    }}
    .cn-presentacion-hero, .cn-presentacion-hero::after,
    .cn-slide-card, .cn-pilar-card {{
        background: {CARD_GRADIENT_LIGHT};
    }}
    .cn-presentacion-hero {{ box-shadow: 0 10px 30px rgba(30,41,59,0.14); }}
    .cn-slide-card {{ box-shadow: 0 8px 24px rgba(30,41,59,0.12); }}
    .cn-pilar-card {{ box-shadow: 0 4px 14px rgba(30,41,59,0.10); }}
    .cn-pilar-card:hover {{
        box-shadow: 0 16px 28px rgba(30,41,59,0.18),
                    0 0 0 1px color-mix(in srgb, var(--accent) 45%, transparent);
    }}
    .cn-page-header-subtitle, .cn-pilar-lead, .cn-pilar-subtitle,
    .cn-slide-eyebrow, .cn-pilar-footer {{ color: #3b5b8c; }}
    .cn-pilar-body, .cn-pilar-list li, .cn-slide-body p {{ color: #334155; }}
    .cn-slide-title {{ color: #1e293b; }}
    [data-testid="stMain"] button {{
        background: #ffffff; color: #1e293b; border: 1px solid #cbd5e1;
    }}
    [data-testid="stMain"] button:hover {{
        background: #f1f5f9; border-color: #94a3b8; color: #1e293b;
    }}
    [data-testid="stMain"] button:disabled {{
        background: #f8fafc; color: #94a3b8; border-color: #e2e8f0;
    }}
    [data-testid="stMain"] [data-testid="stPageLink"] a p {{ color: #1557b0 !important; }}
    [data-testid="stMain"] hr {{ border-color: #dbe4f0; }}
    </style>
    """, unsafe_allow_html=True)
