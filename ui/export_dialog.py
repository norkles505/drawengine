import os
import numpy as np
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QFileDialog,
    QProgressBar, QFrame, QSpinBox, QScrollArea,
    QWidget, QGridLayout, QSizePolicy
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QImage, QPixmap, QPainter, QColor


# ── Worker de exportación ─────────────────────────────────────────────

class ExportWorker(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(str)
    error    = pyqtSignal(str)

    def __init__(self, frames_rgb, fps, fmt, path, audio_path=None,
                 sprite_cols=4):
        super().__init__()
        self.frames_rgb  = frames_rgb
        self.fps         = fps
        self.fmt         = fmt
        self.path        = path
        self.audio_path  = audio_path
        self.sprite_cols = sprite_cols

    def run(self):
        try:
            dispatch = {
                "gif":        self._export_gif,
                "mp4":        self._export_mp4,
                "webp":       self._export_webp,
                "png_seq":    self._export_png_seq,
                "spritesheet":self._export_spritesheet,
            }
            dispatch[self.fmt]()
            self.finished.emit(self.path)
        except Exception as e:
            self.error.emit(str(e))

    # ── Formatos ──────────────────────────────────────────────────────

    def _export_gif(self):
        import imageio
        total    = len(self.frames_rgb)
        duration = 1.0 / self.fps
        with imageio.get_writer(self.path, mode="I",
                                duration=duration, loop=0) as w:
            for i, frame in enumerate(self.frames_rgb):
                w.append_data(frame)
                self.progress.emit(int((i + 1) / total * 100))

    def _export_mp4(self):
        import imageio
        total  = len(self.frames_rgb)
        writer = imageio.get_writer(
            self.path, fps=self.fps, codec="libx264",
            output_params=["-crf", "18", "-pix_fmt", "yuv420p"]
        )
        for i, frame in enumerate(self.frames_rgb):
            writer.append_data(frame)
            self.progress.emit(int((i + 1) / total * 80))
        writer.close()
        if self.audio_path and os.path.isfile(self.audio_path):
            self._mux_audio()
        else:
            self.progress.emit(100)

    def _mux_audio(self):
        import subprocess
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        tmp    = self.path.replace(".mp4", "_tmp.mp4")
        os.rename(self.path, tmp)
        duration = len(self.frames_rgb) / self.fps
        cmd = [ffmpeg, "-y",
               "-i", tmp, "-i", self.audio_path,
               "-t", str(duration),
               "-c:v", "copy", "-c:a", "aac", "-shortest",
               self.path]
        subprocess.run(cmd, check=True,
                       stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
        os.remove(tmp)
        self.progress.emit(100)

    def _export_webp(self):
        """WebP animado usando Pillow."""
        from PIL import Image
        total    = len(self.frames_rgb)
        duration = int(1000 / self.fps)   # ms por frame
        pil_frames = []
        for i, arr in enumerate(self.frames_rgb):
            pil_frames.append(Image.fromarray(arr, "RGB"))
            self.progress.emit(int((i + 1) / total * 70))

        pil_frames[0].save(
            self.path,
            format="WEBP",
            save_all=True,
            append_images=pil_frames[1:],
            duration=duration,
            loop=0,
            quality=90,
        )
        self.progress.emit(100)

    def _export_png_seq(self):
        import imageio
        os.makedirs(self.path, exist_ok=True)
        total = len(self.frames_rgb)
        for i, frame in enumerate(self.frames_rgb):
            imageio.imwrite(
                os.path.join(self.path, f"frame_{i:04d}.png"), frame)
            self.progress.emit(int((i + 1) / total * 100))

    def _export_spritesheet(self):
        """
        Sprite sheet: todos los frames en una sola imagen PNG.
        Disposición: N columnas × M filas.
        """
        from PIL import Image
        total  = len(self.frames_rgb)
        cols   = min(self.sprite_cols, total)
        rows   = (total + cols - 1) // cols
        fh, fw = self.frames_rgb[0].shape[:2]

        sheet = Image.new("RGB", (fw * cols, fh * rows), (0, 0, 0))
        for i, arr in enumerate(self.frames_rgb):
            c = i % cols
            r = i // cols
            sheet.paste(Image.fromarray(arr, "RGB"), (c * fw, r * fh))
            self.progress.emit(int((i + 1) / total * 100))

        sheet.save(self.path, "PNG")


# ── Diálogo principal ─────────────────────────────────────────────────

class ExportDialog(QDialog):
    def __init__(self, animation, canvas, parent=None):
        super().__init__(parent)
        self.animation = animation
        self.canvas    = canvas
        self.setWindowTitle("Export")
        self.setMinimumWidth(540)
        self.setModal(True)
        from ui.dark_titlebar import apply_dark_titlebar
        apply_dark_titlebar(self)
        self.setStyleSheet(self._style())
        self._worker      = None
        self._frames_rgb  = None   # caché de frames renderizados
        self._build_ui()
        # Pre-renderizar frames para el preview
        QTimer.singleShot(100, self._prerender)

    # ── UI ────────────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        layout.addWidget(self._title("Export Animation"))

        # Info
        anim = self.animation
        dur  = anim.total_duration_ms() / 1000
        info = QLabel(
            f"{len(anim.frames)} frames  ·  {anim.fps} FPS  ·  "
            f"{dur:.2f}s  ·  {self.canvas.width}×{self.canvas.height}"
        )
        info.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(info)

        layout.addWidget(self._sep())

        # ── Preview de frames ─────────────────────────────────────────
        layout.addWidget(self._lbl("Preview"))
        self.preview_scroll = QScrollArea()
        self.preview_scroll.setFixedHeight(110)
        self.preview_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.preview_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.preview_scroll.setStyleSheet(
            "QScrollArea { border: 1px solid #333; background: #111; }")

        self.preview_container = QWidget()
        self.preview_layout    = QHBoxLayout(self.preview_container)
        self.preview_layout.setContentsMargins(4, 4, 4, 4)
        self.preview_layout.setSpacing(4)
        self.preview_layout.addStretch()
        self.preview_scroll.setWidget(self.preview_container)
        self.preview_scroll.setWidgetResizable(True)
        layout.addWidget(self.preview_scroll)

        self.lbl_loading = QLabel("Rendering preview…")
        self.lbl_loading.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(self.lbl_loading)

        layout.addWidget(self._sep())

        # ── Opciones de export ────────────────────────────────────────
        opt_row = QHBoxLayout()

        # Formato
        fmt_col = QVBoxLayout()
        fmt_col.addWidget(self._lbl("Format"))
        self.combo_fmt = QComboBox()
        self.combo_fmt.addItems([
            "MP4 (H.264)",
            "GIF",
            "WebP animated",
            "PNG sequence",
            "Sprite sheet (PNG)",
        ])
        self.combo_fmt.currentIndexChanged.connect(self._on_fmt_changed)
        fmt_col.addWidget(self.combo_fmt)
        opt_row.addLayout(fmt_col)

        opt_row.addSpacing(16)

        # Columnas sprite sheet
        self.sprite_col_widget = QWidget()
        sc_lay = QVBoxLayout(self.sprite_col_widget)
        sc_lay.setContentsMargins(0, 0, 0, 0)
        sc_lay.addWidget(self._lbl("Columns"))
        self.spin_cols = QSpinBox()
        self.spin_cols.setRange(1, 32)
        self.spin_cols.setValue(4)
        sc_lay.addWidget(self.spin_cols)
        self.sprite_col_widget.setVisible(False)
        opt_row.addWidget(self.sprite_col_widget)

        opt_row.addStretch()
        layout.addLayout(opt_row)

        # Audio info
        ap = getattr(self.animation, 'audio_path', None)
        audio_txt = (f"🎵 {os.path.basename(ap)}"
                     if ap and os.path.isfile(ap)
                     else "🎵 No audio (MP4 will be silent)")
        self.lbl_audio = QLabel(audio_txt)
        self.lbl_audio.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(self.lbl_audio)

        # Progreso
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color: #888; font-size: 10px;")
        layout.addWidget(self.lbl_status)

        # Botón export
        self.btn_export = QPushButton("Export…")
        self.btn_export.setFixedHeight(40)
        self.btn_export.setStyleSheet("""
            QPushButton {
                background: #f2801a; color: white;
                border: none; border-radius: 6px;
                font-size: 13px; font-weight: bold;
            }
            QPushButton:hover    { background: #ff9d40; }
            QPushButton:disabled { background: #333; color: #666; }
        """)
        self.btn_export.clicked.connect(self._start_export)
        layout.addWidget(self.btn_export)

    # ── Pre-render preview ────────────────────────────────────────────

    def _prerender(self):
        self._frames_rgb = self._render_frames()
        self.lbl_loading.setVisible(False)
        self._build_preview()

    def _render_frames(self) -> list:
        saved_index  = self.animation.current_frame_index
        # Desactivar onion temporalmente para el export
        saved_onion  = self.canvas.onion_enabled
        self.canvas.onion_enabled = False

        frames_rgb = []
        for i in range(len(self.animation.frames)):
            self.animation.current_frame_index = i
            img = self.canvas.composite()
            img = img.convertToFormat(QImage.Format.Format_RGB888)
            ptr = img.bits()
            ptr.setsize(img.sizeInBytes())
            arr = np.frombuffer(ptr, dtype=np.uint8).reshape(
                self.canvas.height, self.canvas.width, 3).copy()
            frames_rgb.append(arr)

        # Restaurar estado original
        self.animation.current_frame_index = saved_index
        self.canvas.onion_enabled          = saved_onion
        return frames_rgb

    def _build_preview(self):
        # Limpiar
        while self.preview_layout.count() > 1:
            item = self.preview_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        thumb_h = 88
        for i, arr in enumerate(self._frames_rgb):
            fh, fw = arr.shape[:2]
            scale  = thumb_h / fh
            tw     = int(fw * scale)

            img = QImage(arr.tobytes(), fw, fh,
                         QImage.Format.Format_RGB888)
            pix = QPixmap.fromImage(img).scaled(
                tw, thumb_h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )

            # Marco con número
            frame_widget = QWidget()
            frame_widget.setFixedSize(tw + 4, thumb_h + 18)
            fw_lay = QVBoxLayout(frame_widget)
            fw_lay.setContentsMargins(2, 2, 2, 2)
            fw_lay.setSpacing(2)

            lbl_img = QLabel()
            lbl_img.setPixmap(pix)
            lbl_img.setFixedSize(tw, thumb_h)
            lbl_img.setStyleSheet(
                "border: 1px solid #444; border-radius: 2px;")

            lbl_num = QLabel(str(i + 1))
            lbl_num.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_num.setStyleSheet("color: #666; font-size: 9px;")

            fw_lay.addWidget(lbl_img)
            fw_lay.addWidget(lbl_num)
            self.preview_layout.insertWidget(i, frame_widget)

    # ── Export ────────────────────────────────────────────────────────

    def _on_fmt_changed(self, idx):
        self.sprite_col_widget.setVisible(idx == 4)

    def _start_export(self):
        if self._frames_rgb is None:
            self._frames_rgb = self._render_frames()

        fmt_map = {0: "mp4", 1: "gif", 2: "webp",
                   3: "png_seq", 4: "spritesheet"}
        fmt = fmt_map[self.combo_fmt.currentIndex()]

        filters = {
            "mp4":         ("Export MP4",          "animation.mp4",   "MP4 (*.mp4)"),
            "gif":         ("Export GIF",           "animation.gif",   "GIF (*.gif)"),
            "webp":        ("Export WebP",          "animation.webp",  "WebP (*.webp)"),
            "png_seq":     ("Select output folder", "",                ""),
            "spritesheet": ("Export Sprite Sheet",  "spritesheet.png", "PNG (*.png)"),
        }

        title, default, flt = filters[fmt]
        if fmt == "png_seq":
            path = QFileDialog.getExistingDirectory(self, title)
        else:
            path, _ = QFileDialog.getSaveFileName(
                self, title, default, flt)
        if not path:
            return

        audio = getattr(self.animation, 'audio_path', None)
        self._worker = ExportWorker(
            self._frames_rgb, self.animation.fps, fmt, path,
            audio, self.spin_cols.value()
        )
        self._worker.progress.connect(self.progress.setValue)
        self._worker.finished.connect(self._on_done)
        self._worker.error.connect(self._on_error)

        self.btn_export.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.lbl_status.setText("Exporting…")
        self._worker.start()

    def _on_done(self, path):
        self.lbl_status.setText(f"✅ Saved: {os.path.basename(path)}")
        self.btn_export.setEnabled(True)
        self.progress.setValue(100)

    def _on_error(self, msg):
        self.lbl_status.setText(f"❌ {msg}")
        self.btn_export.setEnabled(True)

    # ── Helpers ───────────────────────────────────────────────────────

    def _title(self, text):
        l = QLabel(text)
        l.setStyleSheet(
            "font-size: 15px; font-weight: bold; color: #f2801a;")
        return l

    def _lbl(self, text):
        l = QLabel(text)
        l.setStyleSheet("color: #aaa; font-size: 11px;")
        return l

    def _sep(self):
        s = QFrame()
        s.setFrameShape(QFrame.Shape.HLine)
        s.setStyleSheet("color: #333333;")
        return s

    def _style(self):
        return """
            QDialog { background: #202020; }
            QLabel  { color: #ddd; }
            QComboBox, QSpinBox {
                background: #282828; color: #eee;
                border: 1px solid #3a3a3a; border-radius: 4px;
                padding: 4px 8px; font-size: 11px;
            }
            QComboBox:hover, QSpinBox:hover {
                border: 1px solid #f2801a;
            }
            QComboBox QAbstractItemView {
                background: #282828; color: #eee;
                selection-background-color: #f2801a;
            }
            QProgressBar {
                background: #282828; border: 1px solid #3a3a3a;
                border-radius: 4px; height: 12px;
            }
            QProgressBar::chunk {
                background: #f2801a; border-radius: 4px;
            }
            QScrollBar:horizontal {
                background: #202020; height: 8px;
            }
            QScrollBar::handle:horizontal {
                background: #444; border-radius: 4px;
            }
        """
