# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run the app locally
streamlit run app.py

# Install dependencies (requirements-dev.txt pulls in requirements.txt + pytest)
pip install -r requirements-dev.txt

# Run the full test suite
python -m pytest tests/ -v

# Run a single test file / single test
python -m pytest tests/test_parametros.py -v
python -m pytest tests/test_analisis.py::test_debilidad_con_2_o_mas_metricas_fuera_de_rango -v
```

No linter/formatter is configured in this repo. There is no build step — this is a plain Streamlit app deployed as-is to Streamlit Community Cloud (https://cn-hockey.streamlit.app/); a GitHub Action (`.github/workflows/keep-alive.yml`) pings it every 6h to prevent the free tier from sleeping.

**Local dev gotcha**: a running `streamlit run` process does not reliably reimport changed files under `src/` (only the page script itself reruns automatically). After editing anything under `src/`, restart the process (Ctrl+C, rerun `streamlit run app.py`) before testing in the browser — otherwise you'll see stale behavior or `ImportError` for symbols you just added.

## Architecture

### Data flow and sources

Two independent data domains feed the dashboard:

- **Wellness** (TQR/RPE/readiness/molestias) is read live from a Google Sheet, no auth: every loader in `src/loaders/` builds a public CSV-export URL (`https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}`) and reads it with `pd.read_csv`. `settings.py` holds one `WELLNESS_SHEET_ID` and a separate GID per tab (`WELLNESS_SHEET_GID`, `ROSTER_SHEET_GID`, `SESIONES_SHEET_GID`, `PARAMETROS_SHEET_GID`) — they're all tabs of the *same* spreadsheet.
- **GPS/physical** (Catapult exports) is NOT live: `data/processed/gps_procesado.parquet` is the committed source of truth. Pages let the user upload new Catapult CSVs mid-session (Carga Física's "Subir nueva sesión GPS" panel), but uploads only live in `st.session_state["gps_extra"]` for that session — persisting them requires downloading the merged parquet and committing it back manually.
- `player_id` (not the raw "nombre" string) is the canonical join key across GPS/wellness/roster — `normalizar_nombre()` in `src/loaders/wellness_loader.py` reconciles them, since Catapult exports names in uppercase while the roster/wellness sheets use normal case.

### `src/` layering: loaders → metrics → ui

- `src/loaders/`: pure IO. Returns plain pandas DataFrames, no Streamlit and no caching — every page wraps the call in its own `@st.cache_data`-decorated function.
- `src/metrics/`: pure calculation on DataFrames, no Streamlit and no IO. `physical.py` (ACWR/EWMA/intensidad relativa), `wellness.py` (readiness/alertas), `parametros.py` and `analisis.py` (Asistente de Parámetros, see below).
- `src/ui/`: Streamlit-facing, split strictly by concern — `theme.py` (color palette, SVG icons, the one `inject_dashboard_css()` call) holds no logic and imports nothing from the rest of `src/ui`; `state.py` (cross-page session persistence, see below); `charts.py` (Plotly layout dicts); `components.py` (HTML card/table renderers — nav cards, KPI rows, the ACWR/Asistente/molestias/alertas tables, all reusable across pages); `filtros.py` (`popover_multiselect()`, the label+popover+multiselect+persist widget every filter in the app uses); `asistente.py` (wires `metrics/parametros.py` + `metrics/analisis.py` + `components.py` together for the Asistente feature).
- `src/reports/pdf_builder.py`: reportlab + kaleido, builds a print-oriented PDF per page. Every page's "Generar informe PDF" button reuses the SAME already-computed on-screen tables/figures — never recompute a table just for the PDF, pass the existing variable to `SeccionTabla`/`SeccionFigura`.

### Cross-page filter persistence

Streamlit clears a widget's `session_state` entry the instant that widget isn't rendered in a run — so every filter would silently reset on page navigation even with an explicit `key=`. `src/ui/state.py`'s `init_persistent(key, default)` / `save_persistent(key)` work around this by mirroring the value into a separate `__persist_{key}` entry not tied to any widget. The pattern is always: call `init_persistent()` immediately before creating the widget, pass `on_change=lambda: save_persistent(key)` to it. `popover_multiselect()` in `filtros.py` already does this internally — prefer it over a raw `st.popover`/`st.multiselect` pair for any new filter.

### Asistente de Parámetros (spans all 4 "fitting" pages)

Compares real GPS metrics against expected ranges from the Sheet's "Parametros" tab (Match Day × Posición × Métrica → min–max range). Two evaluation paths in `src/metrics/parametros.py`, both built on the shared `_totalizar_por_dia()` step (sums Físico+Técnico-Táctico sessions for the same jugadora/day before comparing, since the Sheet doesn't distinguish session type):

- `armar_evaluacion_equipo()` additionally averages across jugadoras sharing a position — feeds the on-screen comparison table (`components.tabla_asistente_html`).
- `evaluar_por_jugadora()` skips that averaging step, keeping one row per jugadora — feeds `src/metrics/analisis.py`'s `generar_analisis()`, which flags a jugadora as *fortaleza* (nothing out of range) or *debilidad* (2+ metrics out of range) with a template-based recommendation.

`generar_analisis()` is deterministic on purpose — no LLM is involved anywhere in this feature. A wrong flag here could influence a real training-load decision, so every verdict must trace back to an actual number in `df_parametros`, never a generated one.

Every fitting page (`02_carga_fisica.py`, `04_fisico_vs_tt.py`, `05_perfil_jugadora.py`, `06_partidos.py`) drives both paths through the single `render_asistente()` in `src/ui/asistente.py`, passing page-specific `claves_grupo` / `etiqueta_fn` / `match_day`. Adding or changing this feature should almost never require new per-page rendering code — extend `render_asistente()` (and the two `metrics/` functions it calls) instead.

### Auth

`src/utils/auth.py`'s `require_login()` is a bare username/password check against `st.secrets["credentials"]` (`.streamlit/secrets.toml`, gitignored) — call it immediately after `st.set_page_config()` on every page. `st.session_state["authenticated"]` is the only guard; there's no OAuth or session token.

### Page numbering gap

`pages/` goes `02_carga_fisica.py` → `06_partidos.py` with no `01` — `pages/01_overview.py` was deleted after being merged into `03_wellness.py` (which now covers everything Overview showed, plus readiness trends, alertas and molestias Overview never had). The gap is intentional: Streamlit derives page identity/URLs from the filename, so renumbering the remaining five files for a purely cosmetic fix isn't worth the risk.

### Testing convention

Tests exist only for `src/metrics/` (pure functions, no IO/Streamlit) — `test_physical.py`, `test_wellness.py`, `test_parametros.py`, `test_analisis.py`. `src/ui/` (rendering) and `src/loaders/` (network IO) are intentionally untested; keep new pure logic in `src/metrics/` to stay testable the same way.
