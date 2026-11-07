# src/ui/navegacion.py
"""
Única fuente de verdad de la navegación del dashboard: qué páginas hay, cómo se llaman, en
qué sección viven y con qué ícono/color. La Home la recorre para dibujar las tarjetas y el
menú lateral la va a reutilizar (st.navigation). Datos puros: no dibuja nada.

Para sumar una página: crear el archivo en pages/ Y registrarla acá. Un test falla si
un archivo de pages/ queda sin registrar.
"""
import re
from dataclasses import dataclass
from pathlib import Path


# Clave de st.session_state donde el router deja su página "Inicio" (un StreamlitPage) para que
# home_button() sepa a dónde volver cuando "app.py" ya no es una página sino el router.
PAGINA_HOME_KEY = "__pagina_home"

# Clave de st.session_state que el router deja en True cuando el menú está en la barra superior.
# Con la barra arriba ya hay un "Inicio", así que el botón "Home" de cada página sobra.
MENU_ARRIBA_KEY = "__menu_arriba"


@dataclass(frozen=True)
class PaginaNav:
    clave: str                    # identificador estable (también define el key de la tarjeta)
    archivo: str                  # ruta relativa a la raíz del proyecto, ej. "pages/02_carga_fisica.py"
    titulo: str
    subtitulo: str                # una línea para la tarjeta de la Home
    icono: str                    # entrada de ICONS
    color_clave: str | None       # entrada de PAGE_COLORS (None = sin color propio)

    @property
    def url_path(self) -> str:
        """Ruta de la página: el nombre del archivo sin el número (02_carga_fisica -> carga_fisica).
        Es la misma que Streamlit asigna hoy, así que los enlaces guardados siguen funcionando."""
        return re.sub(r"^\d+_", "", Path(self.archivo).stem)


@dataclass(frozen=True)
class Seccion:
    titulo: str
    url_path: str                 # ruta del hub (o de la única página, si la sección tiene una sola)
    paginas: tuple[PaginaNav, ...]

    @property
    def etiqueta_menu(self) -> str:
        """Texto en el menú lateral: el título de la sección, o el de la página si es una sola."""
        return self.titulo if len(self.paginas) > 1 else self.paginas[0].titulo


@dataclass(frozen=True)
class EntradaMenu:
    etiqueta: str
    url_path: str
    icono: str                    # ícono Material (st.page_link(icon=...)) para el menú lateral


SECCIONES: tuple[Seccion, ...] = (
    Seccion("Monitoreo del equipo", "monitoreo", (
        PaginaNav("carga_fisica", "pages/02_carga_fisica.py", "Carga Física",
                  "GPS · ACWR · Intensidad relativa", "carga_fisica", "carga_fisica"),
        PaginaNav("wellness", "pages/03_wellness.py", "Wellness",
                  "Readiness · Alertas · Molestias", "wellness", "wellness"),
        PaginaNav("partidos", "pages/06_partidos.py", "Partidos",
                  "Radar comparativo entre partidos", "trofeo", "partidos"),
    )),
    Seccion("Individual", "perfil_jugadora", (
        PaginaNav("perfil", "pages/05_perfil_jugadora.py", "Perfil de Jugadora",
                  "Evolución individual en el tiempo", "target", "perfil"),
    )),
    Seccion("Planificación", "planificacion", (
        PaginaNav("entrenamiento", "pages/06_sesiones_entrenamiento.py", "Entrenamiento",
                  "Cargas por día · MD-5 / MD-4 / MD-2", "entrenamiento", "entrenamiento"),
        PaginaNav("fuerza", "pages/10_fuerza.py", "Fuerza",
                  "Plan semanal · Sesión · Historial", "fuerza", "fuerza"),
        PaginaNav("biblioteca", "pages/09_biblioteca_ejercicios.py", "Biblioteca de Ejercicios",
                  "Demanda física por ejercicio", "biblioteca", "biblioteca"),
    )),
    Seccion("Análisis", "analitica", (
        PaginaNav("fisico_tt", "pages/04_fisico_vs_tt.py", "Físico vs Técnico-Táctico",
                  "Comparativa de demandas", "balance", "fisico_tt"),
        PaginaNav("analisis", "pages/08_analisis.py", "Análisis",
                  "FODA de entrenamientos", "analisis", "analisis"),
    )),
)

# Ya no se usa en el día a día, solo para alguna charla: no es una tarjeta ni una sección,
# se ofrece como un enlace discreto.
PAGINA_PRESENTACION = PaginaNav(
    "presentacion", "pages/07_presentacion.py", "Presentación",
    "Para charlas con las jugadoras", "presentacion", None)


def paginas_registradas() -> list[PaginaNav]:
    """Todas las páginas registradas: las de las secciones más la Presentación."""
    return [p for s in SECCIONES for p in s.paginas] + [PAGINA_PRESENTACION]


# Íconos Material del menú lateral por sección (clave = url_path de la sección).
_ICONO_MENU = {
    "monitoreo": ":material/monitoring:",
    "perfil_jugadora": ":material/person:",
    "planificacion": ":material/event_note:",
    "analitica": ":material/analytics:",
}


def entradas_menu() -> list[EntradaMenu]:
    """
    Lo que muestra el menú lateral agrupado: Inicio y una entrada por sección. La Presentación
    no está: ya no se usa a diario y se llega a ella desde un enlace al pie de la Home.
    """
    return [EntradaMenu("Inicio", "", ":material/home:")] + [
        EntradaMenu(s.etiqueta_menu, s.url_path, _ICONO_MENU[s.url_path]) for s in SECCIONES
    ]
