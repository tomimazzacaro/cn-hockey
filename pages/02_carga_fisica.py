# pages/02_carga_fisica.py
import io
import datetime
import streamlit as st
import pandas as pd
import plotly.express as px
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from settings import (
    PROCESSED, WELLNESS_SHEET_ID, ROSTER_SHEET_GID, SESIONES_SHEET_GID,
    TIPOS_SESION, CUARTOS,
)
from src.utils.auth import require_login
from src.loaders.gps_loader import (
    cargar_sesion_desde_upload,
    extraer_fecha_de_nombre,
)
from src.loaders.roster_loader import cargar_posiciones_desde_sheets
from src.loaders.sesiones_loader import cargar_sesiones_desde_sheets, orden_match_day
from src.metrics.physical import calcular_acwr, calcular_intensidad_relativa

st.set_page_config(page_title="Carga Física", page_icon="📊", layout="wide")

require_login()
st.title("📊 Carga Física")
st.caption("GPS Catapult — Métricas de carga externa e intensidad relativa")
st.divider()

# ── Subir nueva sesión GPS ─────────────────────────────────────────────────
def _backfill_columnas(df: pd.DataFrame) -> pd.DataFrame:
    """Datos históricos previos a tipo_sesion/cuarto."""
    if "tipo_sesion" not in df.columns:
        df["tipo_sesion"] = TIPOS_SESION[0]
    if "cuarto" not in df.columns:
        df["cuarto"] = "—"
    return df


def _panel_upload(tipo_sesion: str, key_prefix: str) -> None:
    uploaded = st.file_uploader(
        "Archivo CSV exportado de Catapult",
        type=["csv"],
        key=f"{key_prefix}_upload",
        help="El nombre del archivo debe tener formato export_DD-MM-YY.csv",
    )

    if not uploaded:
        return

    # Intentar detectar fecha del nombre
    try:
        fecha_default = extraer_fecha_de_nombre(uploaded.name).date()
    except ValueError:
        fecha_default = datetime.date.today()

    fecha_input = st.date_input(
        "Fecha de la sesión",
        value=fecha_default,
        format="DD/MM/YYYY",
        key=f"{key_prefix}_fecha_{uploaded.file_id}",
    )

    try:
        df_prev = cargar_sesion_desde_upload(uploaded, tipo_sesion, fecha_override=fecha_input)
        df_prev = calcular_intensidad_relativa(df_prev)

        st.success(
            f"✅ {len(df_prev)} jugadoras detectadas — "
            f"{fecha_input.strftime('%d/%m/%Y')}"
        )
        st.dataframe(
            df_prev[["nombre", "fecha", "distancia_total",
                      "hsr", "sprints", "player_load", "vel_max_kmh"]]
                    .reset_index(drop=True),
            use_container_width=True,
            hide_index=True,
        )

        if st.button("➕ Agregar al historial", type="primary", key=f"{key_prefix}_add"):
            _reemplazar_en_historial(df_prev)
            st.rerun()

    except Exception as e:
        st.error(f"Error al procesar el archivo: {e}")


def _reemplazar_en_historial(df_nuevo: pd.DataFrame) -> None:
    """Agrega df_nuevo a gps_extra, reemplazando cualquier entrada previa
    con la misma combinación (fecha, tipo_sesion, cuarto)."""
    fecha, tipo, cuarto = (df_nuevo["fecha"].iloc[0], df_nuevo["tipo_sesion"].iloc[0],
                            df_nuevo["cuarto"].iloc[0])
    extras = st.session_state.get("gps_extra", [])
    extras = [d for d in extras
              if not (d["fecha"].iloc[0] == fecha
                      and d["tipo_sesion"].iloc[0] == tipo
                      and d["cuarto"].iloc[0] == cuarto)]
    extras.append(df_nuevo)
    st.session_state["gps_extra"] = extras


