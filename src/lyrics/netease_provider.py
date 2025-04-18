# src/lyrics/netease_provider.py

import logging
import re
import json
import time
from typing import Optional, List, Dict, Any
import requests
from .lyrics_provider import LyricsProvider, LyricsData, LyricLine

class NeteaseProvider(LyricsProvider):
    """Proveedor de letras usando NetEase Music (China)"""
    
    def __init__(self, cache_dir: str = None):
        super().__init__("NetEase", cache_dir)
        # API alternativa para evitar bloqueo geográfico - servidores públicos de Netease API
        self.base_url = "https://netease-cloud-music-api-gamma-amber.vercel.app"
        self.search_url = f"{self.base_url}/search"
        self.lyric_url = f"{self.base_url}/lyric"
        
        # Activar registros detallados
        self.debug = True
        
        # Headers comunes para las solicitudes
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "application/json, text/plain, */*"
        }
    
    def _fetch_lyrics(self, title: str, artist: str, album: str = "") -> Optional[LyricsData]:
        """Obtiene letras de canciones de NetEase Music"""
        try:
            # Buscar la canción
            self._log_debug(f"Iniciando búsqueda en NetEase para: {artist} - {title}")
            
            # Intentar primero con título y artista combinados
            song_id = self._search_song(title, artist)
            
            # Si no se encuentra, intentar solo con el título
            if not song_id:
                self._log_debug(f"Intentando búsqueda solo con título: {title}")
                song_id = self._search_song(title, "")
            
            # Si aún no hay resultados, intentar con términos alternativos
            if not song_id:
                # Para artistas occidentales, pueden estar listados con nombres diferentes
                alt_title = self._normalize_title(title)
                self._log_debug(f"Intentando búsqueda con título normalizado: {alt_title}")
                song_id = self._search_song(alt_title, artist)
            
            if not song_id:
                logging.info(f"No se encontró canción en NetEase para: {artist} - {title}")
                return None
            
            self._log_debug(f"Canción encontrada con ID: {song_id}")
            
            # Obtener las letras
            lyrics_data = self._get_lyrics(song_id)
            if not lyrics_data:
                self._log_debug("No se pudieron obtener datos de letras")
                return None
            
            self._log_debug(f"Datos de letras obtenidos: {list(lyrics_data.keys()) if isinstance(lyrics_data, dict) else 'No es diccionario'}")
            
            # Extraer el texto de las letras según la estructura de la respuesta
            lyrics_text = ""
            if isinstance(lyrics_data, dict):
                if "lrc" in lyrics_data:
                    if isinstance(lyrics_data["lrc"], dict) and "lyric" in lyrics_data["lrc"]:
                        lyrics_text = lyrics_data["lrc"]["lyric"]
                    elif isinstance(lyrics_data["lrc"], str):
                        lyrics_text = lyrics_data["lrc"]
                
                # Si no hay letras, intentar con tlyric (letras traducidas)
                if not lyrics_text and "tlyric" in lyrics_data:
                    if isinstance(lyrics_data["tlyric"], dict) and "lyric" in lyrics_data["tlyric"]:
                        lyrics_text = lyrics_data["tlyric"]["lyric"]
                    elif isinstance(lyrics_data["tlyric"], str):
                        lyrics_text = lyrics_data["tlyric"]
            
            if not lyrics_text:
                self._log_debug(f"No se encontraron letras para song_id: {song_id}")
                return None
            
            # Procesar las letras (pueden estar sincronizadas)
            has_synced_lyrics = "[" in lyrics_text and "]" in lyrics_text
            lines = self._parse_lyrics_lines(lyrics_text)
            
            return LyricsData(
                title=title,
                artist=artist,
                album=album,
                lyrics_text=self._clean_lyrics_text(lyrics_text),
                lines=lines,
                source="NetEase",
                has_synced_lyrics=has_synced_lyrics
            )
            
        except Exception as e:
            logging.error(f"Error al obtener letras de NetEase: {e}")
            import traceback
            self._log_debug(f"Traza de error: {traceback.format_exc()}")
            return None
    
    def _search_song(self, title: str, artist: str) -> Optional[int]:
        """Busca una canción en NetEase Music y devuelve su ID"""
        try:
            # Preparar query
            query = f"{title} {artist}".strip()
                
            self._log_debug(f"Búsqueda con query: '{query}'")
            
            # Realizar la solicitud GET
            url = f"{self.search_url}?keywords={query}&limit=30&type=1"
            response = requests.get(url, headers=self.headers)
            
            self._log_debug(f"Respuesta HTTP: {response.status_code}")
            
            if response.status_code != 200:
                logging.error(f"Error al buscar en NetEase: Status {response.status_code}")
                return None
            
            try:
                data = response.json()
            except json.JSONDecodeError:
                self._log_debug(f"Error al decodificar JSON, respuesta: {response.text[:200]}")
                return None
                
            self._log_debug(f"Claves en respuesta JSON: {list(data.keys()) if data else None}")
            
            # Verificar si hay resultados
            if not data or "result" not in data or not data["result"] or "songs" not in data["result"]:
                self._log_debug(f"Respuesta completa: {data}")
                logging.warning("No se encontraron resultados en NetEase")
                return None
            
            songs = data["result"]["songs"]
            song_count = len(songs)
            self._log_debug(f"Encontradas {song_count} canciones")
            
            if not song_count:
                return None
                
            # Registrar las primeras 3 canciones para depuración
            if self.debug and song_count > 0:
                for i, song in enumerate(songs[:min(3, song_count)]):
                    name = song.get("name", "")
                    
                    # Obtener artistas
                    artists = []
                    if "artists" in song and isinstance(song["artists"], list):
                        artists = [a.get("name", "") for a in song["artists"]]
                    elif "ar" in song and isinstance(song["ar"], list):
                        artists = [a.get("name", "") for a in song["ar"]]
                    
                    song_id = song.get("id")
                    self._log_debug(f"Canción {i+1}: ID={song_id}, Nombre='{name}', Artistas={artists}")
            
            # Si no hay artista, devolver la primera coincidencia
            if not artist.strip():
                return songs[0].get("id")
            
            # Intentar encontrar la mejor coincidencia
            best_match = None
            highest_score = 0
            
            for song in songs:
                song_name = song.get("name", "").lower()
                
                # Obtener artistas
                song_artists = []
                if "artists" in song and isinstance(song["artists"], list):
                    song_artists = [artist.get("name", "").lower() for artist in song["artists"]]
                elif "ar" in song and isinstance(song["ar"], list):
                    song_artists = [artist.get("name", "").lower() for artist in song["ar"]]
                
                # Obtener aliases/títulos alternativos
                song_aliases = []
                if "alias" in song and isinstance(song["alias"], list):
                    song_aliases = [alias.lower() for alias in song["alias"]]
                elif "alia" in song and isinstance(song["alia"], list):
                    song_aliases = [alias.lower() for alias in song["alia"]]
                
                # Normalizar título para comparación
                norm_song_name = self._normalize_title(song_name)
                norm_title = self._normalize_title(title.lower())
                
                # Calcular puntuación de coincidencia
                title_score = max([
                    self._similarity_score(song_name, title.lower()),
                    self._similarity_score(norm_song_name, norm_title)
                ])
                
                # Comprobar si hay coincidencia en alias
                for alias in song_aliases:
                    alias_score = self._similarity_score(alias, title.lower())
                    if alias_score > title_score:
                        title_score = alias_score
                
                # Verificar artista
                artist_score = 0
                if artist.strip():
                    artist_scores = [self._similarity_score(song_artist, artist.lower()) for song_artist in song_artists]
                    if artist_scores:
                        artist_score = max(artist_scores)
                
                # Puntaje combinado (mayor peso al título)
                if artist.strip():
                    combined_score = title_score * 0.7 + artist_score * 0.3
                else:
                    combined_score = title_score
                
                self._log_debug(f"Canción: '{song_name}' por {song_artists} - Puntuación: {combined_score:.2f} (Título: {title_score:.2f}, Artista: {artist_score:.2f})")
                
                if combined_score > highest_score:
                    highest_score = combined_score
                    best_match = song
            
            # Si encontramos una coincidencia razonable
            if best_match and highest_score > 0.3:  # Umbral más bajo para encontrar más coincidencias
                self._log_debug(f"Mejor coincidencia: {best_match.get('name')} (ID: {best_match.get('id')}) con puntuación {highest_score:.2f}")
                return best_match.get("id")
            
            # Si no hay coincidencia razonable, devolver el primer resultado
            if songs:
                self._log_debug(f"Sin coincidencia con umbral, usando primera canción: {songs[0].get('name')} (ID: {songs[0].get('id')})")
                return songs[0].get("id")
            
            return None
            
        except Exception as e:
            logging.error(f"Error al buscar canción en NetEase: {e}")
            import traceback
            self._log_debug(f"Traza de error en búsqueda: {traceback.format_exc()}")
            return None
    
    def _normalize_title(self, title: str) -> str:
        """Normaliza el título de la canción para mejorar coincidencias"""
        # Eliminar paréntesis y su contenido (versiones, remixes, etc.)
        normalized = re.sub(r'\([^)]*\)', '', title)
        # Eliminar corchetes y su contenido
        normalized = re.sub(r'\[[^\]]*\]', '', normalized)
        # Eliminar - y lo que sigue (típicamente remix, version, etc.)
        normalized = re.sub(r'\s*-\s*.*$', '', normalized)
        # Eliminar caracteres especiales
        normalized = re.sub(r'[^\w\s]', '', normalized)
        # Normalizar espacios
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        return normalized
    
    def _similarity_score(self, str1: str, str2: str) -> float:
        """Calcula un puntaje de similitud entre dos cadenas"""
        # Eliminar caracteres especiales y normalizar espacios
        str1 = re.sub(r'[^\w\s]', '', str1).strip()
        str2 = re.sub(r'[^\w\s]', '', str2).strip()
        
        if not str1 or not str2:
            return 0.0
        
        # Si son iguales
        if str1 == str2:
            return 1.0
        
        # Si uno está contenido en el otro
        if str1 in str2:
            return 0.9
        if str2 in str1:
            return 0.9
        
        # Comparación de palabras comunes
        words1 = set(str1.split())
        words2 = set(str2.split())
        
        if not words1 or not words2:
            return 0.0
        
        common_words = words1.intersection(words2)
        
        return len(common_words) / max(len(words1), len(words2))
    
    def _get_lyrics(self, song_id: int) -> Optional[Dict[str, Any]]:
        """Obtiene las letras de una canción de NetEase por su ID"""
        try:
            self._log_debug(f"Obteniendo letras para song_id: {song_id}")
            url = f"{self.lyric_url}?id={song_id}"
            response = requests.get(url, headers=self.headers)
            
            if response.status_code != 200:
                logging.error(f"Error al obtener letras de NetEase: Status {response.status_code}")
                return None
            
            try:
                data = response.json()
            except json.JSONDecodeError:
                self._log_debug(f"Error al decodificar JSON de letras, respuesta: {response.text[:200]}")
                return None
                
            self._log_debug(f"Respuesta de letras obtenida con claves: {list(data.keys()) if data else None}")
            
            return data
            
        except Exception as e:
            logging.error(f"Error al obtener letras de NetEase: {e}")
            return None
    
    def _parse_lyrics_lines(self, lyrics_text: str) -> List[LyricLine]:
        """Divide el texto de las letras en líneas, procesando las marcas de tiempo si existen"""
        if not lyrics_text:
            return []
        
        lines = []
        time_pattern = re.compile(r'\[(\d+):(\d+)\.(\d+)\](.*)')
        
        for line_text in lyrics_text.split('\n'):
            # Ignorar líneas vacías
            if not line_text.strip():
                continue
            
            # Comprobar si hay marcas de tiempo
            match = time_pattern.match(line_text)
            if match:
                minutes, seconds, milliseconds, text = match.groups()
                start_time_ms = (int(minutes) * 60 * 1000) + (int(seconds) * 1000) + int(milliseconds)
                line = LyricLine(text=text.strip(), start_time_ms=start_time_ms, end_time_ms=start_time_ms + 5000)
            else:
                # Sin marcas de tiempo
                line = LyricLine(text=line_text.strip())
            
            lines.append(line)
        
        # Ajustar los tiempos de finalización basados en la línea siguiente
        for i in range(len(lines) - 1):
            if lines[i].is_synced() and lines[i+1].is_synced():
                lines[i].end_time_ms = lines[i+1].start_time_ms
        
        return lines
    
    def _clean_lyrics_text(self, lyrics_text: str) -> str:
        """Limpia el texto de las letras eliminando las marcas de tiempo"""
        if not lyrics_text:
            return ""
        
        # Eliminar marcas de tiempo
        cleaned_text = re.sub(r'\[\d+:\d+\.\d+\]', '', lyrics_text)
        
        # Eliminar líneas vacías
        lines = [line.strip() for line in cleaned_text.split('\n') if line.strip()]
        
        return '\n'.join(lines)
    
    def _log_debug(self, message: str) -> None:
        """Registra mensajes de depuración si el modo debug está activado"""
        if self.debug:
            logging.debug(f"[NetEase] {message}")