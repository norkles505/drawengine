from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton,
    QLabel, QScrollArea, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QRect, QSize
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QImage, QIcon

from core.animation import Animation
from ui.button_styles import ICON_BUTTON_STYLE
from ui.icon_paths import (
    FRAME_ADD_ICON, FRAME_DUPLICATE_ICON, FRAME_DELETE_ICON,
    ANIM_SETTINGS_ICON, PLAY_ICON, PAUSE_ICON, REWIND_ICON
)


class FrameThumb(QFrame):
    clicked = pyqtSignal(int)

    def __init__(self, index: int, thumbnail: QImage | None,
                 is_active: bool = False, parent=None):
        super().__init__(parent)
        self.index     = index
        self.thumbnail = thumbnail
        self.is_active = is_active
        self.setFixedSize(58, 58)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_style()

    def _update_style(self):
        if self.is_active:
            self.setStyleSheet("""
                QFrame { border: 2px solid #f2801a;
                         border-radius: 4px; background: #3a2a15; }
            """)
        else:
            self.setStyleSheet("""
                QFrame { border: 1px solid #555;
                         border-radius: 4px; background: #282828; }
                QFrame:hover { border: 1px solid #888; background: #333; }
            """)

    def set_active(self, active: bool):
        self.is_active = active
        self._update_style()
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.thumbnail and not self.thumbnail.isNull():
            painter.drawImage(QRect(3, 3, 52, 46), self.thumbnail)
        color = QColor("#f2801a") if self.is_active else QColor("#fff")
        font  = QFont()
        font.setPointSize(8)
        font.setBold(True)
        painter.setFont(font)
        num_rect = QRect(3, 38, 52, 16)
        painter.fillRect(num_rect, QColor(0, 0, 0, 120))
        painter.setPen(QPen(color))
        painter.drawText(num_rect, Qt.AlignmentFlag.AlignCenter,
                         str(self.index + 1))
        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.index)