def _panel_partido() -> None:
    fecha_input = st.date_input(
        "Fecha del partido",
        value=datetime.date.today(),
        format="DD/MM/YYYY",
        key="pa_fecha",
    )

    dfs_cuartos = {}
    for cuarto in CUARTOS:
        uploaded = st.file_uploader(
            f"CSV — {cuarto}",
            type=["csv"],
            key=f"pa_{cuarto}_upload",
        )
        if not uploaded:
            continue
        try:
            df_q = cargar_sesion_desde_upload(
                uploaded, TIPOS_SESION[2], fecha_override=fecha_input, cuarto=cuarto,
            )
            df_q = calcular_intensidad_relativa(df_q)
            dfs_cuartos[cuarto] = df_q
            st.caption(f"✅ {cuarto}: {len(df_q)} jugadoras detectadas")
        except Exception as e:
            st.error(f"{cuarto}: error al procesar el archivo — {e}")

    if dfs_cuartos and st.button("➕ Agregar partido al historial",
                                  type="primary", key="pa_add"):
        for df_q in dfs_cuartos.values():
            _reemplazar_en_historial(df_q)
        st.rerun()


n_extra = len(st.session_state.get("gps_extra", []))
expander_label = (
    f"📂 Subir nueva sesión GPS  ·  {n_extra} sesión/es cargada/s en esta sesión"
    if n_extra else "📂 Subir nueva sesión GPS"
)

with st.expander(expander_label, expanded=(n_extra == 0)):
    tab_fis, tab_tt, tab_pa = st.tabs(
        ["🏃 Sesión Física", "🥅 Sesión Técnico-Táctica", "🏑 Partido"]
    )
    with tab_fis:
        _panel_upload(TIPOS_SESION[0], "fis")
    with tab_tt:
        _panel_upload(TIPOS_SESION[1], "tt")
    with tab_pa:
        st.caption("Subí el CSV de cada cuarto (Catapult los exporta por separado).")
        _panel_partido()

    # Download del parquet actualizado
    extras_dl = st.session_state.get("gps_extra", [])
    if extras_dl:
        st.divider()
        st.caption(
            "Descargá el parquet actualizado y commitealo al repo para que "
            "Streamlit Cloud lo persista entre sesiones."
        )
        try:
            base_dl = pd.read_parquet(PROCESSED / "gps_procesado.parquet")
            base_dl = _backfill_columnas(base_dl)
            base_dl = calcular_intensidad_relativa(base_dl)
        except FileNotFoundError:
            base_dl = pd.DataFrame()

        df_dl = pd.concat([base_dl] + extras_dl, ignore_index=True)
        df_dl = (df_dl.drop_duplicates(subset=["player_id", "fecha", "tipo_sesion", "cuarto"],
                                       keep="last")
                      .sort_values(["fecha", "nombre"])
                      .reset_index(drop=True))

        buf = io.BytesIO()
        df_dl.to_parquet(buf, index=False)
        buf.seek(0)

        st.download_button(
            "⬇️ Descargar gps_procesado.parquet actualizado",
            data=buf,
            file_name="gps_procesado.parquet",
            mime="application/octet-stream",
            use_container_width=True,
        )

st.divider()

# ── Cargar datos (base + uploads de esta sesión) ───────────────────────────
@st.cache_data
def cargar_base():
    df = pd.read_parquet(PROCESSED / "gps_procesado.parquet")
    df = _backfill_columnas(df)
    return calcular_intensidad_relativa(df)

try:
    df_base = cargar_base()
except FileNotFoundError:
    df_base = pd.DataFrame()

extras = st.session_state.get("gps_extra", [])
if extras:
    df = pd.concat([df_base] + extras, ignore_index=True)
    df = (df.drop_duplicates(subset=["player_id", "fecha", "tipo_sesion", "cuarto"], keep="last")
            .sort_values(["fecha", "nombre"])
            .reset_index(drop=True))
else:
    df = df_base

if df.empty:
    st.info("Sin datos GPS. Subí una sesión usando el panel de arriba.")
    st.stop()

df = calcular_acwr(df, col_carga="player_load")


