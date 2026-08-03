# pages/07_presentacion.py
import sys
from pathlib import Path

import streamlit as st

sys.path.append(str(Path(__file__).parent.parent))
from settings import LOGO_PATH
from src.utils.auth import require_login
from src.ui.theme import inject_dashboard_css, inject_presentacion_light_theme, ICONS, PAGE_COLORS_LIGHT
from src.ui.components import home_button, presentacion_title, slide_html, slide_pilares_html

st.set_page_config(page_title="Presentación", page_icon=str(LOGO_PATH), layout="wide")

require_login()
inject_dashboard_css()
inject_presentacion_light_theme()
home_button()

presentacion_title(
    "¿Por y Para Qué hacemos cada cosa?",
    "Cuidarlas. Potenciarlas. Prevenir lesiones.",
    ["#0f2b5b", PAGE_COLORS_LIGHT["carga_fisica"], PAGE_COLORS_LIGHT["wellness"], "#d95926"],
)

# Cada slide reusa el ícono/color de la página real a la que más se asocia
# temáticamente — así cuando en la última slide se salta al Perfil de
# Jugadora en vivo, el color ya "fue visto" antes en la charla. La Slide 1
# ("kind": "pilares") tiene su propio layout de 3 tarjetas — ver
# slide_pilares_html() — en vez del molde ícono+título+cuerpo de las demás.
SLIDES = [
    {
        "kind": "pilares",
        "icon": ICONS["target"],
        "headline": "“No es control, es cuidado.”",
        "lead": "Todo lo que medimos tiene un solo objetivo: su salud y su mejor "
                "versión en la cancha.",
        "headline_color": PAGE_COLORS_LIGHT["wellness"],
        "cards": [
            {
                "label": "PREVENCIÓN", "subtitle": "Monitoreo Wellness",
                "color": PAGE_COLORS_LIGHT["wellness"],
                "body": "Detectar la fatiga y el estrés antes de que se conviertan "
                        "en una lesión.",
            },
            {
                "label": "INDIVIDUALIZACIÓN", "subtitle": "Carga GPS y Fuerza",
                "color": PAGE_COLORS_LIGHT["carga_fisica"],
                "body": "Adaptar el entrenamiento a la respuesta real del cuerpo "
                        "día a día.",
            },
            {
                "label": "RENDIMIENTO", "subtitle": "Trabajo Integrado",
                "color": PAGE_COLORS_LIGHT["fisico_tt"],
                "body": "Asegurar que lleguen con el máximo de energía y frescura "
                        "al día del partido.",
            },
        ],
        "footer": "“El dato nos da la información, el cuidado lo hacemos entre "
                  "todos.”",
    },
    {
        "kind": "pilares",
        "icon": ICONS["carga_fisica"],
        "headline": "GPS & Carga Física: medir para conocer",
        "lead": "El dispositivo no mide tu actitud; protege tu estructura física.",
        "headline_color": PAGE_COLORS_LIGHT["carga_fisica"],
        "cards": [
            {
                "label": "¿QUÉ MIDE EL GPS?", "subtitle": "Las Métricas Clave",
                "color": PAGE_COLORS_LIGHT["carga_fisica"],
                "body": [
                    "Distancia total y metros en sprint.",
                    "Cantidad de aceleraciones y frenadas.",
                    "Velocidad máxima alcanzada.",
                ],
            },
            {
                "label": "¿QUÉ BUSCAMOS EVITAR?", "subtitle": "El Pico de Carga",
                "color": PAGE_COLORS_LIGHT["partidos"],
                "body": [
                    "Detectar saltos bruscos de volumen respecto a tus últimas "
                    "4 semanas.",
                    "Anticipar el sobreentrenamiento muscular.",
                    "Ajustar minutos de práctica en forma individual según tu "
                    "desgaste.",
                ],
            },
            {
                "label": "¿CUÁL ES EL BENEFICIO?", "subtitle": "El Resultado el Sábado",
                "color": PAGE_COLORS_LIGHT["wellness"],
                "body": [
                    "Llegar al fin de semana con velocidad y sin molestias.",
                ],
            },
        ],
        "footer": "“Lo que no se mide no se puede cuidar. El GPS es la alerta "
                  "temprana para que nunca tengas que parar por lesión.”",
    },
    {
        "kind": "pilares",
        "icon": ICONS["wellness"],
        "headline": "Wellness: la otra mitad de la historia",
        "lead": "El GPS mide lo que le exigimos a tu cuerpo. El Wellness nos dice "
                "cómo estás para responder.",
        "headline_color": PAGE_COLORS_LIGHT["wellness"],
        "cards": [
            {
                "label": "LA FOTO COMPLETA", "subtitle": "GPS + Wellness = Cuidado Real",
                "color": PAGE_COLORS_LIGHT["perfil"],
                "body": [
                    "El GPS nos da el dato duro de la cancha.",
                    "El Wellness nos da el contexto biológico de tu cuerpo.",
                    "Sin ambos, entrenamos a ciegas.",
                ],
            },
            {
                "label": "LO QUE EVALUAMOS", "subtitle": "Los 3 Semáforos Diarios",
                "color": PAGE_COLORS_LIGHT["wellness"],
                "body": [
                    "Sueño: Reparación celular y muscular.",
                    "Dolor muscular: Detección precoz de sobrecarga.",
                    "Estrés y Fatiga: Estado del sistema nervioso.",
                ],
            },
            {
                "label": "LA ACCIÓN REAL", "subtitle": "Ajuste Preventivo",
                "color": PAGE_COLORS_LIGHT["fisico_tt"],
                "body": [
                    "Si la planilla marca alerta, adaptamos tu sesión.",
                    "Mantenés la calidad de entrenamiento sin poner en riesgo tu "
                    "salud.",
                    "Cero culpa: avisar a tiempo es ser profesional.",
                ],
            },
        ],
        "footer": "“La planilla de Wellness no es un trámite, es tu voz diaria "
                  "con el cuerpo técnico.”",
    },
    {
        "kind": "pilares",
        "icon": ICONS["balance"],
        "headline": "Trabajo en equipo: 3 miradas, un solo plan",
        "lead": "El entrenamiento de cada semana surge de la intersección exacta "
                "de estas tres áreas.",
        "headline_color": PAGE_COLORS_LIGHT["fisico_tt"],
        "cards": [
            {
                "label": "ÁREA FÍSICA (PF)", "subtitle": "Carga Objetiva",
                "color": PAGE_COLORS_LIGHT["carga_fisica"],
                "body": [
                    "Monitoreo de metros, velocidades y aceleraciones con GPS.",
                    "Control de límites seguros de carga muscular.",
                    "Prevención de fatiga acumulada.",
                ],
            },
            {
                "label": "ÁREA TÁCTICA (DT)", "subtitle": "Modelo de Juego",
                "color": PAGE_COLORS_LIGHT["partidos"],
                "body": [
                    "Exigencias específicas según el puesto.",
                    "Estrategia y lectura del rival del fin de semana.",
                    "Planificación de bloques de juego reducido.",
                ],
            },
            {
                "label": "VOS (JUGADORA)", "subtitle": "Sensación Real",
                "color": PAGE_COLORS_LIGHT["perfil"],
                "body": [
                    "Tu registro diario en el Wellness.",
                    "Cómo responde tu cuerpo y tu mente al esfuerzo.",
                    "Lo que ningún chip ni cámara puede medir.",
                ],
            },
        ],
        "footer": "“Si falta una sola mirada, la decisión queda incompleta. Tu "
                  "feedback es el que activa el ajuste.”",
    },
    {
        "kind": "pilares",
        "icon": ICONS["trofeo"],
        "headline": "Tu perfil: el mapa de tu temporada",
        "lead": "Detrás de cada dato hay una historia: tu esfuerzo, tu descanso "
                "y tu evolución en la cancha.",
        "headline_color": PAGE_COLORS_LIGHT["perfil"],
        "cards": [
            {
                "label": "TU HISTORIAL REAL", "subtitle": "Evolución Temporal",
                "color": PAGE_COLORS_LIGHT["carga_fisica"],
                "body": [
                    "Relación directa entre tu descanso (Wellness) y tus picos "
                    "de velocidad (GPS).",
                    "Detección de tus semanas de mayor rendimiento.",
                    "Tu progreso en la carga de gimnasio y fuerza.",
                ],
            },
            {
                "label": "TU PROPIO MAPA", "subtitle": "Acceso Transparente",
                "color": PAGE_COLORS_LIGHT["fisico_tt"],
                "body": [
                    "Visualización de tus registros en el software.",
                    "Entender por qué en ciertas semanas bajamos la carga y en "
                    "otras te exigimos más.",
                    "Un perfil único adaptado a tu puesto.",
                ],
            },
            {
                "label": "NUESTRO COMPROMISO", "subtitle": "Acompañamiento",
                "color": PAGE_COLORS_LIGHT["wellness"],
                "body": [
                    "Trabajar juntos en tus puntos a mejorar.",
                    "Prevenir lesiones antes de que aparezcan.",
                    "Acompañarte para que llegues a tu pico máximo los días de "
                    "partido.",
                ],
            },
        ],
        "footer": "“Los datos no son del staff, son tuyos. Pasemos a ver el "
                  "software para entender el camino de cada una.”",
    },
]

