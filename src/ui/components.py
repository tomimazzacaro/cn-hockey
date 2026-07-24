# src/ui/components.py
"""
Componentes HTML/Streamlit reutilizables — encabezados, tarjetas de KPI, de
comparación y de navegación, tabla ACWR y tabla del Asistente de Parámetros.
Los colores/umbrales que consumen (COMPARE_COLOR_*, ZONE_CFG, PARAMETRO_CFG)
viven en theme.py junto con el resto de la paleta.
"""
import base64
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.append(str(Path(__file__).parent.parent.parent))
from settings import FOTOS_DIR
from src.ui.theme import COMPARE_COLOR_A, COMPARE_COLOR_B, ZONE_CFG, PARAMETRO_CFG


def home_button() -> None:
    """
    Link "🏠 Home" alineado arriba a la derecha para volver a app.py.
    Llamar al principio de cada página (después de require_login(),
    antes del título) — no en app.py, que ya es la home.
    """
    _, col_home = st.columns([6, 1])
    with col_home:
        with st.container(key="cn-home-link"):
            st.page_link("app.py", label="Home", icon="🏠", use_container_width=True)


def page_header(title: str, subtitle: str | None = None,
                 icon: str | None = None, color: str | None = None) -> None:
    """
    Encabezado de página compartido: ícono en chip de color + título grande
    + subtítulo opcional debajo, reemplazando el st.title()/<h1> suelto que
    cada página armaba por su cuenta. `color` es el mismo acento que la
    tarjeta de esa sección en home (ver nav_card()). Ícono y texto quedan
    pegados como un solo grupo, centrado en la página — pasar icon=None
    (ej. Overview) omite el chip y solo centra el título.
    """
    icon_html = (
        f'<div class="cn-page-header-icon" style="--accent:{color}">{icon}</div>'
        if icon else ""
    )
    subtitle_html = f'<p class="cn-page-header-subtitle">{subtitle}</p>' if subtitle else ""
    st.markdown(
        f'<div class="cn-page-header">'
        f'{icon_html}'
        f'<div class="cn-page-header-text">'
        f'<h1 class="cn-page-header-title">{title}</h1>'
        f'{subtitle_html}'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def render_kpi_row(items: list[tuple[str, object]]) -> None:
    """Renderiza una fila de tarjetas KPI. items = [(label, value), ...]."""
    st.markdown(
        '<div class="cn-kpi-grid">' + "".join(
            f'<div class="cn-kpi-card"><div class="lbl">{label}</div>'
            f'<div class="val">{value}</div></div>'
            for label, value in items
        ) + '</div>',
        unsafe_allow_html=True,
    )


def player_kpi_row(items: list[tuple[str, str, str, str]]) -> None:
    """
    Renderiza una fila de tarjetas KPI de jugadora con ícono acentuado.
    items = [(icono, label, valor, color_acento), ...] — color_acento en hex,
    pensado para usarse con BAR_CATEGORICAL_PALETTE (ya validada contra el
    fondo oscuro del dashboard).
    """
    st.markdown(
        '<div class="cn-player-kpi-grid">' + "".join(
            f'<div class="cn-player-kpi-card" style="--accent:{color}">'
            f'<div class="cn-player-kpi-icon">{icon}</div>'
            f'<div class="cn-player-kpi-label">{label}</div>'
            f'<div class="cn-player-kpi-value">{value}</div>'
            f'</div>'
            for icon, label, value, color in items
        ) + '</div>',
        unsafe_allow_html=True,
    )


def nav_card(key: str, page: str, icon: str, title: str, subtitle: str, color: str) -> None:
    """
    Tarjeta de navegación clickeable para la home.

    Usa st.page_link (navegación real de Streamlit) en vez de un
    <div onclick="window.location.href=...">: ese onclick corre dentro del
    iframe aislado del componente de markdown y navega el iframe, no la app
    — por eso el click no llevaba a ningún lado. st.container(key=...)
    expone una clase CSS estable ("st-key-<key>") que sí podemos estilizar.

    `icon` es una entrada de ICONS (SVG), no un emoji — por eso se renderiza
    en su propio st.markdown (unsafe_allow_html) reusando el chip con tinte
    de page_header(), en vez de ir pegado al label de st.page_link (ese label
    no soporta HTML crudo, solo texto/markdown básico).
    """
    st.markdown(
        f'<style>.st-key-{key} {{ border-top: 4px solid {color}; }}</style>',
        unsafe_allow_html=True,
    )
    with st.container(key=key):
        st.markdown(
            f'<div class="cn-page-header-icon" style="--accent:{color}; margin:0 auto 10px">'
            f'{icon}</div>',
            unsafe_allow_html=True,
        )
        st.page_link(page, label=f"**{title}**", use_container_width=True)
        st.caption(subtitle)


def foto_jugadora_path(player_id: str) -> Path | None:
    """
    Devuelve la ruta de la foto de una jugadora si existe en assets/jugadoras/
    (nombrada por su player_id canónico, ver normalizar_nombre()), o None si
    todavía no se cargó su foto — no todas las jugadoras tienen una.
    """
    for ext in ("jpg", "jpeg", "png", "webp"):
        ruta = FOTOS_DIR / f"{player_id}.{ext}"
        if ruta.exists():
            return ruta
    return None


def compare_card_html(icon: str, name: str, color: str,
                       foto_path: Path | str | None = None) -> str:
    """
    Tarjeta de cabecera para un lado de una comparación A/B (jugadora o tipo
    de sesión). Si se pasa foto_path (ver foto_jugadora_path()) y el archivo
    existe, se muestra esa foto en vez del ícono/emoji.
    """
    if foto_path and Path(foto_path).exists():
        b64 = base64.b64encode(Path(foto_path).read_bytes()).decode()
        ext = Path(foto_path).suffix.lstrip(".") or "jpeg"
        avatar_html = f'<img class="cn-cmp-avatar-foto" src="data:image/{ext};base64,{b64}"/>'
    else:
        avatar_html = f'<div class="cn-cmp-avatar">{icon}</div>'
    return (
        f'<div class="cn-cmp-card" style="--accent:{color}">'
        f'{avatar_html}'
        f'<div class="cn-cmp-name">{name}</div>'
        f'</div>'
    )


def compare_rows_html(metrics: list[tuple[str, str, str]],
                       valores_a, valores_b,
                       color_a: str = COMPARE_COLOR_A,
                       color_b: str = COMPARE_COLOR_B) -> str:
    """
    Genera las filas de barras comparativas A/B.
    metrics: [(label, columna, formato), ...]
    valores_a/valores_b: objetos con .get(columna) -> valor numérico (Series o dict).
    """
    rows_html = ""
    for label, col, fmt in metrics:
        val_a = valores_a.get(col)
        val_b = valores_b.get(col)
        val_a = 0.0 if pd.isna(val_a) else float(val_a)
        val_b = 0.0 if pd.isna(val_b) else float(val_b)
        maximo = max(val_a, val_b, 1e-9)
        pct_a = (val_a / maximo) * 100
        pct_b = (val_b / maximo) * 100

        rows_html += (
            f'<div class="cn-cmp-row">'
            f'<div class="cn-cmp-value cn-cmp-value-a">{fmt.format(val_a)}</div>'
            f'<div class="cn-cmp-bar-a"><div class="cn-cmp-fill-a" '
            f'style="width:{pct_a:.1f}%; --color-a:{color_a}"></div></div>'
            f'<div class="cn-cmp-label">{label}</div>'
            f'<div class="cn-cmp-bar-b"><div class="cn-cmp-fill-b" '
            f'style="width:{pct_b:.1f}%; --color-b:{color_b}"></div></div>'
            f'<div class="cn-cmp-value cn-cmp-value-b">{fmt.format(val_b)}</div>'
            f'</div>'
        )
    return rows_html


def acwr_table_html(df: pd.DataFrame, n_registros: int | None = None) -> None:
    """
    Renderiza la tabla ACWR por jugadora con semáforo de zona de riesgo.
    Espera columnas [nombre, acwr, zona_acwr] en df (una fila por jugadora,
    ya reducida al último registro).
    """
    if n_registros is not None and n_registros < 4:
        st.caption(f"⚠️ Solo {n_registros} registro/s — el ACWR gana precisión a partir de 4+.")

    rows_html = ""
    for _, row in df.sort_values("acwr", ascending=False).iterrows():
        zona = row.get("zona_acwr", "Sin datos")
        cfg = ZONE_CFG.get(zona, ZONE_CFG["Sin datos"])
        acwr_val = f"{row['acwr']:.2f}" if pd.notna(row.get("acwr")) else "—"
        rows_html += (
            f'<tr>'
            f'<td>{row["nombre"]}</td>'
            f'<td style="font-weight:700;color:{cfg["color"]}">{acwr_val}</td>'
            f'<td><span class="cn-acwr-badge" style="background:{cfg["bg"]};'
            f'color:{cfg["color"]}">{zona}</span></td>'
            f'</tr>'
        )
    st.markdown(
        f'<table class="cn-acwr-table">'
        f'<thead><tr><th>Jugadora</th><th>ACWR</th><th>Zona</th></tr></thead>'
        f'<tbody>{rows_html}</tbody>'
        f'</table>',
        unsafe_allow_html=True,
    )
    st.markdown(f"""
    <div style="margin-top:14px; font-size:0.75rem; color:#6b7280; line-height:1.6">
    <span style="color:{ZONE_CFG['Subcarga']['color']}">●</span> Subcarga &lt;0.8 &nbsp;
    <span style="color:{ZONE_CFG['Óptimo']['color']}">●</span> Óptimo 0.8–1.3 &nbsp;
    <span style="color:{ZONE_CFG['Precaución']['color']}">●</span> Precaución 1.3–1.5 &nbsp;
    <span style="color:{ZONE_CFG['Riesgo Alto']['color']}">●</span> Riesgo &gt;1.5
    </div>
    """, unsafe_allow_html=True)


def tabla_asistente_html(df_evaluacion: pd.DataFrame, etiqueta_header: str = "Jugadora") -> None:
    """
    Renderiza la grilla del Asistente de Parámetros (Etiqueta × Métrica),
    con semáforo por celda (ver evaluar_sesiones/armar_evaluacion_equipo en
    src/metrics/parametros.py).

    Espera columnas [etiqueta, metrica, valor_real, rango_min, rango_max,
    estado] en formato largo — acá se pivotea a una tabla ancha. `etiqueta`
    es "Jugadora" en una sesión de equipo (Carga Física) o una fecha/MD en
    el historial de una sola jugadora (Perfil de Jugadora) — `etiqueta_header`
    solo cambia el título de esa primera columna.
    """
    if df_evaluacion.empty:
        st.info(
            "Sin parámetros cargados todavía para el Match Day y las "
            "posiciones correspondientes."
        )
        return

    metricas = list(dict.fromkeys(df_evaluacion["metrica"]))  # preserva orden de aparición
    encabezados = "".join(f"<th>{m}</th>" for m in metricas)

    rows_html = ""
    for etiqueta, grupo in df_evaluacion.groupby("etiqueta", sort=False):
        fila_por_metrica = grupo.set_index("metrica")
        celdas = ""
        for m in metricas:
            if m not in fila_por_metrica.index:
                celdas += '<td>—</td>'
                continue
            fila = fila_por_metrica.loc[m]
            if isinstance(fila, pd.DataFrame):
                # Dos filas de origen distintas colisionaron en la misma
                # etiqueta (ej. Físico y Técnico-Táctico el mismo día sin
                # tipo_sesion en la etiqueta) — mostrar la primera es mejor
                # que romper toda la tabla; el fix de fondo es una etiqueta
                # única en el llamador.
                fila = fila.iloc[0]
            cfg = PARAMETRO_CFG.get(fila["estado"], PARAMETRO_CFG["Sin dato"])
            valor_str = f"{fila['valor_real']:.0f}" if pd.notna(fila["valor_real"]) else "—"
            celdas += (
                f'<td><span class="cn-acwr-badge" style="background:{cfg["bg"]};'
                f'color:{cfg["color"]}">{cfg["icon"]} {valor_str}</span></td>'
            )
        rows_html += f'<tr><td>{etiqueta}</td>{celdas}</tr>'

    st.markdown(
        f'<table class="cn-acwr-table">'
        f'<thead><tr><th>{etiqueta_header}</th>{encabezados}</tr></thead>'
        f'<tbody>{rows_html}</tbody>'
        f'</table>',
        unsafe_allow_html=True,
    )
    st.markdown(f"""
    <div style="margin-top:14px; font-size:0.75rem; color:#6b7280; line-height:1.6">
    <span style="color:{PARAMETRO_CFG['Por debajo']['color']}">●</span> Por debajo del rango &nbsp;
    <span style="color:{PARAMETRO_CFG['En rango']['color']}">●</span> En rango &nbsp;
    <span style="color:{PARAMETRO_CFG['Por encima']['color']}">●</span> Por encima del rango
    </div>
    """, unsafe_allow_html=True)