def _agregar_partidos_completos(df: pd.DataFrame) -> pd.DataFrame:
    """
    Genera una fila 'Completo' por partido, sumando los cuartos disponibles
    (o el máximo, para métricas de velocidad pico). Es solo para visualización
    como una sesión más — no se persiste ni se usa para el ACWR, que ya suma
    la carga por día sobre los cuartos reales.
    """
    partidos = df[df["tipo_sesion"] == TIPOS_SESION[2]]
    if partidos.empty:
        return df

    COLS_SUMA = ["duracion_min", "distancia_total", "hsr", "hsr_esfuerzos", "sprints",
                 "acc_3", "acc_2", "decc_3", "decc_2",
                 "player_load", "pl_fwd", "pl_side", "pl_up", "pl_2d", "pl_slow", "acc_load"]
    COLS_MAX  = ["vel_max_kmh", "vel_max_ms", "vel_max_pct"]
    COLS_ACWR = ["ewma_aguda", "ewma_cronica", "acwr", "zona_acwr"]

    agg = {c: "sum" for c in COLS_SUMA if c in partidos.columns}
    agg.update({c: "max" for c in COLS_MAX if c in partidos.columns})
    # El ACWR ya es el mismo en las 4 filas del día (se agrega por día en calcular_acwr)
    agg.update({c: "first" for c in COLS_ACWR if c in partidos.columns})

    completos = partidos.groupby(["player_id", "nombre", "fecha"], as_index=False).agg(agg)
    completos["tipo_sesion"] = TIPOS_SESION[2]
    completos["cuarto"] = "Completo"

    if "posicion" in partidos.columns:
        mapa_pos = partidos.drop_duplicates("player_id").set_index("player_id")["posicion"]
        completos["posicion"] = completos["player_id"].map(mapa_pos)

    completos = calcular_intensidad_relativa(completos)

    return pd.concat([df, completos], ignore_index=True)


@st.cache_data(ttl=3600)
def cargar_posiciones():
    try:
        return cargar_posiciones_desde_sheets(WELLNESS_SHEET_ID, ROSTER_SHEET_GID)
    except Exception:
        return None

df_pos = cargar_posiciones()
if df_pos is not None:
    df = df.merge(df_pos[["player_id", "posicion"]], on="player_id", how="left")

df = _agregar_partidos_completos(df)


@st.cache_data(ttl=3600)
def cargar_sesiones():
    try:
        return cargar_sesiones_desde_sheets(WELLNESS_SHEET_ID, SESIONES_SHEET_GID)
    except Exception:
        return None

df_sesiones = cargar_sesiones()
if df_sesiones is not None:
    df = df.merge(df_sesiones, on="fecha", how="left")
    df["match_day"] = df["match_day"].fillna("Sin clasificar")
    df["tipo_dia"]  = df["tipo_dia"].fillna("Sin clasificar")
    df["rival"]     = df["rival"].fillna("")

# ── Filtros ────────────────────────────────────────────────────────────────
col_ses, col_pos, col_md = st.columns([1.8, 1, 1])

rival_por_fecha = (
    df[["fecha", "rival"]].drop_duplicates("fecha").set_index("fecha")["rival"].to_dict()
    if "rival" in df.columns else {}
)

with col_ses:
    sesiones_disp = list(
        df[["fecha", "tipo_sesion", "cuarto"]]
          .drop_duplicates()
          .sort_values("fecha", ascending=False)
          .itertuples(index=False, name=None)
    )
    sesion_sel = st.selectbox(
        "Sesión",
        sesiones_disp,
        format_func=lambda x: (
            f"{x[0].strftime('%d/%m/%Y') if hasattr(x[0], 'strftime') else x[0]} · {x[1]}"
            + (f" · {x[2]}" if x[2] != "—" else "")
            + (f" · vs {rival_por_fecha.get(x[0])}" if rival_por_fecha.get(x[0]) else "")
        ),
    )
    fecha_sel, tipo_sel, cuarto_sel = sesion_sel

with col_pos:
    if df_pos is not None:
        posiciones = sorted(df_pos["posicion"].dropna().unique())
        st.markdown(
            '<p style="font-size:0.875rem; color:inherit; margin-bottom:0.25rem">Posición</p>',
            unsafe_allow_html=True,
        )
        with st.popover("Posición", use_container_width=True):
            pos_sel = st.multiselect(
                "Posición", posiciones, default=posiciones, label_visibility="collapsed"
            )
    else:
        pos_sel = None

