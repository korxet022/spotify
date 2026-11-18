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

def sincronizar_canciones():
    print("Buscando canciones recientes en Spotify...")
    resultados = sp.current_user_recently_played(limit=50)
    
    items = resultados.get('items', [])
    print(f"-> Spotify ha devuelto {len(items)} canciones.")
    
    if not items:
        print("No hay canciones recientes.")
        return

    guardadas = 0
    for item in items:
        track = item.get('track')
        if not track:
            continue
            
        played_at_str = item['played_at']
        track_name = track['name']
        
        artist_obj = track['artists'][0] if track.get('artists') else {}
        artist_name = artist_obj.get('name', 'Desconocido')
        
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
            "genre": "Desconocido", # Se asigna por defecto sin consumir la API
            "external_url": track.get('external_urls', {}).get('spotify', '')
        }

        try:
            supabase.table("spotify_history").upsert(fila, on_conflict="played_at").execute()
            guardadas += 1
            print(f"✅ Guardada: {track_name} | Artista: {artist_name}")
        except Exception as e:
            print(f"❌ Error al guardar en Supabase '{track_name}': {e}")

    print(f"¡Sincronización completada! Procesadas y guardadas: {guardadas}")

if __name__ == "__main__":
    sincronizar_canciones()
