# src/config.py

import os
import json
from pathlib import Path
import logging

class Config:
    """Gestiona la configuración del widget de música"""
    
    def __init__(self):
        # Directorio de configuración
        self.config_dir = Path(os.path.expanduser("~")) / ".config" / "sunamu-windows"
        self.config_file = self.config_dir / "config.json"
        self.cache_dir = self.config_dir / "cache"
        self.lyrics_cache_dir = self.cache_dir / "lyrics"
        
        # Configuración por defecto
        self.default_config = {
            "general": {
                "startup_mode": "widget",  # widget, fullscreen
                "always_on_top": True,
                "check_for_updates": True,
                "minimize_to_tray": True,  # minimizar a la bandeja del sistema en lugar de cerrar
            },
            "appearance": {
                "theme": "dark",  # dark, light, system
                "colors_from_artwork": True,
                "font": "",  # Fuente personalizada (vacío = usar la predeterminada)
                "show_lyrics": True,
            },
            "players": {
                "spotify": {
                    "enabled": True,
                    "client_id": "",
                    "client_secret": ""
                },
                "windows_media": {
                    "enabled": True
                },
                "browsers": {
                    "enabled": True,
                    "detect_youtube": True,
                    "detect_spotify_web": True
                }
            },
            "lyrics": {
                "providers": {
                    "lrclib": {
                        "enabled": True,
                        "priority": 0  # Prioridad más alta (número menor)
                    },
                    "netease": {
                        "enabled": True,
                        "priority": 1
                    },
                    "genius": {
                        "enabled": True,
                        "priority": 2,
                        "api_key": ""
                    }
                },
                "cache_lyrics": True,
                "synchronize_lyrics": True  # Intentar sincronizar letras con la reproducción
            }
        }
        
        # Iniciar la configuración
        self._config = {}
        self._initialize()
    
    def _initialize(self):
        """Inicializa la configuración creando directorios y cargando la configuración"""
        # Crear directorios si no existen
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(exist_ok=True)
        self.lyrics_cache_dir.mkdir(exist_ok=True)
        
        # Cargar configuración existente o crear una nueva
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self._config = json.load(f)
                self._update_missing_keys()
            except Exception as e:
                logging.error(f"Error al cargar la configuración: {e}")
                self._config = dict(self.default_config)
                self.save()
        else:
            self._config = dict(self.default_config)
            self.save()
    
    def _update_missing_keys(self):
        """Actualiza las claves faltantes en la configuración con valores predeterminados"""
        def update_dict(target, source):
            for key, value in source.items():
                if key not in target:
                    target[key] = value
                elif isinstance(value, dict) and isinstance(target[key], dict):
                    update_dict(target[key], value)
        
        update_dict(self._config, self.default_config)
    
    def save(self):
        """Guarda la configuración actual en el archivo"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=4)
        except Exception as e:
            logging.error(f"Error al guardar la configuración: {e}")
    
    def get(self, section, key=None, default=None):
        """Obtiene un valor de configuración específico"""
        if key is None:
            return self._config.get(section, default)
        
        section_data = self._config.get(section, {})
        return section_data.get(key, default)
    
    def set(self, section, key, value):
        """Establece un valor de configuración específico"""
        if section not in self._config:
            self._config[section] = {}
        
        self._config[section][key] = value
        self.save()