with col_md:
    if df_sesiones is not None:
        mds_disponibles = sorted(df["match_day"].dropna().unique(), key=orden_match_day)
        st.markdown(
            '<p style="font-size:0.875rem; color:inherit; margin-bottom:0.25rem">Match Day</p>',
            unsafe_allow_html=True,
        )
        with st.popover("Match Day", use_container_width=True):
            md_sel = st.multiselect(
                "Match Day", mds_disponibles, default=mds_disponibles, label_visibility="collapsed"
            )
    else:
        md_sel = None

df_ses = df[(df["fecha"] == fecha_sel) & (df["tipo_sesion"] == tipo_sel)
            & (df["cuarto"] == cuarto_sel)]
if pos_sel is not None:
    df_ses = df_ses[df_ses["posicion"].isin(pos_sel)]
if md_sel is not None:
    df_ses = df_ses[df_ses["match_day"].isin(md_sel)]

st.divider()

# ── KPIs del equipo ────────────────────────────────────────────────────────
st.subheader("Equipo — Resumen de sesión")

st.markdown("""
<style>
.kpi-grid {
    display: flex;
    justify-content: center;
    gap: 16px;
    flex-wrap: wrap;
    margin-bottom: 8px;
}
.kpi-card {
    background: linear-gradient(135deg, #0f2b5b 0%, #1a3a6b 60%, #1e4d8c 100%);
    border-radius: 14px;
    padding: 20px 28px;
    text-align: center;
    min-width: 140px;
    box-shadow: 0 4px 15px rgba(0,0,0,0.25);
}
.kpi-card .kpi-label {
    font-size: 0.78rem;
    color: #93c5fd;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 6px;
}
.kpi-card .kpi-value {
    font-size: 1.6rem;
    font-weight: 700;
    color: #ffffff;
}
</style>
""", unsafe_allow_html=True)

kpis = [
    ("Jugadoras",         f"{len(df_ses)}"),
    ("Distancia media",   f"{df_ses['distancia_total'].mean():,.0f} m"),
    ("HSR media",         f"{df_ses['hsr'].mean():,.0f} m"),
    ("Player Load medio", f"{df_ses['player_load'].mean():,.1f}"),
    ("Vel. Máx media",    f"{df_ses['vel_max_kmh'].mean():,.1f} km/h"),
]

st.markdown(
    '<div class="kpi-grid">' + "".join(
        f'<div class="kpi-card"><div class="kpi-label">{l}</div>'
        f'<div class="kpi-value">{v}</div></div>'
        for l, v in kpis
    ) + '</div>',
    unsafe_allow_html=True,
)

st.divider()

# ── Config gráficos ────────────────────────────────────────────────────────
BG       = "#0d1b3e"
GRID_COL = "#1a2f5a"
FONT_COL = "#e2e8f0"

METRICAS = {
    "Distancia total (m)": ("distancia_total", "%{text:,.0f} m", ["#1e3a8a", "#60a5fa", "#bfdbfe"]),
    "Player Load":         ("player_load",     "%{text:.1f}",    ["#064e3b", "#34d399", "#a7f3d0"]),
    "HSR Distance (m)":    ("hsr",             "%{text:.0f} m",  ["#78350f", "#fbbf24", "#fef3c7"]),
    "Sprints":             ("sprints",         "%{text:.0f}",    ["#7f1d1d", "#f87171", "#fee2e2"]),
    "Vel. Máx (km/h)":     ("vel_max_kmh",     "%{text:.1f}",    ["#4c1d95", "#a78bfa", "#ede9fe"]),
    "Dist/min (m/min)":    ("dist_min",        "%{text:.1f}",    ["#0c4a6e", "#38bdf8", "#e0f2fe"]),
    "Player Load/min":     ("pl_min",          "%{text:.2f}",    ["#052e16", "#4ade80", "#dcfce7"]),
    "ACC >3 (m/s²)":       ("acc_3",           "%{text:.0f}",    ["#431407", "#fb923c", "#ffedd5"]),
    "DECC >3 (m/s²)":      ("decc_3",          "%{text:.0f}",    ["#422006", "#fcd34d", "#fef9c3"]),
}


