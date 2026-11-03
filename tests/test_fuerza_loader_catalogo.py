import pandas as pd
import pytest

# El loader importa psycopg al cargarse; si el entorno no lo tiene, se saltea.
pytest.importorskip("psycopg")

from src.loaders.fuerza_loader import _procesar_catalogo, _procesar_catalogo_resist


def test_catalogo_fuerza_acepta_encabezado_plural_y_trae_el_id():
    # Encabezados reales de la planilla Ejercicios_fisico (pestaña Catalogo_fuerza)
    crudo = pd.DataFrame(
        [["Sentadilla frontal", "Dominante de rodilla", None, "Sí", None, "FZA-001"],
         ["Remo TRX", "Tracción", None, None, None, "FZA-009"],
         [None, None, None, None, None, None]],
        columns=["EJERCICIOS", "CATEGORIA", "UNILATERAL", "ADMITE_RM", "EJERCICIO_REFERENCIA", "ID"])
    out = _procesar_catalogo(crudo)
    assert list(out["ejercicio_id"]) == ["FZA-001", "FZA-009"]
    assert list(out["ejercicio"]) == ["Sentadilla frontal", "Remo TRX"]
    assert list(out["admite_rm"]) == [True, False]


def test_catalogo_fuerza_sin_columna_id_no_rompe():
    crudo = pd.DataFrame({"EJERCICIO": ["Hip thrust"], "CATEGORIA": ["Cadera"]})
    out = _procesar_catalogo(crudo)
    assert list(out["ejercicio_id"]) == [""]


def test_catalogo_resist_conserva_los_nombres_repetidos_con_su_id():
    crudo = pd.DataFrame(
        {"NOMBRE_EJERCICIO": ["Pasadas", "Pasadas", "Velocidad en 30"],
         "CATEGORIA": [None, None, None],
         "ID": ["RES-006", "RES-007", "RES-001"]})
    out = _procesar_catalogo_resist(crudo)
    assert list(out["ejercicio_id"]) == ["RES-006", "RES-007", "RES-001"]
    assert out["ejercicio"].tolist().count("Pasadas") == 2
