import os
import pandas as pd
import plotly.express as px
import streamlit as st
from supabase import create_client, Client

# ==========================================
# --- CONFIGURACIÓN DE PÁGINA Y SUPABASE ---
# ==========================================
st.set_page_config(
    page_title="Spotify Analytics | Dashboard",
    page_icon="🎧",
    layout="wide",
    initial_sidebar_state="expanded"
)

SUPABASE_URL = st.secrets.get("SUPABASE_URL", os.getenv("SUPABASE_URL"))
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", os.getenv("SUPABASE_KEY"))

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("⚠️ Faltan las credenciales de Supabase (`SUPABASE_URL` y `SUPABASE_KEY`).")
    st.stop()

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# ==========================================
# --- FUNCIONES AUXILIARES ---
# ==========================================
def formatear_tiempo_total(ms):
    if pd.isna(ms) or ms <= 0:
        return "0m"
    total_segundos = int(ms // 1000)
    horas = total_segundos // 3600
    minutos = (total_segundos % 3600) // 60
    if horas > 0:
        return f"{horas}h {minutos}m"
    return f"{minutos}m"


def formatear_duracion_cancion(ms):
    if pd.isna(ms) or ms <= 0:
        return "0:00"
    total_segundos = int(round(ms / 1000.0))
    minutos = total_segundos // 60
    segundos = total_segundos % 60
    return f"{minutos}:{segundos:02d}"


@st.cache_data(ttl=60)
def cargar_datos():
    all_rows = []
    batch_size = 1000
    start = 0

    while True:
        response = (
            supabase.table("spotify_history")
            .select("*")
            .order("played_at", desc=True)
            .range(start, start + batch_size - 1)
            .execute()
        )
        rows = response.data
        if not rows:
            break
        all_rows.extend(rows)
        if len(rows) < batch_size:
            break
        start += batch_size

    if not all_rows:
        return pd.DataFrame()

    df = pd.DataFrame(all_rows)

    # Conversión robusta de fechas (soporta distintos decimales de milisegundos en Supabase)
    df['played_at'] = pd.to_datetime(
        df['played_at'],
        format='mixed',
        utc=True,
        errors='coerce'
    )
    df = df.dropna(subset=['played_at'])

    # Convertir a hora local de España
    df['played_at_es'] = df['played_at'].dt.tz_convert('Europe/Madrid')
    df['fecha'] = df['played_at_es'].dt.date
    df['hora'] = df['played_at_es'].dt.hour
    df['dia_semana_num'] = df['played_at_es'].dt.dayofweek

    dias_map = {
        0: 'Lun', 1: 'Mar', 2: 'Mié', 3: 'Jue',
        4: 'Vie', 5: 'Sáb', 6: 'Dom'
    }
    df['dia_semana'] = df['dia_semana_num'].map(dias_map)

    if 'duration_ms' in df.columns:
        df['duration_ms'] = pd.to_numeric(df['duration_ms'], errors='coerce').fillna(0)
        df['minutos'] = df['duration_ms'] / 60000.0
        df['duracion_mmss'] = df['duration_ms'].apply(formatear_duracion_cancion)
    else:
        df['duration_ms'] = 0
        df['minutos'] = 0.0
        df['duracion_mmss'] = "0:00"

    return df


# ==========================================
# --- CARGA DE DATOS Y BARRA LATERAL ---
# ==========================================
st.title("🎧 Mi Historial de Spotify")

if st.sidebar.button("🔄 Actualizar datos"):
    st.cache_data.clear()
    st.rerun()

df = cargar_datos()

if df.empty:
    st.warning("Aún no hay reproducciones registradas en la base de datos.")
    st.stop()

st.sidebar.header("🔍 Filtros")

min_date = df['fecha'].min()
max_date = df['fecha'].max()

date_range = st.sidebar.date_input(
    "Rango de fechas",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date
)

if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = date_range
    df_filtered = df[(df['fecha'] >= start_date) & (df['fecha'] <= end_date)].copy()
else:
    df_filtered = df.copy()

artistas_disponibles = sorted(df_filtered['artist_name'].dropna().unique().tolist())
artista_sel = st.sidebar.multiselect("Filtrar por artista", options=artistas_disponibles)

if artista_sel:
    df_filtered = df_filtered[df_filtered['artist_name'].isin(artista_sel)]

canciones_disponibles = sorted(df_filtered['track_name'].dropna().unique().tolist())
cancion_sel = st.sidebar.multiselect("Filtrar por canción", options=canciones_disponibles)

if cancion_sel:
    df_filtered = df_filtered[df_filtered['track_name'].isin(cancion_sel)]

if df_filtered.empty:
    st.info("No hay reproducciones para los filtros seleccionados.")
    st.stop()

# ==========================================
# --- MÉTRICAS Y KPIS PRINCIPALES ---
# ==========================================
total_reproducciones = len(df_filtered)
total_ms = df_filtered['duration_ms'].sum() if 'duration_ms' in df_filtered.columns else 0
tiempo_escuchado_formateado = formatear_tiempo_total(total_ms)
artistas_unicos = df_filtered['artist_name'].nunique()
canciones_unicas = df_filtered['track_name'].nunique()

if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = date_range
    dias_totales_rango = max((end_date - start_date).days + 1, 1)
    promedio_diario_reps = round(total_reproducciones / dias_totales_rango, 1)

    # Media diaria en formato Xh Ym/día
    ms_por_dia = total_ms / dias_totales_rango
    media_diaria_str = f"{formatear_tiempo_total(ms_por_dia)}/día"
else:
    promedio_diario_reps = 0
    media_diaria_str = "0m/día"

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("🎧 Reproducciones", total_reproducciones)
col2.metric("⏱️ Tiempo Total", tiempo_escuchado_formateado)
col3.metric("⌛ Media Diaria", media_diaria_str)
col4.metric("📈 Reps / Día", f"{promedio_diario_reps} reps/día")
col5.metric("🎤 Artistas / 🎶 Canciones", f"{artistas_unicos} / {canciones_unicas}")

st.divider()

# ==========================================
# --- GRÁFICOS PRINCIPALES ---
# ==========================================
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("🏆 Top 10 Artistas")
    top_artistas = (
        df_filtered.groupby('artist_name', as_index=False)
        .agg(reproducciones=('track_name', 'count'), minutos=('minutos', 'sum'))
        .sort_values(by='reproducciones', ascending=False)
        .head(10)
    )
    fig_artistas = px.bar(
        top_artistas,
        x='reproducciones',
        y='artist_name',
        orientation='h',
        text='reproducciones',
        color='reproducciones',
        color_continuous_scale='Greens',
        labels={'reproducciones': 'Reproducciones', 'artist_name': 'Artista'}
    )
    fig_artistas.update_layout(yaxis={'categoryorder': 'total ascending'}, showlegend=False, coloraxis_showscale=False)
    st.plotly_chart(fig_artistas, use_container_width=True)

with col_right:
    st.subheader("🎵 Top 10 Canciones")
    top_canciones = (
        df_filtered.groupby(['track_name', 'artist_name'], as_index=False)
        .agg(reproducciones=('played_at', 'count'))
        .sort_values(by='reproducciones', ascending=False)
        .head(10)
    )
    top_canciones['etiqueta'] = top_canciones['track_name'] + " - " + top_canciones['artist_name']
    fig_canciones = px.bar(
        top_canciones,
        x='reproducciones',
        y='etiqueta',
        orientation='h',
        text='reproducciones',
        color='reproducciones',
        color_continuous_scale='Tealgrn',
        labels={'reproducciones': 'Reproducciones', 'etiqueta': 'Canción'}
    )
    fig_canciones.update_layout(yaxis={'categoryorder': 'total ascending'}, showlegend=False, coloraxis_showscale=False)
    st.plotly_chart(fig_canciones, use_container_width=True)

st.divider()

# ==========================================
# --- EVOLUCIÓN DIARIA Y HÁBITOS ---
# ==========================================
col_ev, col_hora = st.columns(2)

with col_ev:
    st.subheader("📅 Evolución Diaria (Minutos escuchados)")
    diario = (
        df_filtered.groupby('fecha', as_index=False)
        .agg(minutos=('minutos', 'sum'), reproducciones=('track_name', 'count'))
        .sort_values('fecha')
    )
    diario['minutos'] = diario['minutos'].round(1)
    fig_diario = px.area(
        diario,
        x='fecha',
        y='minutos',
        markers=True,
        labels={'fecha': 'Fecha', 'minutos': 'Minutos'}
    )
    fig_diario.update_traces(line_color='#1DB954')
    st.plotly_chart(fig_diario, use_container_width=True)

with col_hora:
    st.subheader("🕒 Actividad por Hora del Día")
    por_hora = (
        df_filtered.groupby('hora', as_index=False)
        .agg(reproducciones=('track_name', 'count'))
    )
    horas_completas = pd.DataFrame({'hora': range(24)})
    por_hora = horas_completas.merge(por_hora, on='hora', how='left').fillna(0)
    fig_hora = px.bar(
        por_hora,
        x='hora',
        y='reproducciones',
        labels={'hora': 'Hora (0-23h)', 'reproducciones': 'Reproducciones'}
    )
    fig_hora.update_traces(marker_color='#1DB954')
    fig_hora.update_xaxes(dtick=2)
    st.plotly_chart(fig_hora, use_container_width=True)

st.divider()

# ==========================================
# --- HISTORIAL DETALLADO ---
# ==========================================
st.subheader(f"📜 Historial Detallado ({len(df_filtered)} registros)")

tabla_mostrar = df_filtered[['played_at_es', 'track_name', 'artist_name', 'album_name', 'duracion_mmss']].copy()
tabla_mostrar['Fecha y Hora (España)'] = tabla_mostrar['played_at_es'].dt.strftime('%Y-%m-%d %H:%M:%S')

tabla_final = tabla_mostrar[['Fecha y Hora (España)', 'track_name', 'artist_name', 'album_name', 'duracion_mmss']].rename(
    columns={
        'track_name': 'Canción',
        'artist_name': 'Artista',
        'album_name': 'Álbum',
        'duracion_mmss': 'Duración'
    }
)

st.dataframe(tabla_final, use_container_width=True, hide_index=True)
