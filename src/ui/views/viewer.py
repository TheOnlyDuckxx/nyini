from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageOps
from PySide6.QtCore import QEvent, QPoint, Qt, QUrl, Signal
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QScrollArea, QStackedWidget, QVBoxLayout, QWidget

from src.domain.enums import MediaKind
from src.domain.models import Wallpaper
from src.i18n import tr


class ViewerCanvas(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._image: QImage | None = None
        self._empty_text = tr("Selectionnez un wallpaper")
        self.setObjectName("viewerCanvas")
        self.setMinimumSize(200, 200)

    def set_image(self, image: QImage | None, *, empty_text: str | None = None) -> None:
        self._image = image
        if empty_text is not None:
            self._empty_text = empty_text
        self.update()

    def set_empty_text(self, text: str) -> None:
        self._empty_text = text
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#0d1117"))
        if self._image is None or self._image.isNull():
            painter.setPen(QColor("#9aa4b2"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._empty_text)
            return
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.drawImage(self.rect(), self._image)


class WallpaperViewer(QWidget):
    navigate_requested = Signal(int)
    exit_requested = Signal()
    zoom_changed = Signal(float)
    gowall_requested = Signal()
    context_menu_requested = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self._image: QImage | None = None
        self._wallpaper: Wallpaper | None = None
        self._zoom_factor = 1.0
        self._quick_preview = False
        self._panning = False
        self._last_pan_pos = QPoint()
        self._animated_video_previews_enabled = True
        self._gowall_available = False
        self._gowall_message = ""

        self.title_label = QLabel()
        self.title_label.setObjectName("viewerTitle")
        self.meta_label = QLabel()
        self.meta_label.setObjectName("viewerMeta")
        self.mode_badge = QLabel()
        self.mode_badge.setObjectName("viewerBadge")
        self.zoom_label = QLabel("100%")
        self.zoom_label.setObjectName("viewerBadge")
        self.previous_button = QPushButton()
        self.previous_button.clicked.connect(lambda: self.navigate_requested.emit(-1))
        self.next_button = QPushButton()
        self.next_button.clicked.connect(lambda: self.navigate_requested.emit(1))
        self.gowall_button = QPushButton()
        self.gowall_button.clicked.connect(self.gowall_requested.emit)
        self.reset_zoom_button = QPushButton()
        self.reset_zoom_button.clicked.connect(self.reset_zoom)

        self.canvas = ViewerCanvas()
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setWidget(self.canvas)
        self.scroll_area.viewport().installEventFilter(self)
        self.canvas.installEventFilter(self)
        self.canvas.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.canvas.customContextMenuRequested.connect(self.context_menu_requested.emit)

        self.video_widget = QVideoWidget()
        self.video_widget.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
        self.video_widget.installEventFilter(self)
        self.video_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.video_widget.customContextMenuRequested.connect(self.context_menu_requested.emit)
        self.video_widget.setMinimumSize(200, 200)
        video_container = QWidget()
        video_layout = QVBoxLayout(video_container)
        video_layout.setContentsMargins(0, 0, 0, 0)
        video_layout.addWidget(self.video_widget)

        self.preview_stack = QStackedWidget()
        self.preview_stack.addWidget(self.scroll_area)
        self.preview_stack.addWidget(video_container)

        self.audio_output = QAudioOutput(self)
        self.audio_output.setMuted(True)
        self.media_player = QMediaPlayer(self)
        self.media_player.setAudioOutput(self.audio_output)
        self.media_player.setVideoOutput(self.video_widget)
        self.media_player.setLoops(QMediaPlayer.Loops.Infinite)
        self.media_player.errorOccurred.connect(self._on_media_error)

        header = QWidget()
        header.setObjectName("viewerHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 14, 16, 14)
        header_text_layout = QVBoxLayout()
        header_text_layout.addWidget(self.title_label)
        header_text_layout.addWidget(self.meta_label)
        header_layout.addLayout(header_text_layout, stretch=1)
        header_layout.addWidget(self.mode_badge)
        header_layout.addWidget(self.zoom_label)
        header_layout.addWidget(self.previous_button)
        header_layout.addWidget(self.next_button)
        header_layout.addWidget(self.gowall_button)
        header_layout.addWidget(self.reset_zoom_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(header)
        layout.addWidget(self.preview_stack)

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.refresh_language()

    @property
    def wallpaper(self) -> Wallpaper | None:
        return self._wallpaper

    @property
    def quick_preview_mode(self) -> bool:
        return self._quick_preview

    def refresh_language(self) -> None:
        self.previous_button.setText(tr("Precedent"))
        self.next_button.setText(tr("Suivant"))
        self.gowall_button.setText(tr("Themes Gowall"))
        self.reset_zoom_button.setText(tr("Reset zoom"))
        self.set_wallpaper(self._wallpaper)

    def set_animated_video_previews_enabled(self, enabled: bool) -> None:
        self._animated_video_previews_enabled = enabled
        if self._wallpaper is not None and self._wallpaper.media_kind is MediaKind.VIDEO:
            self.set_wallpaper(self._wallpaper)

    def set_wallpaper(self, wallpaper: Wallpaper | None) -> None:
        self._wallpaper = wallpaper
        self._zoom_factor = 1.0
        self._panning = False
        if wallpaper is None:
            self._stop_video_preview()
            self._image = None
            self._quick_preview = False
            self.title_label.setText(tr("Visionneuse"))
            self.meta_label.setText(tr("Selectionnez un wallpaper"))
            self.canvas.set_image(None, empty_text=tr("Selectionnez un wallpaper"))
            self.canvas.resize(self.canvas.minimumSize())
            self.preview_stack.setCurrentWidget(self.scroll_area)
            self.reset_zoom_button.setEnabled(True)
            self.mode_badge.setText(tr("Plein ecran"))
            self.zoom_label.setText("100%")
            self._update_gowall_button()
            return
        self.title_label.setText(wallpaper.filename)
        details = []
        if wallpaper.width and wallpaper.height:
            details.append(f"{wallpaper.width} x {wallpaper.height}")
        if wallpaper.media_kind is MediaKind.VIDEO and wallpaper.duration_seconds is not None:
            details.append(self._human_duration(wallpaper.duration_seconds))
        details.append(str(wallpaper.path.parent))
        self.meta_label.setText(" · ".join(details))
        if wallpaper.media_kind is MediaKind.VIDEO:
            self._show_video_wallpaper(wallpaper)
        else:
            self._show_image_wallpaper(wallpaper)
        self._refresh_mode_badge()
        self._update_gowall_button()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._wallpaper is not None and self._wallpaper.media_kind is MediaKind.IMAGE:
            self._refresh_image()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._wallpaper is not None and self._wallpaper.media_kind is MediaKind.VIDEO and self._animated_video_previews_enabled:
            self._start_video_preview(self._wallpaper.path)

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        if self._wallpaper is not None and self._wallpaper.media_kind is MediaKind.VIDEO:
            self._stop_video_preview()

    def keyPressEvent(self, event) -> None:
        if self._wallpaper is None or self._wallpaper.media_kind is MediaKind.IMAGE:
            if event.key() in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
                self.zoom_in()
                return
            if event.key() == Qt.Key.Key_Minus:
                self.zoom_out()
                return
            if event.key() == Qt.Key.Key_0:
                self.reset_zoom()
                return
        if event.key() == Qt.Key.Key_Left:
            self.navigate_requested.emit(-1)
            return
        if event.key() == Qt.Key.Key_Right:
            self.navigate_requested.emit(1)
            return
        if self._quick_preview and event.key() in (Qt.Key.Key_Escape, Qt.Key.Key_Space):
            self.exit_requested.emit()
            return
        if event.key() == Qt.Key.Key_Escape:
            self.exit_requested.emit()
            return
        super().keyPressEvent(event)

    def eventFilter(self, watched, event) -> bool:
        if self._wallpaper is None or self._wallpaper.media_kind is not MediaKind.IMAGE:
            return super().eventFilter(watched, event)
        if event.type() == QEvent.Type.Wheel and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.angleDelta().y() > 0:
                self.zoom_in()
            else:
                self.zoom_out()
            event.accept()
            return True
        if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton and self._can_pan():
            self._panning = True
            self._last_pan_pos = event.globalPosition().toPoint()
            self.scroll_area.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return True
        if event.type() == QEvent.Type.MouseMove and self._panning:
            current_pos = event.globalPosition().toPoint()
            delta = current_pos - self._last_pan_pos
            self._last_pan_pos = current_pos
            self.scroll_area.horizontalScrollBar().setValue(self.scroll_area.horizontalScrollBar().value() - delta.x())
            self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().value() - delta.y())
            event.accept()
            return True
        if event.type() == QEvent.Type.MouseButtonRelease and self._panning:
            self._panning = False
            self.scroll_area.viewport().unsetCursor()
            event.accept()
            return True
        return super().eventFilter(watched, event)

    def set_quick_preview_mode(self, value: bool) -> None:
        self._quick_preview = value
        self._refresh_mode_badge()

    def set_gowall_enabled(self, enabled: bool, message: str = "") -> None:
        self._gowall_available = enabled
        self._gowall_message = message
        self._update_gowall_button()

    def context_global_pos(self, point) -> QPoint:
        if self.preview_stack.currentWidget() is self.scroll_area:
            return self.canvas.mapToGlobal(point)
        return self.video_widget.mapToGlobal(point)

    def zoom_in(self) -> None:
        if self._wallpaper is None or self._wallpaper.media_kind is not MediaKind.IMAGE:
            return
        self._zoom_factor = min(self._zoom_factor * 1.2, 8.0)
        self._refresh_image()

    def zoom_out(self) -> None:
        if self._wallpaper is None or self._wallpaper.media_kind is not MediaKind.IMAGE:
            return
        self._zoom_factor = max(self._zoom_factor / 1.2, 0.2)
        self._refresh_image()

    def reset_zoom(self) -> None:
        if self._wallpaper is None or self._wallpaper.media_kind is not MediaKind.IMAGE:
            return
        self._zoom_factor = 1.0
        self._refresh_image()

    def _can_pan(self) -> bool:
        return self.canvas.width() > self.scroll_area.viewport().width() or self.canvas.height() > self.scroll_area.viewport().height()

    def _show_image_wallpaper(self, wallpaper: Wallpaper) -> None:
        self._stop_video_preview()
        self._image = self._load_image(wallpaper.path)
        self.preview_stack.setCurrentWidget(self.scroll_area)
        self.reset_zoom_button.setEnabled(True)
        self._refresh_image()

    def _show_video_wallpaper(self, wallpaper: Wallpaper) -> None:
        self.reset_zoom_button.setEnabled(False)
        self.zoom_label.setText(tr("Video"))
        if self._animated_video_previews_enabled:
            self._image = None
            self.preview_stack.setCurrentWidget(self.preview_stack.widget(1))
            self._start_video_preview(wallpaper.path)
            return
        self._stop_video_preview()
        self.preview_stack.setCurrentWidget(self.scroll_area)
        self._image = self._load_image(wallpaper.thumbnail_path or wallpaper.path)
        self._refresh_image()

    def _start_video_preview(self, path: Path) -> None:
        self.media_player.stop()
        self.media_player.setSource(QUrl.fromLocalFile(str(path)))
        self.media_player.play()

    def _stop_video_preview(self) -> None:
        self.media_player.stop()
        self.media_player.setSource(QUrl())

    def _load_image(self, path: Path) -> QImage:
        try:
            with Image.open(path) as image:
                image = ImageOps.exif_transpose(image)
                rgba = image.convert("RGBA")
                data = rgba.tobytes("raw", "RGBA")
                qimage = QImage(data, rgba.width, rgba.height, rgba.width * 4, QImage.Format.Format_RGBA8888)
                return qimage.copy()
        except Exception:
            fallback = QImage(800, 500, QImage.Format.Format_RGB32)
            fallback.fill(QColor("#000000"))
            return fallback

    def _refresh_image(self) -> None:
        if self._image is None or self._image.isNull():
            return
        target = self.scroll_area.viewport().size()
        if target.width() <= 0 or target.height() <= 0:
            return
        fit_scale = min(target.width() / max(1, self._image.width()), target.height() / max(1, self._image.height()))
        scale = max(0.05, fit_scale * self._zoom_factor)
        scaled_width = max(1, int(self._image.width() * scale))
        scaled_height = max(1, int(self._image.height() * scale))
        self.canvas.resize(scaled_width, scaled_height)
        self.canvas.set_image(self._image)
        self.zoom_label.setText(f"{int(scale * 100)}%")
        self.zoom_changed.emit(scale)

    def _refresh_mode_badge(self) -> None:
        if self._wallpaper is not None and self._wallpaper.media_kind is MediaKind.VIDEO:
            label = tr("Preview video") if self._animated_video_previews_enabled else tr("Poster video")
        else:
            label = tr("Quick preview") if self._quick_preview else tr("Visionneuse")
        self.mode_badge.setText(label)

    def _update_gowall_button(self) -> None:
        enabled = self._gowall_available and (self._wallpaper is None or self._wallpaper.media_kind is MediaKind.IMAGE)
        message = self._gowall_message
        if self._wallpaper is not None and self._wallpaper.media_kind is MediaKind.VIDEO:
            message = tr("Gowall ne s'applique qu'aux wallpapers image.")
        self.gowall_button.setEnabled(enabled)
        self.gowall_button.setToolTip(message)

    def _on_media_error(self, _error, _message: str) -> None:
        if self._wallpaper is None or self._wallpaper.media_kind is not MediaKind.VIDEO:
            return
        self.preview_stack.setCurrentWidget(self.scroll_area)
        self._image = self._load_image(self._wallpaper.thumbnail_path or self._wallpaper.path)
        self._refresh_image()
        self.mode_badge.setText(tr("Poster video"))

    def _human_duration(self, duration_seconds: float) -> str:
        total_seconds = max(0, int(duration_seconds))
        minutes, seconds = divmod(total_seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours:d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:d}:{seconds:02d}"
