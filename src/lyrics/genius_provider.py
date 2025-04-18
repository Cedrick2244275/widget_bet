# src/lyrics/genius_provider.py

import logging
import re
from typing import Optional, List
import lyricsgenius
from .lyrics_provider import LyricsProvider, LyricsData, LyricLine

class GeniusProvider(LyricsProvider):
    """Proveedor de letras usando la API de Genius"""
    
    def __init__(self, api_key: str, cache_dir: str = None):
        super().__init__("Genius", cache_dir)
        self.api_key = api_key
        self.genius = None
        
        if api_key:
            try:
                self.genius = lyricsgenius.Genius(
                    api_key, 
                    timeout=10,
                    retries=3,          # Reintentar si falla
                    sleep_time=0.5,     # Tiempo entre reintentos
                    verbose=False,      # No imprimir mensajes
                    remove_section_headers=True,  # Eliminar encabezados de secciones
                    skip_non_songs=True # Omitir resultados que no son canciones
                )
                
                # Configurar el User-Agent para evitar bloqueos
                self.genius._session.headers["User-Agent"] = (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                )
                
                logging.info("API de Genius inicializada correctamente")
            except Exception as e:
                logging.error(f"Error al inicializar Genius API: {e}")
    
    def _fetch_lyrics(self, title: str, artist: str, album: str = "") -> Optional[LyricsData]:
        """Obtiene letras de canciones de Genius"""
        if not self.genius:
            logging.warning("No se ha inicializado la API de Genius")
            return None
        
        try:
            # Buscar la canción mediante la API oficial (método preferido)
            logging.info(f"Buscando letra en Genius para: {artist} - {title}")
            
            # Intentar buscar con distintas combinaciones si falla
            song = None
            search_attempts = [
                (title, artist),  # Texto original
                (self._clean_search_term(title), self._clean_search_term(artist)),  # Limpio
                (title, ""),      # Solo título
                (f"{title} {artist}", "")  # Combinado como una sola consulta
            ]
            
            for search_title, search_artist in search_attempts:
                if not search_title:
                    continue
                    
                try:
                    song = self.genius.search_song(search_title, search_artist)
                    if song:
                        logging.info(f"Encontrada letra en Genius: {song.title} - {song.artist}")
                        break
                except Exception as e:
                    logging.warning(f"Error en búsqueda de Genius ({search_title}, {search_artist}): {e}")
                    continue
            
            if not song:
                logging.info(f"No se encontraron letras en Genius para: {artist} - {title}")
                return None
            
            # Obtener las letras
            lyrics_text = song.lyrics
            
            # Limpiar las letras (eliminar encabezados, etc.)
            lyrics_text = self._clean_lyrics(lyrics_text)
            
            # Dividir las letras en líneas
            lines = self._parse_lyrics_lines(lyrics_text)
            
            return LyricsData(
                title=song.title,
                artist=song.artist,
                album=album,
                lyrics_text=lyrics_text,
                lines=lines,
                source="Genius",
                has_synced_lyrics=False  # Genius no proporciona letras sincronizadas
            )
            
        except Exception as e:
            logging.error(f"Error al obtener letras de Genius: {e}")
            return None
    
    def _clean_search_term(self, text: str) -> str:
        """Limpia términos de búsqueda eliminando caracteres especiales y frases entre paréntesis"""
        if not text:
            return ""
        
        # Eliminar contenido entre paréntesis
        cleaned = re.sub(r'\([^)]*\)', '', text)
        
        # Eliminar contenido entre corchetes
        cleaned = re.sub(r'\[[^\]]*\]', '', cleaned)
        
        # Eliminar caracteres especiales y palabras extra comunes
        for word in ["oficial", "official", "video", "lyrics", "audio", "hd", "4k"]:
            cleaned = re.sub(r'\b' + word + r'\b', '', cleaned, flags=re.IGNORECASE)
        
        # Eliminar caracteres no alfanuméricos excepto espacios
        cleaned = re.sub(r'[^\w\s]', '', cleaned)
        
        # Normalizar espacios
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        return cleaned
    
    def _clean_lyrics(self, lyrics_text: str) -> str:
        """Limpia el texto de las letras eliminando encabezados y otros elementos"""
        if not lyrics_text:
            return ""
        
        # Eliminar la primera línea si contiene el título de la canción (típico en Genius)
        lines = lyrics_text.split('\n')
        if len(lines) > 0 and re.search(r'\[.*Lyrics\]', lines[0]):
            lines = lines[1:]
        
        # Eliminar líneas vacías al principio y al final
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        
        # Eliminar anotaciones y números de línea
        filtered_lines = []
        for line in lines:
            # Eliminar anotaciones entre corchetes
            line = re.sub(r'\[.*?\]', '', line)
            
            # Eliminar números de línea al principio de la línea
            line = re.sub(r'^\d+\s*', '', line)
            
            filtered_lines.append(line)
        
        # Reconstruir el texto
        cleaned_lyrics = '\n'.join(filtered_lines)
        
        # Eliminar múltiples líneas vacías consecutivas
        cleaned_lyrics = re.sub(r'\n{3,}', '\n\n', cleaned_lyrics)
        
        return cleaned_lyrics
    
    def _parse_lyrics_lines(self, lyrics_text: str) -> List[LyricLine]:
        """Divide el texto de las letras en líneas"""
        if not lyrics_text:
            return []
        
        lines = []
        for line_text in lyrics_text.split('\n'):
            # Ignorar líneas vacías
            if not line_text.strip():
                continue
                
            # Crear línea de letras
            line = LyricLine(text=line_text)
            lines.append(line)
        
        return lines