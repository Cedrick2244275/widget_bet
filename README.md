# Sunamu para Windows

Widget de música con detección automática de reproductores y visualización de letras para Windows, inspirado en el proyecto [Sunamu](https://github.com/NyaomiDEV/Sunamu).

## Características

- Detección automática de reproductores de música:
  - Spotify (con API oficial)
  - Reproductores de Windows (usando Windows Media Session)
  - Detección de música en navegadores (YouTube, Spotify Web)
- Muestra información de la canción actual (título, artista, álbum, portada)
- Muestra letras de canciones usando API de Genius
- Controles de reproducción (reproducir/pausar, siguiente, anterior)
- Interfaz personalizable con colores extraídos de la portada del álbum
- Modos de visualización: widget o ventana normal
- Opción "siempre encima" para mantener visible el widget

## Requisitos

- Windows 10 o superior
- Python 3.9 o superior
- Para funcionalidad completa de Spotify: cuenta de desarrollador de Spotify (gratuita)
- Para letras: cuenta de API de Genius (gratuita)

## Instalación

1. Clonar este repositorio:

# Mejoras en el Detector de Música para Windows

## Solución al problema del reinicio constante de detección de canciones

Se han implementado varias mejoras para resolver el problema del reinicio constante de la detección de canciones, lo que causaba que las letras se recargaran continuamente:

### 1. Mejoras en el Detector de Windows Media

- **Caché de detección**: Se implementó un sistema de caché para la última pista detectada, devolviendo esta información si no ha pasado suficiente tiempo desde la última actualización.
- **Intervalo de actualización**: Incrementado de 1-3 segundos a 5 segundos para reducir la frecuencia de escaneo.
- **IDs estables**: Generación de identificadores únicos y estables para cada pista, basados en información consistente.
- **Mecanismo de estabilidad**: Se añadió un contador de estabilidad para evitar cambios rápidos entre pistas.
- **Estimación de posición**: Cálculo automático de la posición de reproducción entre actualizaciones.
- **Estado persistente**: Mantenimiento del estado de reproducción (play/pause) entre actualizaciones.

### 2. Mejoras en la Interfaz de Usuario

- **Lógica de detección de nuevas pistas**: Se mejoró la lógica para identificar cuando una pista es realmente nueva vs. pequeñas variaciones en metadatos.
- **Evitar cargas múltiples**: Implementación para evitar cargas simultáneas de letras para la misma canción.
- **Actualizaciones parciales**: La interfaz ahora solo actualiza la información necesaria (como la posición de reproducción) sin recargar toda la UI.

### 3. Arreglos Adicionales

- **Implementación de is_valid()**: Se añadió el método faltante a la clase MusicInfo.
- **Arrastre de ventana**: Se corrigió el problema con el arrastre de la ventana principal.

## Resultado

Estas mejoras proporcionan una experiencia mucho más estable para el usuario, evitando la carga constante de letras y el reinicio de la detección de música. La aplicación ahora:

1. Detecta las canciones de manera estable sin reinicios constantes
2. Mantiene las letras visibles sin recargas innecesarias
3. Estima correctamente la posición de reproducción
4. Genera IDs consistentes para evitar falsos positivos en cambios de canciones

## Próximas Mejoras Posibles

1. Mejorar el seguimiento de letras sincronizadas
2. Optimizar la detección en reproductores web
3. Implementar más detecciones específicas para reproductores populares