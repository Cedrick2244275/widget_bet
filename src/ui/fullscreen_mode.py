# src/ui/fullscreen_mode.py
# Implementación del modo pantalla completa

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMainWindow

class FullscreenMode:
    """Proporciona funcionalidad para el modo pantalla completa"""
    
    def __init__(self, main_window: QMainWindow):
        self.main_window = main_window
    
    def enable(self):
        """Activa el modo pantalla completa"""
        self.main_window.showFullScreen()
    
    def disable(self):
        """Desactiva el modo pantalla completa"""
        self.main_window.showNormal()
