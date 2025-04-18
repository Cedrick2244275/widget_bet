# src/lyrics/lrclib_provider.py

import logging
import re
import json
from typing import Optional, List, Dict, Any
import requests
from .lyrics_provider import LyricsProvider, LyricsData, LyricLine

class LRCLibProvider(LyricsProvider):
    """Proveedor de letras usando la API de LRCLIB.net"""
    
    def __init__(self, cache_dir: str = None):
        super().__init__("LRCLib", cache_dir)
        self.base_url = "https://lrclib.net/api"
        self.debug = True  # Activar modo debug
    
    def _fetch_lyrics(self, title: str, artist: str, album: str = "") -> Optional[LyricsData]:
        """Obtiene letras de canciones de LRCLIB.net"""
        try:
            self._log_debug(f"Buscando letras para: {artist} - {title}")
            
            # Buscar las letras
            lyrics_data = self._search_lyrics(title, artist, album)
            if not lyrics_data:
                logging.info(f"No se encontraron letras en LRCLIB para: {artist} - {title}")
                return None
            
            self._log_debug(f"Letras encontradas en LRCLIB")
            
            # Verificar si hay letras sincronizadas disponibles
            synced_lyrics = lyrics_data.get("syncedLyrics")
            
            has_synced_lyrics = synced_lyrics is not None and len(synced_lyrics.strip()) > 0
            self._log_debug(f"Tiene letras sincronizadas: {has_synced_lyrics}")
            
            # Obtener las letras (sincronizadas o no)
            if has_synced_lyrics:
                # Usar las letras sincronizadas
                lyrics_text = synced_lyrics
                lines = self._parse_lrc_format(synced_lyrics)
            else:
                # Usar letras no sincronizadas (planas)
                lyrics_text = lyrics_data.get("plainLyrics", "")
                lines = self._parse_lyrics_lines(lyrics_text)
            
            return LyricsData(
                title=lyrics_data.get("trackName", title),
                artist=lyrics_data.get("artistName", artist),
                album=lyrics_data.get("albumName", album),
                lyrics_text=lyrics_text,
                lines=lines,
                source="LRCLib",
                has_synced_lyrics=has_synced_lyrics
            )
            
        except Exception as e:
            logging.error(f"Error al obtener letras de LRCLIB: {e}")
            import traceback
            self._log_debug(f"Traza de error: {traceback.format_exc()}")
            return None
    
    def _search_lyrics(self, title: str, artist: str, album: str = "") -> Optional[Dict[str, Any]]:
        """Busca letras en LRCLIB y devuelve los datos de la canción"""
        try:
            # Construir parámetros de búsqueda
            params = {
                "track_name": title,
                "artist_name": artist
            }
            
            if album:
                params["album_name"] = album
                
            self._log_debug(f"Parámetros de búsqueda: {params}")
            
            # Realizar solicitud de búsqueda
            url = f"{self.base_url}/search"
            self._log_debug(f"URL de búsqueda: {url}")
            
            response = requests.get(url, params=params)
            self._log_debug(f"Código de respuesta: {response.status_code}")
            
            if response.status_code != 200:
                self._log_debug(f"Error en respuesta HTTP: {response.status_code}")
                return None
            
            # Analizar resultados
            results = response.json()
            
            if not results or len(results) == 0:
                self._log_debug("No se encontraron resultados")
                return None
            
            # Tomar el primer resultado
            first_result = results[0]
            self._log_debug(f"Resultado encontrado: {first_result.get('trackName')} - {first_result.get('artistName')}")
            
            # Ahora obtenemos la información completa usando el ID del resultado
            track_id = first_result.get("id")
            if not track_id:
                self._log_debug("No se encontró ID de pista en el resultado")
                return None
                
            # Obtener detalles completos de la canción usando el ID
            lyrics_data = self._get_lyrics_by_id(track_id)
            return lyrics_data
            
        except Exception as e:
            logging.error(f"Error en búsqueda LRCLIB: {e}")
            import traceback
            self._log_debug(f"Traza de error en búsqueda: {traceback.format_exc()}")
            return None
    
    def _get_lyrics_by_id(self, track_id: int) -> Optional[Dict[str, Any]]:
        """Obtiene letras de LRCLIB por ID de canción"""
        try:
            url = f"{self.base_url}/get/{track_id}"
            self._log_debug(f"Obteniendo letras con URL: {url}")
            
            response = requests.get(url)
            
            if response.status_code != 200:
                self._log_debug(f"Error al obtener letras con ID {track_id}: {response.status_code}")
                return None
            
            lyrics_data = response.json()
            
            if not lyrics_data:
                self._log_debug(f"No se encontraron datos de letras para el ID {track_id}")
                return None
                
            return lyrics_data
            
        except Exception as e:
            logging.error(f"Error al obtener letras por ID de LRCLIB: {e}")
            import traceback
            self._log_debug(f"Traza de error: {traceback.format_exc()}")
            return None
    
    def _parse_lrc_format(self, lrc_text: str) -> List[LyricLine]:
        """Parsea letras en formato LRC y las convierte a líneas sincronizadas"""
        lines = []
        if not lrc_text:
            return lines
        
        # Patrón para buscar tiempos en formato LRC [MM:SS.ms]
        lrc_pattern = re.compile(r'\[(\d+):(\d+)\.(\d+)\](.*)')
        
        for line in lrc_text.strip().split('\n'):
            match = lrc_pattern.match(line)
            if match:
                try:
                    minutes, seconds, milliseconds, text = match.groups()
                    # Convertir a milisegundos para el formato interno
                    # Asegurarse de que milliseconds tenga 2 dígitos (algunos LRC usan 2 dígitos, otros 3)
                    if len(milliseconds) == 2:
                        milliseconds = int(milliseconds) * 10
                    else:
                        milliseconds = int(milliseconds)
                        
                    start_time_ms = (int(minutes) * 60 * 1000) + (int(seconds) * 1000) + milliseconds
                    
                    # Crear línea sincronizada
                    lyric_line = LyricLine(
                        text=text.strip(),
                        start_time_ms=start_time_ms,
                        end_time_ms=start_time_ms + 5000  # Valor temporal hasta que se ajuste
                    )
                    lines.append(lyric_line)
                except Exception as e:
                    self._log_debug(f"Error al parsear línea LRC: {line}, error: {e}")
        
        # Ordenar las líneas por tiempo
        lines.sort(key=lambda x: x.start_time_ms)
        
        # Ajustar los tiempos finales basados en las líneas siguientes
        for i in range(len(lines) - 1):
            lines[i].end_time_ms = lines[i+1].start_time_ms
        
        # Para la última línea, dejar el valor por defecto
        
        return lines
    
    def _parse_lyrics_lines(self, lyrics_text: str) -> List[LyricLine]:
        """Divide el texto de las letras no sincronizadas en líneas"""
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
        
    def _log_debug(self, message: str) -> None:
        """Registra mensajes de depuración si el modo debug está activado"""
        if self.debug:
            logging.debug(f"[LRCLib] {message}") 