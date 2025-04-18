# src/player_detection/windows_media_detector.py

import logging
import time
import winreg
import ctypes
from typing import Optional, Dict, List
import os
import sys
import pythoncom
import win32com.client
import win32gui
import win32process
import psutil
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioSessionControl, IAudioSessionControl2
import pygetwindow

from .detector import PlayerDetector, MusicInfo, PlayerControls

class WindowsMediaDetector(PlayerDetector):
    """
    Detector para reproductores de Windows usando Media Session y SMTC.
    
    Este detector ha sido mejorado para evitar el reinicio constante de detección
    mediante las siguientes estrategias:
    
    1. Caché de la última pista detectada y devolverla si no ha pasado suficiente tiempo
    2. Generación de IDs consistentes para cada pista
    3. Mecanismo de conteo de estabilidad para evitar cambios rápidos
    4. Estimación automática de posición entre actualizaciones
    """
    
    def __init__(self):
        super().__init__("Windows Media")
        self.last_update_time = 0
        self.update_interval = 5  # Aumentado a 5 segundos para reducir frecuencia de actualizaciones
        self.media_sessions = []
        self.controls = PlayerControls(
            can_play=True,
            can_pause=True,
            can_next=True,
            can_previous=True,
            can_seek=False,
            can_shuffle=False,
            can_repeat=False
        )
        self.current_track_info = None
        self.last_track_signature = ""
        # Variables para el mecanismo de estabilidad
        self.last_detected_track = None  # Caché de la última pista detectada
        self.track_stable_count = 0      # Contador de veces que se ha detectado la misma pista
        # Lista de reproductores soportados
        self.SUPPORTED_PLAYERS = [
            "spotify.exe", 
            "chrome.exe", 
            "msedge.exe", 
            "firefox.exe", 
            "musicbee.exe", 
            "vlc.exe", 
            "winamp.exe", 
            "itunes.exe", 
            "groove.exe", 
            "wmplayer.exe", 
            "foobar2000.exe"
        ]
    
    def initialize(self) -> bool:
        """Inicializa la detección de reproductores de Windows"""
        try:
            # Inicializamos COM
            pythoncom.CoInitialize()
            self.is_available = True
            return True
        except Exception as e:
            logging.error(f"Error al inicializar WindowsMediaDetector: {e}")
            self.is_available = False
            return False
    
    def get_current_track(self):
        """Obtiene información sobre la pista actual"""
        try:
            # Controlar frecuencia de actualización
            current_time = time.time()
            if current_time - self.last_update_time < self.update_interval:
                # Si no ha pasado suficiente tiempo, devolvemos la última información detectada
                return self.last_detected_track
            
            self.last_update_time = current_time
            
            # Usar AudioUtilities de pycaw para obtener sesiones de audio
            sessions = AudioUtilities.GetAllSessions()
            
            # Lista para almacenar procesos de reproductor detectados
            detected_players = []
            
            # Primero, identificamos procesos que podrían ser reproductores de música
            for session in sessions:
                if session.Process and session.Process.name().lower() in self.SUPPORTED_PLAYERS:
                    is_playing = True  # Suponemos que está reproduciendo si tiene una sesión activa
                    detected_players.append({
                        'process': session.Process,
                        'is_playing': is_playing
                    })
            
            # Si no hay reproductores detectados, salir
            if not detected_players:
                self.last_detected_track = None
                self.track_stable_count = 0
                return None
            
            # Buscar información en ventanas activas de los procesos detectados
            detected_track = None
            
            for player in detected_players:
                process = player['process']
                
                # Obtener todas las ventanas con título
                windows = pygetwindow.getWindowsWithTitle('')
                
                for window in windows:
                    if not window.title:
                        continue
                    
                    # Verificar si esta ventana pertenece al proceso actual
                    try:
                        win_pid = win32process.GetWindowThreadProcessId(window._hWnd)[1]
                        if win_pid != process.pid:
                            continue
                    except Exception:
                        continue
                    
                    title = window.title.strip()
                    process_name = process.name().lower()
                    
                    # Spotify
                    if process_name == "spotify.exe" and " - " in title and title.endswith(" - Spotify"):
                        title = title[:-10]  # Eliminar " - Spotify"
                        parts = title.split(" - ")
                        
                        if len(parts) >= 2:
                            track_title = parts[0].strip()
                            artist = parts[1].strip()
                            
                            # ID estable para Spotify
                            unique_id = f"spotify:{artist}:{track_title}".lower()
                            
                            # Obtener duración y posición
                            duration_ms, position_ms = self._get_track_position()
                            is_playing = player['is_playing']
                            
                            detected_track = MusicInfo(
                                title=track_title,
                                artist=artist,
                                album="",
                                album_art_url="",
                                duration_ms=duration_ms,
                                position_ms=position_ms,
                                is_playing=is_playing,
                                player_name="Spotify",
                                track_id=unique_id
                            )
                            break
                    
                    # Navegadores (YouTube, YouTube Music, etc.)
                    elif process_name in ["chrome.exe", "msedge.exe", "firefox.exe"]:
                        # YouTube Music
                        if " - YouTube Music" in title:
                            parts = title.replace(" - YouTube Music", "").split(" - ")
                            if len(parts) >= 2:
                                track_title = parts[0].strip()
                                artist = parts[1].strip()
                                
                                # ID estable para YouTube Music
                                unique_id = f"ytmusic:{artist}:{track_title}".lower()
                                
                                # Obtener duración y posición
                                duration_ms, position_ms = self._get_track_position()
                                is_playing = player['is_playing']
                                
                                detected_track = MusicInfo(
                                    title=track_title,
                                    artist=artist,
                                    album="",
                                    album_art_url="",
                                    duration_ms=duration_ms,
                                    position_ms=position_ms,
                                    is_playing=is_playing,
                                    player_name="YouTube Music",
                                    track_id=unique_id
                                )
                                break
                        
                        # YouTube
                        elif " - YouTube" in title:
                            track_title = title.replace(" - YouTube", "").strip()
                            if len(track_title) > 3:  # Ignorar títulos muy cortos
                                # Obtener duración y posición
                                duration_ms, position_ms = self._get_track_position()
                                is_playing = player['is_playing']
                                
                                detected_track = MusicInfo(
                                    title=track_title,
                                    artist="YouTube",
                                    album="",
                                    album_art_url="",
                                    duration_ms=duration_ms,
                                    position_ms=position_ms,
                                    is_playing=is_playing,
                                    player_name="YouTube",
                                    track_id=f"youtube_{hash(track_title) % 1000000}"
                                )
                                break
                    
                    # Detector genérico con formato "Artista - Título" para Windows Media Player y otros
                    elif " - " in title:
                        parts = title.split(" - ")
                        if len(parts) >= 2:
                            try:
                                artist = parts[0].strip()
                                track_title = parts[1].strip()
                                
                                # ID estable para el reproductor genérico
                                unique_id = f"generic:{artist}:{track_title}".lower()
                                
                                # Obtener duración y posición
                                duration_ms, position_ms = self._get_track_position()
                                is_playing = player['is_playing']
                                
                                detected_track = MusicInfo(
                                    title=track_title,
                                    artist=artist,
                                    album="",
                                    album_art_url="",
                                    duration_ms=duration_ms,
                                    position_ms=position_ms,
                                    is_playing=is_playing,
                                    player_name=process_name.replace(".exe", "").capitalize(),
                                    track_id=unique_id
                                )
                                break
                            except Exception as e:
                                logging.debug(f"Error al parsear título de ventana genérico: {e}")
                
                if detected_track:
                    break
            
            # Si no pudimos obtener detalles del reproductor pero hay uno activo, devolver información genérica
            if not detected_track and detected_players:
                process = detected_players[0]['process']
                process_name = process.name().lower()
                player_name = process_name.replace(".exe", "").capitalize()
                # Obtener duración y posición
                duration_ms, position_ms = self._get_track_position()
                is_playing = True
                
                detected_track = MusicInfo(
                    title=f"Reproduciendo en {player_name}",
                    artist="",
                    album="",
                    album_art_url="",
                    duration_ms=duration_ms,
                    position_ms=position_ms,
                    is_playing=is_playing,
                    player_name=player_name,
                    track_id=f"{player_name.lower().replace(' ', '_')}_player"
                )
            
            # Mecanismo de estabilidad: comparar con la pista anterior para evitar cambios constantes
            if self.last_detected_track and detected_track:
                # Comparar títulos y artistas para determinar si es la misma pista
                last_track_id = self.last_detected_track.get_unique_id()
                current_track_id = detected_track.get_unique_id()
                
                if last_track_id == current_track_id:
                    # Es la misma pista, actualizar solo la posición
                    self.track_stable_count += 1
                    detected_track.position_ms = self.last_detected_track.position_ms + (self.update_interval * 1000)
                    
                    # Limitar la posición a la duración
                    if detected_track.position_ms > detected_track.duration_ms:
                        detected_track.position_ms = detected_track.duration_ms
                else:
                    # Es una pista diferente, reiniciar el contador de estabilidad
                    self.track_stable_count = 0
                    
                # Si hemos visto la misma pista varias veces, mantener is_playing
                if self.track_stable_count > 1:
                    detected_track.is_playing = self.last_detected_track.is_playing
            
            # Actualizar la pista detectada para la próxima iteración
            self.last_detected_track = detected_track
            return detected_track
            
        except Exception as e:
            logging.error(f"Error al detectar pista actual: {e}")
            return self.last_detected_track
    
    def _get_browser_track_info(self, pid: int) -> Optional[MusicInfo]:
        """Intenta obtener información de la pista de un navegador"""
        try:
            # Obtener todas las ventanas del proceso
            def enum_window_callback(hwnd, windows):
                _, found_pid = win32process.GetWindowThreadProcessId(hwnd)
                if found_pid == pid and win32gui.IsWindowVisible(hwnd):
                    windows.append(hwnd)
                return True
            
            windows = []
            win32gui.EnumWindows(enum_window_callback, windows)
            
            for hwnd in windows:
                title = win32gui.GetWindowText(hwnd)
                
                # Verificar si el título contiene patrones de reproductores web
                if " - YouTube" in title:
                    # Formato típico: "Nombre de la canción - YouTube"
                    track_title = title.replace(" - YouTube", "").strip()
                    # Crear un track_id basado en el título para estabilidad
                    track_id = f"youtube_{hash(track_title) % 1000000}"
                    
                    # Obtener duración y posición
                    duration_ms, position_ms = self._get_track_position()
                    is_playing = True
                    
                    return MusicInfo(
                        title=track_title,
                        artist="YouTube",
                        album="",
                        player_name="YouTube",
                        is_playing=is_playing,
                        track_id=track_id,
                        duration_ms=duration_ms,
                        position_ms=position_ms
                    )
                elif " | Spotify" in title:
                    # Formato típico: "Artista - Canción | Spotify"
                    track_info = title.replace(" | Spotify", "").strip()
                    if " - " in track_info:
                        artist, track_title = track_info.split(" - ", 1)
                        # Crear un track_id basado en el título y artista para estabilidad
                        track_id = f"spotify_web_{hash(artist + track_title) % 1000000}"
                        
                        # Obtener duración y posición
                        duration_ms, position_ms = self._get_track_position()
                        is_playing = True
                        
                        return MusicInfo(
                            title=track_title,
                            artist=artist,
                            album="",
                            player_name="Spotify Web",
                            is_playing=is_playing,
                            track_id=track_id,
                            duration_ms=duration_ms,
                            position_ms=position_ms
                        )
            
            return None
            
        except Exception as e:
            logging.error(f"Error al obtener información del navegador: {e}")
            return None
    
    def _get_smtc_track_info(self, process_name: str) -> Optional[MusicInfo]:
        """Intenta obtener información de la pista usando SMTC (System Media Transport Controls)"""
        try:
            # Esta es una simulación ya que no podemos implementar SMTC completo sin C#/C++
            # En una implementación real, usaríamos Windows.Media.Control namespace
            
            # Intentamos obtener información básica del registro para algunos reproductores
            if process_name == "spotify.exe":
                try:
                    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Spotify\Spotify")
                    value, _ = winreg.QueryValueEx(key, "LastPlaylist")
                    winreg.CloseKey(key)
                    
                    # Solo podemos determinar que Spotify está activo
                    return MusicInfo(
                        title="Reproduciendo en Spotify",
                        artist="",
                        album="",
                        player_name="Spotify",
                        is_playing=True,
                        track_id="spotify_player",  # Añadir un track_id estable
                        duration_ms=180000,  # 3 minutos por defecto
                        position_ms=0
                    )
                except:
                    pass
            
            # Para otros reproductores, solo podemos detectar que están activos
            player_name_map = {
                "spotify.exe": "Spotify",
                "musicbee.exe": "MusicBee",
                "vlc.exe": "VLC",
                "winamp.exe": "Winamp",
                "itunes.exe": "iTunes",
                "groove.exe": "Groove Music",
                "wmplayer.exe": "Windows Media Player",
                "foobar2000.exe": "foobar2000"
            }
            
            player_name = player_name_map.get(process_name, process_name)
            
            # Crear un track_id estable basado en el nombre del reproductor
            track_id = f"{player_name.lower().replace(' ', '_')}_player"
            
            # Obtener duración y posición
            duration_ms, position_ms = self._get_track_position()
            is_playing = True
            
            return MusicInfo(
                title=f"Reproduciendo en {player_name}",
                artist="",
                album="",
                player_name=player_name,
                is_playing=is_playing,
                track_id=track_id,  # Añadir un track_id estable
                duration_ms=duration_ms,
                position_ms=position_ms
            )
            
        except Exception as e:
            logging.error(f"Error al obtener información SMTC: {e}")
            return None
    
    def play(self) -> bool:
        """Inicia la reproducción"""
        # Simular combinación de teclas para reproducir
        try:
            import pyautogui
            pyautogui.press('playpause')
            # Actualizar el estado de la reproducción
            if self.last_detected_track:
                self.last_detected_track.is_playing = True
            return True
        except:
            return False
    
    def pause(self) -> bool:
        """Pausa la reproducción"""
        # Simular combinación de teclas para pausar
        try:
            import pyautogui
            pyautogui.press('playpause')
            # Actualizar el estado de la reproducción
            if self.last_detected_track:
                self.last_detected_track.is_playing = False
            return True
        except:
            return False
    
    def next_track(self) -> bool:
        """Pasa a la siguiente pista"""
        try:
            import pyautogui
            pyautogui.press('nexttrack')
            # Invalidar la pista actual para forzar una nueva detección
            self.last_detected_track = None
            self.track_stable_count = 0
            return True
        except:
            return False
    
    def previous_track(self) -> bool:
        """Vuelve a la pista anterior"""
        try:
            import pyautogui
            pyautogui.press('prevtrack')
            # Invalidar la pista actual para forzar una nueva detección
            self.last_detected_track = None
            self.track_stable_count = 0
            return True
        except:
            return False
    
    def seek(self, position_ms: int) -> bool:
        """No es posible buscar una posición específica con este método"""
        return False
    
    def set_shuffle(self, state: bool) -> bool:
        """No es posible establecer el estado de reproducción aleatoria con este método"""
        return False
    
    def set_repeat(self, state: bool) -> bool:
        """No es posible establecer el estado de repetición con este método"""
        return False

    def _get_track_position(self):
        """Obtiene la duración y posición actuales en milisegundos"""
        # Como no podemos obtener esta información directamente, devolvemos valores predeterminados
        # En una implementación real, esta información se obtendría del reproductor
        duration_ms = 180000  # 3 minutos por defecto
        
        # Si tenemos una pista detectada, intentar estimar la posición
        if self.last_detected_track and self.last_detected_track.position_ms > 0:
            # Incrementar la posición basada en el tiempo transcurrido desde la última actualización
            position_ms = self.last_detected_track.position_ms + 1000  # Incremento de 1 segundo
            
            # Evitar superar la duración total
            if position_ms > duration_ms:
                position_ms = 0  # Reset si llegamos al final
        else:
            position_ms = 0  # Comenzando desde el principio
            
        return duration_ms, position_ms