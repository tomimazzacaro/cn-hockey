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

    /* Grilla de KPIs */
    .cn-kpi-grid {{ display:flex; justify-content:center; gap:10px; flex-wrap:wrap; margin-bottom:4px; }}
    .cn-kpi-card {{
        background: {CARD_GRADIENT};
        border-radius:14px; padding:14px 12px 12px; text-align:center;
        width:150px; box-shadow:0 4px 15px rgba(0,0,0,0.3);
    }}
    .cn-kpi-card .lbl {{ font-size:0.72rem; color:#93c5fd; text-transform:uppercase;
                        letter-spacing:0.05em; margin-bottom:5px; overflow-wrap:break-word; }}
    .cn-kpi-card .val {{ font-size:1.55rem; font-weight:800; color:#fff; }}

    /* Tarjetas KPI de jugadora (perfil individual) — chip de ícono con
       tinte del color de acento, borde superior a juego */
    .cn-player-kpi-grid {{
        display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
        gap: 14px; margin: 28px 0 4px;
    }}
    .cn-player-kpi-card {{
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
    .cn-player-kpi-card:hover {{
        transform: translateY(-2px);
        box-shadow: 0 10px 24px rgba(0,0,0,0.4);
    }}
    .cn-player-kpi-icon {{
        width: 38px; height: 38px; border-radius: 10px;
        display: flex; align-items: center; justify-content: center;
        background: color-mix(in srgb, var(--accent) 22%, transparent);
        font-size: 1.15rem; margin: 0 auto 12px;
    }}
    .cn-player-kpi-label {{
        font-size: 0.7rem; color: #93c5fd; text-transform: uppercase;
        letter-spacing: 0.05em; margin-bottom: 5px;
    }}
    .cn-player-kpi-value {{ font-size: 1.55rem; font-weight: 800; color: #fff; }}

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

    /* Tabla ACWR */
    .cn-acwr-table {{ width:100%; border-collapse:collapse; }}
    .cn-acwr-table th {{ font-size:0.72rem; color:#93c5fd; text-transform:uppercase;
                        letter-spacing:0.05em; padding:8px 12px; text-align:left;
                        border-bottom:1px solid {CHART_GRID}; }}
    .cn-acwr-table td {{ padding:9px 12px; font-size:0.88rem; color:{CHART_FONT};
                        border-bottom:1px solid #0f2040; }}
    .cn-acwr-badge {{ border-radius:20px; padding:3px 12px; font-size:0.75rem;
                     font-weight:700; display:inline-block; }}

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

    /* Tarjetas de readiness individual */
    .cn-readiness-grid {{
        display: flex; flex-wrap: wrap; gap: 14px;
        justify-content: center; margin: 8px 0 16px;
    }}
    .cn-readiness-card {{
        border-radius: 14px; padding: 18px 22px; text-align: center;
        min-width: 148px; max-width: 172px; flex: 1 1 148px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
        border: 1px solid rgba(255,255,255,0.08);
    }}
    .cn-readiness-card .rc-icon  {{ font-size: 1.5rem; margin-bottom: 4px; }}
    .cn-readiness-card .rc-name  {{ font-size: 0.78rem; color: #cbd5e1;
                                   text-transform: uppercase; letter-spacing: 0.04em;
                                   margin-bottom: 10px; }}
    .cn-readiness-card .rc-score {{ font-size: 2rem; font-weight: 800; margin-bottom: 4px; }}
    .cn-readiness-card .rc-zona  {{ font-size: 0.8rem; font-weight: 600;
                                   border-radius: 20px; padding: 2px 12px;
                                   display: inline-block; }}

    /* Alertas */
    .cn-alert-row {{
        background:#1a0a0a; border-left:4px solid #EA4335;
        border-radius:8px; padding:10px 16px; margin-bottom:8px;
        display:flex; align-items:center; gap:14px;
    }}
    .cn-alert-row .ar-name {{ font-weight:700; color:#fca5a5; font-size:0.9rem; }}
    .cn-alert-row .ar-detail {{ font-size:0.8rem; color:#fecaca; }}
    .cn-alert-tag {{ background:#7f1d1d; color:#fca5a5; border-radius:20px;
                    padding:2px 8px; font-size:0.72rem; font-weight:600; margin-right:4px; }}

    /* Molestias */
    .cn-molestia-row {{
        background:#1a1000; border-left:4px solid #FBBC04;
        border-radius:8px; padding:10px 16px; margin-bottom:8px;
    }}
    .cn-molestia-row .mo-name   {{ font-weight:700; color:#fde68a; font-size:0.88rem; }}
    .cn-molestia-row .mo-detail {{ font-size:0.8rem; color:#fef3c7; margin-top:2px; }}

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
