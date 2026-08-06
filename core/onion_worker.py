"""
Worker que pre-calcula los frames de onion skinning
en un hilo separado para no bloquear la UI.
"""

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QImage, QPainter
import numpy as np


class OnionWorker(QThread):
    """
    Computa los frames fantasma del onion skin fuera del hilo principal.
    Emite `done` con la imagen resultante lista para pintar.
    """
    done = pyqtSignal(QImage)   # imagen onion compuesta lista

    def __init__(self, animation, canvas_w: int, canvas_h: int,
                 cur_index: int,
                 prev_count: int, next_count: int,
                 opacity_first: float, opacity_last: float,
                 color_past: tuple, color_future: tuple):
        super().__init__()
        self.animation     = animation
        self.w             = canvas_w
        self.h             = canvas_h
        self.cur           = cur_index
        self.prev_count    = prev_count
        self.next_count    = next_count
        self.op_first      = opacity_first
        self.op_last       = opacity_last
        self.color_past    = color_past    # (r, g, b)
        self.color_future  = color_future
        self._cancelled    = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        result = QImage(self.w, self.h,
                        QImage.Format.Format_ARGB32_Premultiplied)
        result.fill(0)   # transparente
        painter = QPainter(result)
        painter.setCompositionMode(
            QPainter.CompositionMode.CompositionMode_SourceOver)

        total = len(self.animation.frames)
        all_offsets = []

        # Pasado
        for i in range(self.prev_count, 0, -1):
            all_offsets.append((-i, self.color_past))
        # Futuro
        for i in range(1, self.next_count + 1):
            all_offsets.append((+i, self.color_future))

        for offset, color in all_offsets:
            if self._cancelled:
                painter.end()
                return
            idx = self.cur + offset
            if not (0 <= idx < total):
                continue

            # Calcular opacidad degradada
            steps = max(self.prev_count, self.next_count, 1)
            t = (abs(offset) - 1) / max(steps - 1, 1) if steps > 1 else 0
            opacity = self.op_first * (1 - t) + self.op_last * t
            opacity = max(0.01, opacity / 100.0)

            ghost  = self._composite_frame(idx)
            tinted = self._tint(ghost, color, opacity)
            painter.drawImage(0, 0, tinted)

        painter.end()
        if not self._cancelled:
            self.done.emit(result)

    def _composite_frame(self, index: int) -> QImage:
        img = QImage(self.w, self.h,
                     QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(0)
        painter = QPainter(img)
        for layer in self.animation.frames[index].layers:
            if layer.visible:
                painter.setOpacity(layer.opacity / 255.0)
                painter.drawImage(0, 0, layer.image)
        painter.end()
        return img

    def _tint(self, image: QImage, color: tuple,
              opacity: float) -> QImage:
        r, g, b = color
        ptr = image.bits()
        ptr.setsize(image.sizeInBytes())
        arr = np.frombuffer(ptr, dtype=np.uint8).reshape(
            self.h, self.w, 4).copy()
        mask = arr[:, :, 3] > 10
        arr[mask, 0] = b   # BGRA
        arr[mask, 1] = g
        arr[mask, 2] = r
        arr[mask, 3] = np.clip(
            arr[mask, 3].astype(float) * opacity,
            0, 255).astype(np.uint8)
        return QImage(
            arr.tobytes(), self.w, self.h,
            QImage.Format.Format_ARGB32_Premultiplied)