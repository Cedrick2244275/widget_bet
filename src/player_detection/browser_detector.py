import logging
from typing import Optional
import win32gui
import win32process
import psutil

from .detector import PlayerDetector, MusicInfo, PlayerControls

class BrowserDetector(PlayerDetector):
    """Detector para reproductores web en navegadores"""
    
    def __init__(self):
        super().__init__("Browser")
        self.browser_processes = ["chrome.exe", "msedge.exe", "firefox.exe", "opera.exe", "brave.exe"]
        self.controls = PlayerControls(
            can_play=False,
            can_pause=False,
            can_next=False,
            can_previous=False,
            can_seek=False,
            can_shuffle=False,
            can_repeat=False
        )
    
    def initialize(self) -> bool:
        """Inicializa el detector de navegadores"""
        try:
            # No hay mucho que inicializar, solo verificamos si hay navegadores ejecutándose
            for proc in psutil.process_iter(['name']):
                if proc.info['name'] and proc.info['name'].lower() in self.browser_processes:
                    self.is_available = True
                    return True
            
            return False
        except Exception as e:
            logging.error(f"Error al inicializar BrowserDetector: {e}")
            self.is_available = False
            return False
    
    def get_current_track(self) -> Optional[MusicInfo]:
        """Obtiene información sobre la pista actual de navegadores"""
        if not self.is_available:
            return None
        
        try:
            # Buscar ventanas de navegadores que contengan títulos de reproductores
            windows_info = []
            
            def enum_window_callback(hwnd, windows_info):
                if not win32gui.IsWindowVisible(hwnd):
                    return True
                
                title = win32gui.GetWindowText(hwnd)
                if not title:
                    return True
                
                # Verificar si el título indica reproducción de música
                if any(pattern in title for pattern in [" - YouTube", "| Spotify", "| YouTube Music"]):
                    try:
                        _, pid = win32process.GetWindowThreadProcessId(hwnd)
                        proc = psutil.Process(pid)
                        if proc.name().lower() in self.browser_processes:
                            windows_info.append((hwnd, title, proc.name()))
                    except:
                        pass
                return True
            
            win32gui.EnumWindows(enum_window_callback, windows_info)
            
            # Procesar las ventanas encontradas
            for hwnd, title, process_name in windows_info:
                # YouTube
                if " - YouTube" in title:
                    track_title = title.replace(" - YouTube", "").strip()
                    if len(track_title) > 3:  # Ignorar títulos muy cortos
                        return MusicInfo(
                            title=track_title,
                            artist="YouTube",
                            album="",
                            player_name="YouTube",
                            is_playing=True
                        )
                
                # Spotify Web
                elif " | Spotify" in title:
                    track_info = title.replace(" | Spotify", "").strip()
                    if " - " in track_info:
                        artist, track_title = track_info.split(" - ", 1)
                        return MusicInfo(
                            title=track_title,
                            artist=artist,
                            album="",
                            player_name="Spotify Web",
                            is_playing=True
                        )
                
                # YouTube Music
                elif " - YouTube Music" in title:
                    track_info = title.replace(" - YouTube Music", "").strip()
                    if " - " in track_info:
                        artist, track_title = track_info.split(" - ", 1)
                        return MusicInfo(
                            title=track_title,
                            artist=artist,
                            album="",
                            player_name="YouTube Music",
                            is_playing=True
                        )
            
            return None
            
        except Exception as e:
            logging.error(f"Error al obtener pista actual de navegador: {e}")
            return None
    
    def play(self) -> bool:
        """No implementado para navegadores"""
        return False
    
    def pause(self) -> bool:
        """No implementado para navegadores"""
        return False
    
    def next_track(self) -> bool:
        """No implementado para navegadores"""
        return False
    
    def previous_track(self) -> bool:
        """No implementado para navegadores"""
        return False
    
    def seek(self, position_ms: int) -> bool:
        """No implementado para navegadores"""
        return False
    
    def set_shuffle(self, state: bool) -> bool:
        """No implementado para navegadores"""
        return False
    
    def set_repeat(self, state: bool) -> bool:
        """No implementado para navegadores"""
        return False
