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

# --- FUNCIONES AUXILIARES DE FORMATO DE TIEMPO ---
def formatear_duracion(ms):
    if pd.isna(ms) or ms == 0:
        return "0:00"
    segundos_totales = int(ms / 1000)
    minutos = segundos_totales // 60
    segundos = segundos_totales % 60
    return f"{minutos}:{segundos:02d}"

def formatear_tiempo_total(ms):
    if pd.isna(ms) or ms == 0:
        return "0 min"
    segundos_totales = int(ms / 1000)
    horas = segundos_totales // 3600
    minutos = (segundos_totales % 3600) // 60
    segundos = segundos_totales % 60
    
    if horas > 0:
        return f"{horas}h {minutos}m {segundos}s"
    elif minutos > 0:
        return f"{minutos}m {segundos}s"
    else:
        return f"{segundos}s"

# --- TÍTULO Y CABECERA ---
st.title("🎵 Mi Dashboard de Spotify")
st.markdown("Visualización en tiempo real de tu historial de reproducciones conectado con Supabase.")

if df.empty:
    st.warning("⚠️ No hay datos todavía. Espera a que se ejecute la sincronización o lanza el script manual.")
else:
    # ==========================================
    # --- BARRA LATERAL: FILTROS MULTIPLES ---
    # ==========================================
    st.sidebar.header("🔍 Filtros Avanzados")
    
    # 1. Calendario
    min_date = df['played_at'].min().date()
    max_date = df['played_at'].max().date()
    
    date_range = st.sidebar.date_input(
        "📅 Periodo de fechas",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )

    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
        mask = (df['played_at'].dt.date >= start_date) & (df['played_at'].dt.date <= end_date)
        df_filtered = df.loc[mask]
    else:
        df_filtered = df

    # 2. Multiselect de Artistas
    artistas_disponibles = sorted(df_filtered['artist_name'].dropna().unique())
    artistas_seleccionados = st.sidebar.multiselect(
        "🎤 Filtrar por Artistas", 
        artistas_disponibles
    )

    if artistas_seleccionados:
        df_filtered = df_filtered[df_filtered['artist_name'].isin(artistas_seleccionados)]

    # 3. Multiselect de Canciones
    canciones_disponibles = sorted(df_filtered['track_name'].dropna().unique())
    canciones_seleccionadas = st.sidebar.multiselect(
        "🎶 Filtrar por Canciones", 
        canciones_disponibles
    )

    if canciones_seleccionadas:
        df_filtered = df_filtered[df_filtered['track_name'].isin(canciones_seleccionadas)]

    if st.sidebar.button("🔄 Restablecer Filtros"):
        st.rerun()

    # ==========================================
    # --- MÉTRICAS Y KPIS PRINCIPALES ---
    # ==========================================
    total_reproducciones = len(df_filtered)
    total_ms = df_filtered['duration_ms'].sum() if 'duration_ms' in df_filtered.columns else 0
    tiempo_escuchado_formateado = formatear_tiempo_total(total_ms)
    artistas_unicos = df_filtered['artist_name'].nunique()
    canciones_unicas = df_filtered['track_name'].nunique()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🎧 Reproducciones", total_reproducciones)
    col2.metric("⏱️ Tiempo Escuchado", tiempo_escuchado_formateado)
    col3.metric("🎤 Artistas Únicos", artistas_unicos)
    col4.metric("🎶 Canciones Únicas", canciones_unicas)

    st.markdown("---")

    # ==========================================
    # --- SECCIÓN DE GRÁFICOS CON PESTAÑAS ---
    # ==========================================
    col_g1, col_g2 = st.columns(2)

    with col_g1:
        st.subheader("🔥 Artistas Más Reproducidos")
        
        top_artistas = df_filtered['artist_name'].value_counts().head(10)
        top_artistas_df = top_artistas.reset_index()
        top_artistas_df.columns = ['Artista', 'Reproducciones']

        # Pestañas para elegir entre Gráfico (por defecto) o Lista
        tab_grafico_a, tab_lista_a = st.tabs(["📊 Gráfico", "📋 Ver Lista"])
        
        with tab_grafico_a:
            if not top_artistas.empty:
                st.bar_chart(top_artistas)
            else:
                st.info("No hay datos para esta selección.")
                
        with tab_lista_a:
            st.dataframe(top_artistas_df, use_container_width=True, hide_index=True)

    with col_g2:
        st.subheader("🎵 Canciones Más Reproducidas")
        
        top_canciones = df_filtered['track_name'].value_counts().head(10)
        top_canciones_df = top_canciones.reset_index()
        top_canciones_df.columns = ['Canción', 'Reproducciones']

        # Pestañas para elegir entre Gráfico (por defecto) o Lista
        tab_grafico_c, tab_lista_c = st.tabs(["📊 Gráfico", "📋 Ver Lista"])
        
        with tab_grafico_c:
            if not top_canciones.empty:
                st.bar_chart(top_canciones)
            else:
                st.info("No hay datos para esta selección.")
                
        with tab_lista_c:
            st.dataframe(top_canciones_df, use_container_width=True, hide_index=True)

    st.markdown("---")

    # ==========================================
    # --- TABLA DE HISTORIAL DETALLADO ---
    # ==========================================
    st.subheader(f"📜 Historial Detallado ({len(df_filtered)} registros)")
    
    df_display = df_filtered.copy()
    df_display['Duración'] = df_display['duration_ms'].apply(formatear_duracion)
    
    st.dataframe(
        df_display[['played_at', 'track_name', 'artist_name', 'album_name', 'Duración']],
        use_container_width=True,
        hide_index=True,
        column_config={
            "played_at": "Fecha y Hora",
            "track_name": "Canción",
            "artist_name": "Artista",
            "album_name": "Álbum",
            "Duración": "Duración"
        }
    )
