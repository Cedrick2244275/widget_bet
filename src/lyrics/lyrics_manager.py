import logging
from typing import List, Optional, Dict, Any
from .lyrics_provider import LyricsProvider, LyricsData

class LyricsManager:
    """Gestiona múltiples proveedores de letras con sistema de prioridad"""
    
    def __init__(self):
        self.providers: List[LyricsProvider] = []
        self.provider_priority: Dict[str, int] = {}
        self.default_priority = 999  # Valor por defecto para proveedores sin prioridad específica
        
        # Caché en memoria para evitar búsquedas repetidas
        self.memory_cache: Dict[str, LyricsData] = {}
    
    def register_provider(self, provider: LyricsProvider, priority: int = None) -> None:
        """
        Registra un proveedor de letras con una prioridad opcional
        Prioridad más baja = mayor preferencia (0 es la máxima prioridad)
        """
        self.providers.append(provider)
        
        if priority is not None:
            self.provider_priority[provider.name] = priority
            
        # Ordenar proveedores por prioridad
        self._sort_providers()
        
        logging.info(f"Proveedor de letras '{provider.name}' registrado con prioridad {priority}")
    
    def _sort_providers(self) -> None:
        """Ordena los proveedores por prioridad"""
        self.providers.sort(
            key=lambda p: self.provider_priority.get(p.name, self.default_priority)
        )
    
    def _get_cache_key(self, title: str, artist: str) -> str:
        """Genera una clave única para la caché"""
        return f"{artist.lower()}_{title.lower()}"
    
    def get_lyrics(self, title: str, artist: str, album: str = "") -> Optional[LyricsData]:
        """
        Busca letras en todos los proveedores registrados según su orden de prioridad
        Devuelve las primeras letras encontradas
        """
        if not title or not artist:
            return None
            
        if not self.providers:
            logging.warning("No hay proveedores de letras registrados")
            return None
        
        # Verificar primero en la caché en memoria
        cache_key = self._get_cache_key(title, artist)
        if cache_key in self.memory_cache:
            cached_lyrics = self.memory_cache[cache_key]
            logging.info(f"Letras encontradas en caché en memoria para: {artist} - {title}")
            return cached_lyrics
        
        # Registrar búsqueda
        logging.info(f"Buscando letras para: {artist} - {title}")
        
        # Intentar con cada proveedor en orden de prioridad
        for provider in self.providers:
            try:
                logging.info(f"Intentando con proveedor: {provider.name}")
                lyrics = provider.get_lyrics(title, artist, album)
                
                if lyrics and lyrics.is_valid():
                    logging.info(f"Letras encontradas en {provider.name}")
                    
                    # Guardar en la caché en memoria
                    self.memory_cache[cache_key] = lyrics
                    
                    return lyrics
                    
            except Exception as e:
                logging.error(f"Error al obtener letras de {provider.name}: {e}")
        
        logging.warning(f"No se encontraron letras para: {artist} - {title} en ningún proveedor")
        return None
    
    def clear_cache(self) -> None:
        """Limpia la caché en memoria"""
        self.memory_cache.clear()
        logging.info("Caché de letras borrada")
    
    def set_provider_priority(self, provider_name: str, priority: int) -> bool:
        """Establece la prioridad de un proveedor específico"""
        for provider in self.providers:
            if provider.name == provider_name:
                self.provider_priority[provider_name] = priority
                self._sort_providers()
                return True
                
        return False
    
    def get_provider_priorities(self) -> Dict[str, int]:
        """Devuelve un diccionario con las prioridades de todos los proveedores"""
        result = {}
        for provider in self.providers:
            result[provider.name] = self.provider_priority.get(provider.name, self.default_priority)
        return result 