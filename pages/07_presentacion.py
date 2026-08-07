# pages/07_presentacion.py
import sys
from pathlib import Path

import streamlit as st

sys.path.append(str(Path(__file__).parent.parent))
from settings import LOGO_PATH
from src.utils.auth import require_login
from src.ui.theme import inject_dashboard_css, inject_presentacion_light_theme, ICONS, PAGE_COLORS_LIGHT
from src.ui.components import (
    home_button, presentacion_title, slide_html, slide_pilares_html,
    slide_stats_grid_html, slide_gauges_html, slide_gap_compare_html,
)

st.set_page_config(page_title="Presentación", page_icon=str(LOGO_PATH), layout="wide")

require_login()
inject_dashboard_css()
inject_presentacion_light_theme()
home_button()

presentacion_title(
    "¿Por y Para Qué hacemos cada cosa?",
    "Cuidarlas. Potenciarlas. Prevenir lesiones.",
    accent="#0f2b5b",
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
                    "Distancia Total (m)",
                    "Distancia relativa (m/min)",
                    "HSR (distancia a alta intensidad)",
                    "Sprints",
                    "Velocidad máxima",
                    "Acc y Decc a alta intensidad",
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
                    "Llegar al partido sin molestias y con frescura.",
                    "Feedback sobre sensaciones de cada una.",
                    "Buscar rendimientos máximos individuales.",
                ],
            },
        ],
        "footer": "“Lo que no se mide no se puede cuidar. El GPS es la alerta "
                  "temprana para que nunca tengas que parar por lesión.”",
    },
    {
        "kind": "stats",
        "icon": ICONS["carga_fisica"],
        "headline": "Métricas más relevantes - Las demandas del Sábado",
        "lead": "Los partidos nos van indicando nuestras capacidades máximas "
                "alcanzadas. Los entrenamientos semanales se diseñan para "
                "alcanzar, tolerar y potencialmente superar estos valores.",
        "headline_color": PAGE_COLORS_LIGHT["carga_fisica"],
        "stats": [
            {
                "icon": ICONS["carga_fisica"], "label": "Volumen",
                "value": "5.600 ± 500 (m)",
                "caption": "Distancia Total (metros recorridos)",
            },
            {
                "icon": ICONS["reloj"], "label": "Densidad",
                "value": "125 ± 15 (m/min)",
                "caption": "Distancia Relativa",
            },
            {
                "icon": ICONS["velocidad"], "label": "Intensidad",
                "value": "380 ± 100 (m)",
                "caption": "Distancia HSR (High-Speed Running)",
            },
            {
                "icon": ICONS["rayo"], "label": "Potencia",
                "value": "11 ± 4 (m/min)",
                "caption": "HSR por Minuto",
            },
        ],
    },
    {
        "kind": "gauges",
        "icon": ICONS["balance"],
        "headline": "Anatomía de las Métricas: Volumen vs. Densidad",
        "lead": "Por qué 6 kilómetros no siempre significan lo mismo.",
        "headline_color": PAGE_COLORS_LIGHT["carga_fisica"],
        "panels": [
            {
                "titulo": "Distancia Total", "subtitulo": "Volumen Absoluto",
                "meters": [{"pct": 100, "tag": "6000m", "color": PAGE_COLORS_LIGHT["fisico_tt"]}],
                "nota": "Mide el \"cuánto\" pero no el \"cómo\". Un alto volumen "
                        "sin el ritmo adecuado no replica demandas de partido.",
            },
            {
                "titulo": "Distancia Relativa", "subtitulo": "densidad de metros/min",
                "meters": [
                    {"pct": 35, "tag": "6000m en 90 min", "label": "Bajos mts/min",
                     "color": PAGE_COLORS_LIGHT["partidos"]},
                    {"pct": 90, "tag": "6000m en 45 min", "label": "Altos mts/min",
                     "color": PAGE_COLORS_LIGHT["wellness"]},
                ],
                "nota_fuerte": "Mts/min:",
                "nota": "Partidos de élite se encuentran entre los 120-130 m/min. "
                        "Es un gran indicador de intensidad y posterior fatiga "
                        "metabólica aguda.",
            },
        ],
        "regla_label": "IMPORTANTE:",
        "regla_text": "para replicar el estrés de los partidos, debemos igualar "
                       "la densidad (m/min) especialmente los días Martes (MD-4).",
    },
    {
        "kind": "gap",
        "icon": ICONS["trofeo"],
        "headline": "La Grieta: Partido vs Entrenamiento",
        "lead": "En los entrenamientos debemos buscar volúmenes controlados, "
                "llegando a marcas de partidos para proteger y tolerar los "
                "momentos de máxima exigencia.",
        "headline_color": PAGE_COLORS_LIGHT["partidos"],
        "items": [
            {
                "label": "Distancia Total",
                "domingo_val": 5800, "domingo_label": "5800 ± 500",
                "domingo_caption": "Sábado",
                "practica_val": 3450, "practica_label": "3450 ± 400",
                "badge": {"icon": "check", "text": "OK", "color": PAGE_COLORS_LIGHT["wellness"]},
            },
            {
                "label": "HSR (Alta Intensidad)",
                "domingo_val": 380, "domingo_label": "380 ± 100m",
                "domingo_caption": "Sábado",
                "practica_val": 95, "practica_label": "95 ± 10m",
                "callout": "El partido exige >2.5x más metros a alta velocidad.",
                "badge": {"icon": "alerta", "text": "ALERTA", "color": PAGE_COLORS_LIGHT["partidos"]},
            },
            {
                "label": "Distancia Relativa",
                "domingo_val": 125, "domingo_label": "125 ± 15 m/min",
                "practica_val": 75, "practica_label": "75 ± 10 m/min",
                "badge": {"icon": "alerta", "text": "ALERTA", "color": PAGE_COLORS_LIGHT["partidos"]},
            },
        ],
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
elif slide["kind"] == "stats":
    slide_stats_grid_html(
        slide["headline"], slide["lead"], slide["stats"],
        headline_color=slide.get("headline_color", PAGE_COLORS_LIGHT["carga_fisica"]),
        icon=slide.get("icon"),
    )
elif slide["kind"] == "gauges":
    slide_gauges_html(
        slide["headline"], slide["lead"], slide["panels"],
        slide["regla_label"], slide["regla_text"],
        headline_color=slide.get("headline_color", PAGE_COLORS_LIGHT["carga_fisica"]),
        icon=slide.get("icon"),
    )
elif slide["kind"] == "gap":
    slide_gap_compare_html(
        slide["headline"], slide["lead"], slide["items"],
        headline_color=slide.get("headline_color", PAGE_COLORS_LIGHT["partidos"]),
        icon=slide.get("icon"),
    )
else:
    slide_html(slide["icon"], slide["color"], slide["eyebrow"], slide["title"], slide["body"])

if st.button("←", key="cn-slide-prev", help="Sección anterior", disabled=idx == 0):
    st.session_state["cn_slide_idx"] -= 1
    st.rerun()
st.markdown(
    f"<p class='cn-slide-counter'>Sección {idx + 1} de {len(SLIDES)}</p>",
    unsafe_allow_html=True,
)
if st.button("→", key="cn-slide-next", help="Sección siguiente", disabled=idx == len(SLIDES) - 1):
    st.session_state["cn_slide_idx"] += 1
    st.rerun()

if idx == len(SLIDES) - 1:
    st.divider()
    st.page_link("pages/05_perfil_jugadora.py", label="Ir al Perfil de Jugadora en vivo", icon="🎯")
