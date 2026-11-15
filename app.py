import streamlit as st
import pandas as pd
from supabase import create_client, Client

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(
    page_title="Spotify Analytics Dashboard",
    page_icon="🎵",
    layout="wide"
)

# --- CONFIGURACIÓN DE SUPABASE (Desde secrets de Streamlit) ---
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

# --- TÍTULO Y MÉTRICAS ---
st.title("🎵 Mi Dashboard de Spotify")
st.markdown("Visualización en tiempo real de tu historial de reproducciones conectado con Supabase.")

if df.empty:
    st.warning("⚠️ No hay datos todavía. Espera a que se ejecute la sincronización olanza el script manual.")
else:
    total_reproducciones = len(df)
    artistas_unicos = df['artist_name'].nunique()
    canciones_unicas = df['track_name'].nunique()

    col1, col2, col3 = st.columns(3)
    col1.metric("🎧 Total Reproducciones", total_reproducciones)
    col2.metric("🎤 Artistas Únicos", artistas_unicos)
    col3.metric("🎶 Canciones Únicas", canciones_unicas)

    st.markdown("---")

    # --- GRÁFICOS ---
    col_g1, col_g2 = st.columns(2)

    with col_g1:
        st.subheader("🔥 Artistas Más Reproducidos")
        top_artistas = df['artist_name'].value_counts().head(10)
        st.bar_chart(top_artistas)

    with col_g2:
        st.subheader("🎵 Canciones Más Reproducidas")
        top_canciones = df['track_name'].value_counts().head(10)
        st.bar_chart(top_canciones)

    st.markdown("---")

    # --- TABLA DETALLADA ---
    st.subheader("📜 Historial Detallado")
    st.dataframe(
        df[['played_at', 'track_name', 'artist_name', 'album_name', 'external_url']],
        use_container_width=True
    )