def _dark_layout(height):
    return dict(
        height=height,
        showlegend=False,
        coloraxis_showscale=False,
        plot_bgcolor=BG,
        paper_bgcolor=BG,
        font=dict(color=FONT_COL),
        xaxis=dict(showgrid=True, gridcolor=GRID_COL, color=FONT_COL,
                   zerolinecolor=GRID_COL),
        yaxis=dict(color=FONT_COL),
        margin=dict(l=10, r=60, t=10, b=10),
    )


def _bar_chart(data, col, label, fmt, scale, height):
    fig = px.bar(
        data.sort_values(col, ascending=True),
        x=col, y="nombre",
        orientation="h",
        color=col,
        color_continuous_scale=scale,
        labels={col: label, "nombre": ""},
        text=col,
    )
    fig.update_traces(texttemplate=fmt, textposition="outside",
                      textfont=dict(color=FONT_COL))
    fig.update_layout(**_dark_layout(height))
    return fig


# ── Gráfico principal ──────────────────────────────────────────────────────
sel_principal = st.selectbox("Métrica", list(METRICAS.keys()), key="sel_principal")
col_p, fmt_p, scale_p = METRICAS[sel_principal]
st.subheader(sel_principal)
st.plotly_chart(_bar_chart(df_ses, col_p, sel_principal, fmt_p, scale_p, 420),
                use_container_width=True)

# ── Dos columnas con selector independiente ────────────────────────────────
col_izq, col_der = st.columns(2)

with col_izq:
    sel_izq = st.selectbox("Métrica", list(METRICAS.keys()), index=1, key="sel_izq")
    col_i, fmt_i, scale_i = METRICAS[sel_izq]
    st.subheader(sel_izq)
    st.plotly_chart(_bar_chart(df_ses, col_i, sel_izq, fmt_i, scale_i, 360),
                    use_container_width=True)

with col_der:
    sel_der = st.selectbox("Métrica", list(METRICAS.keys()), index=2, key="sel_der")
    col_d, fmt_d, scale_d = METRICAS[sel_der]
    st.subheader(sel_der)
    st.plotly_chart(_bar_chart(df_ses, col_d, sel_der, fmt_d, scale_d, 360),
                    use_container_width=True)

st.divider()

# ── Comparativa entre jugadoras ────────────────────────────────────────────
st.subheader("Comparativa entre jugadoras")

COMPARAR_METRICAS = [
    ("Distancia total", "distancia_total", "{:,.0f} m"),
    ("Player Load",     "player_load",     "{:.1f}"),
    ("HSR Distance",    "hsr",             "{:.0f} m"),
    ("Sprints",         "sprints",         "{:.0f}"),
    ("Vel. Máx",        "vel_max_kmh",     "{:.1f} km/h"),
    ("Dist/min",        "dist_min",        "{:.1f} m/min"),
]
COLOR_A = "#3987e5"   # azul  — misma familia que el resto del dashboard
COLOR_B = "#199e70"   # verde azulado — validado contra el fondo oscuro (CVD ΔE 69.8)

jugadoras_ses = sorted(df_ses["nombre"].unique())

if len(jugadoras_ses) < 2:
    st.info("Se necesitan al menos 2 jugadoras en la sesión filtrada para comparar.")
