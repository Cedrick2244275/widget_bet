# src/player_detection/detector.py

import logging
from abc import ABC, abstractmethod
from typing import Dict, Optional, List, Any
import hashlib

class MusicInfo:
    """Información sobre una canción reproducida"""
    
    def __init__(self, 
                 title: str = "", 
                 artist: str = "", 
                 album: str = "", 
                 album_art_url: str = "",
                 duration_ms: int = 0, 
                 position_ms: int = 0, 
                 is_playing: bool = False, 
                 player_name: str = "",
                 track_id: str = ""):
        self.title = title
        self.artist = artist
        self.album = album
        self.album_art_url = album_art_url
        self.duration_ms = duration_ms
        self.position_ms = position_ms
        self.is_playing = is_playing
        self.player_name = player_name
        self.track_id = track_id
        
        # Si no se proporcionó un ID de pista, generar uno
        if not track_id:
            self.track_id = self.get_unique_id()
    
    def get_unique_id(self) -> str:
        """
        Genera un identificador único para la pista actual.
        Prioriza el track_id específico si está disponible,
        de lo contrario genera un ID consistente basado en 
        artista, título y álbum.
        """
        # Si ya tenemos un ID específico, usarlo
        if self.track_id:
            return self.track_id
            
        # Reemplazo: Generar un ID más consistente basado en datos normalizados
        # para evitar cambios frecuentes en el ID debido a variaciones menores en metadatos
        normalized_artist = self.artist.lower().strip() if self.artist else ""
        normalized_title = self.title.lower().strip() if self.title else ""
        
        # Si tenemos título y artista, usar la combinación para crear un ID estable
        if normalized_title and normalized_artist:
            stable_id = f"{normalized_artist}:{normalized_title}"
            # Crear un hash consistente para evitar caracteres especiales
            hash_object = hashlib.md5(stable_id.encode())
            return f"track_{hash_object.hexdigest()[:12]}"
            
        # Si falta información, usar lo que tenemos
        elif normalized_title:
            hash_object = hashlib.md5(normalized_title.encode())
            return f"title_{hash_object.hexdigest()[:12]}"
        elif normalized_artist:
            hash_object = hashlib.md5(normalized_artist.encode())
            return f"artist_{hash_object.hexdigest()[:12]}"
        else:
            # Último recurso - generar un ID aleatorio basado en el nombre del reproductor
            player_hash = hashlib.md5(self.player_name.encode()) if self.player_name else hashlib.md5(b"unknown")
            return f"unknown_{player_hash.hexdigest()[:12]}"
    
    def is_valid(self) -> bool:
        """Verifica si la información de la pista es válida"""
        # Una pista es válida si al menos tiene título o artista
        return bool(self.title or self.artist)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte la información de la pista a un diccionario"""
        return {
            "title": self.title,
            "artist": self.artist,
            "album": self.album,
            "album_art_url": self.album_art_url,
            "duration_ms": self.duration_ms,
            "position_ms": self.position_ms,
            "is_playing": self.is_playing,
            "player_name": self.player_name,
            "track_id": self.track_id or self.get_unique_id()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MusicInfo':
        """Crea una instancia de MusicInfo a partir de un diccionario"""
        return cls(
            title=data.get("title", ""),
            artist=data.get("artist", ""),
            album=data.get("album", ""),
            album_art_url=data.get("album_art_url", ""),
            duration_ms=data.get("duration_ms", 0),
            position_ms=data.get("position_ms", 0),
            is_playing=data.get("is_playing", False),
            player_name=data.get("player_name", ""),
            track_id=data.get("track_id", "")
        )
        
    def __str__(self) -> str:
        """Representación en cadena de texto de la pista"""
        return f"{self.artist} - {self.title}"
        
    def __bool__(self) -> bool:
        """Verdadero si hay información mínima de pista (título o artista)"""
        return bool(self.title or self.artist)

class PlayerControls:
    """Controles para el reproductor de música"""
    def __init__(self, 
                 can_play: bool = False, 
                 can_pause: bool = False,
                 can_next: bool = False, 
                 can_previous: bool = False,
                 can_seek: bool = False,
                 can_shuffle: bool = False,
                 can_repeat: bool = False):
        self.can_play = can_play
        self.can_pause = can_pause
        self.can_next = can_next
        self.can_previous = can_previous
        self.can_seek = can_seek
        self.can_shuffle = can_shuffle
        self.can_repeat = can_repeat

class PlayerDetector(ABC):
    """Clase base para detectores de reproductores de música"""
    
    def __init__(self, name: str):
        self.name = name
        self.is_available = False
        self.controls = PlayerControls()
    
    @abstractmethod
    def initialize(self) -> bool:
        """Inicializa el detector y verifica si está disponible"""
        pass
    
    @abstractmethod
    def get_current_track(self) -> Optional[MusicInfo]:
        """Obtiene información sobre la pista actual"""
        pass
    
    @abstractmethod
    def play(self) -> bool:
        """Inicia la reproducción"""
        pass
    
    @abstractmethod
    def pause(self) -> bool:
        """Pausa la reproducción"""
        pass
    
    @abstractmethod
    def next_track(self) -> bool:
        """Pasa a la siguiente pista"""
        pass
    
    @abstractmethod
    def previous_track(self) -> bool:
        """Vuelve a la pista anterior"""
        pass
    
    @abstractmethod
    def seek(self, position_ms: int) -> bool:
        """Busca una posición específica en la pista actual"""
        pass
    
    @abstractmethod
    def set_shuffle(self, state: bool) -> bool:
        """Establece el estado de reproducción aleatoria"""
        pass
    
    @abstractmethod
    def set_repeat(self, state: bool) -> bool:
        """Establece el estado de repetición"""
        pass

class MusicDetectionManager:
    """Administra múltiples detectores de reproductores de música"""
    
    def __init__(self):
        self.detectors: List[PlayerDetector] = []
        self.current_detector: Optional[PlayerDetector] = None
        self.current_track: Optional[MusicInfo] = None
    
    def register_detector(self, detector: PlayerDetector) -> None:
        """Registra un detector de reproductor"""
        self.detectors.append(detector)
    
    def initialize_detectors(self) -> None:
        """Inicializa todos los detectores registrados"""
        for detector in self.detectors:
            try:
                detector.initialize()
                logging.info(f"Detector '{detector.name}' initialized. Available: {detector.is_available}")
            except Exception as e:
                logging.error(f"Error initializing detector '{detector.name}': {e}")
                detector.is_available = False
    
    def update(self) -> Optional[MusicInfo]:
        """Actualiza la información de la pista actual de todos los detectores"""
        best_track = None
        best_detector = None
        
        # Verificar primero el detector actual si existe
        if self.current_detector and self.current_detector.is_available:
            try:
                track = self.current_detector.get_current_track()
                if track and track.is_valid() and track.is_playing:
                    self.current_track = track
                    return track
            except Exception as e:
                logging.error(f"Error al obtener pista del detector actual '{self.current_detector.name}': {e}")
        
        # Verificar todos los detectores disponibles
        for detector in self.detectors:
            if not detector.is_available:
                continue
                
            try:
                track = detector.get_current_track()
                if not track or not track.is_valid():
                    continue
                    
                if track.is_playing:
                    best_track = track
                    best_detector = detector
                    break
                elif not best_track:
                    best_track = track
                    best_detector = detector
            except Exception as e:
                logging.error(f"Error al obtener pista del detector '{detector.name}': {e}")
        
        if best_detector:
            self.current_detector = best_detector
            self.current_track = best_track
            return best_track
            
        return None
    
    def play(self) -> bool:
        """Reproduce la pista actual"""
        if self.current_detector and self.current_detector.controls.can_play:
            return self.current_detector.play()
        return False
    
    def pause(self) -> bool:
        """Pausa la pista actual"""
        if self.current_detector and self.current_detector.controls.can_pause:
            return self.current_detector.pause()
        return False
    
    def next_track(self) -> bool:
        """Pasa a la siguiente pista"""
        if self.current_detector and self.current_detector.controls.can_next:
            return self.current_detector.next_track()
        return False
    
    def previous_track(self) -> bool:
        """Vuelve a la pista anterior"""
        if self.current_detector and self.current_detector.controls.can_previous:
            return self.current_detector.previous_track()
        return False
    
    def seek(self, position_ms: int) -> bool:
        """Busca una posición específica en la pista actual"""
        if self.current_detector and self.current_detector.controls.can_seek:
            return self.current_detector.seek(position_ms)
        return False
    
    def set_shuffle(self, state: bool) -> bool:
        """Establece el estado de reproducción aleatoria"""
        if self.current_detector and self.current_detector.controls.can_shuffle:
            return self.current_detector.set_shuffle(state)
        return False
    
    def set_repeat(self, state: bool) -> bool:
        """Establece el estado de repetición"""
        if self.current_detector and self.current_detector.controls.can_repeat:
            return self.current_detector.set_repeat(state)
        return False