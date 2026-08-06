import os
import cv2
import tempfile
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel,
    QProgressBar, QPushButton, QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QImage, QPainter


class VideoImportWorker(QThread):
    progress   = pyqtSignal(int)       # 0-100
    finished   = pyqtSignal(str)       # audio_path o ""
    error      = pyqtSignal(str)

    def __init__(self, path: str, canvas):
        super().__init__()
        self._path   = path
        self._canvas = canvas

    def run(self):
        try:
            cap = cv2.VideoCapture(self._path)
            if not cap.isOpened():
                self.error.emit("No se pudo abrir el video.")
                return

            video_fps   = cap.get(cv2.CAP_PROP_FPS) or 24
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            anim_fps    = self._canvas.animation.fps
            cw          = self._canvas.width
            ch          = self._canvas.height
            anim        = self._canvas.animation

            # Calcular qué frames del video usar según FPS de animación
            duration_s  = total_frames / video_fps
            n_anim      = max(1, int(duration_s * anim_fps))

            # Limpiar frames existentes excepto el primero
            while len(anim.frames) > 1:
                anim.delete_frame(len(anim.frames) - 1)

            for i in range(n_anim):
                # Qué frame del video corresponde
                video_frame_idx = int(i * video_fps / anim_fps)
                cap.set(cv2.CAP_PROP_POS_FRAMES, video_frame_idx)
                ret, bgr = cap.read()
                if not ret:
                    break

                # Convertir BGR → ARGB
                rgb  = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                h, w = rgb.shape[:2]
                qimg = QImage(rgb.tobytes(), w, h,
                              w * 3, QImage.Format.Format_RGB888)
                qimg = qimg.convertToFormat(
                    QImage.Format.Format_ARGB32_Premultiplied)

                # Escalar manteniendo aspecto
                if w != cw or h != ch:
                    qimg = qimg.scaled(
                        cw, ch,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation)

                # Primer frame ya existe, los demás se agregan
                if i == 0:
                    frame = anim.frames[0]
                else:
                    frame = anim.add_frame()

                layer = frame.layers[0]
                layer.name = f"Video {i+1}"
                painter = QPainter(layer.image)
                painter.fillRect(layer.image.rect(),
                                 Qt.GlobalColor.transparent)
                x = (cw - qimg.width())  // 2
                y = (ch - qimg.height()) // 2
                painter.drawImage(x, y, qimg)
                painter.end()

                pct = int((i + 1) / n_anim * 90)
                self.progress.emit(pct)

            cap.release()

            # Extraer audio
            # Extraer audio
            # Extraer audio
            audio_out = ""
            try:
                from moviepy import VideoFileClip
                tmp = tempfile.mktemp(suffix=".mp3")
                clip = VideoFileClip(self._path)
                if clip.audio is not None:
                    clip.audio.write_audiofile(tmp, logger=None)
                    audio_out = tmp
                clip.close()
            except Exception as e:
                print(f"ERROR AUDIO: {e}")
                import traceback
                traceback.print_exc()

            self.progress.emit(100)
            self.finished.emit(audio_out)

        except Exception as e:
            self.error.emit(str(e))


class VideoImportDialog(QDialog):
    def __init__(self, path: str, canvas, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Importando Video…")
        self.setFixedSize(360, 140)
        from ui.dark_titlebar import apply_dark_titlebar
        apply_dark_titlebar(self)
        self.setStyleSheet("background: #202020; color: #ddd;")
        self.setWindowFlags(
            self.windowFlags() &
            ~Qt.WindowType.WindowCloseButtonHint)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        self._lbl = QLabel(f"Procesando: {os.path.basename(path)}")
        self._lbl.setWordWrap(True)
        self._lbl.setStyleSheet("font-size: 11px; color: #aaa;")
        layout.addWidget(self._lbl)

        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setStyleSheet("""
            QProgressBar {
                background: #282828; border-radius: 4px;
                height: 18px; text-align: center; color: white;
            }
            QProgressBar::chunk {
                background: #f2801a; border-radius: 4px;
            }
        """)
        layout.addWidget(self._bar)

        self._lbl_pct = QLabel("0%")
        self._lbl_pct.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_pct.setStyleSheet("color: #f2801a; font-size: 12px;")
        layout.addWidget(self._lbl_pct)

        self._worker = VideoImportWorker(path, canvas)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._canvas = canvas
        self._worker.start()

    def _on_progress(self, v: int):
        self._bar.setValue(v)
        self._lbl_pct.setText(f"{v}%")
        if v < 90:
            self._lbl.setText("Extrayendo frames…")
        else:
            self._lbl.setText("Extrayendo audio…")

    def _on_finished(self, audio_path: str):
        if audio_path:
            self._canvas.animation.audio_path = audio_path
        self._bar.setValue(100)
        self._lbl_pct.setText("100%")
        self.accept()

    def _on_error(self, msg: str):
        QMessageBox.critical(self, "Error al importar video", msg)
        self.reject()
