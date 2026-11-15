import streamlit as st
import pandas as pd
from supabase import create_client, Client

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(
    page_title="Spotify Analytics Dashboard",
    page_icon="🎵",
    layout="wide"
)

# --- CONFIGURACIÓN DE SUPABASE ---
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

@st.cache_resource
def init_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

# --- CARGAR DATOS ---
@st.cache_data(ttl=60)
def cargar_datos():
    response = supabase.table("spotify_history").select("*").order("played_at", desc=True).execute()
    data = response.data
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    df['played_at'] = pd.to_datetime(df['played_at'])
    return df

df = cargar_datos()

# --- TÍTULO Y CABECERA ---
st.title("🎵 Mi Dashboard de Spotify")
st.markdown("Visualización en tiempo real de tu historial de reproducciones conectado con Supabase.")

if df.empty:
    st.warning("⚠️ No hay datos todavía. Espera a que se ejecute la sincronización o lanza el script manual.")
else:
    # ==========================================
    # --- BARRA LATERAL: FILTROS INTERACTIVOS ---
    # ==========================================
    st.sidebar.header("🔍 Filtros Interactivos")
    
    # 1. Filtro de Calendario
    min_date = df['played_at'].min().date()
    max_date = df['played_at'].max().date()
    
    date_range = st.sidebar.date_input(
        "📅 Periodo de fechas",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )

    # Aplicar filtro de fecha
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
        mask = (df['played_at'].dt.date >= start_date) & (df['played_at'].dt.date <= end_date)
        df_filtered = df.loc[mask]
    else:
        df_filtered = df

    # 2. Filtro por Artista Específico
    artistas_disponibles = sorted(df_filtered['artist_name'].dropna().unique())
    artista_seleccionado = st.sidebar.selectbox(
        "🎤 Filtrar por Artista", 
        ["Todos los artistas"] + list(artistas_disponibles)
    )

    if artista_seleccionado != "Todos los artistas":
        df_filtered = df_filtered[df_filtered['artist_name'] == artista_seleccionado]

    # 3. Filtro por Canción Específica (se adapta al artista si se seleccionó uno)
    canciones_disponibles = sorted(df_filtered['track_name'].dropna().unique())
    cancion_seleccionada = st.sidebar.selectbox(
        "🎶 Filtrar por Canción", 
        ["Todas las canciones"] + list(canciones_disponibles)
    )

    if cancion_seleccionada != "Todas las canciones":
        df_filtered = df_filtered[df_filtered['track_name'] == cancion_seleccionada]

    # Botón para limpiar filtros fácilmente
    if st.sidebar.button("🔄 Restablecer Filtros"):
        st.rerun()

    # ==========================================
    # --- MÉTRICAS Y KPIS PRINCIPALES ---
    # ==========================================
    total_reproducciones = len(df_filtered)
    total_ms = df_filtered['duration_ms'].sum() if 'duration_ms' in df_filtered.columns else 0
    total_minutos = int(total_ms / 60000)
    artistas_unicos = df_filtered['artist_name'].nunique()
    canciones_unicas = df_filtered['track_name'].nunique()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🎧 Reproducciones", total_reproducciones)
    col2.metric("⏱️ Tiempo Escuchado", f"{total_minutos} min")
    col3.metric("🎤 Artistas Únicos", artistas_unicos)
    col4.metric("🎶 Canciones Únicas", canciones_unicas)

    st.markdown("---")

    # ==========================================
    # --- SECCIÓN DE GRÁFICOS / RESÚMENES ---
    # ==========================================
    col_g1, col_g2 = st.columns(2)

    with col_g1:
        st.subheader("🔥 Artistas Más Reproducidos")
        top_artistas = df_filtered['artist_name'].value_counts().head(10)
        if not top_artistas.empty:
            st.bar_chart(top_artistas)
        else:
            st.info("No hay datos para esta selección.")

    with col_g2:
        st.subheader("🎵 Canciones Más Reproducidas")
        top_canciones = df_filtered['track_name'].value_counts().head(10)
        if not top_canciones.empty:
            st.bar_chart(top_canciones)
        else:
            st.info("No hay datos para esta selección.")

    st.markdown("---")

    # ==========================================
    # --- TABLA DE HISTORIAL DETALLADO ---
    # ==========================================
    st.subheader(f"📜 Historial Detallado ({len(df_filtered)} registros)")
    st.dataframe(
        df_filtered[['played_at', 'track_name', 'artist_name', 'album_name', 'external_url']],
        use_container_width=True
    )
