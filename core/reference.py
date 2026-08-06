"""
Imagen de referencia — visible en el canvas pero no exportable.
No pertenece a ninguna capa ni frame.
"""

from PyQt6.QtGui import QImage, QPainter, QColor
from PyQt6.QtCore import Qt, QRect, QPoint
import numpy as np


class ReferenceImage:
    def __init__(self):
        self.image:   QImage | None = None
        self.visible: bool          = True
        self.opacity: float         = 0.5    # 0.0 - 1.0
        self.x:       int           = 0
        self.y:       int           = 0
        self._dragging: bool        = False
        self._drag_offset: QPoint   = QPoint(0, 0)

    @property
    def active(self) -> bool:
        return self.image is not None and self.visible

    def load(self, path: str, canvas_w: int, canvas_h: int) -> bool:
        """Carga imagen y la escala para caber en el canvas."""
        img = QImage(path)
        if img.isNull():
            return False

        # Escalar manteniendo proporción si excede el canvas
        if img.width() > canvas_w or img.height() > canvas_h:
            img = img.scaled(
                canvas_w, canvas_h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)

        self.image = img.convertToFormat(
            QImage.Format.Format_ARGB32_Premultiplied)

        # Centrar en el canvas
        self.x = (canvas_w  - self.image.width())  // 2
        self.y = (canvas_h  - self.image.height()) // 2
        return True

    def clear(self):
        self.image = None

    def draw(self, painter: QPainter, zoom: float, offset: QPoint):
        """Dibuja la referencia en el painter del CanvasWidget."""
        if not self.active:
            return

        dx = int(self.x * zoom + offset.x())
        dy = int(self.y * zoom + offset.y())
        dw = int(self.image.width()  * zoom)
        dh = int(self.image.height() * zoom)

        painter.setOpacity(self.opacity)
        painter.setCompositionMode(
            QPainter.CompositionMode.CompositionMode_SourceOver)
        painter.drawImage(QRect(dx, dy, dw, dh), self.image)
        painter.setOpacity(1.0)

        # Borde punteado para indicar que es referencia
        if self._dragging:
            from PyQt6.QtGui import QPen
            from PyQt6.QtCore import Qt as QtCore
            pen = QPen(QColor(255, 200, 0, 180), 1,
                       QtCore.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(QtCore.BrushStyle.NoBrush)
            painter.drawRect(QRect(dx, dy, dw, dh))

    def rect_in_canvas(self) -> QRect | None:
        if self.image is None:
            return None
        return QRect(self.x, self.y,
                     self.image.width(), self.image.height())

    def contains(self, canvas_pt: QPoint) -> bool:
        r = self.rect_in_canvas()
        return r is not None and r.contains(canvas_pt)

    def start_drag(self, canvas_pt: QPoint):
        self._dragging     = True
        self._drag_offset  = QPoint(
            canvas_pt.x() - self.x,
            canvas_pt.y() - self.y)

    def drag_to(self, canvas_pt: QPoint):
        if self._dragging:
            self.x = canvas_pt.x() - self._drag_offset.x()
            self.y = canvas_pt.y() - self._drag_offset.y()

    def end_drag(self):
        self._dragging = False