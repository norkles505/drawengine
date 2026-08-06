from PyQt6.QtGui import QImage, QPainter, QColor
from PyQt6.QtCore import Qt
import numpy as np
from core.tools import BlendMode


class Layer:
    def __init__(self, width: int, height: int, name: str = "Layer"):
        self.name       = name
        self.visible    = True
        self.opacity    = 255
        self.blend_mode = BlendMode.NORMAL
        self.image      = QImage(
            width, height, QImage.Format.Format_ARGB32_Premultiplied)
        self.image.fill(Qt.GlobalColor.transparent)
        self.width  = width
        self.height = height

    def clear(self):
        self.image.fill(Qt.GlobalColor.transparent)

    def get_numpy(self) -> np.ndarray:
        ptr = self.image.bits()
        ptr.setsize(self.image.sizeInBytes())
        arr = np.array(ptr, dtype=np.uint8).reshape(
            self.height, self.width, 4)
        return arr.copy()

    def set_numpy(self, arr: np.ndarray):
        result = QImage(
            arr.tobytes(), self.width, self.height,
            QImage.Format.Format_ARGB32_Premultiplied)
        painter = QPainter(self.image)
        painter.setCompositionMode(
            QPainter.CompositionMode.CompositionMode_Source)
        painter.drawImage(0, 0, result)
        painter.end()