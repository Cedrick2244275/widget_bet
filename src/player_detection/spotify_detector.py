# src/player_detection/spotify_detector.py

import logging
import time
from typing import Optional
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from .detector import PlayerDetector, MusicInfo, PlayerControls

class SpotifyDetector(PlayerDetector):
    """Detector para Spotify"""
    
    def __init__(self, client_id: str = "", client_secret: str = "", redirect_uri: str = "http://localhost:8888/callback"):
        super().__init__("Spotify")
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.sp = None
        self.last_update_time = 0
        self.update_interval = 1  # segundos
        self.controls = PlayerControls(
            can_play=True,
            can_pause=True,
            can_next=True,
            can_previous=True,
            can_seek=True,
            can_shuffle=True,
            can_repeat=True
        )
    
    def initialize(self) -> bool:
        """Inicializa la conexión con Spotify"""
        if not self.client_id or not self.client_secret:
            logging.warning("Faltan credenciales para Spotify (client_id o client_secret)")
            self.is_available = False
            return False
        
        try:
            self.sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
                client_id=self.client_id,
                client_secret=self.client_secret,
                redirect_uri=self.redirect_uri,
                scope="user-read-playback-state,user-modify-playback-state,user-read-currently-playing"
            ))
            
            # Consideramos el detector disponible independientemente de si hay
            # dispositivos activos, para realizar comprobaciones continuas
            self.is_available = True
            logging.info("Detector de Spotify inicializado correctamente")
            return True
                
        except Exception as e:
            logging.error(f"Error al inicializar Spotify: {e}")
            self.is_available = False
            return False
    
    def get_current_track(self) -> Optional[MusicInfo]:
        """Obtiene información sobre la pista actual de Spotify"""
        if not self.is_available or not self.sp:
            return None
        
        # Limitar las actualizaciones para evitar alcanzar el límite de la API
        current_time = time.time()
        if current_time - self.last_update_time < self.update_interval:
            return None
        
        self.last_update_time = current_time
        
        try:
            # Verificar dispositivos primero
            devices = self.sp.devices()
            if not devices or not devices.get('devices'):
                # No hay dispositivos activos, pero seguimos considerando el detector disponible
                return None
            
            # Intentar obtener la reproducción actual
            current_playback = None
            try:
                current_playback = self.sp.current_playback()
            except Exception as e:
                logging.warning(f"Error al obtener playback de Spotify: {e}")
                # Intentar con currently playing como alternativa
                try:
                    current_playback = self.sp.currently_playing()
                except Exception as inner_e:
                    logging.warning(f"Error al obtener currently playing de Spotify: {inner_e}")
                    return None
            
            if not current_playback:
                return None
            
            # Extraer información de la pista actual
            item = current_playback.get('item', {})
            if not item:
                return None
            
            artists = ", ".join([artist['name'] for artist in item.get('artists', [])])
            album = item.get('album', {})
            album_name = album.get('name', "")
            album_images = album.get('images', [])
            album_art_url = album_images[0]['url'] if album_images else ""
            
            # Verificar si está reproduciendo
            is_playing = current_playback.get('is_playing', False)
            # Si tenemos información de una canción pero no está reproduciendo, 
            # igual devolvemos la info con is_playing=False
            
            return MusicInfo(
                title=item.get('name', ""),
                artist=artists,
                album=album_name,
                album_art_url=album_art_url,
                duration_ms=item.get('duration_ms', 0),
                position_ms=current_playback.get('progress_ms', 0),
                is_playing=is_playing,
                player_name="Spotify",
                track_id=item.get('id', "")
            )
            
        except Exception as e:
            logging.error(f"Error al obtener la pista actual de Spotify: {e}")
            return None
    
    def play(self) -> bool:
        """Inicia la reproducción en Spotify"""
        if not self.is_available or not self.sp:
            return False
        
        try:
            self.sp.start_playback()
            return True
        except Exception as e:
            logging.error(f"Error al iniciar la reproducción en Spotify: {e}")
            return False
    
    def pause(self) -> bool:
        """Pausa la reproducción en Spotify"""
        if not self.is_available or not self.sp:
            return False
        
        try:
            self.sp.pause_playback()
            return True
        except Exception as e:
            logging.error(f"Error al pausar la reproducción en Spotify: {e}")
            return False
    
    def next_track(self) -> bool:
        """Pasa a la siguiente pista en Spotify"""
        if not self.is_available or not self.sp:
            return False
        
        try:
            self.sp.next_track()
            return True
        except Exception as e:
            logging.error(f"Error al pasar a la siguiente pista en Spotify: {e}")
            return False
    
    def previous_track(self) -> bool:
        """Vuelve a la pista anterior en Spotify"""
        if not self.is_available or not self.sp:
            return False
        
        try:
            self.sp.previous_track()
            return True
        except Exception as e:
            logging.error(f"Error al volver a la pista anterior en Spotify: {e}")
            return False
    
    def seek(self, position_ms: int) -> bool:
        """Busca una posición específica en la pista actual de Spotify"""
        if not self.is_available or not self.sp:
            return False
        
        try:
            self.sp.seek_track(position_ms)
            return True
        except Exception as e:
            logging.error(f"Error al buscar posición en Spotify: {e}")
            return False
    
    def set_shuffle(self, state: bool) -> bool:
        """Establece el estado de reproducción aleatoria en Spotify"""
        if not self.is_available or not self.sp:
            return False
        
        try:
            self.sp.shuffle(state)
            return True
        except Exception as e:
            logging.error(f"Error al establecer reproducción aleatoria en Spotify: {e}")
            return False
    
    def set_repeat(self, state: bool) -> bool:
        """Establece el estado de repetición en Spotify"""
        if not self.is_available or not self.sp:
            return False
        
        try:
            repeat_state = "track" if state else "off"
            self.sp.repeat(repeat_state)
            return True
        except Exception as e:
            logging.error(f"Error al establecer repetición en Spotify: {e}")
            return False