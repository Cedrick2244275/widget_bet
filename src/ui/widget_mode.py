# src/ui/widget_mode.py
# Implementación del modo widget

from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtWidgets import QMainWindow

class WidgetMode:
    """Proporciona funcionalidad para el modo widget (pequeño, sin bordes, arrastrable)"""
    
    def __init__(self, main_window: QMainWindow):
        self.main_window = main_window
        self.draggable = True
        self.drag_position = QPoint()
    
    def enable(self):
        """Activa el modo widget"""
        # Configurar ventana sin marco y como herramienta
        self.main_window.setWindowFlags(
            Qt.WindowType.Tool | 
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint
        )
        
        # Ajustar tamaño
        self.main_window.resize(400, 200)
        
        # Es necesario volver a mostrar la ventana
        self.main_window.show()
    
    def disable(self):
        """Desactiva el modo widget"""
        # Restaurar a ventana normal
        flags = self.main_window.windowFlags()
        flags &= ~Qt.WindowType.FramelessWindowHint
        flags &= ~Qt.WindowType.Tool
        
        if self.main_window.is_always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowType.WindowStaysOnTopHint
            
        self.main_window.setWindowFlags(flags)
        
        # Ajustar tamaño
        self.main_window.resize(500, 400)
        
        # Es necesario volver a mostrar la ventana
        self.main_window.show()
    
    def handle_mouse_press(self, event):
        """Maneja el evento de presionar el botón del mouse para comenzar a arrastrar"""
        if event.button() == Qt.MouseButton.LeftButton and self.draggable:
            self.drag_position = event.position().toPoint()
            event.accept()
    
    def handle_mouse_move(self, event):
        """Maneja el evento de mover el mouse para arrastrar la ventana"""
        if event.buttons() & Qt.MouseButton.LeftButton and self.draggable:
            self.main_window.move(
                self.main_window.pos() + event.position().toPoint() - self.drag_position
            )
            event.accept()
