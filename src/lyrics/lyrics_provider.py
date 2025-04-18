# src/lyrics/lyrics_provider.py

from abc import ABC, abstractmethod
import os
import json
import logging
import hashlib
from typing import Optional, Dict, List, Tuple

class LyricLine:
    """Representa una línea de letra con tiempo de sincronización opcional"""
    def __init__(self, text: str, start_time_ms: int = -1, end_time_ms: int = -1):
        self.text = text
        self.start_time_ms = start_time_ms
        self.end_time_ms = end_time_ms
    
    def is_synced(self) -> bool:
        """Verifica si la línea tiene tiempos de sincronización"""
        return self.start_time_ms >= 0 and self.end_time_ms >= 0
    
    def to_dict(self) -> Dict:
        """Convierte la línea a un diccionario"""
        return {
            "text": self.text,
            "start_time_ms": self.start_time_ms,
            "end_time_ms": self.end_time_ms
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'LyricLine':
        """Crea una línea a partir de un diccionario"""
        return cls(
            text=data.get("text", ""),
            start_time_ms=data.get("start_time_ms", -1),
            end_time_ms=data.get("end_time_ms", -1)
        )

class LyricsData:
    """Contiene las letras de una canción"""
    def __init__(self, 
                 title: str = "", 
                 artist: str = "", 
                 album: str = "",
                 lyrics_text: str = "",
                 lines: List[LyricLine] = None,
                 source: str = "",
                 has_synced_lyrics: bool = False):
        self.title = title
        self.artist = artist
        self.album = album
        self.lyrics_text = lyrics_text
        self.lines = lines or []
        self.source = source
        self.has_synced_lyrics = has_synced_lyrics
    
    def to_dict(self) -> Dict:
        """Convierte los datos a un diccionario"""
        return {
            "title": self.title,
            "artist": self.artist,
            "album": self.album,
            "lyrics_text": self.lyrics_text,
            "lines": [line.to_dict() for line in self.lines],
            "source": self.source,
            "has_synced_lyrics": self.has_synced_lyrics
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'LyricsData':
        """Crea una instancia a partir de un diccionario"""
        lines = [LyricLine.from_dict(line_data) for line_data in data.get("lines", [])]
        return cls(
            title=data.get("title", ""),
            artist=data.get("artist", ""),
            album=data.get("album", ""),
            lyrics_text=data.get("lyrics_text", ""),
            lines=lines,
            source=data.get("source", ""),
            has_synced_lyrics=data.get("has_synced_lyrics", False)
        )
    
    def get_current_line(self, position_ms: int) -> Tuple[Optional[LyricLine], int]:
        """
        Obtiene la línea actual según la posición de reproducción y su índice
        """
        if not self.has_synced_lyrics:
            return None, -1
        
        for i, line in enumerate(self.lines):
            if not line.is_synced():
                continue
                
            if line.start_time_ms <= position_ms <= line.end_time_ms:
                return line, i
        
        return None, -1
    
    def is_valid(self) -> bool:
        """Verifica si los datos de las letras son válidos"""
        return bool(self.lyrics_text or self.lines)

class LyricsProvider(ABC):
    """Clase base para proveedores de letras de canciones"""
    
    def __init__(self, name: str, cache_dir: str = None):
        self.name = name
        self.cache_dir = cache_dir
    
    def get_lyrics(self, title: str, artist: str, album: str = "") -> Optional[LyricsData]:
        """
        Obtiene las letras de una canción, primero del caché y luego de la fuente
        """
        # Intentar cargar desde la caché
        cached_lyrics = self._load_from_cache(title, artist)
        if cached_lyrics and cached_lyrics.is_valid():
            return cached_lyrics
        
        # Obtener letras de la fuente
        lyrics = self._fetch_lyrics(title, artist, album)
        if lyrics and lyrics.is_valid():
            # Guardar en caché
            if self.cache_dir:
                self._save_to_cache(lyrics)
            return lyrics
            
        return None
    
    @abstractmethod
    def _fetch_lyrics(self, title: str, artist: str, album: str = "") -> Optional[LyricsData]:
        """
        Obtiene las letras de una canción de la fuente (API, web, etc.)
        """
        pass
    
    def _generate_cache_key(self, title: str, artist: str) -> str:
        """
        Genera una clave única para la caché basada en el título y artista
        """
        # Normalizar y crear un hash para el nombre del archivo
        key = f"{artist.lower()}-{title.lower()}"
        return hashlib.md5(key.encode()).hexdigest()
    
    def _load_from_cache(self, title: str, artist: str) -> Optional[LyricsData]:
        """
        Carga las letras desde la caché
        """
        if not self.cache_dir:
            return None
            
        try:
            cache_file = os.path.join(self.cache_dir, f"{self._generate_cache_key(title, artist)}.json")
            if os.path.exists(cache_file):
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return LyricsData.from_dict(data)
        except Exception as e:
            logging.error(f"Error al cargar letras desde caché: {e}")
            
        return None
    
    def _save_to_cache(self, lyrics: LyricsData) -> bool:
        """
        Guarda las letras en la caché
        """
        if not self.cache_dir:
            return False
            
        try:
            # Asegurarse de que el directorio exista
            os.makedirs(self.cache_dir, exist_ok=True)
            
            cache_file = os.path.join(self.cache_dir, f"{self._generate_cache_key(lyrics.title, lyrics.artist)}.json")
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(lyrics.to_dict(), f, indent=2)
            return True
        except Exception as e:
            logging.error(f"Error al guardar letras en caché: {e}")
            return False