class TimelineWidget(QWidget):
    frame_selected   = pyqtSignal(int)
    frame_added      = pyqtSignal()
    frame_duplicated = pyqtSignal(int)
    frame_deleted    = pyqtSignal(int)
    playback_toggled = pyqtSignal(bool)

    def __init__(self, animation: Animation, parent=None):
        super().__init__(parent)
        self.animation = animation
        self.setFixedHeight(110)
        self.setStyleSheet("background: #202020;")

        self._playing       = False
        self._playback_mode = 0   # 0=loop  1=ping-pong  2=one-shot
        self._pp_dir        = 1

        self._timer = QTimer()
        self._timer.timeout.connect(self._advance_frame)
        self._thumbs: list[FrameThumb] = []

        # Audio — sistema del doc 2 que funciona
        self._player       = None
        self._audio_output = None

        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────────

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(6, 4, 6, 4)
        main_layout.setSpacing(4)

        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(4)

        self.btn_rewind = self._icon_btn(
            REWIND_ICON, "Rewind to first frame")
        self.btn_rewind.clicked.connect(self._rewind)

        self.btn_play = self._icon_btn(
            PLAY_ICON, "Play")
        self.btn_play.setCheckable(True)
        self.btn_play.clicked.connect(self._toggle_play)

        self.btn_add = self._icon_btn(
            FRAME_ADD_ICON, "Add frame")
        self.btn_add.clicked.connect(self.frame_added.emit)

        self.btn_dup = self._icon_btn(
            FRAME_DUPLICATE_ICON, "Duplicate frame")
        self.btn_dup.clicked.connect(
            lambda: self.frame_duplicated.emit(
                self.animation.current_frame_index))

        self.btn_del = self._icon_btn(
            FRAME_DELETE_ICON, "Delete frame")
        self.btn_del.clicked.connect(
            lambda: self.frame_deleted.emit(
                self.animation.current_frame_index))

        self.btn_anim_cfg = self._icon_btn(
            ANIM_SETTINGS_ICON, "Animation settings")

        self.lbl_info = QLabel()
        self.lbl_info.setStyleSheet("color: #aaa; font-size: 11px;")

        ctrl_row.addWidget(self.btn_rewind)
        ctrl_row.addWidget(self.btn_play)
        ctrl_row.addWidget(self.btn_add)
        ctrl_row.addWidget(self.btn_dup)
        ctrl_row.addWidget(self.btn_del)
        ctrl_row.addWidget(self.btn_anim_cfg)
        ctrl_row.addStretch()
        ctrl_row.addWidget(self.lbl_info)
        main_layout.addLayout(ctrl_row)

        self.scroll = QScrollArea()
        self.scroll.setFixedHeight(66)
        self.scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }")

        self.thumb_container = QWidget()
        self.thumb_layout    = QHBoxLayout(self.thumb_container)
        self.thumb_layout.setContentsMargins(2, 2, 2, 2)
        self.thumb_layout.setSpacing(4)
        self.thumb_layout.addStretch()

        self.scroll.setWidget(self.thumb_container)
        self.scroll.setWidgetResizable(True)
        main_layout.addWidget(self.scroll)

        self.refresh()

    def _icon_btn(self, icon_path, tooltip=""):
        btn = QPushButton()
        btn.setIcon(QIcon(icon_path))
        btn.setIconSize(QSize(14, 14))
        btn.setFixedSize(30, 26)
        btn.setToolTip(tooltip)
        btn.setStyleSheet(ICON_BUTTON_STYLE)
        return btn

    # ── Thumbnails ────────────────────────────────────────────────────

    def refresh(self):
        for thumb in self._thumbs:
            self.thumb_layout.removeWidget(thumb)
            thumb.deleteLater()
        self._thumbs.clear()

        cur   = self.animation.current_frame_index
        saved = cur

        for i in range(len(self.animation.frames)):
            self.animation.current_frame_index = i
            thumb_img = self._render_thumb(i)
            self.animation.current_frame_index = saved

            thumb = FrameThumb(i, thumb_img, is_active=(i == cur))
            thumb.clicked.connect(self._on_thumb_clicked)
            self.thumb_layout.insertWidget(i, thumb)
            self._thumbs.append(thumb)

        total = len(self.animation.frames)
        ms    = self.animation.total_duration_ms()
        self.lbl_info.setText(
            f"Frame {cur + 1}/{total}  ·  "
            f"{self.animation.fps} FPS  ·  {ms/1000:.2f}s")

    def _render_thumb(self, frame_index: int) -> QImage:
        frame  = self.animation.frames[frame_index]
        result = QImage(self.animation.width, self.animation.height,
                        QImage.Format.Format_ARGB32_Premultiplied)
        result.fill(Qt.GlobalColor.white)
        painter = QPainter(result)
        for layer in frame.layers:
            if layer.visible:
                painter.setOpacity(layer.opacity / 255.0)
                painter.drawImage(0, 0, layer.image)
        painter.end()
        return result.scaled(52, 46,
                             Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)

    # ── Playback ──────────────────────────────────────────────────────

    def _toggle_play(self):
        self._playing = not self._playing
        self.btn_play.setChecked(self._playing)
        if self._playing:
            self.btn_play.setIcon(QIcon(PAUSE_ICON))
            self.btn_play.setToolTip("Pause")
            if self._playback_mode != 1:   # no audio en ping-pong
                self._start_audio()
            self._timer.start(int(1000 / self.animation.fps))
        else:
            self.btn_play.setIcon(QIcon(PLAY_ICON))
            self.btn_play.setToolTip("Play")
            self._timer.stop()
            self._pause_audio()
        self.playback_toggled.emit(self._playing)

    def _rewind(self):
        was_playing = self._playing
        if was_playing:
            self._toggle_play()
        self.animation.current_frame_index = 0
        self._pp_dir = 1
        self.refresh()
        self.frame_selected.emit(0)
        if was_playing:
            self._toggle_play()

    def _advance_frame(self):
        total = len(self.animation.frames)
        cur   = self.animation.current_frame_index

        if self._playback_mode == 0:
            nxt = (cur + 1) % total
            if nxt == 0:
                self._seek_audio(0)
        elif self._playback_mode == 1:
            nxt = cur + self._pp_dir
            if nxt >= total:
                self._pp_dir = -1
                nxt = max(0, total - 2)
            elif nxt < 0:
                self._pp_dir = 1
                nxt = min(total - 1, 1)
        else:
            nxt = cur + 1
            if nxt >= total:
                self._timer.stop()
                self._pause_audio()
                self._playing = False
                self.btn_play.setChecked(False)
                self.btn_play.setIcon(QIcon(PLAY_ICON))
                self.btn_play.setToolTip("Play")
                self.playback_toggled.emit(False)
                return

        self.animation.current_frame_index = nxt
        self._update_active(cur, nxt)       # ← ligero, no reconstruye todo
        self.frame_selected.emit(nxt)

    def _on_thumb_clicked(self, index: int):
        if self._playing:
            return
        self.animation.current_frame_index = index
        self.refresh()
        self.frame_selected.emit(index)

    def stop_playback(self):
        if self._playing:
            self._toggle_play()

    def set_playback_mode(self, mode: int):
        """0 = loop, 1 = ping-pong (sin audio), 2 = one-shot."""
        self._playback_mode = mode
        self._pp_dir = 1

        # Aviso en el label de info
        if mode == 1:
            total = len(self.animation.frames)
            ms    = self.animation.total_duration_ms()
            cur   = self.animation.current_frame_index
            self.lbl_info.setText(
                f"Frame {cur + 1}/{total}  ·  "
                f"{self.animation.fps} FPS  ·  {ms/1000:.2f}s  ·  "
                f"🔇 Audio disabled in ping-pong"
            )
        else:
            self.refresh()   # restaura el label normal

    # ── Audio — sistema del doc 2 (funciona) ─────────────────────────

    def _init_player(self):
        if self._player is not None:
            return
        try:
            from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
            self._audio_output = QAudioOutput()
            self._audio_output.setVolume(1.0)
            self._player = QMediaPlayer()
            self._player.setAudioOutput(self._audio_output)
        except Exception:
            self._player = None

    def _start_audio(self):
        audio_path = getattr(self.animation, 'audio_path', None)
        if not audio_path:
            return
        self._init_player()
        if self._player is None:
            return
        try:
            from PyQt6.QtCore import QUrl
            frame_ms = int(
                self.animation.current_frame_index / self.animation.fps * 1000
            )
            self._player.setSource(QUrl.fromLocalFile(audio_path))
            self._player.setPosition(frame_ms)
            self._player.play()
        except Exception:
            pass

    def _pause_audio(self):
        if self._player:
            try:
                self._player.pause()
            except Exception:
                pass

    def _seek_audio(self, frame_index: int):
        if self._player is None:
            return
        try:
            ms = int(frame_index / self.animation.fps * 1000)
            self._player.setPosition(ms)
        except Exception:
            pass
    
    def _update_active(self, old: int, new: int):
        """Actualiza solo el resaltado del thumb activo, sin reconstruir."""
        if old < len(self._thumbs):
            self._thumbs[old].set_active(False)
        if new < len(self._thumbs):
            self._thumbs[new].set_active(True)

        # Actualizar label de info
        total = len(self.animation.frames)
        ms    = self.animation.total_duration_ms()
        self.lbl_info.setText(
            f"Frame {new + 1}/{total}  ·  "
            f"{self.animation.fps} FPS  ·  {ms/1000:.2f}s")

        # Scroll automático al thumb activo
        if new < len(self._thumbs):
            self.scroll.ensureWidgetVisible(self._thumbs[new])
