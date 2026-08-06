"""
Paleta de colores recientes — se muestra debajo del swatch.
"""

from PyQt6.QtWidgets import QWidget, QGridLayout
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen


class ColorSwatch(QWidget):
    """Un cuadrado de color clickeable."""
    clicked = pyqtSignal(int, int, int, int)  # r, g, b, a

    def __init__(self, r=0, g=0, b=0, a=255, parent=None):
        super().__init__(parent)
        self.setFixedSize(16, 16)
        self._r, self._g, self._b, self._a = r, g, b, a
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(f"RGB({r},{g},{b})")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Tablero para transparencia
        for row in range(2):
            for col in range(2):
                c = QColor(180, 180, 180) if (row+col) % 2 == 0 \
                    else QColor(220, 220, 220)
                painter.fillRect(col*8, row*8, 8, 8, c)
        painter.setBrush(QBrush(QColor(self._r, self._g,
                                       self._b, self._a)))
        painter.setPen(QPen(QColor(80, 80, 80), 1))
        painter.drawRoundedRect(0, 0, 15, 15, 2, 2)
        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._r, self._g, self._b, self._a)


class RecentColorsPanel(QWidget):
    """Grid 4×3 de colores recientes."""
    color_selected = pyqtSignal(int, int, int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(54)
        self._layout = QGridLayout(self)
        self._layout.setContentsMargins(2, 2, 2, 2)
        self._layout.setSpacing(2)
        self._swatches: list[ColorSwatch] = []

    def update_colors(self, colors: list):
        """Recibe lista de [r,g,b,a] y actualiza el grid."""
        # Limpiar
        for sw in self._swatches:
            self._layout.removeWidget(sw)
            sw.deleteLater()
        self._swatches.clear()

        for i, c in enumerate(colors[:12]):
            r, g, b, a = c
            sw = ColorSwatch(r, g, b, a)
            sw.clicked.connect(self.color_selected.emit)
            row = i // 4
            col = i % 4
            self._layout.addWidget(sw, row, col)
            self._swatches.append(sw)