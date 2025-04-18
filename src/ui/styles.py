# src/ui/styles.py
# Estilos para la aplicación

class Styles:
    """Contiene estilos para la aplicación"""
    
    @staticmethod
    def get_dark_theme():
        """Devuelve estilos para tema oscuro"""
        return """
            QMainWindow, QWidget {
                background-color: #1a1a1a;
                color: white;
            }
            
            QPushButton {
                border: none;
                background: transparent;
                color: white;
                padding: 5px;
            }
            
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.1);
                border-radius: 4px;
            }
            
            QSlider::groove:horizontal {
                height: 8px;
                background: #333;
                border-radius: 4px;
            }
            
            QSlider::handle:horizontal {
                width: 16px;
                margin: -4px 0;
                border-radius: 8px;
                background: #3498db;
            }
            
            QSlider::sub-page:horizontal {
                background: #3498db;
                border-radius: 4px;
            }
        """
    
    @staticmethod
    def get_light_theme():
        """Devuelve estilos para tema claro"""
        return """
            QMainWindow, QWidget {
                background-color: #f0f0f0;
                color: black;
            }
            
            QPushButton {
                border: none;
                background: transparent;
                color: #333;
                padding: 5px;
            }
            
            QPushButton:hover {
                background-color: rgba(0, 0, 0, 0.1);
                border-radius: 4px;
            }
            
            QSlider::groove:horizontal {
                height: 8px;
                background: #ccc;
                border-radius: 4px;
            }
            
            QSlider::handle:horizontal {
                width: 16px;
                margin: -4px 0;
                border-radius: 8px;
                background: #3498db;
            }
            
            QSlider::sub-page:horizontal {
                background: #3498db;
                border-radius: 4px;
            }
        """
