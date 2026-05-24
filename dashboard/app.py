"""
Streamlit Dashboard  –  Spotify Insights
─────────────────────────────────────────────────────────────────────────────
Reads Gold-layer Parquet files and presents every insight with rich,
interactive Plotly charts.

Run:
    streamlit run dashboard/app.py
─────────────────────────────────────────────────────────────────────────────
"""

import json
from pathlib import Path
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ── Config ─────────────────────────────────────────────────────────────────────
BASE_DIR  = Path(__file__).resolve().parent.parent
GOLD_PATH = BASE_DIR / "bucket" / "reproduccion" / "gold"

st.set_page_config(
    page_title="Spotify Insights",
    page_icon="🎧",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Spotify-esque colour palette ───────────────────────────────────────────────
GREEN   = "#1DB954"
BLACK   = "#191414"
WHITE   = "#FFFFFF"
GRAY    = "#B3B3B3"
PALETTE = [GREEN, "#17A349", "#6BCB77", "#4D96FF", "#FF6B6B",
           "#FFD93D", "#C77DFF", "#F4845F", "#26C6DA"]

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Background */
    [data-testid="stAppViewContainer"] { background-color: #121212; }
    [data-testid="stSidebar"]          { background-color: #000000; }

    /* Main text */
    html, body, [class*="css"] { color: #FFFFFF; font-family: 'Circular', 'Helvetica Neue', sans-serif; }

    /* Metric cards */
    [data-testid="metric-container"] {
        background: #1E1E1E;
        border: 1px solid #2A2A2A;
        border-radius: 12px;
        padding: 16px;
    }
    [data-testid="stMetricValue"] { color: #1DB954 !important; font-size: 2rem !important; }

    /* Headers */
    h1 { color: #1DB954 !important; }
    h2, h3 { color: #FFFFFF !important; }

    /* Tabs */
    .stTabs [data-baseweb="tab"] { color: #B3B3B3; }
    .stTabs [aria-selected="true"] { color: #1DB954 !important; border-bottom: 2px solid #1DB954; }

    /* Dividers */
    hr { border-color: #2A2A2A; }

    /* Plotly chart backgrounds override */
    .js-plotly-plot { border-radius: 12px; }

    /* Sidebar labels */
    .css-1d391kg { color: #B3B3B3; }
</style>
""", unsafe_allow_html=True)


# ── Helpers ────────────────────────────────────────────────────────────────────

def dark_layout(fig: go.Figure, title: str = "", height: int = 400) -> go.Figure:
    fig.update_layout(
        title=dict(text=title, font=dict(color=WHITE, size=16)),
        paper_bgcolor="#1E1E1E",
        plot_bgcolor="#1E1E1E",
        font=dict(color=GRAY),
        height=height,
        margin=dict(l=10, r=10, t=50, b=10),
        legend=dict(bgcolor="#1E1E1E", bordercolor="#2A2A2A"),
        xaxis=dict(gridcolor="#2A2A2A", zerolinecolor="#2A2A2A"),
        yaxis=dict(gridcolor="#2A2A2A", zerolinecolor="#2A2A2A"),
    )
    return fig


@st.cache_data
def read_parquet(name: str) -> pd.DataFrame | None:
    path = GOLD_PATH / name
    if not path.exists():
        return None
    try:
        return pd.read_parquet(path)
    except Exception:
        return None


def no_data(name: str):
    st.info(f"⚙️  Datos no disponibles todavía para **{name}**. Ejecuta el pipeline primero.", icon="ℹ️")


MESES_ES = {
    1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic",
}

DIAS_ES = {
    1: "Dom", 2: "Lun", 3: "Mar", 4: "Mié", 5: "Jue", 6: "Vie", 7: "Sáb"
}


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 🎧 Spotify Insights")
    st.markdown("---")
    pipeline_ready = GOLD_PATH.exists() and any(GOLD_PATH.iterdir()) if GOLD_PATH.exists() else False

    if pipeline_ready:
        st.success("Pipeline ✓ listo", icon="✅")
    else:
        st.warning("Pipeline no ejecutado aún", icon="⚠️")
        st.markdown("""
**Para ejecutar el pipeline:**
```bash
cd spotify_pipeline
python run_pipeline.py --generate-data
```
""")

    st.markdown("---")
    st.markdown("### Filtros")
    year_filter = st.multiselect(
        "Año",
        options=["2020", "2021", "2022", "2023", "2024", "2025", "2026"],
        default=[],
        placeholder="Todos los años",
    )
    st.markdown("---")
    st.markdown("### Navegación rápida")
    for label in ["📊 Resumen", "⏱️ Tiempo", "🎵 Música", "📻 Podcasts",
                  "📚 Audiolibros", "🌍 Por País", "💡 Recomendación"]:
        st.markdown(f"- {label}")


# ─────────────────────────────────────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("# 🎧 Spotify Analytics Dashboard")
st.markdown("Explora tus hábitos de escucha con datos reales de Spotify.")
st.markdown("---")

# ─────────────────────────────────────────────────────────────────────────────
# TABS
# ─────────────────────────────────────────────────────────────────────────────

tabs = st.tabs([
    "📊 Resumen General",
    "⏱️ Actividad Temporal",
    "🎵 Música & Artistas",
    "📻 Podcasts",
    "📚 Audiolibros",
    "🌍 Por País",
    "💡 Recomendación de Plan",
])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 0 – RESUMEN GENERAL
# ══════════════════════════════════════════════════════════════════════════════

with tabs[0]:
    st.header("📊 Resumen General")

    col1, col2, col3, col4 = st.columns(4)

    # ── KPI cards ─────────────────────────────────────────────────────────────
    df_año = read_parquet("G01_tiempo_total_por_año")
    df_tipo = read_parquet("G02_distribucion_tipo_arte")
    df_skip = read_parquet("G03_tasa_salto_global")
    df_ses  = read_parquet("G09_sesiones_estadisticas")

    total_horas = df_año["horas_total"].sum() if df_año is not None else 0
    total_repro = df_año["reproducciones"].sum() if df_año is not None else 0
    skip_pct    = df_skip["tasa_salto_pct"].iloc[0] if df_skip is not None and len(df_skip) else 0
    dur_ses     = df_ses["duracion_media_min"].iloc[0] if df_ses is not None and len(df_ses) else 0

    col1.metric("🕐 Horas totales",      f"{total_horas:,.0f} h")
    col2.metric("🎵 Reproducciones",     f"{int(total_repro):,}")
    col3.metric("⏭️ Tasa de salto",       f"{skip_pct:.1f} %")
    col4.metric("⌛ Duración media sesión", f"{dur_ses:.0f} min")

    st.markdown("---")
    c1, c2 = st.columns(2)

    # ── Tiempo por año ─────────────────────────────────────────────────────────
    with c1:
        if df_año is not None:
            fig = px.bar(
                df_año, x="año", y="horas_total",
                color_discrete_sequence=[GREEN],
                labels={"año": "Año", "horas_total": "Horas"},
            )
            dark_layout(fig, "⏱ Horas escuchadas por año")
            st.plotly_chart(fig, width="stretch")
        else:
            no_data("G01_tiempo_total_por_año")

    # ── Distribución por tipo ──────────────────────────────────────────────────
    with c2:
        if df_tipo is not None:
            fig = px.pie(
                df_tipo, names="tipo_arte", values="reproducciones",
                color_discrete_sequence=PALETTE,
                hole=0.45,
            )
            fig.update_traces(textfont_color=WHITE)
            dark_layout(fig, "🎧 Distribución por tipo de contenido")
            st.plotly_chart(fig, width="stretch")
        else:
            no_data("G02_distribucion_tipo_arte")

    # ── Horas por tipo de arte ─────────────────────────────────────────────────
    if df_tipo is not None:
        fig = px.bar(
            df_tipo, x="tipo_arte", y="horas_total",
            color="tipo_arte", color_discrete_sequence=PALETTE,
            labels={"tipo_arte": "Tipo", "horas_total": "Horas"},
        )
        dark_layout(fig, "⏳ Tiempo total por tipo de contenido (horas)")
        st.plotly_chart(fig, width="stretch")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 – ACTIVIDAD TEMPORAL
# ══════════════════════════════════════════════════════════════════════════════

with tabs[1]:
    st.header("⏱️ Actividad Temporal")

    c1, c2 = st.columns(2)

    # ── Por hora ───────────────────────────────────────────────────────────────
    df_hora = read_parquet("G05_actividad_por_hora")
    with c1:
        if df_hora is not None:
            fig = px.bar(
                df_hora, x="hora", y="reproducciones",
                color_discrete_sequence=[GREEN],
                labels={"hora": "Hora del día", "reproducciones": "Reproducciones"},
            )
            dark_layout(fig, "🕐 ¿A qué hora eres más activo?")
            st.plotly_chart(fig, width="stretch")
        else:
            no_data("G05_actividad_por_hora")

    # ── Por día de la semana ──────────────────────────────────────────────────
    df_dia = read_parquet("G07_actividad_dia_semana")
    with c2:
        if df_dia is not None:
            fig = px.bar(
                df_dia, x="dia_nombre", y="horas_escuchadas",
                color_discrete_sequence=["#4D96FF"],
                labels={"dia_nombre": "Día", "horas_escuchadas": "Horas"},
                category_orders={"dia_nombre": ["Dom","Lun","Mar","Mié","Jue","Vie","Sáb"]},
            )
            dark_layout(fig, "📅 Actividad por día de la semana")
            st.plotly_chart(fig, width="stretch")
        else:
            no_data("G07_actividad_dia_semana")

    # ── Mapa de calor mes × hora ───────────────────────────────────────────────
    df_mes = read_parquet("G06_actividad_por_mes")
    if df_mes is not None:
        df_mes["mes_nombre"] = df_mes["mes"].map(MESES_ES)
        fig = px.line(
            df_mes.sort_values(["año", "mes"]),
            x="mes_nombre", y="horas_escuchadas", color="año",
            markers=True,
            color_discrete_sequence=PALETTE,
            labels={"mes_nombre": "Mes", "horas_escuchadas": "Horas", "año": "Año"},
            category_orders={"mes_nombre": list(MESES_ES.values())},
        )
        dark_layout(fig, "📆 Evolución mensual de horas escuchadas", height=350)
        st.plotly_chart(fig, width="stretch")

    # ── Franja horaria ────────────────────────────────────────────────────────
    df_franja = read_parquet("G12_franja_horaria")
    if df_franja is not None:
        fig = px.bar(
            df_franja, x="franja", y="horas_escuchadas", color="tipo_arte",
            barmode="stack",
            color_discrete_sequence=PALETTE,
            labels={"franja": "Franja horaria", "horas_escuchadas": "Horas", "tipo_arte": "Tipo"},
        )
        dark_layout(fig, "🌅 Horas por franja del día y tipo de contenido")
        st.plotly_chart(fig, width="stretch")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 – MÚSICA & ARTISTAS
# ══════════════════════════════════════════════════════════════════════════════

with tabs[2]:
    st.header("🎵 Música & Artistas")

    # ── Top artistas ──────────────────────────────────────────────────────────
    df_art = read_parquet("G08_artistas_top30")
    if df_art is not None:
        top_n = st.slider("Mostrar top N artistas", 5, 30, 15)
        fig = px.bar(
            df_art.head(top_n),
            x="horas_total",
            y="master_metadata_album_artist_name",
            orientation="h",
            color="escuchas_completas",
            color_continuous_scale=[[0, "#191414"], [0.5, "#17A349"], [1, GREEN]],
            labels={
                "master_metadata_album_artist_name": "Artista",
                "horas_total": "Horas totales",
                "escuchas_completas": "Escuchas completas",
            },
        )
        fig.update_layout(yaxis=dict(autorange="reversed"))
        dark_layout(fig, "🎤 Artistas más escuchados", height=500)
        st.plotly_chart(fig, width="stretch")
    else:
        no_data("G08_artistas_top30")

    c1, c2 = st.columns(2)

    # ── Top canciones completas ───────────────────────────────────────────────
    df_songs = read_parquet("G04_canciones_completas_top50")
    with c1:
        if df_songs is not None:
            top_songs = st.slider("Top canciones", 5, 50, 10, key="songs")
            fig = px.bar(
                df_songs.head(top_songs),
                x="escuchas_completas",
                y="master_metadata_track_name",
                orientation="h",
                color_discrete_sequence=[GREEN],
                labels={
                    "master_metadata_track_name": "Canción",
                    "escuchas_completas": "Escuchas completas",
                },
            )
            fig.update_layout(yaxis=dict(autorange="reversed"))
            dark_layout(fig, "🏆 Canciones más escuchadas completas", height=450)
            st.plotly_chart(fig, width="stretch")
        else:
            no_data("G04_canciones_completas_top50")

    # ── Tasa de salto por artista ─────────────────────────────────────────────
    df_skip_art = read_parquet("G03_tasa_salto_por_artista")
    with c2:
        if df_skip_art is not None:
            st.subheader("⏭️ Tasa de salto por artista")
            tab_more, tab_less = st.tabs(["Más saltados", "Menos saltados"])
            with tab_more:
                fig = px.bar(
                    df_skip_art.head(10),
                    x="tasa_salto_pct",
                    y="master_metadata_album_artist_name",
                    orientation="h",
                    color_discrete_sequence=["#FF6B6B"],
                    labels={
                        "master_metadata_album_artist_name": "Artista",
                        "tasa_salto_pct": "% Saltadas",
                    },
                )
                fig.update_layout(yaxis=dict(autorange="reversed"))
                dark_layout(fig, "", height=350)
                st.plotly_chart(fig, width="stretch")
            with tab_less:
                fig = px.bar(
                    df_skip_art.tail(10).iloc[::-1],
                    x="tasa_salto_pct",
                    y="master_metadata_album_artist_name",
                    orientation="h",
                    color_discrete_sequence=[GREEN],
                    labels={
                        "master_metadata_album_artist_name": "Artista",
                        "tasa_salto_pct": "% Saltadas",
                    },
                )
                fig.update_layout(yaxis=dict(autorange="reversed"))
                dark_layout(fig, "", height=350)
                st.plotly_chart(fig, width="stretch")
        else:
            no_data("G03_tasa_salto_por_artista")

    # ── Sesiones ──────────────────────────────────────────────────────────────
    df_ses = read_parquet("G09_sesiones_estadisticas")
    if df_ses is not None:
        st.markdown("---")
        st.subheader("⌛ Estadísticas de sesiones")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total sesiones",        f"{int(df_ses['total_sesiones'].iloc[0]):,}")
        c2.metric("Duración media",        f"{df_ses['duracion_media_min'].iloc[0]:.0f} min")
        c3.metric("Tracks por sesión",     f"{df_ses['tracks_media'].iloc[0]:.1f}")
        c4.metric("Sesión más larga",      f"{df_ses['sesion_mas_larga_min'].iloc[0]:.0f} min")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 – PODCASTS
# ══════════════════════════════════════════════════════════════════════════════

with tabs[3]:
    st.header("📻 Podcasts")

    df_pod = read_parquet("G14_podcasts_top20")
    if df_pod is not None:
        fig = px.bar(
            df_pod,
            x="horas_total",
            y="episode_show_name",
            orientation="h",
            color="episodios_escuchados",
            color_continuous_scale=[[0, "#191414"], [0.5, "#4D96FF"], [1, "#C77DFF"]],
            labels={
                "episode_show_name": "Podcast",
                "horas_total": "Horas escuchadas",
                "episodios_escuchados": "Episodios",
            },
        )
        fig.update_layout(yaxis=dict(autorange="reversed"))
        dark_layout(fig, "🎙️ Podcasts más escuchados (top 20)", height=500)
        st.plotly_chart(fig, width="stretch")

        st.dataframe(
            df_pod[["episode_show_name", "episodios_escuchados", "horas_total"]]
            .rename(columns={
                "episode_show_name":    "Podcast",
                "episodios_escuchados": "Episodios",
                "horas_total":          "Horas",
            }),
            width="stretch",
            hide_index=True,
        )
    else:
        no_data("G14_podcasts_top20")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 – AUDIOLIBROS
# ══════════════════════════════════════════════════════════════════════════════

with tabs[4]:
    st.header("📚 Audiolibros")

    df_ab = read_parquet("G15_audiolibros_top10")
    if df_ab is not None and len(df_ab) > 0:
        fig = px.bar(
            df_ab,
            x="horas_total",
            y="audiobook_title",
            orientation="h",
            color_discrete_sequence=["#FFD93D"],
            labels={"audiobook_title": "Audiolibro", "horas_total": "Horas"},
        )
        fig.update_layout(yaxis=dict(autorange="reversed"))
        dark_layout(fig, "📖 Audiolibros más escuchados", height=400)
        st.plotly_chart(fig, width="stretch")

        st.dataframe(
            df_ab[["audiobook_title", "sesiones", "horas_total"]]
            .rename(columns={
                "audiobook_title": "Audiolibro",
                "sesiones":        "Sesiones",
                "horas_total":     "Horas",
            }),
            width="stretch",
            hide_index=True,
        )
    else:
        st.info("No hay datos de audiolibros suficientes en el dataset actual.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 – POR PAÍS
# ══════════════════════════════════════════════════════════════════════════════

with tabs[5]:
    st.header("🌍 Canciones más escuchadas por país")

    df_pais = read_parquet("G11_top_tracks_por_pais")
    if df_pais is not None:
        countries = sorted(df_pais["conn_country"].unique())
        selected = st.selectbox("Selecciona un país", countries, index=0)
        df_sel = df_pais[df_pais["conn_country"] == selected].head(10)

        fig = px.bar(
            df_sel,
            x="reproducciones",
            y="master_metadata_track_name",
            orientation="h",
            color_discrete_sequence=[GREEN],
            labels={
                "master_metadata_track_name":      "Canción",
                "master_metadata_album_artist_name": "Artista",
                "reproducciones":                   "Reproducciones",
            },
            hover_data=["master_metadata_album_artist_name"],
        )
        fig.update_layout(yaxis=dict(autorange="reversed"))
        dark_layout(fig, f"🏆 Top 10 canciones en {df_sel['nombre_pais'].iloc[0] if len(df_sel) else selected}")
        st.plotly_chart(fig, width="stretch")

        # ── Tabla de distribución por país ────────────────────────────────
        st.markdown("### Distribución de reproducciones por país")
        dist = (
            df_pais.groupby(["conn_country", "nombre_pais"])["reproducciones"]
            .sum().reset_index()
            .sort_values("reproducciones", ascending=False)
        )
        fig2 = px.pie(
            dist, names="nombre_pais", values="reproducciones",
            color_discrete_sequence=PALETTE, hole=0.4,
        )
        fig2.update_traces(textfont_color=WHITE)
        dark_layout(fig2, "Participación por país")
        st.plotly_chart(fig2, width="stretch")
    else:
        no_data("G11_top_tracks_por_pais")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 6 – RECOMENDACIÓN DE PLAN
# ══════════════════════════════════════════════════════════════════════════════

with tabs[6]:
    st.header("💡 ¿Plan mensual o anual?")

    df_plan = read_parquet("G10_plan_recomendacion")
    if df_plan is not None:
        row = df_plan.iloc[0]
        rec = row["recomendacion_plan"]

        if rec == "anual":
            st.success(
                f"### ✅ Recomendamos el **Plan Anual**\n"
                f"Con **{row['meses_activos']} meses activos** al año y "
                f"un promedio de **{row['horas_promedio_mes']:.1f} horas/mes**, "
                f"el plan anual te ahorra **${row['ahorro_anual_mxn']:.0f} MXN** al año.",
                icon="💰",
            )
        else:
            st.info(
                f"### ℹ️ El **Plan Mensual** puede ser mejor\n"
                f"Con **{row['meses_activos']} meses activos** al año, "
                f"pagar mensualmente puede ser más conveniente.",
                icon="📊",
            )

        st.markdown("---")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Meses activos",         f"{row['meses_activos']} / 12")
        c2.metric("Horas promedio/mes",     f"{row['horas_promedio_mes']:.1f} h")
        c3.metric("Costo mensual × 12",     f"${row['costo_mensual_x12']:.0f} MXN")
        c4.metric("Costo plan anual",        f"${row['costo_anual_mxn']:.0f} MXN")

        st.markdown("---")
        # ── Bar chart comparación ─────────────────────────────────────────
        comp_df = pd.DataFrame({
            "Plan": ["12 × Mensual", "Plan Anual"],
            "Costo (MXN)": [row["costo_mensual_x12"], row["costo_anual_mxn"]],
        })
        fig = px.bar(
            comp_df, x="Plan", y="Costo (MXN)",
            color="Plan",
            color_discrete_sequence=["#FF6B6B", GREEN],
            text="Costo (MXN)",
        )
        fig.update_traces(texttemplate="$%{text:.0f}", textposition="outside")
        dark_layout(fig, "Comparación de costos (MXN)")
        st.plotly_chart(fig, width="stretch")

        ahorro = row["costo_mensual_x12"] - row["costo_anual_mxn"]
        st.markdown(f"**💸 Ahorro potencial con el plan anual: `${ahorro:.0f} MXN` al año**")
    else:
        no_data("G10_plan_recomendacion")


# ── Footer ─────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    "<center style='color:#535353; font-size:0.8rem;'>"
    "Spotify Analytics Dashboard — Datos Masivos · Gerardo Huerta Hernández"
    "</center>",
    unsafe_allow_html=True,
)