if "cn_slide_idx" not in st.session_state:
    st.session_state["cn_slide_idx"] = 0

idx = st.session_state["cn_slide_idx"]
slide = SLIDES[idx]

if slide["kind"] == "pilares":
    slide_pilares_html(
        slide["headline"], slide["lead"], slide["cards"], slide["footer"],
        headline_color=slide.get("headline_color", PAGE_COLORS_LIGHT["wellness"]),
        icon=slide.get("icon"),
    )
else:
    slide_html(slide["icon"], slide["color"], slide["eyebrow"], slide["title"], slide["body"])

col_prev, col_counter, col_next = st.columns([1, 2, 1])
with col_prev:
    if st.button("← Anterior", use_container_width=True, disabled=idx == 0):
        st.session_state["cn_slide_idx"] -= 1
        st.rerun()
with col_counter:
    st.markdown(
        f"<p style='text-align:center; color:#3b5b8c; margin-top:8px'>"
        f"Sección {idx + 1} de {len(SLIDES)}</p>",
        unsafe_allow_html=True,
    )
with col_next:
    if st.button("Siguiente →", use_container_width=True, disabled=idx == len(SLIDES) - 1):
        st.session_state["cn_slide_idx"] += 1
        st.rerun()

if idx == len(SLIDES) - 1:
    st.divider()
    st.page_link("pages/05_perfil_jugadora.py", label="Ir al Perfil de Jugadora en vivo", icon="🎯")
