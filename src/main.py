# src/main.py (actualización)

import os
import sys
import logging
from pathlib import Path
import traceback
from PyQt6.QtWidgets import QApplication, QMessageBox
import dotenv

from .config import Config
from .player_detection.detector import MusicDetectionManager
from .player_detection.spotify_detector import SpotifyDetector
from .player_detection.windows_media_detector import WindowsMediaDetector
from .player_detection.browser_detector import BrowserDetector
from .lyrics.lyrics_provider import LyricsData
from .lyrics.lyrics_manager import LyricsManager
from .lyrics.genius_provider import GeniusProvider
from .lyrics.lrclib_provider import LRCLibProvider
from .lyrics.netease_provider import NeteaseProvider
from .ui.main_window import MainWindow
from .ui.widget_mode import WidgetMode
from .ui.styles import Styles

def configure_logging():
    """Configura el sistema de registro"""
    log_dir = Path(os.path.expanduser("~")) / ".config" / "sunamu-windows" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    log_file = log_dir / "sunamu.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )

def exception_hook(exc_type, exc_value, exc_traceback):
    """Maneja excepciones no capturadas"""
    logging.error("Excepción no capturada:",
                 exc_info=(exc_type, exc_value, exc_traceback))
    traceback.print_exception(exc_type, exc_value, exc_traceback)

def main():
    """Función principal"""
    # Configurar registro
    configure_logging()
    
    # Configurar manejo de excepciones
    sys.excepthook = exception_hook
    
    # Cargar variables de entorno
    dotenv.load_dotenv()
    
    # Crear la aplicación
    app = QApplication(sys.argv)
    app.setApplicationName("Sunamu para Windows")
    app.setApplicationVersion("1.0.0")
    
    # Cargar configuración
    config = Config()
    
    # Configurar detector de música
    music_manager = MusicDetectionManager()
    
    # Configurar Spotify
    if config.get("players", "spotify", {}).get("enabled", True):
        spotify_client_id = config.get("players", "spotify", {}).get("client_id", "") or os.getenv("SPOTIFY_CLIENT_ID", "")
        spotify_client_secret = config.get("players", "spotify", {}).get("client_secret", "") or os.getenv("SPOTIFY_CLIENT_SECRET", "")
        
        if spotify_client_id and spotify_client_secret:
            spotify_detector = SpotifyDetector(
                client_id=spotify_client_id,
                client_secret=spotify_client_secret
            )
            music_manager.register_detector(spotify_detector)
            logging.info("Detector de Spotify configurado")
        else:
            logging.warning("No se encontraron credenciales de Spotify")
    
    # Configurar detector de Windows Media
    if config.get("players", "windows_media", {}).get("enabled", True):
        windows_media_detector = WindowsMediaDetector()
        music_manager.register_detector(windows_media_detector)
        logging.info("Detector de Windows Media configurado")
    
    # Configurar detector de navegadores
    if config.get("players", "browsers", {}).get("enabled", True):
        browser_detector = BrowserDetector()
        music_manager.register_detector(browser_detector)
        logging.info("Detector de navegadores configurado")
    
    # Inicializar detectores
    music_manager.initialize_detectors()
    
    # Configurar gestor de letras
    lyrics_manager = LyricsManager()
    
    # Registrar proveedores de letras según la configuración y el nuevo orden de prioridades:
    # 1. LRCLIB
    # 2. NetEase
    # 3. Genius
    
    # 1. LRCLIB (prioridad más alta = 0)
    if config.get("lyrics", "providers", {}).get("lrclib", {}).get("enabled", True):
        lrclib_provider = LRCLibProvider(cache_dir=str(config.lyrics_cache_dir))
        # Prioridad 0 (máxima prioridad)
        lyrics_manager.register_provider(lrclib_provider, priority=0)
        logging.info("Proveedor de letras LRCLIB configurado con prioridad 0 (máxima)")
    
    # 2. NetEase (prioridad = 1)
    if config.get("lyrics", "providers", {}).get("netease", {}).get("enabled", True):
        netease_provider = NeteaseProvider(cache_dir=str(config.lyrics_cache_dir))
        lyrics_manager.register_provider(netease_provider, priority=1)
        logging.info("Proveedor de letras NetEase configurado con prioridad 1")
    
    # 3. Genius (prioridad = 2)
    if config.get("lyrics", "providers", {}).get("genius", {}).get("enabled", True):
        genius_api_key = (
            config.get("lyrics", "providers", {}).get("genius", {}).get("api_key", "") or 
            os.getenv("GENIUS_API_KEY", "")
        )
        if genius_api_key:
            genius_provider = GeniusProvider(
                api_key=genius_api_key,
                cache_dir=str(config.lyrics_cache_dir)
            )
            lyrics_manager.register_provider(genius_provider, priority=2)
            logging.info("Proveedor de letras Genius configurado con prioridad 2")
        else:
            logging.warning("No se encontró la clave API de Genius")
    
    # Crear y mostrar la ventana principal
    main_window = MainWindow(config, music_manager, lyrics_manager)
    main_window.show()
    
    # Ejecutar la aplicación
    return app.exec()

if __name__ == "__main__":
    sys.exit(main())