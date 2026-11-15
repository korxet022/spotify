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
st.markdown("Visualización avanzada en tiempo real de tu historial musical.")

if df.empty:
    st.warning("⚠️ No hay datos todavía. Espera a que se ejecute la sincronización o lanza el script manual.")
else:
    min_date = df['played_at'].min().date()
    max_date = df['played_at'].max().date()

    # ==========================================
    # --- INICIALIZACIÓN DE SESSION STATE ---
    # ==========================================
    if "date_range" not in st.session_state:
        st.session_state.date_range = (min_date, max_date)
    if "artistas_seleccionados" not in st.session_state:
        st.session_state.artistas_seleccionados = []
    if "canciones_seleccionadas" not in st.session_state:
        st.session_state.canciones_seleccionadas = []

    # ==========================================
    # --- BARRA LATERAL: FILTROS MULTIPLES ---
    # ==========================================
    st.sidebar.header("🔍 Filtros Avanzados")
    
    # Botón de restablecer filtros funcional
    if st.sidebar.button("🔄 Restablecer Filtros"):
        st.session_state.date_range = (min_date, max_date)
        st.session_state.artistas_seleccionados = []
        st.session_state.canciones_seleccionadas = []
        st.rerun()

    date_range = st.sidebar.date_input(
        "📅 Periodo de fechas",
        min_value=min_date,
        max_value=max_date,
        key="date_range"
    )

    # Las opciones de artistas se basan en el dataset global para no perder la selección al cambiar fechas
    artistas_disponibles = sorted(df['artist_name'].dropna().unique())
    artistas_seleccionados = st.sidebar.multiselect(
        "🎤 Filtrar por Artistas", 
        artistas_disponibles,
        key="artistas_seleccionados"
    )

    # Filtrar canciones disponibles opcionalmente según los artistas elegidos (o todo el df)
    df_para_canciones = df[df['artist_name'].isin(artistas_seleccionados)] if artistas_seleccionados else df
    canciones_disponibles = sorted(df_para_canciones['track_name'].dropna().unique())
    
    canciones_seleccionadas = st.sidebar.multiselect(
        "🎶 Filtrar por Canciones", 
        canciones_disponibles,
        key="canciones_seleccionadas"
    )

    # Aplicar todos los filtros de forma acumulativa sobre una copia del DataFrame
    df_filtered = df.copy()

    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
        mask = (df_filtered['played_at'].dt.date >= start_date) & (df_filtered['played_at'].dt.date <= end_date)
        df_filtered = df_filtered.loc[mask]

    if artistas_seleccionados:
        df_filtered = df_filtered[df_filtered['artist_name'].isin(artistas_seleccionados)]

    if canciones_seleccionadas:
        df_filtered = df_filtered[df_filtered['track_name'].isin(canciones_seleccionadas)]

    # ==========================================
    # --- MÉTRICAS Y KPIS PRINCIPALES ---
    # ==========================================
    total_reproducciones = len(df_filtered)
    total_ms = df_filtered['duration_ms'].sum() if 'duration_ms' in df_filtered.columns else 0
    tiempo_escuchado_formateado = formatear_tiempo_total(total_ms)
    artistas_unicos = df_filtered['artist_name'].nunique()
    canciones_unicas = df_filtered['track_name'].nunique()

    # Promedio diario
    if not df_filtered.empty:
        dias_unicos = df_filtered['played_at'].dt.date.nunique()
        dias_unicos = max(dias_unicos, 1)
        promedio_diario_reps = round(total_reproducciones / dias_unicos, 1)
    else:
        promedio_diario_reps = 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🎧 Reproducciones", total_reproducciones)
    col2.metric("⏱️ Tiempo Escuchado", tiempo_escuchado_formateado)
    col3.metric("📈 Promedio Diario", f"{promedio_diario_reps} reps/día")
    col4.metric("🎤 Artistas / 🎶 Canciones", f"{artistas_unicos} / {canciones_unicas}")

    st.markdown("---")

    # ==========================================
    # --- TARJETAS DE DESTACADOS ---
    # ==========================================
    if not df_filtered.empty:
        top_artista_val = df_filtered['artist_name'].mode()
        top_artista_str = top_artista_val.iloc[0] if not top_artista_val.empty else "N/A"
        
        def obtener_franja(h):
            if 6 <= h < 12: return "🌅 Mañana (06:00 - 12:00)"
            elif 12 <= h < 20: return "☀️ Tarde (12:00 - 20:00)"
            elif 20 <= h < 24: return "🌙 Noche (20:00 - 00:00)"
            else: return "🌌 Madrugada (00:00 - 06:00)"
        
        franjas = df_filtered['played_at'].dt.hour.apply(obtener_franja)
        top_franja = franjas.mode()
        top_franja_str = top_franja.iloc[0] if not top_franja.empty else "N/A"

        kpi_col1, kpi_col2 = st.columns(2)
        kpi_col1.info(f"👑 **Artista Top del Periodo:** {top_artista_str}")
        kpi_col2.info(f"⏰ **Momento Favorito:** {top_franja_str}")

    st.markdown("---")

    # ==========================================
    # --- SECCIÓN DE GRÁFICOS (TOP ARTISTAS Y CANCIONES) ---
    # ==========================================
    col_g1, col_g2 = st.columns(2)

    with col_g1:
        st.subheader("🔥 Artistas Más Reproducidos")
        top_artistas = df_filtered['artist_name'].value_counts().head(10)
        top_artistas_df = top_artistas.reset_index()
        top_artistas_df.columns = ['Artista', 'Reproducciones']

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
    # --- NUEVOS GRÁFICOS ANALÍTICOS ---
    # ==========================================
    st.subheader("📈 Evolución Diaria de Reproducciones")
    df_diario = df_filtered.copy()
    if not df_diario.empty:
        df_diario['dia'] = df_diario['played_at'].dt.date
        conteo_diario = df_diario['dia'].value_counts().sort_index()
        st.line_chart(conteo_diario)
    else:
        st.info("No hay datos para mostrar la evolución temporal.")

    st.markdown("---")

    col_h1, col_h2 = st.columns(2)

    with col_h1:
        st.subheader("⏰ Hábitos por Hora del Día")
        if not df_filtered.empty:
            df_filtered_h = df_filtered.copy()
            df_filtered_h['hora'] = df_filtered_h['played_at'].dt.hour
            conteo_horas = df_filtered_h['hora'].value_counts().reindex(range(24), fill_value=0)
            st.bar_chart(conteo_horas)
        else:
            st.info("No hay datos.")

    with col_h2:
        st.subheader("📅 Distribución por Día de la Semana")
        if not df_filtered.empty:
            df_filtered_d = df_filtered.copy()
            dias_orden = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
            dias_map = {0: 'Lunes', 1: 'Martes', 2: 'Miércoles', 3: 'Jueves', 4: 'Viernes', 5: 'Sábado', 6: 'Domingo'}
            df_filtered_d['dia_semana'] = df_filtered_d['played_at'].dt.dayofweek.map(dias_map)
            conteo_dias = df_filtered_d['dia_semana'].value_counts().reindex(dias_orden, fill_value=0)
            st.bar_chart(conteo_dias)
        else:
            st.info("No hay datos.")

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
