# src/ui/navegacion.py
"""
Única fuente de verdad de la navegación del dashboard: qué páginas hay, cómo se llaman, en
qué sección viven y con qué ícono/color. La Home la recorre para dibujar las tarjetas y el
menú lateral la va a reutilizar (st.navigation). Datos puros: no dibuja nada.

Para sumar una página: crear el archivo en pages/ Y registrarla acá. Un test falla si
un archivo de pages/ queda sin registrar.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class PaginaNav:
    clave: str                    # identificador estable (también define el key de la tarjeta)
    archivo: str                  # ruta relativa a la raíz del proyecto, ej. "pages/02_carga_fisica.py"
    titulo: str
    subtitulo: str                # una línea para la tarjeta de la Home
    icono: str                    # entrada de ICONS
    color_clave: str | None       # entrada de PAGE_COLORS (None = sin color propio)


@dataclass(frozen=True)
class Seccion:
    titulo: str
    paginas: tuple[PaginaNav, ...]


SECCIONES: tuple[Seccion, ...] = (
    Seccion("Monitoreo del equipo", (
        PaginaNav("carga_fisica", "pages/02_carga_fisica.py", "Carga Física",
                  "GPS · ACWR · Intensidad relativa", "carga_fisica", "carga_fisica"),
        PaginaNav("wellness", "pages/03_wellness.py", "Wellness",
                  "Readiness · Alertas · Molestias", "wellness", "wellness"),
        PaginaNav("partidos", "pages/06_partidos.py", "Partidos",
                  "Radar comparativo entre partidos", "trofeo", "partidos"),
    )),
    Seccion("Individual", (
        PaginaNav("perfil", "pages/05_perfil_jugadora.py", "Perfil de Jugadora",
                  "Evolución individual en el tiempo", "target", "perfil"),
    )),
    Seccion("Planificación", (
        PaginaNav("entrenamiento", "pages/06_sesiones_entrenamiento.py", "Entrenamiento",
                  "Cargas por día · MD-5 / MD-4 / MD-2", "entrenamiento", "entrenamiento"),
        PaginaNav("fuerza", "pages/10_fuerza.py", "Fuerza",
                  "Plan semanal · Sesión · Historial", "fuerza", "fuerza"),
        PaginaNav("biblioteca", "pages/09_biblioteca_ejercicios.py", "Biblioteca de Ejercicios",
                  "Demanda física por ejercicio", "biblioteca", "biblioteca"),
    )),
    Seccion("Análisis", (
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
