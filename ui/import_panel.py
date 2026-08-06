"""
ImportPanel — eliminado del layout visual.
Se mantiene como stub para no romper imports en otros módulos.
"""
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import pyqtSignal


class ImportPanel(QWidget):
    image_import_requested    = pyqtSignal(str)
    audio_import_requested    = pyqtSignal(str)
    video_import_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.hide()

    def _pick_image(self):
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Image", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.webp *.tiff)")
        if path:
            self.image_import_requested.emit(path)

    def _pick_audio(self):
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Audio", "",
            "Audio (*.mp3 *.wav *.ogg *.flac *.aac)")
        if path:
            self.audio_import_requested.emit(path)

    def _pick_video(self):
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Video", "",
            "Video (*.mp4 *.avi *.mov *.mkv *.webm)")
        if path:
            self.video_import_requested.emit(path)