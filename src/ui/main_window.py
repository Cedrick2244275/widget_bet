import os
import sys
import logging
import re
from PyQt6.QtWidgets import (QMainWindow, QApplication, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QSlider, QMenu,
                             QSystemTrayIcon, QMessageBox, QStyle, QScrollArea, QSpacerItem, QSizePolicy, QFrame)
from PyQt6.QtGui import QIcon, QPixmap, QAction, QPalette, QColor, QFont
from PyQt6.QtCore import Qt, QTimer, QSize, QUrl, QPoint, QPropertyAnimation, QEasingCurve, QDateTime
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from PIL import Image
from io import BytesIO
from colorthief import ColorThief

from ..player_detection.detector import MusicInfo
from ..lyrics.lyrics_provider import LyricsData, LyricLine
from .widget_mode import WidgetMode
from .styles import Styles

class ImageLoader(QLabel):
    """Widget para cargar imágenes desde URL"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.network_manager = QNetworkAccessManager()
        self.network_manager.finished.connect(self._on_image_loaded)
        self.default_size = QSize(120, 120)
        self.setMinimumSize(self.default_size)
        self.setMaximumSize(self.default_size)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background-color: #333; border-radius: 8px;")
        self.current_url = ""
        self.image_data = None
    
    def load_image_from_url(self, url: str):
        """Carga una imagen desde una URL"""
        if not url or url == self.current_url:
            return
        
        self.current_url = url
        request = QNetworkRequest(QUrl(url))
        self.network_manager.get(request)
    
    def _on_image_loaded(self, reply: QNetworkReply):
        """Maneja la respuesta de la solicitud de imagen"""
        if reply.error() != QNetworkReply.NetworkError.NoError:
            logging.error(f"Error al cargar imagen: {reply.errorString()}")
            return
        
        data = reply.readAll()
        self.image_data = data.data()
        
        pixmap = QPixmap()
        pixmap.loadFromData(data)
        
        # Redimensionar manteniendo la proporción
        scaled_pixmap = pixmap.scaled(
            self.default_size, 
            Qt.AspectRatioMode.KeepAspectRatio, 
            Qt.TransformationMode.SmoothTransformation
        )
        
        self.setPixmap(scaled_pixmap)
    
    def get_dominant_colors(self, count=2):
        """Obtiene los colores dominantes de la imagen cargada"""
        if not self.image_data:
            return None
        
        try:
            img = Image.open(BytesIO(self.image_data))
            color_thief = ColorThief(BytesIO(self.image_data))
            palette = color_thief.get_palette(color_count=count, quality=5)
            return palette
        except Exception as e:
            logging.error(f"Error al obtener colores dominantes: {e}")
            return None

class MainWindow(QMainWindow):
    """Ventana principal del widget de música"""
    
    def __init__(self, config, music_manager, lyrics_manager):
        super().__init__()
        
        self.config = config
        self.music_manager = music_manager
        self.lyrics_manager = lyrics_manager
        
        self.current_track = None
        self.current_lyrics = None
        self.current_track_id = None
        self.lyrics_loaded = False
        self.lyrics_loading = False
        self.is_paused = False  # Variable para controlar mejor el estado de pausa
        self.last_track_info = None  # Variable para almacenar la última información de pista válida
        self.paused_manually = False  # Nueva variable para indicar si la pausa fue manual
        
        # Configurar la ventana completamente transparente
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        
        # Propiedades de la ventana
        self.setWindowTitle("Sunamu")
        self.resize(600, 700)  # Tamaño inicial más adecuado
        
        # Widget central
        self.central_widget = QWidget()
        self.central_widget.setStyleSheet("background-color: transparent;")
        self.setCentralWidget(self.central_widget)
        
        # Layout principal con márgenes reducidos para más espacio
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(0)  # Sin espaciado entre elementos
        
        # Variables para efectos
        self.controls_visible = False
        self.controls_animation_timer = QTimer(self)
        self.controls_animation_timer.timeout.connect(self._update_controls_animation)
        self.controls_opacity = 0.0
        
        # Inicializar el modo widget
        self.widget_mode = WidgetMode(self)
        
        # Inicializar UI
        self._init_ui()
        self._init_systray()
        
        # Temporizadores para actualizar la información
        # Temporizador para actualización de información de la pista (artista, título, etc)
        self.update_track_timer = QTimer(self)
        self.update_track_timer.timeout.connect(self._update_track_info)
        self.update_track_timer.start(2000)  # Actualizar cada 2 segundos
        
        # Temporizador para actualización de progreso (tiempo, barra) - más frecuente
        self.update_progress_timer = QTimer(self)
        self.update_progress_timer.timeout.connect(self._update_progress_info)
        self.update_progress_timer.start(100)  # Actualizar cada 100ms para suavidad visual
        
        # Banderas
        self.is_widget_mode = True  # Siempre en modo widget
        self.is_always_on_top = self.config.get("general", "always_on_top", True)
        
        # Configurar eventos para arrastrar y efectos
        self.mousePressEvent = self._on_mouse_press
        self.mouseMoveEvent = self._on_mouse_move
        self.enterEvent = self._on_mouse_enter
        self.leaveEvent = self._on_mouse_leave
        
        # Ajustar modo
        self._set_widget_mode(self.is_widget_mode)
        self._set_always_on_top(self.is_always_on_top)
        
        # Aplicar temas y estilos
        self._apply_theme()
    
    def _init_ui(self):
        """Inicializa la interfaz de usuario"""
        # Diseño principal completamente transparente
        self.setStyleSheet("background-color: transparent;")
        
        # Área de letras (centro de la pantalla)
        self.lyrics_widget = QWidget()
        self.lyrics_widget.setFixedWidth(600)  # Ancho fijo para las letras
        self.lyrics_widget.setFixedHeight(400)  # Altura fija para las letras
        self.lyrics_widget.setStyleSheet("background-color: transparent;")
        self.lyrics_layout = QVBoxLayout(self.lyrics_widget)
        self.lyrics_layout.setContentsMargins(0, 0, 0, 0)
        self.lyrics_layout.setSpacing(0)
        self.lyrics_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Crear área de desplazamiento para las letras
        self.lyrics_scroll_area = QScrollArea()
        self.lyrics_scroll_area.setWidgetResizable(True)
        self.lyrics_scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.lyrics_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.lyrics_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.lyrics_scroll_area.setStyleSheet("""
            QScrollArea {
                background: transparent; 
                border: none;
            }
            QScrollArea > QWidget > QWidget {
                background: transparent;
            }
            QScrollBar:vertical {
                background: rgba(0, 0, 0, 0.2);
                width: 8px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: rgba(255, 255, 255, 0.3);
                min-height: 20px;
                border-radius: 4px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        
        # Crear contenedor para las letras
        self.lyrics_container = QWidget()
        self.lyrics_container.setStyleSheet("background-color: transparent;")
        self.lyrics_container_layout = QVBoxLayout(self.lyrics_container)
        self.lyrics_container_layout.setContentsMargins(0, 0, 0, 0)
        self.lyrics_container_layout.setSpacing(24)  # Más espacio entre líneas para mejor legibilidad
        self.lyrics_container_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Establecer el contenedor en el área de desplazamiento
        self.lyrics_scroll_area.setWidget(self.lyrics_container)
        
        # Añadir el área de desplazamiento al widget principal
        self.lyrics_layout.addWidget(self.lyrics_scroll_area)
        
        # Temporizador para ocultar la barra de desplazamiento
        self.scrollbar_timer = QTimer(self)
        self.scrollbar_timer.setSingleShot(True)
        self.scrollbar_timer.timeout.connect(self._hide_scrollbar)
        
        # Conectar eventos para mostrar/ocultar la barra de desplazamiento
        self.lyrics_scroll_area.verticalScrollBar().setVisible(False)
        self.lyrics_widget.enterEvent = self._on_lyrics_enter
        self.lyrics_widget.leaveEvent = self._on_lyrics_leave
        
        # Añadir un efecto de difuminado en los bordes superior e inferior
        self.lyrics_widget.setStyleSheet("""
            QWidget {
                background-color: transparent;
            }
        """)
        
        # Barra de título minimalista (solo para arrastrar)
        self.title_bar = QWidget()
        self.title_bar.setStyleSheet("background-color: transparent;")
        self.title_bar.setFixedHeight(30)
        self.title_bar.setCursor(Qt.CursorShape.SizeAllCursor)  # Cursor de mover
        
        self.title_bar_layout = QHBoxLayout(self.title_bar)
        self.title_bar_layout.setContentsMargins(0, 0, 0, 0)
        self.title_bar_layout.setSpacing(5)
        
        # Botones de control para la barra de título
        self.control_buttons_layout = QHBoxLayout()
        self.control_buttons_layout.setSpacing(8)
        
        # Botón de cierre
        self.close_button = QPushButton("✕")
        self.close_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(180, 20, 20, 0.7);
                color: #ffffff;
                font-size: 12px;
                border: none;
                border-radius: 10px;
                padding: 2px;
                min-width: 20px;
                max-width: 20px;
                min-height: 20px;
                max-height: 20px;
            }
            QPushButton:hover {
                background-color: rgba(220, 0, 0, 0.9);
            }
        """)
        self.close_button.setToolTip("Cerrar")
        self.close_button.clicked.connect(self._exit_application)
        
        # Botón para minimizar a la bandeja
        self.tray_button = QPushButton("_")
        self.tray_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(50, 50, 50, 0.7);
                color: #cccccc;
                font-size: 12px;
                border: none;
                border-radius: 10px;
                padding: 2px;
                min-width: 20px;
                max-width: 20px;
                min-height: 20px;
                max-height: 20px;
            }
            QPushButton:hover {
                background-color: rgba(70, 70, 70, 0.9);
            }
        """)
        self.tray_button.setToolTip("Minimizar")
        self.tray_button.clicked.connect(self.hide)
        
        # Añadir botones al layout de controles
        self.control_buttons_layout.addStretch()
        self.control_buttons_layout.addWidget(self.tray_button)
        self.control_buttons_layout.addWidget(self.close_button)
        
        # Añadir elementos a la barra de título
        self.title_bar_layout.addStretch()
        self.title_bar_layout.addLayout(self.control_buttons_layout)
        
        # Hacer botones transparentes inicialmente
        self.close_button.setStyleSheet(self.close_button.styleSheet() + "background-color: rgba(180, 20, 20, 0.0);")
        self.tray_button.setStyleSheet(self.tray_button.styleSheet() + "background-color: rgba(50, 50, 50, 0.0);")
        
        # Panel de control y reproducción (parte inferior)
        self.player_widget = QWidget()
        self.player_widget.setStyleSheet("background-color: transparent;")
        self.player_layout = QVBoxLayout(self.player_widget)
        self.player_layout.setContentsMargins(0, 10, 0, 0)
        self.player_layout.setSpacing(10)
        
        # Info de la canción (minimizada)
        self.song_info_widget = QWidget()
        self.song_info_widget.setStyleSheet("background-color: transparent;")
        self.song_info_layout = QHBoxLayout(self.song_info_widget)
        self.song_info_layout.setContentsMargins(10, 5, 10, 5)
        self.song_info_layout.setSpacing(10)
        
        # Portada del álbum (pequeña)
        self.album_art = ImageLoader(self)
        self.album_art.setMinimumSize(QSize(60, 60))
        self.album_art.setMaximumSize(QSize(60, 60))
        self.album_art.setStyleSheet("background-color: transparent; border-radius: 5px;")
        
        # Información de texto
        self.text_info_layout = QVBoxLayout()
        self.text_info_layout.setContentsMargins(0, 0, 0, 0)
        self.text_info_layout.setSpacing(2)
        
        # Título de la canción
        self.title_label = QLabel("No hay música reproduciéndose")
        self.title_label.setWordWrap(True)
        self.title_label.setStyleSheet("color: white; font-size: 14px; font-weight: bold; background-color: transparent;")
        
        # Artista
        self.artist_label = QLabel("")
        self.artist_label.setWordWrap(True)
        self.artist_label.setStyleSheet("color: #ddd; font-size: 12px; background-color: transparent;")
        
        # Álbum (opcional)
        self.album_label = QLabel("")
        self.album_label.setWordWrap(True)
        self.album_label.setStyleSheet("color: #bbb; font-size: 10px; background-color: transparent;")
        
        # Añadir información de texto
        self.text_info_layout.addWidget(self.title_label)
        self.text_info_layout.addWidget(self.artist_label)
        self.text_info_layout.addWidget(self.album_label)
        
        # Añadir al layout de información de canción
        self.song_info_layout.addWidget(self.album_art)
        self.song_info_layout.addLayout(self.text_info_layout)
        self.song_info_layout.addStretch()
        
        # Slider de progreso (minimalista)
        self.progress_layout = QHBoxLayout()
        self.progress_layout.setContentsMargins(10, 0, 10, 0)
        self.progress_layout.setSpacing(10)
        
        # Tiempo actual
        self.time_current_label = QLabel("0:00")
        self.time_current_label.setStyleSheet("color: #fff; font-size: 10px; background-color: transparent;")
        
        # Slider
        self.progress_slider = QSlider(Qt.Orientation.Horizontal)
        self.progress_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 3px;
                background: rgba(255, 255, 255, 0.2);
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                width: 8px;
                margin: -3px 0;
                border-radius: 4px;
                background: white;
            }
            QSlider::sub-page:horizontal {
                background: white;
                border-radius: 2px;
            }
        """)
        self.progress_slider.sliderMoved.connect(self._on_slider_moved)
        self.progress_slider.sliderReleased.connect(self._on_slider_released)
        
        # Tiempo total
        self.time_total_label = QLabel("0:00")
        self.time_total_label.setStyleSheet("color: #fff; font-size: 10px; background-color: transparent;")
        
        # Añadir al layout de progreso
        self.progress_layout.addWidget(self.time_current_label)
        self.progress_layout.addWidget(self.progress_slider)
        self.progress_layout.addWidget(self.time_total_label)
        
        # Contenedor para controles de reproducción (inicialmente transparente)
        self.controls_container = QWidget()
        self.controls_container.setStyleSheet("background-color: transparent;")
        
        # Controles de reproducción
        self.controls_layout = QHBoxLayout(self.controls_container)
        self.controls_layout.setContentsMargins(0, 0, 0, 0)
        self.controls_layout.setSpacing(15)
        
        # Estilo común para los botones de control
        button_style = """
            QPushButton {
                font-size: 16px; 
                color: white; 
                background-color: rgba(0, 0, 0, 0.3);
                border-radius: 12px;
                min-width: 25px;
                max-width: 25px;
                min-height: 25px;
                max-height: 25px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.2);
            }
        """
        
        self.shuffle_button = QPushButton("🔀")
        self.shuffle_button.setStyleSheet(button_style)
        self.shuffle_button.clicked.connect(self._on_shuffle_clicked)
        
        self.prev_button = QPushButton("⏮")
        self.prev_button.setStyleSheet(button_style)
        self.prev_button.clicked.connect(self._on_prev_clicked)
        
        self.play_pause_button = QPushButton("▶")
        self.play_pause_button.setStyleSheet(button_style)
        self.play_pause_button.clicked.connect(self._on_play_pause_clicked)
        
        self.next_button = QPushButton("⏭")
        self.next_button.setStyleSheet(button_style)
        self.next_button.clicked.connect(self._on_next_clicked)
        
        self.repeat_button = QPushButton("🔁")
        self.repeat_button.setStyleSheet(button_style)
        self.repeat_button.clicked.connect(self._on_repeat_clicked)
        
        # Añadir botones al layout
        self.controls_layout.addStretch()
        self.controls_layout.addWidget(self.shuffle_button)
        self.controls_layout.addWidget(self.prev_button)
        self.controls_layout.addWidget(self.play_pause_button)
        self.controls_layout.addWidget(self.next_button)
        self.controls_layout.addWidget(self.repeat_button)
        self.controls_layout.addStretch()
        
        # Los controles inicialmente estarán ocultos
        self.controls_container.setStyleSheet("background-color: transparent; opacity: 0;")
        
        # Añadir todo al layout del reproductor
        self.player_layout.addWidget(self.song_info_widget)
        self.player_layout.addLayout(self.progress_layout)
        self.player_layout.addWidget(self.controls_container)
        
        # Layout principal
        self.main_layout.addWidget(self.title_bar, 0, Qt.AlignmentFlag.AlignTop)  # Arriba
        self.main_layout.addStretch(1)  # Espacio flexible
        self.main_layout.addWidget(self.lyrics_widget, 0, Qt.AlignmentFlag.AlignCenter)  # Letras en el centro
        self.main_layout.addStretch(1)  # Espacio flexible
        self.main_layout.addWidget(self.player_widget, 0, Qt.AlignmentFlag.AlignBottom)  # Reproductor abajo
        
        # Menú contextual
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
    
    def _update_track_info(self):
        """Actualiza la información de la pista en reproducción (no el progreso)"""
        try:
            # Si estamos en pausa manual, simplemente mantener la información actual
            if self.paused_manually and (self.current_track or self.last_track_info):
                logging.debug("Pausa manual activa, manteniendo información actual")
                
                # Para mayor seguridad, establecer el track actual si solo tenemos el último
                if self.last_track_info and not self.current_track:
                    self.current_track = self.last_track_info
                    self.current_track.is_playing = False
                    logging.debug(f"Restaurando información de track desde last_track_info: {self.last_track_info.title}")
                
                return
                
            # Obtener la información de la pista actual
            track_info = self.music_manager.update()
            
            # Si no hay pista detectada, pero tenemos información guardada
            if not track_info:
                # Verificar si fue pausada manualmente y no hemos detectado aún
                if not self.paused_manually and (self.current_track or self.last_track_info):
                    logging.info("Detectada posible pausa automática, activando modo pausa manual")
                    self.paused_manually = True
                    self.is_paused = True
                    
                    # Si no tenemos información guardada pero sí track actual
                    if not self.last_track_info and self.current_track:
                        # Guardar una copia completa del track actual
                        track_copy = MusicInfo(
                            title=self.current_track.title,
                            artist=self.current_track.artist,
                            album=self.current_track.album,
                            album_art_url=self.current_track.album_art_url,
                            duration_ms=self.current_track.duration_ms,
                            position_ms=self.current_track.position_ms,
                            is_playing=False,
                            player_name=self.current_track.player_name,
                            track_id=self.current_track.track_id
                        )
                        self.last_track_info = track_copy
                        logging.info(f"Se guardó información de pista pausada automáticamente: {self.last_track_info.title}")
                    
                    if self.current_track:
                        self.current_track.is_playing = False
                        self.play_pause_button.setText("▶")
                    
                    return
                
                # Si tenemos información previa guardada, considerar que está pausada
                if self.last_track_info is not None:
                    # Solo actualizar el estado de pausa si estaba reproduciendo
                    if not self.is_paused:
                        logging.debug("Canción pausada detectada, manteniendo información")
                        self.is_paused = True
                        if self.current_track:
                            self.current_track.is_playing = False
                        self.play_pause_button.setText("▶")
                    return
                elif hasattr(self, 'current_track') and self.current_track:
                    # Mantener la información actual, pero marcar como pausada
                    if not self.is_paused:
                        logging.debug("Canción pausada detectada, manteniendo información del track actual")
                        self.is_paused = True
                        self.current_track.is_playing = False
                        self.play_pause_button.setText("▶")
                    return
                else:
                    # No hay información previa ni actual, limpiar la interfaz
                    self._clear_track_info(force=True)
                    return
            
            # Tenemos información de pista, verificar si es la misma o una nueva
            current_id = track_info.get_unique_id()
            
            # Si es la primera detección, establecer el ID actual
            if not hasattr(self, 'current_track_id') or self.current_track_id is None:
                self.current_track_id = current_id
                is_new_track = True
                self.is_paused = not track_info.is_playing
                self.paused_manually = False
            else:
                # Determinar si es una pista nueva comparando los IDs
                is_new_track = (self.current_track_id != current_id)
                
                if is_new_track:
                    self.is_paused = not track_info.is_playing
                    self.paused_manually = False
            
            # Detectar cambio de estado de pausa a reproducción
            was_paused = self.is_paused
            self.is_paused = not track_info.is_playing
            resume_playing = was_paused and not self.is_paused and not is_new_track
            
            # Actualizar botón de reproducción/pausa
            self.play_pause_button.setText("⏸" if track_info.is_playing else "▶")
            
            # Establecer los límites del slider y duración total si es una pista nueva
            if is_new_track and track_info.duration_ms > 0:
                self.progress_slider.setMaximum(track_info.duration_ms)
                self.time_total_label.setText(self._format_time(track_info.duration_ms))
            elif track_info.duration_ms <= 0:
                self.progress_slider.setMaximum(100)
                self.time_total_label.setText("0:00")
            
            # Inicializar o actualizar la posición para el sistema de estimación
            self.last_position_ms = track_info.position_ms
            self.last_position_update = QDateTime.currentMSecsSinceEpoch()
            
            # Solo actualizar etiquetas si es una pista nueva
            if is_new_track:
                logging.info(f"Nueva pista detectada: {track_info.artist} - {track_info.title} (ID: {current_id})")
                
                # Actualizar el ID de la pista actual
                self.current_track_id = current_id
                self.current_track = track_info
                
                # Resetear estado de pausa manual
                self.paused_manually = False
                
                # Actualizar información de la pista
                if track_info.title:
                    self.title_label.setText(track_info.title)
                    # Iniciar animación del título si es necesario
                    self._setup_title_scrolling()
                else:
                    self.title_label.setText("Desconocido")
                    
                if track_info.artist:
                    self.artist_label.setText(track_info.artist)
                else:
                    self.artist_label.setText("Artista desconocido")
                
                # Cargar imagen del álbum si está disponible
                if track_info.album_art_url:
                    self.album_art.load_image_from_url(track_info.album_art_url)
                else:
                    # Sin imagen de álbum, usar imagen predeterminada
                    self._set_default_album_art()
                
                # Cargar letras si están habilitadas
                if self.config.get("lyrics", "show_lyrics", True):
                    # Limpiar letras antiguas y cargar las nuevas
                    self._clear_lyrics()
                    self._load_lyrics(track_info.title, track_info.artist)
                    
                # Actualizar colores si está configurado
                if self.config.get("appearance", "colors_from_artwork", True):
                    self._update_colors_from_artwork()
            else:
                # Simplemente actualizar el estado de la pista sin recargar todo
                # Pero preservar el estado de reproducción actual
                previous_state = self.current_track
                self.current_track = track_info
                
            # Actualizar la última información de pista válida
            self.last_track_info = track_info
                    
        except Exception as e:
            logging.error(f"Error al actualizar la información de la pista: {str(e)}", exc_info=True)
            # Intentar limpiar la interfaz en caso de error
            self._clear_track_info()
    
    def _clear_track_info(self, force=False):
        """Limpia la información de la pista actual
        
        Args:
            force: Si es True, limpia la información aunque esté pausada
        """
        # Si estamos pausados y tenemos información válida, no limpiar a menos que se fuerce
        if not force and self.is_paused and (self.current_track or self.last_track_info):
            return
            
        self.current_track = None
        self.last_track_info = None
        self.title_label.setText("No hay música reproduciéndose")
        self.artist_label.setText("")
        self.album_label.setText("")
        self.play_pause_button.setText("▶")
        self.progress_slider.setValue(0)
        self.time_current_label.setText("0:00")
        self.time_total_label.setText("0:00")
        self._clear_lyrics()
    
    def _load_lyrics(self, track_name=None, artist_name=None):
        """Carga y muestra las letras para la canción actual"""
        try:
            # Obtener información de la pista actual si no se proporciona
            if not track_name or not artist_name:
                if self.current_track:
                    track_name = self.current_track.title
                    artist_name = self.current_track.artist
                elif hasattr(self, 'current_track_info') and self.current_track_info:
                    track_name = self.current_track_info.get('title', '')
                    artist_name = self.current_track_info.get('artist', '')
            
            # Si no hay información de pista, salir
            if not track_name or not artist_name:
                logging.info("No hay información de pista para cargar letras")
                return
            
            # Verificar si ya tenemos letras cargadas para esta canción
            current_song_key = f"{artist_name}:{track_name}".lower()
            if hasattr(self, 'current_lyrics_song_key') and self.current_lyrics_song_key == current_song_key and self.lyrics_loaded:
                logging.info(f"Ya hay letras cargadas para {track_name} - {artist_name}")
                # Actualizar la línea actual si hay letras sincronizadas
                if hasattr(self, 'current_lyrics') and self.current_lyrics and hasattr(self, 'lyrics_widgets'):
                    QTimer.singleShot(100, lambda: self._update_current_lyrics_line(
                        self.current_track.position_ms if self.current_track else 0))
                return
            
            # Evitar múltiples cargas simultáneas de letras
            if self.lyrics_loading:
                logging.info("Ya hay una carga de letras en proceso, cancelando la actual")
                # Reiniciar la bandera de carga para permitir nuevos intentos
                self.lyrics_loading = False
            
            logging.info(f"Cargando letras para {track_name} - {artist_name}")
            
            # Limpiar las letras anteriores
            self._clear_lyrics()
            
            self.lyrics_loading = True
            self.current_lyrics_song_key = current_song_key
            
            # Mostrar un indicador de carga
            loading_label = QLabel("Cargando letras...")
            loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            loading_label.setStyleSheet("""
                color: rgba(255, 255, 255, 0.7);
                font-size: 18px;
                font-style: italic;
                background: transparent;
                padding: 20px;
            """)
            self.lyrics_container_layout.addWidget(loading_label)
            QApplication.processEvents()  # Actualizar la interfaz inmediatamente
            
            # Obtener las letras usando el LyricsManager
            lyrics_data = None
            if hasattr(self, 'lyrics_manager') and self.lyrics_manager:
                lyrics_data = self.lyrics_manager.get_lyrics(track_name, artist_name)
            
            # Limpiar el indicador de carga
            self._clear_lyrics()
            
            # Extraer el texto de las letras
            lyrics_text = lyrics_data.lyrics_text if lyrics_data else None
            has_synced_lyrics = lyrics_data.has_synced_lyrics if lyrics_data else False
            
            # Si no hay letras, mostrar un mensaje
            if not lyrics_text:
                # Crear un mensaje de "No se encontraron letras" centrado y con estilo
                no_lyrics_label = QLabel("No se encontraron letras para esta canción")
                no_lyrics_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                no_lyrics_label.setStyleSheet("""
                    color: rgba(255, 255, 255, 0.7);
                    font-size: 18px;
                    font-style: italic;
                    text-shadow: 1px 1px 5px rgba(0, 0, 0, 0.7);
                    background: transparent;
                    padding: 20px;
                """)
                self.lyrics_container_layout.addWidget(no_lyrics_label)
                self.lyrics_widget.setVisible(True)
                self.lyrics_loading = False
                return
            
            # Añadir información del proveedor de letras en la parte superior
            if lyrics_data and hasattr(lyrics_data, 'source') and lyrics_data.source:
                source_label = QLabel(f"Proveedor: {lyrics_data.source}")
                source_label.setAlignment(Qt.AlignmentFlag.AlignRight)
                source_label.setStyleSheet("""
                    color: rgba(255, 255, 255, 0.5);
                    font-size: 12px;
                    font-style: italic;
                    background: transparent;
                    padding: 4px 8px;
                """)
                self.lyrics_container_layout.addWidget(source_label)
            
            # Preparar las letras sincronizadas o normales
            self.lyrics_widgets = []
            self.lyrics_times = []
            
            if has_synced_lyrics and lyrics_data.lines:
                self.current_lyrics = lyrics_data.lines
                
                # Crear un widget para cada línea de letras
                for i, lyric_line in enumerate(lyrics_data.lines):
                    line_widget = QLabel(lyric_line.text if lyric_line.text else " ")
                    line_widget.setWordWrap(True)  # Permitir envolver el texto
                    line_widget.setFixedWidth(580)  # Ancho fijo para evitar desplazamiento horizontal
                    line_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    line_widget.setStyleSheet("""
                        color: rgba(255, 255, 255, 0.4);
                        font-size: 16px;
                        background: transparent;
                        padding: 4px 10px;
                    """)
                    
                    self.lyrics_container_layout.addWidget(line_widget)
                    self.lyrics_widgets.append(line_widget)
                    self.lyrics_times.append(lyric_line.start_time_ms)
                    
                    # Actualizar la interfaz de forma intermitente para mayor fluidez
                    if i % 10 == 0:
                        QApplication.processEvents()
            else:
                # Letras no sincronizadas - mostrar como texto normal
                self.current_lyrics = None
                
                # Si el texto de letras es una cadena, dividirlo en líneas
                if isinstance(lyrics_text, str):
                    lyrics_lines = lyrics_text.split('\n')
                else:
                    lyrics_lines = lyrics_text
                
                # Crear un widget para cada línea de letras
                for i, line in enumerate(lyrics_lines):
                    if not line.strip():  # Mantener líneas vacías para espaciado
                        line = " "
                        
                    line_widget = QLabel(line)
                    line_widget.setWordWrap(True)  # Permitir envolver el texto
                    line_widget.setFixedWidth(580)  # Ancho fijo para evitar desplazamiento horizontal
                    line_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    line_widget.setStyleSheet("""
                        color: rgba(255, 255, 255, 0.7);
                        font-size: 16px;
                        background: transparent;
                        padding: 4px 10px;
                    """)
                    
                    self.lyrics_container_layout.addWidget(line_widget)
                    self.lyrics_widgets.append(line_widget)
                    self.lyrics_times.append(0)  # No hay tiempo para letras no sincronizadas
                    
                    # Actualizar la interfaz de forma intermitente para mayor fluidez
                    if i % 10 == 0:
                        QApplication.processEvents()
                
                # Seleccionar la primera línea como actual para letras no sincronizadas
                if self.lyrics_widgets:
                    self.lyrics_widgets[0].setStyleSheet("""
                        color: rgba(255, 255, 255, 1.0);
                        font-size: 18px;
                        font-weight: bold;
                        background: transparent;
                        padding: 4px 10px;
                    """)
                
                self.current_line_index = 0
            
            # Añadir un espacio al final para permitir desplazamiento completo
            spacer = QWidget()
            spacer.setMinimumHeight(150)
            spacer.setStyleSheet("background: transparent;")
            self.lyrics_container_layout.addWidget(spacer)
            
            self.lyrics_loaded = True
            
            # Configurar para que se actualice la línea actual
            self.current_line_index = -1  # Inicializar para forzar la primera actualización
            QTimer.singleShot(200, lambda: self._update_current_lyrics_line(
                self.current_track.position_ms if self.current_track else 0))
            
            self.lyrics_loading = False
        
        except Exception as e:
            logging.error(f"Error al cargar letras: {str(e)}", exc_info=True)
            self.lyrics_loading = False
    
    def _clear_lyrics(self):
        """Limpia el área de letras"""
        try:
            # Asegurarse de que exista el contenedor de letras
            if not hasattr(self, 'lyrics_container') or not self.lyrics_container:
                return
            
            # Cancelar cualquier carga en proceso
            self.lyrics_loading = False
            
            # Eliminar todos los widgets del contenedor
            while self.lyrics_container_layout.count():
                item = self.lyrics_container_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            
            # Reiniciar datos
            self.current_lyrics = None
            self.lyrics_loaded = False
            self.lyrics_widgets = []
            self.lyrics_times = []
            
            # Reiniciar índice de línea actual y clave de canción
            if hasattr(self, 'current_line_index'):
                delattr(self, 'current_line_index')
            if hasattr(self, 'current_lyrics_song_key'):
                delattr(self, 'current_lyrics_song_key')
            
        except Exception as e:
            logging.error(f"Error al limpiar letras: {str(e)}", exc_info=True)
    
    def _update_current_lyrics_line(self, position_ms):
        """Actualiza la visualización de letras resaltando la línea actual según el tiempo de reproducción"""
        try:
            # Verificar que tengamos las letras cargadas y los widgets creados
            if not self.current_lyrics or not hasattr(self, 'lyrics_widgets') or not self.lyrics_widgets:
                return
            
            # Verificar que tengamos acceso al controlador del reproductor
            if not self.current_track:
                return
            
            # Obtener la posición actual de reproducción en milisegundos
            current_pos_ms = position_ms
            if current_pos_ms is None or current_pos_ms < 0:
                return
            
            # Ajustar la posición para reducir la latencia (150ms adelantados)
            adjusted_pos_ms = current_pos_ms + 150
            
            # Encuentra la línea actual y también pre-carga la siguiente línea
            new_line_index = -1
            next_line_index = -1
            
            # Si tenemos tiempos de línea sincronizados
            if hasattr(self, 'lyrics_times') and self.lyrics_times:
                # Encontrar la línea correspondiente al tiempo actual y la siguiente
                for i, time_ms in enumerate(self.lyrics_times):
                    if time_ms <= 0:
                        continue
                        
                    if time_ms > adjusted_pos_ms:
                        if i > 0:
                            new_line_index = i - 1
                            next_line_index = i
                        elif i == 0:
                            new_line_index = 0
                            next_line_index = min(1, len(self.lyrics_times) - 1)
                        break
                
                # Si llegamos al final sin encontrar, usar la última línea
                if new_line_index == -1 and self.lyrics_widgets:
                    # Encontrar la última línea con tiempo válido
                    for i in range(len(self.lyrics_times) - 1, -1, -1):
                        if self.lyrics_times[i] > 0:
                            new_line_index = i
                            next_line_index = i
                            break
            
            # Si no se encontró una línea con tiempo, usar la primera
            if new_line_index == -1 and self.lyrics_widgets:
                new_line_index = 0
                next_line_index = min(1, len(self.lyrics_widgets) - 1)
                
            # Si la línea actual ha cambiado o no se ha configurado aún
            if new_line_index != getattr(self, 'current_line_index', -999):
                self.current_line_index = new_line_index
                
                # Aplicar estilos a todas las líneas basados en la distancia a la línea actual
                max_distance = 5  # Número de líneas visibles antes de volverse completamente transparentes
                
                for i, widget in enumerate(self.lyrics_widgets):
                    # Calcular la distancia a la línea actual
                    distance = abs(i - new_line_index)
                    
                    # Preparar la línea siguiente para que esté más visible (pre-carga visual)
                    if i == next_line_index and i != new_line_index:
                        distance = max(0.5, distance - 0.5)  # Reducir la distancia para la siguiente línea
                    
                    if distance == 0:
                        # Línea actual - resaltada y más grande
                        widget.setStyleSheet("""
                            color: rgba(255, 255, 255, 1.0);
                            font-size: 24px;
                            font-weight: bold;
                            background: transparent;
                            padding: 6px 10px;
                        """)
                    else:
                        # Calcular opacidad basada en la distancia (1.0 para línea actual, 0.2 para líneas lejanas)
                        opacity = max(0.2, 1.0 - (distance / max_distance) * 0.8)
                        # Calcular tamaño de fuente basado en la distancia (24px para actual, 16px para lejanas)
                        font_size = max(16, 24 - distance * 2)
                        
                        # La línea siguiente tiene un estilo ligeramente más destacado
                        if i == next_line_index:
                            opacity = min(0.9, opacity + 0.1)
                            font_size = min(22, font_size + 2)
                        
                        widget.setStyleSheet(f"""
                            color: rgba(255, 255, 255, {opacity:.1f});
                            font-size: {font_size}px;
                            background: transparent;
                            padding: 4px 10px;
                        """)
                
                # Desplazar automáticamente para mostrar la línea actual en el centro
                if self.lyrics_widgets and new_line_index >= 0:
                    # Obtener el widget de la línea actual
                    current_widget = self.lyrics_widgets[new_line_index]
                    
                    # Calcular la posición para centrar la línea actual
                    scroll_area = self.lyrics_scroll_area
                    viewport_height = scroll_area.viewport().height()
                    widget_pos = current_widget.mapTo(scroll_area.widget(), QPoint(0, 0))
                    widget_height = current_widget.height()
                    
                    # Calcular la posición de desplazamiento ideal para centrar
                    target_scroll_pos = max(0, widget_pos.y() - (viewport_height // 2) + (widget_height // 2))
                    
                    # Crear una animación para desplazar suavemente a la posición
                    if not hasattr(self, 'scroll_animation'):
                        self.scroll_animation = QPropertyAnimation(scroll_area.verticalScrollBar(), b"value")
                        self.scroll_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
                        self.scroll_animation.setDuration(250)  # Duración reducida para menor latencia
                    
                    # Configurar y comenzar la animación
                    self.scroll_animation.stop()
                    self.scroll_animation.setStartValue(scroll_area.verticalScrollBar().value())
                    self.scroll_animation.setEndValue(target_scroll_pos)
                    self.scroll_animation.start()
            
            # Ya no necesitamos programar una próxima actualización aquí,
            # ya que el temporizador de progreso se encarga de llamar a este método
            
        except Exception as e:
            logging.debug(f"Error al actualizar línea de letras: {e}")
            # No es crítico, solo registramos en debug
    
    def _update_colors_from_artwork(self):
        """Actualiza los colores de la interfaz basados en la portada del álbum"""
        colors = self.album_art.get_dominant_colors(count=2)
        if not colors:
            return
            
        # Obtener los colores principales
        primary_color = colors[0]
        secondary_color = colors[1]
        
        # Convertir a texto de color
        primary_color_str = f"rgb({primary_color[0]}, {primary_color[1]}, {primary_color[2]})"
        secondary_color_str = f"rgb({secondary_color[0]}, {secondary_color[1]}, {secondary_color[2]})"
        
        # Actualizar estilo del slider
        self.progress_slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                height: 8px;
                background: #333;
                border-radius: 4px;
            }}
            QSlider::handle:horizontal {{
                width: 16px;
                margin: -4px 0;
                border-radius: 8px;
                background: {primary_color_str};
            }}
            QSlider::sub-page:horizontal {{
                background: {primary_color_str};
                border-radius: 4px;
            }}
        """)
        
        # Actualizar estilo de los botones
        for button in [self.prev_button, self.play_pause_button, self.next_button]:
            button.setStyleSheet(f"font-size: 24px; color: {primary_color_str}; background: transparent;")
    
    def _on_slider_moved(self, position):
        """Evento al mover el slider"""
        self.time_current_label.setText(self._format_time(position))
    
    def _on_slider_released(self):
        """Evento al soltar el slider"""
        if self.current_track:
            position = self.progress_slider.value()
            self.music_manager.seek(position)
    
    def _on_play_pause_clicked(self):
        """Evento al hacer clic en el botón de reproducción/pausa"""
        track_to_use = self.current_track or self.last_track_info
        if not track_to_use:
            logging.debug("No hay información de pista para pausar/reproducir")
            return
            
        if not self.is_paused:  # Si está reproduciendo, pausar
            logging.info(f"Pausando manualmente: {track_to_use.title} - {track_to_use.artist}")
            self.music_manager.pause()
            self.play_pause_button.setText("▶")
            if self.current_track:
                self.current_track.is_playing = False
            self.is_paused = True
            self.paused_manually = True  # Marca que la pausa fue manual
            
            # IMPORTANTE: Crear una copia del track actual antes de la pausa
            if self.current_track:
                # Guardar una copia completa como último track
                track_copy = MusicInfo(
                    title=self.current_track.title,
                    artist=self.current_track.artist,
                    album=self.current_track.album,
                    album_art_url=self.current_track.album_art_url,
                    duration_ms=self.current_track.duration_ms,
                    position_ms=self.current_track.position_ms,
                    is_playing=False,  # Marcamos como pausado
                    player_name=self.current_track.player_name,
                    track_id=self.current_track.track_id
                )
                self.last_track_info = track_copy
                logging.info(f"Se guardó información de pista pausada manualmente: {self.last_track_info.title}")
        else:  # Si está pausado, reanudar
            logging.info(f"Reanudando reproducción manual: {track_to_use.title} - {track_to_use.artist}")
            # Si fue pausado manualmente, usamos la información guardada
            if self.paused_manually and self.last_track_info:
                # Restaurar la información guardada
                self.current_track = self.last_track_info
                self.current_track.is_playing = True
                logging.info(f"Restaurando track pausado manualmente: {self.current_track.title}")
                
            self.music_manager.play()
            self.play_pause_button.setText("⏸")
            self.is_paused = False
            self.paused_manually = False
            
            # Si tenemos información guardada pero no track actual, restaurar
            if not self.current_track and self.last_track_info:
                self.current_track = self.last_track_info
                self.current_track.is_playing = True
            elif self.current_track:
                self.current_track.is_playing = True
            
            # Actualizar la última posición conocida para evitar saltos en la visualización
            if hasattr(self, 'last_position_ms'):
                self.last_position_update = QDateTime.currentMSecsSinceEpoch()
            
            # Actualizar la línea actual de las letras inmediatamente cuando se reanuda la reproducción
            if hasattr(self, 'current_lyrics') and self.current_lyrics and hasattr(self, 'lyrics_widgets'):
                self._update_current_lyrics_line(track_to_use.position_ms)
                
            # Forzar una actualización inmediata del progreso
            self._update_progress_info()
    
    def _on_prev_clicked(self):
        """Evento al hacer clic en el botón anterior"""
        self.music_manager.previous_track()
    
    def _on_next_clicked(self):
        """Evento al hacer clic en el botón siguiente"""
        self.music_manager.next_track()
    
    def _on_shuffle_clicked(self):
        """Evento al hacer clic en el botón de reproducción aleatoria"""
        # Aquí iría la lógica para activar/desactivar la reproducción aleatoria
        pass
    
    def _on_repeat_clicked(self):
        """Evento al hacer clic en el botón de repetición"""
        # Aquí iría la lógica para activar/desactivar la repetición
        pass
    
    def _show_context_menu(self, pos: QPoint):
        """Muestra el menú contextual"""
        menu = QMenu(self)
        
        # Mostrar/Ocultar
        action_hide = QAction("Ocultar widget", self)
        action_hide.triggered.connect(self.hide)
        menu.addAction(action_hide)
        
        # Modo
        if self.is_widget_mode:
            action_mode = QAction("Modo pantalla completa", self)
        else:
            action_mode = QAction("Modo widget", self)
        action_mode.triggered.connect(self._toggle_widget_mode)
        menu.addAction(action_mode)
        
        # Siempre encima
        action_top = QAction("Siempre visible", self)
        action_top.setCheckable(True)
        action_top.setChecked(self.config.get("general", "always_on_top", False))
        action_top.triggered.connect(self._toggle_always_on_top)
        menu.addAction(action_top)
        
        # Mostrar letras
        action_lyrics = QAction("Mostrar letras", self)
        action_lyrics.setCheckable(True)
        action_lyrics.setChecked(self.lyrics_widget.isVisible())
        action_lyrics.triggered.connect(self._toggle_lyrics)
        menu.addAction(action_lyrics)
        
        # Minimizar a bandeja
        action_minimize_to_tray = QAction("Minimizar a bandeja al cerrar", self)
        action_minimize_to_tray.setCheckable(True)
        action_minimize_to_tray.setChecked(self.config.get("general", "minimize_to_tray", True))
        action_minimize_to_tray.triggered.connect(self._toggle_minimize_to_tray)
        menu.addAction(action_minimize_to_tray)
        
        menu.addSeparator()
        
        # Salir (ocultar)
        action_hide = QAction("Ocultar", self)
        action_hide.triggered.connect(self.hide)
        menu.addAction(action_hide)
        
        # Salir (completamente)
        action_exit = QAction("Salir completamente", self)
        action_exit.triggered.connect(self._exit_application)
        menu.addAction(action_exit)
        
        menu.exec(self.mapToGlobal(pos))
    
    def _toggle_widget_mode(self):
        """Alterna entre modo widget y modo pantalla completa"""
        self.is_widget_mode = not self.is_widget_mode
        self._set_widget_mode(self.is_widget_mode)
        
        # Guardar preferencia
        self.config.set("general", "startup_mode", "widget" if self.is_widget_mode else "fullscreen")
    
    def _toggle_always_on_top(self, checked: bool):
        """Alterna la opción de siempre encima"""
        self.is_always_on_top = checked
        self._set_always_on_top(checked)
        
        # Guardar preferencia
        self.config.set("general", "always_on_top", checked)
    
    def _set_always_on_top(self, enabled: bool):
        """Establece si la ventana está siempre encima"""
        flags = self.windowFlags()
        if enabled:
            self.setWindowFlags(flags | Qt.WindowType.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(flags & ~Qt.WindowType.WindowStaysOnTopHint)
            
        # Es necesario volver a mostrar la ventana
        self.show()
    
    def _toggle_lyrics(self, checked: bool):
        """Alterna la visibilidad de las letras"""
        self.lyrics_widget.setVisible(checked)
        
        # Guardar preferencia
        self.config.set("appearance", "show_lyrics", checked)
    
    def _apply_theme(self):
        """Aplica el tema seleccionado"""
        theme = self.config.get("appearance", "theme", "dark")
        
        if theme == "dark":
            # Tema oscuro
            self.setStyleSheet(Styles.get_dark_theme())
        elif theme == "light":
            # Tema claro
            self.setStyleSheet(Styles.get_light_theme())
        else:
            # Tema del sistema
            pass
    
    def _format_time(self, ms: int) -> str:
        """Formatea el tiempo en milisegundos a formato MM:SS"""
        total_seconds = int(ms / 1000)
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes}:{seconds:02d}"
    
    def _on_mouse_press(self, event):
        """Maneja el evento de clic del ratón para arrastrar la ventana"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.position().toPoint()
    
    def _on_mouse_move(self, event):
        """Maneja el evento de movimiento del ratón para arrastrar la ventana"""
        if hasattr(self, '_drag_pos') and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(self.pos() + event.position().toPoint() - self._drag_pos)
    
    def _on_mouse_enter(self, event):
        """Evento cuando el mouse entra en el widget"""
        # Mostrar los controles
        self.controls_visible = True
        self.controls_animation_timer.start(50)  # Iniciar animación
        
        # Mostrar botones de la barra de título
        self.close_button.setStyleSheet(self.close_button.styleSheet().replace("rgba(180, 20, 20, 0.0)", "rgba(180, 20, 20, 0.7)"))
        self.tray_button.setStyleSheet(self.tray_button.styleSheet().replace("rgba(50, 50, 50, 0.0)", "rgba(50, 50, 50, 0.7)"))
    
    def _on_mouse_leave(self, event):
        """Evento cuando el mouse sale del widget"""
        # Ocultar los controles
        self.controls_visible = False
        self.controls_animation_timer.start(50)  # Iniciar animación
        
        # Ocultar botones de la barra de título
        self.close_button.setStyleSheet(self.close_button.styleSheet().replace("rgba(180, 20, 20, 0.7)", "rgba(180, 20, 20, 0.0)"))
        self.tray_button.setStyleSheet(self.tray_button.styleSheet().replace("rgba(50, 50, 50, 0.7)", "rgba(50, 50, 50, 0.0)"))
    
    def _update_controls_animation(self):
        """Actualiza la animación de los controles"""
        if self.controls_visible:
            # Mostrar gradualmente
            self.controls_opacity += 0.1
            if self.controls_opacity >= 1.0:
                self.controls_opacity = 1.0
                self.controls_animation_timer.stop()
        else:
            # Ocultar gradualmente
            self.controls_opacity -= 0.1
            if self.controls_opacity <= 0.0:
                self.controls_opacity = 0.0
                self.controls_animation_timer.stop()
        
        # Aplicar opacidad a los controles
        opacity_str = str(self.controls_opacity)
        self.controls_container.setStyleSheet(f"background-color: transparent; opacity: {opacity_str};")
        
        # Forzar actualización visual
        self.controls_container.update()
    
    def _init_systray(self):
        """Inicializa el icono en la bandeja del sistema"""
        # Crear ícono en la bandeja del sistema
        self.tray_icon = QSystemTrayIcon(self)
        
        # Usar un icono predeterminado de PyQt
        self.tray_icon.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        
        # Crear menú para el ícono
        self.tray_menu = QMenu()
        
        # Acción para mostrar/ocultar la ventana
        self.show_action = QAction("Mostrar", self)
        self.show_action.triggered.connect(self.show)
        self.tray_menu.addAction(self.show_action)
        
        # Acciones para cambiar el modo
        self.widget_action = QAction("Modo Widget", self)
        self.widget_action.setCheckable(True)
        self.widget_action.setChecked(self.config.get("general", "startup_mode", "fullscreen") == "widget")
        self.widget_action.triggered.connect(lambda checked: self._set_widget_mode(checked))
        self.tray_menu.addAction(self.widget_action)
        
        # Acción para siempre encima
        self.on_top_action = QAction("Siempre Visible", self)
        self.on_top_action.setCheckable(True)
        self.on_top_action.setChecked(self.config.get("general", "always_on_top", False))
        self.on_top_action.triggered.connect(self._toggle_always_on_top)
        self.tray_menu.addAction(self.on_top_action)
        
        # Separador
        self.tray_menu.addSeparator()
        
        # Acción para salir
        self.exit_action = QAction("Salir", self)
        self.exit_action.triggered.connect(self.close)
        self.tray_menu.addAction(self.exit_action)
        
        # Asignar menú al ícono
        self.tray_icon.setContextMenu(self.tray_menu)
        
        # Mostrar el ícono en la bandeja
        self.tray_icon.show()
        
        # Conectar señal de doble clic
        self.tray_icon.activated.connect(self._on_tray_activated)
    
    def _on_tray_activated(self, reason):
        """Maneja la activación del ícono en la bandeja"""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            # Mostrar u ocultar la ventana en doble clic
            if self.isVisible():
                self.hide()
            else:
                self.show()
                self.activateWindow()
    
    def closeEvent(self, event):
        """Evento al cerrar la ventana"""
        # Cuando se cierra la ventana, minimizar a la bandeja del sistema
        if self.config.get("general", "minimize_to_tray", True):
            event.ignore()  # Ignorar el evento de cierre
            self.hide()     # Ocultar la ventana
            
            # Mostrar mensaje en la bandeja
            self.tray_icon.showMessage(
                "Sunamu sigue ejecutándose",
                "La aplicación se está ejecutando en segundo plano. Haz clic en el icono para restaurar.",
                QSystemTrayIcon.MessageIcon.Information,
                3000  # Mostrar durante 3 segundos
            )
        else:
            # Continuar con el cierre normal
            event.accept()
    
    def _toggle_minimize_to_tray(self, checked: bool):
        """Alterna la opción de minimizar a bandeja al cerrar"""
        self.config.set("general", "minimize_to_tray", checked)
        
    def _exit_application(self):
        """Cierra completamente la aplicación"""
        # Desactivar minimizar a bandeja para asegurar un cierre completo
        self.config.set("general", "minimize_to_tray", False)
        
        # Guardar configuración antes de salir
        self.config.save()
        
        # Cerrar la aplicación completamente
        QApplication.quit()
        
        # En caso de que existan otros hilos o procesos
        sys.exit(0)
    
    def _set_default_album_art(self):
        """Establece una imagen predeterminada para la portada del álbum cuando no hay imagen disponible"""
        try:
            # Usar un QPixmap vacío con fondo gris
            default_pixmap = QPixmap(self.album_art.default_size)
            default_pixmap.fill(QColor(60, 60, 60))  # Gris oscuro
            self.album_art.setPixmap(default_pixmap)
            
            # Limpiar datos de imagen
            self.album_art.image_data = None
            self.album_art.current_url = ""
            
            # Actualizar colores con paleta predeterminada
            self._update_controls_with_default_colors()
        except Exception as e:
            logging.error(f"Error al establecer portada predeterminada: {str(e)}", exc_info=True)
    
    def _update_controls_with_default_colors(self):
        """Actualiza los controles con colores predeterminados cuando no hay portada disponible"""
        # Colores predeterminados para la interfaz
        primary_color = "rgb(75, 150, 255)"    # Azul claro
        secondary_color = "rgb(30, 30, 30)"    # Gris muy oscuro
        
        # Actualizar estilo del slider
        self.progress_slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                height: 8px;
                background: #333;
                border-radius: 4px;
            }}
            QSlider::handle:horizontal {{
                width: 16px;
                margin: -4px 0;
                border-radius: 8px;
                background: {primary_color};
            }}
            QSlider::sub-page:horizontal {{
                background: {primary_color};
                border-radius: 4px;
            }}
        """)
        
        # Actualizar estilo de los botones
        for button in [self.prev_button, self.play_pause_button, self.next_button]:
            button.setStyleSheet(f"font-size: 24px; color: {primary_color}; background: transparent;")
            
    def _setup_title_scrolling(self):
        """Configura la animación de desplazamiento para títulos largos si es necesario"""
        try:
            # Verificar si el título es demasiado largo para el espacio disponible
            metrics = self.title_label.fontMetrics()
            text_width = metrics.horizontalAdvance(self.title_label.text())
            label_width = self.title_label.width()
            
            # Solo configurar animación si el texto es más ancho que la etiqueta
            if text_width > label_width:
                # Configuración para que el título se desplace si es demasiado largo
                self.title_label.setTextFormat(Qt.TextFormat.PlainText)
                self.title_label.setWordWrap(False)
                
                # Establecer estilo para permitir desplazamiento con elipsis
                self.title_label.setStyleSheet("""
                    padding-right: 10px;
                    text-overflow: ellipsis;
                """)
            else:
                # Restaurar estilo normal para títulos que caben
                self.title_label.setWordWrap(True)
                self.title_label.setStyleSheet("")
        except Exception as e:
            logging.debug(f"Error al configurar desplazamiento del título: {str(e)}")
            # No es crítico, así que solo registramos en debug

    def _set_widget_mode(self, enabled: bool):
        """Establece el modo widget o pantalla completa"""
        self.is_widget_mode = enabled
        
        if enabled:
            # Activar modo widget
            self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
            if self.is_always_on_top:
                self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
            self.widget_mode.enable()
        else:
            # Desactivar modo widget, pero mantener sin marco
            self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
            if self.is_always_on_top:
                self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
            self.widget_mode.disable()
        
        # Es necesario volver a mostrar la ventana después de cambiar las flags
        self.show()
        
        # Guardar preferencia
        self.config.set("general", "startup_mode", "widget" if enabled else "fullscreen")

    def _on_lyrics_enter(self, event):
        """Muestra la barra de desplazamiento cuando se pasa el cursor sobre las letras"""
        self.lyrics_scroll_area.verticalScrollBar().setVisible(True)
        # Cancelar el temporizador si está en marcha
        if self.scrollbar_timer.isActive():
            self.scrollbar_timer.stop()
    
    def _on_lyrics_leave(self, event):
        """Inicia el temporizador para ocultar la barra de desplazamiento"""
        # Iniciar temporizador para ocultar la barra después de 3 segundos
        self.scrollbar_timer.start(3000)
    
    def _hide_scrollbar(self):
        """Oculta la barra de desplazamiento después del tiempo especificado"""
        self.lyrics_scroll_area.verticalScrollBar().setVisible(False)

    def _update_progress_info(self):
        """Actualiza sólo la información de progreso de la pista para mayor fluidez"""
        try:
            # Si está pausada, no actualizar la posición pero mantener la visualización
            if self.is_paused:
                return
                
            # Si no hay pista actual, intentar usar la última información válida
            track_to_use = None
            if self.current_track:
                track_to_use = self.current_track
            elif self.last_track_info:
                # Si estamos en pausa manual, usar la última información guardada
                if self.paused_manually:
                    # No actualizar progreso durante pausa manual
                    return
                track_to_use = self.last_track_info
            else:
                return  # No hay información para mostrar
                
            # Si el track está pausado, no actualizar la posición
            if not track_to_use.is_playing:
                return
                
            # Estimar la posición actual basado en el tiempo transcurrido desde la última actualización
            if hasattr(self, 'last_position_ms') and hasattr(self, 'last_position_update'):
                elapsed_time = (QDateTime.currentMSecsSinceEpoch() - self.last_position_update)
                estimated_position = self.last_position_ms + elapsed_time
                
                # Asegurarse de no exceder la duración total
                if track_to_use.duration_ms > 0:
                    estimated_position = min(estimated_position, track_to_use.duration_ms)
            else:
                # Si no hay valores previos, usar la posición actual
                estimated_position = track_to_use.position_ms
                
            # Actualizar el slider y etiquetas de tiempo
            if track_to_use.duration_ms > 0:
                self.progress_slider.setValue(estimated_position)
                self.time_current_label.setText(self._format_time(estimated_position))
                
                # Guardar la posición estimada para la próxima actualización
                self.last_position_ms = estimated_position
                self.last_position_update = QDateTime.currentMSecsSinceEpoch()
                
                # También actualizar la posición en la estructura track_to_use
                if track_to_use == self.current_track:
                    self.current_track.position_ms = estimated_position
                
                # Actualizar línea actual de letras con posición estimada (mejora la sincronización)
                if track_to_use.is_playing and hasattr(self, 'current_lyrics') and self.current_lyrics and hasattr(self, 'lyrics_widgets'):
                    self._update_current_lyrics_line(estimated_position)
                    
        except Exception as e:
            logging.debug(f"Error al actualizar progreso: {e}")
            # No es crítico, solo registramos a nivel debug