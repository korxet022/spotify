import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from supabase import create_client, Client

# --- CARGAR CREDENCIALES DESDE EL ENTORNO ---
SPOTIPY_CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
SPOTIPY_CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")
SPOTIPY_REDIRECT_URI = os.getenv("SPOTIPY_REDIRECT_URI", "http://127.0.0.1:8080")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

scope = "user-read-recently-played"
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=SPOTIPY_CLIENT_ID,
    client_secret=SPOTIPY_CLIENT_SECRET,
    redirect_uri=SPOTIPY_REDIRECT_URI,
    scope=scope
))

# Canciones excluidas del filtro de duplicados consecutivos (ej. bucle para leer)
EXCEPCIONES_BUCLE = {
    ("amid the sleeping trees", "hero"),
}


def sincronizar_canciones():
    print("Buscando canciones recientes en Spotify...")
    # ÚNICA LLAMADA A LA API DE SPOTIFY
    resultados = sp.current_user_recently_played(limit=50)

    items = resultados.get('items', [])
    print(f"-> Spotify ha devuelto {len(items)} canciones.")

    if not items:
        print("No hay canciones recientes.")
        return

    # Ordenamos de más antigua a más reciente para evaluar la secuencia real
    items_ordenados = sorted(items, key=lambda x: x['played_at'])

    # Obtenemos únicamente el último registro guardado en Supabase
    ultimo_res = (
        supabase.table("spotify_history")
        .select("track_name, artist_name, played_at")
        .order("played_at", desc=True)
        .limit(1)
        .execute()
        .data
    )
    ultimo_registro = ultimo_res[0] if ultimo_res else None

    guardadas = 0
    for item in items_ordenados:
        track = item.get('track')
        if not track:
            continue

        played_at_str = item['played_at']
        track_name = track['name']

        artist_obj = track['artists'][0] if track.get('artists') else {}
        artist_name = artist_obj.get('name', 'Desconocido')

        clave_cancion = (track_name.strip().lower(), artist_name.strip().lower())
        es_excepcion = clave_cancion in EXCEPCIONES_BUCLE

        # Si no está en excepciones y es igual a la última canción guardada, se salta sin importar el tiempo
        if not es_excepcion and ultimo_registro:
            ultima_clave = (
                ultimo_registro.get('track_name', '').strip().lower(),
                ultimo_registro.get('artist_name', '').strip().lower(),
            )
            if clave_cancion == ultima_clave:
                print(f"⏭️ Saltada (duplicado consecutivo): {track_name} - {artist_name}")
                continue

        album_name = track.get('album', {}).get('name', 'Desconocido')
        duration_ms = track.get('duration_ms', 0)
        device_name = item.get('device', {}).get('name', 'Desconocido')

        popularity = track.get('popularity')
        if not popularity or popularity == 0:
            popularity = track.get('album', {}).get('popularity', 50)

        fila = {
            "played_at": played_at_str,
            "track_name": track_name,
            "artist_name": artist_name,
            "album_name": album_name,
            "duration_ms": duration_ms,
            "device_name": device_name,
            "popularity": popularity,
            "genre": "Desconocido",
            "external_url": track.get('external_urls', {}).get('spotify', '')
        }

        try:
            supabase.table("spotify_history").upsert(fila, on_conflict="played_at").execute()
            guardadas += 1
            ultimo_registro = {
                "track_name": track_name,
                "artist_name": artist_name,
                "played_at": played_at_str
            }
            print(f"✅ Guardada: {track_name} | Artista: {artist_name}")
        except Exception as e:
            print(f"❌ Error al guardar en Supabase '{track_name}': {e}")

    print(f"¡Sincronización completada! Procesadas y guardadas: {guardadas}")


if __name__ == "__main__":
    sincronizar_canciones()