else:
    st.markdown("""
    <style>
    .cmp-card {
        border-radius: 14px;
        padding: 22px 12px;
        text-align: center;
        background: linear-gradient(135deg, #0f2b5b 0%, #1a3a6b 60%, #1e4d8c 100%);
        border-top: 4px solid var(--accent);
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    }
    .cmp-avatar { font-size: 2.4rem; margin-bottom: 8px; }
    .cmp-name   { font-size: 0.92rem; font-weight: 700; color: #fff;
                  text-transform: uppercase; letter-spacing: 0.02em; }

    .cmp-row { display: flex; align-items: center; gap: 8px; margin-bottom: 14px; }
    .cmp-value { width: 72px; font-size: 0.82rem; font-weight: 700; color: #e2e8f0; }
    .cmp-value-a { text-align: right; }
    .cmp-value-b { text-align: left; }
    .cmp-label  {
        width: 130px; flex-shrink: 0; text-align: center;
        font-size: 0.74rem; color: #93c5fd; text-transform: uppercase;
        letter-spacing: 0.04em;
    }
    .cmp-bar-a, .cmp-bar-b {
        flex: 1; display: flex; height: 12px;
        background: #16294f; border-radius: 6px;
    }
    .cmp-bar-a { justify-content: flex-end; }
    .cmp-bar-b { justify-content: flex-start; }
    .cmp-fill-a, .cmp-fill-b { height: 100%; }
    .cmp-fill-a { background: var(--color-a); border-radius: 4px 0 0 4px; }
    .cmp-fill-b { background: var(--color-b); border-radius: 0 4px 4px 0; }
    </style>
    """, unsafe_allow_html=True)

    col_sel_a, _, col_sel_b = st.columns([1, 0.1, 1])
    with col_sel_a:
        jugadora_a = st.selectbox("Jugadora A", jugadoras_ses, index=0, key="cmp_a")
    with col_sel_b:
        idx_b = 1 if len(jugadoras_ses) > 1 else 0
        jugadora_b = st.selectbox("Jugadora B", jugadoras_ses, index=idx_b, key="cmp_b")

    fila_a = df_ses[df_ses["nombre"] == jugadora_a].iloc[0]
    fila_b = df_ses[df_ses["nombre"] == jugadora_b].iloc[0]

    col_card_a, col_rows, col_card_b = st.columns([1, 2.2, 1])

    with col_card_a:
        st.markdown(
            f'<div class="cmp-card" style="--accent:{COLOR_A}">'
            f'<div class="cmp-avatar">🏑</div>'
            f'<div class="cmp-name">{jugadora_a}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    with col_rows:
        rows_html = ""
        for label, col, fmt in COMPARAR_METRICAS:
            val_a = fila_a.get(col)
            val_b = fila_b.get(col)
            val_a = 0.0 if pd.isna(val_a) else float(val_a)
            val_b = 0.0 if pd.isna(val_b) else float(val_b)
            maximo = max(val_a, val_b, 1e-9)
            pct_a  = (val_a / maximo) * 100
            pct_b  = (val_b / maximo) * 100

            rows_html += (
                f'<div class="cmp-row">'
                f'<div class="cmp-value cmp-value-a">{fmt.format(val_a)}</div>'
                f'<div class="cmp-bar-a"><div class="cmp-fill-a" '
                f'style="width:{pct_a:.1f}%; --color-a:{COLOR_A}"></div></div>'
                f'<div class="cmp-label">{label}</div>'
                f'<div class="cmp-bar-b"><div class="cmp-fill-b" '
                f'style="width:{pct_b:.1f}%; --color-b:{COLOR_B}"></div></div>'
                f'<div class="cmp-value cmp-value-b">{fmt.format(val_b)}</div>'
                f'</div>'
            )
        st.markdown(rows_html, unsafe_allow_html=True)

    with col_card_b:
        st.markdown(
            f'<div class="cmp-card" style="--accent:{COLOR_B}">'
            f'<div class="cmp-avatar">🏑</div>'
            f'<div class="cmp-name">{jugadora_b}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.caption("Cada métrica se compara en su propia escala (barra más larga = valor más alto entre las dos). Foto pendiente — por ahora, tarjeta con el nombre.")

st.divider()

# ── Tabla detallada ────────────────────────────────────────────────────────
st.subheader("Tabla completa de la sesión")
cols_tabla = ["nombre", "duracion_min", "distancia_total",
              "dist_min", "hsr", "hsr_pct", "sprints",
              "acc_3", "decc_3", "player_load", "pl_min", "vel_max_kmh"]
st.dataframe(
    df_ses[cols_tabla].sort_values("distancia_total", ascending=False)
                      .reset_index(drop=True),
    use_container_width=True,
    hide_index=True,
)
