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
from settings import FOTOS_DIR, ZSCORE_ALERTA
from src.ui.theme import COMPARE_COLOR_A, COMPARE_COLOR_B, ZONE_CFG, PARAMETRO_CFG, READINESS_CFG


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


def section_title(text: str, color: str, icon: str | None = None) -> None:
    """
    Título de sección chico — barra de acento + ícono opcional + texto en
    mayúsculas — para anteceder un grupo de tarjetas (ej. los KPIs de Perfil
    Jugadora) sin competir con los st.subheader() "grandes" de la página
    (ACWR, Partidos jugados, etc.). `icon` es una entrada de ICONS (SVG),
    igual que page_header() y nav_card().
    """
    icon_html = f'<span class="cn-section-title-icon">{icon}</span>' if icon else ""
    st.markdown(
        f'<div class="cn-section-title" style="--accent:{color}">'
        f'<span class="cn-section-title-bar"></span>'
        f'{icon_html}'
        f'<span class="cn-section-title-text">{text}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )


def presentacion_title(title: str, subtitle: str, gradient: list[str]) -> None:
    """
    Título "hero" exclusivo de pages/07_presentacion.py — envuelto en
    .cn-presentacion-hero (tarjeta con borde de degradado animado, ver
    theme.py) con el texto en degradado que recorre `gradient` adentro, en
    vez del page_header() plano que usan las otras 6 páginas: ese componente
    es compartido, así que un efecto único acá no lo toca.
    """
    gradient_css = ", ".join(gradient)
    st.markdown(
        f'<div class="cn-presentacion-hero" style="--title-gradient: linear-gradient(90deg, {gradient_css})">'
        f'<div class="cn-page-header">'
        f'<h1 class="cn-presentacion-title">{title}</h1>'
        f'<p class="cn-page-header-subtitle">{subtitle}</p>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def slide_pilares_html(headline: str, lead: str, cards: list[dict], footer: str,
                        headline_color: str = "#34A853", icon: str | None = None) -> None:
    """
    Layout de "3 tarjetas" reusado por todas las slides de pages/07_presentacion.py
    — ícono opcional en chip arriba del título (mismo lenguaje visual que
    slide_html()/page_header()), titular grande + bajada, grilla de 3 tarjetas
    (cada una con su propio color de acento) y un mensaje de cierre, todo
    dentro del mismo marco .cn-slide-card que usa slide_html().

    cards = [{"label", "subtitle", "body", "color"}, ...] — `body` es un
    párrafo (str) o una lista de bullets (list[str]).
    `headline_color` deja que cada slide tiña el titular (y el chip del
    ícono, si se pasa) con su propio acento temático (verde para "cuidado",
    azul para GPS, etc.). `icon` es una entrada de ICONS (SVG), como en
    slide_html() — el div NO es flex acá, por eso el chip se centra con
    margin:auto en vez de heredarlo del contenedor.
    """
    icon_html = (
        f'<div class="cn-slide-icon" style="--accent:{headline_color}; margin:0 auto 14px">{icon}</div>'
        if icon else ""
    )

    def _body_html(body) -> str:
        if isinstance(body, list):
            items = "".join(f"<li>{b}</li>" for b in body)
            return f'<ul class="cn-pilar-list">{items}</ul>'
        return f'<p class="cn-pilar-body">{body}</p>'

    cards_html = "".join(
        f'<div class="cn-pilar-card" style="--accent:{c["color"]}">'
        f'<div class="cn-pilar-label">{c["label"]}</div>'
        f'<div class="cn-pilar-subtitle">{c["subtitle"]}</div>'
        f'{_body_html(c["body"])}'
        f'</div>'
        for c in cards
    )
    st.markdown(
        f'<div class="cn-slide-card" style="--accent:#bfdbfe">'
        f'{icon_html}'
        f'<h2 class="cn-pilar-headline" style="color:{headline_color}">{headline}</h2>'
        f'<p class="cn-pilar-lead">{lead}</p>'
        f'<div class="cn-pilar-grid">{cards_html}</div>'
        f'<p class="cn-pilar-footer">{footer}</p>'
        f'</div>',
        unsafe_allow_html=True,
    )


def slide_html(icon: str, color: str, eyebrow: str, title: str, body: list[str]) -> None:
    """
    Renderiza una slide de la Presentación institucional (pages/07_presentacion.py)
    como una tarjeta grande centrada, navegada de a una por vez con
    Anterior/Siguiente — pensada para proyectarse durante una charla en vivo
    con las jugadoras, no para scrollear.

    `icon` es una entrada de ICONS (SVG), igual que en page_header()/nav_card().
    `body` es una lista de párrafos (no un solo bloque de texto) para poder
    cortar las ideas en oraciones cortas, más fáciles de leer proyectadas.
    """
    paragraphs = "".join(f"<p>{p}</p>" for p in body)
    st.markdown(
        f'<div class="cn-slide-card" style="--accent:{color}">'
        f'<div class="cn-slide-icon">{icon}</div>'
        f'<div class="cn-slide-eyebrow">{eyebrow}</div>'
        f'<h2 class="cn-slide-title">{title}</h2>'
        f'<div class="cn-slide-body">{paragraphs}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def kpi_row(items: list[tuple[str, str, object, str]]) -> None:
    """
    Renderiza una fila de tarjetas KPI con ícono en chip de color, borde
    superior a juego y hover al pasar el mouse — un solo componente para
    KPIs de equipo (Carga Física, Wellness) y de una jugadora individual
    (Perfil de Jugadora).

    items = [(icono, label, valor, color_acento), ...] — color_acento en
    hex, pensado para usarse con BAR_CATEGORICAL_PALETTE (ya validada
    contra el fondo oscuro del dashboard) o con el color semántico que
    corresponda (ej. READINESS_CFG para zonas de wellness).
    """
    st.markdown(
        '<div class="cn-kpi-grid">' + "".join(
            f'<div class="cn-kpi-card" style="--accent:{color}">'
            f'<div class="cn-kpi-icon">{icon}</div>'
            f'<div class="cn-kpi-label">{label}</div>'
            f'<div class="cn-kpi-value">{value}</div>'
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


def acwr_leyenda_html(optimo_min: float, optimo_max: float) -> str:
    """
    Leyenda del Ratio A:C en lenguaje simple: qué significa + las 3 zonas de
    color (subcarga, óptimo, sobrecarga) — pensada para que las jugadoras la
    entiendan de un vistazo en la presentación, reemplaza la explicación
    técnica anterior ("banda sombreada", "Hulin et al."). `optimo_min` /
    `optimo_max` son ACWR_OPTIMO_MIN/MAX (settings.py), los mismos umbrales
    que ya dibuja _lineas_umbral_acwr() en los gráficos de arriba — "Sobrecarga"
    junta ahí las dos zonas de riesgo del gráfico (Precaución + Riesgo Alto)
    en una sola categoría, para no abrumar con 4 niveles distintos.
    """
    zonas = [
        ("Subcarga", ZONE_CFG["Subcarga"]["color"], f"por debajo de {optimo_min}",
         "Entrenaste menos de lo habitual"),
        ("Óptimo", ZONE_CFG["Óptimo"]["color"], f"entre {optimo_min} y {optimo_max}",
         "Carga bien equilibrada — la zona ideal"),
        ("Sobrecarga", ZONE_CFG["Riesgo Alto"]["color"], f"por encima de {optimo_max}",
         "Carga muy por encima de lo habitual, más riesgo de lesión"),
    ]
    zonas_html = "".join(
        f'<div class="cn-acwr-leyenda-item">'
        f'<div class="cn-acwr-leyenda-dot" style="background:{color}"></div>'
        f'<div class="cn-acwr-leyenda-texto">'
        f'<span class="cn-acwr-leyenda-label" style="color:{color}">{nombre} <span class="cn-acwr-leyenda-rango">({rango})</span></span>'
        f'<span class="cn-acwr-leyenda-desc">{desc}</span>'
        f'</div></div>'
        for nombre, color, rango, desc in zonas
    )
    return (
        f'<div class="cn-acwr-leyenda">'
        f'<p class="cn-acwr-leyenda-intro">El <b>Ratio A:C</b> compara tu carga de esta '
        f'semana (Agudo) contra tu promedio de las últimas 4 semanas (Crónico) — muestra '
        f'si tu cuerpo está preparado para el esfuerzo actual.</p>'
        f'<div class="cn-acwr-leyenda-zonas">{zonas_html}</div>'
        f'</div>'
    )


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


def hero_foto_html(foto_path: Path | str | None = None) -> str:
    """
    Foto circular grande para la cabecera "hero" de Perfil Jugadora (ver
    pages/05_perfil_jugadora.py) — placeholder cuando la jugadora todavía no
    tiene foto en assets/jugadoras/. El color de borde viene de --accent,
    heredado del contenedor padre (.st-key-cn-perfil-hero en theme.py).
    """
    if foto_path and Path(foto_path).exists():
        b64 = base64.b64encode(Path(foto_path).read_bytes()).decode()
        ext = Path(foto_path).suffix.lstrip(".") or "jpeg"
        return f'<img class="cn-hero-foto" src="data:image/{ext};base64,{b64}"/>'
    return '<div class="cn-hero-foto cn-hero-foto-placeholder">🏑</div>'


def hero_info_html(name: str, posicion: str | None) -> str:
    """Nombre + badge de posición para la cabecera "hero" de Perfil Jugadora."""
    posicion_html = f'<div class="cn-hero-posicion">{posicion}</div>' if posicion else ""
    return f'<div class="cn-hero-name">{name}</div>{posicion_html}'


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
    <div style="margin-top:14px; font-size:0.75rem; color:#6b7280; line-height:1.6; text-align:center">
    <span style="color:{PARAMETRO_CFG['Por debajo']['color']}">●</span> Por debajo del rango &nbsp;
    <span style="color:{PARAMETRO_CFG['En rango']['color']}">●</span> En rango &nbsp;
    <span style="color:{PARAMETRO_CFG['Por encima']['color']}">●</span> Por encima del rango
    </div>
    """, unsafe_allow_html=True)


def analisis_asistente_html(analisis: dict) -> None:
    """
    Renderiza fortalezas/debilidades (ver generar_analisis() en
    src/metrics/analisis.py) en un expander DESPLEGADO por default, debajo
    de la tabla del Asistente — el usuario lo puede replegar si quiere, pero
    arranca visible para no tener que abrirlo cada vez. Sin nada que mostrar
    (sin fortalezas NI debilidades) no se renderiza el expander — evita un
    cajón vacío.

    Fortalezas: fila de chips verdes, solo el nombre. Debilidades: grilla de
    tarjetas (mismo lenguaje visual que las tarjetas de KPI/readiness ya
    existentes) — borde de color según `peor_estado`, badges semáforo por
    cada métrica evaluada (fuera de rango primero, después las que sí están
    en rango óptimo con el mismo tilde ✅ que ya usa el resto de la app) y la
    recomendación ya consolidada por jugadora, no una línea por métrica.
    """
    if not analisis["fortalezas"] and not analisis["debilidades"]:
        return

    def _badge(m: dict) -> str:
        cfg = PARAMETRO_CFG[m["estado"]]
        # z_score es un dato complementario al rango del Sheet — señala que
        # esta sesión también es atípica vs. el propio historial de la
        # jugadora, algo que el rango por posición no puede detectar (ver
        # calcular_zscore_historico en physical.py). Ausente/NaN cuando
        # todavía no hay suficiente historial (ZSCORE_MIN_SESIONES).
        z = m.get("z_score")
        marca_atipica = (
            f' <span title="Atípica vs. su historial (z={z:.1f})">⚡</span>'
            if pd.notna(z) and abs(z) >= ZSCORE_ALERTA else ""
        )
        return (f'<span class="cn-acwr-badge" style="background:{cfg["bg"]};'
                f'color:{cfg["color"]}">{cfg["icon"]} {m["metrica"]}: {m["valor_real"]:.0f}</span>'
                f'{marca_atipica}')

    with st.expander("📋 Análisis", expanded=True):
        if analisis["fortalezas"]:
            st.markdown("**✅ Fortalezas** — en rango en todas las métricas evaluadas:")
            cfg_ok = PARAMETRO_CFG["En rango"]
            # fortalezas_atipicas (ver generar_analisis en analisis.py) es
            # complementario: una jugadora en rango contra el Sheet puede
            # igual tener un pico atípico contra su propio historial — el
            # rango por posición no puede verlo, el z-score sí.
            atipicas_por_nombre = {
                f["nombre"]: f["metricas_atipicas"] for f in analisis.get("fortalezas_atipicas", [])
            }

            def _chip_fortaleza(nombre: str) -> str:
                metricas = atipicas_por_nombre.get(nombre)
                marca = ""
                if metricas:
                    detalle = ", ".join(
                        f"{m['metrica']} (z={m['z_score']:.1f})" for m in metricas
                    )
                    marca = f' <span title="Atípica vs. su historial: {detalle}">⚡</span>'
                return (f'<span class="cn-acwr-badge" style="background:{cfg_ok["bg"]};'
                        f'color:{cfg_ok["color"]}">{nombre}</span>{marca}')

            chips = "".join(_chip_fortaleza(nombre) for nombre in analisis["fortalezas"])
            st.markdown(f'<div class="cn-analisis-fortalezas">{chips}</div>', unsafe_allow_html=True)

        if analisis["debilidades"]:
            st.markdown("**⚠️ A vigilar:**")
            cards = ""
            for d in analisis["debilidades"]:
                accent = PARAMETRO_CFG[d["peor_estado"]]["color"]
                badges = "".join(_badge(m) for m in d["metricas_fuera"] + d["metricas_en_rango"])
                recos = "".join(f'<p class="cn-analisis-reco">{r}</p>' for r in d["recomendaciones"])
                cards += (
                    f'<div class="cn-analisis-card" style="--accent:{accent}">'
                    f'<div class="cn-analisis-nombre">{d["nombre"]}</div>'
                    f'<div class="cn-analisis-posicion">{d["posicion"]}</div>'
                    f'<div class="cn-analisis-badges">{badges}</div>'
                    f'{recos}'
                    f'</div>'
                )
            st.markdown(f'<div class="cn-analisis-grid">{cards}</div>', unsafe_allow_html=True)


def molestias_cards_html(df_molestias: pd.DataFrame) -> None:
    """
    Grilla de tarjetas para molestias físicas reportadas — una tarjeta por
    (jugadora, fecha) en vez de una fila de st.dataframe genérica. Mismo
    lenguaje visual que analisis_asistente_html().

    Espera columnas [fecha, molestia] y opcionalmente "nombre" — si no está
    (ej. Perfil de Jugadora, ya scopeado a una sola jugadora) la tarjeta
    omite ese renglón en vez de repetir un nombre que ya se ve en la página.
    No renderiza nada si el df está vacío; el caller decide el mensaje de
    "sin molestias".
    """
    if df_molestias.empty:
        return

    fmt_fecha = lambda f: f.strftime("%d/%m/%Y") if hasattr(f, "strftime") else str(f)
    tiene_nombre = "nombre" in df_molestias.columns

    cards = "".join(
        '<div class="cn-molestia-card">'
        + (f'<div class="cn-molestia-nombre">{row["nombre"]}</div>' if tiene_nombre else "")
        + f'<div class="cn-molestia-fecha">{fmt_fecha(row["fecha"])}</div>'
        + f'<div class="cn-molestia-detalle">⚠️ {row["molestia"]}</div>'
        + '</div>'
        for _, row in df_molestias.iterrows()
    )
    st.markdown(f'<div class="cn-molestia-grid">{cards}</div>', unsafe_allow_html=True)


_ALERTA_BADGES = [
    ("alerta_tqr_bajo",  lambda r: f"😴 TQR bajo: {r['tqr']:.1f}"),
    ("alerta_rpe_alto",  lambda r: f"🔥 RPE alto: {r['rpe']:.1f}"),
    ("alerta_readiness", lambda r: f"⚠️ Readiness: {r['readiness_index']:.1f}"),
    ("alerta_molestia",  lambda r: "🤕 Molestia"),
]


def alertas_cards_html(df_alertas: pd.DataFrame) -> None:
    """
    Grilla de tarjetas para alertas activas — una tarjeta por jugadora con
    un badge por cada alerta activa (ver generar_alertas() en
    src/metrics/wellness.py: TQR bajo, RPE alto, Readiness bajo, Molestia).

    Borde rojo (READINESS_CFG "No Apta") si tiene la alerta combinada —
    TQR bajo Y RPE alto a la vez, la más crítica — ámbar (READINESS_CFG
    "Precaución") en el resto. Espera las columnas que arma
    resumen_alertas_equipo(). No renderiza nada si el df está vacío.
    """
    if df_alertas.empty:
        return

    fmt_fecha = lambda f: f.strftime("%d/%m/%Y") if hasattr(f, "strftime") else str(f)
    cfg_alerta = READINESS_CFG["Precaución"]
    accent_critico = READINESS_CFG["No Apta"]["color"]
    accent_normal = cfg_alerta["color"]

    cards = ""
    for _, row in df_alertas.iterrows():
        accent = accent_critico if row.get("alerta_combinada") else accent_normal
        badges = "".join(
            f'<span class="cn-acwr-badge" style="background:{cfg_alerta["bg"]};'
            f'color:{cfg_alerta["color"]}">{texto(row)}</span>'
            for col, texto in _ALERTA_BADGES if row.get(col)
        )
        cards += (
            f'<div class="cn-alerta-card" style="--accent:{accent}">'
            f'<div class="cn-alerta-nombre">{row["nombre"]}</div>'
            f'<div class="cn-alerta-fecha">{fmt_fecha(row["fecha"])}</div>'
            f'<div class="cn-alerta-badges">{badges}</div>'
            f'</div>'
        )
    st.markdown(f'<div class="cn-alerta-grid">{cards}</div>', unsafe_allow_html=True)


def periodizacion_cards_html(items: list[tuple[str, list[str], str]],
                              ejercicios: dict[str, dict] | None = None) -> None:
    """
    Tarjetas de "Expectativa de periodización" (nota curada del cuerpo
    técnico sobre qué se espera de cada Match Day — ver _NOTAS_PERIODIZACION
    en pages/08_analisis.py). SIEMPRE visibles, no en un expander plegado: es
    el contexto de lectura para leer el resto del FODA (qué "debería" pasar
    en cada MD), no un detalle opcional que haya que acordarse de abrir.

    items = [(match_day, bullets, color_acento), ...] — `bullets` es una
    lista de puntos cortos (volumen, foco de trabajo, ACC/DECC, HSR/sprints),
    no un párrafo largo, para que se lea de un vistazo.

    `ejercicios` (opcional) = {match_day: {"fisico": [...], "tecnico_tactico":
    [...]}} — listas de viñetas ya armadas (ver dividir_en_bullets() en
    src/metrics/foda.py) desde la pestaña "MD_Ejercicios" del Sheet. Si un MD
    tiene datos, la tarjeta suma un st.popover con la propuesta de ejercicios
    Físico/Técnico-Táctico de ese día.

    A diferencia de foda_quadrant_html() (un solo bloque de HTML), acá cada
    tarjeta es st.container(key=...) + CSS inyectado por key — mismo patrón
    que nav_card() — porque un popover es un widget real de Streamlit, no se
    puede "meter" dentro de un string de HTML crudo.
    """
    cols = st.columns(len(items)) if items else []
    for col, (md, bullets, color) in zip(cols, items):
        key = f"cn-periodizacion-{md.lower().replace(' ', '-').replace('+', 'mas')}"
        with col:
            st.markdown(
                f'<style>.st-key-{key} {{ border-top: 4px solid {color}; }}</style>',
                unsafe_allow_html=True,
            )
            with st.container(key=key):
                st.markdown(
                    f'<span class="cn-periodizacion-md" style="--accent:{color}">{md}</span>'
                    '<ul class="cn-periodizacion-lista">'
                    + "".join(f"<li>{b}</li>" for b in bullets)
                    + '</ul>',
                    unsafe_allow_html=True,
                )
                datos_md = (ejercicios or {}).get(md)
                if datos_md and (datos_md.get("fisico") or datos_md.get("tecnico_tactico")):
                    with st.popover("📋 Ver propuesta de ejercicios", use_container_width=True):
                        st.markdown("**🏃 Físico**")
                        for b in datos_md.get("fisico") or []:
                            st.markdown(f"- {b}")
                        st.markdown("**🥅 Técnico-Táctico**")
                        for b in datos_md.get("tecnico_tactico") or []:
                            st.markdown(f"- {b}")


def foda_quadrant_html(fortalezas: list[str], debilidades: list[str],
                        oportunidades: list[str], amenazas: list[str]) -> None:
    """
    Grilla de 4 tarjetas (2x2 fijo, ver .cn-foda-grid en theme.py) para el
    FODA de entrenamientos de pages/08_analisis.py.

    Cada lista es una colección de bullets ya armados por la página (mezcla
    de hallazgos computados con el número real inline, ej. "ACC>2 por debajo
    del rango en 96% de las sesiones de MD-4", y notas curadas a mano sobre
    periodización/calibración) — este componente solo pinta, no decide
    contenido. Un cuadrante sin bullets muestra un placeholder en vez de
    quedar vacío, para que las 4 tarjetas siempre tengan la misma altura
    aproximada.

    Reutiliza la semántica de color ya establecida en el resto de la app en
    vez de inventar una paleta nueva para el FODA: Fortalezas = verde
    (ZONE_CFG "Óptimo"), Debilidades = rojo (ZONE_CFG "Riesgo Alto"),
    Oportunidades = celeste (ZONE_CFG "Subcarga"), Amenazas = ámbar
    (READINESS_CFG "Precaución").
    """
    cuadrantes = [
        ("💪 Fortalezas", fortalezas, ZONE_CFG["Óptimo"]["color"]),
        ("⚠️ Debilidades", debilidades, ZONE_CFG["Riesgo Alto"]["color"]),
        ("💡 Oportunidades", oportunidades, ZONE_CFG["Subcarga"]["color"]),
        ("🚧 Amenazas", amenazas, READINESS_CFG["Precaución"]["color"]),
    ]

    cards = ""
    for titulo, bullets, color in cuadrantes:
        if bullets:
            contenido = '<ul class="cn-foda-lista">' + "".join(
                f"<li>{b}</li>" for b in bullets
            ) + "</ul>"
        else:
            contenido = '<div class="cn-foda-vacio">Sin hallazgos con los filtros actuales.</div>'
        cards += (
            f'<div class="cn-foda-card" style="--accent:{color}">'
            f'<div class="cn-foda-titulo">{titulo}</div>'
            f'{contenido}'
            f'</div>'
        )
    st.markdown(f'<div class="cn-foda-grid">{cards}</div>', unsafe_allow_html=True)


# ── Tablas de datos estilizadas (zebra + máximo resaltado) ──────────────────

def zebra_rows(fila: pd.Series) -> list[str]:
    """Fondo apenas más claro en las filas impares — ayuda a no "perder la
    fila" en tablas largas. Genérico: sirve para cualquier tabla, aplicar
    vía `tabla.style.apply(zebra_rows, axis=1)` sobre un df con índice
    0..N-1 (reset_index(drop=True) antes si hace falta)."""
    color = "background-color: #16294f" if fila.name % 2 == 1 else ""
    return [color] * len(fila)


def resaltar_maximo_columna(col: pd.Series) -> list[str]:
    """Resalta el valor máximo de una columna numérica — el techo alcanzado
    en esa métrica, sin importar en qué fila haya sido. Aplicar DESPUÉS de
    zebra_rows en el Styler (`.apply(zebra_rows, axis=1).apply(resaltar_maximo_columna,
    subset=[...])`) para que ese fondo gane por encima del rayado en esa
    celda puntual."""
    es_maximo = (col == col.max()).fillna(False)
    estilo = "background-color: rgba(167,139,250,0.35); font-weight: 700; color: #ffffff"
    return [estilo if v else "" for v in es_maximo]


# Columnas/encabezados/redondeo del set estándar de métricas GPS por fila —
# compartido por cualquier tabla "una fila por jugadora o por partido"
# (Carga Física, Perfil de Jugadora, Partidos).
GPS_COLS_METRICAS = ["duracion_min", "distancia_total", "dist_min", "hsr", "hsr_pct",
                     "sprints", "acc_3", "decc_3", "player_load", "pl_min", "vel_max_kmh"]
GPS_ENCABEZADOS_METRICAS = ["Dur (min)", "Dist (m)", "Dist/min", "HSR (m)", "HSR %",
                            "Sprints", "ACC>3", "DECC>3", "Player Load", "PL/min", "Vel Máx (km/h)"]
GPS_REDONDEO_METRICAS = {"duracion_min": 0, "distancia_total": 0, "dist_min": 1, "hsr": 0,
                         "hsr_pct": 1, "sprints": 0, "acc_3": 0, "decc_3": 0,
                         "player_load": 1, "pl_min": 2, "vel_max_kmh": 1}
# Cantidades enteras de verdad (duración, metros redondeados, conteos) — sin
# esto quedan como float y muestran "44.0"/"0.0" en vez de "44"/"0".
GPS_COLS_ENTERAS_METRICAS = ["duracion_min", "distancia_total", "hsr", "sprints", "acc_3", "decc_3"]
GPS_COLUMN_CONFIG_METRICAS = {
    "Dur (min)":      st.column_config.NumberColumn(alignment="center"),
    "Dist (m)":       st.column_config.NumberColumn(alignment="center"),
    "Dist/min":       st.column_config.NumberColumn(alignment="center", format="%.1f"),
    "HSR (m)":        st.column_config.NumberColumn(alignment="center"),
    "HSR %":          st.column_config.NumberColumn(alignment="center", format="%.1f"),
    "Sprints":        st.column_config.NumberColumn(alignment="center"),
    "ACC>3":          st.column_config.NumberColumn(alignment="center"),
    "DECC>3":         st.column_config.NumberColumn(alignment="center"),
    "Player Load":    st.column_config.NumberColumn(alignment="center", format="%.1f"),
    "PL/min":         st.column_config.NumberColumn(alignment="center", format="%.2f"),
    "Vel Máx (km/h)": st.column_config.NumberColumn(alignment="center", format="%.1f"),
}


def formatear_tabla_gps(df: pd.DataFrame, cols_identidad: list[str],
                         encabezados_identidad: list[str]) -> pd.DataFrame:
    """
    Redondea (GPS_REDONDEO_METRICAS), castea a entero las columnas que
    corresponden (GPS_COLS_ENTERAS_METRICAS) y renombra a encabezados
    legibles el set estándar de métricas GPS — el df de entrada debe tener
    cols_identidad + GPS_COLS_METRICAS.

    Devuelve el df ya formateado, SIN estilo — aplicar zebra_rows/
    resaltar_maximo_columna después vía `.style.apply(...)` para la versión
    on-screen; el resultado de acá (sin estilizar) es el que hay que pasarle
    tal cual a SeccionTabla si también se exporta a PDF (mismo patrón que
    Partidos jugados en Perfil de Jugadora).
    """
    tabla = df[cols_identidad + GPS_COLS_METRICAS].copy()
    tabla = tabla.round(GPS_REDONDEO_METRICAS)
    cols_enteras = [c for c in GPS_COLS_ENTERAS_METRICAS if c in tabla.columns]
    tabla[cols_enteras] = tabla[cols_enteras].astype("Int64")
    tabla.columns = encabezados_identidad + GPS_ENCABEZADOS_METRICAS
    return tabla
